# Validate query-only cells through their returned decisions — 29 October 2026

## Finding and scope

The ~32ccf4e device session classifies 21 primary and one fallback cell first
rejections as changed ground-goal values. Twenty also change metadata presence.
No cell log is full or failed. Applying a successful earlier queue callback can
update goals before the next prediction is consumed; those changes do not imply
concurrent mutation while workers execute.

The audit finds one redundant dependency category. LiveOccupancyReader obtains
cells through getCell while evaluating checkDestination/checkForMovement. Those
lookups previously captured all 19 permanent snapshot fields, independently of
the saved complete occupancy result. A cell accessed only within that query can
change a field the query does not use, or change an internal value while returning
the same result, yet the earlier raw snapshot check rejects before query replay.

This stage removes that raw snapshot only for query-contained lookups. It does
not remove snapshots for direct search/coarse lookups or cached-pointer allocation
attempts. It does not claim all 22 device failures are redundant. In particular,
metadata presence changes can alter persistent versus transient allocation credit
when a search actually allocates or materializes that cell's record.

## Audited dependency boundary

| Access | Validation retained |
| --- | --- |
| Direct getCell outside a tracked occupancy evaluator | Original exact 19-field cell snapshot |
| New record allocation, including cached pointers and query scope | Original exact allocation-cell snapshot plus allocation-decision window |
| getCell only inside the tracked occupancy evaluator | Complete saved query input/result, re-evaluated against live world on main |
| Direct lookup before or after a query for the same cell | Original raw entry retained or added; query never erases it |
| Corridor / terrain height / movement / epochs / lifecycle | Existing independent checks unchanged |
| Query capture, conflict or bounded-capacity failure | Existing invalid/overflow rejection; no unchecked result can be reused |

The only production consumers of evaluateOccupancyQuery are checkDestination,
which reads allowed, and checkForMovement, which copies allowed, allyFixedCount,
allyMoving, allyGoal and enemyFixed. PathOccupancy::Result equality compares all
five. Input identity retains every query setting; deduplication keeps the first
result and marks conflicting observations invalid. Every evaluation still runs;
this is not a query-answer cache.

The evaluator's reader resolves cell, goal/occupancy IDs, object existence,
relationships, crushing rules and AI properties. The relevant engine relationship
and crush-test implementations read live settings and return decisions; no Path
or search-node allocation is needed by the evaluator. Worker execution retains
the existing frozen-world/join boundary. Main-side validation replays each saved
query before accepting the loop outcome. Changes in team/AI/occupancy behavior
that affect any returned field still reject.

Under unchanged direct dependencies and identical query outputs, replaying the
search's deterministic control flow visits the same operations. Allocation-kind
snapshots and the admission window preserve allocation outcomes. Thus the fine
loop outcome and accounting remain reusable even if a query's internal read
sequence or raw unused values differ. This reasoning is local to the explicit
query API; it does not justify suppressing arbitrary cell reads or changing the
reference-independent allocation policy.

## Implementation

PathfindSearchContext owns a boolean and noncopyable OccupancyReadScope. Only the
tracked evaluator branch installs the scope; it restores the previous state on
normal return or exception and supports nesting. Inline getCell skips its raw
observation while that flag is set in its current bound context. The independent
observeParallelAllocationCell hook ignores this flag and remains exact.

The read-log pointer remains installed throughout the query, so the complete
result is saved or the existing failure path prevents reuse. The scope adds no
allocation, global state, worker, lock, retained history or new dependency log.
Untracked serial, exclusive and optional shadow evaluation retain their existing
paths. Main-side finalization remains authoritative. Search bounds, queue order,
per-request budget, dispatch width, runner and renderer are unchanged.

No diagnostic row or field is added. Cell failures still classify raw dependency
failures. A changed query-only decision now reaches the existing occupancy reason
instead of being masked by an unnecessary raw snapshot. A falling cell count or
rising occupancy count alone is not an acceptance or performance regression.

## Regression evidence

The shared batch fixture now compiles the actual production evaluator instead of
duplicating its speculative branch. Six additional cases cover:

1. Reproduce the previous unconditional getCell snapshot rule: an unchanged
   query-only decision rejects under that rule and reuses under the scoped rule,
   with identical routes and charged budget, for primary and early fallback.
2. Execute the actual queue and production updateGoal/removeGoal/setGoalUnit after
   controlled successful callbacks. Across both retail modes, two radii and
   separate, intersecting and allied shared destinations, serial and parallel
   runs match routes, blocking flags, published goals, order and charged budget.
   The matrix exercises both reuse and retained raw-cell rejection. The fixture
   uses a controlled ground-only callback and terrain/Path services, not the full
   production AI state machine or bridge logic.
3. In both phases and retail modes, accept unchanged query-only destination
   decisions across goal allocation/owner changes; reject changed allowed or
   allyGoal output, even when allowed itself stays true. Compare serial routes
   and accounting after each case.
4. Keep exact dependencies for direct reads before/after a query and for cached
   allocation inside a query scope. Metadata changes must still reject Cells.
5. Restore observation after nested scopes and a throwing live relationship
   reader. A throwing query does not publish a partial result.
6. Exceed the existing distinct-query bound and retain overflow rejection in both
   phases without growing the raw cell log.

All 225 local workflow regression cases pass, including all 104 batch cases.
All 104 batch cases pass ThreadSanitizer, and all six added cases pass ASan/UBSan.
Diff checks pass. Native build and device follow-up are recorded below. These
controlled tests do not prove full engine race freedom, reference replay parity
or measured device gain.

