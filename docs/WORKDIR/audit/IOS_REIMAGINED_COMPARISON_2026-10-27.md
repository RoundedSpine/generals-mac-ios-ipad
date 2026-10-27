# Current implementation versus Reimagined — 2026-10-27

> Historical review of f705c4a15, before actual parallel search integration.
> For the current implementation and latest device evidence, see
> [the 28 October comparison](IOS_REIMAGINED_COMPARISON_2026-10-28.md).

## Scope and conclusion

Reviewed experiment/ios-mod-testing at f705c4a15 against the supplied
ZeroHourReimagined_1.0.0_source tree, including AIPathfind.cpp, PathSearchContext.h,
PathfindCell.h, AIUpdate.cpp prediction and JobSystem.cpp. This compares implemented
source, not only earlier audit descriptions. No source claim establishes measured
speed, complete thread safety or replay compatibility on iOS.

Reimagined implements actual parallel speculative searches; our gameplay searches
remain serial. Our new worker replays historical occupancy answers and is not a
partial implementation of its path-search dispatcher. Useful parts of our context
work are ready for integration, but full execution and consumption are missing.

## Corrections to the earlier recommendation

1. A complete immutable world snapshot is **not required** to reproduce the reference
   architecture. The reference freezes normal simulation during parallelFor, and
   the logic thread helps with searches before waiting for the batch. Full snapshots
   are an alternative for searches overlapping advancing simulation. The actual
   obligation for the frozen design is audited concurrent access plus stable object
   and map lifetime, followed by validation during serial result consumption.
2. Copying movement settings and making context selection explicit are useful, but
   neither establishes a frozen-world barrier or a usable worker result pipeline.
3. Our owned route collector is currently local to prependCells: it is immediately
   materialized, then discarded. It is not yet an independently returned search
   result. buildActualPath still allocates Path before collection and runs optimize
   inside the search call.
4. ThreadSanitizer success covers the isolated worker/context fixtures, not the live
   engine kernel. Occupancy replay runs the same evaluator with recorded answers;
   it checks the reader boundary, not independent search correctness or freshness.
   The generated comparisons against retained legacy query bodies provide a
   separate correctness check for the query refactor.
5. Main-thread PathNode materialization is our chosen isolation strategy, not an
   absolute requirement inferred from the reference. Reimagined builds/optimizes
   engine Paths in worker searches. Our engine memory implementation already has
   critical sections; it must not be described as wholly unprotected. Allocation
   contention, destruction and transitive services still need auditing.
6. A name-key initialization is a concrete transitive write to audit, not proof of
   a reproduced race or a blanket prohibition on live getters. Prewarming or
   synchronization could resolve a specific initialization issue; a full world
   snapshot is not the only remedy.

## Feature comparison

