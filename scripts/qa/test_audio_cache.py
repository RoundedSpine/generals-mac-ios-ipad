#!/usr/bin/env python3
"""Exercise the production cache against deterministic decoder and OpenAL providers."""
# GeneralsX @test Codex 01/11/2026 Verify borrowed ownership, decoded budgeting, eviction and admission rollback.
import re
import unittest
from compiled_harness import ROOT, run_cpp


def fixture():
    header = (ROOT / 'Core/GameEngineDevice/Source/OpenALAudioDevice/OpenALAudioCache.h').read_text()
    header = header[header.index('struct OpenAudioFile'):]
    source = (ROOT / 'Core/GameEngineDevice/Source/OpenALAudioDevice/OpenALAudioCache.cpp').read_text()
    source = re.sub(r'^#include[^\n]*', '', source, flags=re.M).replace('extern "C" {\n\n}', '')
    return r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <functional>
#include <limits>
#include <list>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
using Bool=bool;using Int=int;using UnsignedInt=unsigned;using ALuint=unsigned;
constexpr bool FALSE=false,TRUE=true;
#define DEBUG_LOG(...) ((void)0)
#define DEBUG_ASSERTLOG(...) ((void)0)
#define DEBUG_CRASH(...) ((void)0)
enum {AVMEDIA_TYPE_AUDIO=1,PP_Attack,PP_Sound,PP_Decay,PP_Done,AL_NO_ERROR=0};
using AVSampleFormat=int;
int av_sample_fmt_is_planar(int format){return format==1;}
struct AsciiString {
 std::string value;AsciiString(const char*v=""):value(v){}
 const char*str()const{return value.c_str();}bool isEmpty()const{return value.empty();}
 bool operator==(const AsciiString&v)const{return value==v.value;}
};
bool failHash=false,failAdmission=false;
namespace rts {template<class T>struct hash {size_t operator()(const T&v)const{if(failHash)throw std::bad_alloc();return std::hash<std::string>{}(v.value);}};
template<class T>using equal_to=std::equal_to<T>;}
struct AudioEventInfo{int m_priority=0;AsciiString m_audioName;};
struct AudioEventRTS{
 AsciiString filename;AudioEventInfo info;int portion=PP_Sound;bool positional=false;
 int getNextPlayPortion(){return portion;}
 AsciiString getAttackFilename(){return filename;}AsciiString getFilename(){return filename;}
 AsciiString getDecayFilename(){return filename;}const AudioEventInfo*getAudioEventInfo(){return &info;}
 bool isPositionalAudio(){return positional;}
};
unsigned fileCount=0,decoderCount=0,decodeCalls=0,forcedStops=0;
bool missing=false,openFails=false,ctorThrows=false,decodeThrows=false,genFails=false,uploadFails=false;
unsigned frames=1,samples=1024,channels=2,bytesPerSample=4;bool planar=false;
struct File {File(){++fileCount;}void close(){--fileCount;delete this;}unsigned size(){return 1024;}};
struct FileSystem{File*openFile(const char*){return missing?nullptr:new File;}}fs;
auto*TheFileSystem=&fs;
struct AVFrame{int nb_samples,format;uint8_t*data[2];};
struct FFmpegFile{
 std::function<void(AVFrame*,int,int,void*)> callback;void*user=nullptr;File*file=nullptr;unsigned decoded=0;
 FFmpegFile(){if(ctorThrows)throw std::bad_alloc();++decoderCount;}
 ~FFmpegFile(){if(file)file->close();--decoderCount;}
 bool open(File*f){file=f;return !openFails;}
 int getSizeForSamples(int n){return n*channels*bytesPerSample;}
 int getNumChannels(){return channels;}int getBytesPerSample(){return bytesPerSample;}
 int getSampleRate(){return 44100;}
 void setFrameCallback(decltype(callback)cb){callback=cb;}void setUserData(void*p){user=p;}
 bool decodePacket(){++decodeCalls;if(decodeThrows)throw std::bad_alloc();if(decoded++>=frames)return false;
  std::vector<uint8_t> a(samples*channels*bytesPerSample,1),b(a.size(),2);
  AVFrame frame{static_cast<int>(samples),planar?1:0,{a.data(),b.data()}};
  callback(&frame,0,AVMEDIA_TYPE_AUDIO,user);return true;}
};
unsigned nextBuffer=0,error=0;std::unordered_map<ALuint,std::vector<uint8_t>> buffers;
int alGetError(){auto result=error;error=0;return result;}
void alGenBuffers(int,ALuint*p){if(genFails){error=1;return;}*p=++nextBuffer;buffers[*p]={};}
void alBufferData(ALuint buffer,int,const void*data,size_t size,int){
 if(uploadFails){error=1;return;}auto*bytes=static_cast<const uint8_t*>(data);buffers.at(buffer)={bytes,bytes+size};if(failAdmission)failHash=true;}
void alDeleteBuffers(int,ALuint*p){assert(buffers.erase(*p)==1);}
struct OpenALAudioManager{static int getALFormat(int,int){return 0;}};
struct AudioManager {std::function<void(ALuint)>close;
 void closeAnySamplesUsingFile(const void*p){++forcedStops;if(close)close(static_cast<ALuint>(reinterpret_cast<uintptr_t>(p)));}}audio;
