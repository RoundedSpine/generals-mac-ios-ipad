# Zone rebuilding and repeated occupancy queries — 29 October 2026

## Device evidence

The supplied `generals-stderr.log` from `08da30b` confirms complete-worker mode,
886 pairs, 1,756 primary reuses, 12 rejections and four unused results. Thirty
fallbacks all reuse. No allocation/thread failure or dependency overflow is
recorded; the session exits zero. Native IPA run 40887588648 succeeds.

Ten queue calls exceed 20 ms; none reach 50 ms. Three of the four retained longest
queue calls rebuild zones (36.307, 32.787 and 30.105 ms). Another spends 35.076 ms
in a joined pair: the worker takes 34.933 ms and caller 13.316 ms. The worker
records 142,281 occupancy observations with 3,550 unique input keys (40.1 calls
per key), examining 3,223 fine cells. These counts establish repetition, not its
share of execution time. Complete-worker task timings cover the whole API and
must not be compared directly with the older fine-only task measurements.

## Source findings

`evaluateOccupancyQuery()` evaluates the live reader first, then records the
input/result in `BoundedObservationLog`. That log deduplicates stored observations
and subsequent validation work; it does not memoize evaluation results. Repeated
calls still scan the unit footprint, inspect occupancy and, when needed, resolve
units, relationships and crushing rules. Each logged repeat also hashes the key
and checks that the returned result agrees with its first observation.

`Path::optimize()` repeatedly tests candidate straight-line shortcuts from each
anchor, walking backward from the farthest eligible node until one passes.
`isLinePassable()` walks each candidate line; `linePassableCallback()` invokes
`checkForMovement()`, which reaches the occupancy evaluator. Overlapping candidate
lines therefore repeat cells and footprint checks. The supplied Reimagined source
retains this same optimizer structure; its pathfinding workers do not remove
this source of repeated geometry checks. Fine-search neighbor/footprint checks
also repeat queries. The device log does not yet separate these origins.

A controlled 12-by-12 fixture using production hierarchy, fine search and Path
optimization gives the following work counts for one ordinary worker request:

| Layout | Total calls | Distinct queries | Preparation | Hierarchy | Fine | Finalization |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Open | 46 | 27 | 1 | 0 | 25 | 20 |
| Alternating winding corridor | 910 | 116 | 1 | 0 | 178 | 731 |

Finalization accounts for 80.3% of calls in the winding fixture. This demonstrates
a concrete repetition mechanism, not a device timing result or proof that the
same stage caused the observed 35 ms pair. Fixture services and allocator remain
controlled substitutes. Host timings are not used for a speed ranking.

Zone rebuilding similarly preserves the existing multi-pass implementation:
cell relabeling/collapse, bridge assignment and table allocation; per-block zone
rebuilding; global equivalence merging; and equivalence flattening. It returns
from the queue call before processing any requests. Thus a zone-only queue spike
cannot be attributed to the search worker or eliminated by adding search workers.

## Added measurements

All instrumentation remains under the existing optional `GENERALS_PATH_TIMING`.
No search limits, worker count, scheduling, route optimization or dependency
validation change. Every occupancy query still evaluates and records its result.

- `zone_rebuild`, `zone_label`, `zone_blocks`, `zone_equivalence` and `zone_flatten`
  report wall-clock phase metrics. At most four `[PATH_ZONE_SLOW]` records retain
  dimensions, block/zone counts and stage times independently of slow pair/queue
  eviction. Queued rebuilds are measured even when queue depth is zero; those
  have queue ordinal zero because the existing queue profiler skips empty queues.
  Initialization calls using the default null timing argument are unmeasured.
- `[PATH_TASK_PROFILE]` retains hierarchy/fine/finalization wall time and sampled
  occupancy evaluation/logging time for the existing top four pairs, separately
  for participant and primary/fallback. These task-stage metrics include rejected
  or unused work. Session stage aggregates still merge accepted private results
  only, plus measured serial calls; they are not all-speculation totals.
- `[PATH_QUERY_STAGE]` attributes exact call counts and samples to preparation,
  hierarchy, fine and finalization. Classification is scoped and restored on
  exception. Complete jobs use their private timing owner; the older fine-only
  mode has no stage classification and reports its calls as preparation.
- Three clock reads sample every 128th query across a job. Evaluation and logging
  intervals use the same sampled call. No clock runs on the other 127 queries.
  Sampled totals are **not estimated whole-task costs** and include clock boundary
  overhead and any scheduling delay. Periodic sampling can bias stage coverage;
  compare per-stage call/sample counts. A stage with no samples has unknown cost,
  not zero cost. No per-cell or per-query log output is added.

Each participant writes its own counters. Main copies retained task data only
after joining. No shared counter is updated by both participants. Profile state
resets with the existing request logs, independent of search generation changes.
All report storage is bounded and scalar. Main still replays each distinct query
against the live world before accepting a result.

## Verification and next decision

New regressions check deterministic sampling/time accounting, every evaluation
and logging call, nested/exception stage restoration, null-owner clock suppression,
zone retention with empty queues, and production zone-table equality with timing
OFF/ON. The zone fixture compiles actual relabel/merge/flatten code and predicates;
its block/layer services remain substitutes. A winding route exercises real
optimizer duplicates and sample publication. An intervening live goal change
still reevaluates, changes the returned result and marks conflicting observations.

All 251 regular regressions pass locally: 113 batch cases, 13 complete-worker
cases and 125 other workflow cases. All 13 complete cases and six targeted batch
cases pass ThreadSanitizer. The latter include the three new profiler/zone cases
and joined publication, rejected/unused timing and fallback timing. The updated
winding test also passes normally after replacing its earlier open-map workload.
The new zone fixture initially lacked fence accessors and TRUE/FALSE constants;
add these controlled services, then both timed and untimed rebuilds compile and
produce identical tables. No production failure or race report is observed in
these checks. Native compilation and profiling on device remain pending for this
change; no performance improvement is claimed.

Use the same heavier save/orders on device and exit normally. Look first at the
slow pair's fine/finalization times and the stage query counts, then at sampled
evaluation versus logging. Inspect `[PATH_ZONE_SLOW]` separately. Main still waits
for both participants; another worker cannot remove the longest single search.

If repeated evaluation dominates, consider bounded per-request memoization inside
the frozen joined participant only. It would need the complete query identity,
fixed mover/AI inputs, all five result fields, explicit reset across request and
fallback lifetimes, and unchanged main-thread live replay. Cross-frame caching
or skipping result validation is not justified. If logging dominates, investigate
dependency indexing first; if zones dominate, optimize their measured pass while
preserving the authoritative rebuild semantics. This stage implements measurement,
not any of those optimizations.
