# Experimental pathfinding phase timings — 28 October 2026

## Purpose and scope

Follow the refreshed Reimagined comparison by measuring the working two-request
implementation before changing worker count, storage or scheduling. Add optional
phase-boundary wall-clock measurements, enabled for experiment/ios-mod-testing's
IPA and disabled by default with GENERALS_PATH_TIMING. It requires the parallel
batch option. Keep the requested macos-15 ARM64 runner.

No request eligibility, search loop, limit, queue budget, result-validation rule,
worker count or path policy changes. std::chrono::steady_clock measures elapsed
wall time, including preemption or suspension, independently of the game clock.
Timing never participates in a gameplay decision. No per-cell clocks, per-request
log lines, dynamic timing allocations or additional worker threads are introduced.

## Measurements

The Pathfinder owns ten session aggregates. Each records calls, total and maximum
elapsed time, and cumulative counts at or above 1/5/20/50/100/500 milliseconds.
Normal destruction prints a fixed eleven-line PATH_TIMING summary alongside the
existing result counters. No summary is guaranteed after a crash or force-kill.
Counters span the Pathfinder lifetime, including multiple games and menu activity;
they do not reset on a map change.

| phase | Meaning |
| --- | --- |
| queue | Entire processPathfindQueue calls that begin with pending requests and a ready map; includes callbacks and pending zone recalculation |
| prepare | Speculative batch preparation attempts, including eligibility failures and allocation; stops before parallel dispatch |
| caller_prepare | Authoritative ordinary fine/safe/closest preparation, including early returns; excludes speculative preparation and stops before validation/kernel/finalization |
| pair | Dispatch, caller task and joined wait for the worker; wall time of the parallel barrier |
| worker_kernel | Executed primary/fallback phase times for job 1, including context/admission binding |
| caller_kernel | Executed primary/fallback phase times for job 0, including context/admission binding |
| serial_kernel | Ordinary/safe/closest loop executions without a speculative read log, including recomputation after rejection |
| validate | Active-batch result lookup and validation, including unsuccessful candidate lookup and rejected results |
| hierarchy | Actual main-side ordinary/closest hierarchy API calls at their call sites |
| finalize | Main-side ordinary/safe/closest completion lambdas, including Path construction/optimization and original cleanup on success or failure |

These are overlapping totals. queue contains other phases; pair overlaps both
task roles; closest caller_prepare contains its hierarchy call. Ordinary outer
quick checks, AI callbacks, some setup/merging and unsupported search types are
not separate metrics. The full queue duration includes work not attributed to a
named subphase; summing the rows is invalid. These are not per-frame render times,
CPU-time samples, device RSS measurements or serial-versus-parallel benchmarks.

Worker code writes only the current job's private metric. After the existing
runPair join, main merges primary and fallback metrics into the role aggregates.
Reset clears per-job metrics before reuse; unused/rejected completed speculation
still counts as work performed. Primary and fallback kernels can contribute two
calls for one request. The barrier includes exceptional attempts; kernel metrics
are merged only after successful completion of the pair, so an exception is not
a normal accounting run. No worker writes the shared session aggregate.

The optional scope records on early return and exception, and stop is idempotent.
A null scope performs no clock reads. With the option disabled, guards remove all
engine timing storage, clock reads and reports. The helper uses only portable C++
facilities in WWLib, with no new native platform API in game logic.

## Verification

The batch fixture now enables timing by default so all existing parallel route,
budget, stale-result, lifecycle and sanitizer cases compile the measured paths.
Five new cases check deterministic threshold/merge/stop/exception behavior with
an injected clock, compare timing ON/OFF across 32 controlled ordinary/safe/
closest/early-fallback scenarios, and exercise actual dispatch, rejected/unused
work, private fallback metrics, empty queue calls and preparation early exits.
World, hierarchy and Path services in these fixtures remain controlled; this is
not a complete engine replay or a device performance measurement.

All 177 local workflow QA tests pass. All 59 batch tests pass ThreadSanitizer
with timing enabled in the fixture; the five new cases pass ASan/UBSan. Actionlint
and git diff checks pass. Actual iOS SDK and device timing verification remain
pending; local fixtures cannot establish native iOS timing overhead or a speedup.

## SDK failure and interface correction

The uploaded logs for [run 40595200430](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40595200430)
show successful macos-15-arm64 provisioning, all 177 Mac QA tests and the complete
race-check step, including all 59 batch cases. Compilation then fails at the three
serial timing probes: searchState() returns PathfindSearchBookkeeping, whereas
m_parallelReads belongs to the derived PathfindSearchContext. No IPA was produced.
The vcpkg setup pathspec diagnostic did not stop its step or configuration; it is
not the reported build blocker.

Read that context-only pointer through activePathfindSearchContext() in ordinary,
closest and safe kernels. Keep searchState()'s existing interface. The fixture now
extracts the accessor directly from the production header instead of returning a
broader type; mock-only context operations likewise use the context accessor.
An explicit negative compilation confirms the original bad probes are rejected
by this corrected fixture. All 177 local QA tests, all 59 batch TSan cases and the
five timing ASan/UBSan cases pass with the production accessor. Actionlint/diff
checks pass. Replacement SDK verification remains pending. This correction does
not change search or timing policy.

## Device test and interpretation

Play a normal game with group moves, tight spaces and bridges, then exit normally
through the game so the log includes PATH_TIMING and the existing worker counters.
No special debug launch flag is required for the experimental IPA.

Check queue maxima and threshold counts first, then pair and the main-side phases.
A large pair relative to individual task times may include wakeup/scheduling and
waiting; elapsed clocks alone cannot separate those causes. Rejected-result
counts together with serial_kernel show recomputation occurred, but do not assign
every serial call to rejection or identify its precise validation failure.
If hierarchy/finalize dominates, more fine-loop workers cannot remove that cost.
Large prepare/validate costs justify reducing duplicate work or lookup overhead.
Use comparable scenarios and an unmeasured build for any eventual speedup claim;
profiling itself has overhead. Memory measurement and compact-record work remain
separate follow-ups.
