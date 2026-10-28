# Matching ordinary corridors and bounded read observations — 28 October 2026

## Motivation and retained policy

The aff9c05 device log shows 80 primary corridor-dependency rejections and five
explicit overflow rejections. All five overflows belong to the expensive tasks
in the three slowest retained pairs; those barriers total 141.919 ms. Rejected
ordinary results fall through to serial recomputation. Address the demonstrated
preparation difference and repeated observation storage, retaining exact validation,
one worker, adjacent pairing, existing search limits and per-request queue budget.

## Ordinary preparation

Under the job's existing main-thread context binding, call findPathWithInputs
instead of jumping straight from clientSafeQuickDoesPathExist to internalFindPath.
This runs the same outer terrain check, corridor clear, hierarchical search and
all-passable fallback used by the authoritative caller. The fine-search entry
still captures a job and returns before executing the fine kernel. Ordinary,
safe and closest worker execution remains unchanged.

The corridor and all coarse search records belong to that job. Preparation does
not copy its charges, lists or corridor into main. The actual caller still runs
its own outer hierarchy and charges its original work before validated fine
reuse. This intentionally performs extra private coarse work without skipping
or billing authoritative work. Early outer rejection still allows the existing
independently captured closest-only fallback. Each job retains its own corridor;
the second prediction cannot overwrite the first one's flags.

Speculative coarse work is included in the existing preparation timer. The
ordinary hierarchy timer excludes this speculative call so the hierarchy row
continues to describe authoritative calls. No full hierarchy or Path construction
is moved onto a worker.

## Recovery boundary

A context-local PreparationScope marks private ordinary preparation and restores
the previous flag on every exit, including exceptions and generation changes.
In parallel builds, guard shared retail-mode transitions, forced cleanup and
preexisting pending cleanup before they can modify global recovery state or
permanent map records. An attempted speculative repair throws a small typed
exception, discards the private batch and leaves the actual caller to perform
normal recovery. It does not disable the worker permanently. Its optional
admission outcome is capture; no per-request stderr message is introduced.

buildHierarchicalPath now owns its temporary coarse Path until it returns,
using the existing engine deletion operation. This releases a partial Path if
private preparation aborts during parent-chain materialization. Outside private
preparation, the original retail/failover behavior remains active. Guards are
compiled only with the parallel feature; the serial/legacy route path retains
its original recovery calls.

## Exact bounded observations

Replace the append-only query/height vectors with BoundedObservationLog. Each
keeps at most 8,192 distinct inputs, a vector in first-observation order and a
fixed generation-stamped index referring to that vector by slot. Index placement
affects lookup only, never candidate ordering or route iteration. The index has
no tombstones and clears stamps on generation rollover.

Query identity includes every PathOccupancy::Input field: destination mode,
x/y/layer/radius, center, transient policy, retail policy, infantry policy and
invalid ID. Mover identity is already per job and checked at result consumption.
Query values compare every Result field. Height keys preserve the exact bytes
of both coordinates, keeping distinct signed-zero/NaN bit patterns separate;
height values retain the original floating-point equality semantics.

Every actual occupancy query and height read still executes against its original
source. These logs do not cache answers used by the search. A repeated identical
input/value consumes no new entry. A repeated key with a different value makes
the log unusable, even if a later observation changes back. A new distinct entry
past the bound also makes it unusable. Allocation/key/comparison failures mark
the log unusable before propagating. Validation checks both the enclosing flag
and each log's state; no partial or conflicting dependency set can authorize reuse.

The existing overflow rejection group now covers unusable observation logs,
including contradictory observations; retained read flags distinguish those from
capacity exhaustion. Main validates each first-seen unique observation using the
same live evaluator, still after cell/corridor checks. This reduces duplicate
validation reads as well as duplicate storage, without dropping distinct inputs.

## Bounded resource cost and device diagnostics

On the local 64-bit fixture ABI, PathfindParallelReads grows from 1,310,872 to
1,441,992 bytes, an increase of 131,120 bytes per phase. Four allocated phases
add 524,480 bytes (about 512 KiB) of index/counter storage. Observation entry
bounds remain 8,192 and there are no map-sized arrays or additional contexts.
Vectors retain capacity across reset as before; fewer unique observations may
require less vector capacity. These sizes are not measured iOS resident memory.

At shutdown, PATH_READS_SLOW prints pair ID, role and primary/fallback phase,
queries, query_observations, heights, height_observations and flags for each
executed phase in the four retained pair samples. Counts are copied only after
join; workers never update shared diagnostic arrays. At most 16 additional lines
are emitted, normally eight for ordinary-only pairs. No per-query logging or
clock is added. All runtime diagnostic reports still require normal exit.

| Flag bit | Meaning |
| --- | --- |
| 1 | Query distinct-entry capacity exhausted |
| 2 | Height distinct-entry capacity exhausted |
| 4 | Same query input produced conflicting replies |
| 8 | Same coordinate key produced conflicting heights |
| 16 | Query log unusable, including failure/conflict/capacity |
| 32 | Height log unusable, including failure/conflict/capacity |

The broad invalid bits accompany capacity/conflict bits; an invalid bit alone
can identify a failed log operation. Zero flags with observations greater than
entries demonstrates duplicate storage removal. It does not prove a speedup.

## Verification and next device test

Seven new cases cover collision-heavy indexes, duplicate-at-capacity behavior,
rollover, conflicts and failures; every query/result field and exact height keys;
the actual live-query adapter reading every time; restricted per-job corridors
with serial route/budget equivalence in both retail modes; recovery abort without
live repair; actual coarse Path cleanup on exception; and a controlled 128-by-128
ordinary failure/fallback case with more than 8,192 query observations, fewer than
8,192 entries and successful primary/fallback reuse matching serial accounting.

