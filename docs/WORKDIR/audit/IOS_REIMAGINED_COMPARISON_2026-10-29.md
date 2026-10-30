# Current pathfinding versus Reimagined — 29 October 2026

## Scope and conclusion

Compare experiment/ios-mod-testing, including compact nodes and complete-worker APIs, with
the supplied ZeroHourReimagined_1.0.0_source. This is a pathfinding comparison;
Reimagined graphics and gameplay content remain outside this integration. This
supersedes the runtime snapshot in the 28 October comparison, while retaining
its historical evidence.
The latest supplied device runtime is 8084275 with complete APIs, fast zone merges,
frozen occupancy caching, arena reuse and anchored lookahead enabled. It exits
normally and records 42 nonadjacent pairs among 920 dispatched pairs. Further
gameplay coverage and matched performance validation remain. Historical stage descriptions below
retain their original scope.

Our implementation has the reference's core speculative model: predict queued
requests, run independent searches concurrently with main participation, join,
validate, and consume once in queue order or recompute. Ordinary, safe, queued
closest and conditional closest-fallback APIs execute on participants. Hierarchy,
Path construction, optimization and private cleanup are included; accepted Paths
return before main repeats preparation. Terrain-layer and ignored-object inputs
join the existing bounded validation. Live retail recovery remains on main.

The allocation-window change now accepts permanent-count differences only when
every reached allocation decision stays equivalent. Cell diagnostics explain
remaining raw failures. Query-only lookups now rely on complete occupancy-result
replay; direct cell and allocation-kind dependencies retain exact snapshots.
Registered cell reads now use a bounded cell-ID to record-slot index. Compact
private nodes then embed search state and discard permanent-only fields and the
separate state arena. The original allocator/admission policy remains. The
reference indexes a complete compact search node directly by cell ID.

The largest remaining differences are dense map-sized node storage, broader
dispatch and different capacity/budget policies.
The reference is not simply our implementation with additional workers enabled.

## Current comparison

| Area | Current iOS branch | Supplied Reimagined source |
| --- | --- | --- |
| Candidate ordering | Stable binary heap, 64-bit insertion sequence, retained retail list fallback | Stable binary heap, 32-bit insertion sequence |
| Search state | Compact private nodes with embedded state, private lists/corridor, allocator/index generation stamps | Private search-only nodes/lists/corridor and per-node generation stamps |
| Search kinds | Ordinary, safe, queued closest and conditional closest fallback; stricter prediction gates | Same API categories, broader ordinary prediction |
| Preparation | Main captures inputs; participant runs hierarchy; accepted completed Path returns before preparation repeats | Whole search API runs in the participant's context; accepted completed Path returns before hierarchy is repeated |
| Off-thread scope | Complete ordinary/safe/closest APIs, including hierarchy, Path construction/optimization and private cleanup; attempted live recovery aborts to caller | Complete findPath/findClosestPath/findSafePath calls, including hierarchy and Path construction/optimization |
| Dispatch | Eligible head plus earliest eligible partner within eight entries; dynamically claim two logical jobs with one worker plus main | Scan eight upcoming requests, skip unsupported entries, share eligible jobs dynamically across pool and main |
| Worker count | One gameplay search worker | Automatic clamp(cores - 3, 0, 8), explicit override capped at 32 |
| Result storage | Two pool-owned participant arenas reused across jobs/phases; results contain no arena reference; Paths/logs/publication stay independent | Thread-local search context reused between jobs/phases; each result owns a completed engine Path |
| Node lookup | Bounded cell-ID to record-slot table, complete compact node; keyed allocation/release and uncovered-cell fallback remain | Cell ID directly selects a compact search-only node |
| Lookup/node memory | Index capped at 1 MiB/context plus bounded complete-node pool; local fixed context shrinks about 1.37 MiB; preceding device main index about 176 KiB | Node/read-mark arrays scale with registered map cells per participating context |
| Capacity | 30,000 records/context; allocation windows preserve every reached permanent/transient admission success and denial | Nonlegacy search nodes independent of permanent metadata; default node allowance is all registered cells, with testing override |
| Dependency checks | Explicit request/movement, all-generation admission, epochs/lifecycle, exact cells, occupancy, ground/layer height, destination layers, ignored-object snapshots and bounded logs; complete corridor is private output | Request/ignore/tunnel matching plus intersection between read-cell set and subsequent cell-write log |
| Read tracking | Bounded exact direct/allocation cell snapshots and complete query results; frozen complete-job cache reuses occupancy evaluations; main validation reevaluates live | Per-cell read marks deduplicate cell observations into a sorted cell-index set |
| Queue budget | Check the existing 5,000-cell budget after each actual request | In nonlegacy mode, check between groups of eight, even with runtime prefetch disabled |
| Wait behavior | Main claims jobs dynamically then waits on a condition variable; joined errors/cancellation and per-job FP propagation; idle workers sleep | Main shares dynamic chunks then yields until all finish; workers spin for 500 microseconds before sleeping, with x86 pause intrinsic |
| Zone rebuilding | Synchronous on main; minimum-root merging and canonical flattening optimization | Synchronous on main; original whole-table merging/flattening |
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
It preserves direct and allocation cell dependencies. The current session has one raw
goal-owner/metadata first failure; its aggregate does not prove that check can be
removed. Indexed lookup changes how the record is found, not which inputs require
validation or which allocation can succeed.

