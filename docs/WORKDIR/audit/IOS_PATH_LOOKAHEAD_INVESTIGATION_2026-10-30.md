# Eligible-request lookahead investigation — 30 October 2026

## Recommendation

Implement a bounded scan across unsupported queue entries, retaining current
eligibility predicates. Start speculation only when the actual queue head is
eligible. Scan at most eight original queue entries, select that head plus the
earliest eligible partners, and apply results only at their original positions.

The first independent production trial can retain the existing one worker and
two result slots. This needs no additional arenas or dynamic pool. Expanding to
four selected requests should follow the participant-arena/pool work in
[the pool feasibility audit](IOS_DYNAMIC_PATH_POOL_FEASIBILITY_2026-10-30.md).
This investigation adds no engine feature flag or runtime/workflow changes.

## What the current code does

`Pathfinder::prepareParallelBatch` inspects exactly the head and its immediate
successor. Missing objects/AI, dozers, unresolved crusher keys or unsuccessful
prediction cause an early return. One unsupported entry therefore prevents a
pair even when eligible requests appear immediately beyond it.

`AIUpdateInterface::predictOrdinaryPath`, `predictSafePath` and
`predictClosestPath` already capture inputs on main without changing waiting
flags, destroying paths or applying goals. The ordinary quick-path predicate
only reads locomotor/movement state; ignored-obstacle lookup is a field read.
Safe prediction resolves repulsors on main. These mechanisms can be reused for
lookahead. Keep their short-circuit order and all current exclusions.

In particular, retain ordinary attack, stuck/patch, nonfinal, quick-path,
production-exit and extent guards. The actual `computePath` can bypass a full
search for nonfinal line-passable requests; attack and stuck requests execute
different logic. Including these cases is a different prediction experiment.
The reference's wider ordinary prediction is not required for queue scanning.

The normal `queueForPath` deduplicates pending object IDs. However, queue
processing clears the head slot before invoking its AI callback, so that object
can legitimately enqueue a fresh request at the tail during the callback. A
lookahead window must distinguish queue occurrences, not just object IDs.

## Two important constraints found by experiment

### Preserve results across skipped positions

The existing active-batch test recognizes only `jobs[0].queueIndex` and
`jobs[1].queueIndex`. For a queue `eligible A, unsupported X, eligible B`, merely
changing selection to A/B still clears the batch at X and discards B.

A controlled production-method fixture gives:

| Selection/lifetime policy | Accepted speculative results |
| --- | ---: |
| Current adjacent-only pair | 0 |
| Broader selection, original two-index lifetime | 1 |
| Broader selection with retained scanned window | 2 |

The same result holds across ring wrap. A serial X callback still runs in place.
If it changes a captured destination, terrain heights or inherited ignored
obstacle, the later result is rejected and recomputed. A world-epoch change
retires the old window. Do not bypass these existing validation checks merely
to improve the reuse count.

### Anchor speculation at an eligible head

Under our per-request frame budget, scanning ahead of an unsupported head can
perform substantial work that the frame never consumes. Because our participants
join before processing the head, this does not overlap that unsupported callback.
Process it first, then decide whether the new head has useful partners.

The controlled low-budget probe uses eight unsupported requests followed by two
eligible requests. Forcing one actual callback per queue call produces:

| Policy | Inspected queue entries across calls | Discarded speculative primary results |
| --- | ---: | ---: |
| Unanchored scan-eight window | 52 | 13 |
| Eligible-head-anchored window | 11 | 1 |

Both process the same callbacks in the same frames with the same paths and
charges. This is a stress case, not a measured device speedup or representative
waste rate. Even anchored lookahead can discard partners if a preceding selected
request or skipped callback consumes the remaining budget.

This refines the previous pool audit: skip unsupported partners, but process an
unsupported head serially before starting a speculative batch.

## Proposed window and capture contract

Use lightweight window metadata separate from heavy result slots:

- Original head, inspected span and captured tail boundary.
- World and lifecycle epochs at capture.
- Selected job count and each selected job's original queue index/ObjectID.
- An inspected-window marker even when fewer than two eligible jobs are found.

Use modular queue offsets for membership; raw numeric index ranges fail at ring
wrap. Keep a window across all inspected positions, including holes between
jobs. Retire it when the head exits its inspected span, the processing call ends,
or reset/world/lifecycle invalidation makes it obsolete. Reset/load must not let
reused queue indices match an old window. Newly appended tail entries belong to
a later window. The existing consumer still requires exact queue position,
object identity, request inputs and live dependencies.

For an ineligible head, a one-entry inspected window suffices. For an eligible
head without enough partners, retain the inspected negative result to avoid
repeatedly scanning the same suffix as serial callbacks advance. Invalidate
deliberately on epoch changes; caching a failed prediction must never prevent
the real callback from running serially.

