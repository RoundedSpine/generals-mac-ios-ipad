#pragma once
// Experimental Metal device/presentation bootstrap.
// This is NOT yet an IDirect3D8/IDirect3DDevice8 implementation.
#ifdef __cplusplus
extern "C" {
#endif
typedef struct GXMetalContext GXMetalContext;
GXMetalContext *gx_metal_create(void *ui_view, int width, int height);
int gx_metal_clear_present(GXMetalContext *context, float r, float g, float b, float a);
void gx_metal_resize(GXMetalContext *context, int width, int height);
void gx_metal_destroy(GXMetalContext *context);
#ifdef __cplusplus
}
#endif
