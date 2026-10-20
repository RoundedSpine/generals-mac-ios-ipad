# Native Metal renderer: phase 0 audit and implementation plan

Status: planning only. No Metal backend is implemented or enabled by this branch yet.

## Confirmed integration points

- `cmake/dx8.cmake` selects DXVK for Apple platforms under `APPLE AND SAGE_USE_MOLTENVK`; the iOS build uses the local `references/fbraz3-dxvk` checkout and applies `Patches/dxvk-ios.patch`.
- `GeneralsMD/Code/CompatLib/CMakeLists.txt` configures the `d3d8lib` interface with DXVK's Wine-compatible Direct3D headers, and links the D3DX8 compatibility helpers.
- `Core/GameEngineDevice/CMakeLists.txt` contains W3D renderer support, including shader manager, terrain, trees, water, and video buffers.
- `CMakePresets.json` defines the `ios-vulkan` preset with `SAGE_USE_MOLTENVK=ON`; the existing iOS packaging script embeds DXVK D3D8/D3D9 and MoltenVK.

## Architectural recommendation

Implement a separate D3D8-compatible Metal backend, preserving the game's renderer-facing D3D8 interfaces. Do **not** immediately replace W3D's high-level rendering, nor remove DXVK before parity is demonstrated.

Suggested milestones:

1. Inventory all D3D8/D3DX8 symbols and interface methods used by the iOS game binary and W3D engine.
2. Identify exact device creation, swapchain/present, window ownership, and SDL3 Metal-layer integration points.
3. Introduce an opt-in `SAGE_RENDERER_METAL` build flag, with the existing Vulkan pipeline remaining default.
4. Prototype device creation, a clear/present frame, and diagnostics using Objective-C++ / Metal.
5. Implement COM-compatible resource lifetime, texture/surface creation, vertex/index buffers, draw calls, state translation, and shader/fixed-function emulation.
6. Validate UI, terrain, water, shroud, shadows, particles, and video on physical iPhone/iPad devices.
7. Benchmark CPU frame time, GPU frame time, peak memory, and stability against the Vulkan baseline.

## Risks requiring source-level investigation

- DXVK's D3D8 interfaces are not a stable drop-in API contract for a custom implementation; header and ABI choices must be validated.
- Fixed-function D3D8 texture stages, transforms, fog, blending, and depth semantics can require substantial Metal shader generation.
- The game may use D3D8-specific surface locks, render-to-texture, lost-device behavior, and nonstandard formats.
- Some iOS window/lifecycle logic may currently reside in the DXVK fork.
- Build system and packaging must eventually omit DXVK/MoltenVK only for the Metal configuration.

## Acceptance criteria for phase 1

A buildable Metal-only test executable or engine backend must initialize Metal, present a clear frame, and cleanly shut down on device, without affecting the current `ios-vulkan` configuration. Until that passes, do not claim playable native Metal rendering.
