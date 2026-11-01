#!/usr/bin/env python3
"""Compile production accounting functions with resource providers, without an iOS SDK."""
# GeneralsX @test Codex 01/11/2026 Validate counter coverage, 64-bit arithmetic and disabled/uninitialized engine states.
import unittest
from compiled_harness import ROOT, run_cpp

INCLUDES = ['-I', str(ROOT / 'Core/GameEngine/Include'),
            '-I', str(ROOT / 'Core/GameEngineDevice/Include')]


def function(path, marker):
    source = (ROOT / path).read_text()
    start = source.index(marker)
    return source[start:source.index('\n}', start) + 2]


def tracker_fixture():
    return r'''
#include "SDL3Device/poolmemorydiagnostics.h"
#include <cassert>
#include <cstdlib>
#include <new>
#include <string>
bool forbidNew=false;
void* operator new(std::size_t size){assert(!forbidNew);if(auto*p=std::malloc(size))return p;throw std::bad_alloc();}
void operator delete(void*p)noexcept{std::free(p);}
void operator delete(void*p,std::size_t)noexcept{std::free(p);}
static gxpoolmemory::Tracker tracker;
int identities[gxpoolmemory::Tracker::Capacity+4];
void pool(size_t index,size_t identity,const char*name,size_t live,size_t reserved,size_t block=64){
 auto&entry=tracker.entries()[index];entry.identity=&identities[identity];
 std::snprintf(entry.name,sizeof(entry.name),"%s",name);entry.nameTruncated=false;
 entry.allocationSize=block;entry.usedBlocks=live;entry.totalBlocks=reserved;}
std::string capture(size_t count){
 FILE*out=std::tmpfile();assert(out);forbidNew=true;tracker.log(out,count);forbidNew=false;
 std::rewind(out);char text[16384]{};size_t n=std::fread(text,1,sizeof(text),out);assert(!std::ferror(out));
 assert(n<sizeof(text));std::fclose(out);return std::string(text,n);}
std::string row(const std::string&text,const char*name){std::string key="name=\"";key+=name;key+='"';
 auto at=text.find(key);assert(at!=std::string::npos);return text.substr(at,text.find('\n',at)-at);}
'''


