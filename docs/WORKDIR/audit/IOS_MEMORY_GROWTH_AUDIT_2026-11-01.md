# iOS gameplay memory growth audit — 1 November 2026

Baseline: `experiment/ios-mod-testing`, `1cf4ae575`. This is a source audit and
compiled-fragment investigation, not an on-device heap or Metal allocation trace.
The findings below describe that baseline. Follow-up implementation status is
recorded at the end; on-device impact remains unmeasured.

## Observed session

The supplied log matches `~1cf4ae5` and contains 59 memory samples. Increased
Memory Limit is true in the executing standalone Generals process; EVA is absent.
The session exits with code 0, with no recorded low-memory warning.

| Uptime | Process footprint (MiB) | Process headroom (MiB) |
| --- | ---: | ---: |
| 31.414 s | 1,108.0 | 5,036.0 |
| 601.500 s | 1,467.0 | 4,677.0 |
| 1,201.581 s | 2,161.8 | 3,982.2 |
| 1,711.652 s | 2,746.0 | 3,398.0 |

The post-loading increase is 1,638 MiB over approximately 28 minutes, or
58.49 MiB/minute. Every successive post-loading sample is larger. Footprint plus
headroom is 6,144 MiB throughout these observations; this is not a promise that
future process policy or available memory will remain unchanged.

The existing log cannot identify which allocator or resource class grew. It
does not record live texture bytes, Metal resource bytes, CPU heap usage versus
reserved space, audio PCM residency, or live gameplay-object counts.

## Findings

### 1. Graphics caches and command pools: highest profiling priority, owner unproven

The active chain is WW3D → D3D8/D3D9 DXVK → MoltenVK 1.4.1 → Metal. iOS unified
memory means graphics resources and driver allocations can contribute to the
same process footprint as engine heap allocations.

- `references/fbraz3-dxvk/src/d3d9/d3d9_fixed_function.cpp:2551` caches shader
  modules by rendering state. Pipeline caches similarly grow when new state
  combinations are encountered (`src/dxvk/dxvk_graphics.cpp:1316`). Cache growth
  is possible; there is no device evidence here showing shader/pipeline counts.
- `src/dxvk/dxvk_cmdlist.cpp:209` resets Vulkan command pools with flags zero.
  MoltenVK 1.4.1's `MVKCommandPool::reset()` trims command-type pools only when
  `VK_COMMAND_POOL_RESET_RELEASE_RESOURCES_BIT` is requested. This permits peak
  command storage to remain cached across frames. It does not establish that
  command storage grows without bound.
- DXVK's allocator deliberately retains some empty chunks, allowing four times
  the normal allowance for mapped pools (`src/dxvk/dxvk_memory.cpp:1517`). It also
  has budget checks and age-based reclamation; freed Vulkan resources do not
  automatically imply an immediate equal decrease in process footprint.
- Command lists have an explicit completion/reset/recycle path
  (`src/dxvk/dxvk_queue.cpp:294`), and their recycler holds 16 cached lists
  (`src/dxvk/dxvk_device.h:616`). The command-stream thread releases each executed
  chunk (`src/dxvk/dxvk_cs.cpp:262`). No missing release was identified in those
  inspected normal paths.

I also inspected the exact MoltenVK source tag used by packaging: `v1.4.1`,
commit `db445ff2042d9ce348c439ad8451112f354b8d2a`. Its `MVKQueue.mm:70` already
wraps submission execution in an autorelease pool; deferred command encoding is
also wrapped in `MVKCommandBuffer.mm:265`. A blanket claim that our graphics
threads have no autorelease protection is therefore unsupported. This does not
prove every possible native allocation path is free of retention.

**Interpretation:** graphics allocation/residency and pipeline/command caches are
important candidates to measure. The source review has not proven a DXVK or
MoltenVK leak, nor established that a cache-policy change would fix this run.

### 2. Unused texture eviction is disabled by the current display policy

`GeneralsMD/Code/GameEngineDevice/Source/W3DDevice/GameClient/W3DDisplay.cpp:967`
sets `WW3D::Set_Thumbnail_Enabled(false)`. The aged-unused-texture invalidator in
`Core/Libraries/Source/WWVegas/WW3D2/texture.cpp:138` immediately returns when
thumbnails are disabled. Named textures remain referenced by the asset-manager
hash (`GeneralsMD/Code/Libraries/Source/WWVegas/WW3D2/assetmgr.cpp:1127`).

Unused asset cleanup exists at display reset (`W3DDisplay.cpp:1150`), with
reference-count-based texture release in `assetmgr.cpp:1176`. This is retention
policy rather than proof of a lost owner. Discovering more unit/effect/terrain
textures during a match can increase residency. A fixed set should eventually
stabilize; the log does not count the set or report whether exploration changed.

