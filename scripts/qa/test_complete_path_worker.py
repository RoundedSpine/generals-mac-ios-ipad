#!/usr/bin/env python3
"""Exercise complete joined search APIs with production hierarchy, Paths and optimization.

World/object/terrain and allocation services are controlled fixtures, not the full engine.
Use --tsan for the same executed production paths under ThreadSanitizer.
"""
# GeneralsX @test Codex 29/10/2026 Verify whole-request execution, ordered transfer and rejection before repeated main preparation.
import re
import sys
import unittest
from functools import partial
from compiled_harness import run_cpp
from test_path_movement_inputs import function, block, HEADER, SOURCE
from test_parallel_path_batch import fixture


def complete_fixture(enabled=True, timing=True):
    source=fixture(timing)
    source='struct PathfindParallelJob;\n'+source
    if enabled:source='#define GENERALS_ZH_COMPLETE_PATH_WORKER 1\n'+source
    source=source.replace('struct Coord3D {Real x=0,y=0,z=0;};',r'''
struct Coord2D {Real x=0,y=0;Real length()const{return std::sqrt(x*x+y*y);}};
struct Coord3D {Real x=0,y=0,z=0;void zero(){x=y=z=0;}};
using UnsignedByte=unsigned char;
struct Xfer;
std::atomic<int> liveEngineObjects{0},allocationCountdown{-1};
std::array<std::atomic<unsigned>,2> hierarchyCalls{},buildCalls{},optimizationCalls{};
std::atomic<bool> abortBuild{false},abortCleanup{false},hierarchyRendezvous{false};std::atomic<unsigned> hierarchyArrived{0},optimizationQueries{0};
enum ErrorCode {ERROR_OUT_OF_MEMORY=1,ERROR_BUG=2};
int engineLock=0;int*TheMemoryPoolCriticalSection=&engineLock;int*TheDmaCriticalSection=&engineLock;
struct MemoryPoolObject {MemoryPoolObject(){++liveEngineObjects;}virtual~MemoryPoolObject(){--liveEngineObjects;}};
template<class T>T*allocateEngineValue(){
 const auto remaining=allocationCountdown.load();
 if(remaining>=0 && allocationCountdown.fetch_sub(1)==0)throw ERROR_OUT_OF_MEMORY;
 return new T;
}
#define newInstance(T) allocateEngineValue<T>()
#define MEMORY_POOL_GLUE_WITH_USERLOOKUP_CREATE(T,name) public: virtual~T(); static void*getClassMemoryPool(){assert(!ExclusiveSearchWorker::onWorker());static int pool=0;return &pool;}
''')
    # Use actual class fields/accessors; omit unrelated snapshot virtuals that this fixture does not link.
    a=HEADER.index('class PathNode :');b=HEADER.index('//----------------------------------------------------------------------------------------------------------',HEADER.index('class Path :',a))
    paths=HEADER[a:b]
    paths=paths.replace('public MemoryPoolObject, public Snapshot','public MemoryPoolObject')
    paths=re.sub(r'\s*virtual void (?:crc|xfer|loadPostProcess)\([^;]*;', '', paths)
    source=source.replace('struct Path {std::vector<ICoord2D> route;bool blocked=false,requestedBlocked=false;};',paths)
    source=source.replace('std::map<ObjectID,Path> results;','')
    source=source.replace('Real bias=0;int getLayerForDestination(const Coord3D*){return 1;}',
        'Real bias=0,layerBias=0;int destinationLayer=1;int getLayerForDestination(const Coord3D*p){return p->z>50?3:destinationLayer;} Real getLayerHeight(Real x,Real y,int layer){return getGroundHeight(x,y)+layerBias+(layer==3?100:0);}')
    # The fixture original puts "bias" after a method, without the above prefix's "Real" adjacency in some versions.
    assert 'layerBias' in source
    source=source.replace('const int LAYER_LAST=3,', 'struct PathfindZoneManager {enum {ZONE_BLOCK_SIZE=4,UNINITIALIZED_ZONE=0};};\nconst int LOCOMOTORSURFACE_GROUND=1;float sqr(float n){return n*n;}constexpr float HUGE_DIST=1000000;\nconst int LAYER_LAST=3,')
    source=source.replace('struct PathfindMovementInput;\nstruct Pathfinder {',r'''
struct PathfindMovementInput;
struct AI {Pathfinder*selected=nullptr;Pathfinder*pathfinder(){return selected;}}ai;
AI*TheAI=&ai;
struct Pathfinder {''')
    source=source.replace('int getEffectiveZone(int,bool,int z){return z;}int getEffectiveTerrainZone(int z){return z;}',r'''
  int getEffectiveZone(int,bool,int z){return z;}int getEffectiveTerrainZone(int z){return z;}
  int getBlockZone(int,bool,int x,int y,PathfindCell**map)const{return map[x][y].getZone();}
  bool interactsWithBridge(int,int)const{return true;}
  void getExtent(ICoord2D&extent)const{extent={3,3};}
  void setPassable(int x,int y,bool passable){if(x<0||x>=12||y<0||y>=12)return;activePathfindSearchContext().setCorridorPassable(unsigned(x/4)*3+y/4,passable);}
''')
    source=source.replace('struct Layer {PathfindCell*getCell(int,int){return nullptr;}}',r'''struct Layer {
 bool enabled=false;PathfindCell cells[12][12];ICoord2D start{2,5},end{8,5};
 PathfindCell*getCell(int x,int y){return enabled&&y==5&&x>=2&&x<=8?&cells[x][y]:nullptr;}
 bool isUnused()const{return !enabled;}bool isDestroyed()const{return false;}
 void getStartCellIndex(ICoord2D*p){*p=start;}void getEndCellIndex(ICoord2D*p){*p=end;}int getZone()const{return 1;}
}''')
    # Replace the simplified line walker with both actual Bresenham overloads.
    source=source.replace('using Callback=int(*)(Pathfinder*,PathfindCell*,PathfindCell*,int,int,void*);','using Callback=int(*)(Pathfinder*,PathfindCell*,PathfindCell*,int,int,void*);using CellAlongLineProc=Callback;')
    start=source.index(' void iterateCellsAlongLine(ICoord2D start,')
    end=source.index('\n static int examineCellsCallback',start)
    source=source[:start]+''' int iterateCellsAlongLine(const ICoord2D&,const ICoord2D&,int,Callback,void*);
 int iterateCellsAlongLine(const Coord3D&,const Coord3D&,int,Callback,void*);'''+source[end:]
    start=source.index(' bool clientSafeQuickDoesPathExist(')
    end=source.index(' PathfindParallelJob*takeParallelResult(',start)
    source=source[:start]+r'''
 bool clientSafeQuickDoesPathExist(const LocomotorSet&,const Coord3D*,const Coord3D*);
 Path*findPathWithInputs(Object*,const LocomotorSet&,const Coord3D*,const Coord3D*);
 Path*findHierarchicalPath(Bool,const LocomotorSet&,const Coord3D*,const Coord3D*,Bool);
 Path*internal_findHierarchicalPath(Bool,const LocomotorSurfaceTypeMask,const Coord3D*,const Coord3D*,Bool,Bool);
 Path*buildHierarchicalPath(const Coord3D*,PathfindCell*);
 void processHierarchicalCell(const ICoord2D&,const ICoord2D&,PathfindCell*,PathfindCell*,zoneStorageType,zoneStorageType*,Int&,Bool,Int&);
 bool validMovementPosition(bool crusher,int layer,const LocomotorSet&locomotor,const Coord3D*position){
  return validMovementPosition(crusher,locomotor.getValidSurfaces(),getCell(layer,position));
 }
#ifdef GENERALS_ZH_COMPLETE_PATH_WORKER
 bool takeCompletePath(const Object*,const LocomotorSet&,const Coord3D&,const Coord3D&,const Coord3D*,Real,const PathfindClosestSettings*,Path*&,Coord3D* =nullptr);
 void executeCompletePath(PathfindParallelJob&);
 int searchDestinationLayer(const Coord3D*);Real searchLayerHeight(Real,Real,int);void observeParallelObject(ObjectID);
#endif
 bool isLinePassable(const Object*,int,int,const Coord3D&,const Coord3D&,bool,bool);
 static int linePassableCallback(Pathfinder*,PathfindCell*,PathfindCell*,int,int,void*);
 void prependCells(Path*,const Coord3D*,PathfindCell*,bool);
 template<class Sink>void prependRouteCells(Sink*,const Coord3D*,PathfindCell*,bool);
'''+source[end:]
    start=source.index(' void adjustCoordToCell(int x,')
    end=source.index(' static void pathXY(',start)
    source=source[:start]+' void adjustCoordToCell(int,int,bool,Coord3D&,int);\n'+source[end:]
    # Remove both fake engine Path construction and the fake closest hierarchy implementation.
    start=source.index('Path*Pathfinder::buildActualPath(')
    end=source.index('struct World {',start)
    source=source[:start]+source[end:]
    start=source.index('void Pathfinder::checkChangeLayers(PathfindCell*cell)')
    end=source.index('struct World {',start)
    source=source[:start]+function('void Pathfinder::checkChangeLayers(')+'\n'+source[end:]
    # Consume the actual ordinary outer API, where complete reuse precedes hierarchy.
    source=source.replace('return p.internalFindPath(&o,','return p.findPathWithInputs(&o,')
    source=source.replace('else p->internalFindPath(obj,','else p->findPathWithInputs(obj,')
    source=source.replace('Pathfinder::Pathfinder(){','Pathfinder::Pathfinder(){ai.selected=this;')
    cleanup=function('void Pathfinder::cleanOpenAndClosedLists()')
    injected=cleanup.replace('{','''{
#ifdef GENERALS_ZH_COMPLETE_PATH_WORKER
 if(abortCleanup.load()&&activePathfindSearchContext().m_completeJob&&activePathfindSearchContext().m_completeJob->outcome.found)
  throw PathfindSearchContext::SpeculativeRecovery{};
#endif''',1)
    source=source.replace(cleanup,injected,1)
    # Full helpers must be declared/defined before the production validator observes them.
    helpers='\n'.join(function(m) for m in [
        'static std::array<unsigned,6> completePathObjectValues(', 'void Pathfinder::observeParallelObject(',
        'PathfindLayerEnum Pathfinder::searchDestinationLayer(', 'Real Pathfinder::searchLayerHeight(',
        'void Pathfinder::executeCompletePath(', 'Bool Pathfinder::takeCompletePath(',
    ])
    marker='PathfindParallelJob* Pathfinder::takeParallelResult('
    source=source.replace(marker,'\n#ifdef GENERALS_ZH_COMPLETE_PATH_WORKER\n'+helpers+'\n#endif\n'+marker,1)
    methods=['PathNode::PathNode()', 'PathNode::~PathNode()', 'void PathNode::setNextOptimized(',
             'PathNode *PathNode::prependToList(', 'PathNode *PathNode::appendToList(', 'Path::Path()', 'Path::~Path()',
             'void Path::prependNode(', 'void Path::appendNode(', 'void Path::optimize(',
             'Path *Pathfinder::findHierarchicalPath(', 'Path *Pathfinder::findClosestHierarchicalPath(',
             'Path *Pathfinder::internal_findHierarchicalPath(', 'void Pathfinder::processHierarchicalCell(',
             'Path *Pathfinder::buildHierarchicalPath(', 'Path *Pathfinder::buildActualPath(',
             'void Pathfinder::adjustCoordToCell(', 'void Pathfinder::prependCells(',
             'void Pathfinder::prependRouteCells(', 'Bool Pathfinder::clientSafeQuickDoesPathExist(',
             'Bool Pathfinder::isLinePassable(', '/*static*/ Int Pathfinder::linePassableCallback(',
             'Int Pathfinder::iterateCellsAlongLine( const Coord3D&', 'Int Pathfinder::iterateCellsAlongLine( const ICoord2D &']
    source+='\n'+block(SOURCE,'struct LinePassableStruct\n')+'\n'
    for marker in methods:
        assert marker in SOURCE,marker
        method=function(marker)
        if marker.startswith('void Pathfinder::prependRouteCells'):method='template<class RouteSink>\n'+method
        if marker.startswith('Path *Pathfinder::findHierarchicalPath') or marker.startswith('Path *Pathfinder::findClosestHierarchicalPath'):
            method=method.replace('{','{++hierarchyCalls[ExclusiveSearchWorker::onWorker()?1:0];if(hierarchyRendezvous.load()&&activePathfindSearchContext().m_parallelReads){++hierarchyArrived;while(hierarchyArrived.load()<2)std::this_thread::yield();}',1)
        if marker.startswith('Path *Pathfinder::buildActualPath'):
            method=method.replace('{','{++buildCalls[ExclusiveSearchWorker::onWorker()?1:0];',1)
        if marker.startswith('void Path::optimize('):
            method=method.replace('{','{++optimizationCalls[ExclusiveSearchWorker::onWorker()?1:0];auto*optReads=activePathfindSearchContext().m_parallelReads;unsigned optBefore=optReads?optReads->queries.observations():0;if(abortBuild.load())throw PathfindSearchContext::SpeculativeRecovery{};',1)
            method=method.replace('m_isOptimized = true;','m_isOptimized = true;if(optReads)optimizationQueries+=optReads->queries.observations()-optBefore;')
        if marker.startswith('Bool Pathfinder::clientSafeQuickDoesPathExist('):
            method=method.replace('{','{if(!quickAllowed)return false;',1)
        source+='\n'+method
    return source


