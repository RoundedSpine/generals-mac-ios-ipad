# Current pathfinding versus Reimagined — 29 October 2026

## Scope and conclusion

Compare experiment/ios-mod-testing at runtime 9117f785d directly with
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
every reached allocation decision stays equivalent. Cell diagnostics explain
remaining raw failures. Query-only lookups now rely on complete occupancy-result
replay; direct cell and allocation-kind dependencies retain exact snapshots.

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
| Read tracking | Bounded exact direct/allocation cell snapshots and complete query results; query-only lookups avoid redundant raw snapshots; query/height duplicates removed while actual reads still execute | Per-cell read marks deduplicate cell observations into a sorted cell-index set |
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

The cell diagnostic stage separates a changed cell snapshot from a full or
failed cell-read log. It identifies differing fields in the first unequal cell
using the existing single read. This adds visibility, not a faster search or a
larger off-thread scope. The subsequent query-only stage avoids redundant raw
snapshots inside an evaluator whose entire returned result is separately replayed.
It preserves direct and allocation cell dependencies. The current session still
has 15 raw goal-owner first failures, ten with metadata presence differences;
their aggregates do not prove the remaining checks can be removed.

## Device evidence and performance limits

The newest supplied device log is ~9117f78. It completes 945 pairs, reuses
1,831/1,854 primary phases (98.76%) and all 36 closest fallback phases. Ten primary
and three fallback phases complete despite changed permanent usage, with zero
admission rejection. All fallback executions in this session are early fallbacks.
Queued closest, safe and ordinary fine-loop-failure fallback do not execute in
parallel here. The 23 primary first rejections are cells 15, occupancy one, kind
five and world epoch two; fallback has no rejections. All cell first failures
contain changed goal-owner values, ten also metadata presence changes, with no
full or failed cell logs. Ordered main-side goal updates provide a source-supported
explanation, not an identified per-request device trace.
Metadata presence still determines allocation kind; do not drop the guard.
Counts and finalizations balance, and the game exits zero.

The longest measured queue update is 59.558 ms, including a 54.110 ms serial
closest kernel. The next two retained updates also contain serial closest kernels
at 38.832 and 36.886 ms, with negligible hierarchy work. The first two calls have
depth one and cannot form an adjacent pair; the depth-two call's exclusion reason
is not correlated in this log. The maximum pair is 33.468 ms and already reuses
both results. The next performance audit should explain these closest kernels'
request/pruning context. Charged counts above 5,000 remain permitted last-request
overshoot; closest's conditional 2,000 pruning test is not a universal hard stop.

Zone rebuilding stays synchronous in both implementations, although no zone call
is retained among this session's top four. More workers cannot guarantee a shorter
single search, and broader groups still have a synchronous completion barrier.
Our latest queue mean is 0.377 ms versus the preceding 0.265 ms in a different
workload, while acceptance improves. Neither acceptance percentages nor these
unmatched timings establish speedup or regression. All eight retained
task samples were reused and cannot explain the rejected cell phases elsewhere
in the session.

No matched replay benchmark or device-memory comparison with Reimagined exists.
Dense storage scales with map size and participating threads; our bounded storage
still contains larger records, indexes and multiple retained phase contexts.
Neither lower memory use nor faster iPhone performance can be inferred from
worker count, node layout or acceptance percentage alone. No completion
percentage is justified.

## Useful next steps

The allocation-decision, cell-classification and query-only stages are exercised
on device. Controlled ordered goal updates match serial routes/accounting, and
direct/allocation dependencies remain guarded. Do not remove the remaining goal
fields or raise bounds without equivalence evidence. The largest current retained
costs instead motivate a bounded audit of serial closest work and pruning.
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

Current validation is 225 local regression cases, 104 batch ThreadSanitizer cases
and six new query-dependency ASan/UBSan cases. Native run
[40810392060](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40810392060)
also passes Mac QA/race checks, iOS SDK compilation, unsigned packaging and
artifact upload for 9117f785d; dependency save is skipped after the cache restore.
Its device session confirms active validation and balanced outcomes. Those
fixtures and this session do not prove full engine race freedom,
reference replay equivalence or all lifecycle stress cases.
This comparison changes documentation only; unchanged tests are not rerun.

## Implementation reports

- [Allocation-decision windows and device evidence](IOS_PATH_ADMISSION_WINDOW_2026-10-29.md)
- [Cell-rejection diagnostics and counter interpretation](IOS_PATH_CELL_REJECTIONS_2026-10-29.md)
- [Query-only dependency audit and device result](IOS_PATH_QUERY_DEPENDENCIES_2026-10-29.md)

Compact search-only storage, full worker APIs, wider dispatch and grouped
scheduling remain separate differences. The current evidence does not establish
performance parity with Reimagined.

## Subsequent query-only dependency stage

The [query dependency audit and implementation](IOS_PATH_QUERY_DEPENDENCIES_2026-10-29.md)
identifies one narrower dependency: getCell inside an explicitly tracked occupancy
evaluation need not also retain a raw 19-field snapshot. Its full returned result
is still saved and replayed on main. Direct cell reads and allocation-kind
observations remain exact, so this does not adopt Reimagined's independent node
allowance or drop metadata validation. Controlled tests reproduce a redundant
old-rule rejection with unchanged routes/budget and compare ordered actual goal
updates against serial execution. Not all device goal changes are proven harmless.

This is a dependency refinement, not a dispatch or execution-scope milestone.
Compact nodes, complete worker APIs and wider batching remain the same major gaps.
The native/device follow-up above verifies this stage executes. It does not
attribute a particular accepted request to the narrowed dependency or establish
a device speedup from the higher reuse rate.

