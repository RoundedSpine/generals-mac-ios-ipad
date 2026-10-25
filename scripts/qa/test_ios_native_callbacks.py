#!/usr/bin/env python3
"""Exercise actual native-loop dispatch/lifecycle bodies with minimal engine/SDL stand-ins."""
# GeneralsX @test Codex 25/10/2026 Validate callback ownership, pacing and lifecycle before device comparison.
from pathlib import Path
import unittest
from test_hitch_diagnostics import run_cpp, ROOT

MAIN = ROOT / 'GeneralsMD/Code/Main/SDL3Main.cpp'
ENGINE = ROOT / 'GeneralsMD/Code/GameEngineDevice/Source/SDL3GameEngine.cpp'
HEADER = ROOT / 'GeneralsMD/Code/GameEngineDevice/Include/SDL3GameEngine.h'


def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2]


class NativeCallbacksTest(unittest.TestCase):
    def test_cadence_caps_display_callbacks_without_catchup_or_pause_delta(self):
        run_cpp(r'''
#include "nativeframecadence.h"
#include <cassert>
#include <cmath>
int main() {
 NativeFrameCadence cadence; double delta=0;int frames=0;
 for(unsigned i=0;i<240;++i) {
   uint64_t now=1000000000ull+i*1000000000ull/120;
   if(i%3==1) now+=300000; // realistic callback jitter must not halve the requested rate.
   if(cadence.Advance(now,60,delta)) { ++frames;assert(delta>0 && delta<.04); }
 }
 assert(frames==120);
 assert(cadence.Advance(10000000000ull,60,delta) && delta>1.0);
 assert(!cadence.Advance(10000000001ull,60,delta));
 cadence.Reset();assert(cadence.Advance(20000000000ull,30,delta));
 assert(std::fabs(delta-1.0/30)<.00001);
 assert(!cadence.Advance(20001000000ull,30,delta));
 assert(cadence.Advance(20002000000ull,120,delta)); // FPS changes take effect without waiting on stale deadlines.
 assert(cadence.Advance(20003000000ull,0,delta)); // uncapped still means one update per callback.
 assert(cadence.Advance(20003000001ull,0,delta));
 cadence.Reset();assert(cadence.Advance(10,60,delta));
 assert(cadence.Advance(5,60,delta) && delta>0); // clock rewind resets phase safely.
}
''')

    def test_actual_app_callbacks_route_once_gate_frames_and_clean_up(self):
        source = MAIN.read_text()
        funcs = '\n'.join(function(source, signature) for signature in [
            'SDL_AppResult SDLCALL SDL_AppInit(', 'SDL_AppResult SDLCALL SDL_AppEvent(',
            'SDL_AppResult SDLCALL SDL_AppIterate(', 'void SDLCALL SDL_AppQuit('])
        run_cpp(r'''
#include "nativeframecadence.h"
#include "nativeframetrace.h"
#include "slowoperation.h"
#include <cassert>
#include <cstdio>
#include <stdexcept>
#include <vector>
#define SDLCALL
using Real=float;
enum SDL_AppResult { SDL_APP_CONTINUE,SDL_APP_SUCCESS,SDL_APP_FAILURE };
enum { SDL_EVENT_TERMINATING=1 };
struct SDL_Event { unsigned type; };
bool onMain=true;uint64_t ticks=1000000000;int initResult=0,shuts=0,launcherExit=-1;
bool SDL_IsMainThread() { return onMain; }
uint64_t SDL_GetTicksNS() { return ticks; }
struct Pacer { int fps=60;float delta=0;int getActualFramesPerSecondLimit() { return fps; } void updateExternal(float value) { delta=value; } } pacer;
Pacer* TheFramePacer=&pacer;
struct SDL3GameEngine {
 bool quitting=false,ready=true,throwFrame=false,throwEvent=false;int events=0,frames=0;std::vector<SDL_Event> pending;
 bool getQuitting() { return quitting; }
 bool nativeFrameReady() { return ready; }
 unsigned nativePauseReasons() const { return ready ? 0u : 2u; }
 bool deferNativeEvent(const SDL_Event& e) { pending.push_back(e);return true; }
 void processSDL3Event(SDL_Event) { if(throwEvent)throw std::runtime_error("event");++events; }
 void drainNativeEvents() { assert(onMain);for(auto e:pending)processSDL3Event(e);pending.clear(); }
 void update() { if(throwFrame)throw std::runtime_error("frame");assert(pacer.delta>0);++frames; }
} engine;
SDL3GameEngine* TheGameEngine=&engine;
int InitializeNativeGameLaunch(int,char**) { if(initResult<0)throw std::runtime_error("init");return initResult; }
bool s_nativeEngineReady=true;
void ShutdownGameEngine() { ++shuts; }
void ShutdownSDL3Launcher(int code) { launcherExit=code; }
void test_exit(int) { throw std::runtime_error("exit"); }
#define _exit test_exit
NativeFrameCadence s_nativeCadence;
NativeFrameTrace s_nativeFrameTrace;
BODY
int main() {
 void* state=&engine;initResult=1;
 assert(SDL_AppInit(&state,0,nullptr)==SDL_APP_FAILURE && !state);
 initResult=-1;assert(SDL_AppInit(&state,0,nullptr)==SDL_APP_FAILURE && !state);
 initResult=0;assert(SDL_AppInit(&state,0,nullptr)==SDL_APP_CONTINUE && state==&engine);
 SDL_Event event{99};assert(SDL_AppEvent(state,&event)==SDL_APP_CONTINUE && engine.events==1);
 onMain=false;assert(SDL_AppEvent(state,&event)==SDL_APP_CONTINUE && engine.events==1);
 onMain=true;assert(SDL_AppIterate(state)==SDL_APP_CONTINUE && engine.frames==1 && engine.events==2);
 ticks+=1000000;assert(SDL_AppIterate(state)==SDL_APP_CONTINUE && engine.frames==1);
 engine.ready=false;ticks+=10000000000ull;assert(SDL_AppIterate(state)==SDL_APP_CONTINUE && engine.frames==1);
 engine.ready=true;assert(SDL_AppIterate(state)==SDL_APP_CONTINUE && engine.frames==2 && pacer.delta<.02f);
 engine.throwFrame=true;ticks+=20000000;assert(SDL_AppIterate(state)==SDL_APP_FAILURE);engine.throwFrame=false;
 engine.throwEvent=true;assert(SDL_AppEvent(state,&event)==SDL_APP_FAILURE);engine.throwEvent=false;
 engine.quitting=true;assert(SDL_AppIterate(state)==SDL_APP_SUCCESS);
 event.type=SDL_EVENT_TERMINATING;assert(SDL_AppEvent(state,&event)==SDL_APP_SUCCESS);
 s_nativeEngineReady=false;bool refused=false;
 try { SDL_AppQuit(state,SDL_APP_FAILURE); } catch(const std::runtime_error&) { refused=true; }
 assert(refused && shuts==0);s_nativeEngineReady=true;
 SDL_AppQuit(state,SDL_APP_SUCCESS);assert(shuts==1 && launcherExit==0);
}
'''.replace('BODY', funcs))

    def test_actual_deferred_events_own_text_and_drain_outside_lock(self):
        header = HEADER.read_text()
        start = header.index('\tstruct DeferredNativeEvent {')
        fields = header[start:header.index('\n\tSDL_Window*', start)]
        source = ENGINE.read_text()
        funcs = function(source, 'bool SDL3GameEngine::deferNativeEvent(') + '\n' + function(source, 'void SDL3GameEngine::drainNativeEvents()')
        run_cpp(r'''
#include <cassert>
#include <mutex>
#include <string>
#include <vector>
#include <thread>
enum { SDL_EVENT_TEXT_INPUT=1 };
struct SDL_Event { unsigned type;struct { const char* text; } text; };
struct SDL3GameEngine {
FIELDS
 int seen=0;std::string result;
 bool deferNativeEvent(const SDL_Event&);
 void drainNativeEvents();
 void processSDL3Event(SDL_Event e) {
  assert(m_nativeEventMutex.try_lock());m_nativeEventMutex.unlock();
  ++seen;if(e.type==SDL_EVENT_TEXT_INPUT) result=e.text.text;
 }
};
BODY
int main() {
 SDL3GameEngine engine;char input[]="original";SDL_Event event{SDL_EVENT_TEXT_INPUT,{input}};
 std::thread producer([&] { assert(engine.deferNativeEvent(event)); });producer.join();
 input[0]='X';engine.drainNativeEvents();assert(engine.seen==1 && engine.result=="original");
 for(int i=0;i<256;++i) assert(engine.deferNativeEvent(event));
 assert(!engine.deferNativeEvent(event));engine.drainNativeEvents();assert(engine.seen==257);
 engine.drainNativeEvents();assert(engine.seen==257);
}
'''.replace('FIELDS', fields).replace('BODY', funcs))

    def test_actual_frame_input_service_skips_manual_polling_in_native_mode(self):
        body = function(ENGINE.read_text(), 'void SDL3GameEngine::pollSDL3Events(')
        run_cpp(r'''
#include "slowoperation.h"
#include <cassert>
#define TARGET_OS_IPHONE 1
using Uint64=uint64_t;
struct SDL_Event {};
int polls=0,longPress=0;bool haveEvent=true;
uint64_t SDL_GetTicksNS() { return 1000000000; }
void TraceInputTiming(const char*,unsigned,uint64_t,uint64_t,unsigned,bool) {}
bool SDL_PollEvent(SDL_Event*) { ++polls;if(haveEvent){haveEvent=false;return true;}return false; }
struct Mouse { virtual ~Mouse(){} };struct SDL3Mouse:Mouse {} mouse;Mouse* TheMouse=&mouse;
void updateTouchLongPress(SDL3Mouse*,void*) { ++longPress; }
struct SDL3GameEngine {
 bool m_UsesNativeCallbacks=true;void* m_SDLWindow=this;int events=0,text=0;
 void updateTextInputState() { ++text; }
 void processSDL3Event(SDL_Event) { ++events; }
 void pollSDL3Events();
};
BODY
int main() {
 SDL3GameEngine engine;engine.pollSDL3Events();assert(!polls && !engine.events && longPress==1);
 engine.m_UsesNativeCallbacks=false;engine.pollSDL3Events();assert(polls==2 && engine.events==1 && longPress==2);
}
'''.replace('BODY', body))

    def test_frame_trace_distinguishes_outside_gap_pause_and_long_callback(self):
        result = run_cpp(r'''#include "nativeframetrace.h"
uint64_t now=1000000000;
uint64_t clockNow() { return now; }
int main() {
 NativeFrameTrace trace;
 { NativeFrameTrace::Scope scope(trace,clockNow);trace.Update(now,0,60,now+16666666);now+=1000000; }
 now+=2000000000;
 { NativeFrameTrace::Scope scope(trace,clockNow);trace.Gate(now,true,2,0,0);now+=1000000; }
 now+=16000000;
 { NativeFrameTrace::Scope scope(trace,clockNow);trace.Gate(now,true,2,0,0);now+=1000000; }
 now+=16000000;
 { NativeFrameTrace::Scope scope(trace,clockNow);trace.Update(now,0,60,now+16666666);now+=200000000; }
}
''')
        self.assertIn('phase=callback-gap', result.stderr)
        self.assertIn('outside_ms=2000.00', result.stderr)
        self.assertIn('phase=gate-change', result.stderr)
        self.assertIn('reason=lifecycle pause_bits=2', result.stderr)
        self.assertIn('phase=update-resumed', result.stderr)
        self.assertIn('phase=callback-long', result.stderr)

    def test_frame_gate_and_lifecycle_output_have_separate_caps(self):
        result = run_cpp(r'''#include "nativeframetrace.h"
int main() {
 NativeFrameTrace trace;
 trace.Enter(1000000000);trace.Update(1000000000,0,1,2000000000);trace.Exit(1000000000);
 trace.Enter(1200000000);trace.Gate(1200000000,false,0,1,2000000000);trace.Exit(1200000000);
 for(uint64_t i=2;i<400;++i) {
   uint64_t now=1000000000+i*1000000000;
   trace.Enter(now);trace.Gate(now,false,0,1,now+1000000000);trace.Exit(now);
 }
 for(int i=0;i<70;++i) TraceNativeLifecycle(10,2,1000000000+i);
}
''')
        self.assertIn('phase=update-skipped', result.stderr)
        self.assertIn('reason=cadence pause_bits=0 fps=1 deadline_ns=2000000000', result.stderr)
        self.assertEqual(result.stderr.count('[NATIVE_FRAME] t='), 256)
        self.assertEqual(result.stderr.count('further frame messages suppressed'), 1)
        self.assertEqual(result.stderr.count('[NATIVE_LIFECYCLE] t='), 64)
        self.assertEqual(result.stderr.count('further lifecycle messages suppressed'), 1)

    def test_actual_lifecycle_watcher_keeps_atomic_pause_decisions(self):
        body = function(ENGINE.read_text(), 'static bool SDLCALL iosLifecycleWatcher(')
        result = run_cpp(r'''#include "nativeframetrace.h"
#include <cassert>
#define SDLCALL
struct SDL_Event { unsigned type; };
enum { SDL_EVENT_WILL_ENTER_BACKGROUND=1,SDL_EVENT_DID_ENTER_BACKGROUND,
 SDL_EVENT_DID_ENTER_FOREGROUND,SDL_EVENT_WINDOW_FOCUS_LOST,SDL_EVENT_WINDOW_FOCUS_GAINED };
std::atomic<bool> s_appBackgrounded{false},s_appInactive{false};
uint64_t SDL_GetTicksNS() { return 1000000000; }
BODY
int main() {
 SDL_Event e{SDL_EVENT_WILL_ENTER_BACKGROUND};assert(iosLifecycleWatcher(nullptr,&e));assert(s_appBackgrounded && !s_appInactive);
 e.type=SDL_EVENT_WINDOW_FOCUS_LOST;iosLifecycleWatcher(nullptr,&e);assert(s_appBackgrounded && s_appInactive);
 e.type=SDL_EVENT_DID_ENTER_FOREGROUND;iosLifecycleWatcher(nullptr,&e);assert(!s_appBackgrounded && s_appInactive);
 e.type=SDL_EVENT_WINDOW_FOCUS_GAINED;iosLifecycleWatcher(nullptr,&e);assert(!s_appBackgrounded && !s_appInactive);
 e.type=99;assert(iosLifecycleWatcher(nullptr,&e));
}
'''.replace('BODY', body))
        self.assertEqual(result.stderr.count('[NATIVE_LIFECYCLE]'), 4)
        for flags in range(4):
            self.assertIn('pause_bits=' + str(flags), result.stderr)

    def test_shared_engine_lifecycle_retains_desktop_and_replay_paths(self):
        source = (ROOT / 'GeneralsMD/Code/GameEngine/Source/Common/GameMain.cpp').read_text()
        funcs = '\n'.join(function(source, name) for name in ['void InitializeGameEngine()', 'void ShutdownGameEngine()', 'Int GameMain()'])
        run_cpp(r'''
#include <cassert>
#include <vector>
using Int=int;
#define TRUE true
int initialized=0,executed=0,enginesDestroyed=0,pacersDestroyed=0,simulated=0;
struct FramePacer { void enableFramesPerSecondLimit(bool){} ~FramePacer(){++pacersDestroyed;} };
FramePacer* TheFramePacer=nullptr;
struct Engine {void init(){++initialized;}void execute(){++executed;}~Engine(){++enginesDestroyed;}};
Engine* TheGameEngine=nullptr;Engine* CreateGameEngine(){return new Engine;}
struct Globals {std::vector<int> m_simulateReplays;int m_simulateReplayJobs=2;} globals;Globals* TheGlobalData=&globals;
struct ReplaySimulation {static int simulateReplays(const std::vector<int>&,int jobs){assert(jobs==2);++simulated;return 7;}};
BODY
int main() {
 assert(GameMain()==0 && initialized==1 && executed==1 && enginesDestroyed==1 && pacersDestroyed==1);
 assert(!TheGameEngine && !TheFramePacer);
 globals.m_simulateReplays.push_back(1);assert(GameMain()==7 && executed==1 && simulated==1);
 InitializeGameEngine();assert(initialized==3 && executed==1 && TheGameEngine);
 ShutdownGameEngine();assert(enginesDestroyed==3 && pacersDestroyed==3);
 ShutdownGameEngine();assert(enginesDestroyed==3 && pacersDestroyed==3);
}
'''.replace('BODY', funcs))


if __name__ == '__main__':
    unittest.main()
