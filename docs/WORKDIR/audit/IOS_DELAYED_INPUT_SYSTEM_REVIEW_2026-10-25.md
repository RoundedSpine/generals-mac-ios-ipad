# iOS delayed-input system review — 2026-10-25

## Symptom and scope

The user reports clicks registering 0.5–3 seconds late, including on the main
menu while background action continues. Some earlier episodes looked like the
scene jumped ahead. This review traces input delivery, gestures, buffering,
message propagation, GUI routing, shell transitions and the shared frame loop,
and compares competing subsystem explanations against the available logs.
It is a source-level audit with compiled isolated tests, not an on-device
profiler run or a claim to have verified every engine implementation.

## Findings in priority order

1. **Input delivery/gesture/UI gates fit continuing animation better than a
   three-second synchronous audio or GPU stall.** SDL polling, client input,
   rendering and message propagation run serially on the game thread. A single
   long blocking call normally stops new engine-rendered frames too. Continued
   audio alone is weaker evidence, since OpenAL mixes independently. A brief
   stall followed by recovery can look like catch-up; this is not proof that
   logic was running on another thread.
2. **Tap commitment is explicitly deferred until finger release.**
   SDL3GameEngine.cpp sends motion on touch-down, but no left-down. A short tap
   sends motion/left-down/left-up on touch-up. A stationary hold crossing 600 ms
   sends a right click instead, then ignores the lift. There is no unconditional
   600 ms timer delaying every quick tap. Dragging commits after movement of
   at least eight window points using Manhattan distance. This can change which
   action occurs while the scene keeps moving; device traces are needed to
   establish whether the user's taps are being classified this way.
3. **Main-menu actions can be deliberately rejected during transitions.**
   MainMenu.cpp gates many branches with dontAllowTransitions, campaignSelected
   and buttonPushed. dontAllowTransitions clears when TheTransitionHandler
   reports finished. Shell animations request 500 ms plus per-window delay;
   transition durations also depend on game data not inspected here. Background
   shell-map animation can continue. These branches reject actions; they do not
   retain a click for replay three seconds later. Thus a demonstrably delayed
   single click requires another explanation, rather than assuming this gate.
4. **Mouse ring overflow can leave button state inconsistent.**
   SDL3Mouse accepts 255 pending events in a 256-slot sentinel ring and drops
   new events if full, including button-up. Dropped up events can leave a GUI
   grab/drag active until later input changes it. No timed recovery guarantees
   0.5–3 seconds. Raw input count, queue depth and drop traces are required to
   establish overflow on this device; none were present in the supplied log.
5. **The UI can route away from the expected widget while animation continues.**
   WindowTranslator skips normal window routing when the tactical view has a
   mouse lock (with a scrolling exception). GameWindowManager routes through
   mouse capture, grabbed windows and modal windows. InGameUI disabled input
   suppresses downstream gameplay after window handling; it does not by itself
   disable the main-menu widgets. Button behavior also depends on hover and
   enabled state. These are routing/filtering mechanisms, not a time queue.
6. **A quick tap's down/up can share one engine frame.** The translator places
   them directly into the mouse ring. Mouse::createStreamMessages emits a
   position message before processing that batch's mouse events. Hover-sensitive
   widgets may therefore see old hover state if touch-down and touch-up were both
   pumped before any client update. Prior touch-down motion helps when there is
   an intervening frame; it is not proof of correct hover in every batched case.
   This is a possible missed-click mechanism, not a demonstrated delay. No
   speculative hover workaround was added.

## Other systems checked

