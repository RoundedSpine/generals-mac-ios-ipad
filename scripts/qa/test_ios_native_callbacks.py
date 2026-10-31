#!/usr/bin/env python3
"""Exercise actual native-loop dispatch/lifecycle bodies with minimal engine/SDL stand-ins."""
# GeneralsX @test Codex 25/10/2026 Validate callback ownership, pacing and lifecycle before device comparison.
from pathlib import Path
import unittest
from compiled_harness import run_cpp, ROOT

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
#include <cassert>
#include <cstdio>
#include <stdexcept>
#include <vector>
#define SDLCALL
using Real=float;
enum SDL_AppResult { SDL_APP_CONTINUE,SDL_APP_SUCCESS,SDL_APP_FAILURE };
enum { SDL_EVENT_TERMINATING=1,SDL_EVENT_LOW_MEMORY=2 };
struct SDL_Event { unsigned type; };
bool onMain=true;uint64_t ticks=1000000000;int initResult=0,shuts=0,launcherExit=-1;
bool SDL_IsMainThread() { return onMain; }
uint64_t SDL_GetTicksNS() { return ticks; }
namespace gxiosmemory {
 int warnings=0,polls=0;
 void noteLowMemoryWarning(){++warnings;}
 void logRuntimeIfDue(FILE*,uint64_t){assert(onMain);++polls;}
}
struct Pacer { int fps=60;float delta=0;int getActualFramesPerSecondLimit() { return fps; } void updateExternal(float value) { delta=value; } } pacer;
Pacer* TheFramePacer=&pacer;
struct SDL3GameEngine {
 bool quitting=false,ready=true,throwFrame=false,throwEvent=false;int events=0,frames=0;std::vector<SDL_Event> pending;
 bool getQuitting() { return quitting; }
 bool nativeFrameReady() { return ready; }
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
 const int beforePolls=gxiosmemory::polls;
 event.type=SDL_EVENT_LOW_MEMORY;onMain=false;
 assert(SDL_AppEvent(state,&event)==SDL_APP_CONTINUE&&gxiosmemory::warnings==1&&gxiosmemory::polls==beforePolls);
 onMain=true;assert(SDL_AppIterate(state)==SDL_APP_CONTINUE&&gxiosmemory::polls==beforePolls+1&&gxiosmemory::warnings==1);
 assert(SDL_AppEvent(state,&event)==SDL_APP_CONTINUE&&gxiosmemory::warnings==2&&gxiosmemory::polls==beforePolls+2);
 event.type=99;
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
#include <cassert>
#define TARGET_OS_IPHONE 1
struct SDL_Event {};
int polls=0,longPress=0;bool haveEvent=true;
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
 // Focus/background cancellation never turns a pending touch into a click on resume.
 mouse.events.clear();finger.type=SDL_EVENT_FINGER_DOWN;handleTouchEvent(&mouse,&window,finger);
 cancelTouchGesture(&mouse,&window);ticks+=10000;updateTouchLongPress(&mouse,&window);
 finger.type=SDL_EVENT_FINGER_UP;handleTouchEvent(&mouse,&window,finger);
 assert(mouse.events.size()==1 && s_touch.phase==TouchState::IDLE);
 // An interrupted drag and camera pan release only their held button, once.
 for(auto phase:{TouchState::DRAGGING,TouchState::PAN}){
  mouse.events.clear();s_touch.phase=phase;cancelTouchGesture(&mouse,&window);
  assert(mouse.events.size()==1 && mouse.events[0].type==SDL_EVENT_MOUSE_BUTTON_UP);
  assert(mouse.events[0].button.button==(phase==TouchState::PAN?SDL_BUTTON_RIGHT:SDL_BUTTON_LEFT));
  cancelTouchGesture(&mouse,&window);assert(mouse.events.size()==1 && s_touch.phase==TouchState::IDLE);
 }

}
'''.replace('BODY', body))
        self.assertEqual(result.returncode, 0)


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
