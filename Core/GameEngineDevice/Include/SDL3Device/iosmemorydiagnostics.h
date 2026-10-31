#pragma once

#include <cstdio>

// GeneralsX @feature Codex 31/10/2026 Report the running iOS process's signed memory capabilities once at startup.
namespace gxiosmemory {
void logStartupCapabilities(FILE* output);
}
