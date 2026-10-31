#!/usr/bin/env python3
"""Verify wider joined batches against serial queue semantics using production search APIs."""
# GeneralsX @feature Codex 31/10/2026 Cover four logical results, two reusable arenas and unchanged per-request scheduling.
import sys
import unittest
import subprocess
import tempfile
from pathlib import Path
from functools import partial
from compiled_harness import ROOT, run_cpp
import test_path_lookahead as look
import test_participant_path_pool as pool


def four_fixture(enabled=True,timing=True,reuse=True,cached=True):
    return '#define GENERALS_ZH_PATH_FOUR_REQUESTS 1\n'+pool.pool_fixture(enabled,timing,reuse,cached)


def queue_fixture(timing=True,cached=True):
    source=four_fixture(timing=timing,cached=cached)
    marker='void AIUpdateInterface::doPathfind(Pathfinder*p)'
    a=source.index(marker);i=source.index('{',a)+1;depth=1
    while depth:
        depth+=(source[i]=='{')-(source[i]=='}');i+=1
    return source[:a]+look.QUEUE_CALLBACKS+source[i:]


SETUP=r'''
struct FourRequests {
 Object c,d;
 FourRequests(Pathfinder&p){c.id=3;d.id=4;c.ai.obj=&c;d.ai.obj=&d;logic.objects[3]=&c;logic.objects[4]=&d;
  for(unsigned i=0;i<4;++i)p.m_queuedPathfindRequests[i]=i+1;p.m_queuePRTail=4;
 }
};
'''


def extended_matrix():
    source=look.QUEUE_MATRIX.replace('scenario<24','scenario<40')
    source=source.replace('switch(scenario){',r'''
 if(scenario>=24){queue={1,2,3,4,5,6};for(unsigned i=0;i<4;++i){extra[i].ai.eligible=true;extra[i].ai.from={25,float(35+i*10),0};}}
 switch(scenario){
  case 24:break;
  case 25:start=510;break;
  case 26:queue={1,7,2,8,3,9,4,5};break;
  case 27:queue={1,2,2,3,3,4,5};break;
  case 28:trialAfter=[&](Pathfinder*,ObjectID id){if(id==1)extra[1].ai.to={75,65,0};};break;
  case 29:trialAfter=[&](Pathfinder*,ObjectID id){if(id==2)terrain.bias=2;};break;
  case 30:trialAfter=[&](Pathfinder*,ObjectID id){if(id==1)logic.objects.erase(3);};break;
  case 31:trialAfter=[&](Pathfinder*,ObjectID id){if(id==2)mainPathfindSearchContext().m_isTunneling=true;};break;
  case 32:extra[0].ai.safe=extra[1].ai.safe=true;trialAfter=[&](Pathfinder*,ObjectID id){if(id==1)mainPathfindSearchContext().m_ignoreObstacleID=999;};break;
  case 33:w.a.ai.safe=w.b.ai.safe=true;for(auto&o:extra)o.ai.safe=true;break;
  case 34:w.a.ai.closest=w.b.ai.closest=true;for(auto&o:extra)o.ai.closest=true;break;
  case 35:for(int x=8;x<=10;++x)for(int y=8;y<=10;++y)if(x!=9||y!=9)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);break;
  case 36:trialAfter=[&](Pathfinder*q,ObjectID id){if(id==2)++q->m_parallelWorldEpoch;};break;
  case 37:trialAfter=[&](Pathfinder*,ObjectID id){if(id==1){PathOccupancy::setValidationPaused(true);PathOccupancy::setValidationPaused(false);}};break;
  case 38:trialAfter=[&](Pathfinder*q,ObjectID id){if(id==1&&!enqueued){enqueued=true;assert(q->queueForPath(1));}};break;
  case 39:queue={1,2,3,4};trialBefore=[&](Pathfinder*q,ObjectID id){if(id==2){auto*path=q->findPathWithInputs(&extra[1],extra[1].ai.locomotor,&extra[1].ai.from,&extra[1].ai.to);delete path;}};break;
''')
    return source


