# Two-request ordinary pathfinding batch — 2026-10-27

## Device baseline

The uploaded log tagged 40453771952 ran 3,094 real exclusive ordinary searches,
validated 17,017 separate shadow occupancy transcripts with zero mismatches,
reached the score screen and exited with code 0. That validates execution of the
preceding exclusive-worker build in that session, not a speed improvement or the
new parallel batch described here.

## What this implementation adds

`GENERALS_PARALLEL_PATH_BATCH` defaults OFF and requires the exclusive search and
occupancy options. The experimental iOS branch enables it. Two adjacent eligible
ordinary final-goal requests get separate 30,000-record contexts. One fine-search
loop runs on the existing worker; the main thread executes the other. A condition
variable joins both tasks before any AI callback, path materialization, optimization,
retail recovery, goal update or ally movement runs. There is one real search worker,
plus the existing independent shadow validator; no additional worker pool is added.

Prediction reads endpoints, ignored ID and ordinary-branch eligibility without
destroying an old path or changing AI flags. Safe, approach, attack, blocked/stuck,
non-final, flying quick-path and production-exit special requests are excluded.
Dozers are excluded because their expansion has an additional direct relationship
dependency. Crusher requests require SquishCollide to exist **before preparation**;
the probe never inserts a key or changes allocation order. Debug, nested ownership,
pause and unavailable-thread conditions retain existing ordinary dispatch.

Preparation runs on main in each private context and stops immediately before the
A* loop. It does not call the hierarchical Path builder, perform cleanup/recovery
or build a speculative engine Path. Prediction uses an unrestricted corridor.
During normal consumption, the original quick/hierarchical checks and ordinary
preparation run again. Every corridor block actually observed by the speculative
loop must match the current hierarchical corridor. This deliberately rejects
searches whose unrestricted preparation changed a relevant decision; it does not
silently replace the hierarchical policy with unrestricted search.

## Validation and consumption

Results are borrowed completions with private parent records, not asynchronous
paths that survive simulation advancement. They exist only inside the current
processPathfindQueue call. A result is single-use and can be considered only at its
original queue position from a top-level ordinary phase.

Before choosing the cached loop outcome, main checks:

| Dependency | Check |
| --- | --- |
| Request | Object ID and pointer, LocomotorSet identity, exact start/destination, ignored ID and queue position |
| Movement | Surfaces, downhill, layer, crusher, through-unit, dozer/vehicle, footprint, center and human policy |
| Preparation | Same start/goal cells, start indices, initial tunneling and permanent allocation admission |
| Compatibility/lifecycle | Same retail mode, no pending repair, unchanged world/lifecycle epochs, application active |
| Cells | Exact permanent values for every cell returned by getCell, including info presence/position, flags, occupancy/goal IDs, obstacles, zones, layers and pinching |
| Corridor | Exact value for each block read by the loop |
| Occupancy | Re-evaluate each recorded input against current live objects/teams/modules/AI and compare all returned decision fields |
| Terrain | Re-sample every recorded ground-height input and compare the height |
| Bounds | Any dependency-log overflow rejects reuse |

Occupancy validation is a fresh main-thread evaluation against live engine values,
unlike the older historical transcript shadow replay. Relationships, unit lookup,
idle status, infantry/AI presence, ignored IDs and crushing outcomes are therefore
rechecked even when permanent cells did not change. The main participant and worker
both bypass shadow-controller sampling state while recording private dependencies.

Broad invalidation precedes map reset/recalculation, obstacle/fence/footprint and
bridge/wall changes, retail repair and operations that issue arbitrary allied AI
commands. Goal/position cell changes are detected by exact cell values and captured
permanent admission. moveAllies' existing early no-work return does not invalidate;
entering its command-capable portion does. No simulation update, event pumping or
other normal world writer runs during either search loop. The existing background
texture loader is outside simulation ownership and does not write this search world.
The earlier exclusive-loop audit still defines the transitive engine read scope;
this is not blanket thread safety for every engine API.

On acceptance, discard only the newly prepared, unexecuted main scratch. Bind the
completed context on main, install the current corridor, and execute the original
success/failure finalizer. It creates and optimizes Path/PathNode objects and
performs original cleanup/recovery ordering. Merge the actual cleanup count and
resulting bookkeeping back to main. On rejection, run the existing ordinary loop;
closest fallback and all AI effects still occur through the original callback.

