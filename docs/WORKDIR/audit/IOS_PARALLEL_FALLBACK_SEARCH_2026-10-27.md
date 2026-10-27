# Conditional ordinary-failure closest search — 27 October 2026

## Behavior

Extend the existing two-request dispatcher to the AI callback's
`findPath` failure followed by `findClosestPath` with no existing path, blocked
false, cost multiplier 0 and move-allies false. Adapt the conditional ordinary/
closest task sequence from dement123's supplied Reimagined source, specifically
`prefetchPaths` / `runPrefetchedSearch`. Keep the original stable loops,
30,000-record admission, 5,000-cell queue accounting, original pruning, one worker,
caller participation and adjacent request order.

On main, prepare the ordinary phase as before. Only if both primary kernels were
captured, prepare one closest fallback for each ordinary request with no current
path. Preparation uses the existing unrestricted-corridor/provisional-hierarchy
policy, does not run hierarchy, allocate a Path, adjust the AI destination, change
AI flags or execute cleanup. This extra preparation can cost CPU time even when
ordinary search succeeds. Existing-path requests and queued safe/approach requests
do not prepare this fallback.

In the original single `runPair`, each task runs its primary kernel. Only ordinary
fine-loop failure executes its prepared closest kernel, in a separate context on
the same task/thread. Both tasks join before queue consumption. No extra dispatch,
worker, larger request batch or wait across frames is introduced.

## Consumption and rejection

The ordinary result must pass the existing exact input/dependency validation and
finish its original main-thread cleanup before the fallback becomes eligible.
An ordinary rejection or success cannot authorize fallback reuse. The subsequent
actual AI call still decides whether fallback is needed. Its closest preparation
and real hierarchy run on main, followed by independent validation of fallback
policies, endpoints, object/locomotor identity, current no-path condition, movement,
ignore/tunnel state, admission, retail mode, world/lifecycle epochs, cells, observed
corridor, occupancy answers and terrain heights. Any mismatch uses the caller loop.

Each phase is single-use at the original queue position. Main constructs and
optimizes Paths, adjusts destination XY, performs original cleanup and charges
actual work. Separate arenas preserve each phase's list links, parent links,
admission and retail cleanup order without estimating a scalar failure cleanup.
Pause/reset/queue-end discards both completions; no result crosses a queue call.

This covers failures of eligible ordinary fine-search loops. Early returns in
the outer quick/hierarchical checks or ordinary preparation, path-materialization
failure and unsupported request types retain normal caller execution. A restrictive
real hierarchy can also reject the speculative unrestricted-corridor result.
It is not full Reimagined prefetch parity or evidence of faster gameplay.

## Bounded memory tradeoff

At most one fallback context is allocated per primary job, lazily on its first
eligible no-path request, and reused. There are at most four search contexts total
for the two queued requests, never recursive fallback contexts. Each phase retains
30,000 records and at most 8,192 entries per read-dependency category. Simultaneous
scratch capacity and dependency storage therefore increase; per-search capacity
and original main-thread admission do not change.

A local 64-bit production-body fixture measures 6,035,600 bytes per job, including
its fixed context and dependency tables, and 12,071,312 bytes for the two-primary
batch. Two allocated fallbacks bring fixed storage to 24,142,512 bytes. Typical
bounded vector/frontier storage at capacity adds about 3.1 MiB for all four phases,
plus four map-sized hierarchical corridor arrays, allocator overhead and the
existing worker runtime/stack. This is approximately 26 MiB total extra search
storage, about 13 MiB above the previous two-context stage, not measured iOS RSS.
Allocation failure joins/discards speculation and retains normal caller dispatch.

## Counters

The primary batch, safe and queued-closest summaries keep their previous meaning.
`[PATH_PARALLEL_FALLBACK] stopped searches=N accepted=A rejected=R unused=U` counts
completed conditional closest kernels (both caller and worker), accepted/reused
completions including no-path results, failed fallback validations and completed
results discarded without consumption. Invalidated ordinary phases can leave
their fallbacks unused. These results are additional to the primary batch totals;
the primary invariant remains two completions per completed batch.

## Verification

The existing 35 batch tests pass before adding this stage's cases. Nine additional
tests plus the revised prior serial-fallback regression cover 256 serial/parallel
combinations across both retail modes, centered/off-center units, two radii,
ordinary success/failure mixtures and seeded obstacles. Routes, adjusted targets,
actual charged work, hierarchy calls, ignore/tunnel flags and corridor state match.
The previous closest and ordinary golden tests remain in the suite.

New cases require actual overlapping fallback kernels on caller and worker within
one dispatch; main-only hierarchy/path finalization; rejection before ordinary
acceptance, changed closest policy/hierarchy/observed corridor/unit/world/lifecycle,
live occupancy and heights, overflow and single-use; no fallback after success or
with an existing path; no fallback preparation for an incomplete pair; bounded
storage reuse/reset and preserved original per-request budget stops and order.

All 162 local workflow QA tests pass, including all 44 batch tests. All 11
fallback-related tests pass ASan/UBSan. All 44 batch race-check cases pass TSan:
the full run passed 43 cases, while the 256-case comparison exceeded the original
10-second execution guard; its focused rerun passes in 15.5 seconds after giving
only that workload a 45-second guard. The matrix and production code were not
reduced to satisfy the guard; other tests retain their 10-second default.
Actionlint and diff checks pass. Actual iOS SDK compilation/packaging and device
validation remain pending.

The first SDK workflow attempt, [run 40518666347](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40518666347),
passed all 162 Mac QA tests but failed the subsequent race-check step before
compilation. Its public annotation exposed only exit 1. Added captured runtime
assertion/sanitizer output to the fixture helper and race-suite CI annotations;
retain all checks and await a concrete diagnosis from the next run.
The fixture uses production cells, lists, contexts, kernels, dispatcher and
validation with controlled world/hierarchy/Path services; it does not prove
full-world race freedom, replay equivalence, device movement, memory or speed.
