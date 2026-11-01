#!/usr/bin/env python3
"""Compile production decoder/stream setup with counted, faulting providers.

No FFmpeg/OpenAL SDK is required. Native codec validation is a separate check.
"""
# GeneralsX @test Codex 01/11/2026 Exercise partial ownership, exceptions, packet retry and failed resizing.
import re
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from compiled_harness import ROOT, run_cpp

DEVICE = ROOT / 'Core/GameEngineDevice'


def function(source, marker):
    start = source.index(marker)
    return source[start:source.index('\n}', start) + 2]


def decoder_fixture():
    header = (DEVICE / 'Include/VideoDevice/FFmpeg/FFmpegFile.h').read_text()
    header = re.sub(r'^#(?:include|pragma once)[^\n]*', '', header, flags=re.M)
    source = (DEVICE / 'Source/VideoDevice/FFmpeg/FFmpegFile.cpp').read_text()
    source = re.sub(r'^#include[^\n]*', '', source, flags=re.M)
    source = source[:source.index('\nvoid FFmpegFile::seekFrame')]
    return r'''
#include <cassert>
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <memory>
#include <new>
#include <type_traits>
#include <vector>
using Bool=bool;using Int=int;using UnsignedInt=unsigned;using UnsignedByte=unsigned char;
#define DEBUG_ASSERTCRASH(x,...) assert(x)
#define DEBUG_LOG(...) ((void)0)
#define LOGGING_LEVEL 0
#define LOGLEVEL_NONE 0
#define AVERROR(x) (-(x))
#define LIBAVFORMAT_VERSION_MAJOR 62
constexpr int AVERROR_EOF=-12345,AVFMT_FLAG_CUSTOM_IO=1,AVMEDIA_TYPE_AUDIO=1;
bool failNextNew=false;
void*operator new(std::size_t n){if(failNextNew){failNextNew=false;throw std::bad_alloc();}
 if(void*p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void operator delete(void*p)noexcept{std::free(p);}
void operator delete(void*p,std::size_t)noexcept{std::free(p);}
int files=0,formats=0,ios=0,codecs=0,frames=0,packets=0,buffers=0;
int fault=0,streamIndex=0,failingStream=0,readMode=0,sendMode=0,sends=0,receives=0,queued=0;
void*rejected=nullptr;
struct File{File(){++files;}int read(uint8_t*,int){return 0;}void close(){--files;delete this;}};
struct AVCodec{int type=AVMEDIA_TYPE_AUDIO;};
struct AVCodecParameters{int codec_id=1;};
struct AVStream{AVCodecParameters*codecpar=new AVCodecParameters;};
struct AVIOContext{uint8_t*buffer;};
struct AVFormatContext{AVIOContext*pb=nullptr;int flags=0;unsigned nb_streams=2;
 AVStream**streams=new AVStream*[2]{new AVStream,new AVStream};};
struct AVCodecContext{};
struct AVFrame{};
struct AVPacket{int stream_index=0,size=0;uint8_t*data=nullptr;};
void*av_malloc(size_t n){if(fault==2)return nullptr;void*p=std::malloc(n);if(p)++buffers;return p;}
void av_free(void*p){if(p){--buffers;std::free(p);}}
template<class T>void av_freep(T**p){av_free(*p);*p=nullptr;}
AVFormatContext*avformat_alloc_context(){if(fault==1)return nullptr;++formats;return new AVFormatContext;}
AVIOContext*avio_alloc_context(uint8_t*b,size_t,int,void*,int(*)(void*,uint8_t*,int),void*,void*){
 if(fault==3)return nullptr;++ios;return new AVIOContext{b};}
void avio_context_free(AVIOContext**p){if(*p){--ios;delete *p;*p=nullptr;}}
void avformat_close_input(AVFormatContext**p){if(*p){for(int i=0;i<2;++i){delete (*p)->streams[i]->codecpar;delete (*p)->streams[i];}
 delete[](*p)->streams;delete *p;*p=nullptr;--formats;}}
int avformat_open_input(AVFormatContext**,void*,void*,void*){return fault==4?-1:0;}
int avformat_find_stream_info(AVFormatContext*,void*){if(fault==13)failNextNew=true;return fault==5?-1:0;}
const AVCodec*avcodec_find_decoder(int){static AVCodec c;int idx=streamIndex++;return fault==6&&idx==failingStream?nullptr:&c;}
const char*avcodec_get_name(int){return "mock";}
int av_strerror(int,char*,size_t){return 0;}
bool failStream(int stage){return fault==stage&&streamIndex-1==failingStream;}
AVCodecContext*avcodec_alloc_context3(const AVCodec*){if(failStream(7))return nullptr;++codecs;return new AVCodecContext;}
int avcodec_parameters_to_context(AVCodecContext*,AVCodecParameters*){return failStream(8)?-1:0;}
int avcodec_open2(AVCodecContext*,const AVCodec*,void*){return failStream(9)?-1:0;}
void avcodec_free_context(AVCodecContext**p){if(*p){--codecs;delete *p;*p=nullptr;}}
AVFrame*av_frame_alloc(){if(failStream(10))return nullptr;++frames;return new AVFrame;}
void av_frame_free(AVFrame**p){if(*p){--frames;delete *p;*p=nullptr;}}
AVPacket*av_packet_alloc(){if(fault==11)return nullptr;++packets;return new AVPacket;}
void av_packet_unref(AVPacket*p){av_free(p->data);p->data=nullptr;p->size=0;}
void av_packet_free(AVPacket**p){if(*p){av_packet_unref(*p);--packets;delete *p;*p=nullptr;}}
int av_read_frame(AVFormatContext*,AVPacket*p){assert(!p->data);if(readMode==1)return AVERROR_EOF;
 if(readMode==2)return -EIO;p->data=static_cast<uint8_t*>(av_malloc(16));p->size=16;
 p->stream_index=readMode==3?-1:readMode==4?100:0;return 0;}
int avcodec_send_packet(AVCodecContext*,AVPacket*p){++sends;assert(p->data);
 if(sendMode==1&&sends==1){rejected=p->data;queued=1;return -EAGAIN;}
 if(sendMode==2)return -EINVAL;
 if(sendMode==1){assert(sends==2&&receives==2&&p->data==rejected);}
 queued=1;return 0;}
int avcodec_receive_frame(AVCodecContext*,AVFrame*){++receives;if(queued){--queued;return 0;}return -EAGAIN;}
void empty(){assert(!files&&!formats&&!ios&&!codecs&&!frames&&!packets&&!buffers);}
''' + header + source


