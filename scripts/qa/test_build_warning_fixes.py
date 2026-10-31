#!/usr/bin/env python3
"""Verify warning fixes preserve allocation, formatting, callback and build contracts."""
# GeneralsX @test Codex 31/10/2026 Exercise real production fragments and pinned patch/setup failure handling.
import json
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from functools import partial
from compiled_harness import ROOT, run_cpp


def function(source, marker):
    start=source.index(marker);at=source.index('{',start);depth=1;i=at+1
    while depth:
        depth+=(source[i]=='{')-(source[i]=='}');i+=1
    return source[start:i]


def patch_postimage(name,filename):
    text=(ROOT/name).read_text();section=text.split('+++ b/'+filename+'\n',1)[1].split('\ndiff --git ',1)[0]
    return '\n'.join(line[1:] for line in section.splitlines() if line.startswith((' ','+')))


def workflow_run(name):
    text=(ROOT/'.github/workflows/build-ios.yml').read_text()
    section=text.split('      - name: '+name+'\n',1)[1].split('\n      - name:',1)[0]
    block=section.split('        run: |\n',1)[1]
    return '\n'.join(line[10:] for line in block.splitlines() if not line or line.startswith('          '))


class BuildWarningFixTests(unittest.TestCase):
    def test_ini_layout_extension_option_is_accepted_and_preserves_the_actual_offset(self):
        options=(ROOT/'cmake/compilers.cmake').read_text()
        flag=re.search(r'COMPILE_LANGUAGE:CXX>:(-Wno-[^>]+)>',options)[1]
        run_cpp(r'''
#include <cstddef>
#include <cassert>
struct IniRecord {virtual ~IniRecord(){};int value;};
int main(){IniRecord record;
 const auto offset=__builtin_offsetof(IniRecord,value);
 assert(reinterpret_cast<char*>(&record.value)-reinterpret_cast<char*>(&record)==offset);}
''',extra_flags=('-Werror',flag))

    def test_warning_report_counts_diagnostics_and_does_not_claim_incomplete_builds_are_clean(self):
        spec=importlib.util.spec_from_file_location('warning_report',ROOT/'scripts/build/ios/report-build-warnings.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            log=Path(directory)/'build.log';log.write_text('''/tmp/a.cpp:12:3: warning: enum mismatch [-Wenum-compare]
/tmp/a.cpp:12:3: warning: enum mismatch [-Wenum-compare]
clang++: warning: ignored option [-Wunused-command-line-argument]
ld: warning: ignoring duplicate libraries
CMake Warning at setup.cmake:12 (message):
CMake Deprecation Warning at old.cmake:1 (message):
ninja: warning: duplicate rule
printf("warning: a source string is not a compiler diagnostic");
''')
            result=module.summarize([log],'success')
            self.assertTrue(result['complete']);self.assertEqual(7,result['observed_warnings'])
            self.assertEqual(2,result['groups']['-Wenum-compare']);self.assertEqual(1,len(result['samples']['-Wenum-compare']))
            self.assertFalse(module.summarize([log],'failure')['complete'])
            self.assertFalse(module.summarize([Path(directory)/'missing'],'success')['complete'])
            log.write_text('CMake Error: a missing registry tree\n')
            incomplete=module.summarize([log],'skipped')
            self.assertFalse(incomplete['complete']);self.assertIn('missing registry tree',incomplete['incomplete_build_output'])
            log.write_text('Build completed\n');clean=module.summarize([log],'success')
            self.assertEqual(0,clean['observed_warnings']);self.assertEqual('',clean['incomplete_build_output'])

    def test_forbidden_pool_new_throws_before_construction_and_failed_placement_frees(self):
        header=(ROOT/'Core/GameEngine/Include/Common/GameMemory.h').read_text()
        macro=header[header.index('#define MEMORY_POOL_GLUE_WITHOUT_GCMP'):header.index('#define MEMORY_POOL_GLUE(ARGCLASS')]
        run_cpp(r'''
#include <cstddef>
#include <new>
#include <cassert>
#define DEBUG_ASSERTCRASH(...) ((void)0)
#define DEBUG_CRASH(...) ((void)0)
#define DECLARE_LITERALSTRING_ARG2
#define PASS_LITERALSTRING_ARG1
using Int=int;enum ErrorCode {ERROR_BUG=99};
int built=0,freed=0;bool fail=false;
struct MemoryPool {void*allocateBlockImplementation(){return ::operator new(128);}void freeBlock(void*p){++freed;::operator delete(p);}}pool;
struct Base {virtual~Base(){};virtual MemoryPool*getObjectMemoryPool()=0;};
'''+macro+r'''
struct Probe:Base {MEMORY_POOL_GLUE_WITHOUT_GCMP(Probe)
 static MemoryPool*getClassMemoryPool(){return &pool;}
 Probe(){++built;if(fail)throw 42;}
 static Probe*ordinary(){return new Probe;}
 static Probe*placed(){return new(Probe_GLUE_NOT_IMPLEMENTED)Probe;}
 static void dispose(Probe*p){delete p;}
};
Probe::~Probe(){}
int main(){try{Probe::ordinary();return 1;}catch(ErrorCode code){assert(code==ERROR_BUG&&built==0);}
 auto*p=Probe::placed();assert(built==1);Probe::dispose(p);assert(freed==1);
 fail=true;try{Probe::placed();return 2;}catch(int code){assert(code==42&&freed==2);}}
''',extra_flags=('-Werror',))

    def test_file_print_rejects_oversize_before_writing_or_overrunning(self):
        source=(ROOT/'Core/GameEngine/Source/Common/System/File.cpp').read_text()
        method=function(source,'Bool\tFile::print (')
        run_cpp(r'''
#include <cstdarg>
#include <cstdio>
#include <string>
#include <cassert>
using Bool=bool;using Int=int;using Char=char;constexpr bool TRUE=true,FALSE=false;
struct File {enum {TEXT=1};int m_access=TEXT,writes=0;std::string data;
 int write(const char*s,int n){++writes;data.assign(s,n);return n;}Bool print(const char*,...);};
'''+method+r'''
int main(){File f;if(!f.print("%s:%d","ok",7)||f.data!="ok:7"||f.writes!=1)return 1;
 std::string large(40000,'x');if(f.print("%s",large.c_str())||f.writes!=1||f.data!="ok:7")return 2;
 f.m_access=0;if(f.print("ignored")||f.writes!=1)return 3;}
''',extra_flags=('-DNDEBUG','-Werror'))

    def test_audio_callback_preserves_full_pointer_width(self):
        source=(ROOT/'Core/Libraries/Source/WWVegas/WWAudio/SoundSceneObj.h').read_text()
        method=function(source,'inline void\nSoundSceneObjClass::On_Event') if 'inline void\nSoundSceneObjClass::On_Event' in source else function(source,'SoundSceneObjClass::On_Event')
        # The source puts the return type on the preceding line.
        if not method.startswith('inline'):method='inline void\n'+method
        run_cpp(r'''
#include <cstdint>
#include <cassert>
struct LogicalListenerClass{};struct LogicalSoundClass{};
struct AudioCallbackClass {enum EVENTS{EVENT_SOUND_STARTED=1,EVENT_SOUND_ENDED=2,EVENT_LOGICAL_HEARD=4};
 void*listener=nullptr;void*sound=nullptr;unsigned mask=~0u;
 void On_Sound_Started(void*){}void On_Sound_Ended(void*){}
 void On_Logical_Heard(LogicalListenerClass*a,LogicalSoundClass*b){listener=a;sound=b;}};
struct SoundSceneObjClass {AudioCallbackClass*m_pCallback=nullptr;unsigned m_RegisteredEvents=~0u;
 void On_Event(AudioCallbackClass::EVENTS,uintptr_t=0,uintptr_t=0);};
'''+method+r'''
int main(){AudioCallbackClass callback;SoundSceneObjClass scene;scene.m_pCallback=&callback;
 const uintptr_t a=sizeof(void*)>4?uintptr_t(0x1234567800000010ull):0x1230;
 const uintptr_t b=sizeof(void*)>4?uintptr_t(0x7654321000000020ull):0x4560;
 scene.On_Event(AudioCallbackClass::EVENT_LOGICAL_HEARD,a,b);
 assert(reinterpret_cast<uintptr_t>(callback.listener)==a&&reinterpret_cast<uintptr_t>(callback.sound)==b);
}
''',extra_flags=('-Werror',))

    def test_dxvk_sampler_sentinel_is_not_an_enum_and_unmapped_states_stay_unmapped(self):
        image=patch_postimage('Patches/dxvk-ios-warnings.patch','src/d3d8/d3d8_d3d9_util.h')
        method=function(image,'inline DWORD GetSamplerStateType9(')
        run_cpp(r'''
#include <cstdint>
#include <type_traits>
#include <cassert>
#include <initializer_list>
using DWORD=std::uint32_t;
enum D3DTEXTURESTAGESTATETYPE {D3DTSS_ADDRESSU=13,D3DTSS_ADDRESSV,D3DTSS_BORDERCOLOR,D3DTSS_MAGFILTER,D3DTSS_MINFILTER,D3DTSS_MIPFILTER,D3DTSS_MIPMAPLODBIAS,D3DTSS_MAXMIPLEVEL,D3DTSS_MAXANISOTROPY,D3DTSS_ADDRESSW=25,D3DTSS_FORCE_DWORD=0x7fffffff};
namespace d3d9 {enum D3DSAMPLERSTATETYPE {D3DSAMP_ADDRESSU=1,D3DSAMP_ADDRESSV,D3DSAMP_ADDRESSW,D3DSAMP_BORDERCOLOR,D3DSAMP_MAGFILTER,D3DSAMP_MINFILTER,D3DSAMP_MIPFILTER,D3DSAMP_MIPMAPLODBIAS,D3DSAMP_MAXMIPLEVEL,D3DSAMP_MAXANISOTROPY,D3DSAMP_FORCE_DWORD=0x7fffffff};}
'''+method+r'''
int main(){static_assert(std::is_same<decltype(GetSamplerStateType9(D3DTSS_ADDRESSU)),DWORD>::value);
 assert(GetSamplerStateType9(D3DTSS_ADDRESSU)==1&&GetSamplerStateType9(D3DTSS_ADDRESSW)==3);
 assert(GetSamplerStateType9(D3DTSS_MAXANISOTROPY)==10);
 for(unsigned unknown:{0u,1u,12u,22u,24u,26u,0x7fffffffu})assert(GetSamplerStateType9(static_cast<D3DTEXTURESTAGESTATETYPE>(unknown))==UINT32_MAX);
}
''',extra_flags=('-Werror',))

    def test_compression_none_and_short_headers_keep_their_original_size_contracts(self):
        header=(ROOT/'Core/Libraries/Source/Compression/Compression.h').read_text()
        enum=header[header.index('enum CompressionType'):header.index('class CompressionManager')]
        source=(ROOT/'Core/Libraries/Source/Compression/CompressionManager.cpp').read_text()
        functions='\n'.join(function(source,m) for m in ['CompressionType CompressionManager::getCompressionType(',
            'Int CompressionManager::getMaxCompressedSize(', 'Int CompressionManager::getUncompressedSize('])
        run_cpp(r'''
#include <cstring>
#include <cmath>
#include <cassert>
using Int=int;using UnsignedByte=unsigned char;using Bool=bool;constexpr bool FALSE=false,TRUE=true;
int CalcNewSize(int n){return n+16;}
'''+enum+r'''
struct CompressionManager {static CompressionType getCompressionType(const void*,Int);static Int getMaxCompressedSize(Int,CompressionType);static Int getUncompressedSize(const void*,Int);};
'''+functions+r'''
int main(){alignas(int) unsigned char bytes[16]={};
 for(int length=0;length<8;++length)assert(CompressionManager::getUncompressedSize(bytes,length)==length);
 assert(CompressionManager::getMaxCompressedSize(123,COMPRESSION_NONE)==0);
 assert(CompressionManager::getUncompressedSize(bytes,16)==16);
 std::memcpy(bytes,"EAR\0",4);int size=123;std::memcpy(bytes+4,&size,sizeof size);
 assert(CompressionManager::getUncompressedSize(bytes,8)==123);
}
''',extra_flags=('-Werror','-Wswitch'))

    def test_ref_owner_identity_evaluates_once_and_preserves_pointer_result(self):
        source=(ROOT/'Core/Libraries/Source/WWVegas/WWLib/always.h').read_text()
        start=source.index('#endif\t//RTS_DEBUG')+len('#endif\t//RTS_DEBUG')
        end=source.index('#endif // (gth) removing the generals memory stuff from W3D')
        block=source[start:end]+'\n#endif\n'
        for flags in [(),('-DDISABLE_GAMEMEMORY',)]:
            run_cpp('#include <cassert>\n#include <new>\nusing std::size_t;\n#define __cdecl\n'+block+r'''
int main(){int value=7,calls=0;auto make=[&]{++calls;return &value;};
 SET_REF_OWNER(make());assert(calls==1);auto*p=SET_REF_OWNER(make());assert(p==&value&&calls==2);}
''',extra_flags=('-Werror','-Wunused-value',*flags))

    def test_patch_application_is_idempotent_inside_a_parent_git_checkout_and_rejects_conflicts(self):
        with tempfile.TemporaryDirectory(prefix='warning patches ') as directory:
            root=Path(directory);subprocess.run(['git','init','-q',str(root)],check=True)
            source=root/'dependency source';source.mkdir();(source/'sample.txt').write_text('before\n')
            patch=root/'fix.patch';patch.write_text('--- a/sample.txt\n+++ b/sample.txt\n@@ -1 +1 @@\n-before\n+after\n')
            command=['cmake','-DSOURCE_DIR='+str(source),'-DPATCH_FILE='+str(patch),'-P',str(ROOT/'cmake/apply-vendored-patch.cmake')]
            for _ in range(2):
                result=subprocess.run(command,text=True,capture_output=True);self.assertEqual(0,result.returncode,result.stdout+result.stderr)
                self.assertEqual('after\n',(source/'sample.txt').read_text())
            (source/'sample.txt').write_text('conflict\n');result=subprocess.run(command,text=True,capture_output=True)
            self.assertNotEqual(0,result.returncode);self.assertEqual('conflict\n',(source/'sample.txt').read_text())

    def test_ios_configuration_never_searches_for_a_host_macos_vulkan_sdk(self):
        text=(ROOT/'cmake/dx8.cmake').read_text();start=text.index('  # GeneralsX @build Codex 31/10/2026 iOS uses the explicit cross-file framework')
        end=text.index('  # iOS cross-compiles DXVK',start)
        with tempfile.TemporaryDirectory() as directory:
            script=Path(directory)/'check.cmake';script.write_text('set(CMAKE_SYSTEM_NAME iOS)\n'+text[start:end])
            result=subprocess.run(['cmake','-P',str(script)],text=True,capture_output=True)
            self.assertEqual(0,result.returncode,result.stderr);self.assertNotIn('WARNING',result.stderr)
            self.assertNotIn('not found',result.stdout+result.stderr)

    def test_vcpkg_bootstrap_verifies_pin_and_handles_paths_with_spaces(self):
        script=workflow_run('Set up vcpkg')
        for valid in [True,False]:
            with tempfile.TemporaryDirectory(prefix='vcpkg tools ') as directory:
                root=Path(directory);bin=root/'bin';bin.mkdir();calls=root/'git calls';stamp=root/'bootstrap stamp';envfile=root/'env file'
                git=bin/'git';git.write_text('#!'+sys.executable+'\n'+r'''
import sys,os,json
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['GX_TEST_CALLS'],'a') as f:f.write(json.dumps(args)+'\n')
if args[0]=='init':
 root=Path(args[1]);root.mkdir(parents=True)
 bootstrap=root/'bootstrap-vcpkg.sh';bootstrap.write_text('#!/bin/bash\nset -eu\ntest "$1" = -disableMetrics\necho done > "$GX_TEST_STAMP"\n');bootstrap.chmod(0o755)
