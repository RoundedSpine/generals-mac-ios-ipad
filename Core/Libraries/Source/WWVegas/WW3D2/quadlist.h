#pragma once

#include <d3d8.h>
#include "stripdiagnostics.h"

// GeneralsX @feature Codex 26/10/2026 Expand verified four-vertex strips without changing winding or vertex attributes.
namespace gxquad {
// Odd strip triangles reverse their first two vertices. Keep vertex 3 last for the second triangle.
constexpr unsigned TriangleOrder[6] = {0, 1, 2, 2, 1, 3};
template<class Vertex>
void expand(const Vertex (&strip)[4], Vertex* triangles) {
 for (unsigned i = 0; i < 6; ++i) triangles[i] = strip[TriangleOrder[i]];
}
template<class Device, class Vertex>
auto draw(Device* device, const Vertex (&vertices)[4])
 -> decltype(device->DrawPrimitiveUP(D3DPT_TRIANGLELIST, 2, vertices, sizeof(Vertex))) {
#ifdef GENERALS_QUAD_LISTS
 Vertex triangles[6];
 expand(vertices, triangles);
 return device->DrawPrimitiveUP(D3DPT_TRIANGLELIST, 2, triangles, sizeof(Vertex));
#else
 return GX_STRIP_UP(device, D3DPT_TRIANGLESTRIP, 2, vertices, sizeof(Vertex));
#endif
}
}
