#pragma once

// GeneralsX @feature Codex 28/10/2026 Explain the first ordinary-prediction guard without repeating live engine queries.
enum class PathPredictionReason {
 Accepted, NotWaiting, Safe, Approach, Attack, Blocked, NonFinal, Quick,
 ProductionExit, OutsideExtent, Count
};
