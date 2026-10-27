# Real ordinary-search loop worker — 2026-10-27

## Implemented behavior

`GENERALS_EXCLUSIVE_PATH_WORKER` enables one worker that executes the actual
ordinary fine-search A* loop. The experimental iOS workflow enables it; it defaults
OFF elsewhere and requires GENERALS_SEARCH_CONTEXT. This is distinct from the
occupancy transcript validator. It is not a completed Reimagined prefetch pipeline.

The caller still performs quick/hierarchical search, fine-request preparation,
movement capture, initial cell/zone/destination checks and list setup. The extracted
runOrdinarySearchLoop performs frontier selection, closed-list insertion, layer
transitions and neighbor expansion, returning last cell, expansion count and found
status. Caller-side code then executes the original debug, path construction,
optimization, cleanup and failure/recovery branches in their original order.

The kernel's phase-local cell pointer is not an asynchronous result: the map and
search context remain alive and exclusively borrowed through the call and main
finalization. No attempt is made to retain/reuse it across advancing simulation.

## Exclusive world and context protocol

1. Enter the existing ordinary fine-search context/admission scope on the caller.
2. If release/debug/lifecycle/nesting conditions permit, release the top-level
   context ownership claim and dispatch one loop to ExclusiveSearchWorker.
3. Caller waits on a condition variable. It does not run simulation, SDL events,
   player updates, map resets, diplomacy changes or arbitrary callbacks during the
   wait. The normal engine API contract remains main-thread simulation ownership.
4. Worker binds the same context, uses captured movement settings and the stable
   live world, and changes temporary search records/lists only. This is exclusive
   transfer, not two threads concurrently searching the main arena.
5. Worker releases its binding before publishing completion. Caller reacquires the
   claim, reads the outcome and executes all finalization/recovery itself before
   leaving the phase. Exceptions restore ownership and propagate; no partial search
   is silently retried. Environment setup errors occur before the loop and can
   safely fall back to the caller.

The handoff keeps existing records and corridor state, so no scratch-copy/adoption
or changed orphan/capacity policy is added by the worker itself. Earlier independent
allocation changed lifetime policy; exact retail replay compatibility is still
unverified. No queue batching or extra gameplay searches are introduced.

## Transitive access checked for this limited loop

- Destination/preparation, geometry and initial object settings stay on caller.
- Occupancy checks still read Object/AI/Team state on the loop's thread. Normal
  simulation is stopped for their entire lifetime. They do not record shadow jobs
  or mutate sampling/controller fields while on this worker.
- Team::getRelationship reads relation maps/player state. Object::getRelationship
  reads team/defector state. Their sources were inspected; no simulation update or
  script dispatch was introduced in this path.
- canCrushOrSquish can initialize SquishCollide via NAMEKEY. For crusher-capable
  movers, dispatch requires findExistingNameKey to find that exact key already.
  Missing keys cause serial execution; the probe does not insert keys or change ID
  order. The ordinary serial path can initialize them naturally when needed.
- W3DTerrainLogic::getGroundHeight delegates to BaseHeightMapRenderObjClass's logical
  height-map sampling. The examined implementation reads the logic height-map and
  computes interpolation; this loop invokes no Metal drawables/render commands.
- checkChangeLayers and neighbor expansion update search scratch. Cell type,
  occupancy, goals, terrain/zone arrays and logical extents remain unchanged by
  the frozen caller. The existing background texture loader loads mip data and
  queues foreground completion; it is not a simulation/map writer in this path.
- Retail list release and forceCleanCells remain outside the extracted loop. The
  caller executes their map/pool repair and UI/audio effects after worker completion.
- Debug/profiling configurations using RTS_DEBUG, INTENSE_DEBUG, DEBUG_LOGGING or
  DUMP_PERF_STATS skip dispatch. Runtime AI debugging also uses the caller.

This is an audit of this specific loop, not blanket permission to call other engine
search APIs on a thread. Future simulation writers or callbacks require re-audit.
The context binding does not turn all public engine mutations into locked APIs.

## Lifecycle, bounds and fallback

The executor owns one std::thread and accepts one synchronous job at a time from
its owning caller thread. There is no speculative queue, polling or busy-wait loop.
It captures/restores the caller's floating-point environment before the task.
It joins in Pathfinder destruction before context/pool memory is released.

The existing iOS inactive/background flags prevent new dispatch. A loop already
running finishes within the current synchronous engine call; it cannot outlive map
reset or engine shutdown because the caller has not returned to those operations.
This does not add mid-search cancellation or guarantee a pause callback runs before
an already-running frame completes. OS process suspension also suspends the phase;
there is no independently advancing world to invalidate the result during it.

Nested context scopes, debug modes, unavailable thread startup/environment setup,
and missing crusher key prerequisites use serial execution. Non-environment task
exceptions propagate after ownership restoration rather than run a duplicate
partially executed search. No stale-result validator is needed for a result consumed
inside the same exclusive call, but that does not solve speculative reuse later.

Logging:

- `[PATH_SEARCH_WORKER] enabled mode=exclusive scope=ordinary_fine main_waits=true`
- `[PATH_SEARCH_WORKER] stopped searches=N mode=exclusive`
- Unavailable messages identify startup/environment fallback.

N greater than zero confirms real loop execution on this worker in that session.
Occupancy worker messages now identify their own shadow scope instead of claiming
all gameplay searches are serial. Both diagnostic and real-worker threads may exist;
there is only one actual search-loop worker.

## Performance and remaining full integration

Main waits while this one loop runs. There is no simultaneous second search, so
this is a correctness/integration baseline, **not a throughput optimization**.
Thread handoff, TLS access and worker scheduling can cost time. Thread stack/runtime
memory is platform-dependent; no second 30,000-record arena is allocated here.

Reimagined's useful parallelism requires multiple eligible requests, private
contexts, main participation, request prediction and validated queue-ordered
consumption. Those remain unimplemented. Closest/safe/attack/hierarchical searches
still run on caller. Do not call this a full Reimagined port or claim that frame
pauses have been fixed by moving this loop.

## Validation

Six tests compile the actual dispatch/loop/caller bodies or actual context/cell
operations with controlled world services. They compare serial and worker routes,
expansion order and ally flags across 48 scenarios, verify callback-thread
identity and caller-only path construction/cleanup, exercise real record ownership
handoff, nested/debug/pause/unavailable fallback, name-key lookup without insertion,
rounding mode, exception restoration, reuse (320 searches) and teardown.

The existing movement tests also check the pre-extraction route/expansion digest
recorded from f7ecc97a3, preventing shared serial/worker refactors from masking a
change to both implementations. These are not full-engine replays or iOS device
performance tests. SDK compilation and real-device execution remain required.

Validation result: all 100 workflow QA tests pass locally. All six new executor
tests pass AddressSanitizer/UndefinedBehaviorSanitizer and ThreadSanitizer. The
workflow runs the executor race tests on macOS too. Actionlint and diff checks
pass. Full SDK compilation, device execution and performance/replay tests remain
pending. This is the first real ordinary-loop worker rollout, not completion of
the entire requested Reimagined integration.
