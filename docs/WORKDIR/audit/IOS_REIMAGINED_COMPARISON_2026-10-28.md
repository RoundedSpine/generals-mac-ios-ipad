# Current pathfinding versus Reimagined — 28 October 2026

For the current runtime and device evidence, see the
[29 October comparison](IOS_REIMAGINED_COMPARISON_2026-10-29.md).
The snapshot below preserves the earlier review and subsequent implementation notes.

## Scope and conclusion

Compare experiment/ios-mod-testing at a1756448e (runtime f2088ba) directly against
the supplied ZeroHourReimagined_1.0.0_source tree. Read both AIPathfind.cpp and
AIUpdate.cpp implementations, our context/worker headers, and the reference
PathSearchContext.h and JobSystem.cpp. This supersedes the earlier comparison at
f705c4a15, which accurately described an earlier shadow-only implementation but
does not describe the current branch.

The current branch implements the reference's core speculative batch model:
predict requests, run real searches concurrently with main participation, join,
validate results and consume them once in queue order, otherwise compute on main.
Ordinary, safe, queued closest and conditional closest-fallback kernels exist.
The latest device log exercises early closest fallback and validates result reuse.
This is a narrower iOS adaptation; it is not full source or performance parity.

## Source comparison

| Area | Reimagined supplied source | Current iOS branch |
| --- | --- | --- |
| Open candidates | Stable binary heap with 32-bit insertion order | Stable binary heap with 64-bit insertion order; retail linked-list recovery retained |
| Hierarchical crossing fix | Allocate missing eligible crossing records in nonlegacy mode | Narrow adaptation implemented; coarse search still executes on main |
| Search isolation | Compact PathSearchNode, private lists/corridor/flags, generation stamps | Private stamped nodes, keyed records, lists/corridor/flags; reuses larger PathfindCellInfo record representation |
| Lookup/storage | Dense node and read-mark arrays sized to registered map cells per participating thread | Bounded keyed lookup, 30,000 records/context; at most four speculative phase contexts |
| Prediction kinds | Normal, safe, approach/closest; conditional closest after normal failure | Same categories of fine kernel, including early ordinary rejection; stricter eligibility |
| Dispatch | Scan eight upcoming requests, skip unpredicted entries; pool and main share eligible jobs | Require two adjacent eligible requests; one search worker and main execute one task each |
| Worker count | Automatic clamp(cores - 3, 0, 8); explicit override capped at 32 | One gameplay search worker; historical shadow validator disabled in this workflow |
| Barrier | Main helps, then yields until all chunks finish; world simulation does not advance | Main executes its task, then waits on a condition variable; both tasks join before callbacks/world effects |
| Worker scope | Calls complete findPath/findClosestPath/findSafePath APIs, including hierarchy and Path creation/optimization | Main prepares; worker runs fine-search loop; hierarchy, Path creation/optimization, recovery and AI effects remain on main |
| Conditional fallback | Same job invokes closest when ordinary returns no Path, including early API failure | Same task can run closest after fine-loop failure or alone after early rejection; actual caller no-path branch authorizes reuse |
| Result | Completed engine Path, adjusted target, charged work, tunnel state and read-cell set | Private loop outcome/parent records; main finalizes an engine Path, adjusted target and actual accounting |
| Stale checks | Exact predicted request/ignore/tunnel matching and read-cell intersection with subsequent cell-write log | Exact request/queue position/movement/preparation/admission checks; cell values, observed corridor flags, live occupancy answers, terrain heights, world/lifecycle epochs and overflow checks |
| Scheduling | Nonlegacy mode checks 5,000-cell budget between groups of eight even when prefetch is disabled | Original 5,000-cell budget check after every actual request; unused speculation discarded |
| Active-node limit | Default permits all registered map cells; optional testing override | 30,000 private-record bound plus permanent/transient admission policy |
| Worker platform | std::thread pool, x86 intrinsics and 500-microsecond worker spin before sleep | Portable thread/CV code, floating-point environment transfer, joined exception paths, iOS pause/reset invalidation |
| Enablement | Runtime m_pathfindPrefetch defaults FALSE; configuration can override | Enabled in experimental iOS workflow; options default OFF outside it |

The reference also excludes attack requests, stuck-path patching and quick paths
from prediction. Those are shared limitations, not worker features we have yet to
copy from it. Our extra exclusions include dozers, ordinary non-final goals,
specific production-exit cases and uninitialized crusher name keys. Failed
safe/approach preparation and unsupported adjacent requests can prevent pairing.
Reference ordinary prediction has fewer such gates, and an eight-entry scan can
share nonadjacent eligible requests despite unsupported entries between them.

Both retain MAX_CELL_COUNT=500, MAX_ADJUSTMENT_CELL_COUNT=400 and
MAX_SAFE_PATH_CELL_COUNT=2000. The material capacity difference is the reference's
map-sized active-node allowance; describing every reference search limit as raised
would be incorrect. Our closest search retains the original conditional pruning
after 2,000 expansions rather than treating that number as a universal hard cap.