| Area | Reimagined source | Current branch |
| --- | --- | --- |
| Open frontier | Stable binary heap, 32-bit insertion sequence | Stable heap, 64-bit sequence, retained retail capped-list fallback |
| Hierarchical edge search | In nonlegacy mode allocates missing crossing records; explains why independent lifetimes exposed the old assumption | Narrow late-allocation adaptation after eligibility/duplicate checks |
| Permanent versus temporary state | Dedicated compact PathSearchNode separate from cell/permanent info | Separate arenas but reuses PathfindCellInfo representation, with unused metadata overhead |
| Node lookup | Dense map-cell index into vector | Bounded keyed pool keyed by cell address, stable record slots |
| Generation reset | Stamps, wrap clears node stamps | Stamps and keyed-pool generations, bounded arenas |
| Scratch selection | Main fast path outside parallel phase; thread-local selected context inside parallel phase | Lexical thread-local binding with ownership checks; main fallback; no parallel execution phase |
| Scratch contents | Nodes, lists, corridor, ignored obstacle, tunneling, counters | Equivalent categories isolated; global retail recovery flags still remain |
| Node budget | Nonlegacy default permits nodes for all registered map cells; optional testing node limit | 30,000 private records plus permanent/transient admission rule |
| Permanent admission snapshot | Nonlegacy search allocation is separate from retail permanent pool credit | Captured during ordinary fine search only; other APIs can read live permanent-use count |
| Prediction | AIUpdateInterface::predictPathfind for normal, approach/closest and safe searches | Absent |
| Unsupported predictions | Attack, stuck patching, quick paths are excluded | No prediction dispatcher exists |
| Parallel work | Actual searches using per-thread contexts; ordinary failure can compute closest fallback in the same job | Only occupancy transcript replay on one worker |
| Scheduling | Nonlegacy queue checks budget between groups of eight, even when runtime prefetch is off | Original budget check between requests; no eight-request grouping |
| Barrier | Main participates then waits for all jobs | No gameplay-search barrier; shadow submission skips on contention |
| Result format | Engine Path plus request prediction, read cells, counters, tunnel state, adjusted destination | Local raw route collector; no transferable whole-search result |
| Result validation | Exact request matching and cell read/write intersection | No stale gameplay-result check |
| Consumption | Single-use, queue order; invalid entries discarded and computed serially | Serial searches only |
| Recovery | Specific old s_useFixedPathfinding/s_forceCleanCells/forceCleanCells paths removed from this reference kernel | Retained, including permanent pool/map mutation and UI/audio |
| Platform worker code | std::thread pool plus intrin.h, _mm_pause, 500-us spin window and main yield barrier | Portable std::thread/CV shadow worker, iOS lifecycle epoch, reset invalidation and join |
| Worker defaults | Runtime m_pathfindPrefetch starts FALSE; jobs also require workers and at least two predicted jobs | Shadow option defaults OFF globally, ON for experimental iOS branch; gameplay workers absent |

Constants MAX_CELL_COUNT=500, MAX_ADJUSTMENT_CELL_COUNT=400 and
MAX_SAFE_PATH_CELL_COUNT=2000 match in the examined trees. The material larger-limit
difference is default nonlegacy active-node capacity, not a claim that every search
constant was raised. Reference legacy-lifetime mode has different serial-only
allocation semantics and cannot be conflated with its worker-capable mode.

## How the reference actually executes

1. Collect predictions for upcoming queue entries. Each includes search kind,
   locomotor pointer, coordinates, blocked/cost settings and ignored obstacle.
   A normal request reserves an optional closest fallback entry.
2. If fewer than two jobs are predicted, skip prefetch: there is nothing to share.
3. Enable read tracking/parallel context selection and dispatch jobs. The main
   thread executes jobs too, then waits until the batch completes. Normal unit,
   diplomacy and terrain simulation does not advance through this barrier.
4. Each participating thread creates/reuses a PathSearchContext, sizes node and
   read-mark arrays to the map, installs it, calls the engine search API, and saves
   its path, allocation count, ending tunneling and sorted cell read set.
5. After the barrier, log cell mutations while actual doPathfind requests are
   processed serially. Match requests exactly and reject any prefetched path whose
   read cells intersect the intervening writes. Take valid results once, merge
   counters/control state and write back closest-path destination adjustment.
6. Discard remaining predictions. Search again serially when a prediction does
   not match or has become invalid.

It is a blocking parallel batch, not an asynchronous service that simply lets
simulation advance while workers inspect the live map. With one worker plus main
participation, two eligible independent jobs can run concurrently. Moving one
search to one worker while the main thread only waits has no such throughput
advantage and would add dispatch overhead.

## Validation limitations, accurately scoped

The reference's cell logging is real and useful. getCell notes read indices and
instrumented cell mutators append write indices. takePrefetchedPath compares object
ID, kind, locomotor identity, coordinates, blocked/cost settings, ignored obstacle
and starting tunneling. This is substantially more complete functionality than our
historical occupancy replay.

It does not explicitly fingerprint every object/team/locomotor/terrain property.
Whether that omission produces a stale result depends on which properties can
change between batch completion and the particular request's consumption. The
barrier already prevents ordinary simulation changes during computation. We must
audit doPathfind/result application and intervening callbacks, rather than assert
that every untracked property is necessarily racing during the batch. Pointer
identity alone cannot detect changes to the contents of a locomotor set.