## Device evidence and performance limits

The newest supplied device log is ~26be01d. It completes 315 pairs, reuses 622/624
primary phases (99.68%) and all six closest fallback phases. One primary phase
completes despite changed permanent usage, with zero admission rejection. All
fallback executions are early fallbacks. Queued closest, safe and ordinary
fine-loop-failure fallback do not execute in parallel here. Primary first reasons
are kind one and cells one; fallback has no rejection. The cell failure changes
goal-owner, metadata, unit flags and metadata position, with no full or failed log.
Indexed lookup does not justify removing the allocation-kind guard. All 4,298
finalizations balance with 628 reused results and 3,670 serial kernels. Exit is zero.

The main index retains 180,024 bytes, approximately 176 KiB. Maximum queue time
is 11.573 ms for 29 callbacks and 14 pairs. The slowest closest kernel is 1.459 ms;
two retained cases reach the exact goal and two prune through the near-goal rule
before returning a closest candidate. The earlier 54.110 ms closest kernel and
its 38.832/36.886 ms neighbors are not reproduced. This session has fewer requests
and much smaller retained tasks; the new counters do not identify the old costs'
cause from this different workload. Charges above 5,000 remain permitted
last-request overshoot; closest's conditional 2,000 test is not a universal cap.

Zone rebuilding stays synchronous in both implementations, though none appears in
this session's top four. Both implementations leave a single eligible request on
main and join all parallel work before continuing simulation. Additional workers
do not divide an individual search loop. The latest queue mean is 0.204 ms versus
0.377 ms previously in a different workload. Six retained tasks reuse and two
reject (kind/cells), both small tasks in queue 3199. Neither these timings nor
acceptance percentages establish a matched device or reference speed ranking.

No matched replay benchmark or device-memory comparison with Reimagined exists.
Dense storage scales with map size and participating threads; our bounded storage
still contains indexes and multiple retained phase contexts. Compact storage
reduces our own fixed object sizes, but does not establish memory use relative to
the reference or iPhone RSS. Faster iPhone performance cannot be inferred from
worker count, node layout or acceptance percentage. No completion percentage is
justified.

## Useful next steps

The allocation-decision, cell-classification, query-only and bounded indexed
lookup stages are exercised on device. Controlled ordered goal updates and
indexed/keyed traces match routes, expansion order and accounting. Direct and
allocation dependencies remain guarded. Do not remove remaining goal fields or
raise bounds without equivalence evidence. Closest work samples and a host
getter benchmark now exist; repeat the heavier scenario for comparable work.

Compact bounded search-only nodes are now implemented: permanent-only fields
and the separate state arena are removed without changing slot allocation order,
capacity or admission decisions. Host memory savings are clear; timings are mixed,
with slower getter mixes and inconsistent complete closest results. The next
step is matched device verification, not a speedup claim. The reference's
independent map-sized capacity and complete dense layout remain separate
policy/memory decisions.

Full hierarchy and Path completion on workers are now implemented behind the
branch-enabled complete option. Verify the native build and the same heavier save
on device. Context reuse is now possible without retaining parent records for
later construction, but requires preserving each completed result's observations
and final control/corridor state. Broader scanning and additional workers remain
separate dispatch steps requiring measured benefit and bounded memory. Retain
per-request scheduling unless a deliberate policy change is made.

## Source anchors and verification

