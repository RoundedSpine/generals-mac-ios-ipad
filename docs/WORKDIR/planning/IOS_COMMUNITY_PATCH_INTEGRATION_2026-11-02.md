# Community Patch investigation on the current iOS mod-testing base

Reviewed 2 November 2026; local integration completed after this investigation.
Implementation and build instructions: [Community Patch iOS guide](../../BUILD/IOS_COMMUNITY_PATCH.md).
The feature is opt-in; real converted assets and native/device validation remain pending.

## Branch and scope

- New local branch: `experiment/ios-community-patch`.
- Base: `experiment/ios-mod-testing`, commit
  `7341715fdbdf5c0f300cfa22df2c6af45f95fd11`.
- Separate checkout: `/workspace/generals-community-patch-ios`.
- The original checkout remains on `experiment/ios-mod-testing`, including its
  uncommitted warning fixes. They remain untouched there. Their reviewed code/test
  changes were separately carried into this branch in local commit `8066a7d0e`.
- Continue the user's previously selected **Full English** profile.
- No push, workflow dispatch, patch-data build or IPA build was performed.

The old `community-patch-ios` branch is a reference, not the base of this branch.
Its common ancestor with current mod testing is `a9c298048`; it predates the current
complete worker path, memory fixes, diagnostics and entitlement packaging.

## Upstream identity and what it contains

Official repository: <https://github.com/TheSuperHackers/GeneralsGamePatch>.
At review, its default `main` branch points to:

```text
patch:   6c7f40d6af6a4babb77a33a4502ec7656446c13e
builder: 90fa9569c4304cc490aef1161f65ba91d9b1e1ef
profile: FullEnglish
```

The builder pin is the actual `Tools/GeneralsModBuilder` gitlink. Both commits
match the pins already used on our older Community Patch branch. Switching the
source URL from the RoundedSpine fork to official upstream does not, at these
revisions, supply a newer patch payload. The upstream README still describes
version 1.0 as work in progress and requires an original Zero Hour 1.04 installation.

This is primarily a **game-data patch**, not a replacement engine or a worker
implementation. The Zero Hour project is `Patch104pZH`; do not combine its sibling
`Patch108pCCG` project into the Zero Hour overlay. Both original Generals and Zero
Hour retail data remain necessary for our engine, as already established.

Source-tree inspection found 737 edited core files, including 226 INIs, 80 window
files, 85 W3D files and 211 PSDs. Optional content contains 2,395 source files,
including 1,760 WAVs and 576 PSDs. These counts span languages and source inputs;
they are not Full English output counts or runtime memory estimates.

## Selected package and conversion

FullEnglish selects 16 bundle items. Fifteen produce BIG archives; CoreMisc is
loose release material. It adds optional audio/language/INI/textures/W3D content
and recovered textures to CoreEnglish's gameplay, art, maps, text and UI fixes.

| Filename prefix | Archive group | Count |
| --- | --- | ---: |
| `600_899_SuperPatch_` | Optional Audio, AudioEnglish, INI, LangEnglish, Textures, W3D | 6 |
| `600_900_SuperPatch_` | Core Audio, AudioEnglish, INI, LangEnglish, Maps, Textures, W3D, Window | 8 |
| `600_901_SuperPatch_` | RecoveredTextures | 1 |

The existing staging helper reproduced these exact 15 archive names from the
official manifests. Keep filename priority: optional precedes core, then recovered;
installed loose runtime files take precedence. Do not simply overlay all source
folders or change the order while merging output archives.

Upstream converts PSD/TGA/TIFF assets to runtime textures, STR to CSF, and any
selected Blender models to W3D, then creates BIG archives. Its configured Windows
tools include crunch 1.04, GameTextCompiler 1.1, GeneralsBIGCreator 1.3, Blender
3.4.1 and the W3D add-on. Tool downloads have configured SHA-256 checks. Builder
Python requires 3.12 or newer and supplies `uv.lock`.

Use a Windows asset-conversion job followed by the existing macOS iOS engine job.
Only converted data and notices belong in the app; Windows converters/installers
do not. Building through `RunWithConfig` can omit installing, uninstalling or
running the PC game. The previous adapter's selected-pack build/install metadata
and Blender-path handling remain relevant at the identical builder revision.
The builder's raw pack uses symlinks; staging must materialize regular files and
retain the existing checks on broken links and links outside the pinned project.

## What is reusable, and what must be adapted

