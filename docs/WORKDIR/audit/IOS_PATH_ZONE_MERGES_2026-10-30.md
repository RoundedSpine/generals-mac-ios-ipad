# Minimum-label zone merging and frozen occupancy-cache prototype

## Current device trial: occupancy cache enabled

After the zone-only `7bc99194d` device baseline, the experimental iOS workflow now
enables the existing frozen occupancy cache on `experiment/ios-mod-testing`.
Other workflow branches and CMake defaults keep it OFF. The cache implementation,
zone option, runner, worker count, scheduling, limits and live result validation
are unchanged. Native compilation and device cache-performance verification
remain pending for this enablement.
All four cache-specific cases pass again normally and under ThreadSanitizer;
the existing iOS workflow also runs the full regression and race-check suites.

The supplied zone-only device log confirms `[PATH_ZONE_MERGES]` and exits zero.
Retained rebuilds with the same 527-by-521 dimensions and 4,823-zone count change
from 37.041 to 18.776 ms; merging from 18.665 to 7.804 ms, flattening from 7.451
to 0.257 ms and labeling from 9.100 to 8.922 ms. Separate sessions limit the
precision of this comparison. It provides device evidence for the targeted
zone-pass improvement, not a controlled game-wide performance result.

Its worst worker still makes 142,281 occupancy requests (138,968 during fine
search), with 3,550 distinct query identities. Fine work takes 32.867 ms and
cache hits are zero as intended. Primary outcomes are 1,281 reuses, seven
rejections and four unused results; fallback outcomes are 29 reuses and one
world-epoch rejection. No allocation/thread failure or dependency-log overflow
is recorded. This is the baseline for the cache trial.

## Evidence and build scope

The `35bed76` device log exits zero and confirms complete-worker execution.
The slowest retained worker spends 32.578 of 33.169 ms in fine search, with only
0.561 ms in finalization. Of its 142,281 occupancy calls, 138,968 originate in
fine search (97.7%). Thus the earlier controlled optimizer example does not
explain this device spike. Fine expansion repeatedly walks lines toward the goal
as well as its eight neighbors; these walks also update search records and costs.
They cannot simply be skipped when occupancy repeats.

Zone rebuilding is a separate measured cost: 55 rebuilds total 1,380.209 ms,
peaking at 37.041 ms. Equivalence merging takes 735.876 ms and flattening
308.137 ms, together 75.6% of rebuild time. Zone rebuilds with queue ordinal zero
are measured empty-queue calls, not absent work. No queue call reaches 50 ms in
the supplied session. One raw-cell log reaches its existing 8,192-entry bound
and correctly rejects reuse; the bound is unchanged.

The first zone-only build, `7bc99194d`, enabled `GENERALS_FAST_ZONE_MERGES` only on
`experiment/ios-mod-testing`. It explicitly kept `GENERALS_FROZEN_OCCUPANCY_CACHE`
OFF to isolate the zone change. Both options default OFF elsewhere; the cache
option requires complete-worker mode. No worker count, search limit, queue
scheduling, fine line-walk behavior or gameplay setting changes.

## Zone implementation and equivalence

The original `resolveZones()` rewrites a whole table to join each pair of
components. Global rebuilding performs many such joins. The new
`MinimumZoneEquivalence` uses path compression and links the larger root to the
smaller root, using the already allocated equivalence table as parent storage.
It adds no scratch allocation. Each table starts as identity; all six tables
are fully materialized before later code consumes them, retaining the same
minimum labels, ordinary table layout and reserved zero entry.

Cell zone assignment, terrain/fence predicates, bridge connections, block work,
allocation and iteration order remain unchanged. The initial labeling pass still
uses the original merger. Only global equivalence merging changes representation
temporarily; no queries or simulation callbacks occur in that interval.

Flattening preserves its original first transform. Its second pass uses compressed
merging only when the transformed table already contains canonical minimum labels.
The check is read-only on failure. Noncanonical transformed inputs retain the
original second pass, preserving its intermediate-table semantics. This guard is
intentional: replacing arbitrary intermediate arrays with a disjoint-set tree
would assume properties the old flattening code does not promise.

`[PATH_ZONE_MERGES] enabled strategy=minimum_root storage=existing_tables
flatten=canonical_only` reports enablement at the first profiled batch. Existing
zone-pass timings and retained zone rows remain available for native comparison.

## Bounded occupancy cache implementation

The optional prototype looks up results in the existing dependency-log index;
there is no second hash table, duplicated query storage or increased entry bound.
The key includes the entire query identity already used for result validation:
destination/movement kind, coordinates/layer, radius/centering, transient policy,
retail/infantry policy and invalid-ID sentinel. All five returned result fields
are reused, not just the allowed flag.

Reuse additionally requires an executing complete request, its bound job, and
exact mover identity. The joined world and mover/AI inputs remain frozen during
that execution. Requests, primary/fallback jobs and their logs stay separate.
Search generation changes do not clear a same-request cache, since those queries
read permanent occupancy, not open/closed lists or costs. Request reset clears it.
Different movers, unbound callers and invalid/full/conflicting logs evaluate live.

