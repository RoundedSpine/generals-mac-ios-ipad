# Community Patch iOS branch

`experiment/ios-community-patch` builds the **Full English** Super Patch data from
[TheSuperHackers/GeneralsGamePatch](https://github.com/TheSuperHackers/GeneralsGamePatch).
The upstream project describes version 1.0 as work in progress. This integration
pins source commit `6c7f40d6af6a4babb77a33a4502ec7656446c13e` and its Mod Builder
submodule `90fa9569c4304cc490aef1161f65ba91d9b1e1ef` in
[`source.json`](../../ios/community-patch/source.json).
EA has not endorsed and does not support this product.

## What the branch includes

This branch starts from the current mod-testing engine at `7341715`, with its
stable heap, hierarchical/compact search contexts, complete worker execution,
validation, four-request lookahead, frozen occupancy and quad/strip rendering
changes. The build profile retains the same one-worker-plus-main configuration,
limits and diagnostics as `experiment/ios-mod-testing`. The previously reviewed
warning cleanup is also carried forward; the original checkout is untouched.

Full English includes core, optional and recovered content, including optional
art/audio and gameplay data. This is a data overlay, not another engine or a
Windows executable. **The integration is locally validated; actual Windows asset
conversion, native iOS compilation and device testing remain pending.** No IPA
or remote workflow was started while implementing it.

The Windows Actions job uses the pinned upstream builder and locked Python
dependencies to convert source assets and build only `FullEnglish`. It never
installs or launches a PC copy of the game and requires no retail game files on
the runner. Upstream conversion tools are downloaded with the checksums specified
by its pinned tool configuration. The checked-in API adapter limits both build
and install metadata to FullEnglish while leaving install/uninstall/run operations
disabled. This avoids an upstream pre-build assertion for unbuilt language packs.
It passes the Blender add-on path through an environment variable, so Windows
backslashes cannot become Python escapes, and sets Blender's Python exit code.
Exceptions propagate to the job and are published as Actions annotations.

The builder's raw pack uses file symlinks to its compiled items and loose project
assets. Staging dereferences only links to regular files inside the pinned patch
project, rejects broken/escaping/directory links, and writes regular output files.

The staging tool requires exactly the 15 BIG archives described by the selected
upstream pack. It merges them using the original filename priority: optional
`600_899` overrides core `600_900`, followed by recovered `600_901`. Loose runtime
assets in the compiled pack take precedence. PSD, BLEND and other source assets
are not shipped as substitutes for converted DDS/W3D/CSF data. The overlay carries
a source/profile/hash manifest and upstream license/terms notices.

## Installation and game files

1. Download `GeneralsXZH-iOS-unsigned` from a successful branch Actions run.
2. Sign and sideload its IPA as usual. This branch uses the existing app bundle
   identity; it normally updates that app rather than installing a second copy.
3. Keep your complete **base Generals plus Zero Hour 1.04** data in Documents,
   as for the existing build. The patch is not a substitute for either game.
4. Start a fresh game to test the changed patch data. Vanilla/mod saves and
   replays are not assumed compatible with this gameplay patch.

The patch ships in `GeneralsXZH.app/CommunityPatch`, separate from `GameData`.
The engine excludes that archive from automatic retail-root discovery, loads your
retail archives first, then mounts the patch with archive override priority.
The log should show `[COMMUNITY_PATCH] mounted profile=FullEnglish commit=6c7f40... after_retail=1`.
The build fails if staged resources are missing; a patch-enabled engine rejects
missing/unreadable bundled patch or missing core retail archives instead of
continuing as vanilla. The six required archive basenames are `INI.big`,
`Textures.big`, `W3D.big`, `INIZH.big`, `TexturesZH.big` and `W3DZH.big`. Base
archives may be in `ZH_Generals` or loaded beside the expansion archives. This is
a core-archive presence check, not a checksum audit of every retail file.

Existing engine rules still let loose files in Documents override archive entries.
Use clean retail files for testing: leftover loose mod INIs or art can override
the bundled patch. Startup reports common loose GameData/CommandSet/English CSF
overrides as `[COMMUNITY_PATCH] local_override=... precedence=loose_file`. No user
data is deleted or replaced by the integration.
Optional high-resolution content may change device memory/GPU demands. Launch,
menus, mission/skirmish loading, unit behavior, audio and sustained performance
need device validation; successful packaging is not gameplay verification.

## Build and verification

This branch requires an **explicit build request**. Manually dispatch
`Build iOS unsigned IPA` on `experiment/ios-community-patch`, or push a commit
whose message contains `[build community patch]`. The latter supports environments
without access to GitHub's dispatch API. Ordinary pushes skip the IPA jobs.
Its Windows patch-data job must succeed before
the macOS 15 IPA job can run. Other existing branches skip patch conversion and
retain their previous build behavior. The shared testing profile explicitly
includes both experiment branches so worker/renderer options do not silently turn
off on the patch branch.

The source and builder pins live in `source.json`. CMake copies that source/profile
record into the engine build directory. Packaging requires the matching patch-
enabled CMake cache and the exact configured source/profile, validates the BIG
hash/entry bounds and required gameplay/English text entries, and checks notices.
It refuses absent, corrupted or mismatched resources. Resources are also rejected
when the engine was built without the patch feature. Current embedded memory
entitlement requests and external-signing behavior remain intact.

For a Windows development build with the pinned source and submodule checked out:

```powershell
uv run --locked --project C:\Patch\Tools\GeneralsModBuilder python scripts/build/ios/build-community-patch.py --source C:\Patch
python scripts/build/ios/stage-community-patch.py --source C:\Patch --pack-dir C:\Patch\Patch104pZH\.Build\RawBundlePacks\FullEnglish --output build/community-patch
```

On macOS, build `ios-vulkan` with `-DGENERALS_COMMUNITY_PATCH=ON`, then:

```bash
python3 scripts/build/ios/stage-community-patch.py --verify build/community-patch
GX_COMMUNITY_PATCH_DIR="$PWD/build/community-patch" bash scripts/build/ios/package-ios-zh.sh --dev --unsigned
```

`CommunityPatch-FullEnglish` is also uploaded as the staged data artifact. Do not
copy it into Documents alongside other patch archives when using the integrated
IPA. The engine already mounts its bundled copy.

Run `python3 scripts/qa/test_community_patch.py`,
`python3 scripts/qa/test_ios_packaging.py` and the existing CSF/worker suites for
local validation. CMake and a C++17 compiler must be on PATH. Checks cover BIG
bounds/paths, deterministic priority, source/profile provenance, missing English
text, retail prerequisites, failed and duplicate mounts, loose-file precedence,
recursive-scan exclusion, packaging resources and preserved entitlement requests.
Packaging fixtures use stand-ins for Xcode/codesign; their test ZIPs are not
installable iOS builds. Real conversion and iOS SDK checks remain future Windows/
macOS workflow work, followed by campaign/skirmish, touch/UI, worker and matched
memory/performance tests on device. Use fresh games for changed gameplay data;
vanilla or other-mod saves/replays are not assumed compatible.


Current local validation passed all 36 workflow test modules, including 11 patch
integration cases and 17 packaging cases. The C++ overlay/precedence fixtures also
passed with AddressSanitizer and UndefinedBehaviorSanitizer. These results verify
code paths and generated fixtures; the real conversion/native/device checks above
remain pending.
