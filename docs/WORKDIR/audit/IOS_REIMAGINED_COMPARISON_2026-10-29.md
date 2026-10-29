# Current pathfinding versus Reimagined — 29 October 2026

## Scope and conclusion

Compare experiment/ios-mod-testing at 82a5c808c, runtime 81d5a83a3, directly with
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
| Capacity | 30,000 records/context and retained permanent/transient admission policy | Nonlegacy search nodes independent of permanent metadata; default node allowance is all registered cells, with testing override |
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
when deciding whether another record fits. Validation requires that count to
match at consumption. The reference's nonlegacy canActivateNode instead checks
its independent active-node count and map-sized allowance. takePrefetchedPath
has no equivalent global permanent-count equality test. Removing our guard
without accounting for changed admission decisions would not preserve our
current search behavior. Adopting its node limit would be a deliberate capacity
policy change, not a consequence of simply separating scratch state.

## Device evidence and performance limits

The current ~81d5a83 log completes 946 pairs, reuses 1,811/1,852 primary phases
(97.79%) and 38/40 closest fallback phases (95%). All fallback executions in this
session are early fallbacks. Queued closest runs 20 primary phases and reuses ten;
safe and ordinary fine-loop-failure fallback are not exercised here. There are
no closest-policy, corridor or explicit overflow first rejections. Permanent
admission accounts for 35 of 43 first rejections across both phases. Counts and
finalizations balance, and the game exits zero.

The longest measured queue update is 41.130 ms. Its 38.380 ms pair already reuses
both results; avoiding rejected work cannot remove that whole wait. Three other
retained slow updates are synchronous zone rebuilding at 30.6–36.7 ms. The
reference keeps that zone-rebuild boundary too. More workers cannot guarantee a
shorter single search, and broader groups still have a synchronous completion
barrier. Our latest queue mean and preparation total increased in a different
workload; higher reuse is not proof of net speedup.

No matched replay benchmark or device-memory comparison with Reimagined exists.
Dense storage scales with map size and participating threads; our bounded storage
still contains larger records, indexes and multiple retained phase contexts.
Neither lower memory use nor faster iPhone performance can be inferred from
worker count, node layout or acceptance percentage alone. No completion
percentage is justified.

## Useful next steps

First audit exact allocation-decision dependencies to determine whether harmless
permanent-count changes can be accepted without changing allocation failures,
routes or finalization accounting. This addresses measured rejected work but
does not target the already-reused longest pair or zone rebuilds. Compact bounded
search-only records are a separate useful storage step toward the reference's
layout without adopting dense map-sized capacity.

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

Current validation is 206 local regression cases, 85 batch ThreadSanitizer cases,
six added ASan/UBSan cases, successful native SDK/package run 40688598327 and the
device session above. Those fixtures and that device session do not prove full
engine race freedom, reference replay equivalence or all lifecycle stress cases.
This comparison changes documentation only; unchanged tests are not rerun.

## Subsequent allocation-decision implementation

The [allocation-window stage](IOS_PATH_ADMISSION_WINDOW_2026-10-29.md) replaces
our strict permanent-count equality with exact equivalence of all reached
transient admission decisions, including denials. It retains the existing bound
and credit policy, validates allocation-kind cell dependencies and uses the
actual caller's frozen allowance for completion. This permits harmless count
changes without adopting the reference's independent map-sized node capacity.
Local regression/sanitizer checks pass; native SDK and device confirmation for
this subsequent stage remain pending. Compact search-only storage, full worker
APIs, wider dispatch and grouped scheduling remain separate differences.

The ~ec6c40d device follow-up and successful native build now verify this stage
executes: five primary and two fallback phases complete despite changed counts,
with no admission rejection. Primary reuse is 98.43%, fallback reuse 28/28. The
remaining 26 cell-dependency first failures need classification as changed values
versus invalid/overflowed logs; prior strict-count checks could mask later cell
failures. The longest retained pair already reuses both results, and synchronous
zone rebuilding remains among the slowest queue updates. See the allocation-window
report for evidence and timing limits; these results do not establish performance
parity with Reimagined.
