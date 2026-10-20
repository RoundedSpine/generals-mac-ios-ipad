#import "MetalD3D8Bootstrap.h"
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <QuartzCore/CAMetalLayer.h>
#import <TargetConditionals.h>
#if TARGET_OS_IOS
#import <UIKit/UIKit.h>
#endif

struct GXMetalContext {
    id<MTLDevice> device;
    id<MTLCommandQueue> queue;
    CAMetalLayer *layer;
    BOOL ownsLayer;
};

GXMetalContext *gx_metal_create(void *ui_view, int width, int height) {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device || width <= 0 || height <= 0) return nullptr;
        GXMetalContext *ctx = new GXMetalContext();
        ctx->device = device;
        ctx->queue = [device newCommandQueue];
        ctx->layer = [CAMetalLayer layer];
        ctx->ownsLayer = YES;
        ctx->layer.device = device;
        ctx->layer.pixelFormat = MTLPixelFormatBGRA8Unorm;
        ctx->layer.framebufferOnly = YES;
        ctx->layer.drawableSize = CGSizeMake(width, height);
#if TARGET_OS_IOS
        UIView *view = (__bridge UIView *)ui_view;
        if (view) {
            ctx->layer.frame = view.bounds;
            [view.layer addSublayer:ctx->layer];
        }
#else
        (void)ui_view;
#endif
        if (!ctx->queue) { delete ctx; return nullptr; }
        return ctx;
    }
}

int gx_metal_clear_present(GXMetalContext *ctx, float r, float g, float b, float a) {
    @autoreleasepool {
        if (!ctx || !ctx->queue) return 0;
        id<CAMetalDrawable> drawable = [ctx->layer nextDrawable];
        if (!drawable) return 0;
        MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
        pass.colorAttachments[0].texture = drawable.texture;
        pass.colorAttachments[0].loadAction = MTLLoadActionClear;
        pass.colorAttachments[0].storeAction = MTLStoreActionStore;
        pass.colorAttachments[0].clearColor = MTLClearColorMake(r,g,b,a);
        id<MTLCommandBuffer> command = [ctx->queue commandBuffer];
        if (!command) return 0;
        id<MTLRenderCommandEncoder> encoder = [command renderCommandEncoderWithDescriptor:pass];
        if (!encoder) return 0;
        [encoder endEncoding];
        [command presentDrawable:drawable];
        [command commit];
        return 1;
    }
}

void gx_metal_resize(GXMetalContext *ctx, int width, int height) {
    if (ctx && width > 0 && height > 0)
        ctx->layer.drawableSize = CGSizeMake(width, height);
}

void gx_metal_destroy(GXMetalContext *ctx) {
    if (!ctx) return;
    @autoreleasepool {
        if (ctx->ownsLayer) [ctx->layer removeFromSuperlayer];
        delete ctx;
    }
}
