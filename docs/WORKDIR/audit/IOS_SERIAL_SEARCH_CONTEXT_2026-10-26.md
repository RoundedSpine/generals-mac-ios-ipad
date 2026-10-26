# Bounded single-threaded search context experiment

Date: 26 October 2026. Branch: `experiment/ios-mod-testing`.

## Scope

The user authorized the serial search-context/generation-stamp stage after the
heap, narrow hierarchical change and verified-quad experiments. This implements
an adapted architecture, not the complete Reimagined rewrite. Reimagined 1.0.0 by
dement123 supplied the separation/generation concept reviewed earlier.

`GENERALS_SEARCH_CONTEXT` defaults OFF. The experimental IPA workflow enables it;
AIPathfind activates the feature only for RTS_ZEROHOUR, leaving base Generals on
local record state. No workers, prefetch, new node limit or request grouping is
added. The 30,000-record allocation limit and 5,000-cell per-request frame budgeting
remain. This does not claim original retail replay equivalence.

## Storage and ownership

Permanent PathfindCellInfo fields retain coordinates, owner cell, occupancy IDs,
obstacle ID and obstacle flags. Search-only parent/open/closed links, costs, heap
index/insertion sequence, open/closed membership and ally-blocking flag move to
PathfindSearchState. Each existing pool record has a stable slot ID initialized
when the pool is allocated. The single context owns exactly 30,000 stamped slots;
it does not grow with map dimensions or allocate one context per worker.

The pool's free list has a separate permanent link in enabled mode. It must not
reuse a search-parent field that can be reset on generation changes. New record
allocation resets its temporary state even if the slot was active earlier in the
same generation; occupancy initialization and pool exhaustion behavior remain in
the original allocator. When disabled, search state stays within the record and
the legacy free-list/parent alias is retained for comparison.

A search-state access initializes only a stale slot. beginSearch increments the
generation; an unsigned generation rollover invalidates all stamps before returning
to generation 1. There are no timing-dependent decisions or additional threads.
The context is single-thread-owned and is not presented as worker-ready.

On the local 64-bit harness: record 56 bytes, search state 48 bytes, stamped arena
1,680,008 bytes for 30,000 slots. Record pool plus arena is about 3.2 MiB, excluding
heap storage, versus about 2.3 MiB for the previous 80-byte heap records. This is
roughly 0.9 MiB additional fixed storage; exact iOS layout is not measured here.

## Search boundaries and cleanup

All nine existing empty-list search boundaries begin a generation: internal fine,
ground, hierarchical, cost, closest, move-away, patch, attack and safe search.
Any remaining lists are cleaned using their current state before the generation
changes. Closest-path's coarse search is followed by another boundary before its
fine search allocates/initializes nodes. Zone passable/corridor flags, tunneling,
ignored-obstacle state and scheduling remain with Pathfinder and retain their
existing explicit behavior; only node bookkeeping is isolated in this stage.

The original per-cell release rules still decide when persistent records can be
returned. Generation stamps invalidate temporary fields, not allocations: they
must not silently discard occupancy, skip required releases or reset heap nodes
while a queue still contains them. Heap sorting/reinsertion and closed-list cleanup
use the same search accessors. Path snapshots are separate from these transient
records; this feature nevertheless can change routes by eliminating stale state.

## Verification

Compiled actual context and cell allocator methods with controlled stand-ins:
fresh/lazy reset, forced small-generation rollover, persistent occupancy/obstacle
preservation, parent/cost/heap reset, free-list survival, 30,000-slot exhaustion,
recycling, repeated pool/map initialization, disabled free-link behavior and actual
search-boundary cleanup ordering. Compared route/expansion fingerprints on 100
synthetic grids with the feature enabled and disabled. The heap/list production
method suite now also runs retail/fixed configurations with the context enabled.
Sanitizers check the context/allocator/boundary fixtures. These are not full-engine
campaign/replay or concurrency tests.

Full iOS compilation runs on GitHub's macOS runner. On the phone compare normal
movement, blocked destinations, long paths, groups near buildings, ramps/cliffs,
bridges, mixed unit sizes, allied congestion and repeated map/save loads. Test the
same mission more than once: this branch still uses a fresh DXVK cache per build,
so first-run shader compilation can confound performance impressions. Report any
new stalls, early stops, poor detours or crashes. No speedup or replay guarantee
is claimed until real engine/device evidence supports it.


