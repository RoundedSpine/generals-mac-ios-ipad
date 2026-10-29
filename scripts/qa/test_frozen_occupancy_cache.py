#!/usr/bin/env python3
"""Test frozen-request occupancy reuse; --benchmark compares complete API work on controlled routes."""
# GeneralsX @performance Codex 30/10/2026 Keep live main validation and all route, budget and lifetime semantics with optional memoization.
import json
import sys
import unittest
from functools import partial
from compiled_harness import run_cpp
from test_complete_path_worker import complete_fixture


def cached_fixture(timing=True):
    return '#define GENERALS_ZH_FROZEN_OCCUPANCY_CACHE 1\n'+complete_fixture(timing=timing)


class FrozenOccupancyCacheTests(unittest.TestCase):
    def test_collision_full_conflict_and_generation_lookup_never_hide_invalid_logs(self):
        run_cpp(r'''
#include "boundedobservationlog.h"
#include <cassert>
struct Value{unsigned key,value;};
struct Key{std::array<unsigned,1>operator()(const Value&v)const{return {{v.key}};}};
struct Same{bool operator()(const Value&a,const Value&b)const{return a.value==b.value;}};
struct Hash{template<class T>unsigned operator()(const T&)const{return 0;}};
int main(){BoundedObservationLog<Value,2,Key,Same,Hash,unsigned char> log;
 for(unsigned generation=0;generation<260;++generation){
  log.clear();assert(!log.find({1,0}));log.observe({1,generation});log.observe({2,17});
  assert(log.find({1,0})->value==generation&&log.find({2,0})->value==17&&!log.find({3,0}));
  assert(log.observations()==2);
  if(generation%2){assert(!log.observe({1,999}));assert(log.conflict());}
  else{assert(!log.observe({3,0}));assert(log.full());}
  assert(!log.find({1,0})&&!log.find({2,0}));
 }
}
''')

    def test_complete_routes_optimized_links_destinations_and_budgets_match_without_cache(self):
        cases=r'''
int main(){for(bool fixed:{false,true})for(bool center:{false,true})for(int radius:{0,1})for(int kind=0;kind<4;++kind)for(bool maze:{false,true}){
 World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;p.testCenter=center;p.testRadius=radius;
 if(maze){for(auto*o:{&w.a,&w.b}){o->ai.from={15,15,0};o->ai.to={105,105,0};}
  for(int x:{3,5,7,9})for(int y=0;y<12;++y)if(y!=((x==3||x==7)?10:1))p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 }
 w.a.ai.safe=w.b.ai.safe=kind==1;w.a.ai.closest=w.b.ai.closest=kind==2;if(kind==3)p.quickAllowed=false;
 p.prepareParallelBatch();
 for(auto*o:{&w.a,&w.b}){p.m_queuePRHead=o->id-1;Path*path=nullptr;
  if(kind==3){assert(!w.consume(p,*o));p.confirmParallelFallback(o,o->ai.locomotor,o->ai.from,o->ai.to,false);
   path=p.findClosestPath(o,o->ai.locomotor,&o->ai.from,&o->ai.to,false,0,false);
  }else path=w.consume(p,*o);
  printf("%d%d%d%d%d:%d ",fixed,center,radius,kind,maze,path!=nullptr);
  if(path)for(auto*n=path->getFirstNode();n;n=n->getNext()){
   const auto*pos=n->getPosition();auto*opt=n->getNextOptimized();
   printf("%.4f,%.4f,%.4f:%d:%d:",pos->x,pos->y,pos->z,n->getLayer(),n->getCanOptimize());
   if(opt)printf("%.4f,%.4f;",opt->getPosition()->x,opt->getPosition()->y);else printf("null;");
  }
  printf(" D%.3f,%.3f B%d\n",o->ai.to.x,o->ai.to.y,mainPathfindSearchContext().m_cumulativeCellsAllocated);delete path;
 }
 p.clearParallelBatch();assert(liveEngineObjects==0);
}}
'''
        baseline=run_cpp(complete_fixture()+cases,timeout=45).stdout
        self.assertEqual(baseline,run_cpp(cached_fixture()+cases,timeout=45).stdout)
        self.assertEqual(baseline,run_cpp(cached_fixture(False)+cases,timeout=45).stdout)

    def test_main_replays_changed_occupancy_and_cache_resets_per_request(self):
        run_cpp(cached_fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.storage[5][5].setPosUnit(w.a.id,{5,5});
 p.prepareParallelBatch();auto&job=p.m_parallelBatch->jobs[1];assert(job.reads.cacheHits>0);
 const auto liveCalls=job.reads.queryProfile.calls;assert(liveCalls==job.reads.queries.observations());
 assert(p.m_pathTiming.slowPairs()[0].tasks[1].primaryReads.cacheHits==job.reads.cacheHits);
 auto*first=w.consume(p,w.a);delete first;w.b.relation=ALLIES;
 bool changed=false;for(const auto&q:job.reads.queries){LiveOccupancyReader live={&p,&w.b};
  if(!(PathOccupancy::evaluate(q.input,live)==q.result))changed=true;}
 assert(changed);auto*second=w.consume(p,w.b);delete second;
 assert(p.m_pathTiming.rejections(false,PathSearchTiming::Rejection::Occupancy)==1);
 p.clearParallelBatch();assert(!job.reads.cacheHits&&!job.reads.queryProfile.calls&&liveEngineObjects==0);
 p.storage[5][5].setPosUnit(0,{5,5});
}
''',timeout=30)

    def test_unbound_or_different_mover_queries_still_evaluate_live(self):
        run_cpp(cached_fixture()+r'''
