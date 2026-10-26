# Temporary strip-rendering diagnostics

Date: 26 October 2026. Branch: `experiment/ios-mod-testing`.

## Purpose and scope

The user explicitly requested targeted diagnostics after the MoltenVK primitive
restart investigation. Preserve rendering semantics while identifying strip draw
sources and potential index collisions. The existing pathfinding experiments and
native callback fixes remain. Earlier input/audio/hitch probes are not restored.

CMake `GENERALS_STRIP_DIAGNOSTICS` defaults OFF. The iOS workflow enables it only
for the mod-testing branch. No MoltenVK/DXVK dependency sources are modified.

## Runtime records

- `[STRIP_DIAG]`: one startup-of-observation banner with limits and timing caveats.
- `[STRIP_DRAW_BEGIN]`: first occurrence of up to 64 configurations, keyed by source
  file/line, literal origin, topology, primitive count and indexed status. Includes
  function, primitive topology, buffer identity, requested index range, base vertex,
  vertex range and known sentinel status. Models and water tracks have distinct
  origin scopes; direct water and screen/filter/smudge/shadow/quad calls show their
  actual file/function. Dynamic state/shader variants within one configuration are
  intentionally not exhaustively traced.
- `[STRIP_DRAW_END]`: same sample ID, original HRESULT and CPU submission duration.
- `[STRIP_INDEX]`: up to 64 observations of an upload containing raw 0xFFFF,
  including its buffer and range. An upload hit is not proof an indexed strip
  actually consumes it; triangle-list buffers can legitimately contain that value.

Indexed samples query existing D3D8 CPU binding state with GetIndices and release
the returned reference. No index-buffer readback, extra draw, flush, fence or GPU
wait is introduced. The original draw arguments and result are preserved. Existing
DX8 wrapper error checks and call counting retain their debug/release behavior.

## Index observations and bounds

Track a fixed table of 64 latest upload-range summaries, each retaining at most 32
sentinel positions. Scan at most 4,194,304 unsigned-short entries (8 MiB of CPU
memory accesses) over the process lifetime. CPU data is inspected while already
write-locked: precise Copy ranges, mesh append ranges, initialized water-grid
entries and initialized fixed water-track entries. The two water allocation padding
indices are not scanned. Other write-lock paths invalidate observations and remain
unknown unless an explicit supported capture repopulates them. Buffer destruction
also invalidates tracked state.

Partial/overlapping writes replace the previous summary conservatively instead of
claiming a coherent full-buffer history. A draw reports absent only when its whole
requested range is covered by the latest known upload and all sentinel positions
were retained. Truncated position lists, evictions, uncaptured writes, out-of-range
draws, and scan-budget exhaustion remain unknown when absence cannot be proven.
New writes invalidate previous knowledge even once the scan budget is exhausted.
Upload min/max values describe the upload range, not necessarily the draw subrange.
Base vertex is logged separately: adding a base does not itself turn a raw index
into the primitive-restart sentinel.

## Timing limitation

The probe times the CPU D3D submission call only. DXVK can compile pipelines on
another thread or defer command execution, so the interval is not isolated
vkCreateGraphicsPipelines duration or GPU draw time. MoltenVK warnings can interleave
asynchronously with these records; adjacency does not prove a causal association.
An exact pipeline-creation trace would require a separate DXVK/MoltenVK-level
instrumentation pass or a device GPU capture. This first build can identify normal
non-indexed sources and actual observed sentinel use without changing dependencies.

## Verification and device test

`test_strip_diagnostics.py` compiles the actual diagnostic header with a CPU-only
D3D8 stand-in. Tests verify original call counts/arguments/HRESULT, no non-indexed
binding queries, indexed reference balance, sentinel detection, conservative
partial/truncated/invalidated status, scan/output limits, nested origin restoration,
and disabled-build silence. Sanitizers check the indexed observation path. Existing
packaging/startup/worker/native-callback/heap/hierarchical suites remain in CI.
All 33 local tests passed, including the six diagnostic tests; actionlint and
whitespace checks passed. Full iOS SDK integration is verified by the macOS runner,
not this Linux workspace.

On the phone, repeat the same mission/save, visit the main menu, move near water
and through the previously tested areas, then send generals-stderr.log. Note any
visible missing geometry and when it happens. The probes add CPU work and bounded
synchronous log writes, so this build should diagnose compatibility rather than
serve as a clean performance benchmark. Disable the CMake option after investigation.

## Follow-up: retained water-track records

Both supplied logs reported the indexed water-track quad but `sentinel16=unknown`.
The general observation table can evict an early water upload after 64 unrelated
buffers; the old logs do not establish whether eviction, budget use or another
invalidation caused that specific miss. Preserve four water-track observations
outside mesh churn, with a separate 4,096-index lifetime scan budget. Up to 16
`[STRIP_WATER_UPLOAD]` lines identify actual buffers/ranges/min/max/sentinel counts.
No regenerated or assumed-safe indices are substituted for captured data.

Draw records now label their observation as `retained_water_upload`, `latest_upload`
or `unavailable`. Every write invalidates both tables before installing new data;
uncaptured writes and destruction forget both. A full budget yields unknown,
including for a previously observed buffer. Tests exercise mesh eviction pressure,
independent budgets, mutation/destruction invalidation, retained record lookup,
output bounds, and capture/draw calls compiled in different translation units.
Ten diagnostic tests pass locally, including sanitizer coverage. The existing
rendering arguments, HRESULTs and pathfinding code are unchanged. The macOS CI
runner must still compile the next SDK build and the phone must confirm that the
captured upload identity matches the draw and supplies complete range coverage.
