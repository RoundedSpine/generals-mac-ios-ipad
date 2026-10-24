#pragma once

// GeneralsX @feature Codex 25/10/2026 Bounded, allocation-free hitch timings for Unix device diagnosis.
#ifdef _UNIX
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <functional>
#include <thread>

class SlowOperationTrace
{
    using Clock = std::chrono::steady_clock;
    const char* Phase;
    char Detail[160];
    Clock::time_point Start;
    double Threshold;
    bool Finished;
public:
    explicit SlowOperationTrace(const char* phase, const char* detail = nullptr, double thresholdMs = 50.0)
        : Phase(phase), Start(Clock::now()), Threshold(thresholdMs), Finished(false)
    {
        Detail[0] = '\0';
        if (detail != nullptr) {
            std::strncpy(Detail, detail, sizeof(Detail) - 1);
            Detail[sizeof(Detail) - 1] = '\0';
        }
    }
    SlowOperationTrace(const SlowOperationTrace&) = delete;
    SlowOperationTrace& operator=(const SlowOperationTrace&) = delete;
    ~SlowOperationTrace() { Finish(); }
    void Finish()
    {
        if (Finished) return;
        Finished = true;
        const auto end = Clock::now();
        const double elapsed = std::chrono::duration<double, std::milli>(end - Start).count();
        if (elapsed < Threshold) return;
        static std::atomic<unsigned> records{0};
        const unsigned record = records.fetch_add(1, std::memory_order_relaxed);
        if (record < 1024) {
            const auto tick = std::chrono::duration_cast<std::chrono::milliseconds>(end.time_since_epoch()).count();
            const size_t thread = std::hash<std::thread::id>{}(std::this_thread::get_id());
            std::fprintf(stderr, "[HITCH] t=%lld thread=%zu phase=%s ms=%.2f detail='%s'\n",
                         static_cast<long long>(tick), thread, Phase, elapsed, Detail);
        } else if (record == 1024) {
            std::fprintf(stderr, "[HITCH] timing record limit reached; further timing messages suppressed\n");
        }
    }
};
#else
// Keep legacy Windows builds free of C++ threading/chrono dependencies.
class SlowOperationTrace
{
public:
    explicit SlowOperationTrace(const char*, const char* = nullptr, double = 50.0) {}
    void Finish() {}
};
#endif
