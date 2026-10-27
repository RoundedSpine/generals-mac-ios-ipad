#!/usr/bin/env python3
"""Exercise production OpenAL streaming with persistent errors, pause, EOF and refill stand-ins."""
# GeneralsX @bugfix Codex 27/10/2026 Reproduce null-context spinning and unwanted automatic unpause.
import unittest
from compiled_harness import ROOT, run_cpp

SOURCE=(ROOT/'Core/GameEngineDevice/Source/OpenALAudioDevice/OpenALAudioStream.cpp').read_text()


def function(marker):
    a=SOURCE.index(marker)
    return SOURCE[a:SOURCE.index('\n}',a)+2]


def fixture():
    return r'''
#include <cassert>
#include <cstdint>
#include <functional>
#include <cstddef>
using ALuint=unsigned;using ALint=int;using ALenum=int;
constexpr int AL_NO_ERROR=0,AL_INVALID_OPERATION=99,AL_SOURCE_STATE=1,AL_BUFFERS_QUEUED=2,
 AL_BUFFERS_PROCESSED=3,AL_STOPPED=4,AL_INITIAL=5,AL_PLAYING=6,AL_PAUSED=7,AL_BUFFER=8,AL_STREAM_BUFFER_COUNT=32;
#define DEBUG_LOG(m) ((void)0)
struct Driver {bool context=true,queryFails=false,uploadFails=false,queueFails=false;
 int error=0,errorCalls=0,state=AL_PLAYING,queued=0,processed=0,plays=0,uploads=0,unqueues=0;}driver;
void*alcGetCurrentContext(){return driver.context?&driver:nullptr;}
int alGetError(){assert(++driver.errorCalls<100);if(!driver.context)return AL_INVALID_OPERATION;int e=driver.error;driver.error=0;return e;}
void alGetSourcei(ALuint,int property,int*out){if(driver.queryFails||!driver.context){driver.error=AL_INVALID_OPERATION;return;}
 *out=property==AL_SOURCE_STATE?driver.state:property==AL_BUFFERS_QUEUED?driver.queued:driver.processed;}
void alBufferData(ALuint,int,uint8_t*,std::size_t,int){++driver.uploads;if(driver.uploadFails)driver.error=AL_INVALID_OPERATION;}
void alSourceQueueBuffers(ALuint,int,ALuint*){if(driver.queueFails)driver.error=AL_INVALID_OPERATION;else ++driver.queued;}
void alSourceUnqueueBuffers(ALuint,int,ALuint*out){assert(driver.queued>0&&driver.processed>0);--driver.queued;--driver.processed;++driver.unqueues;*out=1;}
void alSourceStop(ALuint){driver.state=AL_STOPPED;driver.processed=driver.queued;}
void alSourcei(ALuint,int,int){driver.queued=driver.processed=0;}
struct OpenALAudioStream {
 unsigned m_source=1,m_buffers[32]{},m_current_buffer_idx=0;
 bool m_endOfData=false;int m_stalledProbes=0;std::function<bool()>m_requireDataCallback;
 bool bufferData(uint8_t*,std::size_t,int,int);void update();void reset();bool isPlaying();
 void play(){++driver.plays;driver.state=AL_PLAYING;}
};
'''+'\n'.join(function(m)for m in ['bool OpenALAudioStream::bufferData(', 'void OpenALAudioStream::update()',
                                    'void OpenALAudioStream::reset()', 'bool OpenALAudioStream::isPlaying()'])


class StreamTests(unittest.TestCase):
    def test_null_context_is_finite_and_does_not_advance_stream(self):
        run_cpp(fixture()+r'''
int main(){OpenALAudioStream stream;driver.context=false;int decodes=0;stream.m_requireDataCallback=[&]{++decodes;return true;};
 assert(!stream.bufferData(nullptr,1,1,44100));stream.update();assert(!stream.isPlaying());
 assert(!driver.errorCalls&&!driver.uploads&&!driver.plays&&!decodes&&!stream.m_current_buffer_idx&&!stream.m_endOfData);}
''')

    def test_explicit_pause_is_preserved_until_caller_resumes(self):
        run_cpp(fixture()+r'''
int main(){OpenALAudioStream stream;driver.state=AL_PAUSED;driver.queued=20;driver.processed=3;int decodes=0;
 stream.m_requireDataCallback=[&]{++decodes;return true;};
 for(int n=0;n<50;++n)stream.update();assert(driver.state==AL_PAUSED&&!driver.plays&&!driver.unqueues&&!decodes);
 stream.play();stream.update();assert(driver.state==AL_PLAYING&&driver.plays==1&&driver.unqueues==3);}
''')

    def test_one_sticky_error_cleared_then_new_failures_return_false(self):
        run_cpp(fixture()+r'''
int main(){OpenALAudioStream stream;driver.error=AL_INVALID_OPERATION;uint8_t sample=1;
 assert(stream.bufferData(&sample,1,1,44100));assert(driver.uploads==1&&driver.queued==1&&stream.m_current_buffer_idx==1);
 driver.uploadFails=true;assert(!stream.bufferData(&sample,1,1,44100));assert(stream.m_current_buffer_idx==1);
 driver.uploadFails=false;driver.queueFails=true;assert(!stream.bufferData(&sample,1,1,44100));assert(stream.m_current_buffer_idx==1);}
''')

    def test_failed_queries_and_full_queues_do_not_upload(self):
        run_cpp(fixture()+r'''
int main(){OpenALAudioStream stream;driver.queryFails=true;assert(!stream.bufferData(nullptr,1,1,44100));
 assert(!stream.isPlaying());driver.queryFails=false;driver.queued=32;
 assert(!stream.bufferData(nullptr,1,1,44100));assert(!driver.uploads&&!stream.m_current_buffer_idx);}
''')

    def test_finished_speech_is_not_restarted_and_reset_clears_eof(self):
        run_cpp(fixture()+r'''
int main(){OpenALAudioStream stream;stream.m_endOfData=true;stream.m_stalledProbes=3;
 driver.state=AL_STOPPED;driver.queued=driver.processed=3;stream.update();
 assert(!driver.queued&&driver.unqueues==3&&!driver.plays&&!stream.isPlaying());
 stream.reset();assert(!stream.m_endOfData&&!stream.m_stalledProbes&&!stream.m_current_buffer_idx);}
''')

    def test_manager_does_not_treat_failed_queries_as_completion(self):
        manager=(ROOT/'Core/GameEngineDevice/Source/OpenALAudioDevice/OpenALAudioManager.cpp').read_text()
        a=manager.index('static inline bool sourceIsStopped(')
        helper=manager[a:manager.index('\n}',a)+2]
        run_cpp(fixture()+helper+r'''
int main(){driver.queryFails=true;assert(!sourceIsStopped(1));driver.queryFails=false;
 for(int state:{AL_PAUSED,AL_PLAYING,AL_INITIAL}){driver.state=state;assert(!sourceIsStopped(1));}
 driver.state=AL_STOPPED;assert(sourceIsStopped(1));}
''')

    def test_healthy_refill_still_starts_empty_stream(self):
        run_cpp(fixture()+r'''
int main(){OpenALAudioStream stream;driver.state=AL_STOPPED;int decodes=0;
 stream.m_requireDataCallback=[&]{++decodes;return stream.bufferData(nullptr,1,1,44100);};
 stream.update();assert(driver.queued==16&&decodes==16&&driver.plays==1&&stream.isPlaying());}
''')


if __name__=='__main__':
    unittest.main()
