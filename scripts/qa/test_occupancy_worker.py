#!/usr/bin/env python3
"""Compare real occupancy functions with explicit queries and exercise the bounded shadow worker."""
# GeneralsX @feature Codex 27/10/2026 Validate query semantics separately from any live-world worker search.
import unittest
import sys
from functools import partial
from compiled_harness import ROOT, run_cpp

SOURCE = (ROOT / 'Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp').read_text()


def function(marker):
    a = SOURCE.index(marker)
    return SOURCE[a:SOURCE.index('\n}', a) + 2]


def legacy(marker):
    code = function(marker)
    a = code.index('#ifdef GENERALS_ZH_OCCUPANCY_WORKER')
    b = code.index('#else', a)
    return (code[:a] + code[b + len('#else'):code.rindex('#endif')] + '\n}').replace('Pathfinder::', 'Baseline::')


def fixture(generals=0, infantry=1, shadow=True):
    return ('#define GENERALS_OCCUPANCY_SHADOW_VALIDATION 1\n' if shadow else '') + (f'#define RTS_GENERALS {generals}\n' if generals is not None else '') + '#define RETAIL_COMPATIBLE_PATHFINDING 1\n' + ('#define INFANTRY_MOVES_THROUGH_INFANTRY 1\n' if infantry else '') + r'''
#define GENERALS_ZH_OCCUPANCY_WORKER 1
#include "occupancyvalidationworker.h"
#include <cassert>
#include <random>
#include <string>
#include <system_error>
#include <type_traits>
using Int=int;using Bool=bool;using UnsignedInt=unsigned;using ObjectID=unsigned;using PathfindLayerEnum=int;
const unsigned INVALID_ID=0;
const int ALLIES=1,TEST_CRUSH_OR_SQUISH=3,KINDOF_INFANTRY=7;
struct ICoord2D{int x,y;};
struct AI{unsigned ignored=0;bool aircraft=false,idle=false;
 unsigned getIgnoredObstacleID()const{return ignored;}bool isAircraftThatAdjustsDestination()const{return aircraft;}bool isIdle()const{return idle;}};
struct Object{
 unsigned id=0;AI ai;bool hasAI=false,infantry=false,crush=false;unsigned allyMask=0;
 const AI*getAIUpdateInterface()const{return hasAI?&ai:nullptr;}const AI*getAI()const{return &ai;}
 unsigned getID()const{return id;}bool isKindOf(int)const{return infantry;}
 int getRelationship(const Object*o)const{return (allyMask&(1u<<o->id))?ALLIES:0;}
 bool canCrushOrSquish(const Object*,int)const{return crush;}
};
struct PathfindCell{
 enum CellType{CELL_CLEAR=0,CELL_WATER=1,CELL_CLIFF=2,CELL_RUBBLE=3,CELL_OBSTACLE=4,CELL_BRIDGE_IMPASSABLE=5,CELL_IMPASSABLE=6};
 enum CellFlags{NO_UNITS=0,UNIT_GOAL=1,UNIT_PRESENT_MOVING=2,UNIT_PRESENT_FIXED=3,UNIT_GOAL_OTHER_MOVING=5};
 bool exists=true,aircraft=false;unsigned aircraftID=0,goal=0,pos=0;CellType type=CELL_CLEAR;CellFlags flags=NO_UNITS;
 bool present=false;
 bool isAircraftGoal()const{return aircraft;}unsigned getGoalAircraft()const{return aircraftID;}
 CellType getType()const{return type;}bool isObstaclePresent(unsigned)const{return present;}
 CellFlags getFlags()const{return flags;}unsigned getGoalUnit()const{return goal;}unsigned getPosUnit()const{return pos;}
};
bool IS_IMPASSABLE(PathfindCell::CellType t){return t==PathfindCell::CELL_OBSTACLE||t==PathfindCell::CELL_IMPASSABLE||t==PathfindCell::CELL_BRIDGE_IMPASSABLE;}
struct Logic{Object units[8];bool exists[8]{};
 Object*findObjectByID(unsigned id){return id<8&&exists[id]?&units[id]:nullptr;}}logic;
Logic*TheGameLogic=&logic;
struct TCheckMovementInfo{ICoord2D cell;int layer,radius;bool centerInCell,considerTransient;int acceptableSurfaces;
 int allyFixedCount=0;bool allyMoving=false,allyGoal=false,enemyFixed=false;};
struct PathfindOccupancyValidation{PathOccupancy::ValidationWorker worker;};
struct Pathfinder{
 PathfindCell cells[4][4];
 PathfindOccupancyValidation*m_occupancyValidation=nullptr;bool m_occupancyValidationUnavailable=false;unsigned m_occupancySamplesRemaining=0;
 ~Pathfinder(){delete m_occupancyValidation;}
 PathfindCell*getCell(int,int x,int y){return x>=0&&x<4&&y>=0&&y<4&&cells[y][x].exists?&cells[y][x]:nullptr;}
 PathOccupancy::Result evaluateOccupancyQuery(const Object*,const PathOccupancy::Input&);
 bool checkDestination(const Object*,int,int,int,int,bool);
 bool checkForMovement(const Object*,TCheckMovementInfo&);
};
struct Baseline:Pathfinder{
 bool checkDestination(const Object*,int,int,int,int,bool);
 bool checkForMovement(const Object*,TCheckMovementInfo&);
};
''' + SOURCE[SOURCE.index('struct LiveOccupancyReader {'):SOURCE.index('PathOccupancy::Result Pathfinder::evaluateOccupancyQuery(')] + '\n' + '\n'.join([
        function('PathOccupancy::Result Pathfinder::evaluateOccupancyQuery('),
        function('Bool Pathfinder::checkDestination('), function('Bool Pathfinder::checkForMovement('),
        legacy('Bool Pathfinder::checkDestination('), legacy('Bool Pathfinder::checkForMovement(')])


