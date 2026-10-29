# Bounded direct record indexing and closest work — 29 October 2026

## Scope and relationship to Reimagined

The reference's getters resolve a cell's search index directly into its private
node array. Our getters previously resolved every coordinate, cost and parent
through a pointer-keyed record pool before reaching already-bound state. The
latest device session contains 36–54 ms unpaired closest kernels, making serial
lookup cost relevant as well as parallel throughput.

Implement direct cell-ID to existing-record-slot lookup. Keep the current keyed
allocator, stable record addresses, separate state arena, 30,000-record capacity,
permanent/transient credits, exact admission windows, heap tie order, dependency
validation, queue budget, two-request dispatch and worker count. This is the
lookup stage, not Reimagined's dense search-only node layout or map-sized node
allowance. No renderer, assets, runner or workflow policy changes.

## Cell identities and lookup validity

Only real ground, bridge and wall allocations are registered. Each range receives
distinct monotonically assigned IDs; overlapping layer coordinates cannot alias.
Unregistered standalone cells keep an invalid ID and use the original keyed path.
PathfindCell::reset preserves its identity while clearing occupancy/terrain state.
Registration occurs after array construction, before classification/search.

Pathfinder::reset first invalidates joined predictions, then deletes ground and
layer cells, resets the ID registry and invalidates main search state. New map
IDs can then start at zero. Private contexts are independently reset through the
existing batch lifecycle. Cell IDs are runtime metadata, not serialized world
inputs or new validation fields. No worker writes the registry; map changes and
registration remain outside frozen search execution.

Each context owns BoundedRecordIndex. A packed 32-bit entry holds a 16-bit
generation and 16-bit stable record slot; the existing 30,000 slots fit without
changing allocator capacity. A covered cell is resolved by one index entry and
atSlot, including a direct negative lookup for unallocated cells. New allocations
still use the keyed pool and its existing order/free list, then publish their
slot after record/state initialization. Release invalidates the index entry
before returning the keyed slot. Reuse resets the record/state as before.

Every context beginSearch resets the keyed generation and index generation
together, before preparing the index. Ordinary resets are constant-time; 16-bit
index-generation wrap clears all retained entries before reusing generation one.
Index growth occurs only at these empty-generation boundaries, never while a
record could be hidden by an empty newly covered entry. Existing speculative
setup prepares each primary/fallback context on main before worker dispatch;
the fine loops do not grow the index. releaseStorage invalidates without growing
the table, then releases its backing storage.

## Memory and failure boundary

The table covers at most 262,144 IDs per context, using exactly four backing-array
bytes per covered ID: at most 1 MiB retained per context. The main plus four
retained phase contexts can therefore retain at most 5 MiB of new index arrays.
A growing context briefly owns its old and replacement arrays, adding less than
one further MiB to that aggregate peak. This excludes allocator bookkeeping and
all pre-existing record/state/read-log memory; it is not an engine RSS estimate.

| Situation | Behavior |
| --- | --- |
| Registered ID within prepared coverage | Direct slot lookup; no key probe for a getter |
| Unregistered or ID beyond the bounded prefix | Original keyed lookup |
| New registered range after a context's preparation | Uncovered IDs use keyed lookup until the next empty-generation preparation |
| Optional index allocation fails | Keep the valid bounded prefix for the new generation; uncovered cells continue through the keyed pool |
| Physical record or admission capacity exhausted | Original failure behavior; the index creates no additional records |
| ID registry exhausted | New cells remain unindexed and retain the keyed path |

The cache does not evict live nodes. It does not require all registered cells to
fit, unlike allocating a full map-sized node array. It also leaves some hashing
in allocation/release and keeps the original record/state storage. Full compact
nodes, different dense/sparse lookup policies and broader dispatch remain separate
work. Default construction/copying of map cells is not a supported way to clone
registered identities or permanent records; production maps allocate/register
their own arrays as before.

On the local 64-bit fixture ABI, old/new cell, record and state sizes remain
24/56/48 bytes. Context fixed storage changes from 4,244,488 to 4,244,504 bytes;
the index backing array is additional. At 8,192 registered cells that array uses
32,768 bytes. These are controlled host layout measurements, not native iOS
allocation or device-memory measurements.

## Candidate/pruning measurements in the next build

The optional existing GENERALS_PATH_TIMING option now retains at most four serial
closest kernels as PATH_CLOSEST_SLOW. It uses the existing serial timer: two clock
reads per enabled kernel, no per-cell clocks. Speculative worker/caller loops
only update their local sample; they do not publish to the shared retained array.
The samples contain scalar counters/coordinates only, with no engine pointers,
requests or unbounded history. Loop counters are diagnostic overhead; they are
not a zero-cost or device-performance guarantee.