## Follow-up: serial bookkeeping ownership

The next stage extends PathfindSearchContext to own its node arena, open/closed
lists, tunneling state, ignored obstacle, frame allocation counter and hierarchical
corridor flags. Pathfinder uses `searchState()` for bookkeeping. With the experiment
disabled, it uses local PathfindSearchBookkeeping and legacy ZoneBlock flags.

Corridor storage is one byte per hierarchical block. Map allocation initializes
all blocks passable, matching ZoneBlock construction. Map reset releases storage.
Node generation advances intentionally leave the corridor and control state intact:
coarse search constructs the corridor for the fine search, and callers establish
ignored obstacles before entering search boundaries. Frame accounting resets only
where the existing queue loop reset it, never at an individual search boundary.
Snapshot field sizes and transfer order are unchanged.

Lists now live with a static context, so their heap capacity and corridor capacity
are explicitly released in Pathfinder destruction before the game allocator shuts
down. Recreating the engine can reuse the empty context. Node storage remains fixed
at 30,000 slots; the small list/vector owners and per-block byte array are added,
without allocating map-sized node arrays or worker contexts.

### Remaining boundary

This stage **does not complete worker readiness**. Search records still attach to
shared cell `m_info` and use the existing static record pool. Retained occupancy
records compete for that pool just as before. Replacing the pool requires a separate
cell-to-search-node lookup and an explicit allocation/failure equivalence policy;
it is not safe to silently substitute independent unlimited worker arenas. Debug
paths, movement side effects and live object/terrain reads also remain serial.
See [the prefetch audit](IOS_PATHFIND_PREFETCH_AUDIT_2026-10-26.md).

### Regression coverage

The expanded ten-test search-context suite exercises production arena allocation,
generation and rollover, actual region-corridor methods in both modes with the
same randomized operation stream, map resizing/reset, independent state, heap
storage shutdown/reuse and the production queue loop. The queue fixture checks
head wrapping, missing objects/AI, zone-update deferral, the unchanged 5,000-cell
per-request budget and nested generation changes. Other suites retain stable
heap/list ordering, retail threshold fallback and hierarchical edge allocation
checks. These fixtures are not full-engine replay or device performance tests.

Validation result: all 57 workflow QA tests passed locally. All ten search-context
tests also passed with AddressSanitizer and UndefinedBehaviorSanitizer. Full iOS
SDK compilation and device/replay validation remain pending for this stage.


## Follow-up: independent bounded search-record allocation

Experimental searches now obtain records from a context-owned BoundedKeyedPool.
The permanent PathfindCellInfo pool continues to hold unit goals, positions,
aircraft goals and obstacle metadata. Search entry points use allocateSearchInfo,
hasSearchInfo and releaseSearchInfo; list, parent and cost operations use
searchInfo. The default mode routes these helpers to the legacy cell-owned info.

### Ownership and lookup

The fixed lookup has 65,536 buckets for 30,000 stable-address record slots, uses
linear probing and tombstones, and resets bucket validity by generation. Buckets
are never iterated to choose search work: hash placement and cell addresses do not
define path order. Recycling is explicit, does not allocate per-node heap objects,
and never grows past capacity. Generation rollover clears bucket stamps. Values
must be trivially destructible because invalidation does not destroy each value.

Each search record stores a pointer to its owning node arena. Two contexts can
therefore allocate the same cell key without sharing cost, parent or open state.
Permanent records have no search owner; treating them as search scratch asserts.
Cell searchInfo lazily materializes shadow scratch for a permanent record, preserving
the old distinction between a cell that already had info and one needing new
admission. This also avoids counting occupied cells as newly allocated cells in
existing search-local counters. No search allocation writes the map's m_info or the
permanent free list. Permanent record allocation does not reset search arena slots.

### Capacity and lifetime policy

- The permanent pool stays at 30,000 records; the independent search pool also has
  exactly 30,000 record slots.
- A search cell with permanent metadata consumes a shadow record but no additional
  transient admission credit. Other cells consume transient credit.
- At admission, permanent records in use plus charged transient cells must be below
  30,000 before another transient cell is admitted. Failure returns null through
  the existing caller checks. Workers and larger limits are not enabled.
