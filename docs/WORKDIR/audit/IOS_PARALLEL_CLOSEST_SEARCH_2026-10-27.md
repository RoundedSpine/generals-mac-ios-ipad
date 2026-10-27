# Parallel closest-destination search — 27 October 2026

## Scope

Extend the experimental two-request dispatcher to queued approach requests using
the existing `findClosestPath` search. Predict the start, target, blocked state
and original 0.2 path-cost multiplier without destroying paths, updating goals or
changing waiting flags. This adapts dement123's supplied Reimagined
`AIUpdateInterface::predictPathfind` approach branch. Safe requests retain their
callback precedence; non-ground approaches and other unsupported requests stay
serial. One worker and main still share at most two adjacent requests.

Extract closest scoring/expansion into a scratch-only kernel. Keep exact-goal,
nearest-candidate and failure finalization on main, including destination XY
adjustment, unchanged Z, path creation/optimization, retail cleanup order and
actual budget accounting. Preserve stable ties, distance/cost arithmetic, blocked
and through-unit behavior, initial tunneling and the original pruning rules,
including the existing conditional `count > 2000` check. Do not change capacities,
queue order, per-request frame budget checks or lifecycle handling.

## Preparation and validation

Real hierarchical preparation remains on main at consumption. Prediction uses
an unrestricted corridor and provisionally assumes hierarchy availability when
the unit did not start stuck. This is an assumption to validate, not a computed
hierarchical path. It avoids speculative hierarchical Path allocations, retail
recovery and UI/audio effects. A mismatch with the actual hierarchical outcome or
any observed corridor bit rejects reuse and executes the normal caller loop.

`PathfindClosestSettings` captures blocked state, cost multiplier, move-allies
argument, goal-on-obstacle permission, started-stuck state, hierarchy availability
and initial ignored obstacle. Shared result validation compares every field and
the request kind, in addition to the existing object/locomotor identity,
coordinates, effective ignore/tunneling, copied movement settings, admission,
retail mode, epochs, permanent cell values, live occupancy and ground-height
dependencies. Capture happens after private preparation; consumption remains
single-use at the original queue position. Only main applies the adjusted target.

The existing two bounded contexts/read logs are reused. There is no extra arena
or worker. Normal batch and escape counters remain; a bounded session summary
`[PATH_PARALLEL_CLOSEST] stopped searches=N accepted=A` counts completed closest
computations in pairs and reused completions, including valid no-path results.

## Verification

- All 153 workflow QA tests pass locally. All 35 batch tests pass ThreadSanitizer;
  all 11 closest-related tests pass ASan/UBSan. Actionlint and diff checks pass.
- The previous monolithic function from 368e8f942 and the extracted serial code
  produce the same golden output for 192 controlled combinations: both retail
  modes, three cost multipliers, blocked/unblocked requests, hierarchy success/
  failure and seeded terrain/footprints. Compare routes, expansion order, adjusted
  target XYZ, budget, flags, residual scratch and hierarchical-call count.
- Four 128-by-128 cases also match the previous function, including 16,256 charged
  cells and 52 actual far-distance checks after the 2,000 threshold in each case.
  The test instruments the same condition in both versions without changing its
  limit. Clang fixtures use the engine's disabled floating-point contraction.
- Eighty serial-versus-parallel closest/ordinary/escape pair cases match routes,
  targets and budget. Tests require actual overlapping closest loops; main-only
  hierarchical preparation and path materialization; no destination change during
  prediction; rejection for changed policies, hierarchy, observed corridor, cells,
  requests, ignore state, lifecycle, occupancy or overflow; single-use results;
  and preserved queue budget stops, pause and reset/discard behavior.
- Fixtures use production cells, records, lists, ownership, queue, kernels and
  validation with controlled world, hierarchy and Path services. They do not prove
  full-engine bridge behavior, replay equivalence or a device performance gain.

Code `08d17c2e0` passed all 153 Mac QA tests, the workflow race checks, actual iOS
SDK compilation, platform/rpath packaging checks and unsigned IPA upload in
[run 40502028264](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40502028264).
Artifact: `GeneralsXZH-iOS-unsigned`. Device movement, lifecycle, memory and
performance validation remain pending; first closest-result reuse is recorded below.

## Device log from the closest-capable IPA

The latest supplied `generals-stderr.log` identifies `revision=~08d17c2`, reaches
the score screen and exits with code 0. Its 742 pairs account for 1,484 primary
results: 1,397 accepted (94.1%), 87 rejected and none unused. Worker tasks total
742. Four closest computations completed in pairs, with two accepted; the
kind-specific count includes caller participation and valid no-path completions,
so it does not identify which closest computations ran on the worker or establish
route correctness. Escape counters remain zero. Both CSF tables finish and no
primitive-restart warning appears. Cache-directory state is reused, not a measured
pipeline hit rate. This log contains no frame-time or memory measurements.

## Remaining Reimagined work

The subsequent [fallback stage](IOS_PARALLEL_FALLBACK_SEARCH_2026-10-27.md) adds
conditional closest computation after eligible ordinary fine-loop failures.
It retains a separate bounded fallback arena per request so both phases preserve
their original main-thread cleanup; it does not adopt a scalar cleanup substitute.
Early ordinary preparation rejection and path-materialization failure still use
caller fallback. That newer code passed its own SDK workflow in run 40520080544;
its device validation remains pending.
Hierarchical search and Path optimization remain on main. Larger worker pools,
eight-request scheduling and dense map-sized node storage are not adopted here.
The previous escape-capable device log had zero parallel escape searches, so
this implementation does not imply that escape gameplay was device-validated.

Other reference ideas inspected during this stage: `FramePacer` adds a bounded
logic-frame interpolation phase and preserves native logic rate when rendering
uncapped; `gfx_vulkan.cpp` caches static GPU buffers by version and uses dirty/
content checks for texture upload. These are review candidates, not integrated
changes. Frame pacing must retain our native iOS callback loop, and renderer work
must first account for equivalent DXVK behavior and MoltenVK/iOS requirements.
The compared interpolation consumers are Drawable physics transforms (pitch,
roll, yaw and vertical offset) and particles; the reference also resets timing
after a load screen. This supports a visual-smoothness candidate at higher render
rates, not a claim of faster simulation or a fix for the old input-delivery delay.
Its enhanced water, shadows, lighting and post-processing belong to a larger native
renderer port and have unmeasured iOS GPU cost. None is added by this stage.
