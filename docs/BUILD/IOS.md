# Unsigned iOS IPA builds

The **Build iOS unsigned IPA** GitHub Actions workflow builds Zero Hour for
arm64 iPhones and iPads running iOS 16 or later. It uses a macOS runner with
Xcode and requires no Apple signing secrets.

1. Push the workflow and packaging changes to your GitHub repository. Pushes to
   `ci/ios-unsigned-ipa` start a build automatically, including before merge.
2. Open **Actions → Build iOS unsigned IPA → Run workflow** and select the branch.
   GitHub normally requires the workflow to exist on the default branch before
   showing the manual Run workflow button.
3. After a successful run, download the **GeneralsXZH-iOS-unsigned** artifact
   and extract `GeneralsXZH-unsigned.ipa` from the artifact ZIP.
4. Sign and install the IPA using your preferred sideloading tool and your own
   Apple account. An unsigned IPA cannot be installed directly. Your signing
   tool must sign the embedded dylibs and MoltenVK framework as well as the app.

The IPA excludes original game assets. Supply your own retail Zero Hour data
through the app's shared Documents folder after installation; see
[Getting the Game Files](../HOWTO/GETTING_THE_GAME_FILES.md). For text rendering,
run `bash scripts/build/ios/stage-fonts.sh` on a development machine and copy the
resulting `fonts` directory alongside your game data. No retail data or Apple
credentials are downloaded by this workflow.

