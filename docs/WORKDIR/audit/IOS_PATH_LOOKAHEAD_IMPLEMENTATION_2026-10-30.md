# Anchored eligible-request lookahead — 30 October 2026

## Implemented stage

`GENERALS_PATH_LOOKAHEAD` defaults OFF, requires complete-worker mode, and is
enabled only for `experiment/ios-mod-testing` in the iOS workflow. It applies the
[lookahead findings](IOS_PATH_LOOKAHEAD_INVESTIGATION_2026-10-30.md): capture an
eligible actual head and its earliest eligible partner within at most eight
original queue entries. Keep one worker plus main, two selected requests,
existing arenas/result slots, prediction gates, record allowance and the
per-request queue-budget check. This stage does not add a dynamic pool or a
four-request batch.

Unsupported partner entries remain serial callbacks at their original positions.
An unsupported head runs before any speculative future work. Missing objects or
AI, dozers, unresolved crusher keys, zero movement surfaces, unsuccessful
predictions and later duplicate IDs do not consume a selected slot. Candidate
values are initialized afresh on every capture. Ordinary attack/nonfinal/quick/
stuck and other prediction exclusions remain unchanged. Safe/closest requests
retain their existing capture policies.

## Window lifetime and validation

The lightweight `PathLookaheadWindow` is separate from heavy result buffers. It
stores an inspected modular span and world/lifecycle epochs. A skipped queue
position inside that span does not clear later results. A failed partner scan
also retains its inspected span without allocating result buffers, preventing
repeated suffix scans during an unchanged processing call.

The original tail bounds every scan; appended or requeued requests belong to a
later window. Exact original queue indices are copied into primary/fallback
jobs and remain mandatory at consumption. Nothing is dequeued or installed by
the worker. A nested query for a future unit cannot consume its prediction at
the skipped callback's queue position.

Clear positive and negative windows at queue-call end, including a budget stop.
Leaving the span or changing world/lifecycle epochs retires the old window.
Reset clears joined results before retiring map cells, and post-load processing
invalidates/clears transient jobs and windows. A lifecycle transition during
capture aborts before dispatch. The existing joined exception/recovery cleanup
also clears the window before returning or rethrowing.

Every accepted result still passes the complete request/movement, allocation,
world/lifecycle, cell, occupancy, height/layer and object checks. A skipped callback
may change these inputs; retain rejection and serial recomputation. Later results
are never charged merely because they were computed. A frame may discard a
speculative partner it does not reach, as before.

The compile-time OFF path retains the adjacent dispatcher and fine-only modes.
Lookahead works with profiling, the frozen occupancy cache and arena reuse each
disabled; complete-worker mode is the required execution boundary.

## Bounded diagnostic meanings

`[PATH_LOOKAHEAD] enabled scan=8 selected=2 anchor=head ...` confirms the feature
at the first executed pair. With `GENERALS_PATH_TIMING` enabled, shutdown emits:

- `[PATH_LOOKAHEAD]`: new inspected windows, retained-window attempts, retired
  nonempty windows, inspected entries, eligible entries, selected primary jobs
  and successfully dispatched batches. `selected` counts jobs; `dispatched`
  counts pairs. Capture or lifecycle failure may leave selected jobs undispatched.
- `[PATH_LOOKAHEAD_SKIP]`: candidate exclusions by category.
- `[PATH_LOOKAHEAD_SCAN]`: number of windows inspecting each count from zero to
  eight. An unsupported head normally gives a one-entry window.
- `[PATH_LOOKAHEAD_ELIGIBLE]`: eligible entries found before scanning stops.
- `[PATH_LOOKAHEAD_PARTNER]`: selected partner offset from the original head.
- `[PATH_LOOKAHEAD_PREDICTION]`: first ordinary prediction rejection for candidates
  whose ordinary, safe and closest prediction all failed.

These are bounded session counters, not per-entry logs or worker writes. The
scan stops at two eligible entries, so eligible distributions are censored at
two; they are not a full eight-entry availability histogram. Existing two-slot
prediction counters describe the adjacent OFF path; new candidate exclusions
belong in the lookahead rows. `lookahead_head` and `lookahead_sparse` are separate
terminal admission categories. Existing result/rejection/unused counters retain
their definitions.

## Verification

`scripts/qa/test_path_lookahead.py` compiles the production dispatcher, window,
queue loop, hierarchy, Path/optimization and validator with controlled surrounding
services. Its 24-scenario matrix compares serial execution against lookahead in
both retail modes, including raw/optimized paths, adjusted destinations, final
flags/corridor, callback order, queue positions and charges. It repeats across
budget-limited processing calls, checking each call's charge and clearing state.
Timing/cache/reuse-OFF configurations are also exercised.

