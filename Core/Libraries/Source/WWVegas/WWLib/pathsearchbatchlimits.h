#pragma once

// GeneralsX @feature Codex 31/10/2026 Keep logical result capacity independent of the unchanged physical participant count.
namespace PathSearchBatchLimits {
#ifdef GENERALS_ZH_PATH_FOUR_REQUESTS
inline constexpr unsigned capacity=4;
#else
inline constexpr unsigned capacity=2;
#endif
}
