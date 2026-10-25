#pragma once
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>

// GeneralsX @feature Codex 25/10/2026 Separate missing native callbacks from callbacks gated before update.
class NativeFrameTrace
{
    uint64_t First = 0, LastEntry = 0, LastExit = 0, LastUpdate = 0, LastNotice = 0;
    unsigned Entries = 0, Pauses = 0, CadenceSkips = 0;
    const char* Reason = "startup";
    unsigned Flags = 0;
    int Fps = 0;
    uint64_t Deadline = 0;
    static double Ms(uint64_t older, uint64_t newer) {
        return older && newer >= older ? double(newer - older) / 1000000.0 : -1.0;
    }
    void Log(const char* phase, uint64_t now, double entryGap = -1, double outside = -1)
    {
        static std::atomic<unsigned> records{0};
        const unsigned record = records.fetch_add(1, std::memory_order_relaxed);
        if (record < 256) {
            const auto tick = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now().time_since_epoch()).count();
            std::fprintf(stderr,
                "[NATIVE_FRAME] t=%lld phase=%s now_ns=%llu reason=%s pause_bits=%u fps=%d deadline_ns=%llu entry_gap_ms=%.2f outside_ms=%.2f update_gap_ms=%.2f callbacks=%u paused=%u cadence_skips=%u\n",
                static_cast<long long>(tick), phase, static_cast<unsigned long long>(now), Reason, Flags, Fps,
                static_cast<unsigned long long>(Deadline), entryGap, outside, Ms(LastUpdate ? LastUpdate : First, now),
                Entries, Pauses, CadenceSkips);
        } else if (record == 256) {
            std::fprintf(stderr, "[NATIVE_FRAME] record limit reached; further frame messages suppressed\n");
        }
    }
public:
    void Reset() { First = LastEntry = LastExit = LastUpdate = LastNotice = 0; Entries = Pauses = CadenceSkips = 0; Reason = "startup"; Flags = 0; Fps = 0; Deadline = 0; }
    void Enter(uint64_t now)
    {
        if (!First) First = now;
        ++Entries;
        if (Ms(LastEntry, now) >= 100.0) Log("callback-gap", now, Ms(LastEntry, now), Ms(LastExit, now));
        LastEntry = now;
        Reason = "entry";
    }
    void Exit(uint64_t now)
    {
        if (Ms(LastEntry, now) >= 100.0) Log("callback-long", now, Ms(LastEntry, now), 0.0);
        LastExit = now;
    }
    void Mark(const char* reason) { Reason = reason; }
    void Gate(uint64_t now, bool paused, unsigned flags, int fps, uint64_t deadline)
    {
        const bool transition = Flags != flags;
        Reason = paused ? "lifecycle" : "cadence";
        Flags = flags; Fps = fps; Deadline = deadline;
        if (paused) ++Pauses; else ++CadenceSkips;
        const bool stalled = Ms(LastUpdate ? LastUpdate : First, now) >= 100.0;
        if (transition || (stalled && (!LastNotice || Ms(LastNotice, now) >= 1000.0))) {
            Log(transition ? "gate-change" : "update-skipped", now);
            LastNotice = now;
        }
    }
    void Update(uint64_t now, unsigned flags, int fps, uint64_t deadline)
    {
        Flags = flags; Fps = fps; Deadline = deadline;
        if (Ms(LastUpdate ? LastUpdate : First, now) >= 100.0) Log("update-resumed", now);
        LastUpdate = now; LastNotice = 0;
        Entries = Pauses = CadenceSkips = 0;
        Reason = "engine-update";
    }
    class Scope {
        NativeFrameTrace& Trace;
        uint64_t (*Clock)();
    public:
        Scope(NativeFrameTrace& trace, uint64_t (*clock)()) : Trace(trace), Clock(clock) { Trace.Enter(Clock()); }
        ~Scope() { Trace.Exit(Clock()); Trace.LastExit = Clock(); }
        Scope(const Scope&) = delete;
        Scope& operator=(const Scope&) = delete;
    };
};

inline void TraceNativeLifecycle(unsigned type, unsigned flags, uint64_t now)
{
    static std::atomic<unsigned> records{0};
    const unsigned record = records.fetch_add(1, std::memory_order_relaxed);
    if (record < 64) {
        const auto tick = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        std::fprintf(stderr, "[NATIVE_LIFECYCLE] t=%lld now_ns=%llu type=%u pause_bits=%u\n",
                     static_cast<long long>(tick), static_cast<unsigned long long>(now), type, flags);
    } else if (record == 64) {
        std::fprintf(stderr, "[NATIVE_LIFECYCLE] record limit reached; further lifecycle messages suppressed\n");
    }
}