Do not simply enable thumbnails as an eviction fix: thumbnail generation/loading
has additional behavior. A mobile byte budget and eviction policy need separate
review and measurements.

### 3. Audio cache: two reproduced normal-path defects

Active code: `Core/GameEngineDevice/Source/OpenALAudioDevice/OpenALAudioCache.cpp`
and `.h`; the OpenAL source list is selected by `Core/GameEngineDevice/CMakeLists.txt`.

**Reference count underflow.** `OpenAudioFile::m_openCount` starts at zero
(`OpenALAudioCache.h:63`). Cache hits increment it (`.cpp:124`), but successful
first loads insert the new entry without setting the first borrow to one
(`.cpp:176`). The first `closeBuffer()` decrements zero (`.cpp:190`), wrapping the
unsigned value to 4,294,967,295. Idle entries can consequently appear busy to
eviction (`.cpp:260` and `278`). The filename-only duration query also performs
this open/close sequence (`OpenALAudioManager.cpp:2788`).

**Decoded memory is undercounted for compressed input.** `decodeFFmpeg()` adds
decoded frame bytes to `m_fileSize` (`OpenALAudioCache.cpp:48`) and uploads that
PCM buffer to OpenAL. `getBufferForFile()` then overwrites this count with the
input file size (`.cpp:163`). The nominal 14 MiB cache cap therefore budgets input
bytes, rather than decoded sample storage. For uncompressed input the difference
may be small; for compressed input it may be substantial. Actual OpenAL internal
storage can also differ from the PCM payload size.

A compiled reproduction using these actual three method bodies, with stand-in
file/decoder/OpenAL providers, produced:

```text
audio uploaded_pcm_bytes=8192 budgeted_bytes=1024 initial_open_count=0
audio after_first_close_count=4294967295
```

ASan/UBSan reported no unexpected harness error. These outputs establish the
accounting and lifetime defects, not an eightfold ratio for the user's assets.
The input-byte cap still limits the selected cache contents, so these bugs alone
have not been shown to explain 1.6 GiB of growth.

Recommended repair: initialize the first borrow, protect unmatched closes,
budget retained decoded bytes, and test cache hits, simultaneous borrowers,
duration-only requests, eviction and allocation/decode failure rollback together.

### 4. Legacy WW3D object pool: reproduced 64-bit layout corruption

`Core/Libraries/Source/WWVegas/WWLib/mempool.h:285` reserves a pointer-sized chunk
header and writes the previous-chunk pointer into it. At line 290 it advances
`BlockListHead + 1`, where `BlockListHead` is `uint32*`.
`bittype.h:52` makes `uint32` four bytes on Apple/Linux; pointers are eight bytes
in this build. The first object starts four bytes into the eight-byte header,
overlaps the chunk link, and is misaligned for pointer-bearing types.

The active renderer uses this allocator for `PolyRenderTaskClass` in
`Core/Libraries/Source/WWVegas/WW3D2/dx8renderer.cpp:99`. Compiling the actual pool
template with an eight-byte-aligned node on a 64-bit host reproduces a UBSan
misaligned-pointer-store error. Platform locks were replaced only in this
single-threaded harness; allocation/linking code was unchanged.

This is a serious correctness defect worth an isolated repair with alignment,
multi-chunk, reuse and destruction tests. It is **not established as the source
of the regular RSS slope**: normal free-list reuse and higher-level retention
must still be measured. Fix the local header/object layout; do not widen the
shared fixed-width `uint32` typedef.

### 5. Depth texture helper leaks a COM reference; observed-session relevance low

`Core/Libraries/Source/WWVegas/WW3D2/dx8wrapper.cpp:3017` calls `AddRef()` after a
successful `CreateTexture()` in `_Create_DX8_ZTexture()`. The owning
`ZTextureClass` adopts the returned pointer (`texture.cpp:1219`); its base
destructor releases it once (`texture.cpp:114`). The tracker does not hold an
independent COM owner that balances the extra reference.

The actual helper body with a standard COM-counting stand-in produces:

```text
depth_texture after_create_refs=2
depth_texture after_owner_release_refs=1
```

The helper is reachable from the render-target-with-depth overload and reset
tracker. I did not find an active gameplay caller of that six-argument overload
in the inspected game/device sources. Treat this as a confirmed latent leak,
not a demonstrated per-frame or per-unit leak in this session.

### 6. Ordinary engine pools retain their peak allocations

`Core/GameEngine/Source/Common/System/GameMemory.cpp:1728` returns released blocks
to their pool without returning an empty backing blob to the OS. `releaseEmpties()`
exists at line 1790, but no caller was found. WWLib object pools likewise retain
chunks until pool destruction. Live gameplay objects, particles and render-task
peaks can therefore leave resident reserved memory after individual objects die.

This is expected allocator behavior, not automatically a leak. Sample used bytes
and reserved bytes separately before changing it; aggressive release can add
allocation stalls to gameplay.

