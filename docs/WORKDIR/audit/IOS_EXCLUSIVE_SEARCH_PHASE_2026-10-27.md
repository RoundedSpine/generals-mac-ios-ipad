# Exclusive search phase contract — 2026-10-27

## Decision and current implementation

Use a frozen simulation phase as the first candidate contract for real worker
searches. Do not let the simulation advance while a worker borrows live cell/map
state. This is a proposed full-search execution contract, **not yet an engine-wide
freeze or an enabled gameplay worker**. The copied occupancy-query validator remains
independent and does not establish this contract.

This stage implements explicit scratch selection and ordinary serial admission
capture, and tests those pieces with real cell and list operations. It does not
move engine searches to another thread or install speculative results.

An exclusive phase with one worker and a waiting main thread is a correctness
baseline; it provides no parallel search throughput by itself and adds handoff
cost. Reimagined gains potential concurrency from groups of searches, while our
existing per-request budget checks and queue ordering remain unchanged. Do not
claim that merely transferring the same serial search to a worker speeds it up.

## Actual simulation and effect boundaries examined

`AI::update()` calls `processPathfindQueue()` before player updates. The queue
resolves each object's AI and calls `doPathfind()` serially, checking the existing
cell budget between requests. This is a candidate owner boundary; it is not proof
that arbitrary object getters or other engine services are safe off-thread.

`Pathfinder::forceCleanCells()` shows why a search cannot simply be classified as
read-only: it displays a localized UI message, queues audio, resets records/lists,
walks the permanent map, may clear invalid obstacles and releases permanent info.
Retail list-recovery paths and route parent walking can trigger this repair, and
retail/fixed flags remain global mutable state. These effects must be executed on
the main thread or cause the worker attempt to be discarded and the request rerun
serially. A debug build or m_debugAI also exposes drawing/script/statistics calls.

Occupancy adapters still resolve objects, AI, teams and canCrushOrSquish on the
caller. The latter initializes a name-key lookup. Terrain destination/height/layer
queries and route optimization remain live engine calls. The current serial caller
is the main thread; neither the new binding nor the historical query transcripts
make those services safe to execute from an arbitrary thread.

## Scratch ownership now implemented

`mainPathfindSearchContext()` names engine/main storage. The new
`activePathfindSearchContext()` selects a lexical binding or falls back to that
storage. Cell search helpers, record release, bookkeeping, search-generation
changes and hierarchical corridor operations use the active context. Permanent
pool allocation, zone-block lifetime, map reset and shutdown continue to address
main storage explicitly. They are not supported concurrently with searches.

`SearchContextBinding` uses a thread-local selection pointer and an ownership
claim on each context. It restores the previous selection on every lexical exit,
including exceptions. Same-thread nesting is allowed; a conflicting claim by
another thread throws before changing that thread's selected context. Ownership
is checked at binding time, not with an atomic operation on every hot cell access.
Unbound legacy access still falls back to main storage: dispatch must always bind
its private context before touching search helpers. This is not a universal guard
against incorrect unbound calls elsewhere in the engine.

The context is noncopyable because its ownership token is atomic. Context lifetime
must extend past all bound work; a future dispatcher must join before destruction.
No thread-local copy of the full 30,000-record arena is silently allocated.

## Admission now implemented

A context can carry a copied permanent-use count. Its allocation logic reads that
value instead of the global permanent pool counter while an AdmissionScope is
active. Persistent cells retain their existing uncharged shadow rule; private
records remain bounded to 30,000 and charged transient admission is unchanged.
Generation changes preserve the phase's admission policy. Scope exit restores the
previous policy, allowing nested scopes and reuse without a leaked capacity limit.
Unbound admission scopes and counts above the fixed record capacity are rejected
before changing the prior policy.

Ordinary internalFindPath binds its current context at entry, performs existing
cleanup/generation work and map-readiness checks, then captures the permanent count
for the rest of the call. Capturing earlier would risk using pre-repair capacity
if beginSearchState performs pending retail cleanup. Closest/safe/hierarchical and
other search APIs retain their previous admission policy when no explicit scope
is provided. No request is admitted with a larger record budget.

The current internalFindPath entry still captures the count itself on the main
thread. Before dispatching it, split main-thread preparation from the worker kernel
and pass that count in the prepared request; calling the current entry on a worker
would still perform a live capture. Frozen admission does not freeze cell occupancy,
Object/Team/AI state or the permanent map, and is not a world-revision mechanism.

## Required full-search phase protocol

1. **Prepare on main.** Complete any pending retail repair and hierarchy setup;
   capture request/movement policy, pool admission and map identity. Establish the
   unchanged queue order and immutable topology/lifetime contract. Prepare private
   context corridor and control inputs without copying nodes or parent pointers.
2. **Enter exclusive phase.** Stop simulation updates and prohibit map reset,
   object destruction, diplomacy/topology mutation and competing search contexts
   from touching borrowed mutable data. Do not pump arbitrary engine callbacks
   while waiting. Binding alone does not enforce these world restrictions.
3. **Compute with a selected context.** Only audited pure/safely frozen reads may
   run on the worker. Query services with main-thread side effects must be captured
   or explicitly serviced on main. Preserve deterministic arithmetic/FP settings.
   Abort/reject on retail repair rather than performing UI/audio/map mutation there.
4. **Return owned values.** Do not allocate/optimize engine paths or expose cell/
   parent pointers after the phase. Copy route and counter/control outcomes, then
   join or otherwise establish completion before touching them on main.
5. **Validate/apply on main before releasing the phase.** Check the request, unit
   lifetime, map/lifecycle identity and phase ownership; consume the result once.
   Reject on repair/cancellation/identity mismatch and use a serial fallback. No
   worker result may be reused after the phase without broader stale-state checks.
6. **End/reset safely.** Release borrowed data only after completion. Inactive/
   background transitions stop new phase admission; map reset and shutdown join
   in-flight work before releasing any engine allocations.

The object/world validation and global mutation barriers in this protocol remain
to be implemented. An unchanged frame number or matching ObjectID is insufficient
proof that the world has not changed. No such token is presented as complete here.

## Tests and limits

Five new compiled tests use production context, record, cell, list and corridor
code. They cover nested/exception restoration, simultaneous ownership rejection,
sequential transfer, independent costs/parents for the same cell keys, corridor
selection, admission scope restoration/generation lifetime and persistent shadows
at the cap. A parallel case churns the real permanent pool on the main test thread
while two other threads use distinct frozen-admission contexts and read-only
transient cell keys. This proves those allocation paths avoid the live counter;
it is not a test permitting whole-engine world mutation during worker searches.

The fine-search regression fixture exercises the real binding point with a small
stand-in context; existing route/expansion comparisons still cover both modes.
Full iOS compilation, gameplay, replay CRCs and performance remain separate checks.

Validation result: all 93 workflow QA tests passed locally. All five new context
binding/admission tests pass AddressSanitizer/UndefinedBehaviorSanitizer and
ThreadSanitizer. The experimental workflow runs this new race check alongside the
occupancy worker check. Actionlint and diff checks pass. Full SDK compilation,
device behavior and replay/performance validation remain pending.
