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
