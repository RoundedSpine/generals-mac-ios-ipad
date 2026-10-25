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
