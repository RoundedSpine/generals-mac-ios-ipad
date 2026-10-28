# Match closest preparation and explain remaining mismatches — 28 October 2026

## Evidence and scope

The ~40bb42b device session reuses 1,524/1,548 primary phases and has no corridor
or explicit overflow rejection. Remaining first failures include 17 primary
permanent-admission checks, 16 fallback closest-policy checks and one fallback
permanent-admission check. The session does not identify a changed closest field
or the captured/current record counts. Keep exact validation and investigate the
inputs rather than removing those guards.

Source review finds that closest speculative preparation bypasses the real
hierarchy, marks its corridor unrestricted and assumes gotHierarchicalPath is
true whenever not tunneling. The actual caller runs findClosestHierarchicalPath
and may obtain no route or a restricted corridor. A compiled production-dispatch
probe with an unavailable hierarchy reproduces ClosestPolicy rejection for both
queued closest and early closest fallback. This establishes a source mismatch;
it does not prove that hierarchy availability explains all 16 device failures.

A second probe creates an unrelated persistent goal record after dispatch and
reproduces Admission rejection when captured/current counts are zero/one. Counts
can change without changing an observed cell. However, allocateRecord uses that
frozen count plus live private transient usage to decide whether further search
records fit the 30,000-record bound. Near exhaustion, changing the count changes
allocation outcomes, search termination and potentially the returned route.
The exact-count check is conservative, but cell validation alone cannot replace
it. Any future precision improvement must account for successful and failed
admission decisions, record release/reuse and finalization, not just a final
record count or a guessed amount of headroom.

## Implementation

Remove the provisional closest hierarchy branch. Queued closest and conditional
closest fallback now run the normal coarse preparation on main in their own
bound context. Capture the real hierarchy result, tunneling/started-stuck policy
and corridor before the existing fine-loop capture point. If tunneling already
requires an unrestricted search, retain the original hierarchy skip. Continue
using each phase's original private records and bounded observations.

Extend PreparationScope to all bound primary preparation and to fallback
preparation. The existing guards abort before shared retail-mode changes or
world cleanup. Failed private recovery discards the batch without disabling the
worker; the authoritative caller performs normal recovery. Exclude speculative
closest coarse calls from the authoritative hierarchy timer, as already done
for ordinary preparation. Their cost belongs to preparation timing.

The actual caller still performs its own hierarchy and original accounting
before fine-result validation. No coarse charge is copied from speculation;
neither hierarchy nor Path finalization moves onto a worker. One worker plus
main, adjacent pairing, queue order, search limits and budget checks remain.
Exact closest-policy equality and permanent-record equality remain intact.

Review of the coarse recovery boundary also reveals that a completed coarse
Path can leak if subsequent list cleanup aborts. The earlier buildHierarchicalPath
owner covers partial construction only, then releases its result to the coarse
search routine. In parallel builds, internal_findHierarchicalPath now owns the
completed Path until cleanup succeeds in both the reached-goal and closest-result
branches. It releases ownership on normal return and uses engine deletion on
unwind. The new regression compiles the actual coarse routine, injects a cleanup
abort after Path construction and reproduces the leak before the fix. Successful
returns retain caller ownership; non-parallel source branches are preserved.

## Bounded optional summaries

The existing GENERALS_PATH_TIMING option adds four shutdown rows, two per phase:

- PATH_ADMISSION_MISMATCH: calls, higher, lower, captured_min, captured_max,
  current_min and current_max. Higher/lower compare current usage with captured
  usage. Minima/maxima describe independently aggregated failing counts; they are
  not paired endpoints of a particular request. All fields are zero with no
  observed mismatch.
- PATH_CLOSEST_MISMATCH: calls and per-field counts for blocked, cost_multiplier,
  move_allies, goal_obstacle, started_stuck, hierarchy and initial_ignored. Several
  fields may differ in one call; their sum need not equal calls. Comparisons
  preserve floating-point equality, including NaN inequality.

Only the main-thread validator updates these scalar aggregates at the original
reached checks. The permanent count is read once. Closest equality is evaluated
once before classifying scalar differences. Earlier failures still short-circuit
later checks. There are no retained requests, pointers, per-cell counters, clocks
or per-request log messages. Diagnostics disabled uses the original expressions.
Existing result first-reason counters remain the authoritative rejection totals.

## Cost and device follow-up

Matching closest preparation adds coarse work before dispatch, including fallback
capture that may never be executed if an ordinary search succeeds. This trades
some main-side preparation cost for better prediction fidelity; it is not a
measured performance win. The next device log must show both preparation cost
and actual fallback reuse, rather than treating a lower rejection count alone
as sufficient. No new worker, search context, bound or map-sized array is added.

Repeat the saved mission and include unreachable destinations/obstacle replanning,
then exit normally. Check closest-policy and corridor outcomes, the new field
summaries, preparation totals and slow-pair dispositions. Permanent-admission
rejections remain expected when captured/current usage differs. Device movement,
native SDK compilation and timing confirmation for this change are pending.

## Verification

