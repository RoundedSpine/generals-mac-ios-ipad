# Explain cell-dependency rejections without altering validation — 29 October 2026

## Motivation and retained behavior

The ~ec6c40d session has 26 primary cell_dependencies first rejections after the
allocation-decision change. Its log cannot distinguish a changed cell snapshot
from an unusable/full cell dependency log. Earlier strict-count rejection could
mask later cell checks, and new cached-pointer allocation observation expands
explicit coverage. Those facts do not identify the 26 device failures' causes.

Add classification to the existing optional GENERALS_PATH_TIMING summaries.
Preserve result acceptance, search/observation limits, allocation windows, worker
count, queue order and budget. No dependency field is removed or ignored.

## Read-log cause and first mismatch observation

BoundedSearchReads retains its existing overflow/unusable flag, adding a full
flag set only when acquiring a new distinct entry returns no slot. In the current
BoundedKeyedPool, that occurs only at its fixed entry capacity. A duplicate key
at capacity remains valid and retains its first snapshot. A failed snapshot or
order-vector capture follows the existing exception path, marks the log unusable
and rethrows, without marking it full. Reset clears both flags. Diagnostic size
reports physical acquired entries, including a partially captured entry in a
failed log; it is not the number of cells validated before a mismatch.

The original matches(reader) implementation remains. An additional overload
accepts a mismatch observer. It reads each live snapshot once, compares against
the captured value and calls the observer only for the first unequal pair, then
returns false immediately. It never reads invalid logs or continues after the
first mismatch. The observer receives the captured and already-read current
values; it does not repeat engine queries or retain a cell pointer.

The diagnostic validator first classifies an unusable cell log without any live
snapshot reads. For valid logs it uses the observer overload to count changed
scalar fields. Disabled diagnostics uses the original matches(reader) call.
Both remain at the same Cells guard, after allocation/mode checks and before
corridor, occupancy and height validation. An earlier failure prevents all cell
classification; a later corridor/query failure does not become a cell failure.
Existing used/outcome guards prevent counting a phase twice.

## Bounded shutdown summary

Two new PATH_CELL_REJECTIONS rows, primary and fallback, contain:

| Field | Meaning |
| --- | --- |
| calls | Selected phases whose first failed guard is cell dependencies |
| values | Valid log whose first unequal snapshot rejects the phase |
| log_full | Distinct-entry capacity was exceeded before validation |
| capture_failed | Existing capture failure made the log unusable |
| entries_min / entries_max | Independently aggregated acquired-entry counts across failed phases; zero if there are no failures |

For a normally completed session, calls = values + log_full + capture_failed,
and calls matches that phase's existing cell_dependencies first-reason count.
Reaching the entry count limit by itself is not failure; log_full requires a
failed attempt to add another distinct key. Query/height PATH_READS_SLOW flags
remain separate and cannot be used to infer cell-log validity.

For each values failure, count all differing fields in its first unequal cell:

| Report field | Snapshot source |
| --- | --- |
| metadata | Presence of permanent cell metadata |
| obstacle | Stored cell obstacle ID |
| fence / transparent | Stored cell obstacle flags |
| zone | Cell zone |
| aircraft_goal | Aircraft-goal marker |
| pinched | Pinched marker |
| type | Cell terrain/obstacle type |
| unit_flags | Cell occupancy/goal flags |
| connects_layer / layer | Layer connection and cell layer |
| goal_unit / goal_aircraft / pos_unit | Permanent goal/occupant IDs |
| info_x / info_y | Permanent metadata coordinates, zero without metadata |
| effective_fence / effective_transparent / effective_obstacle | Existing getters under the current retail-allocation policy |

The field count and array parameter types match the production 19-value snapshot;
changing its shape requires updating the diagnostic mapping. Raw/effective
obstacle fields can describe related state. Multiple fields can differ in one
cell, so field totals may exceed values. Later mismatching cells are not visited
or counted. The summary does not identify a particular unit, request or location,
and field counts do not prove which differences affected the eventual route.

All aggregate updates occur on main after join. No per-cell counters, retained
objects/requests, unbounded history, clocks, locks or per-request output are added.
Workers only write their existing private read logs and the private cause flag.
Valid comparisons add no field-counting loop; field classification uses scalar
snapshot comparisons only after a failure is already established.

## Verification and next device result

Five new cases check original/observed validation order, single equality/read and
first mismatch behavior; duplicates at capacity, capacity and capture failures,
reset and validation exception propagation; all 19 field mappings and bounded
primary/fallback report ranges; production validator classification of every
field once; full/capture failures versus earlier epoch guards; and identical
actual snapshot, occupancy/AI and height read counts with diagnostics ON/OFF.
Existing whole-validator traces and route/accounting checks remain enabled.

All 219 local workflow QA cases pass, including all 98 batch cases. All 98 batch
cases pass ThreadSanitizer, and all five new cases pass ASan/UBSan. Existing
whole-validator query traces, serial route/accounting matrices and lifecycle
checks remain passing. Diff checks pass. Native run
[40798412913](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40798412913)
now passes Mac QA/race checks, iOS SDK compilation, unsigned packaging and
artifact upload. Dependency save is skipped after the cache restore. Device
verification remains pending for this diagnostic change. Controlled fixtures do
not establish full engine replay parity or explain a device failure without its
new log.

Repeat the same saved mission, include crowded/blocked movement and exit normally.
Compare calls with cell_dependencies, then inspect values versus log_full and
capture_failed. Value fields identify the next live-state dependency to audit;
full logs instead motivate examining the bounded observation footprint. Neither
outcome justifies dropping validation or raising limits without further evidence.
This change measures cause and does not itself optimize a search or zone rebuild.

