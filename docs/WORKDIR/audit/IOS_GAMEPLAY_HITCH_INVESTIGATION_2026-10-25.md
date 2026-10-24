# iOS gameplay hitch investigation — 2026-10-25

## What is known

The user reports brief freezes during otherwise playable regular gameplay after
the real Unix worker build. Complete base Generals assets fixed the previous
purple textures and startup exits. There is no timing log or matched-map A/B
measurement establishing the new worker as the cause of these pauses.

## Code findings

1. **A foreground request can block behind an unrelated decode.**
   `LoaderThreadClass::Thread_Function` holds `_BackgroundCriticalSection`
   across `task->Load()`. `Request_Foreground_Loading` takes the same lock
   whenever that texture already has a task, even if the worker is currently
   processing another texture. Releasing that lock blindly would risk a task
   being destroyed while the worker still accesses it. This requires ownership
   design, not just removing a lock.
2. **Completion processing has no frame-time budget.**
   `TextureLoader::Update` drains `_ForegroundQueue` before rendering. Completed
   background tasks still call `End_Load` on the render thread, with texture
   unlock/apply and (where managed textures are disabled) UpdateTexture work.
   Multiple completions can therefore form a burst. A budget is plausible, but
   must preserve high-priority/flush behavior and be justified by measurements.
3. **Some texture work is explicitly foreground.**
   `TextureClass::Init` requests foreground loading when thumbnails are disabled
   or the texture has one mip level. Background loading does not move every
   texture access or GPU operation off the rendering thread. Begin_Load also
   performs metadata and surface preparation on the render thread.
4. **The generic worker change has wider callers.**
   GameSpy buddy, peer, ping, persistent-storage and game-results classes use
   ThreadClass too. GameResultsQueue starts a worker in its constructor; other
   worker groups start conditionally. Many idle loops call Switch_Thread, now
   a 1 ms sleep. The number actually running on the user's phone is unknown.
   Start messages now expose worker creation. This does not prove scheduler
   pressure or that unrelated network activity caused a freeze.
5. **Priority is best effort, not guaranteed background QoS.**
   The texture loader requests -4, but Apply_Unix_Priority uses the existing
   scheduler policy. Some policies have no adjustable range. New messages
   report the policy/range or application result, rather than assuming the
   request lowered CPU priority on iOS.
6. **Thread IDs have a shared mutex lookup.**
   GetCurrentThreadIdAsInt uses a process-global map/mutex, including calls from
   render-thread identity checks. This is another potential contention source,
   but has not been measured and was not changed during this investigation.

## Controlled experiment

A compiled harness executes the real Request_Foreground_Loading function body
with minimal task/queue stand-ins. Another thread holds the same background
lock for an intentionally injected 80 ms. The foreground call is delayed by
that lock; timing records identify texture-background-lock and the enclosing
request. This proves a stall mechanism under controlled contention, not its
frequency or duration in real gameplay and not a measured performance gain.

## Diagnostic build

Added bounded `[HITCH]` records using a common monotonic clock and thread token:

- texture-foreground-lock and texture-background-lock: waits of at least 8 ms;
- texture-begin, texture-finish, texture-worker-decode, texture-upload,
  texture-update and texture-flush: operations of at least 50 ms;
- game-update, client-update, audio-update, network-update, logic-update,
  gpu-present and frame-pacing: calls of at least 50 ms.

Names are copied before task destruction, timing Finish is idempotent, and the
process records at most 1024 slow events plus one suppression notice. Startup
and map-loading events are expected: reproduce freezes during normal gameplay
and correlate the monotonic timestamps. Nested events overlap and must not be
summed. A long frame-pacing call can be intentional with a low FPS cap.
GPU-present timing shows time spent in the driver call, not a diagnosis of
shader compilation. Worker decoding duration is not itself a render-thread
stall unless correlated with a wait or long frame. These are wall-clock times,
so they include OS descheduling. Clock reads/logging add diagnostic overhead;
this is a measurement build, not a performance fix.

## Validation and next step

Seventeen local tests pass: seven packaging, four startup primitives, three
worker/queue/shutdown, and three timing/controlled-contention checks. Workflow
lint and whitespace checks pass. Apple compilation and device behavior still
need CI and phone validation. No queue budget, lock-ownership redesign, worker
priority policy or thread-ID optimization has been applied without device data.

Install the diagnostic IPA with the same complete assets and settings. After a
few gameplay freezes, close the app and provide generals-stderr.log (and the
previous log if the current launch overwrote it). Record which map, approximate
time since gameplay started, whether the camera was moving, and whether the
same behavior occurs on the older working IPA. This lets us target a measured
bottleneck rather than changing several unrelated systems at once.
