#include "../MetalD3D8Factory.h"
#include <dlfcn.h>
#include <cstdio>
int main() {
  using Factory = void* (*)(unsigned int);
  void* symbol = dlsym(RTLD_DEFAULT, "Direct3DCreate8");
  if (!symbol) { std::fprintf(stderr, "missing Direct3DCreate8 export\n"); return 1; }
  auto factory = reinterpret_cast<Factory>(symbol);
  if (factory(120) != nullptr) { std::fprintf(stderr, "unexpected COM object\n"); return 2; }
  std::puts("PASS: factory symbol present; unsupported factory fails closed");
  return 0;
}
