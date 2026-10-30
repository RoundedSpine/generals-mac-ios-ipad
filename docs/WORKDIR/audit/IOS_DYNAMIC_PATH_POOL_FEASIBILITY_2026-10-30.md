# Larger pathfinding pool feasibility — 30 October 2026

## Decision

Feasible as a bounded adaptation of Reimagined's dynamic dispatcher. The complete
search APIs, private state, completed-result ownership and main-thread validation
already exist. The remaining work is structural: detach scratch ownership from
logical jobs, replace fixed adjacent pairing with a bounded lookahead window,
and introduce an exception-safe joined pool. No further micro-optimization is a
prerequisite. This investigation does not enable additional workers or change
the IPA workflow.

Start with at most four eligible primary requests from at most eight queued
entries, two background workers plus main, and one arena per participant. Keep
the current prediction exclusions, search limits, per-request queue-budget check
and serial result-application order. The window policy must be independent of
worker count. Test zero, one and two workers against the serial baseline before
considering a wider window or more workers.

## Source comparison

Reviewed branch revision `fc8a2ddc8` and the supplied
`ZeroHourReimagined_1.0.0_source`.

| Concern | Current implementation | Reference | Required adaptation |
| --- | --- | --- | --- |
| Dispatch | Two adjacent requests; one unsupported entry rejects the pair | Scan eight entries and skip unsupported predictions | Keep a bounded scan and separate eligible-job cap; skip unsupported/duplicate entries |
| Assignment | `runPair`, fixed job 0 on main and job 1 on worker | Atomic next-chunk counter; main and pool claim chunks | Claim one primary-plus-conditional-fallback work item at a time |
| Scratch | Primary job owns arena; its fallback borrows it | Reusable thread-local arena | Participant owns arena across multiple logical jobs |
| Outputs | Path, logs/cache, admission, publication state and timing owned per result | Path and read-cell set owned per result | Retain our independent outputs and exact live validation |
| Queue policy | Check 5,000-cell allowance after each actual request | Nonlegacy budget checked between groups of eight | Retain current policy; discard unconsumed speculation at frame boundary |
| Worker count | One background worker | Auto `clamp(cores - 3, 0, 8)`; explicit cap 32 | Begin with explicit 0/1/2; logical core count alone is not an iOS performance policy |
| Waiting | Condition-variable join, including callback exceptions | Caller yields for chunk completion; workers spin 500 microseconds before sleeping | Sleep while idle; join all participants through errors; benchmark wake cost later |
| Portability | Standard C++ threading and captured floating-point environment | `<intrin.h>` / `_mm_pause()`, no per-batch FP propagation | ARM64-compatible pool, retaining environment propagation |

Current source anchors:

- `AIPathfind.cpp:4459`: job-owned arena and immutable context reference.
- `AIPathfind.cpp:4570`: fixed two-job batch.
- `AIPathfind.cpp:5873`: queue-position/request/live dependency validation.
- `AIPathfind.cpp:6014`: whole API execution under a bound private context.
- `AIPathfind.cpp:7169`: authoritative main-thread queue and budget loop.
- `AIPathfind.cpp:7729`: capture, pair-lifetime tests, dispatch and joined cleanup.
- `exclusivesearchworker.h:26–74`: current environment and failure handling.
- `pathsearchtiming.h:90,274,426`: two-task samples, role assertion and reports.

Reference anchors are `GeneralsMD/Code/GameEngine/Source/Common/JobSystem.cpp`
(`Batch::work`, `Pool::parallelFor`, `workerMain`, `chooseWorkerCount`) and
`Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp:5810–5975`
(`processPathfindQueue`, `prefetchPaths`, `runPrefetchedSearch`).

## What already supports concurrency

Generation-stamped nodes, open/closed lists and hierarchy corridor flags are
context-local. Whole APIs already run on participants while simulation is
stopped. Each completed result owns its PathNodes and the publication snapshot;
the latest reuse work demonstrates that applying a result does not need its
original arena contents. This is the key prerequisite for dynamic assignment.

