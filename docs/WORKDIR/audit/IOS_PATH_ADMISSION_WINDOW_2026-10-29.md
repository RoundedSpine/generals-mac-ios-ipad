# Validate allocation decisions rather than permanent-count equality — 29 October 2026

## Motivation and retained policy

The ~81d5a83 device session has 35 permanent-admission first rejections across
primary/fallback phases, with count changes in both directions. Exact equality
is conservative: an unrelated count change can invalidate a result even when no
allocation outcome would change. Keep the 30,000-record bound, permanent/transient
credit rules, one worker plus main, four maximum phase contexts, original search
limits, per-request queue budget and all other result dependencies.

This stage implements allocation-decision equivalence. It does not adopt
Reimagined's independent map-sized search allowance, dense nodes, broader dispatch
or full off-thread hierarchy/Path construction.

## Decision window and correctness boundary

For a new nonpersistent record, the existing admission predicate is P + T < C,
where P is the phase's frozen permanent count, T its current transient usage and
C the existing capacity. A successful predicate requires P <= C - T - 1; a denied
predicate requires P >= C - T. SearchAdmissionWindow intersects these constraints
over all reached predicates in the speculative fine phase, including setup.

At consumption, accept a changed count only if it lies inside that intersection.
The captured source count must also match the tracker's source when observations
exist; changed snapshot sources within a phase or out-of-domain inputs make the
window unusable. A phase with no transient predicate has no count dependency and
permits the whole valid range. Each beginSearch clears the window with the record
generation. Releases change T for later checks but never erase prior denials.

Existing records return before an admission predicate; persistent cells bypass
transient credit. Physical keyed-pool capacity/failure remains unchanged. If an
admission predicate passed before a subsequent physical-pool failure, retaining
that predicate's constraint is conservative. No records are evicted or additional
slots made available by validation.

With unchanged cell/policy inputs and identical earlier allocation decisions,
the next operation sees the same record set and transient count. Its recorded
predicate therefore has the same answer for every count in the window. Induction
preserves subsequent successes, denials, releases, ordering and loop outcome.
This proof needs the entire reached decision history, not merely final record
count, peak usage or a guessed reserve.

The original scalar count test becomes a window check at the same short-circuit
position. Cell, corridor, live occupancy, height, movement, world/lifecycle epochs,
retail recovery and overflow checks remain. An invalid window rejects even when
the captured/current counts are equal. This is a more precise allocation
dependency, not permission to bypass validation.

## Persistent allocation kind and cached pointers

Whether a new record is persistent depends on the cell's permanent metadata.
Record each speculative new-allocation attempt in the existing bounded cell-read
log before the predicate or physical allocation, including attempts through cached
cell pointers that bypass getCell. The exact snapshot includes metadata presence,
IDs, position and movement flags. Changing that allocation kind invalidates reuse
even if global counts or window membership would otherwise permit it.

Use the existing cell log and overflow rejection; no second cell log or unbounded
list is added. Duplicate getCell/allocation observations retain the first exact
snapshot. This adds a bounded-log lookup on new speculative allocation attempts;
it does not add observation work to ordinary serial/finalizer allocations.

## Finalization uses the actual caller's frozen count

Window equivalence covers the completed setup/fine-search trace, not future Path
optimization or cleanup allocations. The actual caller still freezes its count
at the original fine-entry point. Validate against that frozen count and copy it
to the selected job as validatedPermanent only after all checks succeed. Ordinary,
safe and closest/fallback completion bind that validated value while using the
already validated private records.

Completion then executes its original live code and allocation predicate under
the same allowance the serial caller would use. It does not continue with the
prediction's old count, or reread unrelated global usage that may have changed
after the caller entered its phase. Existing transient charges remain valid
because the allocation-kind and full decision dependencies passed. Main-side
hierarchy, finalization, accounting and side effects remain authoritative.

Tracking runs only while the speculative read log is installed. Main serial and
result completion use the original predicate without maintaining a prediction
window. A window uses a fixed handful of scalar fields per context; no allocation,
per-cell bit table, lock, new worker or map-sized storage is introduced.

## Optional diagnostics

The existing timing option retains PATH_ADMISSION_MISMATCH for first window
rejections. Its higher/lower counts are supplemented by equal, covering unusable
windows with unchanged counts or invalid capture. Captured/current minima and
maxima remain independently aggregated, not per-request deltas.

Two new PATH_ADMISSION_REUSE rows, primary/fallback, record changed counts only
after normal finalization reaches the existing Reused outcome. They include calls,
higher/lower and captured/current ranges. Passing a window but failing cell or
other validation is not counted; neither is validated-but-unfinished work. The
existing exactly-once result guard also protects reuse counting. Same-count reuse
continues in the original result totals rather than these changed-count rows.

All updates occur on main after join. Workers write only their private window and
existing private dependencies. No per-allocation logging or clock is introduced.
Diagnostics disabled uses the same window rule without counters or extra output.

## Verification and next device check

Eight added tests plus the updated prior admission-summary test cover exhaustive
small-capacity predicate histories; production allocate/release traces with
persistent cells and full pools; benign increases/decreases for ordinary, safe,
closest and early fallback in both retail modes with serial route/budget matching;
the exact upper-capacity boundary; completion exhausting the actual caller's
remaining allowance in all four kinds; cached-pointer allocation kind and cell-log
overflow; invalid same-count capture; frozen caller versus changed global count;
short-circuit ordering; and unfinished/exactly-once reuse counters. Existing
enabled/disabled diagnostic query traces and route matrices remain enabled.

All 214 local workflow cases pass after fixture corrections. The first 19
workflow suites pass unchanged; the 93-case batch run has one fixture-only
missing-memory-header failure, and that corrected signed-ID case passes when
rerun. The earlier batch run also exposed the old blanket-count rejection
expectation; it now tests mismatched capture integrity while the new cases
explicitly require benign count changes to be accepted. The signed-ID fixture
links the actual observer/dependency log and exercises a persistent allocation,
rather than replacing the observer with a stub.

All 93 batch cases pass ThreadSanitizer after those two fixture corrections,
with corrected cases and the final caller-snapshot case run separately from the
92-case suite. All nine admission-window cases (eight added and one updated)
pass ASan/UBSan, with the final snapshot case run separately. Enabled/disabled
validation query traces, route matrices and per-request budget checks pass. Diff
checks pass. The world, hierarchy and Path services in these fixtures are
controlled; these are not a full-engine replay or proof of every live-world
access. Native SDK and device validation remain pending for this change.

Repeat the saved mission, include obstacle/unreachable destination and crowded
movement, then exit normally. Check PATH_ADMISSION_REUSE, remaining admission and
cell rejections, balanced result counts, paths/destinations and queue/preparation
tails. A positive reuse count proves some changed-count phases completed without
serial recomputation; it does not establish net speedup. The prior longest reused
pair and synchronous zone rebuilds remain separate measured costs.
