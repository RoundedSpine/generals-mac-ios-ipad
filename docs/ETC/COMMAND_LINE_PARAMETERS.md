# Command Line Parameters

Common command line parameters for `GeneralsX` (Generals) and `GeneralsXZH` (Zero Hour).

## Window & Display

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-win` | Forces windowed mode | `./GeneralsXZH -win` |
| `-fullscreen` | Forces fullscreen mode | `./GeneralsXZH -fullscreen` |
| `-xres <width>` | Sets horizontal resolution | `./GeneralsXZH -xres 1920` |
| `-yres <height>` | Sets vertical resolution | `./GeneralsXZH -yres 1080` |

## Development & Testing

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-noshellmap` | Disables the shell map (skip intro) | `./GeneralsXZH -noshellmap` |
| `-quickstart` | Quick launch (skip movies + shell) | `./GeneralsXZH -quickstart` |
| `-debug` | Enable debug mode | `./GeneralsXZH -debug` |
| `-logToCon` | Enables legacy debug-log console routing (`DEBUG_LOG`). **Debug builds only** (`ALLOW_DEBUG_UTILS` / `RTS_BUILD_OPTION_DEBUG=ON`); ignored in release builds. | `./GeneralsXZH -logToCon` |

## Mods & Content

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-mod <path>` | Loads a mod from directory or .big file | `./GeneralsXZH -mod /path/to/mod.big` |

## Replay & Multiplayer

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-replay <file>` | Play a replay file | `./GeneralsXZH -replay match.rep` |
| `-jobs <count>` | Number of parallel replay jobs | `./GeneralsXZH -jobs 4 -replay *.rep` |
| `-headless` | Run without graphics (replay testing) | `./GeneralsXZH -headless -replay *.rep` |

## Common Combinations

### Quick Testing
```bash
./GeneralsXZH -win -noshellmap
```
Launch in windowed mode, skip intro.

### Replay Compatibility Testing
```bash
./GeneralsXZH -jobs 4 -headless -replay subfolder/*.rep
```
Test multiple replays in parallel without graphics (requires optimized VC6 build with `RTS_BUILD_OPTION_DEBUG=OFF`).

### High Resolution Testing
```bash
./GeneralsXZH -win -xres 2560 -yres 1440
```
Test in windowed mode at 1440p resolution.

## Platform-Specific Notes

### Windows
- Parameters can use `/` or `-` prefix (both work)
- Paths can use backslashes

### Linux
- Must use `-` prefix
- Paths must use forward slashes
- Some parameters may not work until Linux port is complete
- `-logToCon` sets a debug flag, but many Linux diagnostics still require explicit `fprintf(stderr, ...)` instrumentation because `OutputDebugString` paths are stubbed/non-visible on this platform.
- **`-logToCon` is only available in debug builds** (`RTS_BUILD_OPTION_DEBUG=ON` / `ALLOW_DEBUG_UTILS` defined). It is unrecognized and has no effect in release builds.

## Logging Diagnostics Recipe