Additional cases check nonadjacent reuse for ordinary/safe/closest and both
fallback mechanisms; every exclusion category; singleton/negative windows and
scan bounds; lifecycle changes during capture; throwing recovery with joined
Path cleanup; positive/negative post-load invalidation; actual deletion of a
captured future object; and exhaustive modular span membership/reset/epoch
changes with bounded report output. Matrix callbacks include nested future-unit
queries, requeueing, newly eligible requests and changes to terrain, destination,
relationships and inherited flags.

All 279 preceding regression cases and eleven new lookahead cases pass (290
total). All eleven new cases also pass TSan and ASan/UBSan; the deletion case and
final timing-OFF configuration were checked in a targeted follow-up to the
ten-case sanitizer run. Controlled service fixtures do not execute every
production AI state-machine callback or constitute
native/device validation. Native SDK compilation and device scenarios remain
required after publication.

## Device trial

Use mixed movement queues with ordinary ground units, attacking units and
builders, including bridges/tight spaces and several repeated group orders.
Confirm normal destinations and input response. Retain a comparable scenario
and inspect partner offsets, dispatch/reuse/rejection/discard rates and queue wall
times. No on-device speedup or optimal worker count is claimed from host tests.
The retained pool/arena result storage is unchanged; the new window and optional
profile add small fixed metadata, not another search arena or result buffer.

After this trial, detach arenas from logical result slots and add the bounded
joined pool before increasing selected jobs or worker count. Keep wider batching,
independent map-sized node limits and altered queue budgets as separate decisions.

## Device follow-up — 31 October 2026

The supplied `~8084275` stderr log confirms anchored lookahead, complete APIs,
two reusable participant arenas, occupancy caching and fast zone merging. It
exits with code zero. No worker/environment/allocation failure, dependency-log
overflow or unfinished validated result is recorded. Movement correctness still
requires gameplay observation; a normal log does not prove every scenario.

All counter identities reconcile: 10,955 windows plus 1,173 retained attempts
equal 12,128 preparations; inspected entries equal eligible entries plus skips;
histogram totals and weighted inspected counts match; 920 selected pairs execute.
All nonempty windows retire. Primary outcomes are 1,796 reused, 21 rejected and
23 unused, totaling 1,840 (97.61% reused). Fallback outcomes are 39 reused and four
unused, totaling 43. Rejections detect changed cell snapshots, including goal
unit changes in all 21 cases; there are no log-full/capture failures.

Partner offsets are 878 adjacent pairs and 42 nonadjacent pairs (4.57%): 30 at
offset two, six at three, four at four, one at five and one at seven. The last
exercises the eighth entry of the scan. This confirms nonadjacent dispatch is
used, not 42 net additional batches compared with an unrecorded counterfactual.
There are 9,223 unsupported-head windows and 812 singleton/sparse windows. The
candidate exclusions include 5,760 dozers and 3,724 failed predictions (2,107
nonfinal, 1,596 attack and 21 not waiting); they include head and partner entries.
Eligibility counts remain censored at two and cannot select an optimal pool size.

The queue maximum is 25.990 ms across 7,854 measured queue calls; seven reach
20 ms and none reach 50 ms. The pair maximum is 17.042 ms. All four retained
slowest queues have no dispatched pair. The largest retained serial closest
search is 21.675 ms, with 5,069 examined cells, 5,506 records and 8,755 expansions.
These pathfinding timers do not cover every game/UI/rendering frame or rule out
unlogged input delays. A larger pool cannot split that single serial search.

A comparable retained worker matches the old cache-OFF session's 3,225 examined
cells, 3,683 records and 142,281 occupancy requests. It now evaluates 3,550 live
queries plus 138,731 cache hits (97.50%). Complete worker time is 17.004 ms versus
33.477 ms in that older session; fine time is 16.691 versus 32.867 ms. This is
supporting evidence for the accumulated cache/reuse work across separate sessions,
not attribution to lookahead or a controlled device speedup benchmark. Another
3,666-cell/3,939-record worker records 12.870 ms versus the preceding cache-ON
session's 14.101 ms, with identical query/hit counts; that difference is also
uncontrolled.

Native layout reports a 2,804,560-byte context and 1,520,720-byte job, with 64-byte
private nodes and 48-byte permanent records. The job grows by 16 bytes relative
to the earlier layout because the optional timing type adds two admission
counters. No extra arena/result slot is introduced; resident memory is unmeasured.

Keep the lookahead trial enabled. The results support continuing the planned
participant-arena separation and bounded joined-pool work, while leaving the
gain from more workers unproven and retaining all prediction/validation policies.
