#!/usr/bin/env python3
"""Exercise production eligible-head lookahead, retained windows and serial queue semantics.

Use --tsan for bounded concurrent search checks. World and AI services are controlled.
"""
# GeneralsX @feature Codex 30/10/2026 Verify nonadjacent dispatch without changing authoritative callback order, budgets or validation.
import sys
import unittest
from functools import partial
from compiled_harness import run_cpp
from test_reused_path_contexts import base_fixture
from test_path_movement_inputs import function, HEADER


def lookahead_fixture(enabled=True,timing=True,reuse=True,cached=True):
    source=base_fixture(reuse,cached,timing)
    if enabled:source='#define GENERALS_ZH_PATH_LOOKAHEAD 1\n#include "pathlookaheadwindow.h"\n'+source
    start=HEADER.index(' unsigned long long m_parallelWorldEpoch;')
    members=HEADER[start:HEADER.index(' void prepareParallelBatch();',start)]
    members=members.replace('m_parallelWorldEpoch;','m_parallelWorldEpoch=0;',1)
    source=source.replace('unsigned long long m_parallelWorldEpoch=0;',members)
    source=source.replace('void prepareParallelBatch();void clearParallelBatch();','void prepareParallelBatch();void clearParallelBatch();void loadPostProcess();void invalidateParallelResults(){++m_parallelWorldEpoch;}Bool queueForPath(ObjectID);')
    source+='\n'+function('Bool Pathfinder::queueForPath(')
    source+='\n'+function('void Pathfinder::loadPostProcess()')
    return source


def queue_fixture(enabled=True,timing=True,reuse=True,cached=True):
    source=lookahead_fixture(enabled,timing,reuse,cached)
    marker='void AIUpdateInterface::doPathfind(Pathfinder*p)'
    a=source.index(marker);i=source.index('{',a)+1;depth=1
    while depth:
        depth+=(source[i]=='{')-(source[i]=='}');i+=1
    return source[:a]+QUEUE_CALLBACKS+source[i:]


QUEUE_CALLBACKS=r'''
std::vector<std::uint32_t> trialTrace;
std::function<void(Pathfinder*,ObjectID)> trialBefore,trialAfter;
void AIUpdateInterface::doPathfind(Pathfinder*p){
 applied.push_back(obj->id);if(trialBefore)trialBefore(p,obj->id);
 Path*path=nullptr;
 if(safe)path=p->findSafePath(obj,locomotor,&from,&repulsor1,&repulsor2,repulsorRadius);
 else if(closest)path=p->findClosestPath(obj,locomotor,&from,&to,blocked,pathCostMultiplier,false);
 else {mainPathfindSearchContext().m_ignoreObstacleID=ignored;path=p->findPathWithInputs(obj,locomotor,&from,&to);
  if(!path){p->confirmParallelFallback(obj,locomotor,from,to,false);path=p->findClosestPath(obj,locomotor,&from,&to,false,0,false);}}
 trialTrace.push_back(obj->id);trialTrace.push_back(path!=nullptr);
 const auto coordinate=[](float f){std::uint32_t bits;std::memcpy(&bits,&f,4);trialTrace.push_back(bits);};
 if(path)for(auto*n=path->getFirstNode();n;n=n->getNext()){
  coordinate(n->getPosition()->x);coordinate(n->getPosition()->y);coordinate(n->getPosition()->z);trialTrace.push_back(n->getLayer());
  auto*opt=n->getNextOptimized();trialTrace.push_back(opt!=nullptr);if(opt){coordinate(opt->getPosition()->x);coordinate(opt->getPosition()->y);}
 }
 coordinate(to.x);coordinate(to.y);coordinate(to.z);trialTrace.push_back(0xffffffff);delete path;if(trialAfter)trialAfter(p,obj->id);
}
'''