The experimental iOS workflow enables the compile-time `GENERALS_PATH_TIMING`
option (default OFF elsewhere; requires `GENERALS_PARALLEL_PATH_BATCH`). This is
not a command-line flag. On normal game exit it writes `[PATH_TIMING]` session
summaries to `generals-stderr.log` for queue, preparation, parallel tasks,
validation, hierarchy and finalization. Times are overlapping wall-clock totals,
not CPU times or FPS measurements. No debug launch flag is needed. Crashes or
force-quitting may prevent the shutdown summary. See
[the phase definitions and test instructions](../WORKDIR/audit/IOS_PATH_TIMING_2026-10-28.md).
The same option also prints `[PATH_PAIR_ADMISSION]`, per-slot prediction/capture
counts, `[PATH_SERIAL_KINDS]` and at most four each of `[PATH_QUEUE_SLOW]` and
`[PATH_PAIR_SLOW]`. These retain only copied scalar work counters and queue-call
ordinals. See [admission and slow-call field definitions](../WORKDIR/audit/IOS_PATH_ADMISSION_2026-10-28.md).
The slow-pair rows also include separate primary/fallback dispositions and the
first validation rejection group for each task role. `[PATH_RESULT_OUTCOMES]`
and `[PATH_RESULT_REJECTIONS]` summarize those phases, including evicted samples.
See [result correlation and status meanings](../WORKDIR/audit/IOS_PATH_RESULT_OUTCOMES_2026-10-28.md).
`[PATH_READS_SLOW]` adds bounded observation/unique-entry counts and capacity/
conflict flags for each executed phase of those retained pairs. See
[corridor preparation and observation-log definitions](../WORKDIR/audit/IOS_PATH_CORRIDOR_READS_2026-10-28.md).
`[PATH_TASK_PROFILE]` and `[PATH_QUERY_STAGE]` split retained complete tasks into
hierarchy/fine/finalization work and occupancy call origins. Every 128th query is
timed separately for live evaluation and dependency logging; reported sampled
wall times are not extrapolated totals, and stages with no samples have unknown
cost. `[PATH_ZONE_SLOW]` separately retains four zone rebuilds with pass times.
The `zone_*` session metrics include empty-queue rebuilds; initialization using
the default null profiler remains unmeasured. See
[query-cost investigation and sampling caveats](../WORKDIR/audit/IOS_PATH_OCCUPANCY_COST_2026-10-29.md).
`GENERALS_FAST_ZONE_MERGES` is an optional Zero Hour compile-time optimization,
enabled on the iOS testing branch. `[PATH_ZONE_MERGES]` confirms it at the first
profiled batch. `GENERALS_FROZEN_OCCUPANCY_CACHE` is a separate compile-time
prototype requiring complete-worker mode, now enabled only on the iOS testing
branch after the zone-only device baseline. `[PATH_OCCUPANCY_CACHE]` confirms it.
`cache_hits` counts reused occupancy results, while query
calls/stages/samples count live evaluations only. Main validation stays live.
See [zone merging, cache scope and benchmark limits](../WORKDIR/audit/IOS_PATH_ZONE_MERGES_2026-10-30.md).
`GENERALS_REUSE_PATH_CONTEXTS` defaults OFF, requires complete-worker mode and is
enabled only on the iOS testing branch. `[PATH_CONTEXT_REUSE]` confirms two
retained participant arenas, shared only with their sequential fallbacks; result
Paths, validation logs and publication state remain independent. Reported native
layout sizes are not resident memory. See
[context reuse, ownership and bounds](../WORKDIR/audit/IOS_PATH_CONTEXT_REUSE_2026-10-30.md).
`GENERALS_PATH_LOOKAHEAD` defaults OFF, requires complete-worker mode and is enabled
on the iOS testing branch. It selects two eligible requests from an anchored
eight-entry window with one worker, retaining skipped serial callbacks and the
per-request budget. `[PATH_LOOKAHEAD] enabled` confirms execution; optional timing
rows summarize inspected/eligible/selected entries, dispatched pairs and partner
offsets. Scans stop at two eligible entries, so these are not full eight-entry
availability counts. See
[lookahead lifetime, counters and tests](../WORKDIR/audit/IOS_PATH_LOOKAHEAD_IMPLEMENTATION_2026-10-30.md).
`[PATH_ADMISSION_MISMATCH]` summarizes captured/current permanent-record ranges
and whether current usage increased, decreased or stayed equal at a rejected
allocation-decision window check. `[PATH_ADMISSION_REUSE]` counts changed permanent
usage only after all validation and finalization complete successfully. These are
separate from windows that pass but fail another dependency check.
`[PATH_CLOSEST_MISMATCH]` counts the differing closest-policy fields; several
fields may differ in one rejected phase. Both have separate primary/fallback
rows and no per-request output; classification does not repeat live queries.
See [closest preparation and mismatch definitions](../WORKDIR/audit/IOS_PATH_CLOSEST_PREPARATION_2026-10-28.md).
See [allocation-decision window semantics](../WORKDIR/audit/IOS_PATH_ADMISSION_WINDOW_2026-10-29.md)
for the subsequent replacement of exact-count equality with exact allocation
decision equivalence; search limits and scheduling stay unchanged.
`[PATH_CELL_REJECTIONS]` separates the first cell failure into changed snapshot
values, a full dependency log or failed capture. Per-field counts describe the
first differing cell of each rejected phase; they do not count every changed cell.
See [cell-rejection classifications and fields](../WORKDIR/audit/IOS_PATH_CELL_REJECTIONS_2026-10-29.md).
Tracked query-only cell lookups now rely on complete occupancy-result replay;
direct cell and allocation dependencies still use exact snapshots. Some changed
decisions can therefore reach the existing `occupancy` rejection instead of an
earlier raw `cell_dependencies` rejection. No output field changes. See
[query-only dependency semantics](../WORKDIR/audit/IOS_PATH_QUERY_DEPENDENCIES_2026-10-29.md).
`[PATH_CLOSEST_SLOW]` retains at most four serial closest fine kernels with
candidate/expansion/pruning counts, initial cell settings and index-array bytes.
It uses the existing kernel timer and has no per-cell clocks. See
[direct indexing and closest work fields](../WORKDIR/audit/IOS_PATH_DIRECT_INDEX_2026-10-29.md)
for flags, outcomes, overlapping pruning reasons and interpretation limits.
`[PATH_SEARCH_STORAGE]` is printed once at the first executed parallel batch when
the timing option is enabled. It reports native `sizeof` values for the compact
node, permanent record and fixed context, plus record capacity and the index-cell
cap. These are layout sizes, not resident memory or live allocation counts. See
[compact-node storage and verification](../WORKDIR/audit/IOS_PATH_COMPACT_NODES_2026-10-29.md).
The experimental branch also enables `GENERALS_COMPLETE_PATH_WORKER` (default OFF;
requires parallel batches). Its first pair prints `[PATH_COMPLETE_WORKER]`.
`worker_kernel`/`caller_kernel` now measure complete APIs, including hierarchy,
construction and optimization. Accepted stage times may come from either thread;
primary reuse can include early-null requests without a fine finalization. Avoid
comparing these wider task times or old fine-phase balance equations directly with
older logs. See [complete execution, validation and timing semantics](../WORKDIR/audit/IOS_PATH_COMPLETE_WORKER_2026-10-29.md).

Use this when investigating runtime behavior (example: skirmish startup flow):

```bash
cd ~/GeneralsX/GeneralsZH
./run.sh -win -logToCon 2>&1 | grep -v "D3DRS_PATCHSEGMENTS" | tee ~/Projects/GeneralsX/logs/manual_run.log
```

Legacy fallback during migration:

```bash
cd ~/GeneralsX/GeneralsMD
./run.sh -win -logToCon 2>&1 | grep -v "D3DRS_PATCHSEGMENTS" | tee ~/Projects/GeneralsX/logs/manual_run.log
```

Then filter the generated log for targeted markers:

```bash
grep -n "SKIRMISH_DIAG\|ScoreScreen\|SkirmishGameOptionsMenu" ~/Projects/GeneralsX/logs/manual_run.log
```

## Source Code Reference

Command line parsing is implemented in:
- `Core/GameEngine/Source/gameclient.cpp` - Client-side parameters
- `GeneralsMD/Code/Main/WinMain.cpp` - Entry point and initial parsing
