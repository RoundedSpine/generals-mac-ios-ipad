# Occupancy query boundary and shadow worker — 2026-10-27

## Scope and decision

User authorized advancing toward full worker pathfinding. This stage enables one
**occupancy-query shadow validator**, not a worker that searches or installs paths.
Full ordinary/closest/safe/hierarchical search offload remains unfinished. Do not
change this option's meaning or describe it as a completed asynchronous pathfinder.

The further transitive audit found Object::canCrushOrSquish initializes a static
NAMEKEY for SquishCollide and resolves modules; Object::getRelationship reads both
units' undetected-defector state and team relationships. These are concrete engine
dependencies, not values captured by the previous movement-policy struct. They,
all object resolution and every cell/AI/terrain access remain on the main thread.

## Explicit query boundary

`pathoccupancyquery.h` defines the destination/movement query inputs, scalar result,
reader operations and pure decision kernel. `LiveOccupancyReader` in AIPathfind.cpp
resolves the engine operations only on the caller. It keeps no engine pointers in
the copied transcript. The reader covers:

- Mover existence, identity, AI presence, ignored obstacle, aircraft behavior and
  infantry kind. Keep the destination special case where missing AI leaves the
  mover identity invalid, while movement reads actual ID per occupied cell.
- Cell existence, type, goal/position IDs, aircraft goals and obstacle presence.
- Other-unit resolution, directional alliance result, AI/idle state, infantry kind
  and full crush/squish result. These decisions are captured as answers from the
  live world; neither team nor object internals are accessed by replay.
- Transient consideration, original footprint order, the five-entry ally identity
  cache and its saturation behavior, partial outputs on failure, legacy rules and
  optional infantry pass-through. Unused acceptableSurfaces was not invented as a
  dependency of these particular functions; movement validity still uses it elsewhere.

Compiled static assertions check the cell flags/types used by the pure kernel.
Disabled builds retain the original query functions. Enabled builds use the same
pure kernel with live answers and optionally record its reads. One comparison of
ignored-obstacle/unit IDs is explicitly sequenced to make transcript order stable;
these ID getters have no decision-changing side effects in the examined code.

A transcript is an **ordered historical read log**, not an independently generated
world snapshot. Replay validates that the explicit query boundary contains its
required answers and reproduces the live query's outputs. It cannot tell whether
an answer is still current and cannot validate or authorize a path result. In
particular, the test that deletes the mock world and then replays successfully is
an ownership test, not a stale-path acceptance test.

## Worker, bounds and lifetime

`GENERALS_OCCUPANCY_WORKER` defaults OFF and requires `GENERALS_SEARCH_CONTEXT`.
The iOS mod-testing branch sets it ON; the stable workflow keeps it OFF. It adds
one lazy std::thread using standard C++ synchronization, without x86 instructions,
spin loops, polling or an eight-search batch barrier.

- At most four recorded queries per processPathfindQueue invocation, preserving the
  existing per-request scheduler and 5,000-cell frame budget.
- Each transcript has 512 events of opcode, three integer arguments and reply.
  Overflow continues the live query normally and skips validation.
- One pending job plus one currently processed value copy. Submit uses try_lock;
  contention/full queues skip sampling rather than wait for worker completion.
- Worker outputs are counters and a first-mismatch message only. There is no path,
  cell, Object or context pointer in a job and no API to install a replay result.
- Existing iOS inactive/background watcher pauses sampling and advances a lifecycle
  epoch. Work from a different lifecycle epoch is discarded. Reset drops pending
  work and advances the worker session epoch. A short in-progress replay may finish
  its integer computation before the epoch check; it accesses no engine resources.
- Pathfinder destruction stops acceptance, discards pending work, joins the worker
  and prints counters before releasing search context and engine record storage.
  Thread startup system_error disables sampling and leaves live serial queries active.

A local 64-bit fixture measures Event=20 bytes, Transcript=10,296 bytes and
ValidationWorker=10,448 bytes. The pending/member transcript, active local transcript
and sampled main-thread transcript are bounded. Thread stack/runtime storage and
actual iOS residency remain platform-dependent and unmeasured. Four samples add
copying and replay work; this stage claims no performance improvement.

Diagnostics:

- `[PATH_OCCUPANCY_WORKER] enabled mode=shadow ... gameplay_searches=serial`
- A bounded first mismatch message if replay disagrees or the transcript read
  sequence is invalid. Gameplay uses the live serial result regardless.
- Shutdown summary: validated/mismatches/skipped. Skips are expected from queue
  contention, overflow or lifecycle invalidation; zero mismatches is the objective.

## Verification and limits

All 88 workflow QA tests pass locally. The new seven-test suite compiles the actual
engine adapter and both original query bodies. It compares 20,000 generated cases
in each of four legacy/infantry combinations (80,000 total), including null mover,
missing AI/objects, off-map cells, occupancy flags, alliance/crush results, aircraft,
footprints and transient settings. Targeted cases exercise the five-ally cache's
saturation behavior and unusual obstacle/aircraft destination rules.

Other tests cover pointer-free replay after source destruction, changed/corrupt
transcripts, bounded overflow, production sampling budget, actual std::thread
execution, pause/reset churn, stop/repeated teardown, and the actual iOS watcher.
All seven pass AddressSanitizer/UndefinedBehaviorSanitizer and ThreadSanitizer.
The workflow also runs `test_occupancy_worker.py --tsan` on macOS with clang++.
Actionlint and diff checks pass. Full iOS SDK compilation and device behavior are
still separate checks. Mock-world agreement does not establish real-game replay
CRCs, all transitive engine safety, or device performance.

## Still required for gameplay workers

1. Establish a complete immutable world view or an audited frozen-world contract,
   including terrain/bridge topology, zones, extents, object lifetimes, relationships,
   crushability and all other read dependencies. Historical query transcripts are
   not sufficient to answer new speculative search queries.
2. Pass an explicitly selected search context through every cell/state operation;
   the current kernel still selects the serial main context. Freeze/adapt permanent
   pool admission and separate search side effects from result application.
3. Define whole-request capture across quick/hierarchical/fine stages and extend
   contracts to closest destination writeback, safe-path starts and optimization.
4. Validate speculative results on the main thread, testing deletion, changed orders,
   movement/diplomacy/occupancy, bridges/terrain and map replacement. Apply in original
   request order with serial fallback, then test real replays and failure equivalence.
5. Only then enable gameplay search offload and measure frame times, memory, thermal
   behavior and lifecycle transitions. One worker does not imply faster frames.
