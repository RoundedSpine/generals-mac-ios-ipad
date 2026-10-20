# D3D8 ABI gate before Metal replacement

## Confirmed game integration
`Core/Libraries/Source/WWVegas/WW3D2/dx8wrapper.cpp` stores `_Hwnd=(HWND)hwnd`, loads `@executable_path/Frameworks/libdxvk_d3d8.0.dylib` on iOS, resolves `Direct3DCreate8`, then invokes `IDirect3D8::CreateDevice`. Its scene lifecycle uses `BeginScene`, `EndScene`, `Present`, and device reset.

## ABI requirements (must be verified against pinned DXVK headers)
- Exact `IDirect3D8`, `IDirect3DDevice8`, texture, surface, vertex/index-buffer and resource vtable order.
- COM `QueryInterface`, `AddRef`, `Release` behavior and object identity.
- HRESULT and integer widths, structures, enum values, packing, calling conventions, and pointer lifetime.
- Factory signature `IDirect3D8* WINAPI Direct3DCreate8(UINT)`.
- iOS HWND-like handle translation to actual SDL3 native window / UIKit view; do not cast arbitrary HWND directly to UIView.
- D3D8 presentation parameters and backbuffer/depth-stencil formats, lost-device semantics, render target switching and offscreen pillarbox.
- D3DX8 helper dependencies remain separate from D3D8 device ABI.

## First acceptance test
1. Build a standalone ABI probe against exactly the headers used by the game.
2. Validate factory entry point, adapter queries, and `CreateDevice` against the real game window.
3. Validate `Clear`, `BeginScene`, `EndScene`, `Present`, `Reset` and teardown.
4. Only then add textures, vertex/index buffers, state translation and actual geometry.
5. Preserve the existing DXVK/MoltenVK build as a selectable fallback.

**Current status:** No native Metal COM device or ABI test has passed. The Metal bootstrap is not a drop-in DXVK replacement.