class FourRequestPathPoolTests(unittest.TestCase):
    def test_cmake_requires_pool_and_lookahead_and_defaults_to_two(self):
        cmake=(ROOT/'CMakeLists.txt').read_text()
        options=cmake[cmake.index('option(GENERALS_COMPLETE_PATH_WORKER'):cmake.index('option(GENERALS_FROZEN_OCCUPANCY_CACHE')]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.25)\nproject(PoolOptions NONE)\n'+options+'''
get_directory_property(flags COMPILE_DEFINITIONS)
file(WRITE "${CMAKE_BINARY_DIR}/flags.txt" "${flags}")
''')
            base=['-DGENERALS_PARALLEL_PATH_BATCH=ON','-DGENERALS_COMPLETE_PATH_WORKER=ON',
                  '-DGENERALS_REUSE_PATH_CONTEXTS=ON','-DGENERALS_PATH_WORKER_POOL=ON','-DGENERALS_PATH_LOOKAHEAD=ON']
            for index,extra in enumerate([[],['-DGENERALS_PATH_FOUR_REQUESTS=ON'],
                    ['-DGENERALS_PATH_FOUR_REQUESTS=ON','-DGENERALS_PATH_WORKER_POOL=OFF'],
                    ['-DGENERALS_PATH_FOUR_REQUESTS=ON','-DGENERALS_PATH_LOOKAHEAD=OFF']]):
                build=root/str(index)
                result=subprocess.run(['cmake','-S',str(root),'-B',str(build),*base,*extra],text=True,capture_output=True)
                if index<2:
                    self.assertEqual(0,result.returncode,result.stdout+result.stderr)
                    definitions=(build/'flags.txt').read_text().split(';')
                    self.assertEqual(index==1,'GENERALS_PATH_FOUR_REQUESTS=1' in definitions)
                    # Exercise the production header's derived flags before its capacity/timing includes.
                    header=(ROOT/'Core/GameEngine/Include/GameLogic/AIPathfind.h').read_text()
                    gates=header[header.index('#if defined(GENERALS_SEARCH_CONTEXT)'):header.index('//#include "GameLogic/Locomotor.h"')]
                    prefix='#include <cstddef>\nusing Bool=bool;\n#define RTS_ZEROHOUR 1\n'
                    prefix+=''.join('#define '+name+' 1\n' for name in ['GENERALS_SEARCH_CONTEXT',
                        'GENERALS_OCCUPANCY_WORKER','GENERALS_EXCLUSIVE_PATH_WORKER','GENERALS_PARALLEL_PATH_BATCH','GENERALS_PATH_TIMING'])
                    prefix+=''.join('#define '+item.replace('=',' ')+'\n' for item in definitions if item)
                    run_cpp(prefix+gates+'\nstatic_assert(PathSearchBatchLimits::capacity=='+str(4 if index else 2)+');int main(){}')
                else:
                    self.assertNotEqual(0,result.returncode)
                    self.assertIn('requires the joined pool and anchored lookahead',result.stderr)

    def test_four_results_use_only_two_arenas_and_retain_private_paths(self):
        run_cpp(four_fixture()+SETUP+r'''
int main(){for(unsigned width=2;width<=4;++width){World w;Pathfinder p;FourRequests units(p);p.m_queuePRTail=width;
 hierarchyArrived=0;hierarchyRendezvous=true;p.prepareParallelBatch();hierarchyRendezvous=false;auto&b=*p.m_parallelBatch;
 static_assert(PathfindParallelBatch::capacity==4);assert(b.count==width&&b.pool.workers()==1&&b.arenas.size()==2);
 assert(b.poolJobs[0]>0&&b.poolJobs[1]>0&&b.poolJobs[0]+b.poolJobs[1]==width);
 auto*first=b.arenas[0].get();auto*second=b.arenas[1].get();
 assert(p.m_lookaheadProfile.selectedCounts[width]==1&&b.primarySearches==width);
 for(unsigned i=0;i<width;++i){assert(b.jobs[i].complete&&b.jobs[i].ready&&b.jobs[i].completedPath);assert(b.jobs[i].executionParticipant<2);}
 for(unsigned i=width;i<4;++i)assert(!b.jobs[i].ready&&!b.jobs[i].locomotor);
 for(auto&arena:b.arenas){PathfindParallelJob::resetArena(*arena);arena->m_cumulativeCellsAllocated=999;}
 for(unsigned i=0;i<width;++i){auto*o=logic.findObjectByID(i+1);delete w.consume(p,*o);}
 assert(b.accepted==width);p.clearParallelBatch();assert(b.count==0&&liveEngineObjects==0);
 assert(b.arenas[0].get()==first&&b.arenas[1].get()==second);
}}
''',timeout=45)

    def test_all_selected_duplicates_are_excluded_with_original_queue_positions(self):
        run_cpp(four_fixture()+SETUP+r'''
