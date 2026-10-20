# Direct3D 8 to Metal: source audit (initial, verified)

## Scope
Inspected `Core/Libraries/Source/WWVegas/WW3D2/dx8wrapper.cpp` and `.h`, `GeneralsMD/Code/GameEngineDevice/Source/W3DDevice/GameClient/W3DDisplay.cpp`, `cmake/dx8.cmake`, `GeneralsMD/Code/CompatLib/CMakeLists.txt`, `Core/GameEngineDevice/CMakeLists.txt`, `CMakePresets.json`, and `cmake/meson-arm64-ios-cross.ini.in`. This is a targeted entry-point audit, **not** a repository-wide API inventory or validated ABI compatibility test.

## Confirmed rendering path
- `DX8Wrapper::Init()` loads `@executable_path/Frameworks/libdxvk_d3d8.0.dylib` on iOS and resolves `Direct3DCreate8` with `GetProcAddress`.
- `DX8Wrapper` calls `IDirect3D8::CreateDevice`, passing its HWND-like handle and `D3DPRESENT_PARAMETERS`; includes a depth-format fallback.
- `DX8Wrapper::Begin_Scene()` invokes `BeginScene`.
- `DX8Wrapper::End_Scene()` invokes `EndScene`, `Present`, and on `D3DERR_DEVICELOST` uses `TestCooperativeLevel` and `Reset_Device`.
- `DX8Wrapper` also issues `DrawIndexedPrimitive`, `SetRenderState` and uses texture/buffer/shader state caching.
- The current code contains a pillarbox path that renders to an offscreen texture then blits to the backbuffer before `Present`.
- `dx8wrapper.h` uses `<d3d8.h>`, and `CompatLib/CMakeLists.txt` supplies DXVK native headers through the `d3d8lib` interface target.

## Risks
1. Replacing the loaded dylib requires compatible D3D8 COM vtables and native calling conventions, not just exporting `Direct3DCreate8`.
2. The current Metal bootstrap is not connected to SDL3 or the game's HWND-like handle. Device creation requires an explicit bridge to the active view/layer.
3. Fixed-function vertex transforms, texture-stage combiners, fog, alpha test, lighting, and shader semantics are not implemented.
4. Texture/surface lock semantics, depth formats, resource ownership, lost-device behavior, and render-target switches require dedicated work.
5. Pillarbox/offscreen rendering is a first-class acceptance requirement.

## Prioritized next actions
1. Inventory D3D8 method calls in `Core/Libraries/Source/WWVegas/WW3D2`, W3D game client, and texture loader code; record usage frequencies and call sites.
2. Trace SDL3 window creation and DXVK's iOS native window bridge.
3. Confirm exact `IDirect3D8` / `IDirect3DDevice8` interface declarations from the pinned DXVK fork.
4. Add an experimental factory and COM ABI conformance tests before replacing the production DXVK library.
5. Demonstrate device creation + clear/present with the actual game window, then add geometry, render states, and resources.

## Current status
Native Metal bootstrap code exists in `native/metal/` but is not a D3D8 implementation. No Metal game frame or IPA has been compiled or tested.
