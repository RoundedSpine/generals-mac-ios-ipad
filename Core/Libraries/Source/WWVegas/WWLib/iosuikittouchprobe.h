#pragma once
#include <stdint.h>

// GeneralsX @feature Codex 25/10/2026 C-compatible diagnostic bridge shared with SDL's UIKit source.
#define GX_UIKIT_TOUCH_PROBE_PROPERTY "generalsx.ios.uikit_touch_probe"
typedef struct GXUIKitTouchSample {
    uint64_t source_ns, finger, callback_ns;
    double callback_uptime, event_timestamp, touch_timestamp;
    uint32_t type;
    int32_t touch_kind;
} GXUIKitTouchSample;

typedef struct GXUIKitTouchProbe {
    void (*record)(const GXUIKitTouchSample* sample);
} GXUIKitTouchProbe;