| System | Path and assessment |
| --- | --- |
| SDL/UIKit event delivery | SDL 3.4.2 UIKit_PumpEvents services default and tracking run-loop modes. UIKit touch callbacks pass OS event timestamps into SDL. No project-configured 0.5–3 second general input timer was found. iOS edge gestures/OS delivery remain external candidates, especially for edge-only failures; SDL traces start after that boundary. |
| Touch cancellation/lifecycle | Cancelled pending taps intentionally produce no click. Focus/background handlers release mouse capture but do not explicitly reset s_touch. An unmatched lost lift can leave gesture state stale; subsequent fingers can be treated as pan/ignored. No fixed timeout or reproduction on the phone establishes this as the cause. |
| Mouse collection | Mouse::updateMouseData drains events up to 256 slots per update; the SDL ring holds at most 255. Normal capacity alone therefore does not impose a multi-second one-event-per-frame backlog. Generic full-array handling can discard the last result for other producers; it does not explain this SDL capacity combination. |
| Message stream | Propagation runs immediately after the client update/draw, iterates translators synchronously and transfers surviving commands to the command list. There is no deliberate multi-second raw mouse delay here. A slow draw/translator can delay dispatch; new timings cover these gaps. |
| Shell update rate | Shell::update checks a roughly 32 ms interval for layout/animation updates. This is not a 0.5–3 second normal polling interval. Gates can still last as long as a transition takes. |
| Frame pacing and game logic | FrameRateLimit waits toward 1/maxFps with nanosleep and a small final spin. Normal configured FPS does not request seconds of sleep. Regular logic accumulator adds at most a target step per update; the code does not establish multi-second parallel simulation catch-up. Network readiness gates logic rather than main-menu mouse dispatch. |
| Audio | Confirmed slow playing-list wall times up to 99 ms; requests up to 53 ms in the latest supplied sample. Source lifecycle can conditionally synchronize with the OpenAL mixer. Worth measuring, but the recorded times do not establish 0.5–3 second input-only stalls. See the gameplay hitch audit. |
| Rendering/GPU/shaders | Recorded world rendering up to 117 ms and presentation up to 162 ms; nested records overlap. Synchronous driver/pipeline waits can stop the main thread, which would affect animation too. Multi-second logic calls are near startup/reset transitions and cannot be assigned to normal gameplay without context. |
| Texture/archive I/O | Foreground lock waits and unbudgeted uploads remain code-level possibilities. No slow texture records in the supplied samples implicate them. Asset/file I/O invoked from the frame thread would normally delay rendering as well. Complete base assets solved the earlier purple-texture problem. |
| Fonts/video/UI resource loading | These can run synchronously from display/window paths; existing client video/windows/display timings cover broad calls. No recorded multi-second stall in those phases establishes them as the input-only cause. |
| Generic/network workers | Only two starts were recorded. No slow network-update record demonstrates network contention. Thread ID mapping has a shared mutex, but no measured contention identifies it. Main-menu symptom makes mission-specific pathfinding/AI an insufficient common explanation. |
| Memory/OS scheduling | Allocation, paging, thermal throttling and OS scheduling can delay a frame. No memory-pressure/termination evidence or measured multi-second allocation is present. Entitlement requests do not establish actual memory grants. No speculative RAM change follows from this symptom. |
| Diagnostics | Input output caps at 2048 records, HITCH at 1024 and stderr at 8 MB. Slow synchronous log writes can themselves perturb timing. The supplied 66 KB log hit neither size nor record cap, but logging is not zero-cost. |

## Validation and diagnostic changes

A compiled harness executes the actual TouchState/sendSyntheticMouse/
handleTouchEvent/updateTouchLongPress source with SDL stand-ins. It checks:
short tap has no button before release, then produces a left click; 599 ms
hold produces no button; 600 ms hold produces a right click; cancellation
produces no committed click. This verifies existing behavior, not device
latency, UIKit delivery, GUI correctness or a performance improvement.

The existing touch, queue, frame, audio and rendering probes remain. Added:

- message-propagation and individual message-translator wall-time scopes,
  threshold 20 ms;
- window-translator input records before early return: state bits 1=mouse
  locked, 2=scrolling, 4=gameplay input disabled, 8=shell active (normal in menus);
- window-dispatch records: state bits 1=mouse captor, 2=modal window,
  4=grabbed window (normal between button-down/up);
- mainmenu-selected records before rejection branches: type is the control ID,
  state bits 1=transitions gated, 2=buttonPushed, 4=campaignSelected.

GUI records share INPUT's steady-clock timestamp and output cap. Unknown
source timestamps produce age=-1; compare their t to mouse-consume/enqueue and
touch-delivery records. No coordinates or physical-contact-to-OS latency are
measured by these extra records. The probes preserve routing, callback order,
gesture thresholds and event lifetimes; Windows keeps its original behavior.

## What a phone reproduction must distinguish

- Late touch-delivery with a poll gap and matching HITCH: whole-frame stall.
- Old touch-delivery with regular polling: SDL/OS delivery or event backlog.
- Prompt delivery but large mouse-consume age/drop records: ring backlog/loss.
- Prompt mouse consumption but late window-translator: work between input and
  propagation, or a translator ahead of WindowTranslator.
- Prompt window dispatch but no selected callback: hit testing, hover, capture,
  modal or widget-level handling; this alone does not identify which one.
- Prompt selected callback with gates set: inspect the exact control's branch;
  flags alone do not imply every control is rejected.
