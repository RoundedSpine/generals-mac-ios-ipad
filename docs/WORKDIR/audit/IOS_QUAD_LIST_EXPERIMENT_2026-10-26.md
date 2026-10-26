# Verified quad triangle-list experiment

Date: 26 October 2026. Branch: `experiment/ios-mod-testing`.

## Evidence and implementation

The latest device log matched a retained water upload to its indexed draw: count
4, minimum 0, maximum 3, sentinel absent. It also captured non-indexed BW-filter,
motion-blur and viewport quads. Both sessions exited with code 0. The warning is
a pipeline-state mismatch, with no collision observed for these draws.

`GENERALS_QUAD_LISTS` defaults OFF. The experimental branch's IPA workflow enables
it. Convert only the verified ScreenBWFilter::postRender, two draws in
ScreenMotionBlurFilter::postRender, W3DShaderManager::drawViewport, and fixed 2x2
water-track geometry. Other filters, models, water surfaces and strip draws retain
their existing topology and are still observable through the temporary probes.
The regular branch/build defaults keep original strips.

A typed helper copies each four-vertex strip to six triangle-list vertices using
0,1,2 / 2,1,3. Positions, depth, color, UV and stride are retained; copying occurs
at each draw so motion-blur updates between passes are honored. DrawPrimitiveUP
still draws two primitives and returns the original API result. No shader,
blend/cull/depth state, texture or dependency change is made.

The water-track index buffer grows from four to six entries, with the original
strip 2,0,3,1 expanded to 2,0,3 / 3,0,1. Draw_Triangles uses start 0, two primitives,
minimum vertex 0 and the existing four vertices. Its buffer base offset and vertex
buffer batching remain unchanged. A compile-time assertion restricts this path to
the verified 2x2 WATER_STRIP_X/Y constants. Existing CPU capture sees the actual six
initialized indices. With conversion disabled, the original generator and strip
draw branches are retained.

## Validation and limitations

Four compiled sanitizer-backed tests cover oriented triangle area/winding, all
vertex attributes, unchanged input vertices, HRESULT/call preservation, the disabled
strip fallback, and the actual conditional water fill/draw statements. Buffer
canaries and expected indices verify the six-entry write and original four-entry
fallback. A diagnostic-enabled helper test verifies list draws do not produce strip
probe records. The iOS workflow runs this suite with the existing regressions.

These tests do not replace device rendering comparison: check BW/motion blur and
viewport overlays for identical colors, opacity, texture mapping and coverage,
and water tracks for missing/inverted triangles. Triangle-list draws should avoid
the strip-restart warning for these paths; other remaining strip pipelines can
still warn. No global warning suppression or primitive-restart override is used.
There is no claimed performance improvement; this experiment trades two extra
vertices/indices per quad for a topology supported without the strip mismatch.

The next uploaded log should show a six-index water upload (min 0, max 3) and may
show remaining unconverted strip sources. Converted list draws intentionally do
not produce STRIP_DRAW records. CPU submission timings from the probes still do
not isolate asynchronous pipeline compilation or GPU execution. Visual comparison
and the macOS SDK build remain required.

## Follow-up: isolated state-cache test

The user confirmed unchanged visuals. The subsequent log showed the six-index
water upload and none of the previous strip draw samples, but still 11 MoltenVK
warnings. DXVK's state cache can compile historical pipeline recipes; this remains
a hypothesis, not an established source for the remaining warnings.

The experimental workflow now passes its run ID as GENERALS_DXVK_CACHE_TAG, selecting
Library/Caches/dxvk-test-<run-id> before loading DXVK. No files are deleted or copied
from the previous cache. A successful first creation logs [DXVK_CACHE_TEST] with
state=new; repeat launches of the same build log state=reused. Empty tags retain
the standard cache behavior. Only safe filename characters are allowed in the tag.
Creation/selection failures are logged and invalidate any cold-cache conclusion.

Repeat the same mission on the first launch and send the log. Extra first-run
pipeline compilation may cause hitches, so do not infer a performance regression
from this cold-cache experiment alone. This isolates DXVK's persistent state cache,
not every Metal/driver-managed shader cache. Other remaining strip pipelines can
still produce warnings even if old DXVK recipes are eliminated.