class CompletePathWorkerTests(unittest.TestCase):
    def test_complete_paths_execute_and_transfer_before_preparation(self):
        run_cpp(complete_fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();
 assert(p.m_parallelBatch&&p.m_parallelBatch->batches==1);
 assert(hierarchyCalls[1]>0&&buildCalls[1]>0&&optimizationCalls[1]>0);
 const auto h=hierarchyCalls[0].load()+hierarchyCalls[1].load();
 const auto b=buildCalls[0].load()+buildCalls[1].load();
 auto*a=w.consume(p,w.a);auto*c=w.consume(p,w.b);assert(a&&c&&p.m_parallelBatch->accepted==2);
 assert(h==hierarchyCalls[0]+hierarchyCalls[1]&&b==buildCalls[0]+buildCalls[1]);
 assert(a->getFirstNode()&&a->getFirstNode()->getNextOptimized());
 delete a;delete c;p.clearParallelBatch();assert(liveEngineObjects==0);
}
''',timeout=30)

    def test_complete_hierarchy_participants_overlap(self):
        run_cpp(complete_fixture()+r"""
int main(){World w;Pathfinder p;w.queue(p);hierarchyRendezvous=true;p.prepareParallelBatch();
 assert(hierarchyArrived>=2&&p.m_parallelBatch->batches==1&&optimizationQueries>0);
 assert(p.m_parallelBatch->jobs[0].requestAdmission.observed());
 assert(p.m_parallelBatch->jobs[1].requestAdmission.observed());
 p.clearParallelBatch();assert(liveEngineObjects==0);
}
""",timeout=30)

    def test_complete_routes_optimized_links_destinations_and_budget_match_serial(self):
        cases=r"""
void show(Path*path){printf("P %d ",path!=nullptr);if(!path)return;
 for(auto*n=path->getFirstNode();n;n=n->getNext()){
  const auto&pos=*n->getPosition();Coord2D dir;float distance;auto*next=n->getNextOptimized(&dir,&distance);
  int index=-1,j=0;for(auto*it=path->getFirstNode();it;it=it->getNext(),++j)if(it==next)index=j;
  printf("%.6f,%.6f,%.6f,%d,%d,%d,%.6f,%.6f,%.6f;",pos.x,pos.y,pos.z,n->getLayer(),n->getCanOptimize(),index,dir.x,dir.y,distance);
 }printf("blocked=%d ",path->getBlockedByAlly());}
int main(){for(bool fixed:{false,true})for(bool center:{false,true})for(int radius:{0,1})for(int kind=0;kind<5;++kind)for(int seed=0;seed<3;++seed){
 World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;p.testCenter=center;p.testRadius=radius;
 w.a.ai.safe=kind==1;w.b.ai.closest=kind==2;w.b.ai.blocked=seed&1;
 w.a.ai.repulsor1=w.a.ai.from;w.a.ai.repulsor2=w.a.ai.from;p.quickAllowed=kind!=3;
 for(int x=0;x<12;++x)for(int y=0;y<12;++y)if((x*31+y*17+seed*13)%11==0)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.storage[2][2].setType(PathfindCell::CELL_CLEAR);p.storage[2][8].setType(PathfindCell::CELL_CLEAR);
 p.storage[9][9].setType(kind==4?PathfindCell::CELL_OBSTACLE:PathfindCell::CELL_CLEAR);
 mainPathfindSearchContext().m_cumulativeCellsAllocated=0;
 PREPARE_BATCH
 for(auto*obj:{&w.a,&w.b}){
  auto*path=w.consume(p,*obj);
  if(!path&&!obj->ai.safe&&!obj->ai.closest){
   p.confirmParallelFallback(obj,obj->ai.locomotor,obj->ai.from,obj->ai.to,false);
   path=p.findClosestPath(obj,obj->ai.locomotor,&obj->ai.from,&obj->ai.to,false,0,false);
  }
  printf("%d:%d:%d:%d:%d:%u ",fixed,center,radius,kind,seed,obj->id);show(path);
  auto&c=mainPathfindSearchContext();printf("B %d T %d I %u D %.6f,%.6f,%.6f C ",c.m_cumulativeCellsAllocated,c.m_isTunneling,c.m_ignoreObstacleID,obj->ai.to.x,obj->ai.to.y,obj->ai.to.z);
  for(auto pass:c.m_corridor)printf("%u",unsigned(pass));puts("");delete path;
 }
 p.clearParallelBatch();assert(liveEngineObjects==0);
}}
"""
        serial=run_cpp(complete_fixture(False)+cases.replace('PREPARE_BATCH',''),timeout=60).stdout
        parallel=run_cpp(complete_fixture()+cases.replace('PREPARE_BATCH','p.prepareParallelBatch();'),timeout=60).stdout
        self.assertEqual(serial,parallel)

    def test_complete_terrain_object_policy_and_lifecycle_changes_reject(self):
        run_cpp(complete_fixture()+r"""
int main(){for(int change=0;change<13;++change){World w;Pathfinder p;w.queue(p);
 terrain.bias=terrain.layerBias=0;terrain.destinationLayer=1;
 if(change==6){w.b.ai.closest=true;w.a.ai.ignored=w.b.ai.ignored=w.a.id;mainPathfindSearchContext().m_ignoreObstacleID=w.a.id;}
 p.prepareParallelBatch();auto*first=w.consume(p,w.a);delete first;assert(p.m_parallelBatch->accepted==1);
 switch(change){
 case 0:terrain.layerBias=3;break;case 1:terrain.destinationLayer=2;break;
 case 2:w.b.ai.through=true;break;case 3:p.testRadius=1;break;case 4:w.b.player.type=PLAYER_COMPUTER;break;
 case 5:++p.m_parallelWorldEpoch;break;case 6:w.a.ai.from.x+=1;break;
 case 7:PathOccupancy::validationLifecycleEpoch().fetch_add(1);break;
 case 8:p.storage[7][3].setGoalUnit(17,{7,3});break;
 case 9:w.b.ai.to.x-=10;break;case 10:s_useFixedPathfinding=!s_useFixedPathfinding;break;
 case 11:mainPathfindSearchContext().m_ignoreObstacleID=99;break;
 case 12:p.m_parallelBatch->jobs[1].reads.overflow=true;break;
 }
 auto*second=w.consume(p,w.b);delete second;
 // A changed cell away from every observed route is allowed; all other changes must reject.
 if(change!=8)assert(p.m_parallelBatch->rejected==1);
 assert(!p.m_parallelBatch->jobs[1].completedPath);
 p.storage[7][3].setGoalUnit(0,{7,3});p.clearParallelBatch();assert(liveEngineObjects==0);
 terrain.bias=terrain.layerBias=0;terrain.destinationLayer=1;s_useFixedPathfinding=true;
}}
""",timeout=45)

    def test_complete_early_null_preserves_unwritten_corridor_then_reuses_fallback(self):
        run_cpp(complete_fixture()+r"""
int main(){World w;Pathfinder p;w.queue(p);p.quickAllowed=false;p.prepareParallelBatch();
 auto&c=mainPathfindSearchContext();c.setCorridorPassable(0,false);const auto before=c.m_corridor;
 assert(!w.consume(p,w.a));assert(c.m_corridor==before&&c.m_cumulativeCellsAllocated==0);
 assert(p.m_parallelBatch->accepted==1&&p.m_parallelBatch->jobs[0].fallbackAllowed);
 p.confirmParallelFallback(&w.a,w.a.ai.locomotor,w.a.ai.from,w.a.ai.to,false);
 auto*path=p.findClosestPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to,false,0,false);
 assert(path&&p.m_parallelBatch->fallbackAccepted==1);delete path;
 p.clearParallelBatch();assert(liveEngineObjects==0);
}
""",timeout=30)

    def test_complete_partial_paths_are_owned_through_recovery_and_pooled_failure(self):
        run_cpp(complete_fixture()+r"""
int main(){for(int failure=0;failure<18;++failure){World w;Pathfinder p;w.queue(p);
 allocationCountdown=failure;p.prepareParallelBatch();allocationCountdown=-1;
 assert(!p.m_parallelBatch || !p.m_parallelBatch->active);assert(p.m_exclusiveWorkerUnavailable);
 assert(liveEngineObjects==0);auto*path=w.consume(p,w.a);assert(path);delete path;
 }
 {World w;Pathfinder p;w.queue(p);abortBuild=true;p.prepareParallelBatch();abortBuild=false;
  assert(!p.m_parallelBatch->active&&!p.m_exclusiveWorkerUnavailable&&liveEngineObjects==0);
  assert(!s_forceCleanCells);auto*path=w.consume(p,w.a);assert(path);delete path;
 }
 assert(liveEngineObjects==0);
}
""",timeout=45)

    def test_complete_timing_disabled_and_missing_pool_locks_use_caller(self):
        run_cpp(complete_fixture(timing=False)+r"""
int main(){World w;Pathfinder p;w.queue(p);TheMemoryPoolCriticalSection=nullptr;p.prepareParallelBatch();
 assert(!p.m_parallelBatch);TheMemoryPoolCriticalSection=&engineLock;p.prepareParallelBatch();
 assert(p.m_parallelBatch->batches==1);auto*a=w.consume(p,w.a);auto*b=w.consume(p,w.b);assert(a&&b);delete a;delete b;
 p.clearParallelBatch();assert(liveEngineObjects==0);
}
""",timeout=30)

    def test_complete_paths_outlive_discarded_contexts_and_transfer_only_once(self):
        run_cpp(complete_fixture()+r"""
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();
 auto*owned=p.m_parallelBatch->jobs[0].completedPath.get();auto*path=w.consume(p,w.a);assert(path==owned);
 assert(p.m_parallelBatch->jobs[0].used&&!p.m_parallelBatch->jobs[0].completedPath);
 auto*again=w.consume(p,w.a);assert(again&&again!=path);delete again;
 p.clearParallelBatch();assert(liveEngineObjects>0);
 unsigned count=0;for(auto*n=path->getFirstNode();n;n=n->getNext())++count;assert(count>1);
 delete path;assert(liveEngineObjects==0);
}
""",timeout=30)

    def test_complete_admission_records_coarse_decisions_across_generation_changes(self):
        run_cpp(complete_fixture()+r"""
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();auto&job=p.m_parallelBatch->jobs[1];
 assert(job.requestAdmission.observed()&&job.requestAdmission.valid());
 assert(job.requestAdmission.matches(job.permanent,job.permanent));
 assert(!job.requestAdmission.matches(job.permanent,PATHFIND_RECORD_CAPACITY));
 // A now-impossible reached admission must reject before transferring the completed Path.
 auto*path=w.consume(p,w.a);delete path;
 PathfindCell occupied;std::vector<PathfindCellInfo*>permanent;
 for(unsigned i=0;i<PATHFIND_RECORD_CAPACITY;++i){auto*r=PathfindCellInfo::getACellInfo(&occupied,{0,0});if(r)permanent.push_back(r);}
 path=w.consume(p,w.b);assert(p.m_parallelBatch->rejected==1&&!job.completedPath);delete path;
 for(auto*r:permanent)PathfindCellInfo::releaseACellInfo(r);
 p.clearParallelBatch();assert(liveEngineObjects==0);
}
""",timeout=30)

    def test_complete_bridge_layers_and_cliff_optimization_match_serial(self):
        cases=r"""
int main(){for(bool fixed:{false,true})for(bool bridgeCase:{false,true}){
 World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;
 if(bridgeCase){auto&bridge=p.m_layers[3];bridge.enabled=true;
  for(int x=0;x<12;++x){PathfindCell::registerSearchCells(bridge.cells[x],12);
   for(int y=0;y<12;++y){bridge.cells[x][y].setLayer(3);bridge.cells[x][y].setZone(1);}}
  bridge.cells[2][5].setConnectLayer(LAYER_GROUND);bridge.cells[8][5].setConnectLayer(LAYER_GROUND);
  p.storage[2][5].setConnectLayer(3);p.storage[8][5].setConnectLayer(3);
  w.a.layer=3;w.a.ai.from={55,55,100};w.b.ai.from={95,95,0};w.b.ai.to={55,55,100};
 }else{
  for(int x=0;x<12;++x)for(int y=0;y<12;++y)if(x!=y&&x!=y+1)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
  p.storage[5][5].setType(PathfindCell::CELL_CLIFF);p.storage[6][5].setType(PathfindCell::CELL_CLIFF);
  w.b.ai.from={35,35,0};w.b.ai.to={85,85,0};
 }
 PREPARE_BATCH
 for(auto*obj:{&w.a,&w.b}){auto*path=w.consume(p,*obj);assert(path);unsigned bridgeNodes=0,unoptimized=0;
  printf("%d:%d:%u ",fixed,bridgeCase,obj->id);
  for(auto*n=path->getFirstNode();n;n=n->getNext()){
   if(n->getLayer()==3)++bridgeNodes;if(n!=path->getFirstNode()&&!n->getCanOptimize())++unoptimized;
   const auto&pos=*n->getPosition();auto*next=n->getNextOptimized();
   printf("%.3f,%.3f,%.3f,%d,%d,%.3f,%.3f;",pos.x,pos.y,pos.z,n->getLayer(),n->getCanOptimize(),next?next->getPosition()->x:-1,next?next->getPosition()->y:-1);
  }
  if(bridgeCase)assert(bridgeNodes>0);else assert(unoptimized>0);
  printf("B %d\n",mainPathfindSearchContext().m_cumulativeCellsAllocated);delete path;
 }
 p.clearParallelBatch();assert(liveEngineObjects==0);
}}
"""
        before=run_cpp(complete_fixture(False)+cases.replace('PREPARE_BATCH',''),timeout=45).stdout
        after=run_cpp(complete_fixture()+cases.replace('PREPARE_BATCH','p.prepareParallelBatch();'),timeout=45).stdout
        self.assertEqual(before,after)

    def test_complete_recovery_after_path_construction_releases_the_owned_result(self):
        run_cpp(complete_fixture()+r"""
int main(){World w;Pathfinder p;w.queue(p);abortCleanup=true;p.prepareParallelBatch();abortCleanup=false;
 assert(buildCalls[0]+buildCalls[1]>0&&optimizationCalls[0]+optimizationCalls[1]>0);
 assert(!p.m_parallelBatch->active&&!p.m_exclusiveWorkerUnavailable&&liveEngineObjects==0);
 assert(!s_forceCleanCells);auto*path=w.consume(p,w.a);assert(path);delete path;
 assert(liveEngineObjects==0);
}
""",timeout=30)


if __name__=='__main__':
    if '--tsan' in sys.argv:
        sys.argv.remove('--tsan')
        run_cpp=partial(run_cpp,extra_flags=('-fsanitize=thread','-g','-O1'))
    unittest.main()
