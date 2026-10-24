#include "types_compat.h"
#include "module_compat.h"

#include <unistd.h>
#include <dlfcn.h>
#include <string.h>

// GeneralsX @feature BenderAI 24/02/2026 Phase 5 macOS executable path detection
#ifdef __APPLE__
#include <mach-o/dyld.h>
#include <TargetConditionals.h>
#endif

bool GetModuleFileName(HINSTANCE hInstance, char* buffer, int size)
{
  // GeneralsX @bugfix Codex 24/10/2026 Fail with an empty, bounded string; hosted iOS paths can exceed MAX_PATH.
  if (buffer == nullptr || size <= 0)
    return false;
  buffer[0] = '\0';
#ifdef __linux__
  ssize_t count = readlink("/proc/self/exe", buffer, size - 1);
  if (count < 0 || count >= size - 1) {
    buffer[0] = '\0';
    return false;
  }
  buffer[count] = '\0';
  return true;
#elif defined(__APPLE__)
#if TARGET_OS_IPHONE
  // LiveContainer's main executable belongs to the host; this function is in the guest image.
  Dl_info image = {};
  if (dladdr(reinterpret_cast<const void *>(&GetModuleFileName), &image) == 0 || image.dli_fname == nullptr)
    return false;
  const size_t length = strlen(image.dli_fname);
  if (length >= static_cast<size_t>(size))
    return false;
  memcpy(buffer, image.dli_fname, length + 1);
  return true;
#else
  uint32_t bufsize = (uint32_t)size;
  int ret = _NSGetExecutablePath(buffer, &bufsize);
  if (ret == 0) {
    return true;
  }
  buffer[0] = '\0';
  return false;
#endif
#else
  return false;
#endif
}

HMODULE LoadLibrary(const char* lpFileName)
{
  // GeneralsX @feature BenderAI 24/02/2026 Phase 5 - Platform-agnostic library loading without C++17
  // Check if filename ends with ".dll" and remove extension if so
  const char* ext = strrchr(lpFileName, '.');
  if (ext && strcmp(ext, ".dll") == 0) {
    // Create a copy without the .dll extension
    size_t len = ext - lpFileName;
    char pathCurrent[512];
    if (len < sizeof(pathCurrent)) {
      strncpy(pathCurrent, lpFileName, len);
      pathCurrent[len] = '\0';
      return dlopen(pathCurrent, RTLD_LAZY);
    }
  }
  
  return dlopen(lpFileName, RTLD_LAZY);
}

FARPROC GetProcAddress(HMODULE hModule, const char* lpProcName)
{
  return (FARPROC)dlsym(hModule, lpProcName);
}

void FreeLibrary(HMODULE hModule)
{
  // Currently misbehaves by unmapping regions not related to the library
  // dlclose(hModule);
}