- Search cleanup releases unlinked records for unoccupied cells and preserves
  permanent occupancy metadata. Records retained for occupied/obstacle cells are
  private scratch and disappear at the next search generation.
- A generation boundary discards any scratch not reached by normal list cleanup;
  it preserves corridor/control state. Map reset additionally invalidates lookup
  keys before a new map can reuse cell addresses. Existing list cleanup still
  contributes to frame accounting before generation changes.

This is an explicit new bounded lifetime policy, **not a claim of identical legacy
pool-exhaustion behavior**. The former shared allocator could retain orphaned
records across searches. Reclaiming them can admit a later search that formerly
failed. Exact replay CRC/failure equivalence under exhaustion remains unverified.
Admission reads the serial permanent-use counter; a future worker kernel must
capture/freeze this input with the other request inputs.

### Memory and validation scope

A local 64-bit compiled fixture measured a 72-byte record, a 3,044,304-byte keyed
pool and a 4,724,472-byte complete context. Combined with the 2,160,000-byte
permanent record array, fixed record/context storage is approximately 6.57 MiB,
about 3.36 MiB more than the previous stage. Heap queue capacity, corridor bytes
and engine overhead are additional; exact iOS allocation/resident usage is unmeasured.
The first implementation reuses the existing record type rather than introducing
another node hierarchy. Splitting unused metadata from private records can be
considered after this lifetime change is validated.

The new seven-test suite exercises forced hash collisions and churn against an
independent map oracle, full capacity, generation rollover, production cell/list
allocation and cleanup, permanent reuse without search resets, full occupied-pool
shadow admission, independent record owners and route/expansion hashes across 50
synthetic obstacle grids in enabled and disabled modes. This is not a full engine
replay or device performance test.

### Remaining before workers

Cell search helpers still select the main context, and search setup/route processing
still reach live object, locomotor, team, terrain and debug/UI services. The next
stage is an explicit immutable request/result boundary and serial comparison of
speculative results. Do not enable worker searches merely because node storage is
now independent. No runtime prefetch, worker scheduling or eight-request batching
is added here.

Validation result for independent allocation: all 64 workflow QA tests passed
locally; all 17 context/allocation tests passed AddressSanitizer and
UndefinedBehaviorSanitizer. Actionlint and diff checks passed. Full iOS SDK
compilation, device movement/performance and replay checks remain pending.


## Follow-up: owned unoptimized route output — 2026-10-27

The serial experiment now builds OwnedPathRoute value data during the parent-cell
walk and materializes new engine PathNodes only after that walk returns. A shared
prependRouteCells template preserves the previous algorithm for both immediate
(default) and deferred (experimental) sinks. This includes corridor marking,
parent clearing and the retail failover branch. The result survives those cells
being cleaned because its payload contains copied coordinates/layers/flags only.

Points are appended internally in prepend order, then applied in the same order,
preserving the final start-to-goal node chain. New points default to canOptimize
false exactly like PathNode; the walk sets intermediate flags and preserves the
special exact start-position behavior. Existing patched-path tails are not copied
or reconstructed: only their head metadata is seeded into the value collector,
then applied back to that same path before new nodes are prepended. Ally blocking
is applied when encountered without clearing a pre-existing blocked flag.

The buffer admits at most PATHFIND_RECORD_CAPACITY + 1 new points, allowing the
existing search records plus an exact source position. This adds temporary vector
storage and an additional materialization pass proportional to route length; it is
an ownership refactor, not a measured speedup. No additional path searches or
background work are performed. Exact iOS memory/performance remains unmeasured.

This is the **unoptimized output side** of a request/result boundary. Terrain
height lookup, cell traversal, corridor/parent bookkeeping and legacy failover
still execute serially. Input object/locomotor/team/terrain state has not been
snapshotted; engine Path allocation and optimization are still part of the serial
caller. Existing-tail capture also remains on that caller. Worker execution and
prefetch remain disabled, and stale-result validation is still future work.

Validation: all 70 workflow QA tests passed locally. Six new compiled tests compare
the production walk with both sinks and assert known results for normal/short,
bridge, cliff, ally and existing-tail cases, retail failover, result lifetime,
copy ownership and bounded failure. They also confirm no engine node is allocated
inside the deferred parent walk. All six pass ASan/UBSan. These are controlled
fixtures, not full-engine replays or device gameplay/performance tests.