int main(){World w;Pathfinder p;FourRequests units(p);
 const unsigned ids[]={1,2,2,3,3,4,4,999,1};p.m_queuePRTail=9;
 for(unsigned i=0;i<9;++i)p.m_queuedPathfindRequests[i]=ids[i];p.prepareParallelBatch();auto&b=*p.m_parallelBatch;
 assert(b.count==4);const int positions[]={0,1,3,5};for(unsigned i=0;i<4;++i)assert(b.jobs[i].queueIndex==positions[i]&&b.jobs[i].id==i+1);
 assert(p.m_lookaheadProfile.inspected==6&&p.m_lookaheadProfile.skipped[unsigned(PathLookaheadEligibility::Duplicate)]==2);
 p.clearParallelBatch();assert(liveEngineObjects==0);
}
''')

    def test_wide_queue_paths_state_and_order_match_serial(self):
        self.assertEqual('serial_equivalence\n',run_cpp(queue_fixture()+extended_matrix(),timeout=90).stdout)

    def test_budget_stops_after_each_actual_request_and_retires_unused_results(self):
        matrix=extended_matrix().replace('p.processPathfindQueue();auto*b=p.m_parallelBatch;',r'''
 for(unsigned frame=0;frame<64&&p.m_queuePRHead!=p.m_queuePRTail;++frame){
  p.processPathfindQueue();trialTrace.push_back(0xeeeeeeee);trialTrace.push_back(mainPathfindSearchContext().m_cumulativeCellsAllocated);
 }
 assert(p.m_queuePRHead==p.m_queuePRTail);auto*b=p.m_parallelBatch;''')
        self.assertEqual('serial_equivalence\n',run_cpp(queue_fixture().replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')+matrix,timeout=90).stdout)
        run_cpp(queue_fixture().replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')+SETUP+r'''
int main(){World w;Pathfinder p;FourRequests units(p);p.processPathfindQueue();auto&b=*p.m_parallelBatch;
 assert((applied==std::vector<ObjectID>{1})&&p.m_queuePRHead==1&&b.primarySearches==4&&b.accepted==1&&b.unused==3);
 assert(b.count==0&&liveEngineObjects==0&&p.m_lookaheadWindow.empty());
}
''')

    def test_third_and_fourth_results_revalidate_changed_inputs(self):
        run_cpp(four_fixture()+SETUP+r'''
int main(){World w;Pathfinder p;FourRequests units(p);p.prepareParallelBatch();auto&b=*p.m_parallelBatch;
 delete w.consume(p,w.a);delete w.consume(p,w.b);units.c.ai.to={75,65,0};units.d.ai.to={85,65,0};
 delete w.consume(p,units.c);delete w.consume(p,units.d);
 assert(b.accepted==2&&b.rejected==2&&p.m_pathTiming.results(false,PathSearchTiming::Result::Rejected)==2);
 p.clearParallelBatch();assert(liveEngineObjects==0);
}
''')

    def test_deleted_third_and_fourth_objects_are_discarded_without_access(self):
        run_cpp(queue_fixture()+r'''
