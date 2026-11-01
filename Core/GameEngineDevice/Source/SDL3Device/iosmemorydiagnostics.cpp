// GeneralsX @feature Codex 31/10/2026 Inspect runtime entitlements, never the build-side plist or provisioning permissions alone.
#include "SDL3Device/iosmemorydiagnostics.h"

#include <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>
#include <mach/mach.h>
#include <malloc/malloc.h>
#include <objc/runtime.h>
#include <os/proc.h>
#include <sys/sysctl.h>
#include <cstdint>
#include <atomic>

namespace {
constexpr double kMiB = 1024.0 * 1024.0;
// GeneralsX @feature Codex 31/10/2026 Keep periodic diagnostics cheap; warning delivery never performs OS queries or I/O.
constexpr uint64_t kSampleIntervalNS = 30ull * 1000000000ull;
constexpr uint64_t kWarningIntervalNS = 1000000000ull;
std::atomic<unsigned> s_pendingWarnings{0};
bool s_runtimeSampled = false;
bool s_warningSampled = false;
uint64_t s_lastSampleNS = 0;
uint64_t s_lastWarningNS = 0;
uint64_t s_warningCount = 0;
gxiosmemory::ResourceSampler s_resourceSampler = nullptr;

// GeneralsX @feature Codex 01/11/2026 Query public Metal device accounting without a GPU wait, resource purge or retained device.
void logAllocationBreakdown(FILE* output)
{
    malloc_statistics_t heap = {};
    malloc_zone_statistics(nullptr, &heap); // nullptr aggregates every registered malloc zone.
    char metalMiB[32] = "unknown";
    const char* metalStatus = "api_unavailable";
    void* metal = dlopen("/System/Library/Frameworks/Metal.framework/Metal", RTLD_LAZY | RTLD_LOCAL);
    if (metal != nullptr) {
        using CreateDevice = id (*)();
        auto create = reinterpret_cast<CreateDevice>(dlsym(metal, "MTLCreateSystemDefaultDevice"));
        if (create != nullptr) {
            id device = create(); // Create returns an owned reference, even without ARC.
            metalStatus = "device_unavailable";
            if (device != nullptr) {
                Class cls = object_getClass(device);
                SEL sizeSelector = sel_registerName("currentAllocatedSize");
                metalStatus = "counter_unavailable";
                if (class_respondsToSelector(cls, sizeSelector)) {
                    using ReadSize = unsigned long (*)(id, SEL);
                    auto readSize = reinterpret_cast<ReadSize>(class_getMethodImplementation(cls, sizeSelector));
                    snprintf(metalMiB, sizeof(metalMiB), "%.1f", static_cast<double>(readSize(device, sizeSelector)) / kMiB);
                    metalStatus = "ok";
                }
                SEL releaseSelector = sel_registerName("release");
                using Release = void (*)(id, SEL);
                reinterpret_cast<Release>(class_getMethodImplementation(cls, releaseSelector))(device, releaseSelector);
            }
        }
        dlclose(metal);
    }
    // Malloc, Metal, engine payload and footprint categories overlap: never add them together.
    fprintf(output, "[IOS_MEMORY_BREAKDOWN] malloc_in_use_mib=%.1f malloc_reserved_mib=%.1f metal_allocated_mib=%s metal_status=%s categories=overlap\n",
        static_cast<double>(heap.size_in_use) / kMiB, static_cast<double>(heap.size_allocated) / kMiB, metalMiB, metalStatus);
}

// SecTask's self-query is not declared in the public iOS SDK. Resolve it optionally
// so an unavailable/restricted query cannot stop the game from launching.
using CreateTask = CFTypeRef (*)(CFAllocatorRef);
using CopyEntitlement = CFTypeRef (*)(CFTypeRef, CFStringRef, CFErrorRef*);

struct EntitlementValue {
    const char* value = "unknown";
    const char* status = "api_unavailable";
    long long error = 0;
};

EntitlementValue readEntitlement(CopyEntitlement copyValue, CFTypeRef task, CFStringRef key)
{
    CFErrorRef error = nullptr;
    CFTypeRef value = copyValue(task, key, &error);
    EntitlementValue result;
    if (error != nullptr) {
        result.status = "query_error";
        result.error = static_cast<long long>(CFErrorGetCode(error));
        CFRelease(error);
    } else if (value == nullptr) {
        result.value = "absent";
        result.status = "ok";
    } else if (CFGetTypeID(value) == CFBooleanGetTypeID()) {
        result.value = CFBooleanGetValue(static_cast<CFBooleanRef>(value)) ? "true" : "false";
        result.status = "ok";
    } else {
        result.status = "unexpected_type";
    }
    if (value != nullptr)
        CFRelease(value);
    return result;
}

void logSnapshot(FILE* output, const char* sample, uint64_t uptimeNS)
{
    // These are OS observations at this instant, not proof of a particular jetsam
    // limit or a promise that a true entitlement supplies a fixed amount of RAM.
    const size_t available = os_proc_available_memory();
    char footprintMiB[32] = "unknown";
    task_vm_info_data_t info = {};
    mach_msg_type_number_t count = TASK_VM_INFO_COUNT;
    if (task_info(mach_task_self(), TASK_VM_INFO, reinterpret_cast<task_info_t>(&info), &count) == KERN_SUCCESS &&
        count >= TASK_VM_INFO_REV1_COUNT) {
        snprintf(footprintMiB, sizeof(footprintMiB), "%.1f", static_cast<double>(info.phys_footprint) / kMiB);
    }
    char physicalMiB[32] = "unknown";
    uint64_t physical = 0;
    size_t length = sizeof(physical);
    if (sysctlbyname("hw.memsize", &physical, &length, nullptr, 0) == 0 && length == sizeof(physical))
        snprintf(physicalMiB, sizeof(physicalMiB), "%.1f", static_cast<double>(physical) / kMiB);
    fprintf(output, "[IOS_MEMORY] available_process_mib=%.1f footprint_mib=%s physical_device_mib=%s sample=%s uptime_s=%.3f low_memory_warnings=%llu\n",
        static_cast<double>(available) / kMiB, footprintMiB, physicalMiB, sample,
        static_cast<double>(uptimeNS) / 1000000000.0, static_cast<unsigned long long>(s_warningCount));
    logAllocationBreakdown(output);
    if (s_resourceSampler != nullptr) s_resourceSampler(output);
}
}

