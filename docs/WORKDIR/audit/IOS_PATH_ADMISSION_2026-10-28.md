# Pair admission and bounded slow-call records — 28 October 2026

## Purpose

The first dba0038 timing log has 6,621 serial loops and 1,333 reused completions,
with only 93 validation rejections. Queue max is 76.476 ms; rare pairs reach
58.739 ms. Before expanding workers, explain where pairing stops and retain
enough scalar context to investigate those outliers. This extends the existing
GENERALS_PATH_TIMING option, default OFF and enabled for the experimental IPA.
No eligibility, request order, search limit, queue budget or worker-count changes.

## Admission accounting

PATH_PAIR_ADMISSION records one terminal outcome for every prepareParallelBatch
call. Sum its categories to obtain calls. Categories, in original guard order:
unavailable worker, runtime debug, paused, nested context, existing pair, short
queue, duplicate object IDs, missing object, missing AI, dozer, uninitialized
crusher key, unsupported prediction, missing captured work, or dispatched pair.
Environment/thread/allocation/other exceptions have separate outcomes. A build
whose debug macros disable dispatch records debug_build. Existing_pair is normal
reuse of an already executed pair, not a failed new batch. Existing_unexecuted
means a prior preparation attempt remains active but supplied no executable pair;
the existing dispatcher skips retrying it at its second queue entry. This is
distinct from successful parallel work and does not change that behavior.

PATH_PAIR_PREDICTION reports the first unsupported-prediction reason separately
for each slot. Ordinary prediction explains its first failed guard in the same
short-circuit order as before: not waiting, safe, approach, attack, blocked/stuck,
non-final, quick path, production exit or out-of-extent endpoints. Safe/closest
predictors are still tried normally. A reason is counted only if all three
predictors fail; an ordinary safe/approach rejection followed by a successful
specialized prediction is not an admission failure. Thus safe will normally be
zero here, and approach identifies an approach that the closest predictor also
declined. There is no second prediction pass or extra expensive live query.

The predictor accepts an optional explanation pointer; existing three-argument
callers remain valid. Without timing, no pointer is requested by the dispatcher.
The enum/optional interface remains compiled with the experimental predictor;
diagnostic storage, counters, clocks and logs remain guarded by the timing option.

PATH_PAIR_CAPTURE counts each slot lacking either a primary or captured fallback
kernel, classified as ordinary/safe/closest. Immobile and existing-path flags are
supplementary and may overlap. Counts are slots, not attempts, and can include a
slot whose fallback was not prepared because the other slot prevented canPair.
They do not identify the exact terrain/zone/preparation return that failed.
The extra surfaces/path flag reads are simple main-thread getters used only for
diagnostic classification after missing work is established.

PATH_SERIAL_KINDS distinguishes ordinary, safe and closest caller loops. These
counts include direct API calls as well as queued work and caller recomputation;
they are not counts of unit commands or failed predictions.

## Slow-call records

Keep the four longest measured queue scopes and four longest completed parallel
barriers, sorted by elapsed nanoseconds with earlier entries retained on ties.
The number of slots is fixed; there are no per-request log writes or unbounded
history vectors. No native platform API or new worker is introduced.

PATH_QUEUE_SLOW records a pending queue-call ordinal, initial ring depth, drained
entries, actual AI callbacks, original charged cells, zone-recalculation and
completed flags, phase-call/timing deltas and serial search kinds. Empty queue
calls do not start a clock or consume a record. The ordinal is not a logic frame,
timestamp or gesture ID. Zone recalculation has zero entries/charged cells.
Unwound queue calls can be retained with completed=0 and incomplete charged-cell
information; they must not be interpreted as normal completed accounting.

PATH_PAIR_SLOW records its pair ordinal and associated queue ordinal, barrier
wall time, caller/worker request kind and executed primary/fallback flags, each
role's total kernel wall time, original cellsExamined outcomes and retained private
record counts. cellsExamined is the existing kernel's work counter, not a new
per-expansion timer or a CPU-time measurement. An early fallback-only task has
ordinary request kind, primary=0 and fallback=1; its executed kernel is closest.
Pairs prepared outside processPathfindQueue have queue=0. Lists retain their top
four independently, so an associated queue need not appear in the queue top four.

All batch snapshots are copied on main after runPair joins. Workers still write
only their private existing timing metric. Retained records contain no engine
objects, cells, paths, names or pointers. An internal stack pointer associates
main-thread queue scopes and restores its previous value for nested calls; the
timing owner is noncopyable. Disabled profiling has no retained records/counters.

Queue phase deltas overlap, particularly with nested calls and closest hierarchy
inside preparation. Serial-kind counts attach to the currently active queue.
Failed pairs can contribute aggregate barrier timing but are not retained as
completed pair samples. Data does not establish successful routes, rejection
reasons, a speedup, CPU scheduling delay or device RSS. A long task with little
recorded work motivates further investigation; it does not prove preemption.

## Verification

Seven added cases exercise all admission guard classes, slot-specific prediction
failures, missing captures, joined failure handling and debug exclusion; stable
top-four retention, empty/nested scope behavior and scalar ownership; actual queue/
pair correlation after scratch is cleared; mixed safe/closest/early fallback;
serial kind attribution and the unchanged one-cell budget cutoff. The real
predictor and its production declaration compile together, with and without an
explanation pointer, checking guard priority, query counts and unchanged outputs
on rejection. Existing timing ON/OFF routes and budget comparisons remain enabled.

All 184 local workflow QA tests pass. All 66 batch tests pass ThreadSanitizer and
the seven new cases pass ASan/UBSan. Follow-up sanitizer cases verify the final
existing_unexecuted classification, queue-ring wrapping and zone-recalculation
early return. Actionlint and diff checks pass. SDK compilation and device
admission/outlier evidence remain pending. Fixtures still use controlled world,
hierarchy and Path services rather than full-engine replays.

## Device test

Use normal gameplay with group moves, tight spaces/bridges, combat and rebuilding
paths around obstacles, then exit through the game. The same generals-stderr.log
will include the old timing/result summaries and the new bounded records, without
a new launch flag. Start with the admission totals, compare serial kinds and
then inspect slow samples with matching queue ordinals. Preserve one worker and
the original per-request budget while choosing the next expansion from evidence.
