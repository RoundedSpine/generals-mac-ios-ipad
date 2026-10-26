# iOS worker-pathfinding prefetch audit — 2026-10-26

## Decision

Do not enable worker searches in the current implementation. The tested serial
search context is useful preparation, but does not make Pathfinder reentrant.
Next implement complete **serial search ownership**, with workers still disabled:
move lists, corridor flags and control state into a context and remove shared
map-record allocation from the search kernel. Validate that separately before
adding speculative execution.

This is a source audit, not a ThreadSanitizer run, full transitive proof of thread
safety, replay comparison or measured performance result. No runtime code changes
or worker-enabled IPA are part of this audit.

## Material examined

Current checkout: `37bdbe30d`, branch `experiment/ios-mod-testing`.
Reference: user-supplied `ZeroHourReimagined_1.0.0_source`, extracted under
`/workspace/scratch/reimagined-source/ZeroHourReimagined_1.0.0_source`.
Reference code is evidence of a design, not an instruction to adopt it wholesale.
Primary reference files:

- `Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp`: 5808–6029, scheduling,
  prediction, worker dispatch and result validation.
- `Core/GameEngine/Include/GameLogic/Pathfinder/PathSearchContext.h`: worker-local
  nodes, lists, corridor flags and read tracking.
- `Core/GameEngine/Include/GameLogic/AIPathfind.h`: 534–556, cell-read tracking.
- `GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/AIUpdate.cpp`:
  522 onward, request prediction.
- `GeneralsMD/Code/GameEngine/Source/Common/JobSystem.cpp`: blocking parallelFor,
  worker lifetime and busy waiting.

User tests report good normal movement, tight spaces and bridges. Two supplied
logs from build 40310791770 reached the score screen and exited with code 0;
the second reused the cache. These support serial functionality, not parallel
correctness, replay equivalence or a quantified speedup.

## What the reference actually does

1. Predict likely searches for up to eight queued requests on the logic thread.
   Attack requests, blocked/stuck patching and quick paths are excluded. It can
   predict normal, closest/approach and safe searches. A failed normal search can
   also compute its closest-path fallback in the same job.
2. Run jobs using thread-local contexts. The caller also executes jobs and waits
   until the entire batch completes. Ordinary logic updates do not continue
   while this phase runs. This is parallel batch computation, not an asynchronous
   service spanning simulation frames.
3. Resume requests in queue order. Match object ID, search kind, locomotor-set
   pointer, exact coordinates, blocked flag, cost multiplier, ignored obstacle
   and starting tunneling state.
4. Reject results when a tracked read cell appears in the subsequent cell-write
   log. Accepted results transfer the path, allocation count, ending tunneling
   state and, for closest searches, adjusted destination. Entries are single-use;
   rejected paths are deleted and searched again normally.
5. Runtime prefetch defaults to FALSE in the reference GlobalData constructor.
   Its non-legacy queue loop nevertheless checks the frame budget between groups
   of eight, a separate scheduling change from worker execution itself.

This barrier design is materially safer than letting workers read a live,
advancing world. It does not itself eliminate worker-to-worker writes, mutable
getter internals or changes between batch completion and result consumption.

## Confirmed integration blockers in our current branch

| Area | Evidence | Required before concurrent searches |
| --- | --- | --- |
| Node state | `AIPathfind.h:226–247`: all records use one main context, not a worker-local context | Explicit context passed to every search-state operation; no shared generation advance |
| Shared record allocation | `AIPathfind.cpp:1159` onward and `PathfindCell::allocateInfo/releaseInfo`: searches assign shared cell `m_info` and modify a static free list | Worker-owned node storage and cell-to-node lookup; workers must not allocate/release shared persistent records |
| Lists and control state | `AIPathfind.h:943–971`: open/closed lists, tunneling, ignored obstacle and cumulative allocation count remain Pathfinder members | Move per-search state into the context; merge accounting only in serial request order |
| Hierarchical corridor | `ZoneBlock::setPassable` writes `m_markedPassable`; search code clears/sets zone-manager flags and `prependCells` marks corridor cells | Context-local corridor flags; immutable shared zone topology during execution |
| Pool capacity semantics | Current searches share a 30,000-record arena, including records retained for occupancy | Define exact serial allocation/failure equivalence; independent 30,000-node worker arenas do not automatically reproduce shared exhaustion behavior |

Changing the main-context accessor to thread_local alone is insufficient: cell
`m_info`, free-list ownership, Pathfinder lists and corridor flags would remain
shared. Our bounded slot IDs come from that shared pool, so duplicating the stamp
array does not provide independent cell-to-node allocation.

## Dependency and invalidation inventory

| Dependency | Where read | Parallel execution requirement | Reuse requirement after the barrier |
| --- | --- | --- | --- |
| Cell terrain/type, occupancy, goals, obstacle and layer links | `validMovementPosition`, `checkDestination`, `checkForMovement`, neighbor expansion | Frozen map/layers or immutable snapshot | Track every relevant mutation, including topology/layer replacement |
| Moving object's AI flags, ignored obstacle, geometry/radius, crusher state and player type | `examineNeighboringCells`, movement checks, search setup | Immutable request descriptor or audited frozen object access | Object revision/generation, not just object ID and start position |
| Other objects' identities, team relationships, AI presence and crushability | `checkDestination`, `checkForMovement`, dozer obstacle handling | Stable object lifetimes and read-only access throughout jobs | Dependency revisions or conservative global world revision |
| Locomotor surfaces and downhill restriction | Search setup and neighbor expansion | Copy immutable parameters or prove set cannot mutate | Pointer equality alone cannot detect changes to the pointed-to locomotor set |
| Terrain heights, destination layers, bridge geometry and map extents | Downhill checks, layer selection, node-coordinate construction | Frozen terrain/layer state; audit transitive getters for caches | Terrain/topology revision, map lifetime generation |
| Zone equivalency and hierarchy | Coarse search and passability checks | Freeze topology; keep corridor scratch private | Zone/topology revision |
| Path and PathNode allocation | `constructPath`/`prependCells` and result destruction | Worker-owned result buffers preferred | Materialize engine objects on logic thread in queue order |
| Diagnostics, failures and fallback behavior | Conditional debug/UI/script/perf branches and allocation failover | Exclude or defer side effects; private counters | Commit side effects exactly once when the actual request consumes a result |

