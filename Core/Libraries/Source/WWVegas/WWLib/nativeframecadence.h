#pragma once
#include <cstdint>

// GeneralsX @feature Codex 25/10/2026 Gate native display callbacks without sleeping or catch-up loops.
class NativeFrameCadence
{
    uint64_t Last = 0, Next = 0;
    unsigned Rate = 0;
public:
    void Reset() { Last = Next = 0; Rate = 0; }
    bool Advance(uint64_t now, unsigned fps, double& elapsed)
    {
        const uint64_t period = fps > 0 && fps <= 1000000 ? 1000000000ull / fps : 0;
        if (Last && now < Last) Reset();
        const bool changed = fps != Rate;
        const uint64_t tolerance = period / 8 < 1000000 ? period / 8 : 1000000;
        if (Last && !changed && period && now < Next && Next - now > tolerance) return false;
        elapsed = Last ? double(now - Last) / 1000000000.0 : (period ? double(period) / 1000000000.0 : 1.0 / 60.0);
        Last = now;
        if (!period) Next = now;
        else if (!Next || changed) Next = now + period;
        else if (now < Next) Next += period;
        else Next += ((now - Next) / period + 1) * period;
        Rate = fps;
        return true;
    }
};