- All stages prompt but a later visible response: menu transition/action
  completion, rather than assuming SDL held the tap.

No single cause for the 0.5–3 second input-only delay has been confirmed. A new
phone log with these probes during a stationary main-menu reproduction is the
most direct next evidence; repeat gameplay afterward to check whether the same
mechanism applies in both contexts.

## Device follow-up: old touches delivered in bursts

The subsequent 324,443-byte log contains 95 touch-delivery records with source
age >=500 ms before INPUT suppression. Distinct bursts include source ages
2143.06 ms, 908.97 ms, 2356.86 ms and 6961.57 ms. These are SDL-translated OS
event timestamp ages, not measurements of physical finger contact. Near the
2143 ms burst, the mouse ring consumes the generated buttons in about 0.5 ms
and window routing occurs about eight ms after delivery. There is no matching
multi-second poll-gap in that interval before the record cap is reached.
Mouse consumption age peaks at 35.76 ms; no mouse-drop-full record occurs.
The four mainmenu-selected records have state=0. These observations strongly
localize the captured burst delay upstream of the game mouse ring, but do not
yet separate UIKit delivery from SDL queue residence or explain every episode.
Both INPUT and HITCH caps are eventually reached, limiting later conclusions.

### SDL event-watch boundary diagnostic

Added a separate iOS SDL event watcher before engine subsystem initialization.
For each finger event it captures SDL_GetTicksNS at watcher entry and stores a
fixed-size diagnostic entry keyed by type, original timestamp, finger ID and
touch ID. It performs no logging, event mutation, filtering or UIKit calls.
The watcher can run on a delivery thread: a private mutex protects 2048 entries;
polling never calls SDL while holding that mutex. Identical keys are consumed
oldest first; overwritten unmatched entries are counted. The watcher is removed
in the engine destructor, and installation success/failure is explicitly logged.

Polling emits separate bounded [TOUCH_QUEUE] records after releasing the mutex:

- source_ns: original SDL event timestamp;
- arrival_ns: the event-watch observation timestamp;
- poll_ns: retrieval observation timestamp;
- prequeue_ms: arrival minus source, measuring upstream age;
- queue_ms: poll minus arrival, measuring time after the watch boundary;
- source_age_ms: poll minus source;
- seq/matched/overwritten: pairing sequence, match availability and tracker loss.

All three nanosecond timestamps use SDL's clock; t uses the shared steady clock
for correlation with HITCH. Zero/future times produce unknown (-1) durations,
never unsigned wraparound. Events already queued before watch registration or
inserted through a path bypassing watchers can be unmatched; queue/prequeue
values must then be treated as unknown. This is a watch boundary, not a precise
measurement of the internal linked-list insertion instruction.

Down/up/cancel events are recorded even when fast. Matched motion events are
logged only if source age or queue residence reaches 50 ms; unmatched events
are visible. The separate budget is 512 records plus one suppression message,
so earlier INPUT suppression does not erase this diagnostic. Logging happens
on the polling thread and remains a possible timing perturbation. Existing
stderr size limits still apply. No async input processing or gesture changes
are introduced. A short main-menu reproduction immediately after launch is
preferred to a long mission session.

Local compiled tests cover FIFO matching of duplicate keys, identity isolation,
ring overwrite reporting, 3000 cross-thread record/consume operations, age
calculations, unknown timestamps, bounded output and the actual SDL watcher
function body preserving event fields. Full SDL/UIKit integration and the
next device measurements still require the IPA built by macOS CI.

## Rejected UIKit pump experiment: device regression

The 1 ms/no-early-return pump experiment (3b20cb01a) was installed, confirmed by
its IOS_EVENT_PUMP startup marker. The user reports worse responsiveness. In
the 94,265-byte log all 88 printed queue records matched with zero overwrites:
maximum prequeue age 8201.44 ms, queue residence 6.10 ms. Seventy records had
prequeue age >=500 ms. The preceding upstream-pump sample had 108 matched
records, maximum prequeue 4106.26 ms, queue residence 1.93 ms and 12 records
>=500 ms. These are thresholded/unmatched-duration sessions, not a controlled
latency-distribution benchmark, but both the report and observed bursts reject
this change as a useful fix. No comparable multi-second processing/polling
stall explains the burst in this sample.

Reverted the iOS SDL pump modification, its FetchContent hook, startup marker
and experiment-specific tests/documentation. Retained all touch queue-boundary
and UI diagnostics. The classic upstream 2 microsecond/return-after-source pump
is restored. The removed experiment's patch was guarded/idempotent and had
local stand-in tests; those tests never established device responsiveness.

