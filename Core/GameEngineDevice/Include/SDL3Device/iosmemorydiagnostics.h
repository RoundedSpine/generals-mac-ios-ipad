#pragma once

#include <cstdio>
#include <cstdint>

// GeneralsX @feature Codex 31/10/2026 Report the running iOS process's signed memory capabilities once at startup.
namespace gxiosmemory {
void logStartupCapabilities(FILE* output);
// GeneralsX @feature Codex 31/10/2026 Event delivery may be off-main; this only records an atomic warning count.
void noteLowMemoryWarning();
// Call only on the main thread. Sample every 30 seconds or on coalesced low-memory warnings.
void logRuntimeIfDue(FILE* output, uint64_t uptimeNS);
}