Validation is keyed to request/object/queue position, not worker identity. It
already checks movement policy, allocation decisions, live cell and occupancy
results, terrain heights/layers, object snapshots and world/lifecycle epochs.
Broader lookahead increases how long results wait before consumption, so retain
every check and measure rejection/discard rates. Validating after the fact is
not a substitute for freezing simulation during execution.

Engine Path allocation/free and DMA paths have existing critical sections;
classes are warmed on main. Increasing workers can increase allocator contention
even when correctness is preserved. Three-way production-search concurrency
still needs tests: prior two-way checks do not establish arbitrary scalability.

## Changes that must precede enablement

1. **Separate participant scratch from result records.** The current job embeds
   an owning pointer and immutable context reference, and its reset may reset
   the arena. Give the joined pool fixed participant arenas and pass the selected
   arena explicitly into complete execution. Bind job logs/cache/admission/timing
   only during that callback. Result reset must never touch an arena potentially
   running a different job. Keep primary and fallback in the same claimed item.
   Retain the fine-only implementation under its existing OFF-path guards.
2. **Replace two-index batch lifetime with a queue window.** Store the original
   queue positions and scanned span, including unsupported holes and ring wrap.
   A serial callback between captured jobs must not clear later results merely
   because its index is not a job index. Do not rescan the same window repeatedly.
   Skip later duplicate object IDs in a window. Newly enqueued requests belong to
   a later window. Do not dequeue, apply paths or charge unused work on workers.
3. **Add a bounded joined pool.** Only its owning logic thread dispatches; reject
   nested/reentrant dispatch. Claim stable logical jobs dynamically and write only
   their result slots. All callbacks exit before return, including failures.
   Capture failures per logical job and choose an explicit, stable error policy
   after join; never propagate whichever thread fails first. Retain serial
   fallback for allocation, engine out-of-memory and environment/thread failure.
   Partial thread construction must stop/join already-created threads before
   unwinding. Zero-worker mode and insufficient eligible work remain supported.
4. **Preserve lifecycle and allocator lifetime.** Check captured pause/lifecycle
   state before claiming another job. If it changed, skip remaining unstarted
   speculation, join in-flight work, then discard on main. Do not pump engine/UI
   callbacks while waiting. Existing SDL watcher atomics and live rejection stay.
   Explicitly drain/stop the pool before arena/map/engine-memory teardown; avoid
   global thread-local contexts outliving the memory manager.
5. **Generalize timing and tests.** Separate logical job slot from executing
   participant ID. Replace two-role assertions/arrays and prediction counters
   with bounded window-aware storage; keep reports bounded and merge on main.
   Measure eligible count, claimed/completed jobs per participant, join duration,
   discarded/rejected work and allocation footprint. Kernel sums overlap and
   cannot be equated to batch wall time.

The existing worker-only occupancy guard must recognize every new pool worker,
including configurations with optional shadow validation. Context bindings must
continue rejecting simultaneous ownership of one arena.

## Controlled reference probes

Compiled the supplied `JobSystem.h/.cpp` as isolated host programs with minimal
engine type/configuration stubs. Replace Windows `<intrin.h>` with the host's
`<immintrin.h>`; scheduling implementation is otherwise unchanged. These probes
do not execute the game or establish iOS performance.

The reference's own output-equivalence self-test succeeds with zero, one and two
workers: `workers=0/1/2 equal=1`. This supports its basic dynamic-claim mechanism.

An exception probe starts one worker callback and holds it on an atomic gate.
The main callback waits for worker entry, then throws. Catching outside
`parallelFor` reports:

```text
caught=1 worker_finished_at_return=0
worker_finished_after_shutdown=1
```

The callback object is deliberately kept alive until explicit release/shutdown,
so the probe does not rely on use-after-free. It demonstrates a caller exception
bypassing the reference's barrier. Its worker callback also has no exception
catch, and constructor unwinding does not explicitly join already-created
threads. Our search code intentionally throws for speculative recovery and
allocation failures, so these contracts must be adapted before integration.

