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
