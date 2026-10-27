#!/usr/bin/env python3
"""Exercise actual ordinary-search worker dispatch and caller-only finalization."""
# GeneralsX @feature Codex 27/10/2026 Compare whole ordinary calls with serial execution across an exclusive phase.
import sys
import unittest
from functools import partial
from compiled_harness import ROOT, run_cpp
from test_path_movement_inputs import fixture
from test_search_record_pool import engine_fixture


class ExclusiveTests(unittest.TestCase):
    def test_actual_search_worker_matches_serial_routes_and_expansions(self):
        main = r'''
int main(){for(bool fixed:{false,true})for(int scenario=0;scenario<24;++scenario){
 s_useFixedPathfinding=fixed;Pathfinder p;Object o;LocomotorSet loco;
 o.kind=scenario%2?1:2;o.crusher=scenario%3==0;o.ai.through=scenario%4==0;
 o.player.type=scenario%2?PLAYER_COMPUTER:1;loco.downhill=scenario%5==0;p.allied=scenario%3==1;
 for(int y=1;y<11;++y)if(y!=scenario%9+1)p.cells[y][6].type=PathfindCell::CELL_OBSTACLE;
 Coord3D from{25,25,0},to{95,95,0};auto*path=p.internalFindPath(&o,loco,&from,&to);
#ifdef GENERALS_ZH_EXCLUSIVE_PATH_WORKER
 assert(p.m_exclusiveWorker&&p.m_exclusiveWorker->searches==1);
 assert(p.workerExpansions==int(p.expansion.size()));
#else
 assert(!p.workerExpansions);
#endif
 std::ostringstream out;out<<scenario<<':'<<(path?1:0)<<':';
 for(auto c:p.result.route)out<<c.x<<','<<c.y<<';';out<<" E ";for(auto c:p.expansion)out<<c.x<<','<<c.y<<';';
 out<<" B "<<p.result.blocked<<'\n';std::fputs(out.str().c_str(),stdout);
}}
'''
        self.assertEqual(run_cpp(fixture(True, False) + main).stdout,
                         run_cpp(fixture(True, True) + main).stdout)

    def test_pause_debug_and_nested_context_use_serial_fallback(self):
        run_cpp(fixture(True, True) + r'''
int main(){Object o;LocomotorSet loco;Coord3D from{25,25,0},to{95,95,0};
 {Pathfinder p;PathOccupancy::setValidationPaused(true);assert(p.internalFindPath(&o,loco,&from,&to));assert(!p.m_exclusiveWorker);}
 PathOccupancy::setValidationPaused(false);
 {Pathfinder p;global.m_debugAI=2;assert(p.internalFindPath(&o,loco,&from,&to));assert(!p.m_exclusiveWorker);}
 global.m_debugAI=0;
 {Pathfinder p;SearchContextBinding<PathfindSearchContext> outer(activePathfindSearchContext());
  assert(p.internalFindPath(&o,loco,&from,&to));assert(!p.m_exclusiveWorker);}
 {Pathfinder p;p.m_exclusiveWorkerUnavailable=true;assert(p.internalFindPath(&o,loco,&from,&to));assert(!p.m_exclusiveWorker);}
 {Pathfinder p;nameKeys.present=false;o.crusher=1;assert(p.internalFindPath(&o,loco,&from,&to));assert(!p.m_exclusiveWorker);}
 nameKeys.present=true;
}
''')

    def test_real_cell_records_survive_worker_handoff(self):
        run_cpp(engine_fixture() + r'''
#include "exclusivesearchworker.h"
int main(){PathfindCellInfo::allocateCellInfos();auto&context=mainPathfindSearchContext();PathfindCell a,b;
 a.setGoalUnit(17,{2,3});
 {
  SearchContextBinding<PathfindSearchContext> owner(context);
  PathfindSearchContext::AdmissionScope admission(context,PathfindSearchContext::permanentRecordsInUse());
  assert(a.allocateSearchInfo({2,3})&&b.allocateSearchInfo({3,3}));
  ExclusiveSearchWorker worker;
  owner.transferAndWait([&]{worker.run([&]{SearchContextBinding<PathfindSearchContext> selected(context);
   a.setCostSoFar(11);a.setTotalCost(12);b.setParentCell(&a);b.setCostSoFar(21);b.setTotalCost(22);
   a.putOnSortedOpenList(context.m_openList);b.putOnClosedList(context.m_closedList);
  });});
  assert(a.getCostSoFar()==11&&b.getParentCell()==&a&&a.getGoalUnit()==17);
  assert(context.m_openList.getHead()==&a&&context.m_closedList.getHead()==&b);
  PathfindCell::releaseOpenList(context.m_openList);PathfindCell::releaseClosedList(context.m_closedList);
 }
 a.setGoalUnit(0,{2,3});context.releaseStorage();PathfindCellInfo::releaseCellInfos();
}
''')

    def test_read_only_name_lookup_does_not_insert_missing_keys(self):
        source=(ROOT / 'GeneralsMD/Code/GameEngine/Source/Common/NameKeyGenerator.cpp').read_text()
        a=source.index('NameKeyType NameKeyGenerator::findExistingNameKey(')
        body=source[a:source.index('\n}',a)+2]
        run_cpp(r'''
#include <cassert>
#include <cstring>
#include <string>
using NameKeyType=int;using UnsignedInt=unsigned;constexpr int NAMEKEY_INVALID=0;
struct Text{std::string text;const char*str()const{return text.c_str();}};
struct Bucket{Bucket*m_nextInSocket=nullptr;int m_key=0;Text m_nameString;};
unsigned calcHashForString(const char*p){unsigned result=0;for(;*p;++p)result=(result<<5)+result+static_cast<unsigned char>(*p);return result;}
struct NameKeyGenerator{enum{SOCKET_COUNT=1};Bucket*m_sockets[1]{};NameKeyType findExistingNameKey(const char*)const;};
''' + body + r'''
int main(){NameKeyGenerator generator;assert(!generator.findExistingNameKey("SquishCollide"));assert(!generator.m_sockets[0]);
 Bucket first{nullptr,17,{"Known"}},second{nullptr,29,{"SquishCollide"}};first.m_nextInSocket=&second;generator.m_sockets[0]=&first;
 assert(generator.findExistingNameKey("SquishCollide")==29&&generator.findExistingNameKey("Known")==17);
 assert(!generator.findExistingNameKey("Missing")&&generator.m_sockets[0]==&first&&first.m_nextInSocket==&second);
}
''')

    def test_transfer_restoration_exceptions_and_floating_point_environment(self):
        run_cpp(r'''
#include "searchcontextbinding.h"
#include "exclusivesearchworker.h"
#include <cassert>
struct Context{SearchContextOwnership m_ownership;int value=0;};
int main(){Context context;SearchContextBinding<Context> owner(context);ExclusiveSearchWorker worker;
 const auto main=std::this_thread::get_id();assert(std::fesetround(FE_DOWNWARD)==0);
 owner.transferAndWait([&]{worker.run([&]{SearchContextBinding<Context> binding(context);
  assert(std::this_thread::get_id()!=main&&ExclusiveSearchWorker::onWorker());
  assert(std::fegetround()==FE_DOWNWARD);context.value=7;
 });});
 assert(context.value==7&&SearchContextBinding<Context>::current()==&context&&owner.canTransfer());
 bool caught=false;try{owner.transferAndWait([&]{worker.run([&]{SearchContextBinding<Context> binding(context);throw std::runtime_error("test");});});}
 catch(const std::runtime_error&){caught=true;}
 assert(caught&&owner.canTransfer()&&SearchContextBinding<Context>::current()==&context);
 owner.transferAndWait([&]{worker.run([&]{SearchContextBinding<Context> binding(context);context.value=9;});});
 assert(context.value==9&&std::fegetround()==FE_DOWNWARD);
}
''')

    def test_reuse_and_shutdown_after_completed_searches(self):
        run_cpp(fixture(True, True) + r'''
int main(){for(int pass=0;pass<8;++pass){Pathfinder p;Object o;LocomotorSet loco;Coord3D from{25,25,0},to{95,95,0};
 for(int i=0;i<40;++i){p.result=Path{};p.expansion.clear();p.workerExpansions=0;
  for(auto&row:p.cells)for(auto&c:row){c.info=false;c.parent=nullptr;}
  assert(p.internalFindPath(&o,loco,&from,&to));assert(p.workerExpansions>0);
 }
 assert(p.m_exclusiveWorker->searches==40);
}}
''')


if __name__ == '__main__':
    if '--tsan' in sys.argv:
        sys.argv.remove('--tsan')
        run_cpp = partial(run_cpp, extra_flags=('-O1', '-g', '-fsanitize=thread'))
    unittest.main()
