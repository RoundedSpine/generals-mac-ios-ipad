#!/usr/bin/env python3
"""Check bounded timing output and reproduce render-thread lock contention with production dispatch code."""
# GeneralsX @test Codex 25/10/2026 Separate a reproducible stall mechanism from unmeasured device behavior.
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / 'Core/Libraries/Source/WWVegas/WWLib'


def run_cpp(source):
    with tempfile.TemporaryDirectory() as temporary:
        code = Path(temporary) / 'test.cpp'
        binary = Path(temporary) / 'test'
        code.write_text(source)
        result = subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-pthread',
                                 '-D_UNIX', '-I', str(LIB), str(code), '-o', str(binary)], text=True, capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        return subprocess.run([str(binary)], text=True, capture_output=True, check=True, timeout=10)


class HitchDiagnosticsTest(unittest.TestCase):
    def test_timing_scope_copies_name_and_finishes_once(self):
        result = run_cpp(r'''
#include "slowoperation.h"
int main() {
  char name[]="original.dds";
  SlowOperationTrace trace("test-phase", name, 0.0);
  name[0]='X'; trace.Finish(); trace.Finish();
  SlowOperationTrace quiet("must-not-appear", nullptr, 1000000.0);
}
''')
        self.assertEqual(result.stderr.count('[HITCH]'), 1)
        self.assertIn("detail='original.dds'", result.stderr)
        self.assertNotIn('must-not-appear', result.stderr)

    def test_timing_output_is_bounded(self):
        result = run_cpp(r'''
#include "slowoperation.h"
int main() { for(int i=0;i<1100;++i) { SlowOperationTrace trace("cap", nullptr, 0.0); } }
''')
        self.assertEqual(result.stderr.count('phase=cap'), 1024)
        self.assertEqual(result.stderr.count('further timing messages suppressed'), 1)

    def test_input_age_handles_unknown_future_and_bounded_output(self):
        result = run_cpp(r'''#include "inputtiming.h"
int main() {
  TraceInputTiming("unknown", 1, 0, 100000000, 0);
  TraceInputTiming("future", 1, 200000000, 100000000, 0);
  TraceInputTiming("fast", 1, 100000000, 101000000, 0);
  TraceInputTiming("delayed", 2, 100000000, 175000000, 7);
  TraceInputTiming("button", 3, 0, 100000000, 4, true);
  for(int i=0;i<2100;++i) TraceInputTiming("burst", 4, 1, 2, 255, true);
}
''')
        self.assertNotIn('phase=unknown', result.stderr)
        self.assertNotIn('phase=future', result.stderr)
        self.assertNotIn('phase=fast', result.stderr)
        self.assertIn('source_ns=100000000 age_ms=75.00 depth=7', result.stderr)
        self.assertIn('age_ms=-1.00 depth=4', result.stderr)
        self.assertEqual(result.stderr.count('phase='), 2048)
        self.assertEqual(result.stderr.count('further input messages suppressed'), 1)

    def test_actual_touch_translator_defers_taps_and_distinguishes_long_press(self):
        source = (ROOT / 'GeneralsMD/Code/GameEngineDevice/Source/SDL3GameEngine.cpp').read_text()
        start = source.index('struct TouchState {')
        body = source[start:source.index('} // anonymous namespace', start)]
        result = run_cpp(r'''#include <cassert>
#include <cmath>
#include <cstring>
#include <vector>
using Uint64=unsigned long long; using Uint32=unsigned; using Uint8=unsigned char;
using SDL_FingerID=long long; using SDL_WindowID=unsigned;
enum { SDL_EVENT_FINGER_DOWN=1, SDL_EVENT_FINGER_UP, SDL_EVENT_FINGER_MOTION,
       SDL_EVENT_FINGER_CANCELED, SDL_EVENT_MOUSE_MOTION, SDL_EVENT_MOUSE_BUTTON_DOWN,
       SDL_EVENT_MOUSE_BUTTON_UP, SDL_EVENT_MOUSE_WHEEL, SDL_BUTTON_LEFT=10, SDL_BUTTON_RIGHT=11 };
struct SDL_Window {};
struct SDL_Event {
  unsigned type=0;
  struct { long long fingerID=0; float x=0,y=0; } tfinger;
  struct { unsigned windowID=0; float x=0,y=0; } motion;
  struct { unsigned windowID=0; unsigned char button=0; bool down=false; int clicks=0; float x=0,y=0; } button;
  struct { unsigned windowID=0; float x=0,y=0,mouse_x=0,mouse_y=0; } wheel;
};
#define SDL_zero(x) x = SDL_Event{}
Uint64 ticks=100;
Uint64 SDL_GetTicks() { return ticks; }
void SDL_GetWindowSize(SDL_Window*, int* w,int* h) { *w=1000;*h=500; }
unsigned SDL_GetWindowID(SDL_Window*) { return 1; }
float SDL_sqrtf(float x) { return std::sqrt(x); }
float SDL_fabsf(float x) { return std::fabs(x); }
struct SDL3Mouse { std::vector<SDL_Event> events; void addSDLEvent(SDL_Event* e) { events.push_back(*e); } };
BODY
int main() {
 SDL3Mouse mouse; SDL_Window window; SDL_Event finger;
 finger.type=SDL_EVENT_FINGER_DOWN; finger.tfinger.fingerID=1; finger.tfinger.x=.5f;finger.tfinger.y=.5f;
 handleTouchEvent(&mouse,&window,finger);
 assert(mouse.events.size()==1 && mouse.events[0].type==SDL_EVENT_MOUSE_MOTION);
 ticks+=100; updateTouchLongPress(&mouse,&window); assert(mouse.events.size()==1);
 finger.type=SDL_EVENT_FINGER_UP;handleTouchEvent(&mouse,&window,finger);
 assert(mouse.events.size()==4 && mouse.events[2].button.button==SDL_BUTTON_LEFT && !mouse.events[3].button.down);
 mouse.events.clear();finger.type=SDL_EVENT_FINGER_DOWN;handleTouchEvent(&mouse,&window,finger);
 ticks+=599; updateTouchLongPress(&mouse,&window); assert(mouse.events.size()==1);
 ticks+=1;updateTouchLongPress(&mouse,&window);
 assert(mouse.events.size()==4 && mouse.events[2].button.button==SDL_BUTTON_RIGHT);
 finger.type=SDL_EVENT_FINGER_UP;handleTouchEvent(&mouse,&window,finger);assert(mouse.events.size()==4);
 mouse.events.clear();finger.type=SDL_EVENT_FINGER_DOWN;handleTouchEvent(&mouse,&window,finger);
 finger.type=SDL_EVENT_FINGER_CANCELED;handleTouchEvent(&mouse,&window,finger);
 assert(mouse.events.size()==1 && s_touch.phase==TouchState::IDLE);
}
'''.replace('BODY', body))
        self.assertEqual(result.returncode, 0)

    def test_source_cleanup_preserves_order_and_reports_delete_wait(self):
        source = (ROOT / 'Core/GameEngineDevice/Source/OpenALAudioDevice/OpenALAudioManager.cpp').read_text()
        start = source.index('void OpenALAudioManager::releaseOpenALHandles(')
        function = source[start:source.index('\n}', start) + 2]
        result = run_cpp(r'''#include "slowoperation.h"
#include <cassert>
using ALuint=unsigned;
int step=0;
struct Stream { ~Stream() { assert(step++==1); } };
struct Decoder { ~Decoder() { assert(step++==2); } };
enum { PAT_INVALID=-1 };
struct PlayingAudio { ALuint m_source=42; Stream* m_stream=new Stream; Decoder* m_ffmpegFile=new Decoder; int m_type=0; };
void alDeleteSources(int n, ALuint* source) {
  assert(n==1 && *source==42 && step++==0);
  std::this_thread::sleep_for(std::chrono::milliseconds(25));
}
struct OpenALAudioManager { void releaseOpenALHandles(PlayingAudio*); };
BODY
int main() {
  OpenALAudioManager manager; PlayingAudio playing;
  manager.releaseOpenALHandles(&playing);
  assert(step==3 && playing.m_source==0 && !playing.m_stream && !playing.m_ffmpegFile && playing.m_type==PAT_INVALID);
  manager.releaseOpenALHandles(&playing); assert(step==3);
}
'''.replace('BODY', function))
        self.assertEqual(result.stderr.count('phase=audio-source-delete'), 1)
        self.assertIn('phase=audio-release-handles', result.stderr)

    def test_audio_update_preserves_order_and_attributes_slow_requests(self):
        source = (ROOT / 'Core/GameEngineDevice/Source/OpenALAudioDevice/OpenALAudioManager.cpp').read_text()
        start = source.index('void OpenALAudioManager::update()')
        function = source[start:source.index('\n}', start) + 2]
        result = run_cpp(r'''#include "slowoperation.h"
#include <cassert>
int sequence=0;
struct AudioManager { void update() { assert(sequence++==0); } };
struct OpenALAudioManager : AudioManager {
  void update();
  void setDeviceListenerPosition() { assert(sequence++==1); }
  void processRequestList() {
    assert(sequence++==2);
    std::this_thread::sleep_for(std::chrono::milliseconds(30));
  }
  void processPlayingList() { assert(sequence++==3); }
  void processFadingList() { assert(sequence++==4); }
  void processStoppedList() { assert(sequence++==5); }
};
BODY
int main() { OpenALAudioManager audio; audio.update(); assert(sequence==6); }
'''.replace('BODY', function))
        self.assertIn('phase=audio-requests', result.stderr)

    def test_foreground_request_can_block_on_background_decode_lock(self):
        source = (ROOT / 'Core/Libraries/Source/WWVegas/WW3D2/textureloader.cpp').read_text()
        start = source.index('void TextureLoader::Request_Foreground_Loading(')
        function = source[start:source.index('\n}', start) + 2]
        harness = r'''
#include "slowoperation.h"
#include <atomic>
#include <cassert>
#include <mutex>
#define WWPROFILE(...) ((void)0)
struct FastCriticalSectionClass {
  std::mutex mutex;
  struct LockClass { std::unique_lock<std::mutex> lock; LockClass(FastCriticalSectionClass& cs):lock(cs.mutex){} };
};
FastCriticalSectionClass _ForegroundCriticalSection, _BackgroundCriticalSection;
struct TextureLoadTaskClass;
struct Queue { void Remove(TextureLoadTaskClass*) {} void Push_Back(TextureLoadTaskClass*) {} } _ForegroundQueue, _BackgroundQueue;
struct Name { const char* str() const { return "foreground.dds"; } };
struct TextureBaseClass {
  TextureLoadTaskClass* TextureLoadTask=nullptr;
  TextureLoadTaskClass* ThumbnailLoadTask=nullptr;
  Name name;
  bool Is_Initialized() const { return false; }
  const Name& Get_Full_Path() const { return name; }
};
struct TextureLoadTaskClass {
  enum { TASK_LOAD, PRIORITY_HIGH, STATE_COMPLETE };
  int finished=0,destroyed=0;
  void Finish_Load() { ++finished; }
  void Destroy() { ++destroyed; }
  void Set_State(int) {}
  void Set_Priority(int) {}
  void* Get_List() { return nullptr; }
  static TextureLoadTaskClass* Create(TextureBaseClass*,int,int) { static TextureLoadTaskClass task; return &task; }
};
struct TextureLoader {
  static bool Is_DX8_Thread() { return true; }
  static void Request_Foreground_Loading(TextureBaseClass*);
};
BODY
int main() {
  TextureBaseClass texture; TextureLoadTaskClass task; texture.TextureLoadTask=&task;
  std::atomic<bool> holding{false};
  std::thread worker([&] {
    std::lock_guard<std::mutex> lock(_BackgroundCriticalSection.mutex);
    holding=true;
    // Controlled 80 ms decode while holding the same lock as the real worker.
    std::this_thread::sleep_for(std::chrono::milliseconds(80));
  });
  while(!holding) std::this_thread::yield();
  auto start=std::chrono::steady_clock::now();
  TextureLoader::Request_Foreground_Loading(&texture);
  const auto elapsed=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
  worker.join();
  assert(elapsed>=60.0 && task.finished==1 && task.destroyed==1);
}
'''.replace('BODY', function)
        result = run_cpp(harness)
        self.assertIn('phase=texture-background-lock', result.stderr)
        self.assertIn('phase=texture-foreground-request', result.stderr)


if __name__ == '__main__':
    unittest.main()
