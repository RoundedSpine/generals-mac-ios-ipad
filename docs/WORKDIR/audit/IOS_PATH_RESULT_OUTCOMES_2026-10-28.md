# Correlating slow searches with result outcomes — 28 October 2026

## Purpose and scope

The ~b7b492a device log contains a 56.865 ms caller kernel and a 35.077 ms worker
kernel in the same pair, followed by serial work in that queue. Its retained
samples cannot identify whether those speculative results were reused, rejected
or never requested. Add that explanation before changing storage or dispatch.

Extend the existing optional GENERALS_PATH_TIMING diagnostics, already enabled
in the experimental IPA and default OFF elsewhere. Keep all validation policy,
eligibility, worker count, search limits, original per-request queue accounting,
zone processing and graphics behavior. No new launch flag or cache reset.

## Ownership and bounded correlation

The existing join completes before main assigns each executed primary/fallback
phase its scalar pair ID, role and pending outcome. Main alone resolves that
phase; worker code still writes only its existing private kernel timer. An early
fallback-only task has no executed primary phase and keeps primary=not_run.

On terminal resolution, update the corresponding role/phase in the retained
sample with that pair ID. A fixed scan of at most four samples handles sorting
and eviction; no pointer into the sorted sample array is cached in a job. If the
pair was evicted, count its terminal outcome/reason in session aggregates without
updating another retained sample. No map cells, objects, names or engine pointers
are added to retained records. Job reset clears its IDs and status; terminal
guards make repeated cleanup idempotent.

The four retained pairs are still selected by barrier duration, not by result
outcome or individual kernel duration. No additional history vector, per-request
log write, per-cell probe, clock, lock or thread is introduced.

## Status semantics

Each caller/worker task now has primary_result/primary_reason and
fallback_result/fallback_reason in its PATH_PAIR_SLOW row:

| Status | Meaning |
| --- | --- |
| not_run | This phase did not execute in the completed pair |
| pending | Executed phase has not yet reached a terminal outcome when sampled |
| reused | Validation passed and the existing main-side finalization/accounting completed |
| rejected | A selected candidate failed an existing validation check; reason is its first failed group |
| discarded | Executed work was never selected for validation before the original cleanup boundary |
| validated_unfinished | Validation passed, but finalization did not reach the existing acceptance increment before cleanup |

The joined job internally distinguishes validated from pending so exceptional
finalization can be explained. Retained snapshots become terminal at rejection,
completed reuse or cleanup. Destructor cleanup now occurs before timing report,
so a normal exit resolves remaining pending samples before printing them.

Reused includes valid no-path results. One ordinary failure followed by a closest
fallback can reuse two phases for a single AI callback; these are not counts of
successful routes or unit commands. Discarded does not mean validation rejected
the result and does not identify whether budget, changed callback behavior or
another circumstance prevented selection. Identity/queue-position candidates
skipped before validation retain the existing behavior and become discarded if
they remain unselected; no new rejection counter is charged for those skips.

## First rejection groups and query preservation

Record a check's failure in place through a timing-only wrapper. The wrapper's
disabled form is the original condition. Preserve the original && chain, guard
order and early loop exits. Never repeat a live query to classify its failure.

Groups follow the existing validation order: object identity, locomotor identity,
from/to endpoints, search kind, safe repulsor settings, closest policy, fallback
path precondition, world/lifecycle epochs, paused state, permanent admission,
ignored obstacle, tunneling, prepared start/goal cells and index, movement settings,
explicit read overflow, retail/failover mode, cell dependencies, corridor
dependencies, live occupancy answers and terrain heights. The two kind checks
share one category; movement settings retain their existing internal order but
share a category. Only the first failed group contributes a reason.

cell_dependencies and corridor_dependencies include failure of their bounded
read logs, not only changed values. They do not name an exact cell or imply a
reproduced race. An earlier world_epoch rejection leaves later checks unexamined;
it does not show whether those later checks would also have failed.