## Focused source comparison: the slow closest searches

Recheck runClosestSearchLoop and examineNeighboringCellsWithMovement against
Reimagined's findClosestPath and examineNeighboringCells, then inspect both node
accessors and dispatchers. The reference's closest-candidate scoring and
far-candidate pruning block matches ours after substituting context/settings
names and removing comments/whitespace. This was checked directly against the
supplied files, not inferred from similar constants. It is not a proof of whole
engine path equivalence: capacity, lifetime, neighboring services and reuse policy
still differ.

| Closest-search detail | Current iOS source | Reimagined source |
| --- | --- | --- |
| Candidate score | Squared goal distance plus costSoFar * (costSoFar * factor) * pathCostMultiplier, strict less-than replacement | Same expression and replacement rule |
| Far pruning | Outer distance > best screen distance * 4, then prune on failed hierarchy, count > 2000 or sufficiently near candidate | Same conditions; no unconditional 2,000-node cutoff |
| Blocked goal after a candidate exists | Zero Hour marks foundGoal, continues selecting from the remaining list and stops further neighbor expansion | Same behavior |
| Initial stuck / failed closest hierarchy | Enable tunneling or permit all corridor blocks as appropriate | Same broad policy |
| Neighbor expansion | Same eight-direction order and initial line shortcut; captured movement settings | Same order/shortcut; live movement getters |
| Node access | searchInfo resolves through bounded pointer-keyed records, then a direct state pointer | Cell search index selects a compact node; generation stamp checks whether it is active |
| Serial current-context access | Bound thread-local context lookup | Main context fast path when not in the parallel phase |
| One eligible queued request | No adjacent pair; authoritative caller searches | prefetchPaths explicitly clears/returns when jobs.size() < 2; authoritative caller searches |
| Search capacity | Retained permanent/transient credit and 30,000-record bound | Nonlegacy active nodes independent of permanent metadata, default allowance all registered cells |

Neither implementation's far-pruning count condition fires independently of its
outer distance test. If no valid closest candidate has been found, the best
distance remains at its initial sentinel and that pruning rule cannot bound an
otherwise finite-distance search. Both can therefore perform substantial work
for difficult destinations. The new log does not establish whether this explains
its three longest closest kernels; candidate/pruning context is still missing.

The reference's node layout is the most directly relevant remaining structural
difference for a long single search. Its getters avoid our repeated keyed lookups
for coordinates, costs, open/closed state and parents. Our direct state binding
already removed an extra owner/slot step, but it did not remove searchInfo's
lookup. This is a source-level opportunity, not measured attribution of the
54.110 ms kernel. Simply making our records smaller would not automatically
provide its direct cell-index access, and dense indexes/nodes have map- and
participant-dependent memory costs. Storage, lookup and capacity policy should
be assessed separately.

Some existing iOS adaptations remain worth keeping. Movement scalars are captured
rather than repeatedly fetched from live objects during expansion. Parent terrain
height is read only in downhill/cliff branches; the reference's neighboring-cell
routine reads it before the neighbor loop even when those branches are unused.
Our branch-local version can reread it for several eligible neighbors, so this
source observation alone does not establish fewer reads for downhill/cliff work.
The explicit query-result, allocation and lifecycle validation remains a distinct
adaptation, not a prerequisite to copy the reference's raw read/write-set scheme.

For the two depth-one slow calls, adopting the reference's pool/width would still
leave only one request to compute. Wider scanning can help when several eligible
requests exist, but neither pool divides an individual closest loop. Full worker
Path completion also cannot remove these single-kernel costs by itself. The
latest measured hierarchy/finalization costs are small relative to these kernels.

Recommended follow-up: capture bounded closest work/candidate/pruning context and
measure the keyed node-access path before choosing compact-node/direct-lookup
work. Preserve the current allocation allowance and per-request scheduling during
that comparison. There is no source-supported reason here to copy a more
aggressive pruning rule or raise search limits. No runtime changes or additional
regression runs were made for this source-only comparison.

## Subsequent bounded direct-lookup implementation

The [direct-index stage](IOS_PATH_DIRECT_INDEX_2026-10-29.md) removes repeated
key probes for registered map-cell getters by mapping cell IDs to existing stable
record slots. The existing allocator/state storage, 30,000-record allowance and
allocation-decision policy remain. Tables are bounded to 1 MiB/context; uncovered
or unregistered cells use the original keyed path. This adopts indexed access
without adopting the reference's map-sized compact-node arrays or its capacity
policy. Search-only node compaction remains a separate difference.

The same stage adds bounded serial closest candidate/pruning work and an optional
host getter benchmark. Controlled route/work/accounting traces match keyed
resolution. Pinned host microbench medians improve for its sequential/random
getter mixes, with noisy unpinned results also documented. Native run 40843223256
now passes Mac QA/race checks, iOS SDK compilation, packaging and upload. The
~26be01d device session exits zero: 622/624 primary phases and all six fallbacks
reuse, with balanced finalizations. The main index table retains 180,024 bytes.
Its slowest closest kernel is 1.459 ms and maximum queue 11.573 ms, but the session
has fewer requests and does not reproduce the older long searches. The four
closest samples show exact-goal and near-goal-pruned outcomes without over-2000
pruning. These are device execution/counter checks, not a matched speed comparison.
The larger compact-node layout, full worker APIs and broader dispatch remain
differences from the reference.
