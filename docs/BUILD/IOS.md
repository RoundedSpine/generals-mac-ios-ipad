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
report startup checkpoints, asset presence, the engine image path and selected
DXVK config. Asset-free IPAs now also carry the iOS renderer config. See the
[startup review](../WORKDIR/audit/IOS_SIDELOAD_STARTUP_REVIEW_2026-10-24.md) for
verified defects, regression tests and remaining device-validation limits.