## Device result — 29 October 2026

The supplied generals-stderr.log identifies ~32ccf4e, enables parallel mode with
one worker plus main, reaches ScoreScreen and exits zero. The new counters are
present and balance against the existing first-rejection summaries. There is no
logged fatal/assertion or primitive-restart warning. Known platform/browser stub
warnings and one WAV wrong-sample-count message remain. Normal completion does
not establish movement correctness, full engine race freedom or lifecycle coverage.

| Measurement | Previous ~ec6c40d | Current ~32ccf4e |
| --- | ---: | ---: |
| Completed pairs | 967 | 748 |
| Primary reused / executed | 1,876 / 1,906 | 1,426 / 1,464 |
| Primary reuse rate | 98.43% | 97.40% |
| Fallback reused / executed | 28 / 28 | 31 / 32 |
| Primary cell first rejections | 26, cause unavailable | 21, unequal values |
| Fallback cell first rejections | 0 | 1, unequal values |
| Changed-count reuse, primary / fallback | 5 / 2 | 9 / 2 |
| Admission first rejections, either phase | 0 | 0 |
| Queue mean / maximum, ms | 0.344 / 39.318 | 0.265 / 49.733 |
| Queue updates at least 5 / 20 / 50 ms | 94 / 22 / 0 | 49 / 15 / 0 |
| Pair total / maximum, ms | 221.970 / 36.435 | 164.888 / 22.494 |
| Serial kernel total / maximum, ms | 626.081 / 23.991 | 508.065 / 30.373 |
| Validation total / maximum, ms | 18.593 / 0.268 | 13.864 / 0.267 |

These are different workloads. Lower mean and pair times, lower acceptance and a
higher queue maximum do not establish either a speedup or a diagnostic regression.
The diagnostic change does not alter the search or acceptance rules.

The new classifications are specific:

| First unequal cell field | Primary phases | Fallback phases |
| --- | ---: | ---: |
| goal_unit | 21 | 1 |
| unit_flags | 20 | 1 |
| metadata | 19 | 1 |
| info_x / info_y, each | 19 | 1 |
| All other snapshot fields | 0 | 0 |
| Full cell logs / capture failures | 0 / 0 | 0 / 0 |
| Acquired entries in rejected cell logs, min–max | 110–634 | 304–304 |

Thus every cell first rejection here includes a ground-unit goal-owner change.
Twenty of the 22 also change permanent metadata presence. Coordinates in this
snapshot become zero without metadata; their differences do not establish that
map cells or units physically moved. These are first-unequal-cell counts only,
not all changed cells, directions or previous/current object IDs. Later guards
are short-circuited, so zero occupancy/height rejection does not establish that
those later checks would pass for the rejected phases. This log also does not
retroactively identify the causes of the preceding session's 26 cell rejections.

Source tracing explains a normal way to produce this signature. AIUpdate.cpp's
doPathfind updates a successful ordinary/approach request's goal before the next
queued request is consumed. Pathfinder::updateGoal calls removeGoal and then
setGoalUnit; setGoalUnit changes the goal ID and occupancy flags, allocating or
releasing permanent metadata as needed. No simulation advancement while workers
are running is required: applying the first request after the join can stale the
next request's prediction. The aggregates do not identify which particular
callback or object caused these device failures.

The current allocation policy makes metadata presence relevant independently of
goal occupancy: searchInfo and allocateSearchInfo use it to choose persistent
versus charged transient records. Ground goals/flags also affect destination and
movement decisions. Therefore these fields cannot simply be ignored, even though
query-result revalidation covers some of the same occupancy information. A useful
next audit is to distinguish cells actually used for allocation from cells only
observed by a query and determine whether any complete dependency can be validated
more precisely. Existing setter/metadata rejection fixtures already cover basic
mutations; a realistic ordered two-request goal-update case would extend that
evidence. Keep the existing guard and capacity until equivalence is demonstrated.

Other primary first reasons are kind 12 and world epoch five; together with cells
21 they account for all 38 primary rejections. Fallback has only the one cell
rejection. The 1,464 primary plus 32 fallback-only slots equal 2 * 748 pairs.
Reused results 1,426 + 31 plus 6,823 serial kernels equal 8,280 finalizations.
There are no discarded or validated-unfinished results. Queued closest executes
24 primary phases and reuses 15. All 32 fallback executions are early fallback;
safe and ordinary-fine-loop-failure fallback are still unexercised here.

The slowest queue update is 49.733 ms: two pairs total 11.418 ms and one serial
ordinary kernel costs 30.373 ms, with preparation 3.900 ms and finalization
2.398 ms. It charges 8,655 cells; overshoot by the last completed request remains
permitted by the unchanged per-request budget. The summary does not identify why
that serial kernel was required. One retained pair from that queue, pair 168,
reuses both results; the other pair is not retained. The next three slow queue
updates are synchronous zone rebuilding at 36.225, 32.734 and 32.542 ms.

All eight retained slow-pair tasks reuse their results, including the maximum
22.494 ms pair. Their query/height flags are zero; they contain 13,402 distinct
query entries from 173,432 observations in total. These retained samples cannot
explain cell-rejected phases elsewhere in the session. Faster acceptance alone
does not address the already-reused searches or synchronous zone rebuilding.

Summary arithmetic and source paths were checked for this review. No runtime
change or new test was needed; the existing regression/sanitizer results above
remain the implementation checks. This is the first device confirmation that
the new classification executes, rather than proof of all unexercised branches.