auto*TheAudio=&audio;
''' + header + source + r'''
struct Cache:OpenALAudioFileCache {
 void budget(unsigned n){m_maxSize=n;}
 unsigned count(ALuint b){for(auto&e:m_openFiles)if(e.second.m_buffer==b)return e.second.m_openCount;assert(false);return 0;}
 ALuint load(const char*name){AsciiString file(name);return getBufferForFile(OpenFileInfo(&file));}
};
void empty(){assert(fileCount==0&&decoderCount==0&&buffers.empty());}
'''


class AudioCacheTests(unittest.TestCase):
    def test_first_borrow_cache_hits_and_unmatched_closes(self):
        run_cpp(fixture() + r'''
int main(){{Cache cache;auto a=cache.load("a");assert(a&&cache.count(a)==1);
 assert(cache.getCurrentlyUsedSize()==8192&&cache.getCachedBufferCount()==1);
 assert(fileCount==0&&decoderCount==0&&decodeCalls==2);
 assert(cache.load("a")==a&&cache.count(a)==2&&decodeCalls==2);
 cache.closeBuffer(a);assert(cache.count(a)==1);cache.closeBuffer(a);assert(cache.count(a)==0);
 for(int i=0;i<1000;++i){assert(cache.load("a")==a);assert(cache.getBufferLength(a)>23);cache.closeBuffer(a);}
 assert(cache.count(a)==0&&decodeCalls==2);
 cache.closeBuffer(a);cache.closeBuffer(a+1);cache.closeBuffer(0);
 assert(cache.getUnmatchedCloseCount()==2&&cache.count(a)==0);}empty();}
''')

    def test_decoded_pcm_budget_evicts_idle_entries(self):
        run_cpp(fixture() + r'''
int main(){{Cache cache;cache.budget(8192);auto a=cache.load("a");cache.closeBuffer(a);
 auto b=cache.load("b");assert(b&&b!=a&&buffers.count(a)==0);
 assert(cache.getCurrentlyUsedSize()==8192&&cache.getCachedBufferCount()==1&&forcedStops==0);
 assert(cache.load("c")==0&&cache.count(b)==1&&cache.getCurrentlyUsedSize()==8192);
 cache.closeBuffer(b);}empty();}
''')

    def test_priority_eviction_closes_all_borrowers(self):
        run_cpp(fixture() + r'''
int main(){{Cache cache;cache.budget(8192);AudioEventRTS low,high;low.filename="low";high.filename="high";
 low.info.m_priority=1;high.info.m_priority=2;
 auto a=cache.getBufferForFile(OpenFileInfo(&low));assert(cache.getBufferForFile(OpenFileInfo(&low))==a);
 audio.close=[&](ALuint b){assert(b==a);cache.closeBuffer(b);cache.closeBuffer(b);};
 auto b=cache.getBufferForFile(OpenFileInfo(&high));assert(b&&forcedStops==1&&buffers.count(a)==0);
 assert(cache.getCurrentlyUsedSize()==8192&&cache.getCachedBufferCount()==1&&cache.getUnmatchedCloseCount()==0);
 cache.closeBuffer(b);audio.close=nullptr;}empty();}
''')

    def test_failed_admission_releases_handles_files_and_budget(self):
        run_cpp(fixture() + r'''
int main(){Cache cache;
 missing=true;assert(!cache.load("missing"));missing=false;empty();
 genFails=true;assert(!cache.load("gen"));genFails=false;empty();
 openFails=true;assert(!cache.load("open"));openFails=false;empty();
 uploadFails=true;assert(!cache.load("upload"));uploadFails=false;empty();
 ctorThrows=true;try{cache.load("ctor");assert(false);}catch(const std::bad_alloc&){}ctorThrows=false;empty();
 decodeThrows=true;try{cache.load("decode");assert(false);}catch(const std::bad_alloc&){}decodeThrows=false;empty();
 failAdmission=true;try{cache.load("admission");assert(false);}catch(const std::bad_alloc&){}failAdmission=failHash=false;empty();
 frames=0;assert(!cache.load("empty"));frames=1;empty();
 assert(cache.getCurrentlyUsedSize()==0&&cache.getCachedBufferCount()==0);
 auto a=cache.load("valid");assert(a&&cache.count(a)==1);cache.closeBuffer(a);}
''')

    def test_oversized_decode_stops_early_and_does_not_upload(self):
        run_cpp(fixture() + r'''
int main(){Cache cache;cache.budget(16384);frames=10000;
 assert(!cache.load("compressed"));assert(decodeCalls==3&&cache.getCurrentlyUsedSize()==0);empty();
 frames=1;samples=4096;assert(!cache.load("large_frame"));assert(decodeCalls==4);empty();}
''')

    def test_planar_conversion_and_multi_frame_pcm_accounting(self):
        run_cpp(fixture() + r'''
int main(){{Cache cache;planar=true;bytesPerSample=2;samples=8;frames=3;
 auto a=cache.load("planar");assert(a&&cache.getCurrentlyUsedSize()==96);
 const auto&data=buffers.at(a);assert(data.size()==96);
 for(size_t i=0;i<data.size();++i)assert(data[i]==((i%4)<2?1:2));
 cache.closeBuffer(a);}empty();}
''')


if __name__ == '__main__':
    unittest.main()
