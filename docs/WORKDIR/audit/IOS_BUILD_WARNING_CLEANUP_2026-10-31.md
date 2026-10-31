# iOS build warning cleanup — 31 October 2026

## Baseline and scope

Use the supplied `logs_111547404319.zip`, building b48b9724400fbd9f602337d033daf8dfea79cf71
on the testing branch. It contains 40,988 file/line compiler warning rows and
4,167 distinct file/line/message combinations, plus driver, linker, configuration
and action-runtime diagnostics. The new report recognizes 40,996 diagnostics in
the complete job transcript; it does not count Node runtime deprecations as C++
compiler warnings. Many diagnostics repeat from a single shared declaration or
macro across hundreds of compilation units.

The current task is the iOS unsigned IPA build. Keep macos-15 ARM64, the vcpkg
revision, dependency versions, game data, rendering options and four-request/
one-background-worker configuration. This is a broad warning cleanup, not a
pathfinding algorithm change or an assertion of cross-platform warning-free builds.

## Root causes and changes

- Memory-pool glue: remove unreachable null returns after `throw ERROR_BUG` and
  make the forbidden base allocation throw. Match standard global delete
  exception specifications in both declarations and definitions. Valid pool
  allocation and constructor-failure cleanup retain their existing behavior.
- INI layouts: retain the compiler-supported offset extension used by polymorphic
  record parsing. Scope `-Wno-invalidoffsetof` to modern non-MSVC C++ compilation.
  Do not rewrite the layouts or replace their offsets with guessed values. This
  is the only explicit diagnostic exception added to engine compilation.
- External SDK boundaries: classify DirectX/native headers as SYSTEM includes in
  engine targets and in the iOS Meson machine file. Keep diagnostics on engine
  implementations and the DXVK implementation sources. Supply fallback platform
  macros only when the SDK has not already supplied them.
- Existing virtual contracts: add 139 reported `override` specifiers across twelve
  headers. No signatures or virtual ordering change as a result of these keywords.
- Partial enum switches: give 176 reported switches explicit no-op default arms
  at their entry. Previously unhandled values still leave the switch without
  changing state; handled cases and fallthrough paths remain intact. Compression
  NONE additionally states its previous zero/original-length result explicitly.
- Inline linkage: make the three path-cell accessors with `.cpp`-only definitions
  ordinary externally linked functions. Optimizers remain free to inline calls
  within the implementation unit; other translation units now have valid
  declarations and linkable definitions.
- Formatting: replace reported unbounded sprintf/vsprintf calls with bounded
  snprintf/vsnprintf using verified destination-array sizes and the existing
  legacy stdio adapter. File::print rejects errors/oversize without writing beyond
  its buffer. Correct float, DWORD, wide-string and profiler-width formats.
  Preserve the old MSVC profiler format branch. Normal fitting output is retained;
  oversized output is bounded rather than overflowing memory.
- 64-bit values: transport integer GUI cookies through intptr_t and logical audio
  event pointers through uintptr_t end-to-end. Do not truncate pointer-bearing
  audio callback arguments to uint32.
- Enum domains and sentinels: use the corresponding drawable/shroud/depth-format
  constants, explicitly compare custom AI state numbers, and store the old script
  conversion table's -1 terminator as an integer. Preserve the effective no-op of
  the contradictory ground-layer/clear-cell predicate rather than enabling a new
  movement exception. Preserve the existing no-op guard-state load callbacks;
  their accidental local function declarations did not invoke onEnter.
- Lifetimes and predicates: explicitly free opaque GUI storage, initialize HUD
  cameo pointers to null, test the actual first video plane rather than an array
  object's address, remove always-true array-address checks, and use the intended
  byte-width filesystem sentinel. Retain existing expression precedence and
  switch behavior while removing unused expressions and clarifying assignments.
- Header casing: rename the expansion File header to file.h, matching its callers
  and the equivalent Core header. Do not create another competing File declaration.
- Obsolete source advisories: preserve old implementation notes as comments,
  remove nested comment-open tokens and express the old integer lighting-cutoff
  truncation explicitly. These do not implement the old platform diagnostic stubs.

## Pinned dependency adapters

Keep fixes in reviewed tracked patches, not edits under build/_deps. The existing
iOS DXVK adapter already consumes a tracked patch against submodule 46a3bc01;
apply its warning patch independently through the same pinned iOS source path.
The gitlink and upstream source versions remain unchanged. These adapter patches
have not been published to the upstream repositories.

- SDL_image 3.4.0, unchanged SHA256: use UniformTypeIdentifiers conformance on iOS
  deployment targets >=14, preserving the original argument order and exact UTI
  identifiers. Link its framework for those targets and use an autorelease pool
  for temporary Objective-C objects. Keep the existing decoder/backend selection.
- GameSpy 07e3d15: compare its internal firewall/list states in their own enum
  domains and retain GP_MORE/GP_DONE in a GPEnum before callbacks can change the
  callback result. GP_MORE is 0x0600, not a boolean.
- DXVK 46a3bc01: represent the invalid sampler mapping as DWORD/UINT32_MAX, converting
  to the sampler enum only after validation. Retain valid mappings and unmapped
  texture-stage routing. Remove an unused shader counter, mark existing priority
  overrides, and avoid GNU static-runtime flags on Darwin.

The shared CMake patch helper accepts pristine or already-patched sources and
rejects mismatches before mutation. A repository ceiling prevents tarball sources
inside the engine checkout from accidentally using the parent repository's path
root. Actual pinned SDL_image/GameSpy patches were applied locally; both modified
GameSpy components compile on the host. Those host GCC builds retain unrelated
upstream string-parameter annotation warnings; they are not the iOS Clang baseline.
The DXVK patch applies/checks against the pinned local source clone.

## Build configuration and reporting

Skip host macOS Vulkan SDK discovery for iOS; the explicit cross-file/framework
configuration remains authoritative. Enable available CMake archive-deduplication
policies so capable linkers avoid repeated archives without removing required
rescans on other platforms.

Upgrade upload-artifact to v6/Node 24. Replace the deprecated Node-based vcpkg
setup action with direct bootstrap of the same verified commit, keeping metrics
disabled and the existing binary cache. Install only missing Homebrew tools;
handle the empty list under the hosted shell's nounset behavior.

The original logs remain unfiltered. `report-build-warnings.py` produces
`logs/ios-warning-summary.json`, a step summary and a bounded notice containing
counts by diagnostic category. It counts configuration, SDL and engine logs and
labels missing/failed builds incomplete, so a failed compile cannot be reported
as a verified clean build. The diagnostics artifact includes this report. Patch payloads retain upstream
context whitespace; source-code whitespace checks exclude those literal unified
diffs, whose applicability is checked separately.

## Verification and remaining boundary

The 334 preceding regular regression cases pass. Eleven new warning/build tests
pass normally and in ASan/UBSan mode (six compiled production-fragment cases and
five build/report checks). Tests cover forbidden/placement allocation, oversized
File::print rejection, full-width callback pointers, valid/unmapped sampler
states, compression NONE and short headers, ref-owner identity/single evaluation,
patch idempotence/conflict rejection, iOS SDK selection, verified vcpkg pin/path
handling, empty/missing tool lists and warning-report completeness/counts.
Packaging checks and changed shell syntax checks also pass. The twenty-one four-request
worker/queue cases also pass TSan after the accessor/default changes. All 345
regular cases pass (334 preceding plus eleven new checks).

Native iOS SDK compilation and the final native warning count remain pending.
Local fixtures cannot establish that every Apple SDK diagnostic has disappeared;
use the new build's complete warning summary and inspect any remaining groups.