int main(){World w;Pathfinder p;auto c=std::make_unique<Object>(),d=std::make_unique<Object>();
 c->id=3;d->id=4;c->ai.obj=c.get();d->ai.obj=d.get();logic.objects[3]=c.get();logic.objects[4]=d.get();
 for(unsigned i=0;i<4;++i)p.m_queuedPathfindRequests[i]=i+1;p.m_queuePRTail=4;applied.clear();
 trialAfter=[&](Pathfinder*,ObjectID id){if(id==1){logic.objects.erase(3);c.reset();}if(id==2){logic.objects.erase(4);d.reset();}};
 p.processPathfindQueue();trialAfter={};auto&b=*p.m_parallelBatch;
 assert((applied==std::vector<ObjectID>{1,2})&&p.m_queuePRHead==4&&b.primarySearches==4&&b.accepted==2&&b.unused==2);
 assert(liveEngineObjects==0&&p.m_lookaheadWindow.empty());
}
''')

    def test_lifecycle_change_on_fourth_capture_retires_every_result(self):
        source=four_fixture().replace('struct Object;struct Pathfinder;','struct Object;struct Pathfinder;std::function<void(Object*)>captureHook;')
        source=source.replace('f=from;t=to;i=ignored;','if(captureHook)captureHook(obj);f=from;t=to;i=ignored;',1)
        run_cpp(source+SETUP+r'''
int main(){World w;Pathfinder p;FourRequests units(p);captureHook=[&](Object*o){if(o->id==4)++PathOccupancy::validationLifecycleEpoch();};
 p.prepareParallelBatch();auto&b=*p.m_parallelBatch;assert(!b.active&&b.count==0&&b.poolBatches==0&&p.m_lookaheadWindow.empty());
 for(auto&arena:b.arenas)assert(arena->m_recordIndex.bytes()==0);assert(liveEngineObjects==0);
 captureHook={};p.prepareParallelBatch();assert(b.count==4&&b.primarySearches==4);p.clearParallelBatch();assert(liveEngineObjects==0);
}
''')

    def test_every_failed_primary_has_its_own_reusable_fallback(self):
        run_cpp(four_fixture()+SETUP+r'''
int main(){World w;Pathfinder p;FourRequests units(p);for(auto*o:{&w.a,&w.b,&units.c,&units.d})o->ai.to={95,95,0};
 for(int x=8;x<=10;++x)for(int y=8;y<=10;++y)if(x!=9||y!=9)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();auto&b=*p.m_parallelBatch;assert(b.primarySearches==4&&b.fallbackSearches==4);
 for(auto*o:{&w.a,&w.b,&units.c,&units.d}){assert(!w.consume(p,*o));auto*path=p.findClosestPath(o,o->ai.locomotor,&o->ai.from,&o->ai.to,false,0,false);assert(path);delete path;}
 assert(b.accepted==4&&b.fallbackAccepted==4);
 assert(p.m_pathTiming.results(false,PathSearchTiming::Result::Reused)==4&&p.m_pathTiming.results(true,PathSearchTiming::Result::Reused)==4);
 p.clearParallelBatch();assert(liveEngineObjects==0);
}
''',timeout=45)

    def test_lifecycle_cancellation_and_late_callback_errors_join_all_four(self):
        source=four_fixture().replace('batch.pool.run(selectedCount,','PathOccupancy::setValidationPaused(true);batch.pool.run(selectedCount,',1)
        run_cpp(source+SETUP+r'''
int main(){World w;Pathfinder p;FourRequests units(p);p.prepareParallelBatch();auto&b=*p.m_parallelBatch;
 assert(b.count==4&&b.poolSkipped==4&&b.primarySearches==0);for(auto&job:b.jobs)assert(!job.ready&&!job.complete);
 p.clearParallelBatch();PathOccupancy::setValidationPaused(false);assert(liveEngineObjects==0);
}
''')
        source=four_fixture().replace('auto& job=batch.jobs[index];','auto& job=batch.jobs[index];if(index==3)throw ERROR_OUT_OF_MEMORY;',1)
        run_cpp(source+SETUP+r'''
