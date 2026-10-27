# Parallel escape search — 27 October 2026

## Change and reference

Extend `experiment/ios-mod-testing`'s two-request batch from ordinary final-goal
movement to escape (`findSafePath`) requests, including mixed pairs. This adapts
the safe-request prediction in dement123's supplied
`ZeroHourReimagined_1.0.0_source`, `AIUpdateInterface::predictPathfind`; it preserves
our effect separation, bounded contexts and ordered live validation instead of
moving the whole engine path function to a worker.

Main copies the unit's start, both resolved repulsor positions and the exact
vision-plus-repulsed radius. Missing first repulsors retain the original
`(-1000,-1000,0)` sentinel; a missing second repulsor inherits the first position.
The safe branch inherits the current context's ignored obstacle and tunneling
state, matching `doPathfind`; it does not substitute the unit's ordinary request
ignore ID. Prediction does not destroy a path or change waiting/AI flags.

Main prepares each private context and stops before expansion. One worker and
main then run two independent loops against the frozen world. The escape loop
retains the original nearest-repulsor distance, cost ordering, destination checks,
search-space exhaustion behavior and soft 2,000-cell threshold. That threshold
is not a hard cap: the original accepts a newly farther candidate after crossing
it. No search/node/queue budget was increased. Escape scoring needs XY only;
sharing the original XY conversion avoids calling terrain-renderer layer-height
code from this worker. Ordinary downhill-height dependencies remain validated.

## Consumption and lifecycle

Both kinds use the same one-use, queue-position-specific validation helper:
unit/pointer/locomotor identity, exact start/request, kind, copied movement
settings, effective ignore/tunneling state, admission, retail mode, world and
lifecycle epochs, all observed permanent cells/corridor values, live occupancy
answers and any recorded ground heights. Escape results additionally compare
both full repulsor positions and radius. A mismatch runs the normal caller search;
it does not fail the movement command or relax validation.

Main alone constructs/optimizes the engine Path, performs original cleanup and
merges its actual allocation count and bookkeeping. Both tasks join before
consumption or any simulation/event processing. No result survives the queue call,
budget stop, reset or shutdown. Pause blocks admission; a pause/lifecycle change
rejects reuse. An in-progress pair still completes its synchronous call.

Storage remains the existing two bounded contexts and read logs, with only small
request fields added. There is still one worker and main participation. Dozers,
missing crusher name keys and unsupported requests remain ineligible.

## Evidence

- The prior device build `f3fb2f9` completed 999 ordinary pairs with 1,862 reused
  results, 129 rejections, seven unused results and normal exit. This is the
  baseline, not device validation of this new escape stage.
- Compare against the previous monolithic safe function from `f023ce8e9` under
  the same controlled world services: 256 combinations of retail mode, centering,
  footprint radius, initial tunneling and seeded terrain/repulsors. Routes,
  expansion order, budget counts, flags and residual scratch counts match exactly.
  Repeating all combinations with a test-only threshold of three exercises the
  original soft-threshold branch; hashes also match. Production remains 2,000.
- Forty-eight ordinary/safe and safe/safe serial-versus-parallel scenarios preserve
  paths and budget counts. Additional tests require actual overlapping escape
  loops and caller-only path materialization; reject changed repulsors, radius,
  start, request kind, ignore/tunneling, movement settings, cells, lifecycle and
  dependency overflow; reject changed live occupancy without cell mutation;
  preserve failure cleanup and per-request queue budget stops; and check pause,
  reset/discard and read-only predictor behavior.
- All 142 workflow QA tests pass locally. All 24 batch tests pass ThreadSanitizer;
  all nine new escape tests pass ASan/UBSan. Actionlint and diff checks pass.
  Corrected code `61122e025` also passed all 142 Mac QA tests, the workflow race
  checks, actual iOS SDK compilation, platform/rpath packaging checks and unsigned
  IPA upload in [run 40487632736](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40487632736).
  The artifact is `GeneralsXZH-iOS-unsigned`.
- The next supplied device log identifies `~61122e0`, reaches the score screen
  and exits with code 0. It completes 87 parallel pairs: 167 accepted results,
  six validation rejections and one unused result, accounting for all 174
  speculative completions (96.0% reuse). The worker reports 87 searches.
  `PATH_PARALLEL_SAFE` reports zero searches and zero accepted results, so the
  new parallel escape kernel was not exercised. This does not establish whether
  safe requests were absent, unpaired or ineligible. The cache directory reports
  `state=reused`; this confirms directory reuse, not individual pipeline-cache
  hits or a timing improvement. Both CSF tables load fully, and no primitive-restart
  warning or fatal error is recorded. Specific escape, lifecycle and performance
  validation remain pending; opening the replay menu does not establish replay
  playback or deterministic equivalence.

Run 40485884866 also passed all 142 Mac QA tests and its race checks, but SDK
compilation found the shared validator above the `LiveOccupancyReader` definition.
The isolated fixture had hidden this by emitting the reader first. Move the
validator below the reader and preserve their real relative order in the fixture.
All 24 batch tests pass after this build correction; a negative control restoring
the old order fails compilation. Subsequent run 40487632736 passed and uploaded
the corrected IPA. The failed run did not produce a new installable artifact.

Only session summaries are added: the existing batch counters plus
`[PATH_PARALLEL_SAFE] stopped searches=N accepted=A`. N counts both caller and
worker escape computations; A counts validated reused escape completions,
including a correctly reused no-path outcome. The overall worker count still
counts one worker task per completed pair. There is no per-cell log or new shadow
replay. No device frame-time, memory or universal replay claim is made.

## Remaining comparison

The follow-up [closest-search stage](IOS_PARALLEL_CLOSEST_SEARCH_2026-10-27.md)
adds queued approach predictions. The paragraph below describes the scope at the
escape stage; ordinary-failure fallback remains serial after that follow-up.

Reimagined also predicts closest-destination requests and the closest fallback
after ordinary failure. Those remain serial here, as do attack/patch requests,
hierarchical preparation and path optimization. The reference's larger batches,
worker pool and dense map records are not adopted. This extends actual worker
coverage; it is not the complete Reimagined implementation.
