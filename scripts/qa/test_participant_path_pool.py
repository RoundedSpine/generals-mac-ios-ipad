#!/usr/bin/env python3
"""Execute complete production searches with participant arenas and dynamic claims; add --tsan or --asan."""
# GeneralsX @feature Codex 31/10/2026 Validate pool-owned scratch, independent results and physical/logical timing ownership.
import sys
import unittest
from functools import partial
from compiled_harness import run_cpp
import test_path_lookahead as look

original_fixture=look.lookahead_fixture


def pool_fixture(enabled=True,timing=True,reuse=True,cached=True):
    if not reuse:raise ValueError('Participant arenas require independent complete-result snapshots')
    source=original_fixture(enabled,timing,reuse,cached)
    source=source.replace('void executeCompletePath(PathfindParallelJob&);','void executeCompletePath(PathfindParallelJob&,PathfindSearchContext&);')
    return '#define GENERALS_ZH_PATH_WORKER_POOL 1\n#include "joinedsearchpool.h"\n'+source


class ParticipantPathPoolTests(unittest.TestCase):
    def test_result_reset_cannot_reset_participant_arenas(self):
        run_cpp(pool_fixture()+r'''
template<class T,class=void>struct ownsArena:std::false_type{};
template<class T>struct ownsArena<T,std::void_t<decltype(std::declval<T>().context)>>:std::true_type{};
int main(){static_assert(!ownsArena<PathfindParallelJob>::value,"Results must not contain search arenas or references");
 World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();auto&batch=*p.m_parallelBatch;
 auto*first=batch.arenas[0].get();auto*second=batch.arenas[1].get();assert(first!=second&&!p.m_exclusiveWorker);
 const auto a=first->generation(),b=second->generation();
 for(auto&job:batch.jobs)job.reset();assert(first->generation()==a&&second->generation()==b&&liveEngineObjects==0);
 p.clearParallelBatch();assert(first->generation()!=a&&second->generation()!=b);
 for(unsigned repeat=0;repeat<12;++repeat){p.m_queuePRHead=0;p.prepareParallelBatch();
  assert(batch.arenas[0].get()==first&&batch.arenas[1].get()==second);
  delete w.consume(p,w.a);delete w.consume(p,w.b);p.clearParallelBatch();assert(liveEngineObjects==0);
  for(const auto&arena:batch.arenas)assert(!arena->m_parallelReads&&!arena->m_completeJob&&!arena->m_requestAdmission&&!arena->m_ownership.owner.load());
 }
}
''',timeout=45)

    def test_four_complete_jobs_share_three_concurrent_participant_arenas(self):
        source=pool_fixture().replace('while(hierarchyArrived.load()<2)','while(hierarchyArrived.load()<3)')
        run_cpp(source+r'''
int main(){World w;Pathfinder p;Object c,d;c.id=3;d.id=4;c.ai.obj=&c;d.ai.obj=&d;logic.objects[3]=&c;logic.objects[4]=&d;
 Path::prepareMemoryPoolForSearch();PathNode::prepareMemoryPoolForSearch();
 auto jobs=std::make_unique<std::array<PathfindParallelJob,4>>();std::array<std::unique_ptr<PathfindSearchContext>,3> arenas;
 for(auto&arena:arenas)arena=std::make_unique<PathfindSearchContext>();
 unsigned index=0;for(auto*o:{&w.a,&w.b,&c,&d}){auto&job=(*jobs)[index++];job.obj=o;job.id=o->id;job.locomotor=&o->ai.locomotor;
  job.from=o->ai.from;job.to=o->ai.to;job.ignored=0;job.tunneling=false;job.completeCorridor=mainPathfindSearchContext().m_corridor;
  job.permanent=PathfindSearchContext::permanentRecordsInUse();job.fixed=s_useFixedPathfinding;
  int radius;bool center;p.getRadiusAndCenter(o,radius,center);const bool human=o->player.type!=PLAYER_COMPUTER;
  job.settings=p.captureMovementSettings(o,*job.locomotor,radius,center,human);
 }
 hierarchyRendezvous=true;JoinedSearchPool pool(2);
 pool.run(4,[&](unsigned job,unsigned participant){(*jobs)[job].executionParticipant=participant;p.executeCompletePath((*jobs)[job],*arenas[participant]);});
 hierarchyRendezvous=false;assert(hierarchyArrived>=4);unsigned total=0,busy=0;
 for(unsigned i=0;i<3;++i){total+=pool.completedBy(i);assert(pool.completedBy(i)>0);busy+=pool.completedBy(i)>1;PathfindParallelJob::resetArena(*arenas[i]);}
 assert(total==4&&busy==1);
 for(auto&job:*jobs){assert(job.complete&&job.completedPath&&job.completeState.charged>0&&job.reads.queries.size()>0);
  assert(job.completedPath->getFirstNode()&&job.completedPath->getFirstNode()->getNextOptimized());job.reset();}
 assert(liveEngineObjects==0);
}
''',timeout=45)

    def test_poisoned_arenas_do_not_change_primary_or_fallback_publication(self):
        run_cpp(pool_fixture()+r'''
int main(){for(bool fallback:{false,true}){World w;Pathfinder p;w.queue(p);
 if(fallback)for(int x=8;x<=10;++x)for(int y=8;y<=10;++y)if(x!=9||y!=9)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();auto&batch=*p.m_parallelBatch;const auto expected=batch.jobs[0].completeState;
 const auto corridor=batch.jobs[0].completeCorridor;
 for(auto&arena:batch.arenas){PathfindParallelJob::resetArena(*arena);arena->m_cumulativeCellsAllocated=999;arena->m_ignoreObstacleID=999;arena->m_corridor.assign(9,0);}
 auto*path=w.consume(p,w.a);auto&main=mainPathfindSearchContext();assert(main.m_cumulativeCellsAllocated==expected.charged);
 assert(main.m_ignoreObstacleID==expected.ignored&&main.m_isTunneling==expected.tunneling);if(expected.corridorWritten)assert(main.m_corridor==corridor);
 if(fallback){assert(!path);const auto closest=batch.jobs[0].fallback->completeState;
  path=p.findClosestPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to,false,0,false);
  assert(path&&batch.fallbackAccepted==1&&main.m_cumulativeCellsAllocated==expected.charged+closest.charged);
 }else assert(path);
 delete path;p.clearParallelBatch();assert(liveEngineObjects==0);
}}
''',timeout=30)

    def test_unstarted_lifecycle_cancelled_jobs_are_not_ready(self):
        source=pool_fixture()
        source='bool cancelBeforeRun=true;\n'+source
        source=source.replace('batch.pool.run(selectedCount,','if(cancelBeforeRun){PathOccupancy::setValidationPaused(true);cancelBeforeRun=false;}batch.pool.run(selectedCount,',1)
        run_cpp(source+r'''
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();auto&batch=*p.m_parallelBatch;
 assert(batch.pool.cancelled()&&batch.poolSkipped==2&&batch.primarySearches==0&&liveEngineObjects==0);
 for(const auto&job:batch.jobs)assert(!job.ready&&!job.complete);
 PathOccupancy::setValidationPaused(false);p.prepareParallelBatch();assert(!batch.pool.cancelled());
 delete w.consume(p,w.a);delete w.consume(p,w.b);assert(batch.accepted==2);p.clearParallelBatch();assert(liveEngineObjects==0);
}
''')

    def test_lifecycle_change_during_capture_never_starts_pool_callbacks(self):
        source=pool_fixture()
        source=source.replace('struct Object;struct Pathfinder;','struct Object;struct Pathfinder;std::function<void(Object*)>captureHook;')
        source=source.replace('f=from;t=to;i=ignored;','if(captureHook)captureHook(obj);f=from;t=to;i=ignored;',1)
        run_cpp(source+r'''
int main(){World w;Pathfinder p;w.queue(p);captureHook=[&](Object*o){if(o==&w.b)++PathOccupancy::validationLifecycleEpoch();};
 p.prepareParallelBatch();assert(p.m_parallelBatch&&!p.m_parallelBatch->active&&p.m_parallelBatch->poolBatches==0&&p.m_lookaheadWindow.empty());
 assert(liveEngineObjects==0);for(const auto&arena:p.m_parallelBatch->arenas)assert(arena->m_recordIndex.bytes()==0);
 captureHook={};p.prepareParallelBatch();assert(p.m_parallelBatch->poolBatches==1);
 delete w.consume(p,w.a);delete w.consume(p,w.b);p.clearParallelBatch();assert(liveEngineObjects==0);
}
''')

    def test_pool_errors_join_and_discard_every_owned_path(self):
        for thrown,disabled in [('ERROR_OUT_OF_MEMORY',True),('ERROR_BUG',False)]:
            source=pool_fixture().replace('auto& job=batch.jobs[index];','auto& job=batch.jobs[index];if(index==0)throw '+thrown+';',1)
            run_cpp(source+r'''
int main(){World w;Pathfinder p;w.queue(p);bool caught=false;
 try{p.prepareParallelBatch();}catch(ErrorCode e){caught=e==ERROR_BUG;}
 assert(caught==CATCHES&&p.m_exclusiveWorkerUnavailable==DISABLED&&p.m_lookaheadWindow.empty()&&!p.m_parallelBatch->active&&liveEngineObjects==0);
 for(const auto&arena:p.m_parallelBatch->arenas)assert(!arena->m_ownership.owner.load()&&!arena->m_parallelReads&&!arena->m_completeJob);
}
'''.replace('CATCHES',str(not disabled).lower()).replace('DISABLED',str(disabled).lower()))

    def test_physical_metrics_and_logical_slots_remain_distinct(self):
        run_cpp(pool_fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();auto&batch=*p.m_parallelBatch;auto&timing=p.m_pathTiming;
 unsigned caller=0,worker=0;
 for(unsigned i=0;i<2;++i){auto participant=batch.jobs[i].executionParticipant;
  assert(timing.slowPairs()[0].tasks[i].participant==participant);if(participant)++worker;else ++caller;}
 assert(timing[PathSearchTiming::CallerKernel].calls==caller&&timing[PathSearchTiming::WorkerKernel].calls==worker);
 assert(batch.poolJobs[0]+batch.poolJobs[1]==2);
 FILE*f=std::tmpfile();timing.report(f);std::rewind(f);char buffer[1024];std::string text;while(std::fgets(buffer,sizeof buffer,f))text+=buffer;std::fclose(f);
 assert(text.find("[PATH_POOL_TASK] pair=1 slot=0 participant=")!=std::string::npos);
 p.clearParallelBatch();assert(liveEngineObjects==0);
}
''')

    def test_timing_and_cache_off_keep_serial_equivalence(self):
        self.assertEqual('serial_equivalence\n',run_cpp(look.queue_fixture(timing=False,cached=False)+look.QUEUE_MATRIX,timeout=60).stdout)


def suite():
    look.lookahead_fixture=pool_fixture
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
    return unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(ParticipantPathPoolTests),
                              unittest.TestSuite(look.PathLookaheadTests(name) for name in names)])


if __name__=='__main__':
    if '--tsan' in sys.argv:run_cpp=partial(run_cpp,extra_flags=('-fsanitize=thread','-g','-O1'))
    if '--asan' in sys.argv:run_cpp=partial(run_cpp,extra_flags=('-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-O1'))
    look.run_cpp=run_cpp
    result=unittest.TextTestRunner().run(suite())
    sys.exit(not result.wasSuccessful())