The changed default-mode duration and return behavior were tested together, so
this does not isolate which change mattered, nor prove starvation or show that
an even shorter/longer delay would fix it. The strongest established boundary
remains late delivery before the SDL watcher. Do not increase pump durations
blindly. A future investigation should examine UIKit callback delivery and the
classic SDL_main/manual nested run-loop integration, with physical contact/OS
queue timing distinguished from SDL's translated timestamp. This rollback
restores the previous behavior; it is not a fix for the original delayed taps.

## Next-step investigation after rollback

Reviewed SDL 3.4.2's UIKit touch view, app delegate, event pump and iOS main
callbacks, plus the engine's startup/execute/cleanup boundaries.

Current path: SDL's postFinishLaunch invokes SDL_main, which calls GameMain;
GameMain initializes the engine, runs execute's while-loop, then destroys the
frame pacer and engine. SDL3Main subsequently destroys its window, quits SDL,
destroys Version and shuts down engine memory. While the loop runs, UIKit is
serviced through SDL's nested manual CFRunLoop pump. The frame limiter sleeps
without returning to UIApplicationMain's outer run loop. This is SDL's supported
classic entry path, so its mere use is not evidence of a defect.

SDL's callback entry is architecturally different. SDL_EnterAppMainCallbacks
returns out of SDL_main after initialization and installs CADisplayLink;
SDL_IterateMainCallbacks performs event handling and one SDL_AppIterate call
per invocation. This would let the native run loop own inter-frame scheduling.
It is a credible alternative to test if loop servicing is implicated. It is
not a drop-in wrapper around GameMain: GameMain and SDL3Main must separate
initialization, one-frame execution and cleanup, preserve shutdown ownership,
and avoid both duplicate polling and a sleeping frame limiter inside display
callbacks. Legacy/headless behavior and lifecycle gates need to remain intact.

**Recommended immediate next step: one thin native UIKit timestamp probe, with
upstream pump behavior retained.** In the SDL touch callbacks, record callback
entry uptime alongside both UIEvent.timestamp and each UITouch.timestamp,
plus SDL_GetTicksNS. Prefer a fixed-size buffer drained during polling rather
than synchronous logging in UIKit. Keep original event/touch timestamps and
run-loop policy unchanged; use a guarded iOS-only dependency diagnostic patch.
Capture touch begin/end/cancel, bounded motion and finger identity so values
can be paired with the existing watcher records. This requires an Objective-C
CI build; host stand-ins cannot establish UIKit semantics.

Why this is needed: current prequeue_ms compares SDL's converted event timestamp
to SDL_GetTicksNS. UIKit_GetEventTimestamp initializes and adjusts a static
clock offset. The view currently supplies UIEvent.timestamp to the finger path,
whereas some pointer paths use UITouch.timestamp. Existing traces do not
independently verify that conversion or per-touch/event timestamp equivalence.
The user clearly observes real delayed responses, but locating every part of
that delay solely from converted timestamps was too strong. Queue residence
is the directly paired SDL-clock measurement; it remains fast.

Decision criteria:

- Callback entry uptime minus UITouch.timestamp is large, and agrees with
  UIEvent age: delivery to the view is genuinely late. Next test native SDL
  frame callbacks and inspect edge/system-gesture behavior. That migration is
  a scheduling experiment, not an already-proven cure.
- Callback touch age is small but event age or converted SDL age is large:
  investigate event reuse/coalescing or clock conversion before modifying the
  loop. Do not replace timestamps with "now" to conceal delayed delivery.
- All native/SDL arrival ages are small but response is late: trace the already
  instrumented gesture/UI route, including 600 ms long press and menu gates.

Do not implement another arbitrary run-loop duration or put rendering on a
background thread as a substitute for this measurement. Preserve the rollback
IPA as the baseline and use short, comparable main-menu tests. No new production
behavior change or new diagnostic IPA was introduced in this investigation.

References (pinned SDL 3.4.2):
- https://github.com/libsdl-org/SDL/blob/release-3.4.2/src/video/uikit/SDL_uikitview.m
- https://github.com/libsdl-org/SDL/blob/release-3.4.2/src/video/uikit/SDL_uikitevents.m
- https://github.com/libsdl-org/SDL/blob/release-3.4.2/src/video/uikit/SDL_uikitappdelegate.m
- https://github.com/libsdl-org/SDL/blob/release-3.4.2/src/main/ios/SDL_sysmain_callbacks.m

