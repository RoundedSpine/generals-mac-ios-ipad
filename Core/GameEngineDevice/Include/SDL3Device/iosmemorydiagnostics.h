#pragma once

#include <cstdio>
#include <cstdint>

// GeneralsX @feature Codex 31/10/2026 Report the running iOS process's signed memory capabilities once at startup.
namespace gxiosmemory {
// GeneralsX @feature Codex 01/11/2026 Optional engine counters share the throttled main-thread sampling cadence.
using ResourceSampler = void (*)(FILE*);
void setResourceSampler(ResourceSampler sampler);
// GeneralsX @feature Codex 01/11/2026 Allocation base pointers only; size includes native rounding and the engine block header.
size_t allocationSize(const void* allocation);
void logStartupCapabilities(FILE* output);
// GeneralsX @feature Codex 31/10/2026 Event delivery may be off-main; this only records an atomic warning count.
void noteLowMemoryWarning();
// Call only on the main thread. Sample every 30 seconds or on coalesced low-memory warnings.
void logRuntimeIfDue(FILE* output, uint64_t uptimeNS);
}