The normal fixture's coarse hierarchy is a controlled service, now restricted
explicitly in the new corridor case. The actual coarse search source and its
transitive recovery/parent-walk paths were reviewed; the new ownership test
compiles the real buildHierarchicalPath body. This is not a full-engine replay
or a device bridge/terrain validation result. Existing route, scheduling,
early-fallback, result-diagnostic and lifecycle checks remain enabled.

All 200 local workflow QA cases pass, including all 79 batch cases. All 79 batch
cases pass ThreadSanitizer, and all seven added cases pass ASan/UBSan. The initial
QA run caught recovery guards unnecessarily compiled in the non-parallel parent-
walk fixture; narrowing them to the parallel feature restored its original
legacy recovery path. All seven owned-route cases and the remaining workflow
suites pass after that correction. Diff checks pass.

Native SDK and device validation remain pending. On device, repeat the saved mission, group movement,
tight spaces/bridges and obstacle replanning, then exit normally. Compare slow
pair outcomes and PATH_READS_SLOW entry/observation/flag fields. Corridor changes,
too many distinct dependencies or changed world/policy may still
reject results. Confirm behavior and measured tails before claiming a gain or
expanding dispatch; zone rebuild cost remains separate.

## Native build and first device result

GitHub Actions run [40657488633](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40657488633)
for 40bb42bf9 completed successfully on the configured macos-15 ARM64 runner.
Mac QA, ThreadSanitizer, iOS device compilation, unsigned packaging and artifact
upload all pass. The separate dependency-save step was skipped; dependency-cache
restoration succeeded. No workflow or runner change was needed.

The next supplied generals-stderr.log identifies revision ~40bb42b. It reaches
ScoreScreen and exits with code zero. There is no logged fatal/assertion or
primitive-restart warning. Existing startup/browser stubs and the WAV sample-count
message remain. This is a normal completed device session, not full replay parity
or confirmation of every movement scenario.

| Session measurement | Previous ~aff9c05 | Current ~40bb42b |
| --- | ---: | ---: |
| Completed pairs | 692 | 793 |
| Primary phases reused / executed | 1,260 / 1,355 | 1,524 / 1,548 |
| Primary reuse rate | 92.99% | 98.45% |
| Primary rejections | 95 | 24 |
| Primary corridor-dependency rejections | 80 | 0 |
| Primary explicit overflow rejections | 5 | 0 |
| Fallback reused / executed | 18 / 29 | 21 / 38 |
| Maximum measured queue update | 78.825 ms | 41.895 ms |
| Maximum pair barrier | 61.223 ms | 38.277 ms |
| Queue updates at least 50 ms | 2 | 0 |
| Queue updates at least 20 ms | 14 | 10 |

The new diagnostics directly demonstrate duplicate removal. In retained pair
193, the worker makes 138,969 actual query observations but stores only 3,501
unique entries, with flags zero. Its result is reused. Pair 50's worker stores
3,749 entries from 65,483 observations and also reuses its result. Across the
eight retained primary samples, 318,339 query observations occupy 16,523 entries;
all read flags are zero. The one sample with terrain reads stores 52 heights
from 78 observations, also with flags zero. These aggregate retained counts are
not session-wide read totals or measurements of resident memory.

The earlier log had workers examining 3,227 and 3,666 cells, respectively, whose
results were rejected for overflow. Those examined/record-count signatures recur
in the new retained pairs above, now reused. Matching counters are supporting
evidence, not proof of identical requests, routes or timing conditions.

Outcome accounting balances: 793 pairs contain 1,548 primary phases plus 38
fallback-only phases. The primary results are 1,524 reused and 24 rejected;
fallbacks are 21 reused and 17 rejected. Neither phase has discarded or
validated-unfinished work. The 1,545 reused phases plus 6,809 serial kernels equal
8,354 finalizations. Reuse includes valid no-path answers and is not a count of
successful unit moves. No safe or queued-closest phase executes in this session;
the 38 closest fallbacks do execute.

## Remaining measured work and interpretation

The 24 primary first rejection reasons are permanent admission (17), search kind
(3), world epoch (2) and cell dependencies (2). The 17 fallback first reasons are
closest policy (16) and permanent admission (1). Source checks compare the
permanent-record count captured for the speculative search against the current
count, and the complete captured closest settings against the actual settings.
The log does not identify the changed closest field or prove those guards can be
relaxed. Keep them and investigate capture/consumption differences before altering
validation or expanding dispatch.

The slowest queue update, 41.895 ms, executes six callbacks in three pairs with
no serial kernels. Its longest pair is 38.277 ms and both results are reused;
duplicate serial recomputation is no longer the explanation for that sample.
The second slowest update, 37.194 ms, has zone work and no callbacks or pairs.
The next two updates, 26.990 and 26.897 ms, each contain two ordinary serial
kernels taking about 24.8 ms in total. The admission aggregates cannot identify
why those individual requests did not pair. There are still ordinary serial,
zone-rebuild and blocking-pair costs; additional workers alone do not address all
three.

Preparation now totals 98.741 ms across 11,314 attempts, versus 31.255 ms across
10,765 previously, consistent with the deliberately added private coarse work.
Queue mean is 0.261 ms across 7,509 measured updates, with ten at least 20 ms and
none at least 50/100/500 ms. Timing totals overlap. Workload, run duration and
device scheduling are not controlled between logs, so the lower observed maximum
is not a measured speedup or an explanation of whole-frame/input latency.

Both targeted rejection categories disappear in this session and bounded read
storage behaves as designed. Preserve the change, obtain movement feedback for
this build, and inspect the remaining capture/policy differences before changing
storage architecture, worker count or scheduling. This review changes no runtime
code; counter consistency and documentation diff checks pass.
