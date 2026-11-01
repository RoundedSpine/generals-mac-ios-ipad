#!/usr/bin/env python3
"""Compile production accounting functions with resource providers, without an iOS SDK."""
# GeneralsX @test Codex 01/11/2026 Validate counter coverage, 64-bit arithmetic and disabled/uninitialized engine states.
import unittest
from compiled_harness import ROOT, run_cpp


def function(path, marker):
    source = (ROOT / path).read_text()
    start = source.index(marker)
    return source[start:source.index('\n}', start) + 2]


class MemoryCounterTests(unittest.TestCase):
    def test_pool_usage_uses_wide_math_and_does_not_allocate(self):
        body = function('Core/GameEngine/Source/Common/System/GameMemory.cpp', 'void MemoryPoolFactory::getPoolMemoryUsage(')
        run_cpp(r'''
#include <cassert>
#include <cstddef>
#include <cstdint>
unsigned locks=0;int TheMemoryPoolCriticalSection=0;
struct ScopedCriticalSection{ScopedCriticalSection(int&){++locks;}~ScopedCriticalSection(){--locks;}};
struct MemoryPool{int used,total,bytes;MemoryPool*next;
 int getUsedBlockCount(){assert(locks==1);return used;}int getTotalBlockCount(){return total;}
 int getAllocationSize(){return bytes;}MemoryPool*getNextPoolInList(){return next;}};
struct MemoryPoolFactory{MemoryPool*m_firstPoolInFactory=nullptr;void getPoolMemoryUsage(size_t&,size_t&);};
BODY
int main(){MemoryPoolFactory factory;size_t used=123,reserved=123;
 factory.getPoolMemoryUsage(used,reserved);assert(used==0&&reserved==0&&locks==0);
 MemoryPool b{1,3,64,nullptr},a{100000000,200000000,128,&b};factory.m_firstPoolInFactory=&a;
 factory.getPoolMemoryUsage(used,reserved);assert(used==12800000064ull&&reserved==25600000192ull&&locks==0);
 a.used=0;b.used=0;factory.getPoolMemoryUsage(used,reserved);assert(used==0&&reserved==25600000192ull);}
'''.replace('BODY', body))

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
struct Factory{void getPoolMemoryUsage(size_t&used,size_t&reserved){used=1048576;reserved=4194304;}};
struct Logic{unsigned getObjectCount(){return 25;}};
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
#ifndef DISABLE_GAMEMEMORY
 assert(text.find("pool_status=ok pool_payload_used_mib=1.0 pool_payload_reserved_mib=4.0")!=std::string::npos);
#else
 assert(text.find("pool_status=disabled")!=std::string::npos);
#endif
}
'''.replace('BODY', body)
        run_cpp(fixture, ['-Wall', '-Wextra', '-Werror'])
        run_cpp(fixture, ['-Wall', '-Wextra', '-Werror', '-DDISABLE_GAMEMEMORY'])


if __name__ == '__main__':
    unittest.main()
