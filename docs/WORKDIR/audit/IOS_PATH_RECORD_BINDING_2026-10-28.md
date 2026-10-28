# Compact pathfinding record bindings — 28 October 2026

## Scope

Follow the device admission review with a small storage/hot-access improvement.
The experimental context used one context pointer, one slot number and a separate
admission Boolean in every PathfindCellInfo. Every search() access called the
context's generation-aware get(slot), although allocateRecord had already reset
that slot and the record pool independently gates lookup by generation.

Bind each live private record to its stable PathfindSearchState address at
allocation instead. Pack the charged-admission bit alongside existing flags.
Permanent records retain separate free-list links and a null search-state pointer;
they do not acquire private state. The disabled search-context path keeps its
original inline state/free-list alias and layout.

This is a first metadata compaction step, not Reimagined's compact search-only
node rewrite. The private pool still stores PathfindCellInfo, including permanent
fields unused by searches; the separate stamped state arena and keyed lookup
remain. No eligibility, worker count, validation policy, search limits, queue
accounting, zone recalculation or graphics behavior changes.

## Lifetime and reset invariants

Both record and state arenas are fixed arrays. PathfindSearchContext is already
noncopyable/nonmovable through its bounded pool, and speculative contexts remain
at stable heap addresses until their joined jobs are destroyed. No bound state
pointer refers to a stack temporary or relocatable vector.

allocateRecord obtains a record slot, resets that same state slot and publishes
its address before returning the record. Explicit resetSlot now initializes the
state once, sets its stamp and returns its address; it no longer calls lazy get
and then assigns a second default state on the first access of a generation.
Other get callers retain lazy reset and rollover behavior.

releaseRecord clears the bound state before freeing its keyed record. A released
slot is reset again before reuse. beginSearch invalidates keyed lookup and state
generations together; old record pointers are not valid search handles. All
production generation boundaries were reviewed: normal boundaries clean lists;
speculative reset/reuse clears lists; failover resets them before further use.
Accepted worker parent chains remain owned by their joined job during main-side
finalization. No state pointer is transferred to another context or stored in a
live map cell.

## Local storage and controlled comparison

On the local GCC 14 64-bit fixture ABI, sizeof(PathfindCellInfo) falls from 72 to
56 bytes; PathfindSearchState stays 48 bytes. Each 30,000-record pool therefore
saves exactly 480,000 bytes. Four allocated speculative phase contexts save
1,920,000 bytes (1.83 MiB). The main context and permanent pool additionally save
960,000 bytes, giving 2.75 MiB across all six pools when both optional fallback
contexts exist. Actual iOS resident memory is not measured by these sizes.

The standalone context fixture without parallel-read metadata falls from
4,724,488 to 4,244,488 bytes. This fixture size excludes the parallel-read pointer,
job/read logs, corridor vectors, heap capacity and worker stack; it is not the
complete application's pathfinding footprint.

A controlled optimized comparison compiles actual cell/allocation/list methods
before and after the change with GCC 14, C++17 and -O2, using 2,000 deterministic
24-by-24 grid searches. Both versions and the context-disabled baseline produce
hash 15686256079113737780. Local timings are workload/host dependent, include
setup/cleanup and are not native game search benchmarks or iOS speedup evidence.
The reliable improvements established here are reduced storage and removal of
owner/slot generation lookup from live record search() access.

## Validation and remaining work

Three new tests check single-initialization explicit resets through an 8-bit
generation rollover, smaller production record layout with immovable contexts,
and direct-state cleanup across 600 record-recycling/search-generation cycles.
Existing fixtures now bind to the actual production direct-state field; permanent
metadata tests verify that its pointer stays null. Actual cell/list route
comparisons still exercise both enabled and disabled modes. Worker/batch tests
exercise independent contexts, ordered results, stale rejection and fallbacks.

All 187 local workflow QA tests pass, including all 66 batch cases and enabled/
disabled route comparisons. All 66 batch cases and all five context-ownership
cases pass ThreadSanitizer. All 20 context/record cases pass ASan/UBSan, including
the three added tests. Diff checks pass. These fixtures use controlled world and
Path services; they do not establish full-engine replay equivalence or a device
performance gain.

Native SDK packaging and device gameplay verification require the new IPA.
Keep existing diagnostics for the next device session; compare large-search
and queue outliers without inferring a gain from unmatched gameplay sessions.
Per-result rejection/outlier correlation, compact search-only records and zone
cost investigations remain separate work.