def streaming_fixture():
    source = (DEVICE / 'Source/OpenALAudioDevice/OpenALAudioManager.cpp').read_text()
    play = function(source, 'void OpenALAudioManager::playAudioEvent(')
    # The entire streaming case is unchanged production code; sound-effect paths
    # have separate cache tests and would otherwise require the full game engine.
    a = play.index('\n\tcase AT_SoundEffect:')
    b = play.index('\n\t// If we were able', a)
    play = play[:a] + '\n\tcase AT_SoundEffect: break;\n\t}\n' + play[b:]
    return r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <functional>
#include <list>
#include <memory>
#include <new>
#include <string>
#include <vector>
using Real=float;using Bool=bool;using AudioHandle=int;using ALenum=int;using ALuint=unsigned;
#define NEW new
#define DEBUG_LOG(...) ((void)0)
constexpr int AT_Music=1,AT_Streaming=2,AT_SoundEffect=3,PAT_Stream=1;
constexpr int AVMEDIA_TYPE_AUDIO=1;
constexpr bool TRUE=true;
enum AVSampleFormat{AV_SAMPLE_FMT_S16P};
int fileCount=0,decoderCount=0,streamCount=0,eventCount=0,playingCount=0,scratch=0;
int fault=0;bool validInfo=true;int missingHandle=0;
struct AsciiString{const char*str()const{return "audio";}};
struct AudioEventInfo{int m_soundType=AT_Music;};
struct AudioEventRTS{AudioEventInfo info;AudioEventRTS(){++eventCount;}~AudioEventRTS(){--eventCount;}
 const AudioEventInfo*getAudioEventInfo(){return validInfo?&info:nullptr;}
 int getHandleToKill(){return missingHandle;}AsciiString getFilename(){return {};}
 bool getUninterruptible(){return false;}float getVolume(){return 1;}int getPlayingHandle(){return 1;}};