An FP probe creates the reference pool under `FE_TONEAREST`, changes the caller
to `FE_DOWNWARD`, and forces both participants to execute. Host output is:

```text
caller_round=1024 worker_round=0 same=0
```

The numeric constants are host-specific. This proves the reference does not
propagate a subsequent caller rounding-mode change; it does not claim normal
reference gameplay uses mismatched modes. Preserve our existing per-dispatch
environment capture/restore and test persistent workers across mode changes.

## Memory feasibility

Using the preceding controlled 64-bit layout of 2,804,560 bytes per arena and
1,520,704 bytes per result job, with a retained fallback slot per primary:

| Configuration | Participant arenas | Maximum primary/fallback result slots | Fixed storage |
| --- | ---: | ---: | ---: |
| Current two requests, one worker plus main | 2 | 4 | 11.15 MiB |
| Four requests, two workers plus main | 3 | 8 | 19.63 MiB |
| Eight requests, two workers plus main | 3 | 16 | 31.23 MiB |

These estimates include the separate heap arenas and retained result-job layouts,
exclude the unchanged serial context, and assume no job embeds another arena.
New wrapper fields may change sizes. Additionally account for indexes (up to
1 MiB per participant), heap/list/corridor capacity, dynamically retained logs,
completed Paths, thread stacks and pool bookkeeping. They are not total RSS or
an iPhone memory-headroom measurement. Result metadata and dependency storage,
not just arenas, make an eight-request window more expensive. Four eligible
requests are a reasonable first cap; validate actual device allocations.

## Expected benefit and limits

The latest supplied `~b05cf78` log records 1,105 dispatched pairs, 8,253 short-queue
attempts, 745 dozer rejections and 3,911 prediction rejections. Prediction failures
are mostly at slot 0 (2,036 attack and 1,752 nonfinal). These are attempts, not
unique requests or an eight-entry eligibility histogram. Skipping unsupported
entries may expose more parallel work; the log cannot establish how many future
eligible requests were available or the best pool size. Preserve exclusions first.

Retained pair 50 has a 14.101 ms worker and 0.039 ms caller; pair 150 has a
34.411 ms worker and 9.520 ms caller. Dynamic claiming lets a participant that
finishes early take another available request. It does not divide the 34 ms
individual search. Main still waits for the longest participating task. Extra
lookahead can also compute results that the frame budget never reaches, increase
stale-result recomputation, or hold up an otherwise cheap queue head behind an
expensive future job. No guaranteed hitch/FPS improvement follows from adding
workers. Zone rebuilding remains synchronous and unaffected by this pool.

## Recommended implementation and acceptance sequence

1. Detach arenas from results and implement the bounded pool with the existing
   two-request window and one worker. Establish ownership, FP and error equivalence.
2. Introduce the fixed scan-eight/cap-four window with one worker. Retain all
   prediction gates and per-request scheduling. This isolates wider-lookahead
   effects before increasing concurrency.
3. Enable two background workers as a separate trial with the same window.
   Compare identical order sequences, actual queue work, frame timings, result
   reuse/discard/rejection rates and device memory/thermal behavior.
4. Consider larger windows/counts only if useful work and join-time evidence
   justify them. Eight-request budget batching and larger node limits remain
   separate gameplay/scheduling choices.

Required checks include zero/one/two-worker output and charge equivalence;
exactly-once dynamic claims under deliberately uneven task durations; three-way
concurrent hierarchy/construction/optimization; independent primary/fallback
publication; queue holes, wrap, duplicate IDs and newly enqueued work; unit deletion,
terrain/bridge/team changes before consumption; budget exhaustion with unused
results; caller/worker exceptions and partial thread creation; pause/resume and
reset/destruction through failure; repeated FP changes and bounded storage. Run
the production fixtures under TSan and ASan/UBSan, then native ARM64 compilation
and device scenarios. Pure source/probe findings do not replace these checks.