| Area | Finding / required treatment |
| --- | --- |
| Builder and staging helpers | Reuse the older branch's focused helpers and failure handling after reviewing their changes. Update source identity to official upstream while keeping immutable revisions. |
| Engine and pathfinding | Keep current mod-testing engine code. This patch supplies INI/data changes and does not justify reverting or replacing our pathfinding implementations. New gameplay data still needs worker/result-validation testing. |
| CI feature selection | Current workflow enables most experiments only when `github.ref_name == 'experiment/ios-mod-testing'`. On this new branch a manual dispatch would silently disable them. Extend the profile selection deliberately before any build. Preserve context, occupancy, complete-worker, reuse, pool, four-request, lookahead, zone, frozen-occupancy, quad and existing diagnostic settings. |
| Workflow reuse | Adapt only the patch-data producer/artifact dependency into the current workflow. Do not replace it with the older workflow, which lacks current checks, fork/dependency handling and worker configuration. Keep macOS 15 for the iOS job. |
| Packaging | Add validated `CommunityPatch` resources to the current packager. Preserve its embedded ad-hoc entitlement requests, request verification, exported entitlements and current dylib/framework handling. Replacing it with the old packager would lose newer fixes. |
| Archive mount | Add an opt-in overlay mount after retail Zero Hour and base Generals loading, with override priority. Exclude the overlay from generic retail-root discovery. Keep initialization/ownership cleanup correct on failed setup. |
| Retail detection | The old mount checks the primary-root success flag; that flag alone does not prove both retail datasets are complete. Retain meaningful base-data validation/logging rather than treating the overlay as a retail substitute. |
| Loose files | Existing FileSystem opens local files before archives. Loose mod INIs, textures or CSFs in Documents can mask a bundled patch. Test against clean retail content, without deleting user data. |
| Text | Current CSF parsing already has the reserved-word correction and stronger bounds/short-read handling than the old Community Patch branch. Keep the current implementation; do not overwrite it with the older parser. |
| Saves/replays | Gameplay definitions change. Use fresh patched games for acceptance; do not assume vanilla, Reimagined-data or other mod saves/replays are interchangeable. |

The new branch now implements the opt-in mount, compiled-data builder/stager,
manual workflow configuration and package verification. No converted game-data
payload is checked into the repository. Patch resources must be built and validated
before an enabled engine can be packaged; merely switching branches does not alter
the currently installed app.

## iOS validation and memory considerations

The runtime formats match formats our current engine already reads; the initial
integration does not require a new graphics backend or Windows executable loader.
That is source-level feasibility, not proof that every patched asset renders or
every changed INI/UI interaction behaves correctly on iOS.

Full English's optional higher-resolution art and restored audio can increase
resource demand. The current baseline still has unexplained CPU malloc growth;
the patch is not a demonstrated memory fix. Measure after warm-up against the
same map, faction, camera activity and test duration. Track CPU malloc, footprint,
Metal resources, engine raw/pool bytes and decoded audio separately; do not infer
a leak or performance improvement solely from a different workload's peak.

For a future compiled overlay, verify archive hash/profile identity and representative
INI/CSF/art entries before packaging. On device, confirm the logged patch source
and profile, missing-label behavior, touch-driven menus/control bar, campaign and
skirmish load, ordinary movement and tight spaces/bridges, changed unit behavior,
EVA/audio, match reset and sustained memory/performance. The engine's existing
validation rejections remain meaningful with changed unit and locomotor data.

Carry upstream GPL/EA terms and relevant asset notices with the converted overlay,
and publish the exact source/build provenance. Preserve the upstream required
statement: “EA has not endorsed and does not support this product.”

## Investigation checks performed

- Verified official default HEAD and the actual builder gitlink against the
  previously pinned integration. The separately cloned builder also matches.
- Inspected official bundle definitions, source formats, configured conversion
  tools and build API behavior. Derived all 15 expected archives from those manifests.
- Compared old integration hooks against current asset discovery, local-file
  precedence, CSF handling, packaging and branch-conditioned build options.
- Re-ran seven existing Community Patch helper checks on the old integration
  reference: selected-pack metadata, Windows path handling, BIG bounds/paths,
  fixture merge priority/provenance, incomplete packs, symlinks and mount ordering.
- Re-ran six CSF regression checks on the new branch's current engine base.

All 13 existing checks pass. The staging tests use small generated archives; they
are not a real Full English asset build. No retail game was installed, no conversion
tools were launched, and no iOS gameplay compatibility claim follows from them.

## Implementation status

- [x] Carry the reviewed warning fixes separately while preserving their original checkout.
- [x] Add the official-source pinned Full English builder/stager and attribution.
- [x] Preserve the current worker/renderer profile on both testing branches.
- [x] Add source/profile/hash-checked packaging while retaining memory requests.
- [x] Mount after six core retail archives; reject missing/failed/duplicate mounts,
  exclude recursive discovery and report common loose-file overrides.
- [x] Preserve current CSF handling and validate loose-file/archive precedence.
- [x] Validate all 36 local workflow test modules, including 11 patch integration
  and 17 packaging cases; the C++ patch fixtures also pass with ASan/UBSan.
- [ ] Build actual Full English conversion outputs on Windows and inspect the result.
- [ ] Build the native IPA only when the user lifts the no-new-build constraint.
- [ ] Test fresh campaign/skirmish games, menus/touch, audio, worker behavior and
  matched sustained memory/performance on device.

No remote push, workflow dispatch or native IPA build was performed. Existing
helper tests use small generated payloads and stand-in packaging tools; they do
not establish compatibility of the real converted assets.
