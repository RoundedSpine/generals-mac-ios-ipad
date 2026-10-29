# Current pathfinding versus Reimagined — 29 October 2026

## Scope and conclusion

Compare experiment/ios-mod-testing at runtime 32ccf4e30 directly with
the supplied ZeroHourReimagined_1.0.0_source. This is a pathfinding comparison;
Reimagined graphics and gameplay content remain outside this integration. This
supersedes the runtime snapshot in the 28 October comparison, while retaining
its historical evidence.

Our implementation has the reference's core speculative model: predict queued
requests, run independent searches concurrently with main participation, join,
validate, and consume once in queue order or recompute. Ordinary, safe, queued
closest and conditional closest-fallback kernels exist. The latest changes match
real ordinary/closest coarse preparation on main and deduplicate exact query and
height observations. They improve our preparation fidelity and result reuse.

The allocation-window change now accepts permanent-count differences only when
every reached allocation decision stays equivalent. The latest cell-rejection
change explains validation failures without changing acceptance or execution.

The largest remaining differences are full off-thread API execution, compact
search-only storage, broader dispatch, and different capacity/budget policies.
The reference is not simply our implementation with additional workers enabled.

## Current comparison

| Area | Current iOS branch | Supplied Reimagined source |
| --- | --- | --- |
| Candidate ordering | Stable binary heap, 64-bit insertion sequence, retained retail list fallback | Stable binary heap, 32-bit insertion sequence |
| Search state | Private records/lists/corridor, generation stamps, direct stable state pointers | Private search-only nodes/lists/corridor and generation stamps |
| Search kinds | Ordinary, safe, queued closest and conditional closest fallback; stricter prediction gates | Same API categories, broader ordinary prediction |
| Preparation | Real ordinary and closest hierarchy in private main-side contexts; authoritative caller repeats its own preparation | Whole search API runs in the participant's context; accepted completed Path returns before hierarchy is repeated |
| Off-thread scope | Fine loops; Path construction, optimization, hierarchy and recovery stay on main | Complete findPath/findClosestPath/findSafePath calls, including hierarchy and Path construction/optimization |
| Dispatch | Two adjacent eligible requests, one worker plus main | Scan eight upcoming requests, skip unsupported entries, share eligible jobs dynamically across pool and main |
| Worker count | One gameplay search worker | Automatic clamp(cores - 3, 0, 8), explicit override capped at 32 |
| Result storage | Separate retained primary/fallback phase contexts, up to four, holding loop outcomes and parent records until main finishes | Thread-local search context reused between jobs/phases; each result already owns a completed engine Path |
| Node lookup | Bounded keyed records plus separate state arena; metadata compacted to 56 bytes on the local 64-bit fixture ABI | Direct cell-index lookup into compact PathSearchNode arrays sized to registered map cells |
| Capacity | 30,000 records/context; allocation windows preserve every reached permanent/transient admission success and denial | Nonlegacy search nodes independent of permanent metadata; default node allowance is all registered cells, with testing override |
| Dependency checks | Explicit request, movement, preparation, admission, epochs/lifecycle, cells, corridor, live occupancy, height and bounded-log checks | Request/ignore/tunnel matching plus intersection between read-cell set and subsequent cell-write log |
| Read tracking | Bounded exact first-observation sets; query/height duplicates removed while actual reads still execute | Per-cell read marks deduplicate cell observations into a sorted cell-index set |
| Queue budget | Check the existing 5,000-cell budget after each actual request | In nonlegacy mode, check between groups of eight, even with runtime prefetch disabled |
| Wait behavior | Main runs one task then waits on a condition variable; joined exception/lifecycle handling and FP environment capture | Main shares dynamic chunks then yields until all finish; workers spin for 500 microseconds before sleeping, with x86 pause intrinsic |
| Zone rebuilding | Synchronous on main before queued searches | Also synchronous before prefetch/queued searches |
| Enablement | Experimental iOS workflow enables the options; defaults OFF elsewhere | Runtime PathfindPrefetch defaults FALSE and configuration can enable it |

## What changed since the previous comparison

The 28 October direct-state binding change removes repeated owner/slot resolution
and shrinks record metadata. It still keeps a record plus separate state rather
than adopting a search-only dense node. The ordinary corridor/read change then
fixes a demonstrated preparation difference and prevents duplicate observations
from consuming the 8,192-entry query/height bounds. The closest change captures
actual coarse success/failure and corridors instead of provisional success, and
owns completed coarse Paths through recovery cleanup.

These changes preserve one worker, adjacent pairing, existing bounds and original
per-request scheduling. Closest fallback preparation now does coarse work even
when an ordinary result later succeeds and that fallback never executes. The
reference only invokes its closest API after the preceding ordinary API fails.
That, plus repeating authoritative preparation and finalizing on main, is a real
remaining source of main-side work in our adaptation.

The record-count issue also follows from different allocation semantics. Our
allocator freezes permanent usage and combines it with private transient usage
when deciding whether another record fits. Validation now accepts a changed count
when it lies inside the intersection of all reached admission predicates,
including denied allocations. Completion uses the consuming caller's frozen
allowance. The reference's nonlegacy canActivateNode instead checks
its independent active-node count and map-sized allowance. takePrefetchedPath
has no equivalent global permanent-count equality test. Removing our guard
without accounting for changed admission decisions would not preserve our
current search behavior. Our allocation window preserves those decisions rather
than removing their dependency. Adopting its node limit would be a deliberate
capacity policy change, not a consequence of simply separating scratch state.

