# Hierarchical edge eligibility experiment

Date: 26 October 2026. Branch: `experiment/ios-mod-testing`.
Baseline: stable-heap commit `473480f26`, reported responsive by the user.

## Change

Zero Hour processHierarchicalCell no longer requires an otherwise eligible border
cell to already have a search record. It rejects already-open/closed border cells,
then keeps existing extent, block-zone, effective-zone, adjacent membership and
duplicate-zone checks. Only after those checks does it acquire a record, returning
safely if the shared pool cannot supply one. Successful border records enter the
existing closed list, including when the adjacent record allocation subsequently
fails, so ordinary search cleanup owns them.

The eligibility concept comes from Zero Hour Reimagined 1.0.0 by dement123, supplied
as source by the user. Its fresh-search implementation allocates earlier; this
adaptation retains our shared-record lifetime and allocates late to avoid retaining
records for rejected crossings. The change is guarded by RTS_ZEROHOUR. Existing
base Generals eligibility remains unchanged.

The stable heap, node pool size, frame budget, detailed movement validity checks,
coarse-failure fallback and native touch callbacks are retained. No new search
contexts, worker prefetch, group scheduling, renderer/balance change or runtime
probe is included. Enabling this experiment can change coarse corridors and final
routes; retail replay equivalence is not claimed.

## Validation

`test_hierarchical_edges.py` extracts and compiles the complete production helper
with controlled zone/cell fixtures. Four compiled tests cover Zero Hour with/without
retail support (including both runtime fixed/retail states), and base Generals
with/without retail support. Fourteen Zero Hour scenarios cover absent/preexisting
records, disconnected zones, failed border and adjacent allocations, duplicate
zones, border-zone mismatch, out-of-bounds coordinates, uninitialized zones,
already-open/closed candidates, pinched cost and preexisting adjacent records.
Assertions check queue/parent/cost results, duplicate prevention, no new records
on rejected crossings, and closed-list ownership on neighbor-allocation failure.
Fixture cleanup checks ownership; this does not replace a real pool-exhaustion
or whole-engine cleanup test. Address/undefined sanitizers check the same harness.

The existing heap differential suite is rerun to guard the working baseline;
startup, packaging, worker and native-callback suites remain in CI alongside both
pathfinding suites. Full device compilation runs on the macOS GitHub runner.
There is no local Xcode or real-map campaign/replay execution in this environment.

## Device comparison

Use the same mission/save and movement orders as the heap-only build. Check groups
around buildings, narrow passages, ramps, cliffs and bridges; watch for units
stopping early, choosing poor detours or failing to reach destinations. A responsive
session is useful evidence, but does not by itself establish a speedup or route
correctness on every map. The change stays on the experimental branch.
