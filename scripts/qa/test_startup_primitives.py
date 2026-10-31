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
    # GeneralsX @test Codex 31/10/2026 Exercise the actual native diagnostic body with denied/missing APIs as well as signed values.
    def test_ios_memory_logging_distinguishes_signed_values_from_unknown_and_releases_queries(self):
        source = (ROOT / 'Core/GameEngineDevice/Source/SDL3Device/iosmemorydiagnostics.cpp').read_text()
        body = source[source.index('namespace {'):]
        compile_and_run(r'''
#include <cassert>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
using std::size_t;
struct CFObject {int type;bool value;long long error;};
using CFTypeRef=const CFObject*;using CFBooleanRef=CFTypeRef;using CFErrorRef=CFTypeRef;
using CFStringRef=const char*;using CFAllocatorRef=const void*;
constexpr CFAllocatorRef kCFAllocatorDefault=nullptr;
#define CFSTR(s) s
constexpr int RTLD_LAZY=1,RTLD_LOCAL=2;
int mode=0,owned=0,closed=0,queries=0;
const CFObject taskObject{2,false,0},enabled{1,true,0},disabled{1,false,0},unexpected{4,false,0},errorObject{3,false,-50};
void CFRelease(CFTypeRef object){assert(object&&owned>0);--owned;}
int CFGetTypeID(CFTypeRef object){return object->type;}
int CFBooleanGetTypeID(){return 1;}
bool CFBooleanGetValue(CFBooleanRef object){assert(object->type==1);return object->value;}
long long CFErrorGetCode(CFErrorRef object){return object->error;}
CFTypeRef fakeCreateTask(CFAllocatorRef){if(mode==7)return nullptr;++owned;return &taskObject;}
CFTypeRef fakeCopyEntitlement(CFTypeRef task,CFStringRef key,CFErrorRef* error){
 assert(task==&taskObject);++queries;
 const bool increased=std::strcmp(key,"com.apple.developer.kernel.increased-memory-limit")==0;
 assert(increased||std::strcmp(key,"com.apple.developer.kernel.extended-virtual-addressing")==0);
 if(increased&&mode==2)return nullptr;
 if(increased&&mode==3){*error=&errorObject;++owned;}
 ++owned;return increased&&mode==1?&disabled:increased&&mode==4?&unexpected:&enabled;
}
void* dlopen(const char*,int){return mode==5?nullptr:reinterpret_cast<void*>(1);}
void* dlsym(void*,const char* name){
 if(std::strcmp(name,"SecTaskCreateFromSelf")==0)return reinterpret_cast<void*>(&fakeCreateTask);
 assert(std::strcmp(name,"SecTaskCopyValueForEntitlement")==0);
 return mode==6?nullptr:reinterpret_cast<void*>(&fakeCopyEntitlement);
}
int dlclose(void*){++closed;return 0;}
size_t os_proc_available_memory(){return 1024ull*1024*1024;}
using mach_msg_type_number_t=unsigned;using task_info_t=int*;
struct task_vm_info_data_t {uint64_t phys_footprint;};
constexpr unsigned TASK_VM_INFO_COUNT=8,TASK_VM_INFO_REV1_COUNT=2;
constexpr int TASK_VM_INFO=22,KERN_SUCCESS=0;
int mach_task_self(){return 3;}
int task_info(int,int,task_info_t output,mach_msg_type_number_t* count){
 if(mode==9)return 1;
 if(mode==10)*count=TASK_VM_INFO_REV1_COUNT-1;
 reinterpret_cast<task_vm_info_data_t*>(output)->phys_footprint=64ull*1024*1024;return KERN_SUCCESS;
}
int sysctlbyname(const char* name,void* output,size_t* length,void*,size_t){
 assert(std::strcmp(name,"hw.memsize")==0);assert(*length==sizeof(uint64_t));
 if(mode==8)return -1;
 *static_cast<uint64_t*>(output)=8ull*1024*1024*1024;return 0;
}
namespace gxiosmemory {void logStartupCapabilities(FILE*);}
BODY
std::string capture(){FILE* output=std::tmpfile();assert(output);
 gxiosmemory::logStartupCapabilities(output);std::rewind(output);
 char text[4096]={};const auto n=std::fread(text,1,sizeof(text),output);std::fclose(output);
 return std::string(text,n);}
int main(){
 for(mode=0;mode<=10;++mode){
  owned=closed=queries=0;const auto text=capture();
  auto has=[&](const char* value){return text.find(value)!=std::string::npos;};
  assert(has("source=running_process"));assert(has("available_process_mib=1024.0"));
  assert(owned==0);assert(closed==(mode==5?0:1));assert(queries==((mode>=5&&mode<=7)?0:2));
  if(mode==1)assert(has("increased_memory_limit=false extended_virtual_addressing=true"));
  else if(mode==2)assert(has("increased_memory_limit=absent extended_virtual_addressing=true"));
  else if(mode==3){assert(has("increased_memory_limit=unknown extended_virtual_addressing=true"));assert(has("increased_status=query_error increased_error=-50"));}
  else if(mode==4){assert(has("increased_memory_limit=unknown extended_virtual_addressing=true"));assert(has("increased_status=unexpected_type"));}
  else if(mode>=5&&mode<=7){assert(has("increased_memory_limit=unknown extended_virtual_addressing=unknown"));assert(has(mode==7?"increased_status=task_unavailable":"increased_status=api_unavailable"));}
  else assert(has("increased_memory_limit=true extended_virtual_addressing=true"));
  assert(has(mode==8?"physical_device_mib=unknown":"physical_device_mib=8192.0"));
  assert(has(mode==9||mode==10?"footprint_mib=unknown":"footprint_mib=64.0"));
 }
}
'''.replace('BODY', body), ['-Werror'])

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



    def test_missing_texture_fallback_handles_detached_task(self):
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
