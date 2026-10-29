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

## Native build and device result — 29 October 2026

GitHub Actions [40784895491](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40784895491)
for ec6c40d9e completes successfully on macos-15 ARM64. The fresh Mac workflow
QA and copied-query ThreadSanitizer steps pass, followed by iOS device compilation,
unsigned packaging and artifact upload. Dependency-cache restoration succeeds;
the separate dependency-save step is skipped. This also confirms the corrected
fixtures pass together in the actual workflow.

The supplied device log identifies ~ec6c40d, reaches ScoreScreen and exits zero.
There is no logged fatal/assertion or primitive-restart warning. Existing
platform/browser stubs and one WAV wrong-sample-count message remain. Normal
completion does not replace movement feedback, lifecycle stress or replay checks.

| Measurement | Previous ~81d5a83 | Current ~ec6c40d |
| --- | ---: | ---: |
| Completed pairs | 946 | 967 |
| Primary reused / executed | 1,811 / 1,852 | 1,876 / 1,906 |
| Primary reuse rate | 97.79% | 98.43% |
| Fallback reused / executed | 38 / 40 | 28 / 28 |
| Fallback reuse rate | 95.00% | 100.00% |
| Permanent-admission first rejections, primary / fallback | 33 / 2 | 0 / 0 |
| Cell-dependency first rejections, primary / fallback | 0 / 0 | 26 / 0 |
| Primary / fallback completed changed-count reuse | Not recorded | 5 / 2 |
| Maximum measured queue update | 41.130 ms | 39.318 ms |
| Queue updates at least 5 / 20 / 50 ms | 112 / 15 / 0 | 94 / 22 / 0 |

The new counters demonstrate actual completed reuse across count changes: five
primary phases (three higher and two lower) and two fallback phases (one higher
and one lower). Primary captured counts span 13,362–15,670 and validated counts
13,360–15,667; fallback spans are 15,637–15,643 and 15,638–15,640. These independent
ranges do not specify per-request deltas or rejected-search headroom. Both
admission-mismatch rows are zero, including equal/invalid-capture counts.

All 28 executed fallbacks are early fallbacks. Queued closest runs 42 primary
phases, with 22 reused; these are subsets of the primary totals. Safe and
ordinary fine-loop-failure fallback remain unexercised in this device session.
There is no discarded or validated-unfinished work. Counts balance: 1,906 primary
plus 28 fallback-only slots equal two times 967 pairs; 1,876 primary and 28 fallback
reuse plus 7,125 serial kernels equal 9,029 finalizations.

## Remaining cell rejections and timing interpretation

The 30 primary first failures are cell dependencies (26), search kind (three)
and world epoch (one). All fallback phases are reused. Closest policy, corridor,
explicit query/height overflow and the other first-reason groups remain zero.
This does not mean every later check executes after an earlier failure.

Source review confirms BoundedSearchReads::matches returns false for either an
unusable/overflowed log or a differing exact cell snapshot. The current device
summary combines both under cell_dependencies. The eight retained slow pairs'
task samples all end Reused and therefore cannot identify the 26 rejected
phases. Their PATH_READS_SLOW flags describe query/height logs, not cell-log
capacity. They do not rule out cell-log overflow elsewhere in the session.

The old permanent-count guard ran before cell validation and could hide a later
cell mismatch. The new allocator observation also explicitly covers cached cell
allocation kinds. Either can contribute to the shift in reported first reasons.
These unmatched logs cannot establish that the same 26 candidates failed before,
or distinguish changed values from invalid cell logs. Keep cell validation;
the next focused investigation should separate those causes before changing
dependency policy or interpreting the count as a new correctness failure.

The slowest queue update is 39.318 ms with a 36.435 ms pair, no serial kernel and
both results reused. Three other retained queue updates are synchronous zone
rebuilds at 35.727, 32.849 and 30.624 ms with no callbacks or pairs. All eight
retained task read samples have zero query/height flags, with 16,717 unique
queries from 352,724 actual observations. The largest worker still makes 138,969
observations using 3,501 entries and reuses its result.

Queue mean is 0.344 ms versus 0.330 ms previously. Serial kernel total/max rise
to 626.081/23.991 ms from 506.072/14.257 ms; pair total rises to 221.970 ms from
196.667 ms while its maximum falls to 36.435 ms from 38.380 ms. Preparation totals
are almost equal, 142.604 versus 142.645 ms, over different attempt counts. No
measured queue update reaches 50/100/500 ms, but more reach 20 ms. Workloads and
run duration differ and totals overlap, so this is evidence of useful reuse and
remaining tail costs, not a controlled overall speedup or regression measurement.

This follow-up changes documentation only. Source/log counter consistency and
diff checks pass; unchanged tests are not rerun and no new IPA build is started.