Main-thread result validation still directly calls the live evaluator for every
distinct stored query. It never uses the cache. Changed world/object/cell inputs
still reject reuse and invoke the existing serial path. Raw cell dependencies,
allocation admission, topology/lifecycle checks and independent fallback
validation remain unchanged. The prototype does not skip any line-walk callback,
cost update, list operation or search-record allocation.

With the option ON, `[PATH_OCCUPANCY_CACHE]` reports the frozen scope and live
validation. `[PATH_TASK_PROFILE] cache_hits` counts cached returns; `query_calls`,
`query_observations` and query-stage/sample counts then describe actual live
evaluations only. Add hits to live calls for total query requests. With the
option OFF, hits are zero and the prior profiler semantics are unchanged.

## Controlled host measurements

Benchmarks compile production methods with `-O2`, discard one warm-up and retain
nine trials. Services remain controlled fixtures; results are neither device
measurements nor whole-engine replay/performance guarantees.

| Workload | Original median | Optimized median | Output/work evidence |
| --- | ---: | ---: | --- |
| 527-by-521 zone rebuild, 4,691 zones | 32.868 ms | 2.965 ms | Matching zone count and table checksum |
| 200 complete ordinary pairs, open layout | 9.824 ms | 9.307 ms | Live evaluations 18,400 to 10,800; 7,600 hits |
| 200 complete ordinary pairs, winding layout | 33.258 ms | 27.443 ms | Live evaluations 364,000 to 46,400; 317,600 hits |

The zone fixture executes actual label/merge/flatten code and terrain predicates;
per-block/layer services are controlled substitutes. Its median improvement is
about elevenfold. The complete-API fixture executes production hierarchy, fine
search, engine Path methods, optimization and live validation with controlled
object/terrain/allocation services. The first cache run gains about 5% open and
17% winding, despite far larger reductions in evaluation count: other fine-search
work and validation remain.

Reversing variant order gives zone medians 32.027 to 2.946 ms with the same output.
The winding cache case improves from 33.326 to 26.932 ms (19%), but the open case
regresses from 9.162 to 9.968 ms (9%). Open-layout benefit is therefore unproven;
do not report the first 5% gain as a stable improvement. The repeat confirms the
zone result and winding benefit on this host, while supporting the decision to
keep caching OFF in the first zone-only IPA. These measurements justify a device zone trial
and continued cache evaluation, not a matching FPS or hitch reduction claim.

Reproduce with `python3 scripts/qa/test_zone_merges.py --benchmark` and
`python3 scripts/qa/test_frozen_occupancy_cache.py --benchmark`. Add `--reverse`
to reverse variant order. The fixture counts and output equivalence are more
portable than these host timings.

## Verification and device follow-up

New zone cases compare randomized component merges against original flat tables,
exhaust 14,400 pairs of descending flattening inputs (including noncanonical
cases), and compare all cell/layer/table outputs across 128 production rebuilds
with controlled bridges, fences and terrain layouts. Outputs match byte for byte
with optimization OFF/ON, including a profiled variant.

Cache cases exercise collisions, capacity, conflicts and generation rollover;
compare complete ordinary/safe/closest/fallback paths, optimized links,
destinations and budget charges with cache OFF/ON and timing OFF; verify request
reset and mover/scope restrictions; and change a live unit relationship after
joining to prove main rejects stale cached results. The relationship test first
asserts that the recorded query result actually changes.

All 258 regular regressions pass across 23 workflow scripts. The seven new zone
and cache cases pass ThreadSanitizer and ASan/UBSan. After expanding the route
matrix to include winding maps, that case passes both sanitizers again. The new
cases are part of the regular and TSan iOS workflow checks. Initial fixture work
needed corrected indentation, an array/index variable name and valid occupancy
setter calls. The first stale-result test selected an unobserved cell; move it
onto the queried route and assert a changed query before testing rejection.
An initially misplaced guarded cache block failed compilation and was moved to
the intended evaluator before successful tests. No new runtime failure or race
report remains in the executed checks. Native SDK compilation and device testing
were pending at that commit; the zone-only device follow-up is recorded above.

For the cache-enabled trial, use the same save/orders and exit normally. Confirm
`[PATH_OCCUPANCY_CACHE] enabled` and inspect the same expensive route, ordinary
movement, bridges, terrain transitions and blocked destinations. Compare complete
pair/task wall time and fine/finalization time, not just evaluation counts.
Add `cache_hits` to live `query_calls` to account for total query requests; the
prior 142,281-request task can remain equally large while live evaluations fall.
Query-stage/sample rows count cache misses only. Main validation remains live,
so monitor rejection/overflow counts as well. The cache does not eliminate
line-walk state updates, lookup/list work, serial searches or all possible spikes.
