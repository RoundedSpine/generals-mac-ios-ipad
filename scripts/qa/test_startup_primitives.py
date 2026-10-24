#!/usr/bin/env python3
"""Compile real allocator/path function bodies with small stand-ins, without an Apple SDK.

These tests cover arithmetic and path contracts, not complete engine startup.
"""
# GeneralsX @test Codex 24/10/2026 Cover early-startup failures independently of retail assets.
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def function_body(source, marker):
    start = source.index(marker)
    end = source.index('\n}', start) + 2
    return source[start:end]


def compile_and_run(source, flags=()):
    with tempfile.TemporaryDirectory() as directory:
        code = Path(directory) / 'test.cpp'
        binary = Path(directory) / 'test'
        code.write_text(source)
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-Wall', '-Wextra',
                        *flags, str(code), '-o', str(binary)], check=True, capture_output=True)
        subprocess.run([str(binary)], check=True, capture_output=True)


class StartupTest(unittest.TestCase):
    def test_real_memory_block_offsets_and_recovery(self):
        source = (ROOT / 'Core/GameEngine/Source/Common/System/GameMemory.cpp').read_text()
        wallcount = re.search(r'#define WALLCOUNT[^\n]+', source).group()
        wallsize = re.search(r'#define WALLSIZE[^\n]+', source).group()
        bodies = '\n'.join(function_body(source, marker) for marker in (
            'inline void* MemoryPoolSingleBlock::getUserDataNoDbg()',
            'inline /*static*/ Int MemoryPoolSingleBlock::calcRawBlockSize(',
            '/* static */ MemoryPoolSingleBlock *MemoryPoolSingleBlock::recoverBlockFromUserData('))
        harness = r'''
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
using Int = int;
#define DEBUG_ASSERTCRASH(...) ((void)0)
Int roundUpMemBound(Int n) { return (n + 3) & ~3; }
class MemoryPoolSingleBlock {
  void* header[HEADER_POINTERS];
public:
  void* getUserDataNoDbg();
  static Int calcRawBlockSize(Int);
  static MemoryPoolSingleBlock* recoverBlockFromUserData(void*);
};
BODIES
int main() {
  for (Int size = 1; size <= 1024; ++size) {
    const Int stride = MemoryPoolSingleBlock::calcRawBlockSize(size);
    auto* allocation = static_cast<char*>(std::malloc(stride * 8));
    assert(allocation != nullptr);
    for (int i = 0; i < 8; ++i) {
      auto* block = reinterpret_cast<MemoryPoolSingleBlock*>(allocation + i * stride);
      auto* user = static_cast<char*>(block->getUserDataNoDbg());
      assert(reinterpret_cast<std::uintptr_t>(user) % 16 == 0);
      assert(MemoryPoolSingleBlock::recoverBlockFromUserData(user) == block);
      assert(user + size <= allocation + (i + 1) * stride);
    }
    std::free(allocation);
  }
}
'''.replace('BODIES', bodies)
        for pointers in (3, 8):
            for walls in (False, True):
                with self.subTest(header_pointers=pointers, walls=walls):
                    defines = wallcount + '\n' + wallsize + '\n'
                    if walls:
                        defines += '#define MEMORYPOOL_BOUNDINGWALL\n'
                    compile_and_run(defines + harness, [f'-DHEADER_POINTERS={pointers}'])

    def test_ios_module_path_and_failure_contract(self):
        source = (ROOT / 'GeneralsMD/Code/CompatLib/Source/module_compat.cpp').read_text()
        body = function_body(source, 'bool GetModuleFileName(')
        harness = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <string>
#undef __linux__
#define __APPLE__ 1
#define TARGET_OS_IPHONE 1
using HINSTANCE = void*;
struct Dl_info { const char* dli_fname; };
const char* guestPath = "/guest/GeneralsXZH.app/GeneralsXZH";
bool resolveImage = true;
int dladdr(const void*, Dl_info* out) {
  out->dli_fname = guestPath;
  return resolveImage ? 1 : 0;
}
BODY
int main() {
  char path[4096];
  assert(GetModuleFileName(nullptr, path, sizeof(path)));
  assert(std::strcmp(path, guestPath) == 0);
  assert(!GetModuleFileName(nullptr, nullptr, 10));
  path[0] = 'x';
  assert(!GetModuleFileName(nullptr, path, 1));
  assert(path[0] == '\0');
  resolveImage = false;
  path[0] = 'x';
  assert(!GetModuleFileName(nullptr, path, sizeof(path)));
  assert(path[0] == '\0');
  resolveImage = true;
  std::string longPath(500, 'a'); guestPath = longPath.c_str();
  path[0] = 'x';
  assert(!GetModuleFileName(nullptr, path, 260));
  assert(path[0] == '\0');
  assert(GetModuleFileName(nullptr, path, sizeof(path)));
  assert(std::strcmp(path, guestPath) == 0);
}
'''.replace('BODY', body)
        compile_and_run(harness)


if __name__ == '__main__':
    unittest.main()
