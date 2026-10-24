#!/usr/bin/env python3
"""Build the real Unix ThreadClass and texture queues against minimal legacy-header stand-ins."""
# GeneralsX @test Codex 25/10/2026 Exercise worker lifecycle and concurrent queue ownership.
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / 'Core/Libraries/Source/WWVegas/WWLib'


def body(source, marker):
    start = source.index(marker)
    return source[start:source.index('\n}', start) + 2]


class UnixWorkerTest(unittest.TestCase):
    def test_worker_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in ('thread.h', 'thread.cpp'):
                (directory / name).write_text((LIB / name).read_text())
            (directory / 'always.h').write_text(r'''
#pragma once
#include <cassert>
#include <cstring>
#include <cstddef>
#define __cdecl
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
inline size_t fixture_strlcpy(char* out, const char* in, size_t n) {
  const size_t length=std::strlen(in);
  if (n) { const size_t copied=length<n-1 ? length : n-1; std::memcpy(out,in,copied); out[copied]=0; }
  return length;
}
#define strlcpy fixture_strlcpy
''')
            for name in ('Vector.h', 'Except.h', 'systimer.h'):
                (directory / name).write_text('#pragma once\n')
            (directory / 'wwdebug.h').write_text('#define WWASSERT(x) assert(x)\n#define WWDEBUG_SAY(x) ((void)0)\n')
            (directory / 'thread_compat.h').write_text('int GetCurrentThreadIdAsInt();\n')
            (directory / 'test.cpp').write_text(r'''
#include "thread.h"
#include <chrono>
#include <stdexcept>
#include <vector>
std::atomic<int> nextID{1};
int GetCurrentThreadIdAsInt() { thread_local int id=nextID.fetch_add(1); return id; }
struct Worker : ThreadClass {
  std::atomic<unsigned> seenID{0};
  std::atomic<int> entries{0};
  ~Worker() override { Stop(); }
  void Thread_Function() override {
    seenID=_Get_Current_Thread_ID(); ++entries;
    while (running) Switch_Thread();
  }
};
struct Finite : ThreadClass {
  std::atomic<bool> done{false};
  ~Finite() override { Stop(); }
  void Thread_Function() override { done=true; }
};
struct SelfStopping : ThreadClass {
  std::atomic<bool> entered{false}, release{false}, stopped{false};
  ~SelfStopping() override { Stop(); }
  void Thread_Function() override {
    entered=true;
    while (!release) Switch_Thread();
    Stop(); stopped=true;
  }
};
struct Slow : ThreadClass {
  std::atomic<bool> entered{false}, finished{false};
  ~Slow() override { Stop(); }
  void Thread_Function() override { entered=true; Sleep_Ms(30); finished=true; }
};
struct Throwing : ThreadClass {
  ~Throwing() override { Stop(); }
  void Thread_Function() override { throw std::runtime_error("expected worker test exception"); }
};
template<class Condition> void waitUntil(Condition condition) {
  auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
  while (!condition()) { assert(std::chrono::steady_clock::now()<deadline); ThreadClass::Switch_Thread(); }
}
int main() {
  const auto mainID=ThreadClass::_Get_Current_Thread_ID(); assert(mainID!=0);
  assert(mainID==ThreadClass::_Get_Current_Thread_ID());
  Worker worker; worker.Set_Priority(-4); worker.Execute();
  waitUntil([&] { return worker.entries.load()==1; });
  assert(worker.Is_Running() && worker.seenID!=mainID);
  worker.Execute(); assert(worker.entries==1);
  worker.Stop(); assert(!worker.Is_Running()); worker.Stop();
  for (int i=0;i<100;++i) { worker.Execute(); worker.Stop(); assert(!worker.Is_Running()); }
  Finite finite;
  for (int i=0;i<10;++i) {
    finite.done=false; finite.Execute();
    waitUntil([&] { return finite.done.load() && !finite.Is_Running(); });
  }
  finite.Stop();
  SelfStopping self; self.Execute(); waitUntil([&] { return self.entered.load(); });
  std::thread owner([&] { self.Stop(); });
  self.release=true; owner.join(); assert(self.stopped && !self.Is_Running());
  Slow slow; slow.Execute(); waitUntil([&] { return slow.entered.load(); });
  slow.Stop(1); assert(slow.finished && !slow.Is_Running());
  Throwing throwing; throwing.Execute(); waitUntil([&] { return !throwing.Is_Running(); }); throwing.Stop();
}
''')
            binary = directory / 'test'
            result = subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-pthread',
                                     '-D_UNIX', '-Wall', '-Wextra', '-Wno-unknown-pragmas',
                                     str(directory / 'thread.cpp'), str(directory / 'test.cpp'),
                                     '-o', str(binary)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(binary)], timeout=15, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('shutdown exceeded', result.stderr)
            self.assertIn('expected worker test exception', result.stderr)

    def test_real_texture_queue_concurrent_producer_and_consumer(self):
        source = (ROOT / 'Core/Libraries/Source/WWVegas/WW3D2/textureloader.cpp').read_text()
        header = (ROOT / 'Core/Libraries/Source/WWVegas/WW3D2/textureloader.h').read_text()
        start = header.index('class TextureLoadTaskListClass\n{')
        end = header.index('\n/*', start)
        declarations = header[start:end]
        functions = '\n'.join(body(source, marker) for marker in (
            'TextureLoadTaskListClass::TextureLoadTaskListClass()',
            'void TextureLoadTaskListClass::Push_Front',
            'void TextureLoadTaskListClass::Push_Back',
            'TextureLoadTaskClass *TextureLoadTaskListClass::Pop_Front()',
            'TextureLoadTaskClass *TextureLoadTaskListClass::Pop_Back()',
            'void TextureLoadTaskListClass::Remove',
            'SynchronizedTextureLoadTaskListClass::SynchronizedTextureLoadTaskListClass()',
            'bool SynchronizedTextureLoadTaskListClass::Is_Empty() const',
            'void SynchronizedTextureLoadTaskListClass::Push_Front',
            'void SynchronizedTextureLoadTaskListClass::Push_Back',
            'TextureLoadTaskClass *SynchronizedTextureLoadTaskListClass::Pop_Front()',
            'TextureLoadTaskClass *SynchronizedTextureLoadTaskListClass::Pop_Back()',
            'void SynchronizedTextureLoadTaskListClass::Remove'))
        harness = r'''
#include <atomic>
#include <cassert>
#include <mutex>
#include <thread>
#include <vector>
#define WWASSERT(x) assert(x)
struct FastCriticalSectionClass {
  std::mutex mutex;
  struct LockClass { std::unique_lock<std::mutex> lock; LockClass(FastCriticalSectionClass& cs):lock(cs.mutex){} };
};
class TextureLoadTaskListClass;
struct TextureLoadTaskListNodeClass { TextureLoadTaskListNodeClass* Next=nullptr; TextureLoadTaskListNodeClass* Prev=nullptr; TextureLoadTaskListClass* List=nullptr; };
struct TextureLoadTaskClass : TextureLoadTaskListNodeClass { int id=0; };
DECLARATIONS
FUNCTIONS
int main() {
  SynchronizedTextureLoadTaskListClass queue;
  assert(queue.Is_Empty() && queue.Pop_Front()==nullptr && queue.Pop_Back()==nullptr);
  std::vector<TextureLoadTaskClass> tasks(10000);
  std::atomic<bool> produced{false};
  std::thread producer([&] {
    for (int i=0;i<10000;++i) { tasks[i].id=i; queue.Push_Back(&tasks[i]); }
    produced=true;
  });
  int expected=0;
  while (expected<10000) {
    if (auto* task=queue.Pop_Front()) { assert(task->id==expected); ++expected; }
    else std::this_thread::yield();
  }
  producer.join(); assert(produced && queue.Is_Empty());
  queue.Push_Front(&tasks[0]); queue.Push_Front(&tasks[1]);
  queue.Remove(&tasks[0]); assert(queue.Pop_Back()==&tasks[1]); assert(queue.Is_Empty());
}
'''.replace('DECLARATIONS', declarations).replace('FUNCTIONS', functions)
        with tempfile.TemporaryDirectory() as temporary:
            code = Path(temporary) / 'queue.cpp'
            binary = Path(temporary) / 'test'
            code.write_text(harness)
            result = subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-pthread', str(code), '-o', str(binary)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], timeout=15, check=True)



    def test_texture_shutdown_stops_before_taking_worker_lock(self):
        source = (ROOT / 'Core/Libraries/Source/WWVegas/WW3D2/textureloader.cpp').read_text()
        function = body(source, 'void TextureLoader::Deinit()')
        harness = r'''
#include <cassert>
#include <mutex>
struct FastCriticalSectionClass {
  std::mutex mutex;
  struct LockClass { std::unique_lock<std::mutex> lock; LockClass(FastCriticalSectionClass& cs):lock(cs.mutex){} };
} _BackgroundCriticalSection;
struct Worker {
  bool stopped=false;
  void Stop() {
    assert(_BackgroundCriticalSection.mutex.try_lock());
    _BackgroundCriticalSection.mutex.unlock(); stopped=true;
  }
} _TextureLoadThread;
struct ThumbnailManagerClass { static void Deinit() { assert(_TextureLoadThread.stopped); } };
struct TextureLoadTaskClass { static void Delete_Free_Pool() { assert(_TextureLoadThread.stopped); } };
struct TextureLoader { static void Deinit(); };
BODY
int main() { TextureLoader::Deinit(); }
'''.replace('BODY', function)
        with tempfile.TemporaryDirectory() as temporary:
            code = Path(temporary) / 'shutdown.cpp'
            binary = Path(temporary) / 'test'
            code.write_text(harness)
            result = subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-pthread', str(code), '-o', str(binary)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], timeout=5, check=True)


if __name__ == '__main__':
    unittest.main()
