#!/usr/bin/env python3
"""Exercise shared participant arenas with independently owned completed results and validation logs."""
# GeneralsX @performance Codex 30/10/2026 Replay complete/cache suites under arena reuse and verify publication across overwritten scratch.
import sys
import unittest
from functools import partial
from compiled_harness import run_cpp
import test_complete_path_worker as complete
import test_frozen_occupancy_cache as cache

_original_complete_fixture=complete.complete_fixture


def base_fixture(reuse=True,cached=True,timing=True):
    return ('#define GENERALS_ZH_REUSE_PATH_CONTEXTS 1\n' if reuse else '')+(
        '#define GENERALS_ZH_FROZEN_OCCUPANCY_CACHE 1\n' if cached else '')+_original_complete_fixture(timing=timing)


def reused_fixture(enabled=True,timing=True):
    return ('#define GENERALS_ZH_REUSE_PATH_CONTEXTS 1\n' if enabled else '')+_original_complete_fixture(enabled,timing)


class ReusedPathContextTests(unittest.TestCase):
    def test_two_distinct_participant_arenas_are_retained_across_request_kinds(self):
        run_cpp(base_fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();auto&b=*p.m_parallelBatch;
 auto*first=&b.jobs[0].context;auto*second=&b.jobs[1].context;assert(first!=second);
 for(unsigned repeat=0;repeat<24;++repeat){
  if(repeat){p.m_queuePRHead=0;p.quickAllowed=repeat%4!=3;
   w.a.ai.safe=w.b.ai.safe=repeat%4==1;w.a.ai.closest=w.b.ai.closest=repeat%4==2;p.prepareParallelBatch();}
  assert(&b.jobs[0].context==first&&&b.jobs[1].context==second);
  for(auto&job:b.jobs){assert(job.ownedContext&&job.complete);
   assert(job.fallback&&!job.fallback->ownedContext&&&job.fallback->context==&job.context);
   assert(&job.reads!=&job.fallback->reads&&&job.requestAdmission!=&job.fallback->requestAdmission);
  }
  for(auto*o:{&w.a,&w.b}){auto*path=w.consume(p,*o);delete path;
   if(repeat%4==3){auto*fallback=p.findClosestPath(o,o->ai.locomotor,&o->ai.from,&o->ai.to,false,0,false);delete fallback;}}
  p.clearParallelBatch();assert(liveEngineObjects==0);
  for(auto&job:b.jobs)assert(!job.context.m_parallelReads&&!job.context.m_completeJob&&!job.context.m_privateTiming);
 }
}
''',timeout=45)

    def test_completed_outputs_survive_overwritten_arenas_and_borrowed_reset(self):
        run_cpp(base_fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();auto&b=*p.m_parallelBatch;
 auto&job=b.jobs[0];const auto expected=job.completeState;const auto corridor=job.completeCorridor;
 const auto queryCount=job.reads.queries.size();
 const auto generation=job.context.generation();
 job.fallback->reset();assert(job.context.generation()==generation);
 for(auto&j:b.jobs){j.context.beginSearch();j.context.m_cumulativeCellsAllocated=999;
  j.context.m_isTunneling=!j.completeState.tunneling;j.context.m_ignoreObstacleID=999;
  j.context.m_corridor.assign(j.completeCorridor.size(),0);}
 assert(job.reads.queries.size()==queryCount);
 auto*path=w.consume(p,w.a);assert(path&&b.accepted==1);auto&main=mainPathfindSearchContext();
 assert(main.m_cumulativeCellsAllocated==expected.charged&&main.m_isTunneling==expected.tunneling&&main.m_ignoreObstacleID==expected.ignored);
 if(expected.corridorWritten)assert(main.m_corridor==corridor);
 assert(path->getFirstNode()&&path->getFirstNode()->getNextOptimized());delete path;
 path=w.consume(p,w.b);assert(path&&b.accepted==2);delete path;p.clearParallelBatch();assert(liveEngineObjects==0);
}
''',timeout=30)

    def test_failed_primary_and_fallback_keep_separate_charges_logs_and_corridors(self):
        run_cpp(base_fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);
 for(int x=8;x<=10;++x)for(int y=8;y<=10;++y)if(x!=9||y!=9)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();auto&primary=p.m_parallelBatch->jobs[0];auto&fallback=*primary.fallback;
 assert(primary.complete&&!primary.completedPath&&primary.outcome.cellsExamined>0);
 assert(fallback.ready&&fallback.completedPath&&&primary.context==&fallback.context);
 const auto a=primary.completeState,b=fallback.completeState;
 const auto aCorridor=primary.completeCorridor,bCorridor=fallback.completeCorridor;
 assert(a.charged>0&&b.charged>0&&a.began&&b.began);
 assert(primary.reads.queryProfile.calls&&fallback.reads.queryProfile.calls);
 primary.context.beginSearch();primary.context.m_cumulativeCellsAllocated=123456;primary.context.m_ignoreObstacleID=999;
 primary.context.m_corridor.assign(primary.context.m_corridor.size(),0);
 assert(!w.consume(p,w.a));auto&main=mainPathfindSearchContext();assert(main.m_cumulativeCellsAllocated==a.charged);
 if(a.corridorWritten)assert(main.m_corridor==aCorridor);
 auto*path=p.findClosestPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to,false,0,false);
 assert(path&&p.m_parallelBatch->fallbackAccepted==1&&main.m_cumulativeCellsAllocated==a.charged+b.charged);
 if(b.corridorWritten)assert(main.m_corridor==bCorridor);
 delete path;p.clearParallelBatch();assert(liveEngineObjects==0);
}
''',timeout=30)

    def test_reuse_matches_separate_arenas_for_paths_publication_and_accounting(self):
        cases=r'''