Two PATH_RESULT_OUTCOMES rows summarize primary/fallback reused, rejected,
discarded and validated_unfinished counts. Two PATH_RESULT_REJECTIONS rows give
the per-phase first-reason counts. Retained sample limits remain four queues and
four pairs, with four additional aggregate lines in the shutdown summary.
For an ordinary completed session, the primary reused/rejected/discarded totals
match the existing accepted/rejected/unused totals, and likewise for fallbacks.
Exceptional partial dispatches need not be a normal accounting run. No summary
is guaranteed after crash or force-quit.

## Verification and next device check

Six added cases exercise actual ordinary/safe/closest reuse, rejected and unused
work, the original one-cell scheduling cutoff, every rejection group, timing
enabled/disabled live-read counts, first-failure priority, sorting/eviction and
fallback-only correlation through job reuse. Existing ordinary-failure fallback
coverage now also checks both phase outcomes independently. Successful direct
validation followed by cleanup exercises validated_unfinished.

All 193 local workflow QA tests pass, including all 72 batch cases. The six new
cases pass ASan/UBSan. An additional compiled comparison against the prior
cffe4080f validator produces exactly the same 26 outcome/live-read traces as the
instrumented validator. This independently checks the pre-change guard behavior,
in addition to the persistent ON/OFF comparison. The final ordinary/safe/closest
and combined-fallback assertions are also checked separately under sanitizers.
All 72 batch cases pass ThreadSanitizer. The final expanded kind/fallback
assertions also pass their targeted TSan and ASan/UBSan runs. Diff checks pass.

Code aff9c059d passed Mac QA, the full workflow race-check stage, native iOS SDK
compilation, device packaging and unsigned artifact upload in
[run 40637961023](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40637961023).
The host remains macos-15 ARM64; the separate dependency-save step was skipped.
The first device outcome report is recorded below. Fixtures still use controlled world and
Path services rather than full-engine replay validation. No performance claim.

The next supplied log still identifies ~b7b492a. It has neither PATH_RESULT_OUTCOMES
nor PATH_RESULT_REJECTIONS nor per-task result/reason fields in PATH_PAIR_SLOW.
It therefore cannot validate the aff9c059d diagnostics or identify the slow
results' outcomes. This older-code session exits zero: 849 pairs balance as
1,664 primary plus 34 fallback-only slots; 1,466 primary and 22 fallback results
are accepted, with 198/12 rejected and none unused. 1,488 reused plus 6,817
serial kernels equal 8,305 finalizations. Queue maximum is 78.018 ms, with no
measured pending queue reaching 100/500 ms. Its 60.564 ms largest pair again
coincides with serial work but supplies no individual outcome evidence. Install
the IPA from the verified run above and obtain a fresh normal-exit log identifying
~aff9c05 before using rejection reasons to choose a runtime change.

After installing the new IPA, use the same gameplay and exit normally. Match
PATH_PAIR_SLOW pair/queue IDs to the existing queue samples, then inspect both
roles' primary/fallback status and first reason. This can distinguish reused
expensive work from rejected or unused speculation before deciding which
validation/storage/dispatch change is warranted. Separate main-thread zone
rebuild outliers from these search results.

## First aff9c05 device outcome evidence

The next supplied log identifies ~aff9c05 and includes all new outcome/rejection
rows and retained task fields. It reaches the score screen and exits zero, with
no reported fatal/assertion or primitive-restart error. The existing WAV warning
remains. This is the first native device verification of the outcome diagnostics.

692 pairs balance as 1,355 primary plus 29 fallback-only completions. Primary
outcomes are 1,260 reused, 95 rejected, zero discarded/unfinished: 92.99% reuse
among primary completions. Fallback outcomes are 18 reused, 11 rejected, zero
discarded/unfinished. Those counts match the existing accepted/rejected/unused
rows exactly. 1,278 reused plus 6,687 serial kernels equal 7,965 finalizations;
reuse is 16.05% of these measured phases, not a CPU or command percentage.

First primary rejection groups:

| Group | Rejections |
| --- | ---: |
| Corridor dependencies | 80 |
| Permanent admission | 6 |
| Explicit validation-log overflow | 5 |
| Search kind | 2 |
| World epoch | 1 |
| Cell dependencies | 1 |
| All others | 0 |