int main(){World w;Pathfinder p;FourRequests units(p);p.prepareParallelBatch();auto&b=*p.m_parallelBatch;
 assert(p.m_exclusiveWorkerUnavailable&&!b.active&&b.count==0&&liveEngineObjects==0);
 for(auto&arena:b.arenas)assert(!arena->m_ownership.owner.load()&&!arena->m_parallelReads&&!arena->m_completeJob);
}
''')

    def test_four_then_two_results_never_publish_retired_slots(self):
        run_cpp(four_fixture()+SETUP+r'''
int main(){World w;Pathfinder p;FourRequests units(p);p.prepareParallelBatch();auto&b=*p.m_parallelBatch;assert(b.count==4);
 p.clearParallelBatch();p.m_queuePRTail=2;p.prepareParallelBatch();assert(b.count==2&&b.primarySearches==6);
 for(unsigned i=2;i<4;++i)assert(!b.jobs[i].ready&&!b.jobs[i].completedPath&&!b.jobs[i].locomotor);
 delete w.consume(p,w.a);delete w.consume(p,w.b);assert(b.accepted==2);p.clearParallelBatch();assert(liveEngineObjects==0);
}
''')

    def test_timing_resolves_all_four_slots_without_physical_role_confusion(self):
        run_cpp(four_fixture()+SETUP+r'''
int main(){World w;Pathfinder p;FourRequests units(p);p.prepareParallelBatch();auto&b=*p.m_parallelBatch;auto&t=p.m_pathTiming;
 assert(t.slowPairs()[0].taskCount()==4);unsigned worker=0,caller=0;
 for(unsigned i=0;i<4;++i){assert(t.slowPairs()[0].tasks[i].participant==b.jobs[i].executionParticipant);
  if(b.jobs[i].executionParticipant)++worker;else ++caller;}
 assert(t[PathSearchTiming::WorkerKernel].calls==worker&&t[PathSearchTiming::CallerKernel].calls==caller);
 p.clearParallelBatch();assert(t.results(false,PathSearchTiming::Result::Discarded)==4);
 for(unsigned i=0;i<4;++i)assert(t.slowPairs()[0].tasks[i].primaryOutcome.result==PathSearchTiming::Result::Discarded);
 FILE*f=std::tmpfile();t.report(f);p.m_lookaheadProfile.report(f);std::rewind(f);char buffer[1024];std::string text;
 while(std::fgets(buffer,sizeof buffer,f))text+=buffer;std::fclose(f);
 assert(text.find("slot=3 participant=")!=std::string::npos&&text.find("slot3_primary_result=discarded")!=std::string::npos);
 assert(text.find("[PATH_LOOKAHEAD_SELECTED] n0=0 n1=0 n2=0 n3=0 n4=1")!=std::string::npos);
 assert(liveEngineObjects==0);
}
''')

    def test_timing_and_cache_off_preserve_wide_queue_equivalence(self):
        self.assertEqual('serial_equivalence\n',run_cpp(queue_fixture(timing=False,cached=False)+extended_matrix(),timeout=90).stdout)


def suite():
    look.lookahead_fixture=four_fixture
    names=[
        'test_queue_paths_state_and_order_match_serial_in_both_retail_modes',
        'test_per_request_budget_and_frame_end_retirement_match_serial',
        'test_nonadjacent_results_survive_holes_in_every_search_kind',
        'test_candidate_exclusions_and_fresh_capture_preserve_selected_inputs',
        'test_head_anchor_scan_bound_and_negative_windows_need_no_result_buffers',
        'test_recovery_joins_then_clears_window_and_all_owned_paths',
        'test_loaded_world_retires_positive_and_negative_windows',
        'test_deleted_future_object_is_discarded_without_dereferencing_capture',
    ]
    return unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(FourRequestPathPoolTests),
                              unittest.TestSuite(look.PathLookaheadTests(name) for name in names)])


if __name__=='__main__':
    if '--tsan' in sys.argv:run_cpp=partial(run_cpp,extra_flags=('-fsanitize=thread','-g','-O1'))
    if '--asan' in sys.argv:run_cpp=partial(run_cpp,extra_flags=('-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-O1'))
    look.run_cpp=run_cpp
    result=unittest.TextTestRunner().run(suite())
    sys.exit(not result.wasSuccessful())
