# Compact private pathfinding nodes — 29 October 2026

## Change and boundaries

On `experiment/ios-mod-testing`, replace each private permanent-record-shaped
record plus separately stamped search state with one `PathfindSearchNode`.
It embeds links, parent, stable insertion sequence, heap index, costs, flags and
allocation credit, followed by its cell and coordinates. `search()` returns the
embedded base state; there is no state-pointer lookup. Private nodes cannot be
passed as permanent `PathfindCellInfo` records.

Permanent records retain occupancy IDs, obstacle metadata and their free list.
Remove their unused private-state pointer and private admission flag. The enabled
context no longer inherits the separate 30,000-entry stamped state arena. Its
bounded keyed pool already owns generation invalidation and initializes each
complete node on acquisition. The generic stamped arena and disabled legacy
path remain available; the compact context does not allocate that arena.

Keep the existing slot allocation/LIFO reuse order, 30,000-node capacity,
permanent/transient admission predicates, generation rollover, direct index and
keyed fallback. Release still clears search links before recycling. Each context
owns its nodes and lists, including retained primary/fallback outcomes. Preserve
64-bit tie ordering, retail list conversion, search/pruning limits, request/result
validation, one worker plus main, adjacent pairing and per-request scheduling.

This adopts the reference's search-only node separation, not its entire storage
policy. Reimagined directly indexes a map-sized full-node array, uses a 32-bit
sequence and per-node stamp, and normally permits all map cells independently of
permanent occupancy. Our index still resolves a bounded pool slot; generation
stamps live in allocator/index metadata. No dense map-sized node allocation or
capacity-policy change is included. Full hierarchy/Path completion on workers and
wider dispatch remain separate work.

## Layout evidence

Measured with the actual extracted declarations on this 64-bit Linux host. The
test reconstruction of the preceding split representation has the same sizes
as the saved pre-change source. These are object sizes, not resident memory.

| Storage | Previous split layout | Compact layout |
| --- | ---: | ---: |
| Map cell | 24 bytes | 24 bytes |
| Permanent cell record | 56 bytes | 48 bytes |
| Private record plus stamped state entry | 56 + 56 = 112 bytes | 64 bytes complete |
| Embedded state portion | 48 bytes in separate entry | 48 bytes inside the node |
| Fixed search context, excluding dynamic backing | 4,244,504 bytes | 2,804,496 bytes |

The fixed saving is 1,440,008 bytes, about 1.37 MiB per allocated context, and
240,000 bytes for a full 30,000-record permanent pool. Main plus four retained
phase contexts would save about 7.1 MiB including that pool, **if all five
contexts are allocated**. This is not a measured reduction in iPhone RSS.
Heap vectors, observation logs, corridors and index backing remain separate;
the direct index is still capped at 1 MiB/context.

When timing instrumentation is enabled, the first executed batch adds one
`[PATH_SEARCH_STORAGE]` row with `node_bytes`, `permanent_bytes`, `context_bytes`,
`capacity` and `max_index_cells`. It measures the native compiler's layout once,
without per-cell logging or clocks. It does not report live allocations or RSS.

## Verification

- All 235 workflow regression cases pass locally, including all 110 batch cases.
- The full 110-case ThreadSanitizer batch run passes 109 cases; the 80-world
  closest/mixed matrix exceeds its default 10-second process deadline. That case
  passes alone. Give only that larger matrix a bounded 30-second deadline, then
  rerun it and both new compact differential cases under TSan: all three pass.
  No race report was produced. This is not a claim that the original full run
  passed without interruption.
- Seven targeted ASan/UBSan cases pass: compact route/work and large closest
  comparisons, compact binding/layout, randomized pool churn, recycling,
  occupancy isolation and independent/capacity ownership.
- Compare preceding split versus compact layouts through ordinary, safe,
  queued closest and early fallback searches, both retail modes, movement
  center/radius settings, obstacles and ordered production goal updates.
  Routes, targets, reuse/rejection, charged work and serial/both participants'
  expansion traces match. Large closest cases preserve conditional over-2,000
  pruning and routes. Existing historical route hashes also pass.
- New randomized churn covers 600 generations with a forced 8-bit rollover,
  release/reacquisition, occupancy changes, frozen admission, live-node costs,
  insertion sequences and allocation-credit equivalence. Existing tests cover
  physical capacity, failed optional index growth, uncovered cells, independent
  contexts and cleanup/lifecycle behavior.
- Saved pre-change generated fixtures, the test-only split reconstruction and
  compact fixtures also produce identical small and large traces. Controlled
  service fixtures are not a whole-engine replay or a proof of all race freedom.

During implementation, stale harness assumptions about the removed state pointer
and comparisons between now-distinct pointer types were corrected. The new
randomized fixture initially omitted the required admission binding and could
exhaust its deliberately tiny permanent pool; it now binds the context and keeps
occupancy within that fixture's bound. Neither required weakening production
guards.

Native iOS compilation and device verification are pending when this change is
committed. The preceding successful native/device runtime is `26be01d4a`.

## Performance evidence and limits

Memory reduction is established by the layout checks. Faster execution is not.
The optional benchmark now supports `--storage` (split versus compact getter
groups, both indexed) and `--search` (complete closest API calls using controlled
terrain/Path services). Both check equivalent output/work; neither sets a CI
timing threshold. Existing default indexed-versus-keyed lookup mode remains.

Pinned host getter run, 8,192 records, 5,000,000 groups, 11 repeats, `-O2 -DNDEBUG`:

| Getter mix | Split median | Compact median |
| --- | ---: | ---: |
| Sequential | 14.625 ns/group | 16.166 ns/group |
| Random | 14.633 ns/group | 15.743 ns/group |

Compact is about 10.5% and 7.6% slower in those mixes. Removing an indirection and
shrinking the total footprint do not guarantee that a particular access mix or
compiler layout runs faster.

Whole closest API host results are mixed too. An exploratory nine-repeat run
using the saved actual preceding fixture gave split/compact medians of
73.974/69.242, 97.955/70.266, 78.069/70.347 and 73.653/70.733 ms for the four
retail/hierarchy settings. A subsequent three-repeat run through the checked-in
benchmark gave 74.231/70.001, 62.430/68.821, 57.874/79.458 and 57.771/68.852 ms.
All compared paths and work fingerprints match. Other QA ran during these
measurements; CPU affinity is not exclusive CPU ownership. The inconsistent
direction and baseline variation prevent a causal speed ranking. Do not select
only the favorable run or extrapolate either set to device FPS.

Reproduce with a C++17 compiler; optional CPU pinning is host-specific:

```sh
python3 scripts/qa/benchmark_path_index.py --storage --iterations 5000000 --repeats 11
python3 scripts/qa/benchmark_path_index.py --search --repeats 9
```

Test the new IPA against the same heavier saved game and orders as the preceding
IPA. Compare responsiveness, routes, closest work counts, queue/kernel times,
balanced reuse/finalization and the native layout row. Device timing and memory
measurements are still needed before claiming a performance improvement or
parity with Reimagined. Keep current limits and scheduling throughout.
