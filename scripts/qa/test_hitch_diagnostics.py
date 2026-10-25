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
