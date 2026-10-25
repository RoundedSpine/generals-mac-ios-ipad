#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <mutex>

// GeneralsX @feature Codex 25/10/2026 Record SDL watch arrival without writing logs on the delivery thread.
// This stores diagnostics only. Event contents, ordering and dispatch stay owned by SDL.
class TouchQueueTiming
{
public:
    struct Entry {
        unsigned type = 0;
        uint64_t source = 0, finger = 0, touch = 0, arrival = 0, sequence = 0;
        bool valid = false;
    };
private:
    static constexpr unsigned Capacity = 2048;
    Entry Entries[Capacity];
    unsigned Next = 0, Count = 0;
    uint64_t Sequence = 0, Overwritten = 0;
    std::mutex Mutex;
public:
    void Record(unsigned type, uint64_t source, uint64_t finger, uint64_t touch, uint64_t arrival)
    {
        std::lock_guard<std::mutex> lock(Mutex);
        if (Entries[Next].valid) ++Overwritten;
        Entries[Next] = {type, source, finger, touch, arrival, ++Sequence, true};
        Next = (Next + 1) % Capacity;
        if (Count < Capacity) ++Count;
    }
    bool Take(unsigned type, uint64_t source, uint64_t finger, uint64_t touch,
              Entry& result, uint64_t& overwritten)
    {
        std::lock_guard<std::mutex> lock(Mutex);
        overwritten = Overwritten;
        // Consume the oldest identical key, including events sharing an OS timestamp.
        const unsigned first = (Next + Capacity - Count) % Capacity;
        for (unsigned offset = 0; offset < Count; ++offset) {
            Entry& entry = Entries[(first + offset) % Capacity];
            if (entry.valid && entry.type == type && entry.source == source &&
                entry.finger == finger && entry.touch == touch) {
                result = entry;
                entry.valid = false;
                return true;
            }
        }
        return false;
    }
};

inline double TouchQueueAgeMs(uint64_t earlier, uint64_t later)
{
    return earlier != 0 && later >= earlier ? double(later - earlier) / 1000000.0 : -1.0;
}

// Separate output budget: old INPUT records exhausting their cap must not hide this boundary.
// Called on the polling thread only, after releasing the diagnostic mutex.
inline void TraceTouchQueueTiming(const TouchQueueTiming::Entry* entry, unsigned type,
                                 uint64_t source, uint64_t polled, uint64_t overwritten, bool edge)
{
    const double sourceAge = TouchQueueAgeMs(source, polled);
    const double beforeQueue = entry ? TouchQueueAgeMs(source, entry->arrival) : -1.0;
    const double inQueue = entry ? TouchQueueAgeMs(entry->arrival, polled) : -1.0;
    if (!edge && entry && sourceAge < 50.0 && inQueue < 50.0) return;
    static std::atomic<unsigned> records{0};
    const unsigned record = records.fetch_add(1, std::memory_order_relaxed);
    if (record < 512) {
        const auto tick = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        std::fprintf(stderr,
            "[TOUCH_QUEUE] t=%lld type=%u source_ns=%llu arrival_ns=%llu poll_ns=%llu seq=%llu matched=%d prequeue_ms=%.2f queue_ms=%.2f source_age_ms=%.2f overwritten=%llu\n",
            static_cast<long long>(tick), type, static_cast<unsigned long long>(source),
            static_cast<unsigned long long>(entry ? entry->arrival : 0),
            static_cast<unsigned long long>(polled),
            static_cast<unsigned long long>(entry ? entry->sequence : 0), entry ? 1 : 0,
            beforeQueue, inQueue, sourceAge, static_cast<unsigned long long>(overwritten));
    } else if (record == 512) {
        std::fprintf(stderr, "[TOUCH_QUEUE] timing record limit reached; further queue messages suppressed\n");
    }
}