struct File{File(){++fileCount;}void close(){--fileCount;delete this;}};
struct FileSystem{File*openFile(const char*){return fault==1?nullptr:new File;}}fs;
auto*TheFileSystem=&fs;
struct AVFrame{int format=0,nb_samples=1,sample_rate=8000;struct{int nb_channels=1;}ch_layout;uint8_t*data[1];};
int av_get_bytes_per_sample(AVSampleFormat){return 2;}
int av_samples_get_buffer_size(void*,int,int,AVSampleFormat,int){return 2;}
bool av_sample_fmt_is_planar(AVSampleFormat){return true;}
void*av_malloc(size_t n){if(fault==10)return nullptr;++scratch;return new uint8_t[n];}
void av_free(void*p){if(p){--scratch;delete[]static_cast<uint8_t*>(p);}}
struct FFmpegFile{File*file=nullptr;std::function<void(AVFrame*,int,int,void*)>callback;
 FFmpegFile(){if(fault==2)throw std::bad_alloc();++decoderCount;}~FFmpegFile(){if(file)file->close();--decoderCount;}
 bool open(File*f){file=f;if(fault==4)throw std::bad_alloc();return fault!=3;}
 bool decodePacket(){return false;}bool isAtEof(){return false;}
 void setFrameCallback(decltype(callback)c){if(fault==7)throw std::bad_alloc();callback=c;}};
struct OpenALAudioStream{std::function<bool()>callback;OpenALAudioStream(){if(fault==5)throw std::bad_alloc();++streamCount;}
 ~OpenALAudioStream(){--streamCount;}void setRequireDataCallback(decltype(callback)c){if(fault==6)throw std::bad_alloc();callback=c;}
 void bufferData(uint8_t*,int,int,int){if(fault==11)throw std::bad_alloc();}};
struct PlayingAudio{OpenALAudioStream*m_stream=nullptr;FFmpegFile*m_ffmpegFile=nullptr;
 AudioEventRTS*m_audioEventRTS=nullptr;int m_type=0;PlayingAudio(){++playingCount;}~PlayingAudio(){--playingCount;}};
struct GameLogic{int getFrame(){return 1;}}logic;
auto*TheGameLogic=&logic;unsigned s_disallowSpeechSetFrame=0;
struct OpenALAudioManager{std::list<PlayingAudio*>m_playingStreams;float m_musicVolume=1,m_speechVolume=1;
 void playAudioEvent(AudioEventRTS*);
 PlayingAudio*allocatePlayingAudio(){if(fault==8)throw std::bad_alloc();return new PlayingAudio;}
 void releasePlayingAudio(PlayingAudio*p){delete p->m_stream;delete p->m_ffmpegFile;delete p->m_audioEventRTS;delete p;}
 void stopAllSpeech(){}void setDisallowSpeech(bool){}void playStream(AudioEventRTS*,OpenALAudioStream*){if(fault==9)throw std::bad_alloc();}
 static int getALFormat(int,int){return 0;}
 ~OpenALAudioManager(){for(auto*p:m_playingStreams)releasePlayingAudio(p);}};
void empty(){assert(!fileCount&&!decoderCount&&!streamCount&&!eventCount&&!playingCount&&!scratch);}
''' + play


def video_fixture():
    source = (DEVICE / 'Source/VideoDevice/FFmpeg/FFmpegVideoPlayer.cpp').read_text()
    return r'''
#include <cassert>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <memory>
#include <new>
using Int=int;using Bool=bool;using ALenum=int;
#define SAGE_USE_OPENAL
#define NEW new
#define DEBUG_LOG(...) ((void)0)
constexpr int AVMEDIA_TYPE_AUDIO=1,AVMEDIA_TYPE_VIDEO=2;
enum AVSampleFormat{AV_SAMPLE_FMT_FLT,AV_SAMPLE_FMT_FLTP,AV_SAMPLE_FMT_S16P};
int allocations=0,frameCount=0,fileCount=0,decoderCount=0,fault=0;
void*av_malloc(size_t n){++allocations;return std::malloc(n);}
void*av_realloc(void*p,size_t n){if(fault==1)return nullptr;if(!p)++allocations;return std::realloc(p,n);}
template<class T>void av_freep(T**p){if(*p){--allocations;std::free(*p);*p=nullptr;}}
struct AVFrame{int format=AV_SAMPLE_FMT_FLTP,nb_samples=4;struct{int nb_channels=1;}ch_layout;
 uint8_t*data[1];int sample_rate=8000;};
