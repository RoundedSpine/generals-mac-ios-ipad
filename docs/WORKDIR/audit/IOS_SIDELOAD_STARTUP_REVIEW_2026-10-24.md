# iOS sideload startup review — 2026-10-24

## Evidence and scope

Reviewed the checked-out repository's primary iOS/Zero Hour path: CMake preset,
vcpkg manifest and triplet, GitHub workflow, Xcode wrapper, IPA packaging,
SDL entry point and lifecycle bootstrap, early memory/version/command-line
initialization, module path compatibility layer, DXVK iOS patch, Vulkan driver
loading, font discovery and game-data staging. This is a targeted review of
startup and deployment, not certification of every game-engine subsystem.

The successful GitHub run compiled and packaged the engine. The two supplied
LiveContainer logs stop after the banner, before the SDL initialization log.
Code between those messages includes memory manager initialization, Version
construction and GlobalData/command-line initialization. Those logs do not
identify which call fails. Later user testing reported that direct sideloading
launches farther, renders purple textures, then exits after 3–5 seconds.
The direct-install log has not been provided. These are distinct observations;
LiveContainer, JIT or game data cannot be declared the sole cause.

## Defects corrected

1. **Debug memory walls break the promised 16-byte allocator alignment.**
   `GameMemory.cpp` rounds headers and strides to 16 bytes, then adds an
   8-byte leading wall in the default bounding-wall configuration. Every
   returned block is therefore misaligned by 8 bytes. Increased each wall to
   16 bytes; allocation-size and recovery calculations already use `WALLSIZE`.
   This changes allocator metadata, not serialized game/replay data. Both games
   share this allocator. Actual on-device crash causality remains unconfirmed.
2. **Unchecked executable-path failure during early pool initialization.**
   `GameMemoryInit.cpp` passed an uninitialized 260-byte buffer to a path lookup
   and used it without checking success. Long sandbox paths can exceed that
   capacity. Failure now retains compiled-in pool defaults. The compatibility
   function now returns an empty string on failure and bounds Linux readlink
   termination too. On iOS it resolves its own image using dladdr.
3. **Host-relative paths in a hosted app.** The entry point derived bundle data
   from argv[0], and the DXVK patch searched executable-relative driver paths.
   A host executable is not necessarily the game image. The entry point now
   resolves its own image, SDL loads that image's embedded MoltenVK framework,
   and DXVK first tries paths relative to its own library. Existing standalone
   executable-relative and bare-name fallbacks remain in the patch.
4. **Opaque stdio internals copied by value.** The iOS log redirect assigned
   `*stderr = *sink`, copying internal FILE state. It now redirects the stream
   pointer instead. New before/after checkpoints cover early initialization,
   and diagnostics show asset presence, the engine image and selected DXVK
   configuration. No signal handler claims to recover fatal memory errors.
5. **Asset-free IPA omitted the iOS renderer configuration.** The --dev packaging
   path skipped the config containing the existing terrain shader stability
   workaround. All packages now include dxvk.conf and DefaultOptions.ini at
   the app root. Startup selects an explicit DXVK_CONFIG_FILE if supplied,
   otherwise the working-directory config, otherwise the app's config. This
   does not prove the reported purple textures are fixed; direct-install logs
   and on-device retesting remain necessary. Existing asset-bundle option
   seeding is unchanged; loose-data launches retain normal settings behavior.

## Verified and outstanding

- Seven packaging tests verify IPA layout, shader config inclusion, signature
  removal, dylib checks, error propagation and the existing signed path.
- C++ harnesses compile the real allocator offset/recovery function bodies and
  test sizes 1–1024, multiple blocks, two header sizes, and walls on/off. The
  prior wall size fails the alignment assertions.
- A compiled path harness exercises the real iOS compatibility function with
  valid, missing, null, small and over-260-character image paths. It models
  dladdr's result and does not emulate the Apple loader.
- Workflow lint, shell syntax, patch applicability and whitespace are checked.
- CI must compile all Apple-specific changes and produce the revised IPA.
- Only a real device can validate LiveContainer behavior, purple textures,
  audio, touch, memory usage and sustained gameplay. There is no claim that
  the repository is bug-free or that a successful IPA build proves gameplay.

## Follow-up — persistent purple textures (2026-10-25)

The updated direct-install log passes the early checkpoints and reaches the
main loop with data, fonts and the shipped DXVK configuration found. The user
still sees purple textures. The engine's MissingTexture fallback deliberately
fills with magenta, making texture-load state a stronger lead than treating
the final MoltenVK primitive-restart warning as a crash diagnosis.

Found two additional defects:

- `corei_always` propagates `_UNIX` into WWLib, whose `ThreadClass::Execute()`
  returns without launching a worker. TextureLoader nevertheless queues
  low-priority tasks to `_BackgroundQueue`. When no worker is running, it now
  completes tasks through the existing `Finish_Load` synchronous path instead
  of leaving them permanently pending. Windows' active-worker queue path is
  retained. This favors correctness over asynchronous loading performance;
  frame-time impact needs device testing.
- Loading primary BIG files from cwd records an empty asset root, so the
  base-Generals resolver skipped sibling `Generals` and nested `ZH_Generals`.
  It now uses `.` as that fallback root. Shared base-game data is edition
  dependent: earlier advice that the collected Zero Hour-only folder would
  generally suffice was too confident. Keep base archives in `ZH_Generals`
  instead of overwriting Zero Hour's root archives.

Compiled tests execute the real queue-dispatch function with active/inactive
workers and failed tasks, and the real base-asset resolver with empty/explicit
roots. Device logs now identify the first 64 missing-texture names. These
changes still require a fresh IPA and device validation; no fatal error or
out-of-memory termination was established by the supplied rendering log.

## Standalone-only rollback — 2026-10-25

The user confirmed that complete base-game assets removed both purple textures
and crashes, then requested removal of LiveContainer changes. The hosted-image
parts of item 3 above are now reverted: no guest-image dladdr lookup, no explicit
guest-path SDL driver override, and no added loader-relative DXVK driver paths.
The original executable-relative iOS DXVK patch is retained. Standalone app
resource paths still select the packaged renderer config. The executable-path
helper retains empty-on-failure/bounds checks but uses _NSGetExecutablePath on
Apple platforms again. Regression tests model that API rather than dladdr.
Earlier statements above describe the investigation history, not a claim that
LiveContainer caused the user's asset-related failures.

## Texture fallback removal — 2026-10-25

At the user's request, the synchronous fallback described above was removed.
TextureLoader again follows its original Begin_Load/background queue behavior.
The fallback-only test and activation message were removed; the shared base
asset lookup fix and bounded missing-texture diagnostics remain. This is an
intentional restoration of the prior behavior, not implementation of a working
Unix background thread. Device behavior without the fallback is unverified.