| Field | Meaning |
| --- | --- |
| queue / ms | Existing queue ordinal (zero outside one) and fine-kernel wall time |
| start_x/y, goal_x/y, radius, cost_multiplier | Initial fine-search settings; not an object or AI callback trace |
| flags | Bits: 1 hierarchy available, 2 started stuck, 4 initial tunneling, 8 blocked, 16 goal on obstacle |
| outcome | 0 interrupted before loop completion, 1 exact goal, 2 closest candidate, 3 exhausted without a candidate |
| pops | Open-list removals |
| destination_checks / candidates / improvements | Actual destination calls; eligible closest candidates; strict score improvements |
| far_tests / far_prunes | Outer far-distance condition reached; those entries actually pruned |
| no_hierarchy / over_2000 / near_goal | Individual true pruning reasons inside the outer condition; multiple can describe one entry |
| expansions | Calls to neighbor examination after layer checking |
| examined | Existing accumulated neighbor-work count returned by the loop; not pops or queue charge |
| records / index_bytes | Records still live before main completion and current index-array bytes; not peak nodes or process memory |

Destination wrappers preserve the original short-circuit call order. Finishing
copies counters without changing returned cells/count/success. An interrupted
sample can contain partial counts and default final-record fields. Serial loop
timings exclude hierarchy and Path completion as before. The row does not yet
identify direct approach versus the caller's closest fallback; request-source
classification remains a separate possible extension.

## Verification and local measurements

Three new record/index tests cover randomized equivalence against the keyed pool,
slot recycling, 8-bit test-generation rollover, the 1 MiB bound, failed growth,
registry overflow/reset, distinct layer IDs, identity-preserving cell reset,
permanent/transient credit, unregistered and capped-prefix fallback, and storage
release. Four new batch cases compare indexed versus forced-keyed lookup through
ordinary/safe/queued closest/early fallback, both retail modes, radii, center modes,
obstacles and inter-request goal changes. Routes, destinations, blocking flags,
expansion order, reuse/rejections and budgets match. Getter probes verify zero
keyed finds for registered cells and retained keyed finds for unregistered ones.

Large closest cases compare independent existing far/over-2000 observations with
the new counters, exercise conditional pruning, and show speculative tasks do not
publish serial samples. A controlled clock verifies top-four retention and no
additional timer reads. The shared production fixtures were updated for the new
header/helper; early fixture-only failures were missing includes or a helper
definition before the real cell type, then corrected without changing runtime
semantics.

All 232 local workflow regression cases pass, including all 108 batch cases.
All 108 batch cases pass ThreadSanitizer and all seven added cases pass ASan/UBSan.
Diff checks pass. Native iOS SDK and device validation remain pending. Controlled
services do not establish full-engine replay parity, all lifecycle safety or
device speedup.

Run the reproducible host probe with:

```bash
python3 scripts/qa/benchmark_path_index.py --records 8192 --iterations 5000000 --repeats 11
```

The script compiles production getters at -O2 -DNDEBUG, forcing only findRecord
back to keyed lookup for the baseline, preserving allocation/setup and checking
equal returned-value checksums. One group reads x, y, cost-so-far and total cost.
It reports medians and ranges without a pass/fail performance threshold.

The initial unpinned run under concurrent QA was noisy, including a slower random
indexed median. A follow-up pinned to one available host CPU produced:

| Getter access pattern | Keyed median, ns/group | Indexed median, ns/group | Keyed / indexed |
| --- | ---: | ---: | ---: |
| Sequential | 18.386 | 15.349 | 1.20 |
| Random | 18.673 | 14.241 | 1.31 |

This supports pursuing the lookup adaptation, not a universal speed ranking.
The host, compiler, cache residency, scheduling and artificial getter mix differ
from an iPhone path search. Larger full-search timings and device results can
still differ. The benchmark is optional and does not run as a timing-sensitive
CI test. The pre-change generated fixture was also retained locally for layout
comparison; committed tests do not depend on that temporary snapshot.

## Device follow-up

Repeat the same saved mission and crowded/unreachable destinations, then exit
normally. Check PATH_CLOSEST_SLOW for no-candidate searches versus far pruning,
retained records/index size and queue correlation, together with balanced reuse
and finalization totals. Compare serial-kernel tails with the earlier 54.110,
38.832 and 36.886 ms cases without treating unmatched sessions as a controlled
benchmark. Use the work counts to guide compact-node and lookup improvements;
retain current allocation limits and scheduling.