## Next device check

Repeat the saved mission and crowded/overlapping goal orders, then exit normally.
Compare primary/fallback reuse, Cells versus Occupancy first reasons, changed-count
reuse and balanced finalizations. Ordinary fine-failure fallback and safe movement
remain separate device coverage gaps from the latest session. This change is
expected to help only query-only dependencies; raw allocation/direct-read changes
will continue rejecting, and synchronous zone rebuilding and long accepted
searches remain separate costs.

## Native build and device result — 29 October 2026

GitHub Actions [40810392060](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40810392060)
passes Mac QA/race checks, native iOS SDK compilation, unsigned packaging and
artifact upload on macos-15 ARM64. Dependency save is skipped after cache restore.
The supplied log identifies ~9117f78, reaches ScoreScreen and exits zero. No fatal,
assertion or primitive-restart warning is logged. Existing platform/browser stubs
and the WAV sample-count message remain.

| Measurement | Previous ~32ccf4e | Current ~9117f78 |
| --- | ---: | ---: |
| Completed pairs | 748 | 945 |
| Primary reused / executed | 1,426 / 1,464 | 1,831 / 1,854 |
| Primary reuse rate | 97.40% | 98.76% |
| Fallback reused / executed | 31 / 32 | 36 / 36 |
| Primary / fallback cell first rejections | 21 / 1 | 15 / 0 |
| Primary occupancy first rejections | 0 | 1 |
| Changed-count reuse, primary / fallback | 9 / 2 | 10 / 3 |
| Admission first rejections, either phase | 0 | 0 |
| Queue mean / maximum, ms | 0.265 / 49.733 | 0.377 / 59.558 |
| Queue updates at least 5 / 20 / 50 ms | 49 / 15 / 0 | 82 / 24 / 1 |
| Pair total / maximum, ms | 164.888 / 22.494 | 225.511 / 33.468 |
| Serial kernel total / maximum, ms | 508.065 / 30.373 | 757.442 / 54.110 |
| Validation total / maximum, ms | 13.864 / 0.267 | 17.806 / 0.278 |

This is consistent with the intended validation boundary: raw changes still
reject and occupancy-result validation is exercised. It does not count which
successful requests specifically benefited from query-only suppression, and the
sessions differ in workload. Lower cell rejection and higher reuse do not prove
the change caused a speedup. The queue mean and tail are higher in this session.

The remaining 15 cell first failures are all unequal snapshots, not full or
failed logs. All include goal_unit, 12 unit_flags and ten metadata/info_x/info_y;
all other first-unequal-cell fields are zero. Their acquired-entry ranges are
73–314. The aggregate does not identify allocation versus direct-read roles or
prove that any remaining dependency is redundant. The single occupancy failure
does not reveal which query, output field or object changed. Later guards still
short-circuit; zero later counts are not proof those inputs never changed.

All primary first reasons balance: cells 15 + occupancy one + kind five + world
epoch two = 23. The 1,854 primary plus 36 fallback-only slots equal 2 * 945 pairs.
Reused results 1,831 + 36 plus 6,738 serial kernels equal 8,605 finalizations.
There are no discarded or validated-unfinished phases, no admission failures,
and 13 changed-count results complete reuse. All fallback executions are early;
safe, queued-closest primary and ordinary-fine-failure fallback are not exercised
by parallel work in this session. Serial closest does execute 248 kernels.

The three largest retained queue calls now contain serial closest kernels:

| Queue | Queue time, ms | Serial closest kernel, ms | Depth / callbacks | Charged cells | Pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5225 | 59.558 | 54.110 | 1 / 1 | 11,912 | 0 |
| 5204 | 43.954 | 38.832 | 1 / 1 | 10,600 | 0 |
| 5213 | 40.682 | 36.886 | 2 / 1 | 11,351 | 0 |

Hierarchy in those calls costs only 0.001–0.002 ms and finalization 0.361–0.492 ms;
the measured fine kernel is their dominant cost. The summaries do not identify
whether closest was a direct approach or an early/ordinary caller fallback, its
unit/settings, pruning decisions or why no pair formed for the depth-two call.
The two depth-one calls cannot form the existing adjacent pair. Additional
workers alone cannot divide one of these individual search loops.

Charged cells are queue accounting, not a count of expanded nodes in that kernel.
The original 5,000-cell budget is checked between completed requests and permits
the last request to overshoot. Source inspection confirms count > 2000 in the
closest loop is conditional far-candidate pruning, not a global hard stop. Thus
these charges do not by themselves demonstrate a broken budget or search limit.

The fourth retained queue, 1752, costs 37.824 ms across three pairs (33.891 ms
combined pair time). Its retained pair 187 costs 33.468 ms and reuses both results.
All eight retained slow-pair tasks reuse, with query/height flags zero; their
12,936 distinct query entries represent 327,919 observations. These samples do
not explain the rejected phases or the three serial closest calls. Zone rebuilds
are absent from the top four here, not proven absent from the session.

The next performance investigation should explain those serial closest searches
with bounded per-search work/pruning and request context, before changing limits
or broadening dispatch. Compact search-only storage remains a separate useful
architecture step; this evidence does not establish which node-layout operation
dominates the closest kernels. Retain validation and per-request scheduling.
Summary arithmetic and relevant source paths were checked; this review changes
documentation only and does not rerun unchanged regression/sanitizer checks.
