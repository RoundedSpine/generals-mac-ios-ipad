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

## Native build and first device evidence

Code 3228907bc passed Mac QA, the full race-check stage, actual iOS compilation,
device packaging and unsigned IPA upload in
[run 40606130507](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40606130507).
The host remains macos-15 ARM64. The separate dependency-save step was skipped;
it is not another successful cache-write measurement.

The supplied generals-stderr.log identifies revision ~3228907, contains all new
diagnostic tags, reaches the score screen and exits zero. No fatal or primitive-
restart report appears. The WAV sample_count warning and platform browser stubs
remain; the reused cache-directory marker is not a pipeline-hit measurement.

All 11,248 admission outcomes balance exactly:

| Outcome | Calls |
| --- | ---: |
| Fewer than two requests remain | 7,398 |
| Unsupported prediction | 1,490 |
| New pair dispatched | 795 |
| Existing executed pair | 795 |
| Dozer exclusion | 740 |
| Missing object | 20 |
| Missing capture | 5 |
| Existing unexecuted preparation | 5 |
| All other outcomes | 0 |

Short queues account for 65.77% of preparation calls. This is the largest observed
admission category, not a percentage of frame time, serial searches or failed
unit commands. Another worker cannot supply a missing second queued request.
Prediction failures split into 788 non-final, 689 attack and 13 no-longer-waiting
cases; these are first failed guards, not exhaustive eligibility reasons. Slot 0
accounts for 1,426 and slot 1 for 64 of these failures. All five capture failures
have an old path; the five existing-unexecuted returns are too few in this sample
to justify making their retry policy the first optimization.

795 pairs balance as 1,562 primary plus 28 fallback-only completions. Primary
results have 1,400 accepted, 162 rejected and none unused (89.63% acceptance).
All 28 fallback searches are early fallbacks: 17 accepted, 11 rejected, none
unused. Separately queued closest primary searches have 31 completions and 14
accepted; they are already included in primary totals. No safe kernel is
recorded. Serial kernels split into 6,830 ordinary and 205 closest. Accepted
speculation (1,417) plus serial kernels (7,035) equals 8,452 finalizations; reuse
covers 16.77% of those measured completion phases. This does not measure all
path APIs, command counts, route success or a performance improvement. Compared
with the previous session, primary acceptance is lower, but workloads differ and
the logs do not explain individual rejection causes.

7,586 pending queue calls total 2,515.208 ms, mean 0.332 ms and maximum 88.101 ms.
Fourteen reach 20 ms, one reaches 50 ms and none reaches 100/500 ms. This session
does not reproduce a half-second stall inside a measured pending queue call;
whole-frame/input/render timing remains outside these probes.

| Retained queue | Wall ms | Observed context |
| --- | ---: | --- |
| 1307 | 88.101 | Five callbacks, two pairs, five serial ordinary kernels; pair time 61.331 ms and serial time 23.774 ms |
| 102 | 37.638 | Fifteen callbacks, seven pairs, three serial kernels; pair time 23.469 ms and serial time 13.419 ms |
| 156 | 36.688 | Zone recalculation, no request callback or pair |
| 6100 | 31.334 | Zone recalculation, no request callback or pair |

The 60.576 ms pair in queue 1307 contains a 60.512 ms worker ordinary kernel
with 4,515 cellsExamined and 5,144 retained records; the caller takes 0.490 ms
with 135 cellsExamined. Queue 102 contains a 23.136 ms pair whose worker takes
23.118 ms with 3,666 cellsExamined and 3,939 records. These are substantial
recorded searches, rather than demonstrably empty worker waits. They still
measure wall time, including possible preemption, and do not identify the cost
of allocation, read tracking, hashing or expansion individually. Samples do not
include per-result acceptance, so neither slow worker result can be classified
as reused or rejected from this log.

Pair 211 in queue 1997 takes 11.843 ms while its caller and worker kernels take
only 0.029/0.058 ms with 1/8 cellsExamined. Most of that interval lies outside
the measured kernels. Worker wakeup, synchronization or scheduling is a candidate,
not a demonstrated cause. Its queue is not retained in the independent top four.

Source review confirms that processPathfindQueue recalculates zones synchronously
and returns before processing requests. calculateZones traverses the map and
rebuilds zone relationships; increasing search worker count will not move that
work. The 8,655 charged cells in queue 1307 do not by themselves violate the
original 5,000-cell scheduling rule: its check occurs before each complete AI
callback, so the final request can overshoot the threshold. It is not a per-cell
interrupt or a wall-time budget.

## Evidence-led next investigation

Prioritize the expensive existing search kernels and zone rebuild path before
expanding worker count. Controlled large-search comparisons should distinguish
private-record/read-validation overhead from search work, and bounded result
diagnostics can identify whether the expensive speculative results were reused
or recomputed. Keep the original search limits and scheduling while measuring.
The separate low-work 11.843 ms barrier deserves dispatch/join investigation;
it does not explain the two much heavier worker samples by itself.

For later eligibility expansion, non-final requests are a measured candidate.
AIUpdateInterface::computePath first tests isLinePassable for non-final goals and
may build a quick path without calling findPath. Removing the predictor guard
alone could launch unnecessary full searches; preserve that authoritative fast
path and validate actual demand before accepting such results. Attack and dozer
restrictions also require their own side-effect/read audit. This review changes
no runtime behavior and does not establish a need for more workers.

## Device test

Use normal gameplay with group moves, tight spaces/bridges, combat and rebuilding
paths around obstacles, then exit through the game. The same generals-stderr.log
will include the old timing/result summaries and the new bounded records, without
a new launch flag. Start with the admission totals, compare serial kinds and
then inspect slow samples with matching queue ordinals. Preserve one worker and
the original per-request budget while choosing the next expansion from evidence.