QUEUE_MATRIX=r'''
struct Output {std::vector<std::uint32_t> trace;std::vector<ObjectID> order;int charge,head,tail;unsigned accepted,rejected,unused,batches;int scans,probes,maxScan;ObjectID ignored;bool tunneling;std::vector<unsigned char>corridor;};
Output run(int scenario,int mode){
 World w;Pathfinder p;std::array<Object,12> extra;
 for(unsigned i=0;i<extra.size();++i){auto&o=extra[i];o.id=i+3;o.ai.obj=&o;o.ai.eligible=false;o.ai.from={25,25,0};o.ai.to={95,95,0};logic.objects[o.id]=&o;}
 p.m_exclusiveWorkerUnavailable=mode==0;
 applied.clear();trialTrace.clear();trialBefore={};trialAfter={};terrain.bias=0;
 std::vector<ObjectID> queue{1,3,2};int start=0;bool enqueued=false;
 switch(scenario){
  case 0:break;
  case 1:queue={999,1,3,2};break;
  case 2:start=510;break;
  case 3:trialBefore=[&](Pathfinder*,ObjectID id){if(id==3)terrain.bias=2;};break;
  case 4:trialBefore=[&](Pathfinder*,ObjectID id){if(id==3)w.b.ai.to={75,65,0};};break;
  case 5:trialAfter=[&](Pathfinder*q,ObjectID id){if(id==1&&!enqueued){enqueued=true;assert(q->queueForPath(1));}};break;
  case 6:queue={1,1,2};break;
  case 7:queue={3,4,5,6,7,8,9,10,1,2};break;
  case 8:queue={1,3,4};break;
  case 9:queue={3,4,5};break;
  case 10:queue={3,1,2};break;
  case 11:trialBefore=[&](Pathfinder*q,ObjectID id){if(id==3)++q->m_parallelWorldEpoch;};break;
  case 12:w.a.ai.safe=w.b.ai.safe=true;break;
  case 13:w.a.ai.closest=w.b.ai.closest=true;break;
  case 14:p.quickAllowed=false;break;
  case 15:for(int x=8;x<=10;++x)for(int y=8;y<=10;++y)if(x!=9||y!=9)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);break;
  case 16:w.b.ai.safe=true;trialAfter=[&](Pathfinder*,ObjectID id){if(id==3)mainPathfindSearchContext().m_ignoreObstacleID=999;};break;
  case 17:w.b.ai.safe=true;trialAfter=[&](Pathfinder*,ObjectID id){if(id==3)mainPathfindSearchContext().m_corridor.assign(9,0);};break;
  case 18:trialBefore=[&](Pathfinder*q,ObjectID id){if(id==3){auto*path=q->findPathWithInputs(&w.b,w.b.ai.locomotor,&w.b.ai.from,&w.b.ai.to);delete path;}};break;
  case 19:trialBefore=[&](Pathfinder*,ObjectID id){if(id==3)logic.objects.erase(2);};break;
  case 20:queue={1,3,2,4};w.b.ai.eligible=false;extra[1].ai.eligible=true;
   trialAfter=[&](Pathfinder*,ObjectID id){if(id==1)w.b.ai.eligible=true;};break;
  case 21:trialAfter=[&](Pathfinder*,ObjectID id){if(id==3){PathOccupancy::setValidationPaused(true);PathOccupancy::setValidationPaused(false);}};break;
  case 22:p.storage[5][5].setPosUnit(w.a.id,{5,5});trialAfter=[&](Pathfinder*,ObjectID id){if(id==3)w.b.relation=ALLIES;};break;
  case 23:queue={1,3,4,5,6,7,8,9,2};break;
 }
 p.m_queuePRHead=start;p.m_queuePRTail=(start+int(queue.size()))%512;
 for(unsigned i=0;i<queue.size();++i)p.m_queuedPathfindRequests[(start+i)%512]=queue[i];
 p.processPathfindQueue();auto*b=p.m_parallelBatch;
 Output out{trialTrace,applied,mainPathfindSearchContext().m_cumulativeCellsAllocated,p.m_queuePRHead,p.m_queuePRTail,
  b?unsigned(b->accepted):0,b?unsigned(b->rejected):0,b?unsigned(b->unused):0,b?unsigned(b->batches):0,0,0,0,
  mainPathfindSearchContext().m_ignoreObstacleID,mainPathfindSearchContext().m_isTunneling,mainPathfindSearchContext().m_corridor};
 assert(liveEngineObjects==0);trialBefore={};trialAfter={};terrain.bias=0;return out;
}

int main(){for(bool fixed:{false,true})for(int scenario=0;scenario<24;++scenario){s_useFixedPathfinding=fixed;
 const auto serial=run(scenario,0),window=run(scenario,1);
 assert(window.trace==serial.trace&&window.order==serial.order&&window.charge==serial.charge&&window.head==serial.head&&window.tail==serial.tail);
 assert(window.ignored==serial.ignored&&window.tunneling==serial.tunneling&&window.corridor==serial.corridor);
}puts("serial_equivalence");}
'''


