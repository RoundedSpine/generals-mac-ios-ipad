# Four logical requests on two participants — 31 October 2026

## Device baseline

The uploaded e18c0ae log confirms the participant-owned pool on iOS, normal exit
code zero and reconciled accounting: 1,406 batches, 2,812 primary jobs, 1,623 main
and 1,189 background executions. Primary results resolve as 2,765 reused, 20
rejected and 27 unused (98.33% reuse). All 37 closest fallbacks resolve: 34 reused,
one rejected and two unused. No logged pool failure, skipped work, overflow or
unfinished validation. The expected rejections cover changed request kind, cell
snapshots and occupancy. Parallel safe and standalone closest searches were not
exercised; closest fallbacks were.

Dynamic assignment is visible directly: both logical slots of retained batch 52
ran on participant zero. Other retained samples show main and worker overlap.
The largest queue call was 25.546 ms, joined batch 22.563 ms, worker search
22.468 ms and zone rebuild 19.053 ms. No measured queue call reached 50 ms.
These are separate gameplay sessions, not proof of improved speed. A larger
pool cannot split the single expensive search dominating the retained batch.

Lookahead found 46 nonadjacent pairs. Its eligibility counts stop at two and
cannot establish four-request availability. Unsupported heads account for
11,576/14,098 windows (82.11%) and remain serial under the next trial.

## Enabled trial and preserved contracts

`GENERALS_PATH_FOUR_REQUESTS` defaults OFF. CMake requires the joined participant
pool and anchored lookahead; the header derives the Zero Hour flag only when
those prerequisites are active. Enable this option only on experiment/ios-mod-testing.
Disabling it restores the two-result configuration. Keep macos-15, one background
worker plus main, and exactly two reusable participant arenas.

Select the eligible real head and up to three further distinct eligible requests
within eight original queue entries. A window with only two or three eligible
requests still executes those requests. An unsupported head executes serially
first. Exclude duplicates against every already selected ID, not only the head.
Retain nonadjacent results and negative inspected windows as before.

Only the selected logical slots participate in capture, fallback preparation,
dispatch, timing merges and readiness accounting. Idle capacity must never be
dereferenced as a captured request. Every selected job retains its own completed
Path, dependencies, admission windows, publication snapshot and conditional
fallback; arenas remain participant-owned. Main and the single worker dynamically
claim jobs and can reuse scratch for subsequent jobs in the same batch.

The simulation remains frozen until every started callback joins. Validate and
apply each result at its original actual queue/API position. Preserve all existing
prediction/exclusion gates, captured movement inputs, live object/team/terrain and
occupancy checks, lifecycle invalidation, recovery policy, 30,000-record admission
and budget checks after each actual request. Speculative unused searches do not
charge the live budget. A budget stop discards their outputs rather than advancing
extra callbacks. Load/reset, queue-call end and exception cleanup retire every
slot and reset each arena once. Retired slots now also clear locomotor and cell
handles, in addition to the existing object-pointer reset.

A shared capacity definition sizes job storage and profiler arrays. Retained
batch samples carry their actual task count; all four result dispositions can be
resolved. Keep legacy pair tags and logical-slot-zero/one names for comparisons;
`slot2` and `slot3` identify additional slots. `[PATH_POOL_TASK]` maps logical slots
to physical participants. Kernel aggregate metrics remain physical. Add
`[PATH_LOOKAHEAD_SELECTED]` for selected widths zero through four. Selection occurs
before capture/dispatch, and eligible counts are still censored at the configured
capacity; neither distribution establishes full eight-entry availability.
`[PATH_LOOKAHEAD_PARTNER]` continues to count the second selected request's offset,
not the offsets of every additional selected request.

## Storage and performance limits

Controlled 64-bit layouts with profiling enabled:

| Storage | Two requests | Four requests |
| --- | ---: | ---: |
| Participant arena | 2,804,560 bytes | 2,804,560 bytes |
| Result job | 1,520,768 bytes | 1,525,200 bytes |
| Per-job timing object | 9,232 bytes | 13,664 bytes |
| Batch object, excluding arena/fallback allocations | 3,042,120 bytes | 6,101,384 bytes |

With all conditional fallback slots allocated, fixed batch/result storage grows
by 6,118,528 bytes (about 5.84 MiB), excluding unchanged arena allocations and
variable index, corridor, dependency and engine Path storage. Fallback slots are
allocated lazily and retained for reuse. There are no additional participant
arenas or index tables. These host layouts are not iPhone RSS measurements.

Wider speculation can improve balance when eligible work is available, but can
also increase join duration and work later discarded at validation/budget stops.
There is no claimed device speedup. Inspect selected widths, participant counts,
reuse/discard rates, queue/join times, memory and thermal behavior before adding
a second worker. Broader prediction, map-sized dense nodes, higher search limits
and eight-request budget grouping remain separate from this change.

## Verification

See `scripts/qa/test_four_request_path_pool.py`. Fixtures compile production
queue dispatch, hierarchy, ordinary/safe/closest search, Path construction,
optimization, publication and cleanup with controlled surrounding world services.
The wider matrix compares exact paths, optimized links, endpoints, callback order,
queue position, charges, ignored obstacle, tunneling and corridor state against
serial for forty scenarios in both retail modes. A second matrix repeats through
budget-limited calls. Include contiguous/nonadjacent/ring queues, duplicates,
changed inputs/terrain, removed units, lifecycle/world invalidation, requeueing,
nested API use, safe/closest requests and actual failed-primary fallbacks.

Additional focused cases verify widths two/three/four on two arenas, retained
Paths across scratch reset, changed late-slot inputs, actual deletion of third
and fourth objects, fourth-capture lifecycle changes, four separate fallback
results, skipped unstarted work, late callback errors with joined cleanup,
four-to-two retirement, and all four physical/logical timing dispositions.
CMake option checks exercise the actual dependency blocks and default OFF.

All 334 regular cases pass: 313 preceding regressions plus 21 wider-batch cases
(including eight replayed queue cases under the four-request flag). All twenty
C++ integration cases pass TSan and ASan/UBSan, including targeted actual deletion
and fourth-capture cancellation. The CMake case also compiles the production
header's derived flag/capacity/timing section in the two- and four-request modes.
Final Python syntax and diff-whitespace checks pass.

An initial retirement test exposed an unused stale locomotor pointer; retirement
now clears that handle and retained cell handles. The preceding pool cancellation
fixture was updated to inject at the variable-count dispatch call. Local CMake
was installed under /tmp to run the new option checks; the host's existing C++
compiler ran all checks and sanitizers. No SDK or game data was changed.

Native iOS SDK compilation and device gameplay remain required; controlled
fixtures do not prove arbitrary production thread safety or multiplayer/replay
parity.