To collect game data on Windows, save
[`collect-ios-game-data.ps1`](../../scripts/build/ios/collect-ios-game-data.ps1)
and run it in PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\collect-ios-game-data.ps1
```

The default source is `D:\Command & Conquer Generals Zero Hour`. The script
creates `GeneralsZH-iOS-Transfer` on your Desktop, copies all top-level `.big`
archives plus `Data`, `Window`, `Maps` and `ZH_Generals` when present, and stages
four fonts from the game folder or Windows Fonts. It does not change the
installation and refuses to overwrite an existing transfer folder. Override
`-SourceDirectory`, `-DestinationDirectory` or `-FontsDirectory` as needed.
Copy the **contents** of the transfer folder into the app's Documents folder.
This copies the installed data as-is; it does not remove mods or apply patches.

For local packaging on a Mac, first build the `ios-vulkan` CMake preset, stage
MoltenVK with `scripts/build/ios/fetch-moltenvk.sh`, and run:

```bash
bash scripts/build/ios/package-ios-zh.sh --dev --unsigned
```

`GX_MOLTENVK` selects the iOS device MoltenVK framework and `GX_BUNDLE_ID`
overrides the bundle identifier. The workflow passes the verified MoltenVK
archive's static library and headers to CMake and embeds its dynamic framework
for DXVK. It initializes only the required DXVK submodule and pins vcpkg to a
revision containing the manifest's FFmpeg override.

The output is `build/ios-package/GeneralsXZH-unsigned.ipa`. The existing signed
packaging path remains the default; `--unsigned` cannot be combined with
`--install`. Logs are uploaded even when a build fails. A successful CI build
checks packaging, not gameplay: launch, graphics, audio, touch input and retail
asset loading still need validation on a real device after sideloading.

For startup failures, the app writes `generals-stderr.log` and retains the
previous run as `generals-stderr-prev.log` in its Documents folder. New builds
report startup checkpoints, asset presence, the standalone app path and selected
DXVK config. Asset-free IPAs now also carry the iOS renderer config. See the
[startup review](../WORKDIR/audit/IOS_SIDELOAD_STARTUP_REVIEW_2026-10-24.md) for
verified defects, regression tests and remaining device-validation limits.

## Memory entitlements

The iOS wrapper requests both capabilities from `ios/GeneralsXZH.entitlements`:

- `com.apple.developer.kernel.increased-memory-limit`
- `com.apple.developer.kernel.extended-virtual-addressing` (EVA)

The externally signed artifact carries these requests in an **ad-hoc signature
on the Generals executable**. The packager extracts that signature and fails if
the requests were lost. The artifact also includes `GeneralsXZH.entitlements`
and `GeneralsXZH-embedded-entitlements.plist` beside the IPA for inspection.
Here, "unsigned" means no Apple certificate or provisioning profile: the ad-hoc
signature is a request carrier that your sideloader must replace. It does not
grant either capability or allow direct installation.

SideStore reads the app's request from the executable signature; the adjacent
plist alone is insufficient. Older builds removed all executable signatures,
so even a capable signer could obtain a profile and then omit the memory key
from the installed executable. A compatible provisioning profile and a retained
executable request are both required. Verify the final signed app's entitlements.
On a Mac, use
`codesign -d --entitlements :- /path/to/GeneralsXZH.app` after extracting the
signed IPA. Requested keys in an executable signature are not by themselves
proof that the OS granted the capability on the current device.

Increased Memory Limit can raise the supported process allowance; it does not
guarantee access to all physical RAM. EVA expands virtual address space and does
not add physical RAM. Neither capability is a fix for invalid memory access or
missing game assets. Under LiveContainer, the host process's entitlements and
memory allowance matter; adding keys to the guest does not grant them to the
host. This does not integrate GetMoreRAM or add a runtime memory-limit bypass.

At startup, `generals-stderr.log` includes a runtime check such as:

```text
[IOS_MEMORY_ENTITLEMENTS] source=running_process increased_memory_limit=true extended_virtual_addressing=true
[IOS_MEMORY_ENTITLEMENT_QUERY] increased_status=ok increased_error=0 eva_status=ok eva_error=0
[IOS_MEMORY] available_process_mib=... footprint_mib=... physical_device_mib=... sample=startup
```

These entitlement values come from the executing process, after sideload signing,
rather than the build plist or profile permissions. `false` and `absent` report
their respective query results. `unknown` means the optional native query was
unavailable, failed, or returned an unexpected type; the query row explains why.
The self-query uses dynamically resolved Security framework symbols because the
public iOS SDK does not declare SecTask. Failure to resolve/query them is harmless
and does not prevent startup. Memory observations use public OS APIs. Available
process memory is a changing headroom measurement, not a fixed total RAM limit;
a `true` signed entitlement alone does not prove the OS granted a particular
memory allowance. No memory stress allocation is performed.

For SideStore, use a signer that enables Increased Memory Limit for your team
and import the newly packaged **Generals IPA** for a complete signing and
installation/update operation. Back up game data and keep the same Apple team
and bundle ID for an update. Refresh All can update provisioning profiles
without re-signing the executable, so it cannot add a missing executable request.
Do not assume an entitlement editor or a profile view proves the final signature
retained the key; inspect the next startup log after restarting the app.

The custom SideStore build applying [SideSign PR #4](https://github.com/SideStore/SideSign/pull/4)
enables **Increased Memory Limit**, not EVA. It logs capability-request failures
and may continue installing without the grant. EVA remains a separate provisioning
requirement even though the game IPA requests it. When Generals is installed
directly, inspect Generals' profile and signature; LiveContainer's entitlements
have no effect on that standalone process. Copying an entitlements file into
Documents does not change a signed app.

For long sessions, `[IOS_MEMORY]` also records `sample=periodic` at the first
native iteration and every 30 seconds while callbacks run. Rows include SDL
`uptime_s` and a cumulative `low_memory_warnings` count. iOS low-memory events
request an additional `sample=low_memory`; repeated warnings coalesce at up to
one sample per second, retaining the event count. Off-main event delivery only
updates an atomic counter; the main thread performs the OS queries and logging.
There is no sampling thread or catchup burst after suspension. Entitlements are
still queried only at startup. These low-rate memory rows remain eligible for
capture after the general 8 MiB debug-log cap, alongside existing fatal/error
lines. A memory kill may happen without a warning or final sample, so missing
warnings do not rule it out.

Each sample now includes these diagnostic rows:

| Row | Coverage |
| --- | --- |
| `[IOS_MEMORY_BREAKDOWN]` | All malloc zones' in-use/reserved bytes and the default Metal device's `currentAllocatedSize`; unavailable Metal queries say `unknown`. |
| `[IOS_ENGINE_MEMORY]` | Engine memory-pool payload used/reserved bytes; excludes block headers and raw DMA allocations. Disabled pools are identified. |
| `[IOS_MEMORY_RAW]` | Live large allocations routed through engine DMA allocators: block count, native usable bytes, largest block, size ranges and measurement coverage. Includes engine block headers and native rounding. |
| `[IOS_MEMORY_POOLS]` / `[IOS_MEMORY_POOL]` | Named pool coverage, selected pools' live/reserved allocation counts and bytes, and changes since the preceding sample. See the limits below. |
| `[IOS_RESOURCE_MEMORY]` | Named texture count/estimated bytes from the asset hash, vertex/index buffer count/bytes, live objects and particles, pause/menu state and logic frame. Texture coverage excludes some procedural, font and render-target resources. |
| `[IOS_AUDIO_MEMORY]` | Retained decoded PCM cache bytes, buffer count, unmatched closes and playback-list sizes; excludes streamed decoder/OpenAL internal allocations. |

The categories overlap and must not be added to produce a total. Compare their
trends against footprint. Sampling does not wait for GPU completion or flush caches.
Named pool tracking retains only the preceding snapshot in fixed storage;
there is no growing history. Engine counters become available after initialization;
all sample categories survive the general debug-log cap.

Named pool snapshots cover up to 1,024 pools using about 272 KiB of fixed storage
on ARM64. Each sample logs at most 16 distinct pools: the eight largest positive
increases in live bytes, four largest live payloads and four largest reserved
payloads, with duplicates combined. Summary `total`, `captured` and `omitted`
fields make partial coverage explicit; aggregate pool totals still cover all pools.
Rows include signed byte/block changes and `baseline=first_sample`,
`previous_sample` or `not_in_previous`. An unseen pool starts from zero only after
the first sample; a newly observed pool is not automatically a leak. Names are
copied while locked, sanitized for one-line logging and flagged if truncated.
The sampler prints after releasing the pool lock and does not allocate tracking
storage, release empty blobs or change the game's allocation/scheduling policy.

Raw allocation sampling walks the existing live lists under the DMA lock, using
the iOS device layer's `malloc_size` query on each original allocation base.
`usable_mib` includes engine block headers and native size-class rounding; it is
neither requested payload nor process footprint. The six size-range fields are
disjoint: for example `le_16k` counts blocks larger than 4 KiB and at most 16 KiB.
`status=partial` and `unmeasured_blocks` identify blocks whose size is unknown;
known bytes then form a partial total. Disabled/unavailable allocators are marked.
`scan_ms` records query time including lock wait, before formatting the row.
No allocation headers, allocation/free paths or retention rules are changed.
The walk uses fixed stack storage, and its work scales with current raw-block count.

These counters identify an allocation route, not the calling subsystem: linked
libraries may use the engine's global `new`, and engine code may allocate directly
outside it. Compare raw-allocation trends with pool and malloc trends before
assigning the remaining growth to a library. Do not add overlapping categories
or assume their difference gives an exact library-only total.

For the next focused test, pause a loaded mission for 15–20 minutes, resume and
issue a move command, then return to the main menu for a few minutes. Exit through
the menu and collect the log.
`game_paused`, `shell_game` and `logic_frame` help distinguish these phases.
These rows report net live allocations, not allocation call stacks; allocations
outside engine pools still require separate investigation if CPU heap keeps rising.

Paused offline live games now coalesce repeated frame-tick and replay-camera
metadata after all client translators run. An idle paused queue retains the
latest tick/camera pair; real commands and changes of originating player remain
ordering barriers. Active play, networking and recorded replay/simulation
playback keep their prior transfers. Replay file encoding is unchanged. The next
log should show the steady paused growth of `GameMessage`, `GameMessageArgument`
and their argument-vector pools disappear; other CPU allocations still need
measurement. Existing pools may retain their reserved capacity after messages
are released. A short recorded skirmish with pause/resume and replay playback is
also useful for verifying the final camera and command behavior on the device.

For a useful comparison, record the times when you pause a stationary match,
resume normal play, and return to the menu. A 20–30 minute session helps reproduce
the previous growth. Returning to the menu need not release reserved allocator
storage; rising in-use allocations and rising reserved space mean different things.

Some Zero Hour editions rely on shared base-Generals archives. If your
installation does not already include `ZH_Generals`, place the base game's
`.big` archives in a `ZH_Generals` subfolder alongside the Zero Hour archives
in the app's Documents directory. Keep the two sets separate: do not overwrite
Zero Hour archives with the base game's files. New builds search this folder
when the primary asset root is Documents. Missing texture names are logged as
`[TEX_MISSING]`; use those reports to distinguish incomplete data from rendering
problems rather than assuming every purple surface is a shader error.

Collect base-game archives on Windows with
[`collect-ios-base-generals.ps1`](../../scripts/build/ios/collect-ios-base-generals.ps1):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\collect-ios-base-generals.ps1 -SourceDirectory "D:\Games\Command and Conquer Generals"
```

