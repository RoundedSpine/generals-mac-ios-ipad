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

    def test_apple_executable_path_and_failure_contract(self):
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
const char* executablePath = "/guest/GeneralsXZH.app/GeneralsXZH";
bool resolveImage = true;
int _NSGetExecutablePath(char* output, uint32_t* size) {
  const auto required = std::strlen(executablePath) + 1;
  if (!resolveImage || *size < required) {
    *size = static_cast<uint32_t>(required);
    return -1;
  }
  std::memcpy(output, executablePath, required);
  return 0;
}
BODY
int main() {
  char path[4096];
  assert(GetModuleFileName(nullptr, path, sizeof(path)));
  assert(std::strcmp(path, executablePath) == 0);
  assert(!GetModuleFileName(nullptr, nullptr, 10));
  path[0] = 'x';
  assert(!GetModuleFileName(nullptr, path, 1));
  assert(path[0] == '\0');
  resolveImage = false;
  path[0] = 'x';
  assert(!GetModuleFileName(nullptr, path, sizeof(path)));
  assert(path[0] == '\0');
  resolveImage = true;
  std::string longPath(500, 'a'); executablePath = longPath.c_str();
  path[0] = 'x';
  assert(!GetModuleFileName(nullptr, path, 260));
  assert(path[0] == '\0');
  assert(GetModuleFileName(nullptr, path, sizeof(path)));
  assert(std::strcmp(path, executablePath) == 0);
}
'''.replace('BODY', body)
        compile_and_run(harness)



    def test_base_assets_are_searched_when_primary_root_is_cwd(self):
        source = (ROOT / 'Core/GameEngineDevice/Source/StdDevice/Common/StdBIGFileSystem.cpp').read_text()
        body = 'template <typename TBigFileSystem>\n' + function_body(source, 'static void loadBaseGeneralsAssetsForZH(')
        harness = r'''
#include <cassert>
#include <string>
#include <vector>
using Bool = bool;
class AsciiString {
  std::string value;
public:
  AsciiString(const char* s="") : value(s) {}
  bool isNotEmpty() const { return !value.empty(); }
  void concat(const char* s) { value += s; }
  const char* str() const { return value.c_str(); }
};
const char* kBaseGeneralsAssetEnv="CNC_GENERALS_PATH";
const char* kBaseGeneralsAssetIniKey="generals";
const char* noEnvironment(const char*) { return nullptr; }
#define getenv noEnvironment
std::vector<std::string> attempted;
std::string available;
bool getExecutableDirectory(AsciiString&) { return false; }
bool tryResolveFromIni(const AsciiString&, const char*, AsciiString&) { return false; }
void GetStringFromGeneralsRegistry(const char*, const char*, AsciiString&) {}
template<class T> bool tryLoadBigFiles(T*, const AsciiString& path, const char*) {
  attempted.push_back(path.str()); return available==path.str();
}
BODY
int main() {
  int filesystem=0;
  available="./ZH_Generals";
  loadBaseGeneralsAssetsForZH(&filesystem, AsciiString());
  assert(attempted.back()==available);
  attempted.clear(); available="/data/ZH/ZH_Generals";
  loadBaseGeneralsAssetsForZH(&filesystem, AsciiString("/data/ZH"));
  assert(attempted.back()==available);
}
'''.replace('BODY', body)
        compile_and_run(harness)



    def test_missing_texture_logging_uses_character_buffer(self):
        source = (ROOT / 'Core/Libraries/Source/WWVegas/WW3D2/textureloader.cpp').read_text()
        body = function_body(source, 'void TextureLoadTaskClass::Apply_Missing_Texture()')
        harness = r'''
#include <cassert>
#include <cstdio>
#include <string>
#define WWASSERT(...) ((void)0)
class StringClass {
  std::string text;
public:
  StringClass() : text("missing.dds") {}
  const char* str() const { return text.c_str(); }
};
struct TextureClass { StringClass path; const StringClass& Get_Full_Path() const { return path; } };
struct MissingTexture { static void* _Get_Missing_Texture() { static int texture; return &texture; } };
struct TextureLoader { static bool Is_DX8_Thread() { return true; } };
class TextureLoadTaskClass {
public:
  TextureClass* Texture=nullptr;
  void* D3DTexture=nullptr;
  int Format=1;
  unsigned Width=32, Height=32;
  int applied=0;
  void Apply(bool) { ++applied; }
  void Apply_Missing_Texture();
};
BODY
int main() {
  TextureLoadTaskClass task;
  task.Apply_Missing_Texture(); assert(task.applied==0);
  TextureClass texture; task.Texture=&texture;
  task.Apply_Missing_Texture(); assert(task.applied==1);
}
'''.replace('BODY', body)
        compile_and_run(harness, ['-Werror=format'])


if __name__ == '__main__':
    unittest.main()