AVFrame*av_frame_clone(AVFrame*p){++frameCount;return new AVFrame(*p);}
void av_frame_free(AVFrame**p){if(*p){--frameCount;delete *p;*p=nullptr;}}
void sws_freeContext(void*){}
int av_get_bytes_per_sample(AVSampleFormat fmt){return fmt==AV_SAMPLE_FMT_S16P?2:4;}
int av_samples_get_buffer_size(void*,int c,int n,AVSampleFormat fmt,int){return c*n*av_get_bytes_per_sample(fmt);}
bool av_sample_fmt_is_planar(AVSampleFormat fmt){return fmt!=AV_SAMPLE_FMT_FLT;}
struct OpenALAudioStream{int uploads=0;void reset(){}void play(){}void update(){}
 void setVolume(float){if(fault==5)throw std::bad_alloc();}
 void bufferData(uint8_t*,int,int,int){++uploads;}};
struct Audio{OpenALAudioStream stream;void*getHandleForBink(){return &stream;}
 float getVolume(int){return 1;}}audio;
auto*TheAudio=&audio;constexpr int AudioAffect_Speech=1;
struct OpenALAudioManager{static int getALFormat(int,int){return 0;}};
struct File{File(){++fileCount;}void close(){--fileCount;delete this;}};
struct FFmpegFile{File*file=nullptr;void*user=nullptr;int phase=0;
 std::function<void(AVFrame*,int,int,void*)>callback;
 FFmpegFile(){if(fault==2)throw std::bad_alloc();++decoderCount;}
 ~FFmpegFile(){if(file)file->close();--decoderCount;}
 bool open(File*f){file=f;if(fault==4)throw std::bad_alloc();return fault!=3;}
 void setFrameCallback(decltype(callback)c){callback=c;}void setUserData(void*p){user=p;}
 bool decodePacket(){float samples[4]={0,.5f,-.5f,1};AVFrame frame;frame.data[0]=reinterpret_cast<uint8_t*>(samples);
 callback(&frame,0,phase++?AVMEDIA_TYPE_VIDEO:AVMEDIA_TYPE_AUDIO,user);return true;}};
struct VideoStreamInterface{virtual ~VideoStreamInterface()=default;};
struct FFmpegVideoPlayer;
struct FFmpegVideoStream:VideoStreamInterface{bool m_good=true,m_gotFrame=false;AVFrame*m_frame=nullptr;
 void*m_swsContext=nullptr;FFmpegFile*m_ffmpegFile;uint8_t*m_audioBuffer=nullptr;uint64_t m_startTime=0;
 FFmpegVideoStream*m_next=nullptr;FFmpegVideoPlayer*m_player=nullptr;
 explicit FFmpegVideoStream(FFmpegFile*);~FFmpegVideoStream();
 static void onFrame(AVFrame*,int,int,void*);};
struct FFmpegVideoPlayer{FFmpegVideoStream*m_firstStream=nullptr;VideoStreamInterface*createStream(File*);};
void empty(){assert(!allocations&&!frameCount&&!fileCount&&!decoderCount);}
''' + '\n'.join(function(source, marker) for marker in [
        'VideoStreamInterface* FFmpegVideoPlayer::createStream(',
        'FFmpegVideoStream::FFmpegVideoStream(',
        'FFmpegVideoStream::~FFmpegVideoStream()',
        'void FFmpegVideoStream::onFrame('])


class OwnershipTests(unittest.TestCase):
    def test_zero_hour_headers_use_shared_owning_types(self):
        with tempfile.TemporaryDirectory() as temp:
            include = Path(temp)
            (include / 'Lib').mkdir()
            (include / 'GameClient').mkdir()
            (include / 'Lib/BaseType.h').write_text('#pragma once\nusing Bool=bool;using Int=int;using UnsignedInt=unsigned;'
                'using Char=char;using UnsignedByte=unsigned char;using UnsignedInt64=unsigned long long;\n')
            # Compile the real base interface too, so override checking cannot be
            # satisfied by an unrelated stand-in with matching method names.
            (include / 'Common').mkdir()
            (include / 'WWMath').mkdir()
            with (include / 'Lib/BaseType.h').open('a') as output:
                output.write('using Real=float;\n')
            (include / 'WWMath/rect.h').write_text('class RectClass {};\n')
            (include / 'Common/SubsystemInterface.h').write_text(
                'class SubsystemInterface {public: virtual ~SubsystemInterface()=default;'
                'virtual void init()=0;virtual void reset()=0;virtual void update()=0;};\n')
            (include / 'Common/AsciiString.h').write_text('class AsciiString {};\n')
            (include / 'Common/INI.h').write_text('struct FieldParse {};\n')
            (include / 'Common/STLTypedefs.h').write_text('#include <vector>\n')
            (include / 'GameClient/VideoPlayer.h').write_text(
                (ROOT / 'Core/GameEngine/Include/GameClient/VideoPlayer.h').read_text())
            headers = ROOT / 'GeneralsMD/Code/GameEngineDevice/Include/VideoDevice/FFmpeg'
            run_cpp(f'#include "{headers / "FFmpegFile.h"}"\n'
                f'#include "{headers / "FFmpegVideoPlayer.h"}"\n' + r'''
