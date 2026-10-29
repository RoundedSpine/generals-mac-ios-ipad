# Complete path APIs on joined participants — 29 October 2026

## Result and enablement

`GENERALS_COMPLETE_PATH_WORKER` moves eligible queued requests through the original
ordinary, safe and closest APIs on their parallel participant. This includes
hierarchy, fine search, engine Path/PathNode construction, optimization and private
cleanup. Main captures input values; it no longer prepares speculative hierarchy.
An accepted completed Path returns before authoritative hierarchy/preparation is
repeated. A rejected result is destroyed and the existing caller recomputes.

The option defaults OFF, requires `GENERALS_PARALLEL_PATH_BATCH`, and is enabled
only for `experiment/ios-mod-testing` in the iOS workflow. OFF retains the preceding
fine-loop implementation for comparison. One worker plus main, two adjacent
eligible requests, existing prediction gates, joined waiting, 30,000-node capacity,
retail tie/list behavior, pruning and per-request 5,000-cell scheduling remain.
An individual request with no eligible partner still executes on main.

Ordinary closest fallback is now executed through its complete API only after
the ordinary API returns no Path. Its input capture allocates a private context,
but does not perform hierarchy in advance. Main still authorizes fallback reuse
after ordinary failure or the existing real-caller no-path confirmation.

## Ownership, allocations and recovery

Each job owns a completed engine Path with a `deleteInstance` deleter until a
successful, single consumption transfers ownership. Primary and fallback remain
separately validated and retain up to four phase contexts; this stage does not
adopt the reference's context reuse/pooling policy. Completed Paths contain their
own nodes and optimized links and survive destruction/reset of private contexts.

The engine already protects pool allocation/free with
`TheMemoryPoolCriticalSection`; dynamic allocation uses its DMA lock. Unix
CriticalSection uses a recursive mutex, not a stub. SDL3Main installs these locks
before memory-manager initialization. PathPool/PathNodePool are listed in the
Zero Hour pool initialization table. Resolve both class pools on main before
dispatch so no lazy class-pool lookup is first performed by a participant.
Tools without the pool/DMA locks, maps not ready, pending lists or retail recovery
do not dispatch complete jobs.

No new allocator-wide lock or serialized whole-search lock is added. Path
constructors and optimization mutate only their owned nodes. The shared-static
direction helper is not on the construction/optimization call chain. Locomotor
surface/downhill getters are scalar reads. Zone/cell topology, bridge layers,
logical height-map data and live object reads remain frozen during the joined
pair. Zone rebuilding still runs synchronously before dispatch. Existing world
epoch/lifecycle invalidation remains part of consumption validation.

The speculative recovery guard now spans the whole API, including final cleanup.
Any attempted global retail repair aborts the pair before shared recovery writes;
the joined caller retains responsibility for real recovery. Partial fine Paths
are owned inside construction, and completed fine Paths remain owned through
subsequent list cleanup. Coarse Paths already had equivalent ownership. A new
injected cleanup-after-build case reproduced a leak before this second ownership
boundary was added and passes afterward. Pool `ERROR_OUT_OF_MEMORY` and standard
allocation failures discard joined results and disable speculative dispatch for
the session; other engine errors still propagate after cleanup.

## Validation and application

Keep object identity, locomotor identity, coordinates, kind, repulsors, movement
settings, initial ignored obstacle/tunneling, fixed mode, recovery, world epoch,
lifecycle, pause, cell snapshots, occupancy-query replay and ground-height checks.
Safe requests additionally validate the actual object position used for building
their path. Complete closest validation compares the caller's blocked/cost/
move-allies inputs; derived hierarchy/stuck/obstacle settings are protected by
their observed inputs instead of requiring main to repeat preparation.

Add bounded observations for terrain destination-layer selection and layer height,
including bridge/wall services used by hierarchy and path construction. Replay
their complete returned values before reuse. Add bounded snapshots of the ignored
object/obstacle existence, layer, position and airfield classification read by
closest preparation outside occupancy queries. Terrain observations allow at
most 8,192 distinct entries; object snapshots allow 64. Full/failed/conflicting
logs reject reuse. Existing raw/query/ground-height bounds remain unchanged.

Admission is checked over **all** reached coarse/fine generations: a separate
request window accumulates the same permanent/transient success/denial predicates
without being reset at a phase boundary. It does not enlarge capacity or remove
the permanent-record dependency. The original per-phase window remains available
for the fine-only mode.