Capture one candidate at a time into a value record, initializing every field
before each attempt. An unsupported entry must not leave safe/closest flags or
coordinates in a slot later reused by a successful candidate. Missing objects,
missing AI, dozers, unresolved crusher keys and zero valid movement surfaces do
not consume a selected-job slot. Skip later duplicate IDs defensively. Keep
global pause/debug/map/allocator/context guards authoritative.

Keep the selected-job cap independent of worker count. Stop scanning at the
original tail, the eight-entry cap or the selected-job cap, whichever comes
first. A selected ordinary request and its conditional closest fallback remain
one logical work item with independently validated result phases.

Illustrative sequence:

```text
main: inspect head eligibility
      if unsupported: process the ordinary head callback
      otherwise: capture head + eligible partners in the bounded window
participants: compute selected requests; join before simulation resumes
main: process every original callback in order, including skipped positions
      validate/reuse only at the matching position; otherwise recompute
      check the existing budget after each actual callback
      discard unconsumed results and retire the window at call end
```

Do not move dequeueing, waiting-flag updates, goal registration, ally movement,
path installation or callback scheduling to workers. Do not copy Reimagined's
eight-request budget batching as part of this change.

## Controlled verification

The local investigation generator is
`/workspace/scratch/lookahead-investigation.py`. It builds the existing
complete-worker/reused-context/cache fixture with temporary dispatcher selection
and window changes; it does not edit production source. Its five modes are:
serial, current adjacent dispatcher, naive wider selection with old lifetime,
unanchored retained window, and eligible-head-anchored retained window. All wider
modes keep the existing two-job executor and arena count.

The 18-scenario matrix compares raw Path coordinates/layers, optimized links,
adjusted destinations, callback order, budget charge, queue head/tail, final
corridor, ignored obstacle and tunneling state against serial. It covers:

- Unsupported middle/head, missing objects and ring wrap.
- Terrain-height and destination changes from skipped callbacks.
- Self-requeue at the tail and defensive duplicate queue IDs.
- Eight-entry bounds; singleton and wholly ineligible windows without repeated
  suffix scans during an unchanged queue-processing call.
- World invalidation, inherited ignored-obstacle changes and corridor changes.
- Ordinary, safe, closest, early-null/closest fallback and actual failed-fine
  search followed by closest fallback.

All 18 scenarios match across five modes in both retail pathfinding settings.
Repeat the matrix with a forced one-cell frame allowance and drain the queue
over subsequent processing calls, comparing per-call charges as well as final
results: both retail modes match. The normal fixed-mode matrix passes TSan and
ASan/UBSan; the budget/drain fixed-mode matrix also passes ASan/UBSan. Commands:

```sh
python3 /workspace/scratch/lookahead-investigation.py
python3 /workspace/scratch/lookahead-investigation.py --legacy
python3 /workspace/scratch/lookahead-investigation.py --budget --drain
python3 /workspace/scratch/lookahead-investigation.py --legacy --budget --drain
python3 /workspace/scratch/lookahead-investigation.py --tsan
python3 /workspace/scratch/lookahead-investigation.py --asan
python3 /workspace/scratch/lookahead-investigation.py --budget --drain --asan
```

The fixture executes production queue, hierarchy, search, Path/optimization and
validator methods with controlled object/terrain/allocation services. Its AI
callbacks and prediction responses are controlled, including injected mutations;
it does not reproduce every real attack/dozer/state-machine callback or measure
iOS performance. The generator is an investigation artifact, not a replacement
for committed production regression tests when implementing the feature.

## Production work and measurements still needed

Extract value-only candidate capture and a bounded window helper, then use
explicit captured queue indices throughout dispatch. Preserve the fine-only
OFF-path implementation or guard the trial behind complete-worker mode. Add
window-aware admission counters; current slot-0/slot-1 prediction counters cannot
describe inspected positions independently of selected jobs. Separate inspected,
eligible, selected, executed, reused, rejected and discarded counts and report
bounded distributions rather than per-entry logs.

Before enabling the trial, commit production regressions for the matrix above
plus object deletion, lifecycle changes, newly eligible predictions, nested
queries from skipped callbacks, exception cleanup and save/reset window
invalidation. Run the existing suite and sanitizers, compile natively, then test
mixed movement/attack/builder queues and tighter frame-budget scenes on device.
Measure actual eligible partners per anchored window and useful/unused work.

No historical device log records the full eight-entry eligibility distribution.
Current adjacent-pair rejection counts cannot predict the extra worker work or
justify four selected jobs. The two-slot trial can establish this evidence while
keeping current fixed context/result storage and one worker. More retained jobs
and dynamic assignment remain the next independent step.
