#include "MetalD3D8Factory.h"
// Explicit fail-closed placeholder: do not return a fake COM pointer.
extern "C" GX_D3D8_EXPORT void *Direct3DCreate8(unsigned int sdk_version) {
  (void)sdk_version;
  return nullptr;
}
