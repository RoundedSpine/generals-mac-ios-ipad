# Stable open-list heap experiment

Branch: `experiment/ios-mod-testing`. Date: 26 October 2026.

## Scope and attribution

The user requested a stable binary heap as the first mod-testing experiment.
The queue design was informed by Zero Hour Reimagined 1.0.0 by dement123, supplied
in `ZeroHourReimagined_1.0.0_source.zip` (its PathSearchContext.h / AIPathfind.cpp).
The mod README identifies its base as ModernGeneralsZH and TheSuperHackers
GeneralsGameCode and distributes source under GPL v3 with EA's additional terms.
This implementation adapts the stable heap concept to our existing cell records;
it does not import the context/worker/pathfinding rewrite.

## Behavior

Only Pathfinder's open list opts into heap storage; closed lists remain linked.
Heap keys are the existing 16-bit total cost followed by a 64-bit insertion
sequence, reset at the existing list-reset boundaries. Each existing cell-info
record carries its heap index. Removing and reinserting an updated cell gives it
a fresh insertion sequence, matching insertion after existing equal-cost cells.
Removal supports callers that change cost before removing the node. Cleanup
continues through the original cell releaseInfo method. Debug display enumerates
heap entries without assuming sorted linked traversal.

The default retail path has a 5,000-step insertion traversal limit. A fully sorted
heap would change this behavior for large queues. Before inserting into a heap
with at least 5,000 entries in retail mode, the queue is converted, in stable
sorted order, into the original linked representation. That search keeps using
the original retail insertion method until reset. Fixed mode can retain the heap
for larger queues. Seeded retail reset and existing crash-recovery resets remain
supported. No general replay-compatibility guarantee is inferred from queue tests,
especially for already-corrupted legacy states.

The 30,000-record pool and 5,000-cell frame budget are unchanged. No batch of eight,
worker prefetch, fresh-search node lifetime, new movement rule, balance adjustment,
graphics change or runtime diagnostic is included. Additional memory consists of
index/sequence fields per existing pool record and a retained vector of pointers
for the open queue, rather than a record for every map cell per worker.

## Validation

`python3 scripts/qa/test_pathfind_heap.py` compiles the actual header declarations
and production queue methods against minimal cell fixtures. It compares heap
selection against the original list selection under retail, fixed-with-retail
support, and fixed-without-retail support builds. Each configuration exercises
64,000 deterministic randomized iterations with equal costs, cost changes before
removal, reinsertion and head removal; 6,100-entry queues cross the retail cap;
record reuse, cleanup and seeded reset are covered. Each configuration also
compares expansion order and route output on 100 synthetic four-neighbor grids.
These grids use a harness A* driver, not the complete engine pathfinder.

The suite passes locally. The four existing packaging/startup/worker/native
callback suites also pass (20 tests), for 23 tests total. Address/undefined
sanitizer runs of the extracted production queue are checked separately. Workflow
syntax and whitespace are checked with actionlint and git diff --check.

The iOS workflow now accepts pushes to the experimental branch and runs the heap
suite before the SDK build. Full iOS compilation is left to that macOS runner;
this Linux environment has no Xcode. Real campaign/skirmish route behavior,
retail replay CRC equivalence, device memory and frame-time improvements still
need validation. This change is experimental and makes no speedup claim.