Replace the source path with your actual **base Generals** installation. The
script creates `Generals-Base-iOS-Transfer/ZH_Generals` on your Desktop. Copy the
**ZH_Generals folder itself** into the iOS app's Documents directory, alongside
the Zero Hour archives. It collects top-level `.big` files only; the base
archive resolver does not use loose files from this secondary folder. No
Windows executables or extra fonts are needed for this shared-archive step.

To collect **both** games in one operation, use
[`collect-ios-combined-data.ps1`](../../scripts/build/ios/collect-ios-combined-data.ps1).
It defaults to `D:\Command and Conquer - Generals\Command and Conquer Generals`
and its sibling `Command and Conquer Generals Zero Hour`, with output at
`D:\GeneralsZH-iOS-Complete`. Override `-SourceDirectory` (Zero Hour),
`-BaseGeneralsDirectory`, `-DestinationDirectory` or `-FontsDirectory` if needed.
It validates both installations and fonts before creating output, and refuses
existing output folders. The explicitly selected base installation supplies
`ZH_Generals`; an existing copy inside the Zero Hour installation is not merged.
Copy the output folder's **contents**, preserving `ZH_Generals` and `fonts`.

The current build targets direct sideloading. LiveContainer-specific guest-image
path handling was removed at the user's request; it is not a verified hosted-app
configuration. Standalone bundle resource and default Vulkan loading behavior
are retained.