int main(){for(bool fixed:{false,true})for(bool center:{false,true})for(int radius:{0,1})for(int kind=0;kind<4;++kind)for(int layout=0;layout<3;++layout){
 World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;p.testCenter=center;p.testRadius=radius;
 if(layout==1){for(auto*o:{&w.a,&w.b}){o->ai.from={15,15,0};o->ai.to={105,105,0};}
  for(int x:{3,5,7,9})for(int y=0;y<12;++y)if(y!=((x==3||x==7)?10:1))p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);}
 if(layout==2)for(int x=8;x<=10;++x)for(int y=8;y<=10;++y)if(x!=9||y!=9)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 w.a.ai.safe=w.b.ai.safe=kind==1;w.a.ai.closest=w.b.ai.closest=kind==2;p.quickAllowed=kind!=3;
 p.prepareParallelBatch();
 for(auto*o:{&w.a,&w.b}){auto*path=w.consume(p,*o);if(kind==3){assert(!path);path=p.findClosestPath(o,o->ai.locomotor,&o->ai.from,&o->ai.to,false,0,false);}
  printf("%d%d%d%d%d:%d ",fixed,center,radius,kind,layout,path!=nullptr);
  if(path)for(auto*n=path->getFirstNode();n;n=n->getNext()){
   auto*pos=n->getPosition();auto*opt=n->getNextOptimized();printf("%.4f,%.4f,%.4f:%d:%d:",pos->x,pos->y,pos->z,n->getLayer(),n->getCanOptimize());
   if(opt)printf("%.4f,%.4f;",opt->getPosition()->x,opt->getPosition()->y);else printf("null;");}
  auto&main=mainPathfindSearchContext();printf(" D%.4f,%.4f B%d T%d I%d C",o->ai.to.x,o->ai.to.y,main.m_cumulativeCellsAllocated,main.m_isTunneling,int(main.m_ignoreObstacleID));
  for(auto block:main.m_corridor)printf("%d",int(block));puts("");delete path;
 }
 p.clearParallelBatch();assert(liveEngineObjects==0);
}}
'''
        for cached in [False,True]:
            self.assertEqual(run_cpp(base_fixture(False,cached)+cases,timeout=60).stdout,
                             run_cpp(base_fixture(True,cached)+cases,timeout=60).stdout)


def suite():
    # Apply reuse to the existing production fixtures rather than duplicating or weakening their assertions.
    complete.complete_fixture=reused_fixture
    cache.complete_fixture=reused_fixture
    return unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(complete.CompletePathWorkerTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(cache.FrozenOccupancyCacheTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(ReusedPathContextTests),
    ])


if __name__=='__main__':
    if '--tsan' in sys.argv:
        run_cpp=partial(run_cpp,extra_flags=('-fsanitize=thread','-g','-O1'))
        complete.run_cpp=run_cpp;cache.run_cpp=run_cpp
    result=unittest.TextTestRunner().run(suite())
    sys.exit(not result.wasSuccessful())