#include <type_traits>
static_assert(!std::is_copy_constructible<FFmpegFile>::value);
static_assert(sizeof(FFmpegVideoStream)>sizeof(void*));
int main(){}
''', extra_flags=['-I', str(include), '-Werror', '-Wsuggest-override'])

    def test_video_factory_partial_constructor_and_realloc(self):
        run_cpp(video_fixture() + r'''
int main(){FFmpegVideoPlayer player;
 for(fault=2;fault<=5;++fault){try{auto*p=player.createStream(new File);assert(!p);}
 catch(const std::bad_alloc&){}empty();}
 fault=0;auto*stream=static_cast<FFmpegVideoStream*>(player.createStream(new File));
 assert(stream&&allocations==1&&frameCount==1&&fileCount==1&&decoderCount==1);
 auto*original=stream->m_audioBuffer;int uploads=audio.stream.uploads;
 float samples[4]={0,.5f,-.5f,1};AVFrame frame;frame.data[0]=reinterpret_cast<uint8_t*>(samples);
 fault=1;for(int fmt=AV_SAMPLE_FMT_FLT;fmt<=AV_SAMPLE_FMT_S16P;++fmt){frame.format=fmt;
 FFmpegVideoStream::onFrame(&frame,0,AVMEDIA_TYPE_AUDIO,stream);
 assert(stream->m_audioBuffer==original&&allocations==1&&audio.stream.uploads==uploads);}
 fault=0;delete stream;empty();}
''')

    def test_cmake_compiles_one_shared_implementation(self):
        """Resolve actual source declarations through a small CMake target graph."""
        core = (DEVICE / 'CMakeLists.txt').read_text()
        a = core.index('        target_sources(corei_gameenginedevice_private INTERFACE\n            Include/VideoDevice/FFmpeg')
        sources = core[a:core.index('\n        target_include_directories', a)]
        zh = (ROOT / 'GeneralsMD/Code/GameEngineDevice/CMakeLists.txt').read_text()
        a = zh.index('if(RTS_BUILD_OPTION_FFMPEG)', zh.index('# Phase 3:'))
        block = zh[a:zh.index('\n# CURL::', a)]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ['Core', 'ZH', 'cmake']:
                (root / directory).mkdir()
            (root / 'cmake/ffmpeg_framework_fix.cmake').write_text('function(sage_fix_ffmpeg_framework_flags)\nendfunction()\n')
            for directory in ['Core', 'ZH']:
                for filename in re.findall(r'(?:Include|Source)/VideoDevice/[^\s)]+', sources + block):
                    p = root / directory / filename
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text('// fixture translation unit\n')
            (root / 'Core/CMakeLists.txt').write_text('add_library(corei_gameenginedevice_private INTERFACE)\n' + sources)
            (root / 'ZH/dummy.cpp').write_text('void fixture(){}\n')
            (root / 'ZH/CMakeLists.txt').write_text('add_library(z_gameenginedevice STATIC dummy.cpp)\n'
                'target_link_libraries(z_gameenginedevice PRIVATE corei_gameenginedevice_private)\n' + block)
            (root / 'main.cpp').write_text('int main(){}\n')
            (root / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(ownership CXX)\n'
                'set(CMAKE_EXPORT_COMPILE_COMMANDS ON)\nset(RTS_BUILD_OPTION_FFMPEG ON)\n'
                'add_library(PkgConfig::FFMPEG INTERFACE IMPORTED GLOBAL)\n'
                'add_subdirectory(Core)\nadd_subdirectory(ZH)\nadd_executable(game main.cpp)\n'
                'target_link_libraries(game PRIVATE z_gameenginedevice)\n')
            result = subprocess.run(['cmake', '-S', str(root), '-B', str(root / 'build')], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            commands = json.loads((root / 'build/compile_commands.json').read_text())
            for name in ['FFmpegFile.cpp', 'FFmpegVideoPlayer.cpp']:
                matches = [Path(c['file']) for c in commands if Path(c['file']).name == name]
                self.assertEqual([root / 'Core/Source/VideoDevice/FFmpeg' / name], matches)

    def test_partial_open_and_throwing_storage_cleanup(self):
        run_cpp(decoder_fixture() + r'''