int main(){World w;Pathfinder p;PathfindParallelJob job;job.obj=&w.a;job.context.m_parallelReads=&job.reads;
 PathOccupancy::Input input;input.destination=true;input.center=true;input.x=5;input.y=5;input.layer=1;
 {SearchContextBinding<PathfindSearchContext> binding(job.context);
  assert(p.evaluateOccupancyQuery(&w.a,input).allowed);assert(p.evaluateOccupancyQuery(&w.a,input).allowed);
  assert(!job.reads.cacheHits&&job.reads.queryProfile.calls==2);
  job.context.m_completeExecuting=true;job.context.m_completeJob=&job;
  assert(p.evaluateOccupancyQuery(&w.a,input).allowed);assert(job.reads.cacheHits==1);
  p.storage[5][5].setGoalUnit(w.a.id,{5,5});w.b.relation=ALLIES;
  assert(!p.evaluateOccupancyQuery(&w.b,input).allowed);assert(job.reads.cacheHits==1&&job.reads.queries.conflict());
  job.context.m_completeExecuting=false;job.context.m_completeJob=nullptr;
 }
 p.storage[5][5].setGoalUnit(0,{5,5});job.reset();assert(!job.reads.cacheHits);
}
''',timeout=30)


def benchmark():
    cases=r'''
int main(){for(bool maze:{false,true}){World w;Pathfinder p;w.queue(p);
 for(auto*o:{&w.a,&w.b}){o->ai.from={15,15,0};o->ai.to={105,105,0};}
 if(maze)for(int x:{3,5,7,9})for(int y=0;y<12;++y)if(y!=((x==3||x==7)?10:1))p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 for(unsigned repeat=0;repeat<10;++repeat){unsigned long long evaluations=0,hits=0;
  const auto start=std::chrono::steady_clock::now();
  for(unsigned request=0;request<200;++request){p.m_queuePRHead=0;mainPathfindSearchContext().m_cumulativeCellsAllocated=0;
   p.prepareParallelBatch();for(const auto&job:p.m_parallelBatch->jobs){evaluations+=job.reads.queryProfile.calls;hits+=job.reads.cacheHits;}
   auto*a=w.consume(p,w.a);auto*b=w.consume(p,w.b);assert(a&&b);delete a;delete b;p.clearParallelBatch();
  }
  const auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
  if(repeat)printf("%d %lld %llu %llu\n",maze,static_cast<long long>(ns),evaluations,hits);
 }
 assert(liveEngineObjects==0);
}}
'''
    variants=[('baseline',complete_fixture()),('cache',cached_fixture())]
    if '--reverse' in sys.argv:variants.reverse()
    for name,fixture in variants:
        rows=run_cpp(fixture+cases,extra_flags=('-O2',),timeout=60).stdout.splitlines()
        for maze in [0,1]:
            values=[list(map(int,row.split())) for row in rows if int(row.split()[0])==maze]
            times=sorted(row[1]/1000000 for row in values)
            print(json.dumps({'case':name,'maze':bool(maze),'pairs':200,'median_ms':times[len(times)//2],
                              'range_ms':[times[0],times[-1]],'evaluations':values[0][2],'hits':values[0][3]}))


if __name__=='__main__':
    if '--benchmark' in sys.argv:
        benchmark()
    else:
        if '--tsan' in sys.argv:
            sys.argv.remove('--tsan');run_cpp=partial(run_cpp,extra_flags=('-fsanitize=thread','-g','-O1'))
        unittest.main()
