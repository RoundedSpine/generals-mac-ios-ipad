# Closest fallback after early ordinary rejection — 27 October 2026

## Scope and behavior

Continue the Reimagined-inspired conditional closest-search implementation without
waiting for a positive device fallback counter. The previous stage required both
ordinary/safe/approach fine kernels to be captured; ordinary preparation rejection
prevented the pair from running. Now each of the same two adjacent queued requests
can contribute its primary kernel or a closest-only fallback kernel when ordinary
preparation/terrain screening rejects it. The existing ordinary predictor still
limits eligible requests; unsupported AI branches remain serial.

Perform the original quick terrain check on main during ordinary preparation.
If it rejects, skip speculative ordinary expansion. Prepare the closest kernel
on main using its existing provisional hierarchy policy. If the quick check passes
but ordinary preparation rejects (for example, a destination or zone check), the
prepared closest kernel can likewise supply that request's task. Immobile units,
unsupported safe/approach preparation and early ordinary rejection with an existing
path cannot supply a fallback; they do not create a one-request worker dispatch.
Both queued requests must offer work before the original single `runPair` runs.

The worker and caller execute only their own scratch kernels. Actual quick checks,
hierarchy, Path construction/optimization, destination changes, cleanup, AI changes
and search accounting remain on main. Retain one worker, two adjacent requests,
the 30,000-record per-search limit, 8,192-entry dependency categories, original
pruning, original queue order and 5,000-cell budget checks after each actual
request. Reset the speculative ordinary outcome at each request so an early exit
cannot inherit the prior request's found flag.

## Caller confirmation and independent validation

The original AI `theNewPath == nullptr && m_path == nullptr` branch now confirms
fallback eligibility immediately before calling `findClosestPath`. That branch
is authoritative even when an early destination check bypasses `findPath`, the
outer quick check rejects, ordinary preparation returns early, or a rejected
ordinary result has been recomputed on main and still fails. Confirmation requires
the same current queue position, object/ID, locomotor identity, exact endpoints,
no existing path, unblocked request, active batch, unpaused state and no nested
search binding. It changes only private result eligibility, not AI state.

Accepted ordinary-loop failure can still authorize fallback through its existing
main finalization. Other callers cannot consume an early fallback merely by
calling `findClosestPath` without the actual no-path confirmation. A caller search
that succeeds discards the prediction. A main Path-materialization failure retains
caller fallback when no closest kernel was computed, as before.

Confirmation never replaces validation. Closest preparation and real hierarchy
still run on main, followed by the same exact closest-policy, object/locomotor,
movement, endpoint, ignore/tunnel, admission, retail-mode, epoch/lifecycle, cell,
observed-corridor, occupancy and height checks. Stale results are single-use and
fall back to the caller. An invalid ordinary completion can authorize no result
by itself; after actual caller recomputation fails, an independently valid closest
completion may be reused. No ordinary failure cleanup is synthesized or cached.

## Memory, lifecycle and counters

Reuse the previous stage's two primary and at most two fallback contexts. No new
arena, worker or map-sized node storage is added. The local 64-bit fixture still
measures 6,035,600 bytes per job; added session counters bring the primary batch
to 12,071,344 bytes and four-phase fixed storage to 24,142,544 bytes. The prior
approximately 26 MiB total bounded search-storage estimate, plus map-dependent
corridors/runtime overhead, remains applicable. This is not measured device RSS.
Fallback preparation and discarded speculation can add CPU work; no performance
gain is established by preserving the original queue budget.

Pause/reset/queue-end still discard both phases; work joins before consumption.
No result crosses queue calls. Completed primary and fallback-only tasks are now
distinguished in `[PATH_PARALLEL_BATCH]` by `primary=N fallback_only=F`. During
normal completion, `N + F == 2 * batches`, and primary accepted/rejected/unused
totals account for `N`, not necessarily twice the batch count. No primary result
is counted when that kernel was never executed.

`[PATH_PARALLEL_FALLBACK]` retains its existing searches/accepted/rejected/unused
counts and adds `early_searches`/`early_accepted` for completions whose primary
kernel was not captured. Those are subsets of fallback totals. Counts include
caller participation and accepted no-path completions, not only successful routes
or worker-thread executions. Existing queued-safe and queued-closest counts retain
their previous meaning.

## Verification and device evidence

Ten new tests cover 144 controlled serial/parallel cases across both retail modes,
early destination/zone/outer-quick rejection, request-kind/order mixtures and seeded
obstacles. Compare routes, adjusted targets, charged work, corridor/ignore/tunnel
state and counter accounting. Require actual overlapping early-fallback-only tasks
within one dispatch, explicit caller confirmation, guarded queue/object/request/
locomotor identity and no-path state, stale-world rejection after confirmation,
normal caller success overriding prediction, independent fallback validation after
caller recomputation, and original per-request budget cutoff/discard behavior.
Compile the actual AI no-path branch in enabled and disabled builds to verify
confirmation precedes closest execution and existing paths/success skip both.

All 172 local workflow QA tests pass, including all 54 batch cases. All 54 pass
TSan, and all ten new cases pass ASan/UBSan. Actionlint and diff checks pass.
SDK and device checks remain pending. Fixtures use production cells, records, contexts, kernels, dispatch,
validation and the AI fallback branch with controlled quick-check/hierarchy/world/
Path services. They do not establish full-engine replay equivalence, full-world
race freedom, device movement, memory high-water mark or frame-time improvement.

The first SDK attempt, [run 40531271316](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40531271316),
remained queued waiting for a macOS runner without starting any steps. The runner
configuration is unchanged from successful run 40520080544. At the user's request,
trigger a fresh attempt with the same engine/workflow and cancel the queued
attempt through the existing per-branch concurrency rule; SDK validation is still
pending, with no build failure established by the queue delay.

The retry [40533086198](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40533086198)
failed at runner provisioning without starting any steps. GitHub annotations
report `Internal server error`, `The job was not acquired by Runner of type hosted
even after multiple attempts`, and repeated ARM64 capacity warnings; the user's
screenshot confirms them. The
[official image catalog](https://github.com/actions/runner-images#available-images)
maps `macos-15` to ARM64 and `macos-15-intel` to x64. Change the workflow to the
explicit Intel pool and retain the same iOS preset, ARM64 vcpkg triplet and Meson
cross file. The documented host images share default Xcode 16.4, and the cache
key already includes `runner.arch`. The final IPA's ARM64/device-platform checks
remain unchanged. Intel allocation, SDK compilation and packaging remain pending;
this is a pool change, not a claim of guaranteed availability or a gameplay fix.
Local actionlint 1.7.7 predates the documented Intel label; validate the workflow
with only its exact `label "macos-15-intel" is unknown` catalog warning filtered.
All other actionlint checks and `git diff --check` pass. The official image catalog
above, not the older local label list, establishes that this hosted label exists.

The latest supplied log identifies the prior `b97fa0c` binary, reaches the score
screen and exits 0. It records 280 pairs/560 primary completions: 546 accepted
(97.5%), 14 rejected, none unused, and 280 worker tasks. Parallel safe, closest and
fallback counters are zero. Both CSF tables finish, cache-directory state is
reused and no primitive-restart warning appears. One WAV sample-count warning is
present. The log does not exercise fallback or measure performance. The user
explicitly requested continued implementation even if fallback remained untriggered.
