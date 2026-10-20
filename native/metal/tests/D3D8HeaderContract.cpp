// Compile-time contract against the actual DXVK D3D8 header, not a guessed ABI.
#include <d3d8.h>
#include <type_traits>
#include <cstdint>

static_assert(std::is_abstract<IDirect3D8>::value, "IDirect3D8 must be an interface");
static_assert(std::is_abstract<IDirect3DDevice8>::value, "IDirect3DDevice8 must be an interface");
static_assert(sizeof(HRESULT) == 4, "HRESULT must be 32-bit");
static_assert(sizeof(DWORD) == 4, "DWORD must be 32-bit");
static_assert(sizeof(UINT) == 4, "UINT must be 32-bit");
static_assert(sizeof(void*) == 8, "Probe expects 64-bit target");
using Factory = IDirect3D8* (WINAPI *)(UINT);
static_assert(std::is_pointer<Factory>::value, "D3D8 factory type");
int main() { return 0; }
