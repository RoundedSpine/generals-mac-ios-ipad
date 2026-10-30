# Complete-search participant context reuse — 30 October 2026

## Scope

`GENERALS_REUSE_PATH_CONTEXTS` defaults OFF and requires complete-worker mode.
The iOS workflow enables it only on `experiment/ios-mod-testing`. Each of the
two fixed participants retains one owned search arena; its sequential closest
fallback borrows that arena. The main serial context stays separate. Keep one
worker plus main, adjacent pairs, the existing allocation allowance, per-request
queue budget and all live result validation.

Reimagined uses a thread-local context across complete jobs and fallback phases.
This adapts that reuse principle to our existing fixed participant slots and
Pathfinder lifetime, without adding a cross-Pathfinder thread-local pool or
adopting the reference's wider dispatcher and different capacity policy.

## Ownership and publication

Each result retains its own completed engine Path, request metadata, admission
window, dependency logs, frozen occupancy cache and timing. Snapshot the search
began/corridor-written flags, charged count, tunneling and ignored obstacle before
reusing scratch. Store the completed corridor in the result too. Main publishes
those saved values after validation; it never reads the recycled arena to apply
a completed result. An early-null API must not publish a synthetic search reset.

Primary and fallback keep independent caches and validation records even though
they share scratch. A failed ordinary search and its closest fallback may both
be consumed, each with its own charge and corridor. Completed Paths own PathNodes
and do not retain a search-record parent chain. Borrowed-result reset does not
advance or clear the owner's arena. Member destruction releases the fallback,
completed Paths and logs before destroying the arena.

Reset execution pointers and scratch before each task; scoped guards clear
bindings, admission, recovery and profiling state through exceptions. Both tasks
join before main clears jobs, validates results or advances simulation. One arena
is never used concurrently by a primary and fallback, or by both participants.

## Storage evidence

The controlled 64-bit host fixture reports:

| Layout | Before | Reuse enabled |
| --- | ---: | ---: |
| Result job, excluding heap arena | 4,325,208 bytes | 1,520,704 bytes |
| One search context | 2,804,560 bytes | 2,804,560 bytes |
| Maximum retained participant arenas | Four | Two |

The smaller job now owns its primary arena on the heap, so comparing job sizes
alone overstates the saving. With two allocated fallback jobs, eliminating their
two arenas saves approximately 5.35 MiB of fixed context storage, less the small
new ownership/publication fields. Their dynamic indexes can additionally use up
to 1 MiB each; heap/list/corridor capacities vary. With no fallback jobs allocated,
there is no arena-count saving. Result dependency logs remain separately bounded
and retained. These are layout/allocation observations, not iPhone RSS or FPS.

## Verification

`test_reused_path_contexts.py` replays thirteen complete-worker and four cache
cases with reuse enabled, then adds four targeted checks:

- Stable, distinct participant arenas across repeated ordinary/safe/closest/null
  requests; borrowed fallbacks and separate admission/log ownership.
- Completed Paths, charges, flags and corridor publication survive deliberate
  arena overwrites; resetting a borrowed fallback leaves its owner unchanged.
- A genuinely failed fine search and successful fallback retain independent
  charges, logs and corridors after reuse.
- Reuse OFF/ON matches Path nodes, optimized links, destination, corridor, flags
  and accounting across fixed modes, sizes/centering, search kinds and open,
  winding and isolated-goal maps, with the occupancy cache OFF and ON.

All 279 regular regression cases pass, including the 21-case reused-context
suite. All 21 also pass ThreadSanitizer and ASan/UBSan. Fixtures compile production
search/hierarchy,
Path and optimizer code with controlled world/allocation services. Native iOS
compilation and on-device movement/lifecycle testing remain separate checks.
`[PATH_CONTEXT_REUSE]` confirms enablement and reports native job/context sizes.

## Preceding cache-enabled device evidence

The supplied `~b05cf78` log exits normally, runs 1,105 pairs, reuses 2,155 primary
results and 36 fallbacks, and records three live occupancy rejections. On the
retained comparable worker with 3,666 examined cells and 3,939 records, 65,486
occupancy requests become 3,749 live evaluations plus 61,737 cache hits (94.28%).
Its worker time is 14.101 ms versus 19.925 ms in the preceding cache-OFF log,
about 29% lower across separate sessions. A different, larger search still takes
34.411 ms. Keep the cache enabled, but neither maxima nor unmatched sessions
prove a universal speedup. This log predates context reuse and cannot validate it.