int main(){static_assert(!std::is_copy_constructible<FFmpegFile>::value);
 static_assert(!std::is_copy_assignable<FFmpegFile>::value);
 for(fault=1;fault<=11;++fault)for(failingStream=0;failingStream<2;++failingStream){
  streamIndex=0;FFmpegFile d;assert(!d.open(new File));empty();d.close();empty();}
 fault=13;try{FFmpegFile d(new File);assert(false);}catch(const std::bad_alloc&){}empty();
 fault=0;for(int n=0;n<1000;++n){streamIndex=0;FFmpegFile d;assert(d.open(new File));d.close();d.close();empty();}}
''')

    def test_packet_errors_and_same_packet_retry(self):
        run_cpp(decoder_fixture() + r'''
int main(){for(int mode=0;mode<5;++mode){streamIndex=0;FFmpegFile d;assert(d.open(new File));
 readMode=mode;sends=receives=0;int calls=0;d.setFrameCallback([&](AVFrame*,int,int,void*){++calls;});
 assert(d.decodePacket()==(mode==0));assert(sends==(mode==0?1:0));assert(d.isAtEof()==(mode==1));
 assert(calls==(mode==0?1:0));assert(buffers==1);d.close();empty();}
 readMode=0;streamIndex=0;{FFmpegFile d;assert(d.open(new File));sendMode=1;sends=receives=0;
 int calls=0;d.setFrameCallback([&](AVFrame*,int,int,void*){++calls;});assert(d.decodePacket());
 assert(sends==2&&calls==2&&buffers==1);d.close();empty();}
 streamIndex=0;{FFmpegFile d;assert(d.open(new File));sendMode=2;sends=0;
 assert(!d.decodePacket()&&sends==1&&buffers==1);d.close();empty();}
 streamIndex=0;{FFmpegFile d;assert(d.open(new File));sendMode=1;sends=receives=0;
 d.setFrameCallback([](AVFrame*,int,int,void*){throw std::bad_alloc();});
 try{d.decodePacket();assert(false);}catch(const std::bad_alloc&){}assert(buffers==1);d.close();empty();}}
''')

    def test_stream_setup_failure_and_success_ownership(self):
        run_cpp(streaming_fixture() + r'''
int main(){for(fault=1;fault<=9;++fault){try{OpenALAudioManager manager;manager.playAudioEvent(new AudioEventRTS);}
 catch(const std::bad_alloc&){}empty();}
 fault=0;validInfo=false;{OpenALAudioManager m;m.playAudioEvent(new AudioEventRTS);}empty();validInfo=true;
 missingHandle=5;{OpenALAudioManager m;m.playAudioEvent(new AudioEventRTS);assert(m.m_playingStreams.empty());}empty();missingHandle=0;
 {OpenALAudioManager m;m.playAudioEvent(new AudioEventRTS);assert(m.m_playingStreams.size()==1);
 assert(fileCount==1&&decoderCount==1&&streamCount==1&&eventCount==1&&playingCount==1);}
 empty();}
''')

    def test_stream_conversion_scratch_failure_and_exception(self):
        run_cpp(streaming_fixture() + r'''
int main(){{OpenALAudioManager m;m.playAudioEvent(new AudioEventRTS);auto*p=m.m_playingStreams.front();
 uint8_t samples[2]={1,2};AVFrame frame;frame.data[0]=samples;
 for(fault=10;fault<=11;++fault){try{p->m_ffmpegFile->callback(&frame,0,AVMEDIA_TYPE_AUDIO,nullptr);}
 catch(const std::bad_alloc&){}assert(!scratch);}
 fault=0;p->m_ffmpegFile->callback(&frame,0,AVMEDIA_TYPE_AUDIO,nullptr);assert(!scratch);}
 empty();}
''')


if __name__ == '__main__':
    unittest.main()
