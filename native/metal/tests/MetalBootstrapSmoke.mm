#import "../MetalD3D8Bootstrap.h"
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstdio>
int main() {
  @autoreleasepool {
    if (!MTLCreateSystemDefaultDevice()) {
      std::fprintf(stderr, "SKIP: no Metal device available\n");
      return 77;
    }
    if (gx_metal_create(nullptr, 0, 64) != nullptr) return 1;
    GXMetalContext *ctx = gx_metal_create(nullptr, 64, 64);
    if (!ctx) return 2;
    gx_metal_resize(ctx, 128, 128);
    // Headless drawable acquisition is not guaranteed; don't assert present success.
    gx_metal_destroy(ctx);
    std::puts("PASS: native Metal bootstrap create/resize/destroy");
    return 0;
  }
}