class OccupancyTests(unittest.TestCase):
    def test_zero_hour_with_undefined_base_game_macro(self):
        run_cpp(fixture(None) + r'''
int main(){Pathfinder p;Baseline baseline;Object mover;mover.id=1;
 TCheckMovementInfo a{{1,1},1,0,true,false,1},b=a;
 assert(p.checkForMovement(&mover,a)==baseline.checkForMovement(&mover,b));
 assert(p.checkDestination(&mover,1,1,1,0,true)==baseline.checkDestination(&mover,1,1,1,0,true));
}
''')

    def test_original_and_explicit_queries_match_random_worlds(self):
        main = r'''
int main(){std::mt19937 random(4481);Pathfinder p;Baseline baseline;
 for(unsigned trial=0;trial<20000;++trial){
  for(unsigned i=0;i<8;++i){auto&o=logic.units[i];o.id=i;o.hasAI=random()%2;o.ai.ignored=random()%8;o.ai.aircraft=random()%2;
   o.ai.idle=random()%2;o.infantry=random()%2;o.crush=random()%2;o.allyMask=random()%256;logic.exists[i]=random()%2;}
  for(int y=0;y<4;++y)for(int x=0;x<4;++x){auto&c=p.cells[y][x];c.exists=random()%8!=0;c.aircraft=random()%2;c.aircraftID=random()%8;
   c.goal=random()%8;c.pos=random()%8;c.type=static_cast<PathfindCell::CellType>(random()%7);
   constexpr int flags[]={0,1,2,3,5};c.flags=static_cast<PathfindCell::CellFlags>(flags[random()%5]);c.present=random()%2;baseline.cells[y][x]=c;}
  const Object*obj=random()%5?&logic.units[random()%8]:nullptr;
  TCheckMovementInfo a{{int(random()%6)-1,int(random()%6)-1},1,int(random()%3),bool(random()%2),bool(random()%2),1},b=a;
  assert(p.checkDestination(obj,a.cell.x,a.cell.y,1,a.radius,a.centerInCell)==baseline.checkDestination(obj,b.cell.x,b.cell.y,1,b.radius,b.centerInCell));
  assert(p.checkForMovement(obj,a)==baseline.checkForMovement(obj,b));
  assert(a.allyFixedCount==b.allyFixedCount&&a.allyMoving==b.allyMoving&&a.allyGoal==b.allyGoal&&a.enemyFixed==b.enemyFixed);
 }
}
'''
        for generals, infantry in ((0, 1), (0, 0), (1, 1), (1, 0)):
            run_cpp(fixture(generals, infantry) + main)

    def test_ally_dedup_saturation_and_destination_special_cases(self):
        run_cpp(fixture() + r'''
int main(){Pathfinder p;Baseline baseline;Object mover;mover.id=7;mover.hasAI=true;mover.allyMask=0xff;
 for(unsigned i=1;i<=6;++i){logic.units[i].id=i;logic.units[i].hasAI=true;logic.exists[i]=true;}
 for(int x=0;x<4;++x)for(int y=0;y<4;++y){auto&c=p.cells[y][x];c.flags=PathfindCell::UNIT_PRESENT_FIXED;
  c.pos=1+(x*4+y)%6;baseline.cells[y][x]=c;}
 TCheckMovementInfo a{{2,2},1,2,false,false,1},b=a;
 assert(p.checkForMovement(&mover,a)&&baseline.checkForMovement(&mover,b));
 assert(a.allyFixedCount==7&&a.allyFixedCount==b.allyFixedCount);
 p.cells[0][0].type=PathfindCell::CELL_OBSTACLE;p.cells[0][0].present=true;
 assert(p.checkDestination(&mover,0,0,1,0,true));
 p.cells[0][0].present=false;assert(!p.checkDestination(&mover,0,0,1,0,true));
 mover.ai.aircraft=true;p.cells[0][0].aircraft=false;
 assert(p.checkDestination(&mover,0,0,1,0,true));
 p.cells[0][0].aircraft=true;p.cells[0][0].aircraftID=7;
 assert(p.checkDestination(&mover,0,0,1,0,true));
 p.cells[0][0].aircraftID=6;assert(!p.checkDestination(&mover,0,0,1,0,true));
}
''')

    def test_actual_ios_watcher_pauses_and_invalidates_validation(self):
        source = (ROOT / 'GeneralsMD/Code/GameEngineDevice/Source/SDL3GameEngine.cpp').read_text()
        a = source.index('static inline bool iosShouldPauseRendering()')
        b = source.index('\n}', source.index('static bool SDLCALL iosLifecycleWatcher(', a)) + 2
        run_cpp(r'''
#define GENERALS_OCCUPANCY_WORKER 1
#define GENERALS_SEARCH_CONTEXT 1
#define SDLCALL
#include "occupancyvalidationworker.h"
#include <cassert>
std::atomic<bool> s_appBackgrounded{false},s_appInactive{false};
enum{SDL_EVENT_WILL_ENTER_BACKGROUND,SDL_EVENT_DID_ENTER_BACKGROUND,SDL_EVENT_DID_ENTER_FOREGROUND,SDL_EVENT_WINDOW_FOCUS_LOST,SDL_EVENT_WINDOW_FOCUS_GAINED};
struct SDL_Event{int type;};
''' + source[a:b] + r'''
int main(){using namespace PathOccupancy;SDL_Event event{SDL_EVENT_WILL_ENTER_BACKGROUND};
 auto epoch=validationLifecycleEpoch().load();iosLifecycleWatcher(nullptr,&event);assert(validationPaused().load());
 assert(validationLifecycleEpoch().load()>epoch);
 event.type=SDL_EVENT_WINDOW_FOCUS_LOST;iosLifecycleWatcher(nullptr,&event);
 event.type=SDL_EVENT_DID_ENTER_FOREGROUND;iosLifecycleWatcher(nullptr,&event);assert(validationPaused().load());
 event.type=SDL_EVENT_WINDOW_FOCUS_GAINED;iosLifecycleWatcher(nullptr,&event);assert(!validationPaused().load());
}
''')

    def test_transcripts_survive_world_and_unit_deletion(self):
        run_cpp(fixture() + r'''
int main(){PathOccupancy::Transcript transcript;
 {
  Pathfinder p;Object mover;mover.id=7;mover.hasAI=true;
  for(int i=1;i<5;++i){logic.units[i].id=i;logic.units[i].hasAI=true;logic.exists[i]=true;}
  mover.allyMask=0xff;
  p.cells[1][1].flags=PathfindCell::UNIT_PRESENT_FIXED;p.cells[1][1].pos=1;
  p.cells[2][1].flags=PathfindCell::UNIT_GOAL_OTHER_MOVING;p.cells[2][1].pos=2;
  transcript.input={false,1,1,1,1,true,true,false,true,0};
  LiveOccupancyReader live{&p,&mover};live.transcript=&transcript;
  transcript.expected=PathOccupancy::evaluate(transcript.input,live);
  assert(!transcript.overflow&&transcript.expected.allyFixedCount>0&&transcript.expected.allyMoving);
 }
 logic=Logic{};assert(PathOccupancy::validate(transcript));
 auto corrupt=transcript;corrupt.events[0].op=PathOccupancy::Op::Cell;
 bool rejected=false;try{rejected=!PathOccupancy::validate(corrupt);}catch(const std::exception&){rejected=true;}assert(rejected);
 transcript.expected.allowed=!transcript.expected.allowed;assert(!PathOccupancy::validate(transcript));
}
''')

    def test_live_queries_need_no_shadow_thread(self):
        run_cpp(fixture(shadow=False) + r'''
int main(){Pathfinder p;Object mover;mover.id=1;p.m_occupancySamplesRemaining=4;
 TCheckMovementInfo info{{1,1},1,0,true,false,1};
 for(int i=0;i<10000;++i)assert(p.checkForMovement(&mover,info));
 assert(!p.m_occupancyValidation&&p.m_occupancySamplesRemaining==4);
}
''')

    def test_budget_and_worker_submission_are_bounded(self):
        run_cpp(fixture() + r'''
int main(){Pathfinder p;Object mover;mover.id=1;p.m_occupancySamplesRemaining=4;
 TCheckMovementInfo info{{1,1},1,0,true,false,1};
 for(int i=0;i<10000;++i)assert(p.checkForMovement(&mover,info));
 assert(p.m_occupancyValidation&&p.m_occupancySamplesRemaining==0);
 p.m_occupancyValidation->worker.stop();assert(!p.m_occupancyValidation->worker.mismatches());
}
''')

    def test_overflow_does_not_change_live_query(self):
        run_cpp(fixture() + r'''
int main(){Pathfinder p;Object mover;mover.id=7;mover.hasAI=true;mover.allyMask=0xff;
 logic.units[1].id=1;logic.units[1].hasAI=true;logic.exists[1]=true;
 for(auto&row:p.cells)for(auto&c:row){c.flags=PathfindCell::UNIT_PRESENT_FIXED;c.pos=1;}
 PathOccupancy::Transcript trace;trace.input={false,1,1,1,1,true,true,false,false,0};
 LiveOccupancyReader live{&p,&mover};live.transcript=&trace;auto result=PathOccupancy::evaluate(trace.input,live);
 // Force a bounded transcript overflow without changing the evaluator or live result.
 for(unsigned i=0;i<600;++i)trace.record(PathOccupancy::Op::HasMover,0,0,0,1);
 assert(result.allowed&&result.allyFixedCount==1&&trace.overflow&&trace.count==trace.capacity);
 PathOccupancy::ValidationWorker worker;assert(!worker.submit(trace));worker.stop();
}
''')

    def test_pause_reset_teardown_and_actual_worker_execution(self):
        run_cpp(r'''
#include "occupancyvalidationworker.h"
#include <cassert>
#include <chrono>
#include <thread>
#include <type_traits>
int main(){using namespace PathOccupancy;
 static_assert(std::is_trivially_copyable<Transcript>::value,"Owned records");
 Transcript trace;trace.input.destination=false;
 trace.record(Op::HasMover,0,0,0,0);trace.expected.allowed=true;
 setValidationPaused(true);
 ValidationWorker worker;assert(!worker.submit(trace));
 setValidationPaused(false);
 auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
 bool submitted=false;
 while(!(submitted=worker.submit(trace))&&std::chrono::steady_clock::now()<deadline)std::this_thread::yield();
 assert(submitted);
 while(!worker.validated()&&std::chrono::steady_clock::now()<deadline)std::this_thread::yield();
 assert(worker.validated()==1&&!worker.mismatches());
 worker.invalidate();setValidationPaused(true);assert(!worker.submit(trace));
 setValidationPaused(false);
 for(int i=0;i<5000;++i){worker.submit(trace);if(i%7==0)worker.invalidate();if(i%11==0){setValidationPaused(true);setValidationPaused(false);}}
 worker.stop();assert(!worker.submit(trace));assert(!worker.mismatches());
 for(int i=0;i<100;++i){ValidationWorker shortLived;shortLived.submit(trace);}
}
''')


if __name__ == '__main__':
    if '--tsan' in sys.argv:
        sys.argv.remove('--tsan')
        run_cpp = partial(run_cpp, extra_flags=('-O1', '-g', '-fsanitize=thread'))
    unittest.main()
