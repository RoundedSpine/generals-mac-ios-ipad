# iOS build review — 27 October 2026

## Scope and evidence

Reviewed `experiment/ios-mod-testing` at 452ea6f20 and the changes made during
this audit. The change inventory from c5c8c4d3e covers 91 files, including runtime,
build scripts, tests and documentation. The review followed the active startup,
input/lifecycle, audio/video-stream, texture/thread, allocator, archive/font,
renderer/cache, packaging and pathfinding paths, including their transitive
services. This is a review of our iOS work and its integration points, not a claim
to have verified every line of the roughly 500,000-line engine or every mod.

Run [40476386557](https://github.com/RoundedSpine/generals-mac-ios-ipad/actions/runs/40476386557)
for code commit f3fb2f9e8 passed all 131 Mac QA tests, ThreadSanitizer, iOS
compilation, actual platform/rpath packaging checks and IPA artifact upload.
The latest supplied device log identifies revision `~f3fb2f9`: it reaches the
score screen and exits with code 0 after 999 completed parallel pairs. Of 1,998
speculative results, 1,862 were reused (93.2%), 129 failed validation and used the
ordinary search fallback, and seven were never consumed. The worker's 999-search
summary agrees with one worker task per pair. No primitive-restart warning or
fatal error is recorded. Both CSF passes completed (6,422 and 6,364 labels).
The stable `quad-lists-v1` cache reports `state=new` on this launch; reuse on a
subsequent launch is still unverified. These counters establish on-device use,
not a measured speedup or validation of interrupted gestures, audio pause/resume,
every route or replay equivalence. Community Patch asset integration remains on its
separate branch; only its shared CSF parser correction is brought into this branch here.

## Confirmed issues corrected

| Area | Finding and trigger | Change |
| --- | --- | --- |
| Audio context loss | `bufferData` cleared errors in an unbounded loop. OpenAL Soft 1.24.2 returns AL_INVALID_OPERATION repeatedly with no current context, so the loop cannot terminate. Several failed queries also left output variables uninitialized. | Check context/source before streaming, clear the single sticky error once, reject failed queue queries and initialize query outputs. Failed manager queries do not invent a stopped state. |
| Audio pause | `pauseAudio` pauses speech/music sources, but `processPlayingList` still calls stream update. Its recovery branch restarted AL_PAUSED sources automatically. | Return from stream update while paused; the existing explicit play/resume path owns resumption. Keep the EOF/chirp/EVA fixes and their state reset. |
| Touch/lifecycle | The gesture translator retained PENDING/DRAGGING/PAN across focus loss or reset. A pending touch could become a long-press after resuming; held synthetic buttons had no gesture-level cancellation. | Cancel pending gestures without clicking, release only the held synthetic button, reset gesture state on focus/background/reset and remove the lifecycle watcher during teardown. All gesture mutation remains on main, not in the event watcher. |
| Bundled assets | On first use of bundled GameData, the old tidy-up deleted Documents `.big`, Data, Window, ZH_Generals, fonts and other names. It could not distinguish original copies from user mods or a separate installation. Current asset-free CI did not enter this branch. | Remove automatic Documents cleanup entirely. Bundled assets do not authorize deleting user data. |
| Mod text loading | This branch still interpreted the reserved CSF header word as a seek offset. The Community Patch branch already fixed the resulting missing-label problem. | Backport the shared parser fix without merging Community Patch assets or branch configuration. |
| Malformed text files | CSF label/text/speech lengths and read counts were unchecked before writing fixed buffers. A short header leaked the file; a declared label count could drive allocation without checking whether the file could hold those labels. | Validate lengths, short reads and table boundaries; reject impossible header counts before allocation; close short-header files. Preserve valid retail and nonzero-reserved headers. This does not claim arbitrary-length CSF or complete Unicode support. |
| Packaging | ARM64 verification also accepts macOS and arm64 Simulator libraries. The package could pass that check with the wrong platform. | Check Mach-O build-platform commands for iOS device, including the legacy minimum-iPhoneOS command, as well as ARM64 and dependencies. |
| Packaging errors | `install_name_tool -add_rpath ... || true` suppressed every error to tolerate duplicate rpaths. Real failures were therefore hidden too. | Inspect existing rpaths first, skip only the existing framework path and propagate real tool failures. |

Audio regressions were also run against the previous production bodies: both
null-context and unwanted-unpause tests fail there and pass with the corrections.
The null-context behavior was checked against the exact vendored OpenAL Soft
[1.24.2 error implementation](https://github.com/kcat/openal-soft/blob/1.24.2/al/error.cpp),
not inferred from a generic API warning. None of this establishes that audio caused
the user's earlier touch delays; those were resolved by the native callback change.

## Redundant work removed from the active build

| Addition | Audit conclusion | Current disposition |
| --- | --- | --- |
| Strip/index graphics probes | Bounded logging does not mean bounded lifetime overhead: upload/draw calls still acquire a mutex and inspect tables after logging budgets expire. The verified-quad experiment already has device support. | Compile diagnostics OFF. Keep the actual quad conversion and opt-in probe code/tests. |
| Historical occupancy shadow replay | Replaying captured answers tests the adapter, not freshness of a gameplay result. Parallel result validation already evaluates live occupancy on main. The extra thread/transcript copying is diagnostic overhead. | New `GENERALS_OCCUPANCY_SHADOW_VALIDATION` defaults OFF. Keep the query adapter and live result validation. The older OCCUPANCY_WORKER option name is retained for build compatibility; it no longer implies diagnostic sampling. |
| Per-IPA DXVK cache namespace | A new run-ID namespace starts every installed experimental build cold and accumulates old cache directories. This obscures comparisons and repeats pipeline work unnecessarily. | Reuse `dxvk-test-quad-lists-v1` across experimental builds, separated from old strip-pipeline caches. Retain manual clearing and optional custom test tags. Log the executable's actual git revision separately. |
| Owned raw-route collector | Current paths are finalized on main while their private context still lives. Copying every route into a temporary vector and immediately materializing it adds a pass/allocation without providing an asynchronous result boundary. | Default to immediate construction through the same tested parent walk. Keep `GENERALS_OWNED_PATH_ROUTE` as an explicit OFF-by-default prototype, with equivalence tests. |
| Single-search exclusive fallback | Moving one fallback search to a worker while main waits adds a handoff without concurrent useful work. | Parallel builds run unbatched/rejected searches on the caller. Keep actual parallel pairs and the separate exclusive-worker baseline option. |

The cleanup does not establish a measured FPS improvement. It removes identifiable
operations and recurring cold-cache conditions. Parallel preparation, validation,
rejected predictions and unused second requests can still cost CPU time.

## Changes retained after review

| Area | Retained implementation and reason |
| --- | --- |
| Native frame/input loop | SDL_AppEvent/SDL_AppIterate and the non-sleeping cadence gate. Device feedback supported the fix for delayed touch delivery. No custom UIKit pump or touch tracing is restored. |
| Gesture policy | Deferred taps, drag threshold, long-press timing, two-finger pan/pinch and suppression of duplicate SDL touch-mouse events. The audit changes cancellation, not the established gesture policy. |
| Unix texture thread | Real joined ThreadClass lifecycle, atomic run state, synchronized queue inspection, derived-worker stop and join-before-background-lock shutdown. Missing base files did not make these thread fixes redundant. |
| Texture foreground ownership | File/mip loading stays on the loader; engine texture finalization remains on the render thread. The removed synchronous texture fallback stays removed. |
| Memory/startup fixes | Debug-wall alignment and bounded executable-path failure handling. These address concrete ARM64/alignment/path contracts, independent of whether retail files are now complete. |
| Base assets and collector | Separate base archives in ZH_Generals and cwd-aware fallback loading. Zero Hour still needs shared base content; the data fix remains necessary. The combined collector remains the recommended entry point. |
| Standalone collectors | The older base-only and Zero-Hour collectors remain usable for their separate purposes. They are not a substitute for the combined transfer. No broad script deletion/renaming is justified. |
| Verified quad conversion | Preserve the tested triangle winding/attributes and fixed 2x2 water-track assumption. Complex strips/fans remain untouched. No DXVK source or downloaded dependency is patched by this audit. |
| Manual cache reset | Keep the Files request, managed cache selection and completion report. It removes DXVK state-cache files, not every driver-managed Metal cache. |
| Session logs | Keep two user-accessible logs and normal error reporting. Normal output has an 8 MiB threshold; errors may continue past it. Do not describe this as an absolute file-size cap. |
| Pathfinding foundation | Keep stable heap ordering, late eligible hierarchical allocation, private bounded records, generations, movement capture, ownership bindings, real parallel ordinary pairs and validated ordered consumption. No scheduling/node-limit expansion. |
| Signing/memory requests | Keep the increased-memory and extended-addressing entitlement requests/sidecar. An unsigned IPA cannot grant them; the signer/profile and iOS decide. Native ARM64 execution does not need a JIT. |
| Dependency configuration | iOS device preset, local pinned DXVK submodule, verified MoltenVK download, unsigned packaging and runtime dependency checks. Platform checks supplement architecture checks. |

The active audio backend is Core/OpenALAudioDevice. An older similarly named
GeneralsMD backend remains in the tree; reading or changing that copy alone would
not fix the current build. The audit uses the files selected by CMake.

## Better implementations worth measuring next

1. **Parallel search acceptance and duplicated preparation.** Current prediction
   uses an unrestricted corridor and redoes normal preparation/hierarchy at
   consumption. Corridor mismatches, changed permanent admission, ally commands,
   overflows or budget stops can discard work. Use the existing session counters
   to establish reuse before expanding search types or adding workers. Sharing a
   properly prepared request/continuation would remove more work than extra
   diagnostic replay. Do not silently relax validation to improve the acceptance rate.
2. **Texture queue scheduling.** The loader currently sleeps/polls at 1 ms even
   when idle, and foreground Update drains its queue. A condition-variable wakeup
   could reduce idle wakeups; a measured foreground budget could reduce upload
   bursts. Both require preserving flush/stop/wakeup and texture-priority semantics.
   There is no device measurement here proving either currently causes a hitch.
3. **Search record layout and lookup.** Separate records still carry unused
   permanent metadata and incur repeated bounded-hash/TLS lookups. Compact search
   records or stable indexed lookup could reduce memory/access costs. Dense map-sized
   contexts have different memory scaling; compare representative maps first.
4. **GPU cost.** Native 2868x1320 rendering and 16x anisotropic filtering trade
   quality for GPU work. The configuration's old claim that filtering is free is
   not a benchmark. Lower render scale/filtering are useful controlled comparisons,
   not justified default changes from this source audit alone.

The bounded off-main event mailbox deliberately fails rather than dropping input
when full. Native touch normally arrives on main, and no supplied log establishes
mailbox overflow. A future queue redesign should preserve ordering and button/text
payload ownership rather than silently discard releases. Cooperative texture-worker
shutdown/flush can still wait on actual I/O; no fault-injection/device storage test
of that condition was completed here.

Exact retail replay equivalence, multiplayer determinism, long-session memory,
GPU timing and every mod/mission remain unverified. No percentage-complete or
universal performance/safety claim follows from passing isolated fixtures.

## Validation

- 131 current local workflow QA tests pass, including the newly added audio/CSF
  cases and platform/rpath packaging checks. Fixtures compile production bodies
  with controlled service implementations; they are not full-engine runs.
- Audio, CSF, immediate/deferred route and touch-cancellation checks pass ASan/UBSan.
- All 13 parallel-batch and 9 occupancy tests pass local ThreadSanitizer. The
  macOS runner also passed its QA/TSan steps and the full SDK/package build for
  f3fb2f9e8. Race checks still cover controlled fixtures, not the live engine world.
- Staged PowerShell combined-collector execution verified both games, font aliases,
  excluded top-level executable, unchanged source hashes, existing-output rejection
  and missing-font preflight before creating output. XDG cache/config paths were
  redirected into the temporary fixture because this environment's home is read-only.
- All 13 original-game CSF files available under GameFilesOriginalZH in the
  Community Patch source parsed with production buffer bounds under ASan/UBSan.
- Actionlint, shell syntax and diff checks pass. Local packaging tests use tool
  stand-ins; the successful macOS build additionally ran the actual Mach-O
  platform/rpath checks on every packaged runtime binary.

Next device validation should include menu/game input, interrupted drag/pan and
background/resume, speech/music pause/resume, consecutive EVA lines, maps/bridges,
large group moves and repeated launches using the same cache. Compare the same
save/scenario; avoid treating a warm second launch as proof of a pathfinding gain.