## What the latest device log establishes

Revision ~f2088ba completes 968 pairs: 1,909 primary kernels plus 27 fallback-only
tasks, totaling 1,936 request slots. Primary results: 1,788 accepted (93.7%), 119
rejected and two unused. Separately queued closest accounts for 26 primary kernels
and four of the primary acceptances; safe is zero in this session.

Conditional fallback: 27 completed, 16 accepted, 11 rejected and none unused.
All 27 are early fallbacks, with 16 early acceptances. Thus the new early path is
executing on device and its results are reused after validation. The log reaches
the score screen and exits zero, without a primitive-restart warning.

These totals include main participation and valid no-path outcomes. They do not
mean 16 successful routes, identify which fallback ran on the worker, explain each
rejection, or measure time saved. No ordinary fine-loop-failure fallback is shown
in this particular log. It does not exercise safe search or prove lifecycle stress,
long-session behavior, full-world race freedom or replay equivalence.

## Tradeoffs and remaining work

The broader reference dispatcher can amortize wakeup costs and use more cores.
It can also perform more work before returning control. Its dynamic chunk sharing
can balance unequal searches; our fixed pair waits for its slower task. Both are
synchronous barriers, so neither guarantees elimination of a single long search
or main-thread hierarchy/optimization pauses.

Our additional checks cover more explicitly enumerated non-cell dependencies,
but cost preparation, recording and main-thread validation work. Reference cell
logging is useful and is not evidence of a reproduced reference race. Our stricter
checks are likewise not proof that every live-world access is safe. A result can
be rejected because of an unrelated epoch/admission change or overflow, then
recomputed; accepted-result percentage alone cannot establish a net speedup.

Reimagined's compact dense nodes reduce lookup indirection but scale storage with
map size and participating threads. Our bounds avoid that scaling, although the
larger record representation and dependency logs are substantial: the prior
four-phase estimate is about 26 MiB plus map corridors and runtime overhead.
This is an estimate of extra search storage, not measured iOS RSS, and does not
establish lower memory use than Reimagined for every map.

Keep the working dispatch and fallback changes. The next useful engineering work
is measuring search/preparation/validation/finalization time and device memory,
then considering compact bounded search records and reducing repeated lookups.
Any broader prediction coverage or moving hierarchy/optimization onto workers
needs its own transitive-access and result-validation audit. More workers, larger
groups and map-sized node allowances are separate policy changes, not missing
requirements for our two-request implementation. No percentage-complete estimate
or performance ranking is supported by this source comparison.

## Verification

This is a source/log review; no engine code changed and no unchanged tests were
rerun. Existing evidence remains the 172 Mac QA tests, workflow race checks
(including 54 batch tests), successful iOS SDK/package build 40538565784, and the
device log above. The subsequent runner-label-only ARM64 change does not alter
the runtime implementation compared here.

## Subsequent measurements and metadata compaction

The later ~3228907 device log and successful ARM64 build are recorded in the
[pair-admission review](IOS_PATH_ADMISSION_2026-10-28.md). They show real reuse,
short-queue/eligibility limits, heavy-search outliers and synchronous zone costs;
they do not establish a matched speed comparison with Reimagined. Both sources
still calculate zones synchronously before draining pending requests.

The follow-up [direct-state binding change](IOS_PATH_RECORD_BINDING_2026-10-28.md)
reduces our record metadata from 72 to 56 bytes on the local 64-bit fixture ABI
and removes repeated owner/slot resolution from live search-state access.
Private record and state arrays remain separate and bounded. This narrows one
storage/access cost without adopting Reimagined's compact dense search-only node
layout, broader dispatcher, worker pool or grouped budget policy.

## Subsequent preparation fidelity and reuse

The [ordinary corridor and read-log change](IOS_PATH_CORRIDOR_READS_2026-10-28.md)
now prepares the real ordinary hierarchy in each private context on main, and
deduplicates exact query/height observations without caching live search answers.
Its ~40bb42b device session reuses 1,524/1,548 primary phases, with no corridor or
explicit read-overflow rejection. The original keyed bounds remain; this does not
introduce dense map-sized storage or establish a matched performance comparison.

The next [closest preparation change](IOS_PATH_CLOSEST_PREPARATION_2026-10-28.md)
also captures the real closest hierarchy outcome/corridor in private main-side
preparation instead of assuming success. It strengthens coarse Path ownership
through cleanup and adds bounded scalar mismatch summaries while retaining exact
admission/policy validation. Local regression and sanitizer checks pass; native
SDK and device confirmation for this subsequent change remain pending. Hierarchy
and finalization still execute on main, one worker still pairs two adjacent
requests, and the storage, dispatch and scheduling differences above remain.