class MemoryCounterTests(unittest.TestCase):
    def test_named_pool_rows_survive_the_existing_debug_log_cap(self):
        source = (ROOT / 'GeneralsMD/Code/Main/SDL3Main.cpp').read_text()
        start = source.index('if ((len >= 11 && memcmp(buf, "[IOS_MEMORY"')
        condition = source[start + len('if ('):source.index(') {', start)]
        run_cpp(r'''
#include <cassert>
#include <cstring>
bool retain(const char*buf,int len){return CONDITION;}
int main(){
 for(const char*line:{"[IOS_MEMORY] x", "[IOS_MEMORY_POOL] name=\"AudioEventRTS\"", "[IOS_MEMORY_POOLS] total=500", "[IOS_ENGINE_MEMORY] x", "ERROR test"})
  assert(retain(line,std::strlen(line)));
 for(const char*line:{"", "[IOS", "debug noise", "[PATH_TIMING] x"})assert(!retain(line,std::strlen(line)));
 assert(!retain(nullptr,0));
}
'''.replace('CONDITION', condition).replace('#include <cassert>', '#include <cassert>\n#include <initializer_list>'))

    # GeneralsX @test Codex 01/11/2026 Use the real bounded tracker through reorder, shrinkage, missing pools, reset and rankings.
    def test_pool_deltas_follow_identity_and_only_the_previous_sample(self):
        run_cpp(tracker_fixture() + r'''
int main(){
 pool(0,0,"alpha",8,10);pool(1,1,"beta",1,20);auto text=capture(2);
 assert(text.find("growing_used=0 newly_seen=2")!=std::string::npos);
 assert(row(text,"alpha").find("baseline=first_sample")!=std::string::npos);
 pool(0,1,"beta",9,22);pool(1,0,"alpha",5,10);pool(2,2,"gamma",6,12,128);text=capture(3);
 assert(text.find("growing_used=2 newly_seen=1")!=std::string::npos);
 auto beta=row(text,"beta"),alpha=row(text,"alpha"),gamma=row(text,"gamma");
 assert(beta.find("used_delta_bytes=512 reserved_delta_bytes=128 live_delta_blocks=8 baseline=previous_sample growth_rank=2")!=std::string::npos);
 assert(alpha.find("used_delta_bytes=-192 reserved_delta_bytes=0 live_delta_blocks=-3")!=std::string::npos);
 assert(gamma.find("used_delta_bytes=768 reserved_delta_bytes=1536 live_delta_blocks=6 baseline=not_in_previous growth_rank=1")!=std::string::npos);
 pool(0,0,"alpha",5,10);pool(1,2,"gamma",6,12,128);pool(2,1,"beta",9,22);text=capture(3);
 assert(text.find("growing_used=0 newly_seen=0")!=std::string::npos);
 assert(row(text,"beta").find("used_delta_bytes=0 reserved_delta_bytes=0 live_delta_blocks=0")!=std::string::npos);
 // Reusing an address for a different pool must not inherit the previous class's counts.
 pool(0,0,"different",2,4);text=capture(1);
 assert(row(text,"different").find("baseline=not_in_previous")!=std::string::npos);
 assert(capture(0).find("total=0 captured=0 omitted=0 previous_captured=1 growing_used=0 newly_seen=0 rows=0")!=std::string::npos);
 pool(0,0,"different",2,4);text=capture(1);assert(row(text,"different").find("baseline=not_in_previous")!=std::string::npos);
 tracker.reset();pool(0,0,"different",2,4);text=capture(1);
 assert(row(text,"different").find("used_delta_bytes=0 reserved_delta_bytes=0 live_delta_blocks=0 baseline=first_sample")!=std::string::npos);
}
''', [*INCLUDES, '-Wall', '-Wextra', '-Werror'])

    def test_pool_rankings_bound_output_and_make_capacity_omissions_explicit(self):
        run_cpp(tracker_fixture() + r'''
size_t rows(const std::string&text){size_t count=0,at=0;while((at=text.find("[IOS_MEMORY_POOL]",at))!=std::string::npos){++count;++at;}return count;}
int main(){
 // A reserved-only pool is kept visible even with no live allocations.
 pool(0,0,"retained",0,200000000,128);auto text=capture(1);
 assert(row(text,"retained").find("used_bytes=0 reserved_bytes=25600000000")!=std::string::npos);
 assert(row(text,"retained").find("reserved_rank=1")!=std::string::npos);
 tracker.reset();
 for(size_t i=0;i<gxpoolmemory::Tracker::Capacity;++i){char label[64];std::snprintf(label,sizeof(label),"pool_%04zu",i);pool(i,i,label,i+1,i+100);}
 text=capture(gxpoolmemory::Tracker::Capacity+3);
 assert(text.find("total=1027 captured=1024 omitted=3")!=std::string::npos);assert(rows(text)<=8);
 assert(row(text,"pool_1023").find("live_rank=1 reserved_rank=1")!=std::string::npos);
 // Many growth candidates still produce at most 8 growth + 4 used + 4 reserved rows.
 for(size_t i=0;i<gxpoolmemory::Tracker::Capacity;++i){char label[64];std::snprintf(label,sizeof(label),"pool_%04zu",i);pool(i,i,label,i+10,i+100);}
 text=capture(gxpoolmemory::Tracker::Capacity);assert(rows(text)<=16);
 assert(text.find("growing_used=1024 newly_seen=0")!=std::string::npos);
 // The same fixed buffers support arbitrarily many later snapshots without retaining history.
 for(int sample=0;sample<100;++sample){pool(0,0,"alone",100+sample,1000);text=capture(1);assert(rows(text)==1);}
 assert(row(text,"alone").find("used_delta_bytes=64 reserved_delta_bytes=0 live_delta_blocks=1")!=std::string::npos);
}
''', [*INCLUDES, '-Wall', '-Wextra', '-Werror'])

    def test_pool_labels_cannot_inject_log_lines_and_ties_are_deterministic(self):
        run_cpp(tracker_fixture() + r'''
int main(){
 pool(0,0,"zulu",1,1);pool(1,1,"alpha",1,1);pool(2,2,"bad\n\"\\name",1,1);
 tracker.entries()[2].nameTruncated=true;auto text=capture(3);
 assert(row(text,"alpha").find("live_rank=1 reserved_rank=1")!=std::string::npos);
 assert(row(text,"bad___name").find("name_truncated=1")!=std::string::npos);
 pool(0,1,"alpha",2,3);pool(1,0,"zulu",2,3);text=capture(2);
 assert(row(text,"alpha").find("growth_rank=1")!=std::string::npos);
 assert(row(text,"zulu").find("growth_rank=2")!=std::string::npos);
}
''', [*INCLUDES, '-Wall', '-Wextra', '-Werror'])

    def test_pool_usage_uses_wide_math_and_does_not_allocate(self):
        body = function('Core/GameEngine/Source/Common/System/GameMemory.cpp', 'size_t MemoryPoolFactory::getPoolMemoryUsage(')
        run_cpp(r'''
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include "Common/MemoryPoolUsage.h"
unsigned locks=0;int TheMemoryPoolCriticalSection=0;
struct ScopedCriticalSection{ScopedCriticalSection(int&){++locks;}~ScopedCriticalSection(){--locks;}};
struct MemoryPool{int used,total,bytes;MemoryPool*next;const char*name;
 int getUsedBlockCount(){assert(locks==1);return used;}int getTotalBlockCount(){return total;}
 int getAllocationSize(){return bytes;}MemoryPool*getNextPoolInList(){return next;}const char*getPoolName(){return name;}};
struct MemoryPoolFactory{MemoryPool*m_firstPoolInFactory=nullptr;size_t getPoolMemoryUsage(size_t&,size_t&,MemoryPoolUsage* = nullptr,size_t = 0);};
BODY
int main(){MemoryPoolFactory factory;size_t used=123,reserved=123;
 assert(factory.getPoolMemoryUsage(used,reserved)==0);assert(used==0&&reserved==0&&locks==0);
 char name[150];std::memset(name,'x',sizeof(name));name[149]=0;
 MemoryPool b{1,3,64,nullptr,"small"},a{100000000,200000000,128,&b,name};factory.m_firstPoolInFactory=&a;
 factory.getPoolMemoryUsage(used,reserved);assert(used==12800000064ull&&reserved==25600000192ull&&locks==0);
 MemoryPoolUsage slots[3]{};slots[0].usedBlocks=slots[2].usedBlocks=777;
 assert(factory.getPoolMemoryUsage(used,reserved,&slots[1],1)==2);
 assert(used==12800000064ull&&reserved==25600000192ull&&slots[0].usedBlocks==777&&slots[2].usedBlocks==777);
 assert(slots[1].identity==&a&&slots[1].allocationSize==128&&slots[1].usedBlocks==100000000);
 assert(slots[1].nameTruncated&&std::strlen(slots[1].name)==95);
 name[0]='z';assert(slots[1].name[0]=='x'); // Snapshot owns its name, not a dangling pool string.
 assert(factory.getPoolMemoryUsage(used,reserved,slots,0)==2&&slots[0].usedBlocks==777);
 assert(factory.getPoolMemoryUsage(used,reserved,nullptr,100)==2);
 assert(factory.getPoolMemoryUsage(used,reserved,slots,3)==2);
 assert(!slots[1].nameTruncated&&std::strcmp(slots[1].name,"small")==0&&slots[1].usedBlocks==1);
 a.used=0;b.used=0;factory.getPoolMemoryUsage(used,reserved);assert(used==0&&reserved==25600000192ull);}
'''.replace('BODY', body), INCLUDES)

    def test_audio_counter_snapshot_tracks_actual_cache_and_playback_lists(self):
        body = function('Core/GameEngineDevice/Source/OpenALAudioDevice/OpenALAudioManager.cpp', 'void OpenALAudioManager::logMemoryUsage(')
        run_cpp(r'''
#include <cassert>
#include <cstdio>
#include <string>
#include <vector>
struct Cache{unsigned getCurrentlyUsedSize(){return 1572864;}unsigned getMaxSize(){return 14680064;}
 size_t getCachedBufferCount(){return 7;}unsigned getUnmatchedCloseCount(){return 3;}};
struct OpenALAudioManager{Cache*m_audioCache=nullptr;std::vector<int>m_playingSounds,m_playing3DSounds,m_playingStreams,m_fadingAudio,m_stoppedAudio;
 void logMemoryUsage(FILE*)const;};
BODY
int main(){FILE*output=std::tmpfile();assert(output);OpenALAudioManager manager;manager.logMemoryUsage(output);assert(std::ftell(output)==0);
 Cache cache;manager.m_audioCache=&cache;manager.m_playing3DSounds.resize(2);manager.m_playingStreams.resize(1);manager.logMemoryUsage(output);
 std::rewind(output);char line[1024]{};std::fread(line,1,sizeof(line),output);std::fclose(output);
 std::string text(line);assert(text.find("decoded_pcm_mib=1.500 cache_limit_mib=14.0 cached_buffers=7 unmatched_closes=3 playing_2d=0 playing_3d=2 streams=1 fading=0 stopped=0")!=std::string::npos);}
'''.replace('BODY', body))

    def test_engine_snapshot_handles_missing_subsystems_and_disabled_pools(self):
        body = function('GeneralsMD/Code/GameEngineDevice/Source/SDL3GameEngine.cpp', 'static void logIOSResourceMemory(')
        fixture = r'''
#include <cassert>
#include <cstdio>
#include <string>
#include "SDL3Device/poolmemorydiagnostics.h"
#ifndef DISABLE_GAMEMEMORY
static gxpoolmemory::Tracker s_poolMemoryTracker;
#endif
struct Factory{size_t getPoolMemoryUsage(size_t&used,size_t&reserved,MemoryPoolUsage*pools,size_t){
 used=1048576;reserved=4194304;pools[0]={this,"test",64,16384,65536,false};return 1;}};
struct Logic{unsigned getObjectCount(){return 25;}bool isGamePaused(){return true;}bool isInShellGame(){return false;}unsigned getFrame(){return 10;}};
struct Particles{unsigned getParticleCount(){return 100;}};
struct OpenALAudioManager{unsigned calls=0;void logMemoryUsage(FILE*){++calls;}};
Factory*TheMemoryPoolFactory=nullptr;Logic*TheGameLogic=nullptr;Particles*TheParticleSystemManager=nullptr;OpenALAudioManager*TheAudio=nullptr;
struct TextureBaseClass{static int _Get_Total_Texture_Count(){return 10;}static int _Get_Total_Texture_Size(){return 2097152;}};
struct VertexBufferClass{static unsigned Get_Total_Buffer_Count(){return 8;}static unsigned Get_Total_Allocated_Memory(){return 1048576;}};
struct IndexBufferClass{static unsigned Get_Total_Buffer_Count(){return 5;}static unsigned Get_Total_Allocated_Memory(){return 524288;}};
BODY
std::string capture(){FILE*out=std::tmpfile();assert(out);logIOSResourceMemory(out);std::rewind(out);char line[2048]{};std::fread(line,1,sizeof(line),out);std::fclose(out);return line;}
int main(){auto text=capture();assert(text.find("objects=0 particles=0")!=std::string::npos);
#ifndef DISABLE_GAMEMEMORY
 assert(text.find("pool_status=unavailable")!=std::string::npos);
#endif
 Factory factory;Logic logic;Particles particles;OpenALAudioManager audio;
 TheMemoryPoolFactory=&factory;TheGameLogic=&logic;TheParticleSystemManager=&particles;TheAudio=&audio;
 text=capture();assert(audio.calls==1&&text.find("objects=25 particles=100")!=std::string::npos);
 assert(text.find("texture_coverage=asset_hash named_textures=10 named_texture_mib=2.0 vertex_buffers=8 vertex_buffer_mib=1.0 index_buffers=5 index_buffer_mib=0.5")!=std::string::npos);
 assert(text.find("game_paused=1 shell_game=0 logic_frame=10")!=std::string::npos);
#ifndef DISABLE_GAMEMEMORY
 assert(text.find("pool_status=ok pool_payload_used_mib=1.0 pool_payload_reserved_mib=4.0")!=std::string::npos);
 assert(text.find("[IOS_MEMORY_POOLS] total=1 captured=1 omitted=0")!=std::string::npos);
 assert(text.find("name=\"test\"")!=std::string::npos);
#else
 assert(text.find("pool_status=disabled")!=std::string::npos);
#endif
}
'''.replace('BODY', body)
        run_cpp(fixture, [*INCLUDES, '-Wall', '-Wextra', '-Werror'])
        run_cpp(fixture, [*INCLUDES, '-Wall', '-Wextra', '-Werror', '-DDISABLE_GAMEMEMORY'])


if __name__ == '__main__':
    unittest.main()
