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

The unsigned artifact includes `GeneralsXZH.entitlements` next to the IPA.
Configure your signing tool to use those entitlements and a compatible
provisioning profile. The file alone does not activate them: unsigned packages
have no signed entitlement grant, and some sideloading tools strip unsupported
keys. Verify the final signed app's entitlements when possible. On a Mac, use
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
