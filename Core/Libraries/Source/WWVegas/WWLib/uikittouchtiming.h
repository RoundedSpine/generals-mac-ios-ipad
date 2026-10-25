#pragma once
#include "iosuikittouchprobe.h"
#include <atomic>
#include <chrono>
#include <cstdio>
#include <mutex>

// GeneralsX @feature Codex 25/10/2026 Preserve native callback timing for comparison at the SDL poll boundary.
class UIKitTouchTiming
{
    static constexpr unsigned Capacity = 2048;
    struct Slot { GXUIKitTouchSample sample{}; bool valid = false; } Slots[Capacity];
    unsigned Next = 0, Count = 0;
    uint64_t Overwritten = 0;
    std::mutex Mutex;
public:
    void Record(const GXUIKitTouchSample& sample)
    {
        std::lock_guard<std::mutex> lock(Mutex);
        if (Slots[Next].valid) ++Overwritten;
        Slots[Next].sample = sample;
        Slots[Next].valid = true;
        Next = (Next + 1) % Capacity;
        if (Count < Capacity) ++Count;
    }
    bool Take(unsigned type, uint64_t source, uint64_t finger,
              GXUIKitTouchSample& result, uint64_t& overwritten)
    {
        std::lock_guard<std::mutex> lock(Mutex);
        overwritten = Overwritten;
        const unsigned first = (Next + Capacity - Count) % Capacity;
        for (unsigned offset = 0; offset < Count; ++offset) {
            Slot& slot = Slots[(first + offset) % Capacity];
            if (slot.valid && slot.sample.type == type && slot.sample.source_ns == source &&
                slot.sample.finger == finger) {
                result = slot.sample;
                slot.valid = false;
                return true;
            }
        }
        return false;
    }
};

inline double UIKitNativeAgeMs(double timestamp, double uptime)
{
    return timestamp > 0.0 && uptime >= timestamp ? (uptime - timestamp) * 1000.0 : -1.0;
}

inline void TraceUIKitTouchTiming(const GXUIKitTouchSample* sample, unsigned type,
                                 uint64_t source, uint64_t polled, uint64_t arrival,
                                 uint64_t overwritten, bool edge)
{
    const double eventAge = sample ? UIKitNativeAgeMs(sample->event_timestamp, sample->callback_uptime) : -1.0;
    const double touchAge = sample ? UIKitNativeAgeMs(sample->touch_timestamp, sample->callback_uptime) : -1.0;
    const double convertedAge = sample && source && sample->callback_ns >= source
        ? double(sample->callback_ns - source) / 1000000.0 : -1.0;
    const double toWatch = sample && arrival >= sample->callback_ns
        ? double(arrival - sample->callback_ns) / 1000000.0 : -1.0;
    if (!edge && sample && eventAge < 50.0 && touchAge < 50.0 && convertedAge < 50.0 && toWatch < 50.0) return;
    static std::atomic<unsigned> records{0};
    const unsigned record = records.fetch_add(1, std::memory_order_relaxed);
    if (record < 256) {
        const auto tick = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        std::fprintf(stderr,
            "[UIKIT_TOUCH] t=%lld type=%u source_ns=%llu callback_ns=%llu poll_ns=%llu matched=%d kind=%d uptime=%.9f event_time=%.9f touch_time=%.9f event_age_ms=%.2f touch_age_ms=%.2f converted_age_ms=%.2f callback_to_watch_ms=%.2f overwritten=%llu\n",
            static_cast<long long>(tick), type, static_cast<unsigned long long>(source),
            static_cast<unsigned long long>(sample ? sample->callback_ns : 0),
            static_cast<unsigned long long>(polled), sample ? 1 : 0, sample ? sample->touch_kind : -1,
            sample ? sample->callback_uptime : -1.0, sample ? sample->event_timestamp : -1.0,
            sample ? sample->touch_timestamp : -1.0, eventAge, touchAge, convertedAge, toWatch,
            static_cast<unsigned long long>(overwritten));
    } else if (record == 256) {
        std::fprintf(stderr, "[UIKIT_TOUCH] timing record limit reached; further native messages suppressed\n");
    }
}