Six added cases cover real hierarchy availability/restricted corridors with
serial route/destination/accounting comparisons in both retail modes; private
recovery isolation; tunneling's hierarchy skip; exact permanent admission and
short-circuit checks for both phases; every closest policy field, NaNs and
bounded report ranges; and actual coarse ownership through successful/throwing
cleanup in both result branches. The general dispatcher fixture uses controlled
hierarchy services and counts private and authoritative calls separately. The
ownership case compiles internal_findHierarchicalPath itself with controlled
zone/edge services. Neither fixture is a full-engine replay.

All 206 local workflow cases pass: the 205-case workflow suite plus the final
coarse-ownership regression run separately after reproducing and fixing the leak.
All 85 batch cases pass ThreadSanitizer (the 84-case suite plus the added ownership
case), and all six new cases pass ASan/UBSan. Existing diagnostic enabled/disabled
validation traces and serial route checks remain passing. Diff checks pass.
The only intervening diagnostic-header edit splits adjacent if statements onto
separate lines; it changes no expression or control flow. Native SDK and device
verification remain pending for the pushed runtime change.

## Native build and device follow-up — 29 October 2026

GitHub Actions [40688598327](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40688598327)
for 81d5a83a3 completes successfully on the configured macos-15 ARM64 runner.
Mac workflow QA, copied-query ThreadSanitizer checks, native iOS compilation,
unsigned packaging and artifact upload pass. The separate dependency-save step
is skipped after successful dependency-cache restoration.

The next supplied device log identifies ~81d5a83, reaches ScoreScreen and exits
zero. There is no logged fatal/assertion or primitive-restart warning. Existing
browser/platform stubs and four WAV wrong-sample-count messages remain. Normal
completion does not establish that the recovery/cleanup edge executed or verify
device memory savings from the ownership fix.

| Measurement | Previous ~40bb42b | Current ~81d5a83 |
| --- | ---: | ---: |
| Completed pairs | 793 | 946 |
| Primary reused / executed | 1,524 / 1,548 | 1,811 / 1,852 |
| Primary reuse rate | 98.45% | 97.79% |
| Fallback reused / executed | 21 / 38 | 38 / 40 |
| Fallback reuse rate | 55.26% | 95.00% |
| Fallback closest-policy first rejections | 16 | 0 |
| Primary corridor / explicit overflow first rejections | 0 / 0 | 0 / 0 |
| Preparation attempts / total time | 11,314 / 98.741 ms | 11,985 / 142.645 ms |
| Maximum measured queue update | 41.895 ms | 41.130 ms |
| Queue updates at least 5 / 20 / 50 ms | 53 / 10 / 0 | 112 / 15 / 0 |

All 40 executed fallbacks are early fallbacks; 38 are reused and two fail exact
permanent admission. Queued closest executes 20 primary phases, with ten reused;
these are included in the 1,852/1,811 primary totals. Safe and ordinary-loop-
failure fallback execution are not exercised by this log. Primary first failures
are permanent admission (33), world epoch (6) and search kind (2). No phase has
discarded or validated-unfinished work. Accounting balances: 1,852 primary plus
40 fallback-only slots equal two times 946 pairs; 1,811 primary plus 38 fallback
reuse plus 7,296 serial kernels equal 9,145 finalizations.

The new closest-field summaries have zero calls for both phases, agreeing with
zero closest-policy first rejections. Permanent-admission summaries also balance:
primary 33 = 15 higher + 18 lower, fallback two = one higher + one lower. Captured
primary counts range 13,278–15,670 and current counts 13,273–15,667; fallback
captured counts range 15,637–15,643 and current counts 15,638–15,640. These are
independent aggregate ranges, not per-request deltas, global pool high-water
marks or a measurement of how many transient records a rejected phase required.
They cannot prove that changing usage was harmless for every rejected search.
The exact guard correctly remains active. Permanent admission now explains 35
of the 43 first rejections across both phases.

All eight retained read samples have flags zero. Together they contain 12,667
unique query entries from 306,274 actual observations. The slowest worker still
records 3,501 entries from 138,969 observations, and its result is reused. This
confirms bounded deduplication remains active; retained samples are not whole-
session read totals and earlier first failures can bypass later validation checks.

The slowest queue update, 41.130 ms, contains one 38.380 ms pair and no serial
kernel. Both pair results are reused; avoiding rejected recomputation cannot
remove that entire barrier. Three other retained queue updates are zone rebuilds
at 36.744, 33.227 and 30.604 ms, with no callbacks or pairs. Maximum validation is
0.281 ms and maximum authoritative hierarchy is 2.164 ms. No measured queue update
reaches 50/100/500 ms; these scopes do not cover whole-frame or touch latency.

The measured queue mean rises from 0.261 to 0.330 ms, and the number of updates
at least 5/20 ms rises. Preparation averages 0.0119 ms per attempt versus 0.0087
ms previously. Workload and run duration differ, timing totals overlap, and the
added private hierarchy has a real preparation cost. The stronger fallback reuse
does not establish a net speedup, nor do these unmatched sessions establish a
performance regression. Keep the preparation fix; the targeted policy mismatch
is absent in this device session. Before broadening dispatch, investigate whether
exact allocation-decision dependencies can distinguish harmless count changes
while preserving capacity failures and finalization semantics. Separately, the
reused long kernels and synchronous zone rebuilds remain measured tail costs.

This follow-up reviews the log/build and checks counter consistency only. No
runtime change or new build is introduced; unchanged tests are not rerun.
