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
