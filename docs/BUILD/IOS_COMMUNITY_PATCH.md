# Community Patch iOS branch

`community-patch-ios` builds the **Full English** Super Patch data from
[RoundedSpine/GeneralsGamePatch](https://github.com/RoundedSpine/GeneralsGamePatch).
The upstream project describes version 1.0 as work in progress. This integration
pins source commit `6c7f40d6af6a4babb77a33a4502ec7656446c13e` and its Mod Builder
submodule `90fa9569c4304cc490aef1161f65ba91d9b1e1ef` in
[`source.json`](../../ios/community-patch/source.json).
EA has not endorsed and does not support this product.

## What the branch includes

The branch starts from engine experiment `a9c298048` and retains its heap,
hierarchical search, single-threaded search-context/allocator and verified quad
changes. Workers stay disabled. Full English includes the upstream core, optional
and recovered content, including optional art/audio and gameplay data. This is a
content patch integration, not a merge of another engine or a Windows executable.

The Windows Actions job uses the pinned upstream builder and locked Python
dependencies to convert source assets and build only `FullEnglish`. It never
installs or launches a PC copy of the game and requires no retail game files on
the runner. Upstream conversion tools are downloaded with the checksums specified
by its pinned tool configuration. `--debug` makes build errors propagate instead
of prompting for interactive input.

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
The log should show `[COMMUNITY_PATCH] mounted FullEnglish overlay after retail data`.
The build fails if staged resources are missing; a patch-enabled engine rejects
missing retail roots or a missing/unreadable bundled patch instead of silently
continuing as vanilla.

Existing engine rules still let loose files in Documents override archive entries.
Use clean retail files for testing: leftover loose mod INIs or art can override
the bundled patch. No user data is deleted or replaced by the integration.
Optional high-resolution content may change device memory/GPU demands. Launch,
menus, mission/skirmish loading, unit behavior, audio and sustained performance
need device validation; successful packaging is not gameplay verification.

## Build and verification

Pushes to `community-patch-ios` trigger the Windows patch-data job followed by the
macOS IPA job. Failure to build/stage the selected patch prevents the IPA job.
Other existing branches skip the patch job and retain their prior configurations.
The patch source and builder revisions are immutable until `source.json` is
intentionally updated. The workflow uses the repository named in that file.

For a Windows development build with the pinned source and submodule checked out:

```powershell
uv run --locked --project C:\Patch\Tools\GeneralsModBuilder generalsmodbuilder --debug --build-pack FullEnglish --release --config-list C:\Patch\Patch104pZH\ModJsonFiles.json C:\Patch\Patch104pZH\Scripts\Windows\WindowsTools.json
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

Local automated checks cover BIG bounds/path handling, deterministic merge
priority, pin/profile checks, missing artifacts, overlay-after-retail loading,
recursive-scan exclusion and IPA resource layout. Windows conversion and iOS SDK
compilation cannot be run in the Linux workspace; Actions and device tests provide
those remaining checks.