Our shadow transcript records answers, including directional alliance and crush
results. It can replay after deleting the source mock world because it owns those
answers. That says nothing about whether a route is still valid in the new world.
A zero-mismatch device run would validate historical query playback only.

## Tradeoffs in our additions

- Fixed record capacity provides a predictable arena bound, while dense indexing
  avoids per-cell hash lookups. Neither is universally faster. Our reused record
  representation also duplicates metadata not needed by a pure search node.
- Generation invalidation and independent allocation change lifetime/exhaustion
  behavior relative to retained retail orphan records. Keeping a 30,000 bound and
  old frame scheduling does not establish exact retail replay equivalence.
- Our heap preserves a retail fallback the reference worker-capable kernel removed.
  That is a compatibility choice, and a source of extra recovery complexity.
- The raw route collector adds temporary vector storage and a second pass. It is
  useful only if developed into an actual result boundary; no speedup is measured.
- Current active-context selection adds thread-local lookup on hot search helpers.
  The reference has a main-context fast path outside parallel work. Binding checks
  also add work once per ordinary fine search. Benchmark before keeping all of this
  enabled for performance builds.
- The occupancy reader abstraction executes on main even for unsampled queries in
  the enabled build. Sampling/replay adds work. The validator is diagnostic tooling,
  and should remain switchable or be disabled after its specific validation task.
- Frozen admission is scoped to ordinary fine search and does not freeze occupancy,
  other objects, map lifetime or global retail recovery flags.

## Concrete route to real integration

Use the reference frozen parallel model as the target, not additional unrelated
shadow diagnostics and not an immediate full async-world rewrite.

1. Prepare eligible requests on main and define a whole-search return object,
   preserving adjusted destinations, failures, allocation accounting and tunnel
   state. Start with an explicitly limited request subset.
2. Isolate/defer the retained recovery, debug/UI/audio and optimization effects.
   Decide which audited services can execute under the frozen contract and which
   remain on main. Avoid changing retail recovery semantics silently.
3. Build actual dispatch using selected private contexts and captured admission.
   Main must participate in another eligible search for one worker to offer search
   parallelism. Join before advancing normal simulation and before teardown.
4. Preserve budget checks between original requests. Copying the reference's
   eight-request grouping would violate our current constraint. If speculative work
   is performed for a request not ultimately admitted this frame, discard it without
   committing its counters or effects; measure the extra work.
5. Add exact request matching and cell invalidation, then audit additional non-cell
   dependencies through serial consumption. Verify rejection and serial fallback,
   single consumption, unused result disposal and map/lifecycle cancellation.
6. Compare real serial/worker routes and failures, replay CRCs and device frame
   times before expanding coverage or claiming faster gameplay.

This is a real integration effort. None of the existing 93 fixture tests establishes
completion of those dispatch/consumption stages.

## Verification status at review time

The current branch is f705c4a15. Its Actions run 40449121660 has passed the QA and
macOS ThreadSanitizer steps and is still compiling the iOS app at review time.
This verifies the isolated tests on a second toolchain; it is not a completed IPA
or device test of the latest changes. Earlier device logs support earlier serial
stages only.

The reference README explicitly lists replays, multiplayer and long sessions among
untested areas. Source comments claiming determinism are design claims, not a
substitute for independent replay/device validation. The reference is a useful
implementation to adapt, not proof that a direct iOS port is already correct.

This review changes no engine behavior and adds no worker dispatch. No unchanged
code tests were rerun merely to repeat previously passing checks.


## SDK follow-up during this review

Run 40449121660 subsequently failed iOS compilation at the two occupancy adapters:
RTS_GENERALS is undefined for this Zero Hour build, so it cannot be used as an
ordinary C++ expression. The isolated query fixtures had always defined it to zero
or one. Replaced those assignments with preprocessor guards and added an actual
undefined-macro compile/execution case. All eight occupancy tests pass local
ThreadSanitizer, and the new regression passes ASan/UBSan. This fixes a build
blocker; it does not introduce full worker searches. All 94 workflow QA tests pass
locally. A new SDK build is required.