In the supplied source tree, inspected Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp:
PathSearchContext::resize/beginSearch, processPathfindQueue, prefetchPaths,
runPrefetchedSearch, takePrefetchedPath and the early reuse entry in findPath;
Core/GameEngine/Include/GameLogic/Pathfinder/PathSearchContext.h;
GeneralsMD/Code/GameEngine/Source/Common/JobSystem.cpp: parallelFor/workerMain/
chooseWorkerCount; AIUpdate.cpp: predictPathfind; and GlobalData.cpp's default.
Checked the current dispatcher, validator, context allocation, finalization,
bounded observation logs, prediction gates and portable worker against them.

The indexed-stage validation was 232 local regression cases, 108 batch
ThreadSanitizer cases and seven index/work-counter ASan/UBSan cases. Native run
[40843223256](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40843223256)
also passes Mac QA/race checks, iOS SDK compilation, unsigned packaging and
artifact upload for 26be01d4a; dependency save is skipped after the cache restore.
Its device session confirms active validation and balanced outcomes. Those
fixtures and this session do not prove full engine race freedom,
reference replay equivalence or all lifecycle stress cases.
The original comparison was documentation-only. The subsequent compact stage
passes 235 local regressions and seven targeted ASan/UBSan cases. Its full batch
TSan run passes 109 cases with one 10-second matrix timeout; that case passes
alone, and passes again with both new compact cases after its bound increases to
30 seconds. No race report. See the compact report for scope and mixed benchmarks.

## Implementation reports

- [Allocation-decision windows and device evidence](IOS_PATH_ADMISSION_WINDOW_2026-10-29.md)
- [Cell-rejection diagnostics and counter interpretation](IOS_PATH_CELL_REJECTIONS_2026-10-29.md)
- [Query-only dependency audit and device result](IOS_PATH_QUERY_DEPENDENCIES_2026-10-29.md)
- [Direct indexing, work counters and device result](IOS_PATH_DIRECT_INDEX_2026-10-29.md)
- [Compact private nodes, layout savings and mixed host timings](IOS_PATH_COMPACT_NODES_2026-10-29.md)
- [Complete participant APIs, ownership, validation and verification](IOS_PATH_COMPLETE_WORKER_2026-10-29.md)

Dense map-sized storage, context reuse, wider dispatch and grouped
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
accessors and dispatchers. The pre-instrumentation check matched closest-candidate
scoring and far-pruning after context/settings and comment/whitespace normalization.
The latest stage only wraps these conditions with counters. This was checked against the
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
| Node access | Covered cell IDs select record slots and then state; keyed fallback and allocation remain | Cell search index selects a compact node and generation stamp |
| Serial current-context access | Bound thread-local context lookup | Main context fast path when not in the parallel phase |
| One eligible queued request | No adjacent pair; authoritative caller searches | prefetchPaths explicitly clears/returns when jobs.size() < 2; authoritative caller searches |
| Search capacity | Retained permanent/transient credit and 30,000-record bound | Nonlegacy active nodes independent of permanent metadata, default allowance all registered cells |

Neither implementation's far-pruning count condition fires independently of its
outer distance test. If no valid closest candidate has been found, the best
distance remains at its initial sentinel and that pruning rule cannot bound an
otherwise finite-distance search. Both can therefore perform substantial work
for difficult destinations. The new log does not reproduce the earlier long
kernels; its smaller retained cases cannot identify their pruning context.

The indexed stage now removes repeated getter key probes for covered cells. Its
lookup remains cell ID -> record slot -> record -> state. The reference instead
uses cell ID -> compact search node. Our original keyed allocator and larger
record format remain, including permanent-record-only fields that private search
does not need. Compact nodes could remove those fields and the separate state
indirection while retaining the bounded allocation policy. That is distinct from
raising limits or copying the reference's map-sized dense storage.

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

Bounded closest work samples and getter measurements are now implemented. Use
those data for the compact-node step and repeat the heavier scenario when available. Preserve the current allocation allowance and per-request scheduling during
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

## Subsequent compact-node implementation

The [compact-node stage](IOS_PATH_COMPACT_NODES_2026-10-29.md) supersedes the
record/state-chain gap described in the historical sections above. A private
node now embeds state and omits permanent IDs, obstacle flags, the free-link
pointer and the state pointer. The context no longer owns a second stamped arena.
Local fixed context size drops from 4,244,504 to 2,804,496 bytes; complete private
slot/state storage drops from 112 to 64 bytes. Permanent records shrink too.

