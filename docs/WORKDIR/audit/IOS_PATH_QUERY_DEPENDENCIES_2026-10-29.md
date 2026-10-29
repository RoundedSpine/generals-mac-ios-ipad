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
Diff checks pass. Native iOS SDK and device verification remain pending. These
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
