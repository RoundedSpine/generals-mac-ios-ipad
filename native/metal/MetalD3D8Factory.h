#pragma once
#include <cstdint>

// Minimal ABI-independent factory entry point for early dynamic-loading tests.
// The IDirect3D8 COM vtable must be implemented using the pinned DXVK headers
// before this can be substituted for the game's D3D8 library.
#if defined(__cplusplus)
extern "C" {
#endif
#if defined(_WIN32)
#define GX_D3D8_EXPORT __declspec(dllexport)
#else
#define GX_D3D8_EXPORT __attribute__((visibility("default")))
#endif
GX_D3D8_EXPORT void *Direct3DCreate8(unsigned int sdk_version);
#if defined(__cplusplus)
}
#endif