## Scheduling, memory and lifecycle

The original queue loop still checks its 5,000-cell budget after each consumed
request, removes requests in the same order and retains all per-search limits.
No eight-request admission or increased node limit is adopted. An unconsumed
speculative result is discarded at the end of the queue call and does not alter
simulation scheduling or the cumulative count. **Speculation can nevertheless do
extra CPU work**, including a second loop whose request does not fit this frame,
rejected results, repeated preparation and dependency validation. Preserving the
queue's accounting does not promise equal total CPU work or smaller frame times.

Both private contexts are lazily allocated on the first eligible pair and reused.
Each dependency category is capped at 8,192 entries; overflow changes only reuse,
not the normal search's capacity. A local 64-bit fixture measures 12,071,088 bytes
for the batch's fixed storage. Bounded dynamic query/height/order/frontier storage
adds about 1.6 MB, plus two map-dependent corridor arrays, allocator overhead and
the existing worker's runtime/stack. This is approximately 13 MiB of extra search
storage at those bounds, not a measured iOS resident-memory figure. No dense
per-terrain-cell worker arena or larger worker pool is added.

Both tasks finish before runPair returns, including when either throws. Startup,
floating-point setup or allocation failure discards speculative scratch and uses
normal dispatch; these tasks have not applied AI/path/world effects. Other exceptions
join, clear batch state and propagate. Context bindings release before completion
is published. No request/result survives the queue call, reset or shutdown. iOS
pause prevents admission and lifecycle changes reject reuse; an already running
pair completes the current synchronous call, without mid-search cancellation.

## Logs and validation

New bounded session summaries:

- `[PATH_PARALLEL_BATCH] enabled width=2 worker=1 caller=1 ...`
- `[PATH_PARALLEL_BATCH] stopped batches=N accepted=A rejected=R unused=U width=2`

N confirms completed pairs; A counts reused completions, R attempted completions
that failed validation, U completed speculative results never requested by their
queue callback. These are distinct from shadow-validator samples. Existing
PATH_SEARCH_WORKER searches also count the worker half of each pair.

`test_parallel_path_batch.py` compiles the production cell/record/list/context,
ordinary preparation/loop/finalization, dispatcher, queue loop and live occupancy
reader with controlled world services. Twelve tests cover actual overlap, 48
serial/parallel route and budget comparisons across both retail modes, one-use
queue-ordered consumption, original budget stop/next-frame continuation, exact
cell/request/policy/admission/epoch/lifecycle/corridor/height rejection, live object
query changes without cell mutation, overflow/hash collisions, predictor behavior,
pause/debug/missing-key/wrap handling, joined exceptions and FP environment.
The signed enum ObjectID snapshot also compiles, avoiding a fixture-only unsigned
type assumption. Fixture world/terrain/line traversal and Path materialization
remain controlled services, not a complete engine replay or graphics test.

All 112 workflow QA tests pass locally. All 12 new batch tests pass AddressSanitizer/
UndefinedBehaviorSanitizer and ThreadSanitizer. Actionlint and diff checks pass.
The iOS workflow includes both ordinary and ThreadSanitizer runs of the new tests.

Full SDK, iOS movement/lifecycle, replay equivalence and performance validation
are separate from these local regression/sanitizer checks. Useful device cases
include group moves across distant areas, tight spaces/bridges, shared destinations,
blocked units, unit removal, pause/resume and map changes. Acceptance/rejection
counts will show whether the conservative corridor and admission checks allow
enough reuse to justify the extra work.

## Remaining scope

The follow-up [escape-search stage](IOS_PARALLEL_ESCAPE_SEARCH_2026-10-27.md)
extends this baseline to safe and mixed ordinary/safe pairs. The remainder of
this report describes the original ordinary-only stage and its evidence.

This introduces actual simultaneous ordinary searches and validated ordered reuse.
It is still narrower than Reimagined's full prediction/worker system. Closest, safe
and attack kernels, blocked/path patch requests, dozers and other special requests
remain outside this batch. Hierarchical search, optimization and engine effects
stay on main. More workers, dense map-sized nodes, eight-request batching and new
search limits are not part of this change. No device speedup is claimed.