### Secondary failure-path leaks

- `OpenALAudioManager.cpp:793` allocates an `FFmpegFile`, but on `open()` failure
  cleans up `audio` before assigning the decoder to its owner at line 858. The
  decoder object is not deleted on that branch. Internal decoder cleanup in
  `open()` does not delete the outer object.
- `Core/GameEngineDevice/Source/VideoDevice/FFmpeg/FFmpegFile.cpp:75` allocates the
  64 KiB AVIO buffer before `avio_alloc_context()`. If AVIO-context allocation
  fails, `close()` has no pointer to that raw buffer. Codec parameter/open errors
  also occur before the new codec context is assigned to `m_streams`.

These are source-visible ownership gaps under failures. The log does not show a
rate of such failures that would explain the continuous observed growth.

## Recent worker and diagnostic changes checked

- Two persistent participant arenas, each 2,804,560 bytes in the device log;
  four logical primary result slots, with bounded fallback ownership.
- 30,000 search-record capacity; bounded observation logs and lookup storage;
  generation reset reuses storage rather than retaining past searches.
- Joined callbacks are cleared after all participants finish. Completed paths
  use owning pointers until transferred or discarded. Existing paths held by live
  units are a separate quantity and should be counted with live units.
- Timing summaries retain four ranked samples; strip observations use fixed
  arrays. The periodic memory logger stores scalar counters, not sample history.
- Inspected normal render tasks and surface/buffer wrappers have matching
  releases; texture-loader task recycling calls its cleanup routine.

These checks make an ever-growing scratch-context or diagnostics-history list a
weaker explanation than resource residency. They do not prove every pathfinding
caller or gameplay-object lifetime is leak-free.

## Recommended next implementation

1. Repair the reproduced 64-bit pool layout and audio-cache defects in isolated
   changes with regression cases. Keep the latent depth-texture fix separately
   identifiable; it is not the lead explanation for the device slope.
2. Extend the existing 30-second sample with aggregate libmalloc in-use/reserved
   bytes, Metal `currentAllocatedSize`, live object/drawable/particle counts,
   asset texture count/bytes, vertex/index buffer count/bytes and decoded audio
   cache bytes/borrow counts. Asset-hash texture statistics exclude some
   procedural/font/render-target textures, so label their coverage explicitly.
   Heap, Metal resource and process footprint numbers overlap; compare trends
   rather than adding them into a supposed total.
3. If Metal grows while engine resource counts and CPU heap stay flat, inspect
   DXVK basic heap statistics, pipeline counts and command-pool retention. DXVK's
   detailed allocation dump is documented as expensive; do not sample it per
   frame. Avoid adding GPU-idle waits or frame-by-frame cache purges to measure
   memory, since those would change the workload and introduce stalls.
4. Compare a paused stationary match, normal play, and a return to the menu.
   Record the transition times so persistent cache residency can be separated
   from simulation growth and temporary peaks. A menu return alone need not
   return all reserved memory to the OS.

The reproduction script is saved as
`/workspace/artifacts/ios-memory-audit/reproduce.py`. Run it with the repository
path as its optional argument. It asserts the observed **baseline defects** and
expects the pool UBSan failure; it is not a passing regression test for repaired
code. No Apple signing credentials, retail assets or real GPU/audio device are
used by the harness.

## Follow-up implementation — 1 November 2026

- Repair the WWLib chunk header/payload overlap and align every free-list slot,
  including over-aligned and odd-sized types. Keep locking, reuse and retention.
- Repair OpenAL first-borrow accounting and unmatched-close underflow. Charge
  actual decoded PCM to the existing 14 MiB budget, bound a single decoded clip,
  and roll back file/decoder/buffer/budget ownership on admission failures.
  Retire the decoder after upload; streaming policy remains unchanged.
- Extend the existing sample with aggregate malloc in-use/reserved bytes,
  optional public Metal device accounting, engine pool payload used/reserved,
  asset-hash textures, vertex/index buffers, live objects/particles and audio
  cache/playback counts. Keep main-thread throttling and coalesced warnings.
  Queries do not wait for the GPU or change cache retention. No history is kept.
- Add `test_wwlib_pool.py`, `test_audio_cache.py` and `test_memory_counters.py` to
  CI; extend the native diagnostic fixture with Metal failure/ownership and
  category-sampling cadence checks. Local pool/audio/counter fixtures and the
  native diagnostic fixture pass with AddressSanitizer/UndefinedBehaviorSanitizer.

The latent depth-texture reference, FFmpeg failure-path gaps and renderer/cache
retention policies remain separate findings. Do not infer that these repairs
explain or eliminate the 58.49 MiB/minute device slope. The next long-session log
must identify which categories continue to rise. Heap, Metal, pool and footprint
measurements overlap; texture/audio rows intentionally describe narrower coverage.
