// GeneralsX @feature Codex 31/10/2026 Inspect runtime entitlements, never the build-side plist or provisioning permissions alone.
#include "SDL3Device/iosmemorydiagnostics.h"

#include <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>
#include <mach/mach.h>
#include <os/proc.h>
#include <sys/sysctl.h>
#include <cstdint>

namespace {
constexpr double kMiB = 1024.0 * 1024.0;

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
    fprintf(output, "[IOS_MEMORY] available_process_mib=%.1f footprint_mib=%s physical_device_mib=%s sample=startup\n",
        static_cast<double>(available) / kMiB, footprintMiB, physicalMiB);
}