## Unix texture worker

Current builds implement the Unix ThreadClass worker rather than leaving its
start/stop functions as stubs. Texture file loading can run on that worker;
foreground texture creation/finalization stays on the render thread. The
synchronous fallback remains removed. Queue inspection is synchronized and
shutdown joins the worker before taking its background lock. Unix shutdown is
cooperative: the time budget triggers a warning, not unsafe forced cancellation.
An unresponsive worker can therefore delay shutdown. Scheduler priority changes
are best effort and normal Unix scheduling may offer no adjustable range.
The legacy cursor GPU-drawing worker remains disabled on Unix.

Use `python3 scripts/qa/test_unix_worker.py` to run the compiled lifecycle,
queue-concurrency and shutdown-order tests. They exercise production function
bodies and the actual ThreadClass implementation with minimal legacy-header
stand-ins; they do not establish device-level renderer or gameplay correctness.
Retest map loading, texture appearance, sustained gameplay and exit behavior
on the phone before replacing a known-working IPA.

## Native iOS frame callbacks

The current IPA uses SDL's native iOS frame callbacks and returns control to the
native run loop between engine updates. Event handling uses SDL_AppEvent;
frames use a nonblocking render-rate gate instead of a sleeping limiter. Input
routing, touch gestures, lifecycle pause/resume, worker threads and shutdown
fixes are retained.

Investigation-only timers, touch/queue probes, diagnostic buffers, worker-status
messages and startup checkpoints have been removed. SDL is built from its
unmodified pinned source, without the UIKit diagnostic patch. Normal application
logging and error reporting remain. Prior findings are retained in the
[input investigation history](../WORKDIR/audit/IOS_DELAYED_INPUT_SYSTEM_REVIEW_2026-10-25.md).

Verify menu responsiveness, gameplay, text input, background/resume and exit on
the phone. The removal of instrumentation needs device validation because the
probes could influence timing. iOS callback mode supports interactive play;
desktop/headless builds retain the original loop. Run
`python3 scripts/qa/test_ios_native_callbacks.py` for compiled callback/cadence,
event-ownership, gesture and lifecycle checks. These stand-ins do not replace a
full macOS/Xcode build or device testing.


## Manually clear the DXVK state cache

1. Fully close Generals ZH.
2. In Files, open **On My iPhone/iPad > Generals ZH**.
3. Create an empty folder named exactly **Clear DXVK Cache**.
4. Launch the game. The reset runs before DXVK starts.
5. Open **DXVK Cache Reset Result.txt** in the same Files location to check the result.

On success, the request folder disappears. Repeat these steps whenever another
reset is needed. The next run can have shader/pipeline compilation hitches.

The reset removes regular `.dxvk-cache` files directly in the app's Library/Caches
and directly inside its `dxvk-test-<tag>` folders, including the active test cache.
It leaves game data, saves, settings, other caches and directories in place.
Symlinks are not followed. A nonempty request folder is rejected; remove its
contents yourself or create a fresh empty request folder. Failed resets keep the
request for a later attempt and report an incomplete result. An externally
overridden cache location is not deleted or reported as fully cleared.

This resets DXVK's persistent state cache, not every Metal/driver-managed cache.

## Experimental build review defaults

The mod-testing workflow now reuses the `dxvk-test-quad-lists-v1` cache namespace
between IPAs. The session log identifies the executable separately with
`[IOS_BUILD] revision=...`. Graphics strip probes and historical occupancy-shadow
replay default OFF; live gameplay-result validation and parallel ordinary pairs
remain enabled on that branch. Unbatched searches run on the caller, and routes
are materialized directly on main. The old collector and exclusive baseline remain
opt-in experiments. See the [full build review](../WORKDIR/audit/IOS_FULL_BUILD_REVIEW_2026-10-27.md).

Bundled-data startup no longer removes assets from Documents. The Files-based
installation and combined collector remain supported. The CSF parser handles the
reserved header word used by some mods and rejects invalid lengths/short reads.