All 11 fallback rejections are closest_policy. These are first failed groups;
later checks were not necessarily evaluated. Corridor dependency failures account
for 84.21% of primary rejections, but rare overflow failures dominate the retained
expensive searches:

| Pair / queue | Barrier ms | Caller kernel / outcome | Worker kernel / outcome |
| --- | ---: | --- | --- |
| 149 / 1469 | 61.223 | 61.200 ms, 4,428 examined, rejected: overflow | 39.087 ms, 3,227 examined, rejected: overflow |
| 310 / 3779 | 58.887 | 58.883 ms, 6,680 examined, rejected: overflow | 57.933 ms, 6,605 examined, rejected: overflow |
| 54 / 341 | 21.809 | 0.030 ms, one examined, reused | 21.788 ms, 3,666 examined, rejected: overflow |
| 97 / 546 | 3.937 | 3.479 ms, 434 examined, reused | 3.801 ms, 551 examined, rejected: corridor dependencies |

All five explicit overflow rejections occur in the five expensive tasks of the
three slowest retained pairs. Those barriers total 141.919 ms, 65.00% of the
218.351 ms session barrier total. The barrier contains overlapping task wall
times and a tiny reused caller task in pair 54; it is not a sum of CPU work or
a predicted time saving. Source flow confirms that rejected ordinary completions
fall through to the serial kernel. Queue 1469 records both rejected tasks plus
two serial kernels, taking 78.825 ms; queue 3779 takes 69.791 ms. These are now
confirmed examples of costly rejected speculation followed by caller work.

7,297 pending queue calls average 0.271 ms, maximum 78.825 ms; 14 reach 20 ms,
two reach 50 ms and none reaches 100/500 ms. Queue 395 spends 34.137 ms on zone
recalculation without callbacks or pairs. This identifies wasted work in brief
queue pauses, but does not reproduce older half-second input stalls or measure
whole-frame/render/input time.

## Source investigation prompted by this log

The explicit overflow flag is set by two append-only vectors: occupancy query
observations and terrain-height observations, each capped at 8,192 entries.
Permanent-cell/corridor read-log overflow instead appears under their dependency
groups. The current device fields do not distinguish query versus height overflow
or count distinct inputs, so that specific device attribution remains open.

Occupancy observations are appended even when their entire input/result repeats.
A small compiled reproduction of the actual PathfindParallelReads block confirms
8,192 identical inputs fit, while the next identical input sets overflow despite
only one distinct dependency. Terrain observations likewise append repeated
coordinates. Overflow correctly rejects unverifiable results; the avoidable work
to investigate is duplicate observation storage, not a reason to weaken validation.
Deduplication must preserve full query/coordinate identity and all distinct
dependencies; contradictory repeated results must continue to invalidate reuse.

There is also a preparation mismatch. prepareParallelBatch resets each ordinary
job's corridor to fully passable, then calls internalFindPath without the ordinary
outer hierarchy. The authoritative findPathWithInputs first clears corridor
flags, runs findHierarchicalPath and uses its corridor before the same fine
search. This can both invalidate speculative corridor reads and admit broader
speculative work. It is a concrete source difference, not proof that every one
of the 80 device corridor rejections has that cause.

A controlled production-dispatch/validation fixture with its main-thread hierarchy
stub restricting one observed block reproduces one corridor rejection and one
serial recomputation, while still producing a route. Speculative preparation
made zero hierarchy calls; the actual request made one. The normal fixture's
ordinary hierarchy marks every block passable, which does not expose this case
unless a restricting hierarchy is supplied.

Recommend matching speculative ordinary hierarchical preparation to the actual
request, keeping that preparation on main and private to the job. Audit coarse
search state, dependency capture, accounting and early-fallback semantics; preserve
the actual caller's original hierarchy work and queue budget. Then compact the
bounded duplicate query/height observations while keeping exact stale checks and
overflow rejection. Matching corridors may itself reduce both over-search and
validation volume. Fallback policy mismatches and synchronous zone cost remain
separate investigations. No runtime changes or replacement build were made in
this log review; only the two targeted compiled reproductions were run.