The reference read set is populated by `Pathfinder::getCell`; its write log is
populated by instrumented cell mutators. That mechanism does not by itself cover
team relationships, object properties, locomotor contents or arbitrary terrain
state. This is a validation-coverage gap, not proof of a reproduced stale route.
An object can retain its ID and position while some of those inputs change.

A conservative first implementation could invalidate **all** outstanding results
on any relevant world/object/terrain revision. Fine-grained read dependencies can
come later if measurements show excessive recomputation. Revision updates must
cover actual writers; a counter without a complete mutation inventory is not a
correctness guarantee. A new map/load epoch must invalidate results even if IDs
or coordinates happen to match.

## Allocation, side effects and portability

- Engine MemoryPool allocation/free and DMA paths already contain
  `ScopedCriticalSection` guards (`GameMemory.cpp:1648,1733,1792,1813,2181,2297`).
  It would be inaccurate to call the entire allocator unprotected. These guards
  do not protect Pathfinder's own static cell-info free list. Lazy pool creation,
  constructors, accounting and lock contention still require targeted validation.
- Prefer plain worker-owned route coordinates/flags, then create Path/PathNode
  objects on the logic thread. This avoids making engine allocation and debug
  path ownership part of the first parallel kernel.
- Reference failed-search statistics include build-conditional
  `incrementOverallFailedPathfinds` calls; the underlying counter is a plain
  increment. Debug path ownership, icons and script messages also need exclusion
  or deferred effects. These are configuration-dependent hazards, not a claim
  that every release search executes them.
- `PathNode::computeDirectionVector` has mutable static scratch. No call to it
  from the audited path-search source was found, so it is not a demonstrated
  worker-search race; it matters if route processing is expanded later.
- Reference JobSystem includes `<intrin.h>` and `_mm_pause`, requiring an ARM64
  platform adaptation. Its workers spin up to 500 microseconds between batches;
  the caller yields while waiting for all jobs. Evaluate CPU, thermal impact and
  contention with DXVK/audio on the actual iPhone rather than selecting worker
  count solely from hardware_concurrency.
- Cancellation, map teardown and app lifecycle handling need a join/barrier
  contract. No worker may retain Object, terrain or locomotor pointers beyond
  their guaranteed lifetime.

## Memory and frame-time constraints

The reference allocates nodes, read marks and corridor flags per context based on
map size, plus read-cell lists, heap storage and completed routes. Memory therefore
scales with active worker contexts and total layered map cells. Exact resident and
peak memory on iOS have not been measured. Do not transplant this allocation model
without a bounded design and a failure path that falls back serially.

Keep our existing per-request frame budget and queue order. Do not adopt the
reference's eight-request budget granularity as an incidental dependency. A
barrier still blocks the logic thread for the longest running job, and rejected
predictions add duplicate work. More aggregate throughput does not guarantee fewer
input stalls. Useful metrics are accepted/computed/recomputed results, wasted
nodes, batch-wait time, worst frame duration and memory high-water mark.

## Recommended implementation sequence and acceptance criteria

1. **Serial ownership refactor, workers OFF.** Explicit context owns open/closed
   lists, tunneling/ignore flags, allocation accounting and hierarchical corridor
   scratch. Give search nodes independent bounded lookup/storage without mutating
   persistent map records. Define and test retained-record/exhaustion behavior;
   compare route order, failure outcome and budget usage against today's build.
2. **Pure request/result boundary.** Capture movement inputs on the logic thread,
   return route data and deferred effects. Start with ordinary queued ground
   searches only; retain attack/safe/closest/patch/quick paths serially until their
   dependencies are individually verified. No live engine object writes in jobs.
3. **Serial speculative validation.** Predict and compute with a second context
   on the same thread, then compare with the real ordered search. Exercise changed
   occupancy, team/crush/locomotor properties, bridges, object destruction and
   save/load. Validate null results and fallback chains as well as successful paths.
4. **Bounded worker experiment, opt-in.** One worker initially, fixed memory cap,
   original scheduling, explicit lifetime barrier and serial fallback. Race-test
   the extracted kernel and dispatcher on a supported host; run ASan/UBSan and
   repeated deterministic route/accounting comparisons across worker counts.
5. **Device and replay validation.** Check crowded bridges and narrow passages,
   mixed groups, moving obstacles, construction/destruction and repeat loads.
   Compare replay CRCs and ordered path hashes where available. Measure frame
   tails and thermal/memory behavior with warm graphics caches before claiming
   improvement or increasing concurrency.

The next useful code change is step 1. Workers remain a later opt-in experiment;
this audit does not establish that prefetch will improve this device's performance.


## Implementation follow-up

After the audited baseline, the serial ownership stage moved lists, control flags,
frame accounting and corridor scratch into the context. Shared record allocation
and live engine dependencies remain blockers. The original findings above describe
37bdbe30d; see [the implementation notes](IOS_SERIAL_SEARCH_CONTEXT_2026-10-26.md)
for the completed subset and its validation scope. No workers or prefetch are enabled.