class PathLookaheadTests(unittest.TestCase):
    def test_queue_paths_state_and_order_match_serial_in_both_retail_modes(self):
        expected=run_cpp(queue_fixture(False)+QUEUE_MATRIX,timeout=60).stdout
        self.assertEqual(expected,run_cpp(queue_fixture()+QUEUE_MATRIX,timeout=60).stdout)

    def test_per_request_budget_and_frame_end_retirement_match_serial(self):
        matrix=QUEUE_MATRIX.replace('p.processPathfindQueue();auto*b=p.m_parallelBatch;',r'''
 for(unsigned frame=0;frame<32 && p.m_queuePRHead!=p.m_queuePRTail;++frame){
  p.processPathfindQueue();trialTrace.push_back(0xeeeeeeee);trialTrace.push_back(mainPathfindSearchContext().m_cumulativeCellsAllocated);
 }
 assert(p.m_queuePRHead==p.m_queuePRTail);auto*b=p.m_parallelBatch;''')
        expected=run_cpp(queue_fixture(False).replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')+matrix,timeout=60).stdout
        self.assertEqual(expected,run_cpp(queue_fixture().replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')+matrix,timeout=60).stdout)

    def test_timing_cache_and_arena_reuse_are_optional(self):
        # The rollout requires complete APIs, not the profiler, occupancy cache or borrowed-arena implementation.
        for reuse,cached in [(False,False),(True,True)]:
            self.assertEqual('serial_equivalence\n',run_cpp(queue_fixture(timing=False,reuse=reuse,cached=cached)+QUEUE_MATRIX,timeout=60).stdout)

    def test_nonadjacent_results_survive_holes_in_every_search_kind(self):
        run_cpp(queue_fixture()+r'''
int main(){for(int kind=0;kind<5;++kind){World w;Pathfinder p;Object middle;middle.id=3;middle.ai.obj=&middle;middle.ai.eligible=false;
 logic.objects[3]=&middle;p.m_queuedPathfindRequests[0]=1;p.m_queuedPathfindRequests[1]=3;p.m_queuedPathfindRequests[2]=2;p.m_queuePRTail=3;
 w.a.ai.safe=w.b.ai.safe=kind==1;w.a.ai.closest=w.b.ai.closest=kind==2;p.quickAllowed=kind!=3;
 if(kind==4)for(int x=8;x<=10;++x)for(int y=8;y<=10;++y)if(x!=9||y!=9)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();auto&batch=*p.m_parallelBatch;auto&profile=p.m_lookaheadProfile;
 assert(batch.jobs[0].queueIndex==0&&batch.jobs[1].queueIndex==2&&profile.windows==1&&profile.inspected==3&&profile.selected==2&&profile.dispatched==1);
 p.m_queuePRHead=0;w.a.ai.doPathfind(&p);p.m_queuePRHead=1;p.prepareParallelBatch();middle.ai.doPathfind(&p);
 assert(batch.unused==0&&profile.retained==1);
 p.m_queuePRHead=2;p.prepareParallelBatch();w.b.ai.doPathfind(&p);
 assert(batch.accepted==2&&profile.retained==2&&batch.batches==1&&profile.partnerOffsets[2]==1);
 p.clearParallelBatch();assert(profile.retired==1&&p.m_lookaheadWindow.empty()&&liveEngineObjects==0);
}}
''',timeout=45)

    def test_candidate_exclusions_and_fresh_capture_preserve_selected_inputs(self):
        run_cpp(lookahead_fixture()+r'''
int main(){using E=PathLookaheadEligibility;for(unsigned reason=1;reason<unsigned(E::Count);++reason){
 World w;Pathfinder p;Object middle;middle.id=3;middle.ai.obj=&middle;logic.objects[3]=&middle;
 p.m_queuedPathfindRequests[0]=1;p.m_queuedPathfindRequests[1]=3;p.m_queuedPathfindRequests[2]=2;p.m_queuePRTail=3;
 switch(E(reason)){
  case E::Duplicate:p.m_queuedPathfindRequests[1]=1;break;
  case E::MissingObject:logic.objects.erase(3);break;case E::MissingAI:middle.hasAI=false;break;
  case E::Dozer:middle.kind=KINDOF_DOZER;break;case E::CrusherKey:middle.crusher=1;keys.present=false;break;
  case E::Immobile:middle.ai.safe=true;middle.ai.locomotor.surfaces=0;break;
  case E::Prediction:middle.ai.eligible=false;middle.ai.rejectedPrediction=PathPredictionReason::NonFinal;break;
  default:assert(false);
 }
 p.prepareParallelBatch();const auto&job=p.m_parallelBatch->jobs[1];
 assert(job.queueIndex==2&&job.id==w.b.id&&!job.safe&&!job.closest&&job.to.x==w.b.ai.to.x&&job.repulsorRadius==0);
 assert(p.m_lookaheadProfile.skipped[reason]==1&&p.m_lookaheadProfile.eligible==2);
 if(E(reason)==E::Prediction)assert(p.m_lookaheadProfile.predictions[unsigned(PathPredictionReason::NonFinal)]==1);
 keys.present=true;p.clearParallelBatch();assert(liveEngineObjects==0);
}}
''',timeout=30)

    def test_head_anchor_scan_bound_and_negative_windows_need_no_result_buffers(self):
        run_cpp(lookahead_fixture()+r'''
int main(){
 {World w;Pathfinder p;w.queue(p);w.a.ai.eligible=false;p.prepareParallelBatch();
  assert(!p.m_parallelBatch&&p.m_lookaheadProfile.inspected==1&&p.m_lookaheadProfile.selected==0);
  p.prepareParallelBatch();assert(p.m_lookaheadProfile.windows==1&&p.m_lookaheadProfile.retained==1);
  p.clearParallelBatch();assert(p.m_lookaheadWindow.empty()&&p.m_lookaheadProfile.retired==1);
 }
 {World w;Pathfinder p;p.m_queuePRTail=9;p.m_queuedPathfindRequests[0]=1;
  for(int i=1;i<8;++i)p.m_queuedPathfindRequests[i]=999;p.m_queuedPathfindRequests[8]=2;
  p.prepareParallelBatch();assert(!p.m_parallelBatch&&p.m_lookaheadProfile.inspected==8&&p.m_lookaheadProfile.eligible==1);
  for(int i=1;i<8;++i){p.m_queuePRHead=i;p.prepareParallelBatch();}
  assert(p.m_lookaheadProfile.windows==1&&p.m_lookaheadProfile.retained==7);
  p.m_queuePRHead=8;p.prepareParallelBatch();assert(p.m_lookaheadProfile.windows==2&&p.m_lookaheadProfile.inspected==9&&!p.m_parallelBatch);
 }
}
''')

    def test_lifecycle_transition_during_capture_aborts_before_dispatch(self):
        source=lookahead_fixture()
        source=source.replace('struct Object;struct Pathfinder;','struct Object;struct Pathfinder;std::function<void(Object*)>captureHook;')
        source=source.replace('f=from;t=to;i=ignored;','if(captureHook)captureHook(obj);f=from;t=to;i=ignored;',1)
        run_cpp(source+r'''
int main(){for(bool pause:{false,true}){World w;Pathfinder p;w.queue(p);
 captureHook=[&](Object*o){if(o==&w.b){if(pause)PathOccupancy::setValidationPaused(true);else ++PathOccupancy::validationLifecycleEpoch();}};
 p.prepareParallelBatch();assert(p.m_parallelBatch&&!p.m_parallelBatch->active&&p.m_lookaheadWindow.empty());
 assert(p.m_exclusiveWorker->searches==0&&p.m_lookaheadProfile.dispatched==0&&p.m_lookaheadProfile.retired==1&&liveEngineObjects==0);
 captureHook={};PathOccupancy::setValidationPaused(false);p.prepareParallelBatch();assert(p.m_parallelBatch->batches==1);
 delete w.consume(p,w.a);delete w.consume(p,w.b);p.clearParallelBatch();assert(liveEngineObjects==0);
}}
''')

    def test_recovery_joins_then_clears_window_and_all_owned_paths(self):
        run_cpp(lookahead_fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);abortCleanup=true;p.prepareParallelBatch();
 assert(p.m_lookaheadWindow.empty()&&!p.m_parallelBatch->active&&p.m_lookaheadProfile.retired==1&&liveEngineObjects==0);
 abortCleanup=false;p.prepareParallelBatch();assert(p.m_parallelBatch->batches==1);
 delete w.consume(p,w.a);delete w.consume(p,w.b);p.clearParallelBatch();assert(liveEngineObjects==0);
}
''')

    def test_loaded_world_retires_positive_and_negative_windows(self):
        run_cpp(lookahead_fixture()+r'''
int main(){for(bool negative:{false,true}){World w;Pathfinder p;w.queue(p);w.b.ai.eligible=!negative;p.prepareParallelBatch();
 assert(!p.m_lookaheadWindow.empty());const auto epoch=p.m_parallelWorldEpoch;
 p.loadPostProcess();assert(p.m_parallelWorldEpoch==epoch+1&&p.m_lookaheadWindow.empty()&&liveEngineObjects==0);
 assert(!p.m_parallelBatch||!p.m_parallelBatch->active);
 w.b.ai.eligible=true;p.prepareParallelBatch();assert(p.m_lookaheadProfile.windows==2&&p.m_parallelBatch->active);
 delete w.consume(p,w.a);delete w.consume(p,w.b);p.clearParallelBatch();assert(liveEngineObjects==0);
}}
''')

    def test_deleted_future_object_is_discarded_without_dereferencing_capture(self):
        run_cpp(queue_fixture()+r'''
int main(){World w;Pathfinder p;Object middle;middle.id=3;middle.ai.obj=&middle;middle.ai.eligible=false;logic.objects[3]=&middle;
 auto target=std::make_unique<Object>();target->id=4;target->ai.obj=target.get();logic.objects[4]=target.get();
 p.m_queuedPathfindRequests[0]=1;p.m_queuedPathfindRequests[1]=3;p.m_queuedPathfindRequests[2]=4;p.m_queuePRTail=3;
 applied.clear();trialTrace.clear();trialBefore=[&](Pathfinder*,ObjectID id){if(id==3){logic.objects.erase(4);target.reset();}};
 p.processPathfindQueue();trialBefore={};
 assert((applied==std::vector<ObjectID>{1,3})&&p.m_queuePRHead==3&&p.m_parallelBatch->accepted==1&&p.m_parallelBatch->unused==1);
 assert(p.m_lookaheadWindow.empty()&&liveEngineObjects==0);
}
''')

    def test_window_epoch_wrap_reset_and_profile_reports(self):
        run_cpp(r'''
#include "pathlookaheadwindow.h"
#include <string>
int main(){PathLookaheadWindow<512> window;
 for(unsigned begin=0;begin<512;++begin)for(unsigned count=0;count<=8;++count){
  window.capture(begin,count,7,11);
  for(unsigned offset=0;offset<512;++offset)assert(window.contains((begin+offset)%512,7,11)==(offset<count));
  assert(!window.contains(begin,8,11)&&!window.contains(begin,7,12));window.reset();assert(window.empty());
 }
 PathLookaheadProfile p;p.record(3,2,2,2);p.record(8,1,0,0);p.reject(PathLookaheadEligibility::Prediction,PathPredictionReason::NonFinal);
 FILE*f=std::tmpfile();assert(f);p.report(f);std::rewind(f);char buffer[1024];std::string text;while(std::fgets(buffer,sizeof buffer,f))text+=buffer;std::fclose(f);
 assert(text.find("inspected=11 eligible=3 selected=2 dispatched=0")!=std::string::npos);
 assert(text.find("offset2=1")!=std::string::npos&&text.find("nonfinal=1")!=std::string::npos);
}
''')


if __name__=='__main__':
    if '--tsan' in sys.argv:run_cpp=partial(run_cpp,extra_flags=('-fsanitize=thread','-g','-O1'))
    if '--asan' in sys.argv:run_cpp=partial(run_cpp,extra_flags=('-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-O1'))
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(PathLookaheadTests))
    sys.exit(not result.wasSuccessful())