if 'rev-parse' in args:print(os.environ['GX_TEST_REVISION'])
''');git.chmod(0o755)
                pin='08098dce081e9411889686fc3f4aecbde95fc2b1'
                env=dict(os.environ,PATH=str(bin)+os.pathsep+os.environ['PATH'],RUNNER_TEMP=str(root/'runner temp'),GITHUB_ENV=str(envfile),
                         GX_TEST_CALLS=str(calls),GX_TEST_STAMP=str(stamp),GX_TEST_REVISION=pin if valid else 'bad')
                result=subprocess.run(['bash','-euc',script],env=env,text=True,capture_output=True)
                if valid:
                    self.assertEqual(0,result.returncode,result.stderr);self.assertTrue(stamp.exists())
                    self.assertIn('VCPKG_ROOT='+str(root/'runner temp/generals-ios-vcpkg'),envfile.read_text())
                    invocations=[json.loads(line) for line in calls.read_text().splitlines()]
                    self.assertTrue(any('fetch' in row and row[-1]==pin for row in invocations))
                    self.assertFalse(any('--depth' in row for row in invocations))
                else:
                    self.assertNotEqual(0,result.returncode);self.assertFalse(stamp.exists());self.assertFalse(envfile.exists())

    def test_hosted_tools_install_only_missing_formulae_and_accept_an_empty_list(self):
        script=workflow_run('Select Xcode and install build tools')
        tools=['cmake','ninja','meson','pkg-config','xcodegen','glslang','autoconf','autoconf-archive','automake','libtool']
        for installed in [tools,tools[:2]]:
            with tempfile.TemporaryDirectory(prefix='brew tools ') as directory:
                root=Path(directory);bin=root/'bin';bin.mkdir();record=root/'install args'
                for tool in ['xcodebuild','xcrun']:
                    path=bin/tool;path.write_text('#!/bin/sh\nexit 0\n');path.chmod(0o755)
                brew=bin/'brew';brew.write_text('#!'+sys.executable+'\n'+r'''
import sys,os,json
from pathlib import Path
args=sys.argv[1:]
if args[:2]==['list','--versions']:sys.exit(0 if args[2] in json.loads(os.environ['GX_TEST_PRESENT']) else 1)
if args[0]=='install':Path(os.environ['GX_TEST_INSTALL']).write_text(json.dumps(args[1:]));sys.exit(0)
sys.exit(9)
''');brew.chmod(0o755)
                env=dict(os.environ,PATH=str(bin)+os.pathsep+os.environ['PATH'],VCPKG_DEFAULT_BINARY_CACHE=str(root/'cache'),
                         GX_TEST_PRESENT=json.dumps(installed),GX_TEST_INSTALL=str(record))
                result=subprocess.run(['bash','-euc',script],cwd=root,env=env,text=True,capture_output=True)
                self.assertEqual(0,result.returncode,result.stderr)
                missing=[name for name in tools if name not in installed]
                self.assertEqual(missing,json.loads(record.read_text()) if record.exists() else [])


if __name__=='__main__':
    if '--asan' in sys.argv:run_cpp=partial(run_cpp,extra_flags=('-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-O1'))
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(BuildWarningFixTests))
    sys.exit(not result.wasSuccessful())