## Implemented native callback boundary diagnostic

Added an iOS-only, guarded FetchContent patch to SDL_uikitview.m. Each finger
callback captures SDL_GetTicksNS and NSProcessInfo.systemUptime immediately on
entry. Before its existing SDL_SendTouch/SDL_SendTouchMotion call, it records
UIEvent.timestamp, UITouch.timestamp and touch kind, using the same normalized
SDL timestamp already required by that send. Conversion still occurs exactly
once and the original SDL event arguments/order are preserved. The patch does
not alter SDL_uikitevents.m, event pumping, gestures, or native run-loop policy.

A shared C-compatible data bridge is registered through a namespaced SDL global
pointer property. The native callback invokes a fixed-size app-side recorder;
there is no logging in the callback. Native samples pair by type, converted
source timestamp and finger identity (FIFO for duplicate keys). The 2048-slot
buffer is mutex protected and reports overwrites. The property is cleared on
engine destruction; bridge storage has static lifetime. Layout orders 64-bit
fields ahead of 32-bit fields to avoid differing four/eight-byte struct packing
across legacy C++ and Objective-C units.

On polling, independent bounded [UIKIT_TOUCH] records report:

- event_age_ms and touch_age_ms: callback entry uptime minus the original
  event/touch timestamps, without SDL clock conversion;
- converted_age_ms: callback entry SDL clock minus converted SDL source time;
- callback_to_watch_ms: entry to the existing SDL queue watcher;
- original uptime/event_time/touch_time, source_ns/callback_ns/poll_ns,
  matched, kind and overwrite count, for cross-checking assumptions.

Unknown/future ages are -1. Edge events always log; matched fast motion is
suppressed unless one measured stage reaches 50 ms. The independent native log
cap is 256 records plus one suppression message. Matching failures are explicit;
no inference should be made from unknown durations. Reading native timestamps
later in a callback can matter if UIKit mutates touch objects; entry uptime is
captured first and future readings are not silently clamped into plausible ages.
Native finger contact-to-OS latency is still not measured.

Validation: patch idempotence and changed-context rejection; exact recovery of
original fixture callbacks after removing diagnostic inserts; one conversion
per send; stable C bridge layout under four-byte packing; native clock arithmetic
and unknown ages; FIFO, overflow and 3000 cross-thread pairings; independent log
cap. Applied/reviewed the patch against actual pinned SDL source. Added an
Objective-C helper syntax check using the iOS SDK on macOS CI; Linux skips this
one check. Full production SDL compilation is still performed by the IPA build.
No phone improvement is claimed: this build measures native delivery so the
next scheduling decision is based on independent clock evidence.

## Native UIKit evidence and iOS callback-loop implementation

A subsequent 280,374-byte device log independently captured native event and
UITouch ages of 16720.87 ms at callback entry. Callback-to-watch remained <=0.19
ms, watch-to-poll <=16 ms and mouse queue consumption <=25.12 ms. There was no
matching long poll gap. This rules out SDL clock conversion alone for that
captured old-touch burst and justifies testing native inter-frame run-loop
ownership. The prior delay-free log did not prove resolution; the failure is
intermittent. Native logging later reached its cap, so this evidence concerns
the captured portion.

Implemented iOS-only SDL_MAIN_USE_CALLBACKS in SDL3Main.cpp. SDL_AppInit performs
the existing launcher bootstrap and engine initialization, then returns; the
SDK's native CADisplayLink backend owns subsequent event/frame scheduling.
Shared InitializeGameEngine/ShutdownGameEngine helpers preserve the existing
GameMain desktop and replay paths. Launcher resources stay alive until
SDL_AppQuit, which uses the existing window/SDL/Version/memory cleanup sequence
and final _exit. If engine init failed partway through, the current destructor
cannot safely run (it dereferences subsystems unconditionally); that failure
logs and exits instead of trying unsafe partial teardown.

SDL_AppEvent dispatches through the extracted existing processSDL3Event handler.
The normal callback path never SDL_PollEvents again; SDL already owns queue
consumption. SDL-owned text is consumed synchronously. Off-main callbacks are
marshaled through a mutex-protected bounded 256-event mailbox, copying the text
payload that the handler consumes; main processing drains outside that lock.
Lifecycle atomics still gate rendering immediately. Foreground iteration
reconciles mouse focus on main. Mailbox exhaustion or callback exceptions fail
explicitly rather than silently dropping state or unwinding into SDL.