The latest diagnostic stage separates a changed cell snapshot from a full or
failed cell-read log. It identifies differing fields in the first unequal cell
using the existing single read. This adds visibility, not a faster search or a
larger off-thread scope. Its new device session identifies goal-owner changes
in all 22 cell first rejections, 20 also with metadata presence changes, and no
full or failed cell logs. It cannot
retroactively classify the preceding session's 26 cell failures.

## Device evidence and performance limits

The newest supplied device log is ~32ccf4e. It completes 748 pairs, reuses
1,426/1,464 primary phases (97.40%) and 31/32 closest fallback phases. Nine primary
and two fallback phases complete despite changed permanent usage, with zero
admission rejection. All fallback executions in this session are early fallbacks.
Queued closest runs 24 primary phases and reuses 15; safe and ordinary
fine-loop-failure fallback are not exercised here. The 38 primary first rejections
are cells 21, kind 12 and world epoch five; the one fallback rejection is cells.
All 22 cell first rejections contain changed goal-owner values, 20 also metadata
presence changes, with no full or failed cell logs. Ordered main-side goal updates
provide a source-supported explanation, not an identified per-request device trace.
Metadata presence still determines allocation kind; do not drop the guard.
Counts and finalizations balance, and the game exits zero.

The longest measured queue update is 49.733 ms, including 30.373 ms of serial
ordinary search and 11.418 ms across two pairs. The log does not identify why the
serial search was needed. The maximum pair is 22.494 ms and already reuses both
results. Three other retained slow updates are synchronous zone rebuilding at
32.5–36.2 ms. The reference keeps that zone-rebuild boundary too. More workers cannot guarantee a
shorter single search, and broader groups still have a synchronous completion
barrier. Our latest queue mean is 0.265 ms versus the preceding 0.344 ms in a
different workload, while the maximum increases. Neither this mixed timing result
nor acceptance percentages establish speedup or regression. All eight retained
task samples were reused and cannot explain the rejected cell phases elsewhere
in the session.

No matched replay benchmark or device-memory comparison with Reimagined exists.
Dense storage scales with map size and participating threads; our bounded storage
still contains larger records, indexes and multiple retained phase contexts.
Neither lower memory use nor faster iPhone performance can be inferred from
worker count, node layout or acceptance percentage alone. No completion
percentage is justified.

## Useful next steps

The allocation-decision and cell-classification stages are exercised on device.
The next dependency audit can focus on ordered goal updates: separate actual
allocation-kind uses from query-only cell observations and prove whether any
unchanged decisions permit reuse. Existing basic setter/metadata mutation checks
do not replace a realistic two-request callback trace. Do not remove fields or
raise bounds without equivalence evidence. This targets rejected work, not the
already-reused longest pair or zone rebuilds.
Compact bounded search-only records remain a separate useful storage step toward
the reference's layout without adopting dense map-sized capacity.

Full hierarchy and Path completion on workers is the larger execution milestone.
It requires auditing transitive engine reads, allocations, ownership, recovery
and result application before main-side work can be removed. A broader queue scan
and additional workers are separate dispatch changes that should follow measured
benefit and bounded-memory validation. Retain existing limits and per-request
scheduling unless a deliberate policy change is authorized.

## Source anchors and verification

In the supplied source tree, inspected Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp:
PathSearchContext::resize/beginSearch, processPathfindQueue, prefetchPaths,
runPrefetchedSearch, takePrefetchedPath and the early reuse entry in findPath;
Core/GameEngine/Include/GameLogic/Pathfinder/PathSearchContext.h;
GeneralsMD/Code/GameEngine/Source/Common/JobSystem.cpp: parallelFor/workerMain/
chooseWorkerCount; AIUpdate.cpp: predictPathfind; and GlobalData.cpp's default.
Checked the current dispatcher, validator, context allocation, finalization,
bounded observation logs, prediction gates and portable worker against them.

Current validation is 219 local regression cases, 98 batch ThreadSanitizer cases
and five new diagnostic ASan/UBSan cases. Native run
[40798412913](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40798412913)
also passes Mac QA/race checks, iOS SDK compilation, unsigned packaging and
artifact upload for 32ccf4e30; dependency save is skipped after the cache restore.
Its new device session confirms the diagnostic classifications and balanced
outcomes. Those fixtures and this session do not prove full engine race freedom,
reference replay equivalence or all lifecycle stress cases.
This comparison changes documentation only; unchanged tests are not rerun.

## Implementation reports

- [Allocation-decision windows and device evidence](IOS_PATH_ADMISSION_WINDOW_2026-10-29.md)
- [Cell-rejection diagnostics and counter interpretation](IOS_PATH_CELL_REJECTIONS_2026-10-29.md)

Compact search-only storage, full worker APIs, wider dispatch and grouped
scheduling remain separate differences. The current evidence does not establish
performance parity with Reimagined.