At complete consumption, start/goal pointers and hierarchy-derived corridor flags
are not recomputed just to compare them. Coordinates, terrain-service observations,
exact cells and topology/lifecycle epochs protect those inputs. A complete API
derives its own corridor, so it is not an input dependency on the preceding
request's final corridor. Publish its corridor only if that API wrote it; an
early null return must preserve the caller's newer unwritten corridor.

Apply completed cell charges and final control state only for accepted requests.
Closest destination changes remain private until acceptance. Begin a new caller
record generation only if the accepted API began one. No AI callback, command
application or simulation mutation moves onto the worker. Main participates and
then waits for the pair; this remains joined speculation, not asynchronous work
over a continuously changing simulation.

## Diagnostics

`[PATH_COMPLETE_WORKER] enabled hierarchy=true path_construction=true
optimization=true reuse=before_preparation` identifies this mode at the first
executed pair. Existing batch width/worker/scheduling and native layout rows remain.
Paths and nodes retain the compact layout; new bounded observation logs and owned
results have additional memory cost. No device RSS measurement is claimed.

Complete requests use private timing objects while executing. Main merges stage
metrics after accepted transfer; participants do not race on the caller aggregate.
`worker_kernel`/`caller_kernel` and pair task wall times now include **complete API
work**, including hierarchy and optimization, rather than only fine loops. Their
primary counts include completed early-null API attempts. Fine examined/record
samples are captured before cleanup. `serial_kernel` remains serial fine work.
Hierarchy/finalization times can describe work performed on either participant
for an accepted result, so overlapping phase totals must not be added.

Consequently old `serial kernels + reused fine phases = finalizations` arithmetic
is not a general invariant for complete early-null requests. Confirm request
consumption, ownership, queue charges and dispositions instead. No direct speed
ranking is supported by comparing the old fine-only kernel time with this wider
scope. Queue time and matched work/paths remain useful comparisons.

## Verification and remaining limits

The 235 preceding workflow regressions pass locally (110 batch cases and 125
other cases). Eleven new complete-worker cases also pass, for 246 total. The new
eleven pass ThreadSanitizer. Ten initial cases pass ASan/UBSan; after adding the
cleanup-after-construction regression, that case passes ASan/UBSan as well.

The fixture compiles production hierarchy, parent walking, Path/PathNode methods,
optimizer, Bresenham traversal, search loops, dispatcher and validator. Unit,
zone, terrain and allocation services remain controlled substitutes. Coverage:

- Concurrent hierarchy on both participants and proof that accepted consumption
  does not repeat hierarchy or Path construction.
- Serial/parallel raw nodes, optimized links/directions/distances, blocking,
  destinations, corridor effects and budget equality across both retail modes,
  movement center/radius settings, obstacles, ordinary/safe/closest and fallback.
- Actual layer transitions over a controlled bridge and cliff optimization flags.
- Rejection of changed terrain layer/height, ignored object position, movement,
  request, topology epoch, lifecycle, fixed mode, ignored obstacle and failed logs.
- Admission changes, generation boundaries, valid early-null behavior, exactly-once
  transfer and accepted Paths outliving discarded contexts.
- Missing pool locks, timing OFF, injected pooled failures, optimizer abort and
  recovery after construction, with no retained fixture engine objects.

Fixture compile errors exposed the noncopyable timing object and a missing
callback typedef; reset only private stage metrics and use the production
callback shape. A validation test initially supplied an ignored-obstacle state
inconsistent with its first prediction; correct that fixture input. The cleanup
regression's initial failure was a real ownership issue and was fixed in production.

Native iOS SDK compilation and device testing are pending at commit time. These
fixtures do not establish whole-engine race freedom, every platform's allocation
behavior, iOS lifecycle stress coverage or a device speedup. Test the same heavier
save/orders, including bridges and blocked destinations, against the prior IPA.
Check the mode row, routes, input responsiveness, queue time and result rejection
rates. Both compact storage and complete execution still need device evidence.

Reimagined still differs in dense map-sized node arrays, independent node
allowance, broader prediction/scanning, a dynamically shared worker pool, context
reuse and eight-request budget groups. This stage closes the main execution-scope
gap while retaining our bounded iOS allocation and scheduling policies.