SDL_AppIterate performs at most one normal engine update per eligible native
callback. NativeFrameCadence uses SDL nanoseconds, honors the current render
limit without sleeping, tolerates small display-callback jitter, advances
missed deadlines without a catch-up loop, and resets while inactive. The shared
FramePacer receives elapsed time through updateExternal; the original sleeping
frame-pacer update remains on the desktop loop. Background callback iterations
return without SDL_Delay or graphics calls. Existing touch gesture timer checks
continue during eligible frames. A startup IOS_MAIN_LOOP marker identifies the
new mode; callback-frame-gap/input-frame-service timings replace misleading
manual-poll labels in this path. Native/SDL queue probes remain.

This is a scheduling experiment, not yet a confirmed cure. Blocking map loads,
script callbacks, GPU calls or file work inside one update can still block the
main thread. Native cadence is constrained by the device's display callbacks
and can differ from the old loop. The iOS callback path targets interactive
play; it rejects headless/replay simulation launch flags. Desktop headless and
replay simulation keep GameMain. Legacy execute-loop debug benchmark/profiling
wrappers are not entered by the iOS callback path; normal engine update and
subsystem diagnostics still run. Rendering/gameplay/pause/exit behavior needs
phone validation even after CI compilation.

Added compiled actual-body tests for SDL_AppInit/Event/Iterate/Quit, including
init/event/frame exceptions, pause/resume cadence and avoiding unsafe partial
teardown; actual deferred mailbox text ownership, full-buffer handling and
processing outside locks; actual input service proving no manual SDL polling
in native mode while long-press checks remain; shared startup/shutdown retaining
desktop execute and replay simulation; and cadence under 120 Hz callbacks with
jitter, frame limits, late frames, rate changes, reset and clock rewind. These
stand-ins cannot verify CADisplayLink/UIKit behavior. The existing macOS CI
build must compile/link the full iOS application and native probe.

## Remaining 2.1 second episode and native callback/gate tracing

The next 474,493-byte callback-build log captures a different remaining stall.
Near t=810170923, native touch ages are about 12–16 ms and SDL delivery is
sub-millisecond/few-millisecond, but generated mouse events wait up to 2108.86
ms. At t=810173064 the frame-service gap is 2116.93 ms, followed immediately by
consumption and UI dispatch. No matching two-second game-update scope appears.
This episode was captured before suppression. It localizes a delay between
native event handling and the next serviced engine frame; it does not alone
say whether display callbacks stopped, a lifecycle gate held, cadence skipped,
or untimed callback/event work blocked.

Added independent bounded NATIVE_FRAME diagnostics at SDL_AppIterate entry,
exit, lifecycle/cadence skips and engine-update start. Fields include entry
interval, time since the prior callback returned, time since update start,
last decision, pause bits, FPS, cadence deadline and callback/skip counts.
Callback-gap fields describe the previous callback decision; consult lifecycle
records for intervening changes. Update-resumed records summarize the preceding
no-update interval. Paused records use fps=0 because the FPS policy has not
been queried. Cadence exposes its deadline read-only; no eligibility policy,
frame timing decision or reset order is changed.

NATIVE_LIFECYCLE separately records the existing watcher decisions, with bits
1=backgrounded and 2=inactive. This remains available when display callbacks do
not fire. These rare lifecycle notifications may log on their delivery thread;
touch callbacks still do not log there. NATIVE_FRAME is capped at 256 and
NATIVE_LIFECYCLE at 64 records, each with a suppression marker independent of
INPUT/UIKIT_TOUCH/TOUCH_QUEUE/HITCH budgets. Frame skips log on state change or
at most once per second during a >=100 ms no-update interval; fast normal
callbacks do not produce continuous trace output. Logging remains a possible
timing perturbation, and the existing stderr size limit still applies.

Added HITCH scopes for the complete native frame callback, native event callback,
deferred event drain and focus reconciliation. This fills the untimed paths
before normal GameEngine::update. The frame RAII exit clock is sampled again
after its own diagnostic write so that write is not classified as time outside
the callback. Source timestamps use SDL's clock; t remains the common steady
clock used by the other traces.

Controlled tests distinguish an injected two-second outside-callback interval,
continuously invoked lifecycle-gated callbacks, cadence skips, resume, long
callbacks and bounded independent output. An actual lifecycle-watcher harness
verifies that diagnostic additions preserve the atomic pause flags and do not
log unrelated events. Existing actual callback/body tests cover routing and
cadence decisions with the new traces. No new scheduling experiment is included;
the purpose is to identify which branch accounts for the remaining episode.
