# Participant arenas and joined dynamic pool — 31 October 2026

## Enabled trial

`GENERALS_PATH_WORKER_POOL` defaults OFF and requires complete-worker mode plus
independent result snapshots (`GENERALS_REUSE_PATH_CONTEXTS`). The experimental
iOS branch enables it with the existing anchored lookahead. Production still
selects two requests and starts one background worker plus main. Search limits,
prediction gates, live validation and per-request budgeting stay unchanged.

This applies the ownership and pool work in
[the feasibility audit](IOS_DYNAMIC_PATH_POOL_FEASIBILITY_2026-10-30.md). It does
not yet enable four selected requests or two background workers on device.
The bounded generic executor supports zero to two workers and up to four logical
jobs; these larger configurations are exercised in host tests.

## Ownership and execution

The pool and its arenas belong to `PathfindParallelBatch`, whose lifetime is
subordinate to Pathfinder and engine memory. Each physical participant has one
arena. Logical jobs no longer own an arena, hold an arena reference, or reset an
arena when their result is discarded. Complete execution receives scratch as an
explicit argument. Capturing complete-record counts reads the active bound
context rather than an arena associated with a result slot.

Main and the worker dynamically claim logical job indices. A claimed item runs
the primary and any conditional closest fallback on the same participant arena.
That arena can then execute another job. Paths, dependency logs, occupancy caches,
admission windows, timing and publication snapshots remain independently owned
by each result. Main validation and application still follow actual queue order.
Generation stamps and stable candidate ordering remain context-local.

Bind execution pointers only for the duration of the complete API and restore
them through exceptions. After join, clear each participant once, independently
of job/result resets. Retirement does not allocate a new lookup table for an
arena that never executed. The next actual search prepares its bounded index.
The pool stops/joins before its arena storage is destroyed. The existing
one-worker exclusive/fine-only implementation remains under the OFF path.

## Pool contracts

`JoinedSearchPool` uses fixed-capacity bookkeeping, atomic next-job claims,
condition-variable wake/join, and stable participant IDs (main zero). It does not
spin while waiting for a new batch, use x86 intrinsics or allocate a shared batch
object for each dispatch. `std::function` captures can still allocate depending
on their size and standard-library implementation.

- Only the idle owning thread dispatches; nested pool calls and dispatch from
  search worker callbacks are rejected.
- Every started callback exits before dispatch returns or rethrows, including
  caller and worker failures. Result/error slots are written only by the owner
  of the corresponding logical job.
- Callback errors are collected, then selected in logical job order after join;
  participant setup errors follow in participant order. Error arrival order does
  not select the propagated failure. Engine recovery/out-of-memory handling
  retains the existing caller-side discard/fallback policy.
- Capture the caller's floating-point environment per dispatch, restore it before
  each callback, and restore main's environment after join, including errors.
- Check the captured lifecycle/pause condition before claiming and before starting
  another job. Cancellation skips unstarted work; callbacks already running finish
  and join. A cancelled unexecuted result is never marked ready. Main validation
  retains lifecycle checks for all completed results.
- Partial thread construction stops/joins created threads before unwinding. The
  factory injection used to test this does not change production thread creation.
- Worker-role scope is shared with `ExclusiveSearchWorker::onWorker`, preserving
  the optional occupancy-sampling exclusion on every background participant.

The callback and cancellation predicate must obey the frozen-world, private-output
contract. These rules do not permit asynchronous simulation or live AI callbacks
while the pool runs.

## Timing and storage

`[PATH_WORKER_POOL] enabled` reports dynamic assignment and the unchanged engine
width/count. Shutdown reports returned pool batches, skipped jobs and executed
logical items per participant. Primary/fallback phases belong to one logical
item; the counts are not counts of individual fine kernels.

`worker_kernel` and `caller_kernel` aggregate by the actual executing participant.
The retained two-slot task samples and disposition matching stay indexed by
logical result slot. Existing `caller`/`worker` prefixes in those retained sample
rows now denote legacy slot names in pool mode, not guaranteed physical execution.
`[PATH_POOL_TASK] pair=... slot=... participant=...` gives the physical mapping.
This preserves sample/result identity even when main claims both requests.

Controlled 64-bit layout reports an unchanged 2,804,560-byte arena. The profiled
result job changes from 1,520,720 to 1,520,768 bytes: removing arena ownership
fields is offset by physical-participant metadata in its private timing samples.
Two arenas and up to four primary/fallback result slots remain retained. These
layout sizes and small fixed pool bookkeeping are not device RSS or a demonstrated
speedup. Native layout rows remain authoritative for the next IPA.

## Verification scope

`test_joined_search_pool.py` covers exactly-once claims, zero/one/two-worker output
equivalence, three-participant overlap, successive dynamic claims, callback error
ordering, FP changes through successful and throwing callbacks, cancellation,
owner/nesting/bounds/stop checks, and partial/empty thread-construction failures.

`test_participant_path_pool.py` uses complete production search methods and replays
the queue/path/budget, candidate-exclusion, nonadjacent, deletion, recovery and
post-load checks with the new executor. New cases assert results have no context
member, result reset cannot reset participant arenas, arenas persist across batches,
and poisoned arena contents cannot change primary/fallback publication.

An explicit host probe executes four complete ordinary APIs on three participant
arenas, forcing three-way concurrent hierarchy and successive arena reuse. It
retains all four Paths after scratch is reset. This validates a future pool
configuration without enabling it in the engine's device dispatcher. Other cases
check lifecycle changes during capture and before claims, cancellation readiness,
engine errors, private-pointer restoration, physical timing assignment and
profiler/cache-OFF serial equivalence.

All 313 regular cases pass: the preceding 290 plus seven executor and sixteen
pool integration cases. All 23 pool cases pass TSan and ASan/UBSan. The final
cleanup/index refinement also passes the sixteen integration cases normally
and two targeted ownership/capture cases under both sanitizers.
Fixtures use controlled world/AI/allocation services; they do not prove arbitrary
production thread safety, iOS scheduling behavior or multiplayer replay parity.
Native SDK compilation and device gameplay/lifecycle testing remain required.

## Next boundary

Test this ownership/executor change on the same gameplay scenarios first. Then
expand the independent logical result/window capacity to four and retain one
worker for an isolated lookahead-width trial. Only afterward trial two workers
with the same window and measure useful work, join time, stale/discard rates,
memory and thermal behavior. A pool cannot divide the current single serial
closest-search spikes. Broader AI prediction or altered search/queue budgets
remain separate changes.
