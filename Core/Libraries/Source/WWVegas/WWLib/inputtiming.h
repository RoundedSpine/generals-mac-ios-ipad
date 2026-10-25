#pragma once

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdint>

// GeneralsX @feature Codex 25/10/2026 Correlate SDL delivery and mouse queue delays with hitch timestamps.
// now/source use SDL's nanosecond clock; t uses the same steady clock as SlowOperationTrace.
// source=0 means unknown. Never interpret a future timestamp as an unsigned delay.
inline void TraceInputTiming(const char* phase, unsigned type, uint64_t source,
                             uint64_t now, unsigned depth, bool force = false, int state = -1)
{
    const double age = source != 0 && now >= source ? double(now - source) / 1000000.0 : -1.0;
    if (!force && age < 50.0) return;
    static std::atomic<unsigned> records{0};
    const unsigned record = records.fetch_add(1, std::memory_order_relaxed);
    if (record < 2048) {
        const auto tick = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        std::fprintf(stderr, "[INPUT] t=%lld phase=%s type=%u source_ns=%llu age_ms=%.2f depth=%u state=%d\n",
                     static_cast<long long>(tick), phase, type,
                     static_cast<unsigned long long>(source), age, depth, state);
    } else if (record == 2048) {
        std::fprintf(stderr, "[INPUT] timing record limit reached; further input messages suppressed\n");
    }
}