We now share the reference's search-only node design principle. We retain a
bounded ID-to-slot index, keyed allocator and original admission/lifetime policy,
where its map-sized array provides direct ID-to-node access. These remain real
differences; compact nodes do not imply complete worker APIs, dynamic dispatch,
eight-request scheduling or independent map-sized limits.

Split/compact controlled routes, expansion order, closest pruning and accounting
match. Host getter benchmarks regress around 8–11%, while complete closest
timings change direction between runs. This stage has a verified fixed-memory
benefit, not a demonstrated speed benefit or device/reference performance parity.
Test the new IPA in a matched heavier scenario before drawing that conclusion.

## Subsequent complete-worker API implementation

The [complete-worker stage](IOS_PATH_COMPLETE_WORKER_2026-10-29.md) closes the
fine-loop-only execution gap described in the historical sections. Both
participants now run hierarchy, fine search, engine Path construction, optimization
and private cleanup. Main validates the completed result at API entry and transfers
ownership before repeating preparation. Fallback hierarchy executes only when
ordinary completion fails. Global retail recovery still aborts speculation and
remains the caller's responsibility.

Warm Path pools on main, use existing recursive allocation locks, retain partial
and completed Paths through throwing cleanup, accumulate admission across phase
generations, add bounded terrain-layer/height and ignored-object validation, and
keep participant timing private. The tests compile actual hierarchy, Paths and
optimizer with controlled surrounding services, including bridge/cliff cases.
The preceding 235 regressions and eleven new cases pass; the new cases pass TSan
and targeted ASan/UBSan, including a reproduced and fixed cleanup ownership leak.

Dense lookup/capacity, wider scanning/dynamic worker dispatch, context reuse and
eight-request scheduling remain distinct from the reference. Main still joins
the pair, so there is no asynchronous simulation overlap. New task timings cover
complete APIs and cannot be ranked directly against old fine-only kernel times.
Native/device verification and a matched speed comparison are still required.

## Subsequent participant-arena reuse

The [context-reuse stage](IOS_PATH_CONTEXT_REUSE_2026-10-30.md) removes the retained
primary/fallback arena duplication. Our two fixed participant slots each own one
arena and reuse it for the sequential fallback. Each result owns its completed
Path, validation/cache/admission records, timing and final publication snapshot.
Reimagined uses thread-local reusable contexts with its dynamic dispatcher; our
implementation keeps the existing fixed participants and Pathfinder lifetime.

The controlled 64-bit layout eliminates up to two 2,804,560-byte fallback arenas
and their dynamic indexes. Logs remain separately owned; this is not measured
iPhone RSS or a speedup. The subsequent cache-enabled b05cf78 device log confirms
complete APIs and live rejection checks, but predates arena reuse. Native/device
validation of this stage remains required. Dense node lookup/capacity, wider
scanning, dynamic pool dispatch and eight-request scheduling remain distinct.

## Subsequent anchored partner lookahead

The [lookahead stage](IOS_PATH_LOOKAHEAD_IMPLEMENTATION_2026-10-30.md) adds bounded
scanning past unsupported partners while preserving the existing one-worker,
two-result executor. An unsupported actual head runs serially first. A lightweight
inspected-span window retains nonadjacent results across skipped callbacks and
negative scans until the call ends, the head exits, or an epoch invalidates it.
Request identity, live validation and per-request queue budgeting remain.

This adopts eligible-entry scanning without adopting the reference's dynamic
pool, up-to-eight selected requests or eight-request budget grouping. The two-job
cap censors the new eligibility counts; they cannot establish how many additional
workers would be useful. Native/device verification and matched timing remain.

## Subsequent participant-owned joined pool

The [pool foundation](IOS_PARTICIPANT_PATH_POOL_2026-10-31.md) detaches scratch
from logical result records and adds bounded dynamic job claims. Main and the
one retained worker reuse their own arenas across complete jobs and fallbacks.
Logical result identity is independent of physical execution, with explicit
timing mappings. Joined failure handling, per-job FP propagation and lifecycle
cancellation adapt the reference dispatcher for our contracts and ARM64 build.

This closes the fixed-assignment/arena-ownership gap. The device trial still
selects two jobs with one background worker; it does not yet adopt the reference's
wider job window or larger pool. Host tests additionally execute four complete
searches on three participant arenas. Native/device validation of the new pool
and performance benefits remain pending; the latest device log predates it.
