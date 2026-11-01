# FFmpeg ownership repair

Reviewed on `experiment/ios-mod-testing`, starting at `d9b12fbdf`.

## Result

Repair the confirmed failed-setup ownership gaps in the shared FFmpeg decoder,
OpenAL music/speech setup and video audio conversion. Make the Zero Hour CMake
build use the shared implementation and declarations consistently. Keep gameplay,
pathfinding, cache budgets, memory entitlements and ordinary stream scheduling.

These repairs address real defects; they do not establish the owner of the
remaining steady malloc growth in device logs. The last settled paused sample
gained about 24 MiB in nine minutes while measured pool/raw allocations and Metal
bytes remained flat. Repeated setup failures have not been established in that
session. The user's planned long normal-game test remains useful.

## Implementation

- Free the initial 64 KiB AVIO buffer if context creation fails. FFmpeg does not
  consume that allocation on failure.
- Store each codec context in its owning stream before parameter conversion or
  codec opening can fail. Reject null frame and packet allocations.
- Clean partially opened decoder state on C++ exceptions, including a throwing
  stream-vector allocation during the convenience constructor. Forbid copying
  the owning decoder. `open()` consumes its input file on success and failure.
- Scope the current packet reference through read/send errors, invalid stream
  indices and throwing callbacks. On send EAGAIN, drain available output and
  resend the same packet before reading more input. Release accepted input
  before the normal receive loop. Preserve true-EOF state and current EOF policy.
- Retain the incoming audio event until a playing owner exists. Scope streaming
  setup until list publication; assign decoder/stream ownership before later
  operations can fail. Close an input file if decoder allocation throws. Scope
  planar PCM scratch across queue exceptions and check conversion allocation.
- In video setup, keep the file and decoder owned until handoff. Clean partial
  frame storage if video construction throws. Use temporary realloc results in
  both audio conversion branches so failures preserve the original buffer.

## Duplicate implementation investigation

Core's private interface target supplies FFmpeg source files to the Zero Hour
device archive. Zero Hour also listed its own copies as PUBLIC sources, which
propagated them to consumers. The copies had drifted: the old Zero Hour decoder
returned on EOF without setting its declared `m_atEof` state.

Remove the duplicate Zero Hour CMake source entries. Forward its FFmpeg headers
to Core declarations so callers share the same owning types. Preserve existing
FFmpeg feature flags and library linkage. The older source files remain available
for historical project references but are not part of this CMake build.

A generated CMake compile graph using the actual target source declarations
verifies that each FFmpeg implementation compiles exactly once from Core and no
FFmpeg `.cpp` propagates into the final executable as a PUBLIC source. A separate
compiled check includes both Zero Hour forwarding headers and verifies the
noncopyable decoder API. This is build-graph validation, not an iOS link-map dump.

## Validation

Run the portable regression suite with CMake and a C++17 compiler on PATH:

```sh
python3 scripts/qa/test_ffmpeg_ownership.py
python3 scripts/qa/test_audio_cache.py
python3 scripts/qa/test_openal_stream.py
python3 scripts/qa/test_build_warning_fixes.py
python3 scripts/qa/test_ios_packaging.py
```

The new suite compiles production method bodies against counted, faulting
providers. Seven cases cover both streams' partial setup failures, native handle
and input ownership, throwing stream storage and callbacks, packet errors and
same-packet retry, streaming constructor/callback failures, PCM scratch cleanup,
video factory/partial-constructor cleanup, failed resizing, shared headers and
the generated CMake source graph. The iOS workflow runs this suite before building.
It does not require FFmpeg/OpenAL SDKs. All seven cases pass normally and with
AddressSanitizer/UndefinedBehaviorSanitizer. Existing audio cache (six), streaming
(seven), build-warning (thirteen) and IPA packaging (twelve) cases pass.

For a real-codec check, build FFmpeg tag `n8.1.1` locally with WAV demuxing and
PCM S16LE, IMA ADPCM WAV and Microsoft ADPCM decoding. This matches the engine's
selected FFmpeg source version, though not Apple's compiler/platform or the full
vcpkg feature set. Compile the actual repaired decoder methods against those
libraries with ASan/UBSan and injected API failures. Results:

- 1,000 PCM cycles: 16,000 callbacks, 8,000,000 decoded samples.
- 100 IMA ADPCM cycles: 400 callbacks, 816,400 decoded samples.
- 100 Microsoft ADPCM cycles: 400 callbacks, 814,400 decoded samples.
- Zero surviving input files; repeated close is safe. No sanitizer findings.
- AVIO/codec/frame/packet setup failures close owned state. Demux EIO makes no
  codec send. Send EAGAIN retries input; send errors and throwing frame callbacks
  leave the packet reference clear. Invalid input closes cleanly.

ADPCM totals include block padding and are not presented as sample-accurate
duration equivalence. FFmpeg libraries in this additional native check are not
themselves sanitizer-instrumented; the wrapper/harness are, and their allocations
remain visible to leak detection. Investigation/native probe artifacts are saved
outside the repository under `/workspace/artifacts/ffmpeg-ownership-audit-d9b12fb/`.

Actual iOS compilation and device playback/memory-trend verification remain the
next build's checks. This is not an all-codec or hour-long device leak proof.

## Deliberate limits

Demux EOF still does not flush delayed codec output; a future decoder-correctness
change should test that behavior with codecs that actually delay frames. The
OpenAL requires-data callback still distinguishes EOF from decode errors as
before; persistent terminal-error policy is not broadened here. No additional
device logging, cache purges, thread changes or audio disabling were introduced.
