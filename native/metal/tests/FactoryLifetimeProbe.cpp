#include <atomic>
#include <cstdint>
#include <cstdio>

// Standalone factory ABI harness. This deliberately does not claim to implement
// IDirect3D8 yet; the real interface must use the project's pinned DXVK headers.
struct GXFactoryProbe {
  std::atomic<uint32_t> references{1};
  uint32_t AddRef() { return ++references; }
  uint32_t Release() {
    uint32_t n = --references;
    if (!n) delete this;
    return n;
  }
};
int main() {
  auto* factory = new GXFactoryProbe;
  if (factory->AddRef() != 2) return 1;
  if (factory->Release() != 1) return 2;
  if (factory->Release() != 0) return 3;
  std::puts("PASS: standalone reference-count lifecycle");
  return 0;
}
