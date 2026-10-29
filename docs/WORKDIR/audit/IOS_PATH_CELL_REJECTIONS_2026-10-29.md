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