void gxiosmemory::setResourceSampler(ResourceSampler sampler)
{
    s_resourceSampler = sampler;
}

void gxiosmemory::logStartupCapabilities(FILE* output)
{
    EntitlementValue increased;
    EntitlementValue eva;
    void* security = dlopen("/System/Library/Frameworks/Security.framework/Security", RTLD_LAZY | RTLD_LOCAL);
    if (security != nullptr) {
        auto createTask = reinterpret_cast<CreateTask>(dlsym(security, "SecTaskCreateFromSelf"));
        auto copyValue = reinterpret_cast<CopyEntitlement>(dlsym(security, "SecTaskCopyValueForEntitlement"));
        if (createTask != nullptr && copyValue != nullptr) {
            CFTypeRef task = createTask(kCFAllocatorDefault);
            if (task != nullptr) {
                increased = readEntitlement(copyValue, task, CFSTR("com.apple.developer.kernel.increased-memory-limit"));
                eva = readEntitlement(copyValue, task, CFSTR("com.apple.developer.kernel.extended-virtual-addressing"));
                CFRelease(task);
            } else {
                increased.status = eva.status = "task_unavailable";
            }
        }
        dlclose(security);
    }
    fprintf(output, "[IOS_MEMORY_ENTITLEMENTS] source=running_process increased_memory_limit=%s extended_virtual_addressing=%s\n",
        increased.value, eva.value);
    fprintf(output, "[IOS_MEMORY_ENTITLEMENT_QUERY] increased_status=%s increased_error=%lld eva_status=%s eva_error=%lld\n",
        increased.status, increased.error, eva.status, eva.error);
    logSnapshot(output, "startup", 0);
}

void gxiosmemory::noteLowMemoryWarning()
{
    s_pendingWarnings.fetch_add(1, std::memory_order_relaxed);
}

void gxiosmemory::logRuntimeIfDue(FILE* output, uint64_t uptimeNS)
{
    const bool periodicDue = !s_runtimeSampled || uptimeNS < s_lastSampleNS || uptimeNS - s_lastSampleNS >= kSampleIntervalNS;
    const bool warningDue = s_pendingWarnings.load(std::memory_order_relaxed) != 0 &&
        (!s_warningSampled || uptimeNS < s_lastWarningNS || uptimeNS - s_lastWarningNS >= kWarningIntervalNS);
    if (!periodicDue && !warningDue)
        return;

    const unsigned warnings = s_pendingWarnings.exchange(0, std::memory_order_relaxed);
    s_warningCount += warnings;
    if (warnings != 0) {
        s_lastWarningNS = uptimeNS;
        s_warningSampled = true;
    }
    s_lastSampleNS = uptimeNS;
    s_runtimeSampled = true;
    logSnapshot(output, warnings != 0 ? "low_memory" : "periodic", uptimeNS);
}
