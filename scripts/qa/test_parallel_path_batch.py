#!/usr/bin/env python3
"""Compile real cells, two-task dispatch, ordinary/escape/closest searches and ordered consumption with a controlled world."""
# GeneralsX @feature Codex 27/10/2026 Verify independent routes and rejection of stale speculative searches.
import sys
import unittest
import hashlib
from functools import partial
from compiled_harness import ROOT, run_cpp
from test_path_movement_inputs import function, block, HEADER, SOURCE
from test_search_record_pool import engine_fixture


def fixture(timing=True):
    # Use production cells, lists, record pool and TLS ownership, rather than sharing fake cell scratch.
    source = ('#define GENERALS_ZH_PATH_TIMING 1\n' if timing else '') + '#include "pathsearchtiming.h"\n#define GENERALS_ZH_PARALLEL_PATH_BATCH 1\nstruct PathfindParallelReads;\n' + engine_fixture()
    source += r'''
#include "exclusivesearchworker.h"
#include "occupancyvalidationworker.h"
#include "boundedsearchreads.h"
#include <array>
#include <memory>
#include <map>
#include <string>
#include <atomic>
#include <algorithm>
#include <cfloat>
#define deleteInstance(pointer) delete (pointer)
#ifdef __clang__
// Match cmake/compilers.cmake's floating-point contraction policy, including optimized sanitizer fixtures.
#pragma clang fp contract(off)
#endif
#define GENERALS_ZH_EXCLUSIVE_PATH_WORKER 1
#define GENERALS_ZH_OCCUPANCY_WORKER 1
#define REAL_TO_INT(v) int(v)
using Real=float;using LocomotorSurfaceTypeMask=int;
struct Coord3D {Real x=0,y=0,z=0;};
struct IRegion2D {ICoord2D lo{0,0},hi{11,11};};
const int LAYER_WALL=2,PLAYER_COMPUTER=2,KINDOF_DOZER=1,KINDOF_VEHICLE=2,ENEMIES=3,ALLIES=4,KINDOF_INFANTRY=5,TEST_CRUSH_OR_SQUISH=0;
const int LAYER_LAST=3,ZONE_BLOCK_SIZE=4,PATHFIND_QUEUE_LEN=512,PATHFIND_CELL_SIZE=10,MAX_SAFE_PATH_CELL_COUNT=2000;
const Real PATHFIND_CELL_SIZE_F=10;
const Real COST_TO_DISTANCE_FACTOR_SQR=(1.0f/10.0f)*(1.0f/10.0f);
int IABS(int n){return n<0?-n:n;}
const int KINDOF_FS_AIRFIELD=99;
struct Player{int type=1;int getPlayerType()const{return type;}};
struct LocomotorSet {int surfaces=1;bool downhill=false;
 int getValidSurfaces()const{return surfaces;}bool isDownhillOnly()const{return downhill;}};
struct Object;struct Pathfinder;
struct AIUpdateInterface {
 void doPathfind(Pathfinder*);
 Object* obj=nullptr;LocomotorSet locomotor;Coord3D from{25,25,0},to{95,95,0};ObjectID ignored=0;
 bool eligible=true,through=false,idle=true;
 bool existingPath=false;
 const void*getPath()const{return existingPath?&existingPath:nullptr;}
 bool safe=false;Coord3D repulsor1{25,25,0},repulsor2{25,25,0};Real repulsorRadius=60;
 bool closest=false,blocked=false;Real pathCostMultiplier=.2f;
 ObjectID getIgnoredObstacleID()const{return ignored;}bool isAircraftThatAdjustsDestination()const{return false;}bool isIdle()const{return idle;}
 PathPredictionReason rejectedPrediction=PathPredictionReason::Quick;
 bool predictOrdinaryPath(Coord3D&f,Coord3D&t,ObjectID&i,PathPredictionReason*reason=nullptr){
  f=from;t=to;i=ignored;const bool accepted=eligible&&!safe&&!closest;
  if(reason)*reason=accepted?PathPredictionReason::Accepted:rejectedPrediction;return accepted;
 }
 bool predictSafePath(Coord3D&f,Coord3D&r1,Coord3D&r2,Real&r){f=from;r1=repulsor1;r2=repulsor2;r=repulsorRadius;return eligible&&safe;}
 bool predictClosestPath(Coord3D&f,Coord3D&t,Bool&b,Real&cost){f=from;t=to;b=blocked;cost=pathCostMultiplier;return eligible&&!safe&&closest;}
 const LocomotorSet&getLocomotorSet()const{return locomotor;}
 bool canPathThroughUnits()const{return through;}
};
struct Object {
 ObjectID id=0;int layer=1,crusher=0,kind=2,relation=ENEMIES;bool hasAI=true,crush=false;Player player;AIUpdateInterface ai;
 const Player*getControllingPlayer()const{return &player;}
 AIUpdateInterface*getAIUpdateInterface()const{return hasAI?const_cast<AIUpdateInterface*>(&ai):nullptr;}
 int getLayer()const{return layer;}int getCrusherLevel()const{return crusher;}
 bool isKindOf(int k)const{return kind==k;}int getRelationship(Object*)const{return relation;}
 AIUpdateInterface*getAI()const{return getAIUpdateInterface();}
 bool canCrushOrSquish(Object*,int)const{return crush;}
 ObjectID getID()const{return id;}
 const Coord3D*getPosition()const{return &ai.from;}
};
struct Logic {std::map<ObjectID,Object*> objects;Object*findObjectByID(ObjectID id){auto i=objects.find(id);return i==objects.end()?nullptr:i->second;}}logic;
Logic*TheGameLogic=&logic;
struct Region3D {Coord3D lo{0,0,0},hi{120,120,0};};
struct Terrain {void getExtent(Region3D*r){*r=Region3D{};}Real bias=0;int getLayerForDestination(const Coord3D*){return 1;}
 Real getGroundHeight(Real x,Real y){return x*.03f+y*.02f+bias;}}terrain;
Terrain*TheTerrainLogic=&terrain;
struct Global {int m_debugAI=0;}global;Global*TheGlobalData=&global;
const int AI_DEBUG_PATHS=1,NAMEKEY_INVALID=0;
struct NameKeyGenerator {bool present=true;int findExistingNameKey(const char*)const{assert(!ExclusiveSearchWorker::onWorker());return present?1:0;}}keys;
NameKeyGenerator*TheNameKeyGenerator=&keys;
struct Path {std::vector<ICoord2D> route;bool blocked=false,requestedBlocked=false;};
struct TCheckMovementInfo {ICoord2D cell;int layer,radius,acceptableSurfaces;bool centerInCell,considerTransient;
 bool enemyFixed=false,allyMoving=false,allyGoal=false;int allyFixedCount=0;};
struct PathfindParallelBatch;struct PathfindParallelJob;
''' + block(HEADER, 'struct PathfindMovementSettings {') + block(HEADER,'struct PathfindClosestSettings {') + r'''
struct PathfindMovementInput;
struct Pathfinder {
 enum {NO_ATTACK=0};
 struct OrdinarySearchOutcome {PathfindCell* lastCell;Int cellsExamined;Bool found;};
 struct ClosestSearchOutcome {PathfindCell*lastCell;PathfindCell*closestCell;Int cellsExamined;Bool reachedGoal;};
 PathfindExclusiveWorker* m_exclusiveWorker=nullptr;bool m_exclusiveWorkerUnavailable=false;
 PathfindParallelBatch* m_parallelBatch=nullptr;unsigned long long m_parallelWorldEpoch=0;
#ifdef GENERALS_ZH_PATH_TIMING
 PathSearchTiming m_pathTiming;
#endif
 std::thread::id owner=std::this_thread::get_id();bool m_isMapReady=true;
 IRegion2D m_extent,m_logicalExtent;
 PathfindCell storage[12][12];PathfindCell* m_map[12];
 struct Layer {PathfindCell*getCell(int,int){return nullptr;}}m_layers[4];
 struct Zones {
  bool needToCalculateZones(){return false;}template<class... A>void calculateZones(A&&...){}
  void setAllPassable(){auto&c=activePathfindSearchContext();for(std::size_t i=0;i<c.m_corridor.size();++i)c.setCorridorPassable(i,true);}
  void clearPassableFlags(){auto&c=activePathfindSearchContext();for(std::size_t i=0;i<c.m_corridor.size();++i)c.setCorridorPassable(i,false);}
  int getEffectiveZone(int,bool,int z){return z;}int getEffectiveTerrainZone(int z){return z;}
  bool isPassable(int x,int y){auto block=std::size_t(x/4)*3+y/4;auto&c=activePathfindSearchContext();
   bool result=c.corridorPassable(block);observeParallelCorridor(block,result);return result;}
 }m_zoneManager;
 ObjectID m_queuedPathfindRequests[512]{};int m_queuePRHead=0,m_queuePRTail=2;
 std::atomic<int> workerLoops{0},callerLoops{0};bool rendezvous=false;
 std::atomic<int> workerFallbackLoops{0},callerFallbackLoops{0},fallbackArrived{0};bool fallbackRendezvous=false;
 std::vector<ICoord2D> serialExpansion;
 std::atomic<int> arrived{0};
 std::map<ObjectID,Path> results;
 Pathfinder();~Pathfinder();
 PRODUCTION_SEARCH_STATE_ACCESSOR
 int testRadius=0;bool testCenter=true;
 void getRadiusAndCenter(const Object*,int&r,bool&c){r=testRadius;c=testCenter;}
 void clip(Coord3D*,Coord3D*){}
 void worldToCell(const Coord3D*p,ICoord2D*c){*c={int(p->x/10),int(p->y/10)};}
 PathfindCell*getCell(int,int,int);
 PathfindCell*getCell(int l,const Coord3D*p){return getCell(l,int(p->x/10),int(p->y/10));}
 PathfindCell*getClippedCell(int l,const Coord3D*p){return getCell(l,p);}
 void observeParallelCell(PathfindCell*);
 Real searchGroundHeight(Real,Real);
 void processPathfindQueue();unsigned m_occupancySamplesRemaining=0;
 void prepareParallelBatch();void clearParallelBatch();
 void confirmParallelFallback(const Object*,const LocomotorSet&,const Coord3D&,const Coord3D&,Bool);
 bool quickAllowed=true;int ordinaryHierarchicalCalls=0;
 bool clientSafeQuickDoesPathExist(const LocomotorSet&,const Coord3D*,const Coord3D*){assert(std::this_thread::get_id()==owner);return quickAllowed;}
 Path*findPathWithInputs(Object*,const LocomotorSet&,const Coord3D*,const Coord3D*);
 Path*findHierarchicalPath(Bool,const LocomotorSet&,const Coord3D*,const Coord3D*,Bool){
  assert(std::this_thread::get_id()==owner);++ordinaryHierarchicalCalls;searchState().m_cumulativeCellsAllocated+=2;
  m_zoneManager.setAllPassable();return new Path;
 }
 PathfindParallelJob*takeParallelResult(const Object*,const LocomotorSet&,const Coord3D&,const Coord3D&,const Coord3D*,Real,
  PathfindCell*,PathfindCell*,const ICoord2D&,const PathfindMovementSettings&,const PathfindClosestSettings* =nullptr);
 void beginSearchState();void cleanOpenAndClosedLists();
 void forceCleanCells(){++m_parallelWorldEpoch;searchState().m_openList.reset();searchState().m_closedList.reset();activePathfindSearchContext().beginSearch();}
 void debugShowSearch(bool){}
 bool rejectDestinations=false;
 bool checkDestination(const Object*,int,int,int,int,bool);
 bool checkForMovement(const Object*,TCheckMovementInfo&);
 PathOccupancy::Result evaluateOccupancyQuery(const Object*,const PathOccupancy::Input&);
 bool checkCellOutsideExtents(ICoord2D&c){return c.x<0||c.x>11||c.y<0||c.y>11;}
 void checkChangeLayers(PathfindCell*);
 Path*buildActualPath(const Object*,int,const Coord3D*,PathfindCell*,bool,bool);
 PathfindMovementSettings captureMovementSettings(const Object*,const LocomotorSet&,int,bool,bool);
 bool validMovementPosition(bool crusher,int surfaces,PathfindCell*c,PathfindCell*from=nullptr){return c&&(c->getType()!=PathfindCell::CELL_OBSTACLE||crusher)&&(surfaces&1);}
 bool validMovementPosition(bool,int,const PathfindMovementInput&,const Coord3D*);
 using Callback=int(*)(Pathfinder*,PathfindCell*,PathfindCell*,int,int,void*);
 void iterateCellsAlongLine(ICoord2D start,ICoord2D end,int layer,Callback cb,void* data){
  auto*from=getCell(layer,start.x,start.y);int x=start.x,y=start.y;
  while(x!=end.x||y!=end.y){if(x!=end.x)x+=(x<end.x?1:-1);if(y!=end.y)y+=(y<end.y?1:-1);
   auto*to=getCell(layer,x,y);if(cb(this,from,to,x,y,data))break;from=to;}
 }
 static int examineCellsCallback(Pathfinder*,PathfindCell*,PathfindCell*,int,int,void*);
 int examineNeighboringCells(PathfindCell*,PathfindCell*,const LocomotorSet&,bool,bool,int,const ICoord2D&,const Object*,int);
 int examineNeighboringCellsWithMovement(PathfindCell*,PathfindCell*,const PathfindMovementInput&,bool,bool,int,const ICoord2D&,const Object*,int);
 OrdinarySearchOutcome runOrdinarySearchLoop(PathfindCell*,PathfindCell*,const PathfindMovementInput&,bool,bool,int,const ICoord2D&,const Object*);
 OrdinarySearchOutcome runSafeSearchLoop(PathfindCell*,const PathfindMovementInput&,bool,bool,int,const ICoord2D&,const Coord3D&,const Coord3D&,Real);
 Path*findSafePath(const Object*,const LocomotorSet&,const Coord3D*,const Coord3D*,const Coord3D*,Real);
 ClosestSearchOutcome runClosestSearchLoop(PathfindCell*,PathfindCell*,const PathfindMovementInput&,Bool,Bool,Int,const ICoord2D&,const PathfindClosestSettings&);
 Path*findClosestPath(Object*,const LocomotorSet&,const Coord3D*,Coord3D*,Bool,Real,Bool);
 bool hierarchical=true;int hierarchicalCalls=0,restrictCorridor=-1;
 Path*findClosestHierarchicalPath(Bool,const LocomotorSet&,const Coord3D*,const Coord3D*,Bool);
 void adjustCoordToCell(int x,int y,bool center,Coord3D&p,int){pathXY(x,y,center,p);p.z=terrain.getGroundHeight(p.x,p.y);}
 static void pathXY(int x,int y,bool center,Coord3D&p){p.x=center?(float(x)+.5f)*10:(float(x)+.05)*10;p.y=center?(float(y)+.5f)*10:(float(y)+.05)*10;}
 Path*internalFindPath(Object*,const LocomotorSet&,const Coord3D*,const Coord3D*);
};
''' + block(SOURCE, 'struct PathfindExclusiveWorker {') + '\n' + block(SOURCE, 'struct PathfindParallelReads {') + '\n' + block(SOURCE, 'struct PathfindParallelJob {') + '\n' + block(SOURCE, 'struct PathfindParallelBatch {')
    # GeneralsX @bugfix Codex 28/10/2026 Compile the production accessor: a broader fixture return type hid the iOS timing build error.
    a=HEADER.index('PathfindSearchBookkeeping& searchState() const {')
    source=source.replace('PRODUCTION_SEARCH_STATE_ACCESSOR',HEADER[a:HEADER.index('\n }',a)+3])
    # Pathfinder needs only a forward declaration before the worker state definition.
    source = source.replace('struct PathfindMovementInput;\nstruct Pathfinder', 'struct PathfindExclusiveWorker;\nvoid observeParallelCorridor(std::size_t,Bool);\nstruct PathfindMovementInput;\nstruct Pathfinder', 1)
    source += '\n' + block(SOURCE, 'struct PathfindMovementInput {') + '\n' + block(SOURCE, 'struct ExamineCellsStruct\n')
    source += '\n'.join(function(m) for m in [
        'void PathfindCell::setType(', 'inline Bool PathfindCell::isObstaclePresent(', 'inline Bool PathfindCell::isObstacleFence(',
        'inline Bool PathfindCell::isObstacleTransparent(', 'inline ObjectID PathfindCell::getObstacleID(',
        'inline PathfindCell *Pathfinder::getCell( PathfindLayerEnum layer, Int x, Int y )',
    ] if not m.startswith('inline PathfindCell *Pathfinder'))
    # getCell is inline in the header.
    a=HEADER.index('inline PathfindCell *Pathfinder::getCell( PathfindLayerEnum layer, Int x, Int y )')
    source += HEADER[a:HEADER.index('\n}',a)+2]
    source += '\n#define PROFILER_PLOT(a,b) ((void)0)\n'
    # Preserve production declaration order: a fixture must not silently predeclare the reader for the validator.
    reader=block(SOURCE,'struct LiveOccupancyReader {')
    validator=function('PathfindParallelJob* Pathfinder::takeParallelResult(')
    source += '\n'.join(part for _,part in sorted([(SOURCE.index('struct LiveOccupancyReader {'),reader),
                                                  (SOURCE.index('PathfindParallelJob* Pathfinder::takeParallelResult('),validator)]))+'\n'
    source += '\n'.join(function(m) for m in [
        'void Pathfinder::processPathfindQueue()', 'void observeParallelCorridor(', 'void Pathfinder::observeParallelCell(', 'Real Pathfinder::searchGroundHeight(',
        'void Pathfinder::clearParallelBatch()', 'void Pathfinder::prepareParallelBatch()',
        'void Pathfinder::confirmParallelFallback(', 'Path *Pathfinder::findPathWithInputs(',
        'void Pathfinder::beginSearchState()', 'void Pathfinder::cleanOpenAndClosedLists()',
        'PathfindMovementSettings Pathfinder::captureMovementSettings(',
        'Bool Pathfinder::validMovementPosition(Bool crusher, PathfindLayerEnum layer,',
        'Bool Pathfinder::checkForMovement(', '/*static*/ Int Pathfinder::examineCellsCallback(', 'Int Pathfinder::examineNeighboringCells(',
        'Int Pathfinder::examineNeighboringCellsWithMovement(',
        'Pathfinder::OrdinarySearchOutcome Pathfinder::runOrdinarySearchLoop(', 'Path *Pathfinder::internalFindPath(',
        'static void pathfindCellXY(', 'Pathfinder::OrdinarySearchOutcome Pathfinder::runSafeSearchLoop(', 'Path *Pathfinder::findSafePath(',
        'Pathfinder::ClosestSearchOutcome Pathfinder::runClosestSearchLoop(', 'Path *Pathfinder::findClosestPath(',
    ])
    source += r'''
std::vector<ObjectID> applied;
void AIUpdateInterface::doPathfind(Pathfinder*p){assert(std::this_thread::get_id()==p->owner);applied.push_back(obj->getID());
 if(safe)p->findSafePath(obj,locomotor,&from,&repulsor1,&repulsor2,repulsorRadius);
 else if(closest)p->findClosestPath(obj,locomotor,&from,&to,blocked,pathCostMultiplier,false);
 else p->internalFindPath(obj,locomotor,&from,&to);}
Pathfinder::Pathfinder(){mainPathfindSearchContext().resizeCorridor(9);
 for(int x=0;x<12;++x){m_map[x]=storage[x];for(int y=0;y<12;++y){storage[x][y].setLayer(1);storage[x][y].setZone(1);}}
}
Pathfinder::~Pathfinder(){clearParallelBatch();delete m_parallelBatch;delete m_exclusiveWorker;mainPathfindSearchContext().releaseStorage();}
PathOccupancy::Result Pathfinder::evaluateOccupancyQuery(const Object*obj,const PathOccupancy::Input&input){
 LiveOccupancyReader live={this,obj};auto result=PathOccupancy::evaluate(input,live);
 if(auto* reads=activePathfindSearchContext().m_parallelReads)reads->query(input,result);
 return result;
}
bool Pathfinder::checkDestination(const Object*obj,int x,int y,int layer,int radius,bool center){
 if(rejectDestinations)return false;
 PathOccupancy::Input input;input.destination=true;input.x=x;input.y=y;input.layer=layer;input.radius=radius;input.center=center;
 return evaluateOccupancyQuery(obj,input).allowed;
}
void Pathfinder::checkChangeLayers(PathfindCell*cell) {
 if(ExclusiveSearchWorker::onWorker())++workerLoops;else ++callerLoops;
 if(m_parallelBatch)for(auto&job:m_parallelBatch->jobs)if(job.fallback && &activePathfindSearchContext()==&job.fallback->context){
  if(ExclusiveSearchWorker::onWorker())++workerFallbackLoops;else ++callerFallbackLoops;
  if(fallbackRendezvous&&cell==job.fallback->start){++fallbackArrived;while(fallbackArrived.load()<2)std::this_thread::yield();}
 }
 if(!activePathfindSearchContext().m_parallelReads)serialExpansion.push_back({cell->getXIndex(),cell->getYIndex()});
 // Both jobs must reach the kernel before either can proceed: catches a silently serialized executor.
 if(rendezvous && activePathfindSearchContext().m_parallelReads && searchState().m_closedList.getHead()==searchState().m_closedList.getTailDummy()){}
}
Path*Pathfinder::buildActualPath(const Object*o,int,const Coord3D*,PathfindCell*c,bool,bool blocked){
 assert(std::this_thread::get_id()==owner);auto&path=results[o->getID()];path=Path{};
 path.requestedBlocked=blocked;
 for(;c;c=c->getParentCell()){path.route.push_back({c->getXIndex(),c->getYIndex()});path.blocked|=c->isBlockedByAlly();}
 return &path;
}
Path*Pathfinder::findClosestHierarchicalPath(Bool,const LocomotorSet&,const Coord3D*,const Coord3D*,Bool){
 assert(std::this_thread::get_id()==owner&&(!m_parallelBatch||!m_parallelBatch->preparing));
 ++hierarchicalCalls;searchState().m_isTunneling=false;searchState().m_cumulativeCellsAllocated+=2;
 if(!hierarchical)return nullptr;
 m_zoneManager.setAllPassable();if(restrictCorridor>=0)activePathfindSearchContext().setCorridorPassable(restrictCorridor,false);
 return new Path;
}
struct World {
 Object a,b;
 World(){PathfindCellInfo::allocateCellInfos();a.id=1;b.id=2;a.ai.obj=&a;b.ai.obj=&b;
  a.ai.from={25,25,0};a.ai.to={95,95,0};b.ai.from={25,85,0};b.ai.to={95,25,0};logic.objects={{1,&a},{2,&b}};
  PathOccupancy::validationPaused().store(false);
 }
 ~World(){logic.objects.clear();PathfindCellInfo::releaseCellInfos();}
 void queue(Pathfinder&p){p.m_queuedPathfindRequests[0]=1;p.m_queuedPathfindRequests[1]=2;}
 Path*consume(Pathfinder&p,Object&o){if(p.m_parallelBatch)for(auto&job:p.m_parallelBatch->jobs)if(job.id==o.id)p.m_queuePRHead=job.queueIndex;
  if(o.ai.safe)return p.findSafePath(&o,o.ai.locomotor,&o.ai.from,&o.ai.repulsor1,&o.ai.repulsor2,o.ai.repulsorRadius);
  if(o.ai.closest)return p.findClosestPath(&o,o.ai.locomotor,&o.ai.from,&o.ai.to,o.ai.blocked,o.ai.pathCostMultiplier,false);
  return p.internalFindPath(&o,o.ai.locomotor,&o.ai.from,&o.ai.to);}
};
'''
    source=source.replace('if(rendezvous && activePathfindSearchContext().m_parallelReads && searchState().m_closedList.getHead()==searchState().m_closedList.getTailDummy()){}',
                          'if(rendezvous && activePathfindSearchContext().m_parallelReads){static thread_local PathfindSearchContext*last=nullptr;if(last!=&activePathfindSearchContext()){last=&activePathfindSearchContext();++arrived;while(arrived.load()<2)std::this_thread::yield();}}')
    return source


def safe_route_cases():
    return r'''
int main(){for(bool fixed:{false,true})for(bool center:{false,true})for(int radius:{0,1})for(bool tunneling:{false,true})for(int seed=0;seed<16;++seed){
 World w;Pathfinder p;s_useFixedPathfinding=fixed;p.testCenter=center;p.testRadius=radius;
 w.a.ai.safe=true;w.a.ai.repulsor1={float(25+(seed%3)*10),25,0};w.a.ai.repulsor2={55,55,10};
 w.a.ai.repulsorRadius=seed%4==0?500:60;p.rejectDestinations=seed%7==0;
 for(int x=0;x<12;++x)for(int y=0;y<12;++y)if((x*31+y*17+seed*13)%11==0)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.storage[2][2].setType(PathfindCell::CELL_CLEAR);
 mainPathfindSearchContext().m_isTunneling=tunneling;
 mainPathfindSearchContext().m_cumulativeCellsAllocated=0;
 auto*path=w.consume(p,w.a);
 std::printf("%d:%d:%d:%d:%d:%d R ",fixed,center,radius,tunneling,seed,path!=nullptr);
 if(path)for(auto c:path->route)std::printf("%d,%d;",c.x,c.y);
 std::printf(" E ");for(auto c:p.serialExpansion)std::printf("%d,%d;",c.x,c.y);
 auto&state=mainPathfindSearchContext();
 std::printf(" B %d T %d I %d\n",state.m_cumulativeCellsAllocated,state.m_isTunneling,int(state.m_ignoreObstacleID));
 std::printf(" C %d %d %zu\n",state.m_openList.empty(),state.m_closedList.empty(),state.m_records.size());
 assert(state.m_openList.empty()&&state.m_closedList.empty());
}}
'''


def closest_route_cases():
    return r'''int main(){for(bool fixed:{false,true})for(float cost:{0.f,.2f,1.f})for(bool blocked:{false,true})for(bool hierarchical:{false,true})for(int seed=0;seed<8;++seed){
 World w;Pathfinder p;s_useFixedPathfinding=fixed;p.testCenter=(seed&1)!=0;p.testRadius=(seed>>1)&1;p.hierarchical=hierarchical;
 w.a.ai.closest=true;w.a.ai.blocked=blocked;w.a.ai.pathCostMultiplier=cost;w.a.ai.to.z=123;
 for(int x=0;x<12;++x)for(int y=0;y<12;++y)if((x*31+y*17+seed*13)%11==0)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.storage[2][2].setType(seed==4?PathfindCell::CELL_OBSTACLE:PathfindCell::CELL_CLEAR);
 p.storage[9][9].setType(seed&1?PathfindCell::CELL_OBSTACLE:PathfindCell::CELL_CLEAR);
 if(seed>=6)for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 p.rejectDestinations=seed==7;
 mainPathfindSearchContext().m_cumulativeCellsAllocated=0;
 auto*path=w.consume(p,w.a);auto&state=mainPathfindSearchContext();
 std::printf("%d:%.1f:%d:%d:%d:%d D %.6f,%.6f,%.6f R ",fixed,cost,blocked,hierarchical,seed,path!=nullptr,w.a.ai.to.x,w.a.ai.to.y,w.a.ai.to.z);
 if(path)for(auto c:path->route)std::printf("%d,%d;",c.x,c.y);
 std::printf(" E ");for(auto c:p.serialExpansion)std::printf("%d,%d;",c.x,c.y);
 std::printf(" B %d T %d I %d C %d,%d,%zu H %d\n",state.m_cumulativeCellsAllocated,state.m_isTunneling,int(state.m_ignoreObstacleID),state.m_openList.empty(),state.m_closedList.empty(),state.m_records.size(),p.hierarchicalCalls);
 assert(state.m_openList.empty()&&state.m_closedList.empty());
}}
'''


def large_closest_fixture():
    source=fixture()
    for before,after in [('hi{11,11}','hi{127,127}'),('storage[12][12]','storage[128][128]'),
                         ('m_map[12]','m_map[128]'),('x<12','x<128'),('y<12','y<128'),
                         ('c.x>11','c.x>127'),('c.y>11','c.y>127'),('*3+y/4','*32+y/4'),
                         ('resizeCorridor(9)','resizeCorridor(1024)'),('hi{120,120,0}','hi{1280,1280,0}')]:
        assert before in source,before
        source=source.replace(before,after)
    source='int farPrunes=0,limitPrunes=0;\n'+source
    source=source.replace('if (distSqr > closestDistScreenSqr*4) {',
                          'if (distSqr > closestDistScreenSqr*4) {++farPrunes;if(count>2000)++limitPrunes;')
    source=source.replace('if(rejectDestinations)return false;','if(rejectDestinations||x>22)return false;')
    return source


def large_closest_case():
    return r'''int main(){for(bool fixed:{false,true})for(bool hierarchical:{false,true}){
 World w;Pathfinder p;s_useFixedPathfinding=fixed;p.hierarchical=hierarchical;w.a.ai.closest=true;
 w.a.ai.from={25,645,0};w.a.ai.to={645,645,9};w.a.ai.pathCostMultiplier=0;
 p.storage[64][64].setType(PathfindCell::CELL_OBSTACLE);farPrunes=limitPrunes=0;
 mainPathfindSearchContext().m_cumulativeCellsAllocated=0;
 auto*path=w.consume(p,w.a);assert(path&&farPrunes>0&&limitPrunes>0);
 std::printf("%d:%d F %d L %d B %d D %.1f,%.1f,%.1f R ",fixed,hierarchical,farPrunes,limitPrunes,
  mainPathfindSearchContext().m_cumulativeCellsAllocated,w.a.ai.to.x,w.a.ai.to.y,w.a.ai.to.z);
 for(auto c:path->route)std::printf("%d,%d;",c.x,c.y);
 std::printf(" E ");for(auto c:p.serialExpansion)std::printf("%d,%d;",c.x,c.y);std::puts("");
}}
'''


# GeneralsX @test Codex 28/10/2026 Trace validation reads in both compile modes using actual joined searches and validator guards.
def validation_outcome_fixture(timing=True):
    source=fixture(timing)
    source=source.replace('struct Object {\n ObjectID id=',
                          'std::atomic<unsigned> validationAiReads{0},validationHeightReads{0};\nstruct Object {\n ObjectID id=',1)
    source=source.replace('AIUpdateInterface*getAIUpdateInterface()const{return hasAI?',
                          'AIUpdateInterface*getAIUpdateInterface()const{++validationAiReads;return hasAI?',1)
    return source.replace('Real getGroundHeight(Real x,Real y){return',
                          'Real getGroundHeight(Real x,Real y){++validationHeightReads;return',1)


def validation_outcome_cases():
    return r'''
int main(){using T=PathSearchTiming;using R=T::Rejection;using S=T::Result;
 for(unsigned scenario=0;scenario<unsigned(R::Count);++scenario){World w;Pathfinder p;w.queue(p);
  if(scenario==unsigned(R::Repulsors))w.a.ai.safe=true;
  if(scenario==unsigned(R::ClosestPolicy))w.a.ai.closest=true;
  if(scenario==unsigned(R::FallbackPath))p.quickAllowed=false;
  p.prepareParallelBatch();auto&primary=p.m_parallelBatch->jobs[0];
  bool fallback=scenario==unsigned(R::FallbackPath);
  if(fallback)p.confirmParallelFallback(&w.a,w.a.ai.locomotor,w.a.ai.from,w.a.ai.to,false);
  auto&job=fallback?*primary.fallback:primary;
  auto from=job.from,to=job.to,r2=job.repulsor2;auto radius=job.repulsorRadius;
  auto*start=job.start;auto*goal=job.goal;auto index=job.startIndex;auto settings=job.settings;
  auto closestSettings=job.closestSettings;const auto*closest=job.closest?&closestSettings:nullptr;
  const auto*repulsor=job.safe?&r2:nullptr;
  switch(static_cast<R>(scenario)){
   case R::None:break;case R::Object:job.obj=&w.b;break;case R::Locomotor:job.locomotor=&w.b.ai.locomotor;break;
   case R::From:++from.x;break;case R::To:++to.x;break;case R::Kind:job.safe=true;break;
   case R::Repulsors:++radius;break;case R::ClosestPolicy:closestSettings.goalOnObstacle=!closestSettings.goalOnObstacle;break;
   case R::FallbackPath:w.a.ai.existingPath=true;break;case R::WorldEpoch:++p.m_parallelWorldEpoch;break;
   case R::Lifecycle:PathOccupancy::validationLifecycleEpoch().fetch_add(1);break;
   case R::Paused:PathOccupancy::validationPaused().store(true);break;case R::Admission:++job.permanent;break;
   case R::IgnoredObstacle:++job.ignored;break;case R::Tunneling:job.tunneling=!job.tunneling;break;
   case R::StartCell:start=nullptr;break;case R::GoalCell:goal=nullptr;break;case R::StartIndex:++index.x;break;
   case R::Movement:++settings.radius;break;case R::Overflow:job.reads.overflow=true;break;
   case R::FixedMode:s_useFixedPathfinding=!s_useFixedPathfinding;break;case R::Recovery:s_forceCleanCells=true;break;
   case R::Cells:job.start->setPinched(true);break;
   case R::Corridor:job.reads.corridor.reset();job.reads.corridor.observe(0,true);mainPathfindSearchContext().setCorridorPassable(0,false);break;
   case R::Occupancy:{PathOccupancy::Input input;input.destination=true;input.x=2;input.y=2;input.layer=1;input.center=true;
    LiveOccupancyReader live={&p,&w.a};auto result=PathOccupancy::evaluate(input,live);result.allowed=!result.allowed;
    job.reads.queries.clear();job.reads.query(input,result);break;}
   case R::Height:job.reads.heights={{1,2,9999}};break;
   case R::Count:assert(false);break;
  }
  validationAiReads=validationHeightReads=0;
  auto*result=p.takeParallelResult(&w.a,w.a.ai.locomotor,from,to,repulsor,radius,start,goal,index,settings,closest);
  assert(bool(result)==(scenario==0));assert(job.used);
  if(scenario>0&&scenario<unsigned(R::Occupancy)){
   assert(validationAiReads==(fallback?2u:0u)&&validationHeightReads==0);
  }
  printf("%u %u %u %u %llu %llu\n",scenario,unsigned(result!=nullptr),unsigned(validationAiReads.load()),unsigned(validationHeightReads.load()),
   p.m_parallelBatch->rejected,p.m_parallelBatch->fallbackRejected);
  PathOccupancy::validationPaused().store(false);s_useFixedPathfinding=true;s_forceCleanCells=false;
  p.clearParallelBatch();
#ifdef GENERALS_ZH_PATH_TIMING
  const auto&task=p.m_pathTiming.slowPairs()[0].tasks[0];
  const auto&outcome=fallback?task.fallbackOutcome:task.primaryOutcome;
  assert(outcome.result==(scenario?S::Rejected:S::Unfinished));
  assert(outcome.reason==static_cast<R>(scenario));
  assert(p.m_pathTiming.results(fallback,scenario?S::Rejected:S::Unfinished)==1);
  for(unsigned reason=0;reason<unsigned(R::Count);++reason)
   assert(p.m_pathTiming.rejections(fallback,static_cast<R>(reason))==unsigned(scenario&&scenario==reason));
#endif
 }
}
'''


class ParallelBatchTests(unittest.TestCase):
    # GeneralsX @test Codex 28/10/2026 Outcomes resolve once on main and stay associated with the original retained pair/role/phase.
    def test_result_reuse_rejection_discard_and_reset_accounting(self):
        run_cpp(fixture()+r'''
int main(){using T=PathSearchTiming;using S=T::Result;using R=T::Rejection;
 for(int kind=0;kind<3;++kind)for(int mode=0;mode<3;++mode){World w;Pathfinder p;w.queue(p);
  w.a.ai.safe=w.b.ai.safe=kind==1;w.a.ai.closest=w.b.ai.closest=kind==2;
  w.b.ai.repulsor1=w.b.ai.from;w.b.ai.repulsor2=w.b.ai.from;p.prepareParallelBatch();
  const auto id=p.m_parallelBatch->jobs[0].timingPair;assert(id==1&&p.m_parallelBatch->jobs[1].timingRole==1);
  if(mode==0){assert(w.consume(p,w.a)&&w.consume(p,w.b));}
  if(mode==1){++p.m_parallelWorldEpoch;assert(w.consume(p,w.a));}
  p.clearParallelBatch();p.clearParallelBatch();auto&t=p.m_pathTiming;const auto&pair=t.slowPairs()[0];
  assert(pair.id==id&&pair.tasks[0].primaryOutcome.result==(mode==0?S::Reused:mode==1?S::Rejected:S::Discarded));
  assert(pair.tasks[1].primaryOutcome.result==(mode==0?S::Reused:S::Discarded));
  assert(pair.tasks[0].primaryOutcome.reason==(mode==1?R::WorldEpoch:R::None));
  assert(t.results(false,S::Reused)==unsigned(mode==0?2:0));
  assert(t.results(false,S::Rejected)==unsigned(mode==1));
  assert(t.results(false,S::Discarded)==unsigned(mode==2?2:mode==1?1:0));
  for(const auto&job:p.m_parallelBatch->jobs)assert(!job.timingPair&&job.timingResult==S::NotRun);
 }
}
''')
        run_cpp(fixture().replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')+r'''
int main(){World w;Pathfinder p;w.queue(p);p.processPathfindQueue();using T=PathSearchTiming;using S=T::Result;
 assert(p.m_pathTiming.results(false,S::Reused)==1&&p.m_pathTiming.results(false,S::Discarded)==1);
 assert(p.m_pathTiming.slowPairs()[0].tasks[1].primaryOutcome.result==S::Discarded&&p.m_queuePRHead==1);
}
''')

    def test_result_rejection_reasons_cover_every_validation_group(self):
        run_cpp(validation_outcome_fixture()+validation_outcome_cases())

    def test_result_diagnostics_preserve_validation_query_counts(self):
        self.assertEqual(run_cpp(validation_outcome_fixture(False)+validation_outcome_cases()).stdout,
                         run_cpp(validation_outcome_fixture(True)+validation_outcome_cases()).stdout)

    def test_result_correlation_survives_sorting_and_eviction(self):
        run_cpp(r'''
#include "pathsearchtiming.h"
#include <type_traits>
int main(){using T=PathSearchTiming;using S=T::Result;using R=T::Rejection;T t;
 static_assert(std::is_trivially_copyable<T::PairSample>::value,"snapshots own no live handles");
 for(int ms:{9,4,8,3,7,6}){T::PairSample sample;sample.nanoseconds=ms*1000000;
  sample.tasks[0].primary=sample.tasks[1].primary=true;sample.tasks[1].fallback=true;t[T::Pair].record(sample.nanoseconds);
  const auto id=t.recordPair(sample);assert(id==t[T::Pair].calls);
 }
 assert(t.slowPairs()[0].id==1&&t.slowPairs()[1].id==3&&t.slowPairs()[2].id==5&&t.slowPairs()[3].id==6);
 t.resolveResult(1,1,false,S::Rejected,R::Cells);t.resolveResult(3,0,false,S::Reused,R::None);
 t.resolveResult(2,0,false,S::Reused,R::None); // Evicted work still contributes exactly one terminal aggregate.
 t.resolveResult(1,1,true,S::Discarded,R::None);
 assert(t.results(false,S::Reused)==2&&t.results(false,S::Rejected)==1&&t.results(true,S::Discarded)==1);
 assert(t.rejections(false,R::Cells)==1&&t.slowPairs()[0].tasks[1].primaryOutcome.reason==R::Cells);
 assert(t.slowPairs()[0].tasks[1].fallbackOutcome.result==S::Discarded&&t.slowPairs()[1].tasks[0].primaryOutcome.result==S::Reused);
 assert(t.slowPairs()[2].tasks[0].primaryOutcome.result==S::Pending);
}
''')

    def test_result_fallback_outcomes_and_pair_identity_survive_reuse(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.quickAllowed=false;p.prepareParallelBatch();using T=PathSearchTiming;using S=T::Result;using R=T::Rejection;
 p.confirmParallelFallback(&w.a,w.a.ai.locomotor,w.a.ai.from,w.a.ai.to,false);
 assert(p.findClosestPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to,false,0,false));
 ++p.m_parallelWorldEpoch;p.m_queuePRHead=1;p.confirmParallelFallback(&w.b,w.b.ai.locomotor,w.b.ai.from,w.b.ai.to,false);
 p.findClosestPath(&w.b,w.b.ai.locomotor,&w.b.ai.from,&w.b.ai.to,false,0,false);p.clearParallelBatch();
 auto&t=p.m_pathTiming;auto first=t.slowPairs()[0];assert(first.id==1);
 assert(first.tasks[0].primaryOutcome.result==S::NotRun&&first.tasks[0].fallbackOutcome.result==S::Reused);
 assert(first.tasks[1].fallbackOutcome.result==S::Rejected&&first.tasks[1].fallbackOutcome.reason==R::WorldEpoch);
 assert(t.results(true,S::Reused)==1&&t.results(true,S::Rejected)==1&&t.results(false,S::Reused)==0);
 w.queue(p);p.m_queuePRHead=0;p.prepareParallelBatch();assert(p.m_parallelBatch->jobs[0].fallback->timingPair==2);p.clearParallelBatch();p.clearParallelBatch();
 assert(t.results(true,S::Discarded)==2&&t.results(true,S::Reused)==1&&t.results(true,S::Rejected)==1);
 bool found=false;for(const auto&pair:t.slowPairs())if(pair.id==1){found=true;
  assert(pair.tasks[0].fallbackOutcome.result==S::Reused&&pair.tasks[1].fallbackOutcome.reason==R::WorldEpoch);}
 assert(found);
}
''')

    def test_result_first_failure_priority_and_report_fields(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();using T=PathSearchTiming;using R=T::Rejection;using S=T::Result;
 auto&job=p.m_parallelBatch->jobs[0];++p.m_parallelWorldEpoch;job.reads.overflow=true;s_forceCleanCells=true;
 w.consume(p,w.a);s_forceCleanCells=false;p.clearParallelBatch();
 assert(p.m_pathTiming.rejections(false,R::WorldEpoch)==1&&p.m_pathTiming.rejections(false,R::Overflow)==0);
 assert(p.m_pathTiming.rejections(false,R::Recovery)==0&&p.m_pathTiming.results(false,S::Discarded)==1);
 FILE*f=std::tmpfile();assert(f);p.m_pathTiming.report(f);std::rewind(f);std::string report;char buffer[2048];
 while(std::fgets(buffer,sizeof buffer,f))report+=buffer;std::fclose(f);
 assert(report.find("[PATH_RESULT_OUTCOMES] phase=primary reused=0 rejected=1 discarded=1 validated_unfinished=0")!=std::string::npos);
 assert(report.find("[PATH_RESULT_REJECTIONS] phase=primary")!=std::string::npos);
 assert(report.find("caller_primary_result=rejected caller_primary_reason=world_epoch")!=std::string::npos);
 assert(report.find("worker_primary_result=discarded worker_primary_reason=none")!=std::string::npos);
}
''')

    def test_prediction_reason_preserves_short_circuit_queries(self):
        ai_source=(ROOT/'GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/AIUpdate.cpp').read_text()
        ai_header=(ROOT/'GeneralsMD/Code/GameEngine/Include/GameLogic/Module/AIUpdate.h').read_text()
        a=ai_source.index('Bool AIUpdateInterface::predictOrdinaryPath(')
        predictor=ai_source[a:ai_source.index('\n}',a)+2]
        a=ai_header.index('Bool predictOrdinaryPath(')
        declaration=ai_header[a:ai_header.index(';',a)+1]
        source=r'''
#include "pathsearchprediction.h"
#include <cassert>
#include <initializer_list>
using Bool=bool;using ObjectID=unsigned;
struct Coord3D{float x=0,y=0,z=0;};
struct Region3D{bool isInRegionNoZ(const Coord3D*p)const{return p->x>=0&&p->y>=0&&p->x<=100&&p->y<=100;}};
struct Terrain{void getMaximumPathfindExtent(Region3D*){}}terrain;auto*TheTerrainLogic=&terrain;
constexpr int AI_FOLLOW_EXITPRODUCTION_PATH=3;
struct Object{Coord3D p{10,20,0};const Coord3D*getPosition(){return &p;}};
struct State{int id=0;int getCurrentStateID(){return id;}};
struct AIUpdateInterface {
 bool m_waitingForPath=true,m_isSafePath=false,m_isApproachPath=false,m_isAttackPath=false,m_isBlockedAndStuck=false,m_isFinalGoal=true;
 bool quick=false,through=false;int quickCalls=0,throughCalls=0,objectCalls=0;
 Coord3D m_requestedDestination{80,90,0};Object object;State state;State*m_stateMachine=&state;
 bool canComputeQuickPath(){++quickCalls;return quick;}bool canPathThroughUnits(){++throughCalls;return through;}
 Object*getObject(){++objectCalls;return &object;}unsigned getIgnoredObstacleID(){return 41;}
 DECLARATION
};
'''.replace('DECLARATION',declaration)+predictor+r'''
int main(){using R=PathPredictionReason;
 const R expected[]={R::Accepted,R::NotWaiting,R::Safe,R::Approach,R::Attack,R::Blocked,R::NonFinal,R::Quick,R::ProductionExit,R::OutsideExtent,R::OutsideExtent,R::NotWaiting};
 for(bool explain:{false,true})for(int scenario=0;scenario<12;++scenario){AIUpdateInterface ai;
  switch(scenario){case 1:ai.m_waitingForPath=false;break;case 2:ai.m_isSafePath=true;break;
   case 3:ai.m_isApproachPath=true;break;case 4:ai.m_isAttackPath=true;break;case 5:ai.m_isBlockedAndStuck=true;break;
   case 6:ai.m_isFinalGoal=false;break;case 7:ai.quick=true;break;case 8:ai.state.id=3;ai.through=true;break;
   case 9:ai.m_requestedDestination.x=101;break;case 10:ai.object.p.x=101;break;
   case 11:ai.m_waitingForPath=false;ai.m_isSafePath=ai.m_isAttackPath=ai.quick=true;break;}
  R reason=R::Count;Coord3D from{-9,-9,0},to=from;ObjectID ignored=99;
  const bool accepted=ai.predictOrdinaryPath(from,to,ignored,explain?&reason:nullptr);
  assert(accepted==(scenario==0));assert(reason==(explain?expected[scenario]:R::Count));
  assert(ai.quickCalls==int(scenario==0||(scenario>=7&&scenario<=10))&&ai.throughCalls==int(scenario==8));
  assert(ai.objectCalls==(scenario==0?2:scenario==10?1:0));
  if(accepted)assert(from.x==10&&to.y==90&&ignored==41);else assert(from.x==-9&&to.y==-9&&ignored==99);
 }
}
'''
        run_cpp(source)

    # GeneralsX @feature Codex 28/10/2026 Exercise admission accounting and scalar snapshots through the actual queue and dispatcher.
    def test_admission_outcomes_explain_every_attempt(self):
        run_cpp(fixture()+r'''
int main(){using T=PathSearchTiming;using A=T::Admission;
 const A expected[]={A::Unavailable,A::Debug,A::Paused,A::Nested,A::ShortQueue,A::Duplicate,
  A::MissingObject,A::MissingAI,A::Dozer,A::CrusherKey,A::Prediction,A::Prediction,A::Capture,A::Dispatched};
 for(unsigned scenario=0;scenario<14;++scenario){World w;Pathfinder p;w.queue(p);global.m_debugAI=0;keys.present=true;
  switch(scenario){
   case 0:p.m_exclusiveWorkerUnavailable=true;break;case 1:global.m_debugAI=1;break;
   case 2:PathOccupancy::validationPaused().store(true);break;case 4:p.m_queuePRTail=1;break;
   case 5:p.m_queuedPathfindRequests[1]=1;break;case 6:logic.objects.erase(2);break;
   case 7:w.b.hasAI=false;break;case 8:w.b.kind=KINDOF_DOZER;break;
   case 9:w.b.crusher=1;keys.present=false;break;
   case 10:w.a.ai.eligible=false;w.a.ai.rejectedPrediction=PathPredictionReason::Quick;break;
   case 11:w.b.ai.eligible=false;w.b.ai.rejectedPrediction=PathPredictionReason::NonFinal;break;
   case 12:p.m_isMapReady=false;break;
  }
  if(scenario==3){SearchContextBinding<PathfindSearchContext> outer(activePathfindSearchContext());p.prepareParallelBatch();}
  else p.prepareParallelBatch();
  assert(p.m_pathTiming.admissions(expected[scenario])==1);
  std::uint64_t sum=0;for(unsigned i=0;i<unsigned(A::Count);++i)sum+=p.m_pathTiming.admissions(static_cast<A>(i));assert(sum==1);
  if(scenario==10)assert(p.m_pathTiming.predictions(0,PathPredictionReason::Quick)==1);
  if(scenario==11)assert(p.m_pathTiming.predictions(1,PathPredictionReason::NonFinal)==1);
  if(scenario==12){p.prepareParallelBatch();assert(p.m_pathTiming.admissions(A::ExistingAttempt)==1&&p.m_pathTiming.admissions(A::ExistingPair)==0);}
  if(scenario==13){p.prepareParallelBatch();assert(p.m_pathTiming.admissions(A::ExistingPair)==1&&p.m_pathTiming.admissions(A::Dispatched)==1);}
  global.m_debugAI=0;keys.present=true;PathOccupancy::validationPaused().store(false);
 }
}
''')

    def test_admission_exception_and_debug_outcomes(self):
        main=r'''
int main(){World w;Pathfinder p;w.queue(p);bool caught=false;
 try{p.prepareParallelBatch();}catch(const std::runtime_error&){caught=true;}
 assert(p.m_pathTiming.admissions(EXPECTED)==1&&p.m_pathTiming.slowPairCount()==0);
 assert(!p.m_parallelBatch||!p.m_parallelBatch->active);
 assert(caught==PROPAGATES);
}
'''
        call='m_exclusiveWorker->worker.runPair([&]{execute(1);},[&]{execute(0);});'
        for thrown,expected,propagates in [
            ('throw ExclusiveSearchWorker::EnvironmentError("test");','EnvironmentFailure',False),
            ('throw std::system_error(std::make_error_code(std::errc::resource_unavailable_try_again));','ThreadFailure',False),
            ('throw std::bad_alloc();','AllocationFailure',False),
            ('throw std::runtime_error("test");','Exception',True),
        ]:
            run_cpp(fixture().replace(call,thrown)+main.replace('EXPECTED','PathSearchTiming::Admission::'+expected).replace('PROPAGATES',str(propagates).lower()))
        run_cpp('#define GENERALS_ZH_PATH_TIMING 1\n#define DUMP_PERF_STATS 1\n#include "pathsearchtiming.h"\n#include <cassert>\n'
                'struct Pathfinder {PathSearchTiming m_pathTiming;void prepareParallelBatch();};\n'+function('void Pathfinder::prepareParallelBatch()')+r'''
int main(){Pathfinder p;p.prepareParallelBatch();assert(p.m_pathTiming.admissions(PathSearchTiming::Admission::DebugBuild)==1);}
''')

    def test_slow_samples_retain_four_and_restore_queue_context(self):
        run_cpp(r'''
#include "pathsearchtiming.h"
#include <cassert>
#include <type_traits>
struct Clock {using duration=std::chrono::nanoseconds;using time_point=std::chrono::time_point<Clock>;
 static long long ticks;static int reads;static time_point now(){++reads;return time_point(duration(ticks));}};
long long Clock::ticks=0;int Clock::reads=0;
int main(){using T=BasicPathSearchTiming<Clock>;T t;
 static_assert(std::is_trivially_copyable<T::PairSample>::value&&std::is_trivially_copyable<T::QueueSample>::value,"Snapshots must own only values");
 {T::QueueScope empty(t,0);}assert(Clock::reads==0&&t.slowQueueCount()==0);
 for(int ms:{2,9,4,7,9,1}){T::QueueScope q(t,3);q.sample.completed=true;Clock::ticks+=ms*1000000;}
 assert(t.slowQueueCount()==4);const auto&top=t.slowQueues();
 assert(top[0].id==2&&top[1].id==5&&top[2].id==4&&top[3].id==3);
 T nested;{
  T::QueueScope outer(nested,2);Clock::ticks+=100;
  {T::QueueScope inner(nested,1);T::SerialScope serial(nested,true,T::Kind::Closest);Clock::ticks+=200;}
  T::PairSample pair;{T::Scope timer(&nested[T::Pair]);Clock::ticks+=300;pair.nanoseconds=timer.stop();}
  nested.recordPair(pair);assert(nested.slowPairs()[0].queue==outer.sample.id);
  {T::SerialScope serial(nested,true,T::Kind::Ordinary);Clock::ticks+=400;}
 }
 assert(nested.slowQueueCount()==2&&nested.slowQueues()[0].serialKinds[0]==1&&nested.slowQueues()[1].serialKinds[2]==1);
 for(int ms:{1,8,2,7,8,3}){T::PairSample sample;sample.nanoseconds=ms*1000000;t.recordPair(sample);}
 assert(t.slowPairCount()==4&&t.slowPairs()[0].nanoseconds==8000000&&t.slowPairs()[1].nanoseconds==8000000&&t.slowPairs()[3].nanoseconds==3000000);
}
''')

    def test_slow_queue_and_pair_capture_actual_work_after_join(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.processPathfindQueue();using T=PathSearchTiming;auto&t=p.m_pathTiming;
 assert(t.slowQueueCount()==1&&t.slowPairCount()==1);const auto&q=t.slowQueues()[0];const auto&pair=t.slowPairs()[0];
 assert(q.id==pair.queue&&q.depth==2&&q.entries==2&&q.callbacks==2&&q.completed&&!q.zones);
 assert(q.charged==unsigned(mainPathfindSearchContext().m_cumulativeCellsAllocated));
 assert(q.phaseCalls[T::Pair]==1&&q.phaseCalls[T::Validation]==2&&q.phaseCalls[T::Finalization]==2&&q.phaseCalls[T::SerialKernel]==0);
 for(const auto&task:pair.tasks)assert(task.kind==T::Kind::Ordinary&&task.primary&&!task.fallback&&task.records>0&&task.examined>0);
 assert(!p.m_parallelBatch->active&&p.m_parallelBatch->jobs[0].context.m_records.size()==0);
 assert(t.admissions(T::Admission::Dispatched)==1&&t.admissions(T::Admission::ExistingPair)==1);
 FILE*f=std::tmpfile();assert(f);t.report(f);std::rewind(f);std::string report;char buffer[2048];while(std::fgets(buffer,sizeof buffer,f))report+=buffer;std::fclose(f);
 assert(report.find("[PATH_PAIR_ADMISSION] calls=2 dispatched=1 existing_pair=1")!=std::string::npos);
 assert(report.find("[PATH_QUEUE_SLOW] rank=1 queue=1")!=std::string::npos&&report.find("caller_kind=ordinary caller_primary=1")!=std::string::npos);
}
''')

    def test_slow_fallback_and_mixed_kinds_are_copied(self):
        run_cpp(fixture()+r'''
int main(){using T=PathSearchTiming;for(int kind=0;kind<3;++kind){World w;Pathfinder p;w.queue(p);
 if(kind==0)w.b.ai.safe=true;else if(kind==1)w.a.ai.closest=true;else p.quickAllowed=false;
 p.prepareParallelBatch();assert(p.m_pathTiming.slowPairCount()==1);auto saved=p.m_pathTiming.slowPairs()[0];assert(saved.queue==0);
 if(kind==0)assert(saved.tasks[1].kind==T::Kind::Safe&&saved.tasks[1].primary);
 if(kind==1)assert(saved.tasks[0].kind==T::Kind::Closest&&saved.tasks[0].primary);
 if(kind==2)for(const auto&task:saved.tasks)assert(!task.primary&&task.fallback&&task.fallbackRecords>0);
 p.clearParallelBatch();assert(p.m_pathTiming.slowPairs()[0].tasks[0].records==saved.tasks[0].records);
}}
''')

    def test_slow_queue_records_serial_kinds_and_original_budget_cutoff(self):
        run_cpp(fixture()+r'''
int main(){using T=PathSearchTiming;for(int kind=0;kind<3;++kind){World w;Pathfinder p;w.queue(p);p.m_exclusiveWorkerUnavailable=true;
 w.a.ai.safe=w.b.ai.safe=kind==1;w.a.ai.closest=w.b.ai.closest=kind==2;p.processPathfindQueue();
 const auto&q=p.m_pathTiming.slowQueues()[0];assert(q.serialKinds[kind]==2&&q.phaseCalls[T::SerialKernel]==2&&q.phaseCalls[T::Pair]==0);
}}
''')
        run_cpp(fixture().replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')+r'''
int main(){World w;Pathfinder p;w.queue(p);p.processPathfindQueue();using T=PathSearchTiming;
 const auto first=p.m_pathTiming.slowQueues()[0];assert(first.depth==2&&first.entries==1&&first.callbacks==1&&first.charged>1);
 assert(p.m_parallelBatch->accepted==1&&p.m_parallelBatch->unused==1&&p.m_queuePRHead==1);
 p.processPathfindQueue();assert(p.m_pathTiming.slowQueueCount()==2&&p.m_pathTiming.admissions(T::Admission::ShortQueue)==1);
 bool found=false;for(const auto&q:p.m_pathTiming.slowQueues())if(q.id==2){found=true;assert(q.depth==1&&q.entries==1&&q.serialKinds[0]==1);}assert(found);
}
''')
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;p.m_queuePRHead=511;p.m_queuePRTail=1;p.m_queuedPathfindRequests[511]=1;p.m_queuedPathfindRequests[0]=2;
 p.processPathfindQueue();const auto&q=p.m_pathTiming.slowQueues()[0];
 assert(q.depth==2&&q.entries==2&&q.callbacks==2&&p.m_queuePRHead==1&&p.m_parallelBatch->accepted==2);
}
''')
        run_cpp(fixture().replace('bool needToCalculateZones(){return false;}','bool needToCalculateZones(){return true;}')+r'''
int main(){World w;Pathfinder p;w.queue(p);p.processPathfindQueue();const auto&q=p.m_pathTiming.slowQueues()[0];
 assert(q.depth==2&&q.entries==0&&q.callbacks==0&&q.charged==0&&q.zones&&q.completed&&p.m_queuePRHead==0);
}
''')

    # GeneralsX @feature Codex 28/10/2026 Exercise real timed dispatch/consumption, including work discarded or recomputed.
    def test_phase_timing_scopes_thresholds_and_exception_cleanup(self):
        run_cpp(r'''
#include "pathsearchtiming.h"
#include <cassert>
#include <stdexcept>
#include <string>
struct Clock {
 using duration=std::chrono::nanoseconds;
 using time_point=std::chrono::time_point<Clock>;
 static long long ticks;static int reads;
 static time_point now(){++reads;return time_point(duration(ticks));}
};
long long Clock::ticks=0;int Clock::reads=0;
int main(){using Timing=BasicPathSearchTiming<Clock>;Timing timing;
 {Timing::Scope ignored(nullptr);ignored.stop();}assert(Clock::reads==0);
 auto&metric=timing[Timing::Preparation];
 {Timing::Scope scope(&metric);Clock::ticks=1000000;scope.stop();Clock::ticks=9000000;scope.stop();}
 assert(Clock::reads==2&&metric.calls==1&&metric.totalNanoseconds==1000000);
 assert(metric.thresholds[0]==1&&metric.thresholds[1]==0);
 try{Timing::Scope scope(&metric);Clock::ticks+=5000000;throw std::runtime_error("test");}catch(const std::runtime_error&){}
 assert(metric.calls==2&&metric.totalNanoseconds==6000000&&metric.maxNanoseconds==5000000);
 Timing::Metric task;task.record(500000000);metric.merge(task);
 assert(metric.calls==3&&metric.totalNanoseconds==506000000&&metric.maxNanoseconds==500000000);
 const std::array<std::uint64_t,6>expected{{3,2,1,1,1,1}};assert(metric.thresholds==expected);
 FILE*output=std::tmpfile();assert(output);timing.report(output);std::rewind(output);
 std::string report;char buffer[1024];while(std::fgets(buffer,sizeof buffer,output))report+=buffer;std::fclose(output);
 assert(report.find("totals=overlapping")!=std::string::npos);
 assert(report.find("phase=prepare calls=3 total_ms=506.000 max_ms=500.000")!=std::string::npos);
 assert(report.find("phase=worker_kernel calls=0")!=std::string::npos);
}
''')

    def test_timing_enabled_and_disabled_preserve_routes_targets_and_budgets(self):
        main=r'''
int main(){for(bool fixed:{false,true})for(int kind=0;kind<4;++kind)for(int seed=0;seed<4;++seed){
 World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;
 w.a.ai.safe=w.b.ai.safe=kind==1;w.a.ai.closest=w.b.ai.closest=kind==2;
 if(kind==3)p.quickAllowed=false;
 for(int x=3;x<7;++x)for(int y=4;y<7;++y)if((x*31+y*17+seed*13)%11==0)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();
 for(Object*o:{&w.a,&w.b}){p.m_queuePRHead=o->id-1;Path*path;
  if(kind==3){assert(!p.findPathWithInputs(o,o->ai.locomotor,&o->ai.from,&o->ai.to));
   p.confirmParallelFallback(o,o->ai.locomotor,o->ai.from,o->ai.to,false);
   path=p.findClosestPath(o,o->ai.locomotor,&o->ai.from,&o->ai.to,false,0,false);
  }else path=w.consume(p,*o);
  std::printf("%d:%d:%d:%d:%d ",fixed,kind,seed,int(o->id),path!=nullptr);
  if(path)for(auto c:path->route)std::printf("%d,%d;",c.x,c.y);
  std::printf(" T %.3f %.3f B %d\n",o->ai.to.x,o->ai.to.y,mainPathfindSearchContext().m_cumulativeCellsAllocated);
 }
 p.clearParallelBatch();auto&b=*p.m_parallelBatch;
 std::printf("P %llu %llu %llu F %llu %llu %llu\n",b.accepted,b.rejected,b.unused,b.fallbackAccepted,b.fallbackRejected,b.fallbackUnused);
}}
'''
        self.assertEqual(run_cpp(fixture(True)+main).stdout,
                         run_cpp(fixture(False)+main).stdout)

    def test_phase_timing_merges_after_join_and_counts_rejected_and_unused_work(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();using T=PathSearchTiming;
 auto&t=p.m_pathTiming;assert(t[T::Pair].calls==1&&t[T::WorkerKernel].calls==1&&t[T::CallerKernel].calls==1);
 assert(t[T::SerialKernel].calls==0&&t[T::Finalization].calls==0&&t[T::CallerPreparation].calls==0);
 auto workerNs=t[T::WorkerKernel].totalNanoseconds;
 p.prepareParallelBatch();assert(t[T::Pair].calls==1&&t[T::WorkerKernel].totalNanoseconds==workerNs);
 ++p.m_parallelWorldEpoch;assert(w.consume(p,w.a));
 assert(p.m_parallelBatch->rejected==1&&t[T::Validation].calls==1&&t[T::SerialKernel].calls==1);
 assert(t[T::Finalization].calls==1&&t[T::CallerPreparation].calls==1);
 p.clearParallelBatch();assert(p.m_parallelBatch->unused==1);
 assert(t[T::WorkerKernel].calls==1&&t[T::CallerKernel].calls==1);
}
''')

    def test_early_fallback_timing_uses_private_kernel_metrics(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.quickAllowed=false;p.fallbackRendezvous=true;
 p.prepareParallelBatch();using T=PathSearchTiming;auto&t=p.m_pathTiming;
 assert(t[T::Pair].calls==1&&t[T::CallerKernel].calls==1&&t[T::WorkerKernel].calls==1);
 assert(t[T::SerialKernel].calls==0);
 for(auto&job:p.m_parallelBatch->jobs){assert(job.kernelTime.calls==0&&job.fallback->kernelTime.calls==1);}
 p.confirmParallelFallback(&w.a,w.a.ai.locomotor,w.a.ai.from,w.a.ai.to,false);
 assert(p.findClosestPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to,false,0,false));
 assert(t[T::Validation].calls==1&&t[T::Finalization].calls==1&&t[T::Hierarchy].calls==1);
 assert(t[T::CallerPreparation].calls==1&&t[T::SerialKernel].calls==0);
 p.clearParallelBatch();assert(p.m_parallelBatch->fallbackAccepted==1&&p.m_parallelBatch->fallbackUnused==1);
}
''')

    def test_queue_timing_empty_calls_and_early_preparation_exit(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;p.m_queuePRTail=0;p.processPathfindQueue();using T=PathSearchTiming;
 auto&t=p.m_pathTiming;assert(t[T::Queue].calls==0);
 w.queue(p);p.m_queuePRTail=2;p.processPathfindQueue();
 assert(t[T::Queue].calls==1&&t[T::Pair].calls==1&&t[T::Finalization].calls==2);
 p.processPathfindQueue();assert(t[T::Queue].calls==1);
 const auto before=t[T::CallerPreparation].calls;Coord3D zero{};
 assert(!p.internalFindPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&zero));
 assert(t[T::CallerPreparation].calls==before+1&&t[T::Finalization].calls==2);
}
''')

    def test_early_fallback_routes_targets_and_budgets_match_serial(self):
        run_cpp(fixture()+r'''
int main(){for(bool fixed:{false,true})for(int reason=0;reason<3;++reason)for(int mask=1;mask<4;++mask)for(int seed=0;seed<8;++seed){
 World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;
 for(int i=0;i<2;++i)if(mask&(1<<i)){
  auto*c=p.getCell(1,i?&w.b.ai.to:&w.a.ai.to);
  if(reason==0)c->setType(PathfindCell::CELL_OBSTACLE);else if(reason==1)c->setZone(2);
 }
 if(reason==2)p.quickAllowed=false;
 for(int x=3;x<7;++x)for(int y=4;y<7;++y)if((x*31+y*17+seed*13)%11==0)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 auto route=[](Path*path){std::vector<int>r;if(!path)return std::vector<int>{-1};for(auto c:path->route)r.push_back(c.x*100+c.y);return r;};
 auto consume=[&](Object&o){
  auto&ai=o.ai;p.m_queuePRHead=o.id-1;auto*path=p.findPathWithInputs(&o,ai.locomotor,&ai.from,&ai.to);
  if(!path){p.confirmParallelFallback(&o,ai.locomotor,ai.from,ai.to,false);path=p.findClosestPath(&o,ai.locomotor,&ai.from,&ai.to,false,0,false);}
  return route(path);
 };
 const auto originalA=w.a.ai.to,originalB=w.b.ai.to;auto&state=mainPathfindSearchContext();state.m_cumulativeCellsAllocated=0;
 const auto a=consume(w.a),b=consume(w.b);const auto budget=state.m_cumulativeCellsAllocated;
 const auto targetA=w.a.ai.to,targetB=w.b.ai.to;auto corridor=state.m_corridor;
 w.a.ai.to=originalA;w.b.ai.to=originalB;p.m_queuePRHead=0;state.m_cumulativeCellsAllocated=0;state.m_isTunneling=false;
 p.ordinaryHierarchicalCalls=p.hierarchicalCalls=0;p.prepareParallelBatch();auto&batch=*p.m_parallelBatch;
 assert(batch.batches==1&&p.hierarchicalCalls==0&&p.ordinaryHierarchicalCalls==0);
 assert(consume(w.a)==a&&consume(w.b)==b);
 assert(w.a.ai.to.x==targetA.x&&w.a.ai.to.y==targetA.y&&w.b.ai.to.x==targetB.x&&w.b.ai.to.y==targetB.y);
 assert(state.m_cumulativeCellsAllocated==budget&&state.m_corridor==corridor&&!state.m_isTunneling&&state.m_ignoreObstacleID==0);
 assert(state.m_openList.empty()&&state.m_closedList.empty());
 const unsigned early=reason==2?2:bool(mask&1)+bool(mask&2);
 assert(batch.primarySearches+batch.fallbackOnly==2&&batch.fallbackOnly==early);
 assert(batch.earlyFallbackSearches==early&&batch.earlyFallbackAccepted==early&&batch.fallbackRejected==0);
 assert(batch.accepted+batch.rejected+batch.unused==batch.primarySearches);
}}
''', timeout=45)

    def test_early_fallback_only_tasks_overlap_and_require_caller_confirmation(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.quickAllowed=false;p.fallbackRendezvous=true;
 p.prepareParallelBatch();auto&batch=*p.m_parallelBatch;
 assert(batch.batches==1&&batch.primarySearches==0&&batch.fallbackOnly==2&&batch.earlyFallbackSearches==2);
 assert(p.fallbackArrived==2&&p.workerFallbackLoops>0&&p.callerFallbackLoops>0&&p.m_exclusiveWorker->searches==1);
 assert(!batch.jobs[0].ready&&!batch.jobs[1].ready&&!batch.jobs[0].fallbackAllowed);
 assert(!p.findPathWithInputs(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to));
 p.confirmParallelFallback(&w.a,w.a.ai.locomotor,w.a.ai.from,w.a.ai.to,false);
 assert(p.findClosestPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to,false,0,false));
 assert(batch.earlyFallbackAccepted==1&&batch.accepted==0);
 p.clearParallelBatch();assert(batch.unused==0&&batch.fallbackUnused==1);
}
''')

    def test_early_fallback_confirmation_checks_queue_identity_and_callback_inputs(self):
        run_cpp(fixture()+r'''
int main(){for(int change=0;change<10;++change){World w;Pathfinder p;w.queue(p);p.quickAllowed=false;p.prepareParallelBatch();
 auto&ai=w.a.ai;auto from=ai.from,to=ai.to;bool blocked=false;LocomotorSet copy=ai.locomotor;const LocomotorSet*loco=&ai.locomotor;
 assert(!p.findPathWithInputs(&w.a,ai.locomotor,&ai.from,&ai.to));
 switch(change){
 case 0:p.m_queuePRHead=1;break;case 1:from.z+=1;break;case 2:to.x+=1;break;case 3:loco=&copy;break;
 case 4:blocked=true;break;case 5:ai.existingPath=true;break;case 6:PathOccupancy::validationPaused().store(true);break;
 case 7:p.m_parallelBatch->active=false;break;case 8:w.a.hasAI=false;break;case 9:w.a.id=999;break;
 }
 p.confirmParallelFallback(&w.a,*loco,from,to,blocked);
 assert(!p.m_parallelBatch->jobs[0].fallbackAllowed&&!p.m_parallelBatch->jobs[0].fallback->used);
}}
''')

    def test_early_fallback_cannot_be_consumed_without_confirmation_or_from_a_nested_search(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.quickAllowed=false;p.prepareParallelBatch();
 auto&ai=w.a.ai;auto original=ai.to;
 {SearchContextBinding<PathfindSearchContext> bound(mainPathfindSearchContext());p.confirmParallelFallback(&w.a,ai.locomotor,ai.from,ai.to,false);}
 assert(!p.m_parallelBatch->jobs[0].fallbackAllowed);
 assert(p.findClosestPath(&w.a,ai.locomotor,&ai.from,&ai.to,false,0,false));
 assert(p.m_parallelBatch->fallbackAccepted==0&&!p.m_parallelBatch->jobs[0].fallback->used);
 ai.to=original;p.clearParallelBatch();assert(p.m_parallelBatch->fallbackUnused==2);
}
''')

    def test_caller_recomputed_failure_can_authorize_an_independently_valid_fallback(self):
        run_cpp(fixture()+r'''
int main(){for(bool stale:{false,true}){World w;Pathfinder p;w.queue(p);
 for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();p.m_parallelBatch->jobs[0].reads.overflow=true;
 if(stale)p.storage[2][2].setPinched(true);
 auto&ai=w.a.ai;assert(!p.findPathWithInputs(&w.a,ai.locomotor,&ai.from,&ai.to));
 assert(p.m_parallelBatch->rejected==1&&!p.m_parallelBatch->jobs[0].fallbackAllowed);
 p.confirmParallelFallback(&w.a,ai.locomotor,ai.from,ai.to,false);
 assert(p.findClosestPath(&w.a,ai.locomotor,&ai.from,&ai.to,false,0,false));
 assert(p.m_parallelBatch->fallbackAccepted==unsigned(!stale)&&p.m_parallelBatch->fallbackRejected==unsigned(stale));
}}
''')

    def test_early_fallback_validation_rejects_changed_world_after_confirmation(self):
        run_cpp(fixture()+r'''
int main(){for(int change=0;change<7;++change){World w;Pathfinder p;w.queue(p);p.quickAllowed=false;p.prepareParallelBatch();auto&ai=w.a.ai;
 assert(!p.findPathWithInputs(&w.a,ai.locomotor,&ai.from,&ai.to));p.confirmParallelFallback(&w.a,ai.locomotor,ai.from,ai.to,false);
 assert(p.m_parallelBatch->jobs[0].fallbackAllowed);
 switch(change){case 0:++p.m_parallelWorldEpoch;break;case 1:PathOccupancy::validationLifecycleEpoch().fetch_add(1);break;
 case 2:p.storage[2][2].setPinched(true);break;case 3:p.m_parallelBatch->jobs[0].fallback->reads.overflow=true;break;
 case 4:ai.locomotor.downhill=true;break;case 5:ai.existingPath=true;break;case 6:p.hierarchical=false;break;}
 p.findClosestPath(&w.a,ai.locomotor,&ai.from,&ai.to,false,0,false);
 assert(p.m_parallelBatch->fallbackRejected==1&&p.m_parallelBatch->fallbackAccepted==0);
}}
''')

    def test_early_fallback_pairs_with_queued_safe_and_closest_searches(self):
        run_cpp(fixture()+r'''
int main(){for(bool fixed:{false,true})for(int kind=0;kind<2;++kind)for(int first=0;first<2;++first){
 World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;p.quickAllowed=false;
 auto&other=first?w.a:w.b;other.ai.safe=kind==0;other.ai.closest=kind==1;
 auto&early=first?w.b:w.a;
 auto route=[](Path*path){std::vector<int>r;if(!path)return std::vector<int>{-1};for(auto c:path->route)r.push_back(c.x*100+c.y);return r;};
 auto consume=[&](Object&o){p.m_queuePRHead=o.id-1;if(o.ai.safe||o.ai.closest)return route(w.consume(p,o));
  auto&ai=o.ai;auto*path=p.findPathWithInputs(&o,ai.locomotor,&ai.from,&ai.to);
  if(!path){p.confirmParallelFallback(&o,ai.locomotor,ai.from,ai.to,false);path=p.findClosestPath(&o,ai.locomotor,&ai.from,&ai.to,false,0,false);}return route(path);};
 auto originalA=w.a.ai.to,originalB=w.b.ai.to;auto&state=mainPathfindSearchContext();state.m_cumulativeCellsAllocated=0;
 auto a=consume(w.a),b=consume(w.b);auto budget=state.m_cumulativeCellsAllocated;auto targetA=w.a.ai.to,targetB=w.b.ai.to;
 w.a.ai.to=originalA;w.b.ai.to=originalB;state.m_cumulativeCellsAllocated=0;state.m_isTunneling=false;p.m_queuePRHead=0;
 p.prepareParallelBatch();assert(consume(w.a)==a&&consume(w.b)==b);
 assert(w.a.ai.to.x==targetA.x&&w.a.ai.to.y==targetA.y&&w.b.ai.to.x==targetB.x&&w.b.ai.to.y==targetB.y);
 auto&batch=*p.m_parallelBatch;assert(batch.primarySearches==1&&batch.fallbackOnly==1&&batch.accepted==1&&batch.earlyFallbackAccepted==1);
 assert(state.m_cumulativeCellsAllocated==budget);
}}
''')

    def test_early_fallback_queue_budget_discards_the_second_result(self):
        source=fixture().replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')
        source=source.replace('else p->internalFindPath(obj,locomotor,&from,&to);',
          'else if(!p->findPathWithInputs(obj,locomotor,&from,&to)&&!existingPath){p->confirmParallelFallback(obj,locomotor,from,to,false);p->findClosestPath(obj,locomotor,&from,&to,false,0,false);}')
        run_cpp(source+r'''
int main(){World w;Pathfinder p;w.queue(p);p.quickAllowed=false;
 p.processPathfindQueue();assert((applied==std::vector<ObjectID>{1})&&p.m_queuePRHead==1);
 auto&batch=*p.m_parallelBatch;assert(batch.fallbackOnly==2&&batch.earlyFallbackAccepted==1&&batch.fallbackUnused==1&&batch.unused==0);
 auto dispatched=p.m_exclusiveWorker->searches;p.processPathfindQueue();
 assert((applied==std::vector<ObjectID>{1,2})&&p.m_exclusiveWorker->searches==dispatched&&batch.earlyFallbackAccepted==1&&p.hierarchicalCalls==2);
}
''')

    def test_caller_success_discards_an_early_fallback_prediction(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.quickAllowed=false;p.prepareParallelBatch();p.quickAllowed=true;
 auto&ai=w.a.ai;assert(p.findPathWithInputs(&w.a,ai.locomotor,&ai.from,&ai.to));
 assert(!p.m_parallelBatch->jobs[0].fallbackAllowed&&p.m_parallelBatch->fallbackAccepted==0);
 p.clearParallelBatch();assert(p.m_parallelBatch->fallbackUnused==2&&p.m_parallelBatch->unused==0);
}
''')

    def test_real_ai_no_path_branch_confirms_before_closest_and_skips_existing_paths(self):
        ai_source=(ROOT/'GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/AIUpdate.cpp').read_text()
        a=ai_source.index('if (theNewPath==nullptr && m_path==nullptr) {')
        branch=ai_source[a:ai_source.index('\n\tTheAI->pathfinder()->setIgnoreObstacleID',a)]
        for enabled in [False,True]:
            run_cpp(('#define GENERALS_PARALLEL_PATH_BATCH 1\n' if enabled else '')+r'''
#include <cassert>
#include <vector>
using Bool=bool;using Real=float;
#define FALSE false
struct Coord3D{float x=0,y=0,z=0;};struct Path{};struct LocomotorSet{};
struct Object{Coord3D p;const Coord3D*getPosition(){return &p;}};
std::vector<int>events;Path result;
struct Pathfinder{
 void confirmParallelFallback(Object*,const LocomotorSet&,const Coord3D&,const Coord3D&,bool){events.push_back(1);}
 Path*findClosestPath(Object*,const LocomotorSet&,const Coord3D*,Coord3D*,Bool,Real cost,Bool allies){assert(cost==0&&!allies);events.push_back(2);return &result;}
}pathfinder;
struct AI{Pathfinder*pathfinder(){return &::pathfinder;}}ai;auto*TheAI=&ai;
struct AIUpdateInterface{
 Path*m_path=nullptr;LocomotorSet m_locomotorSet;bool m_isBlockedAndStuck=false,m_retryPath=false;Object object;
 Object*getObject(){return &object;}
 void finish(Path*&theNewPath,Coord3D*destination){auto*pathServices=&pathfinder;
'''+branch+r'''
 }
};
int main(){AIUpdateInterface ai;Coord3D to;Path*path=nullptr;ai.finish(path,&to);assert(path==&result&&ai.m_retryPath);
#ifdef GENERALS_PARALLEL_PATH_BATCH
 assert((events==std::vector<int>{1,2}));
#else
 assert((events==std::vector<int>{2}));
#endif
 events.clear();ai.m_retryPath=false;ai.finish(path,&to);assert(events.empty()&&!ai.m_retryPath);
 path=nullptr;ai.m_path=&result;ai.finish(path,&to);assert(events.empty()&&!ai.m_retryPath&&path==nullptr);
}
''')

    def test_closest_serial_matches_previous_routes_destinations_and_budget(self):
        result=run_cpp(fixture()+closest_route_cases()).stdout
        # Recorded from 368e8f942's monolithic closest search using these same controlled world services.
        self.assertEqual(hashlib.sha256(result.encode()).hexdigest(),
                         '25fd66093d3fca7854d655b62cc1aa1e2004453025b5f02e50acf3c394a4d2bb')

    def test_closest_large_search_preserves_the_2000_expansion_pruning_rule(self):
        # GeneralsX @build Codex 27/10/2026 Four full 128x128 serial traces need more than 10 seconds under Intel macOS TSan.
        result=run_cpp(large_closest_fixture()+large_closest_case(),timeout=45).stdout
        # The previous monolithic loop produces the same trace, including actual >2,000 pruning checks.
        self.assertEqual(hashlib.sha256(result.encode()).hexdigest(),
                         '38aa4435e7bc5bbb8891a575a29677996d18cb3aa8d29b9e970de7347e28e5d2')

    def test_closest_and_mixed_pairs_match_serial_and_apply_destination_on_main(self):
        run_cpp(fixture()+r'''
int main(){for(bool fixed:{false,true})for(int kinds=0;kinds<5;++kinds)for(int seed=0;seed<8;++seed){
 World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;
 const int aKind[]={2,0,2,1,2},bKind[]={0,2,2,2,1};
 w.a.ai.closest=aKind[kinds]==2;w.b.ai.closest=bKind[kinds]==2;
 w.a.ai.safe=aKind[kinds]==1;w.b.ai.safe=bKind[kinds]==1;
 w.b.ai.repulsor1=w.b.ai.from;w.b.ai.repulsor2=w.b.ai.from;
 w.a.ai.blocked=w.b.ai.blocked=seed&1;
 for(int x=0;x<12;++x)for(int y=0;y<12;++y)if((x*31+y*17+seed*13)%11==0)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.storage[2][2].setType(PathfindCell::CELL_CLEAR);p.storage[2][8].setType(PathfindCell::CELL_CLEAR);
 p.storage[9][9].setType(w.a.ai.closest&&(seed&1)?PathfindCell::CELL_OBSTACLE:PathfindCell::CELL_CLEAR);
 p.storage[9][2].setType(w.b.ai.closest&&(seed&1)?PathfindCell::CELL_OBSTACLE:PathfindCell::CELL_CLEAR);
 auto route=[](Path*path){std::vector<int>r;if(!path)return std::vector<int>{-1};for(auto c:path->route)r.push_back(c.x*100+c.y);return r;};
 const auto originalA=w.a.ai.to,originalB=w.b.ai.to;auto&state=mainPathfindSearchContext();state.m_cumulativeCellsAllocated=0;
 auto a=route(w.consume(p,w.a)),b=route(w.consume(p,w.b));auto budget=state.m_cumulativeCellsAllocated;
 const auto targetA=w.a.ai.to,targetB=w.b.ai.to;
 w.a.ai.to=originalA;w.b.ai.to=originalB;state.m_cumulativeCellsAllocated=0;state.m_isTunneling=false;p.hierarchicalCalls=0;
 p.prepareParallelBatch();assert(p.m_parallelBatch->batches==1&&p.hierarchicalCalls==0);
 assert(w.a.ai.to.x==originalA.x&&w.a.ai.to.y==originalA.y&&w.b.ai.to.x==originalB.x&&w.b.ai.to.y==originalB.y);
 assert(route(w.consume(p,w.a))==a);assert(route(w.consume(p,w.b))==b);
 assert(w.a.ai.to.x==targetA.x&&w.a.ai.to.y==targetA.y&&w.b.ai.to.x==targetB.x&&w.b.ai.to.y==targetB.y);
 assert(p.m_parallelBatch->accepted==2&&p.m_parallelBatch->rejected==0);
 assert(p.m_parallelBatch->closestAccepted==unsigned(w.a.ai.closest+w.b.ai.closest));
 assert(p.m_parallelBatch->closestSearches==p.m_parallelBatch->closestAccepted);
 assert(state.m_cumulativeCellsAllocated==budget&&state.m_openList.empty()&&state.m_closedList.empty());
}}
''')

    def test_two_closest_kernels_overlap_and_hierarchy_stays_on_main(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);w.a.ai.closest=w.b.ai.closest=true;p.rendezvous=true;
 p.prepareParallelBatch();assert(p.arrived==2&&p.workerLoops>0&&p.callerLoops>0&&p.hierarchicalCalls==0);
 assert(w.consume(p,w.a)&&w.consume(p,w.b));assert(p.hierarchicalCalls==2&&p.m_parallelBatch->closestAccepted==2);
}
''')

    def test_closest_rejects_changed_policy_hierarchy_corridor_request_and_lifecycle(self):
        run_cpp(fixture()+r'''
int main(){for(int change=0;change<10;++change){World w;Pathfinder p;w.queue(p);w.b.ai.closest=true;
 p.prepareParallelBatch();assert(w.consume(p,w.a));
 switch(change){
 case 0:w.b.ai.pathCostMultiplier=0;break;
 case 1:w.b.ai.blocked=true;break;
 case 2:p.hierarchical=false;break;
 case 3:p.m_parallelBatch->jobs[1].reads.corridor.matches([&](std::size_t block){if(p.restrictCorridor<0)p.restrictCorridor=int(block);return true;});assert(p.restrictCorridor>=0);break;
 case 4:w.b.ai.to.x-=1;break;
 case 5:mainPathfindSearchContext().m_ignoreObstacleID=57;break;
 case 6:w.b.ai.closest=false;break;
 case 7:PathOccupancy::validationLifecycleEpoch().fetch_add(1);break;
 case 8:p.storage[2][8].setType(PathfindCell::CELL_OBSTACLE);break;
 case 9:p.m_parallelBatch->jobs[1].reads.overflow=true;break;
 }
 w.consume(p,w.b);assert(p.m_parallelBatch->accepted==1&&p.m_parallelBatch->rejected==1&&p.m_parallelBatch->closestAccepted==0);
}}
''')

    def test_closest_policy_checks_goal_permission_and_move_allies(self):
        run_cpp(fixture()+r'''
int main(){for(int change=0;change<2;++change){World w;Pathfinder p;w.queue(p);w.b.ai.closest=true;
 p.prepareParallelBatch();assert(w.consume(p,w.a));auto&job=p.m_parallelBatch->jobs[1];
 if(change==0)job.closestSettings.goalOnObstacle=!job.closestSettings.goalOnObstacle;
 p.m_queuePRHead=1;p.findClosestPath(&w.b,w.b.ai.locomotor,&w.b.ai.from,&w.b.ai.to,w.b.ai.blocked,w.b.ai.pathCostMultiplier,change==1);
 assert(p.m_parallelBatch->rejected==1&&p.m_parallelBatch->closestAccepted==0);
}}
''')

    def test_closest_queue_budget_still_stops_after_the_first_request(self):
        source=fixture().replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')
        run_cpp(source+r'''
int main(){World w;Pathfinder p;w.queue(p);w.a.ai.closest=w.b.ai.closest=true;
 p.processPathfindQueue();assert(p.m_queuePRHead==1&&p.m_parallelBatch->closestAccepted==1&&p.m_parallelBatch->unused==1);
 assert((applied==std::vector<ObjectID>{1})&&p.hierarchicalCalls==1);
 auto dispatched=p.m_exclusiveWorker->searches;p.processPathfindQueue();
 assert((applied==std::vector<ObjectID>{1,2})&&p.hierarchicalCalls==2&&p.m_exclusiveWorker->searches==dispatched);
}
''')

    def test_ordinary_failure_closest_fallback_is_validated_and_finalized_on_main(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);
 for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();assert(p.m_parallelBatch->batches==1&&!p.m_parallelBatch->jobs[0].outcome.found);
 assert(!w.consume(p,w.a));auto workerSteps=p.workerLoops.load();auto dispatched=p.m_exclusiveWorker->searches;
 assert(p.findClosestPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to,false,0,false));
 assert(w.a.ai.to.x<60&&p.hierarchicalCalls==1&&p.workerLoops==workerSteps&&p.m_exclusiveWorker->searches==dispatched);
 assert(p.m_parallelBatch->closestSearches==0&&p.m_parallelBatch->closestAccepted==0);
 assert(p.m_parallelBatch->fallbackSearches==2&&p.m_parallelBatch->fallbackAccepted==1);
 using S=PathSearchTiming::Result;auto&t=p.m_pathTiming;auto sample=t.slowPairs()[0];
 assert(sample.tasks[0].primaryOutcome.result==S::Reused&&sample.tasks[0].fallbackOutcome.result==S::Reused);
 assert(t.results(false,S::Reused)==1&&t.results(true,S::Reused)==1);
}
''')

    def test_combined_fallback_routes_targets_budget_and_flags_match_serial(self):
        run_cpp(fixture()+r'''
int main(){for(bool fixed:{false,true})for(bool center:{false,true})for(int radius:{0,1})for(int mask=0;mask<4;++mask)for(int seed=0;seed<8;++seed){
 World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;p.testCenter=center;p.testRadius=radius;
 w.a.ai.to.x=mask&1?95:45;w.b.ai.to.x=mask&2?95:45;
 for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 for(int x=0;x<5;++x)for(int y=4;y<=6;++y)if((x*31+y*17+seed*13)%19==0&&x!=2)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 auto route=[](Path*path){std::vector<int>r;if(!path)return std::vector<int>{-1};for(auto c:path->route)r.push_back(c.x*100+c.y);return r;};
 unsigned failures=0;auto consume=[&](Object&o){auto*path=w.consume(p,o);if(!path){++failures;path=p.findClosestPath(&o,o.ai.locomotor,&o.ai.from,&o.ai.to,false,0,false);}return route(path);};
 const auto originalA=w.a.ai.to,originalB=w.b.ai.to;auto&state=mainPathfindSearchContext();state.m_cumulativeCellsAllocated=0;
 auto a=consume(w.a),b=consume(w.b);const unsigned serialFailures=failures;failures=0;auto budget=state.m_cumulativeCellsAllocated;auto records=state.m_records.size();
 const auto targetA=w.a.ai.to,targetB=w.b.ai.to;auto corridor=state.m_corridor;
 w.a.ai.to=originalA;w.b.ai.to=originalB;state.m_cumulativeCellsAllocated=0;state.m_isTunneling=false;p.hierarchicalCalls=0;
 p.prepareParallelBatch();assert(p.m_parallelBatch->batches==1&&p.hierarchicalCalls==0);
 assert(w.a.ai.to.x==originalA.x&&w.a.ai.to.y==originalA.y&&w.b.ai.to.x==originalB.x&&w.b.ai.to.y==originalB.y);
 assert(consume(w.a)==a&&consume(w.b)==b);
 assert(w.a.ai.to.x==targetA.x&&w.a.ai.to.y==targetA.y&&w.b.ai.to.x==targetB.x&&w.b.ai.to.y==targetB.y);
 auto&batch=*p.m_parallelBatch;assert(batch.accepted==2&&batch.rejected==0);
 assert(failures==serialFailures);
 assert(batch.fallbackSearches==failures&&batch.fallbackAccepted==failures&&batch.fallbackRejected==0);
 assert(p.hierarchicalCalls==int(failures)&&state.m_cumulativeCellsAllocated==budget);
 assert(state.m_corridor==corridor&&!state.m_isTunneling&&state.m_ignoreObstacleID==0&&state.m_openList.empty()&&state.m_closedList.empty());
 // Transferred phases retain their original residual records in their own contexts; main has no active list.
 if(!mask)assert(state.m_records.size()<=records);
 for(auto&job:batch.jobs)assert(!job.fallback->fallback);
}}
''', timeout=45)  # 256 four-arena lifetimes exceed the normal 10-second guard under TSan.

    def test_combined_fallbacks_really_overlap_without_an_extra_worker_dispatch(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);p.fallbackRendezvous=true;
 for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();assert(p.fallbackArrived==2&&p.workerFallbackLoops>0&&p.callerFallbackLoops>0);
 assert(p.m_exclusiveWorker->searches==1&&p.m_parallelBatch->fallbackSearches==2&&p.hierarchicalCalls==0);
 for(Object*o:{&w.a,&w.b}){assert(!w.consume(p,*o));assert(p.findClosestPath(o,o->ai.locomotor,&o->ai.from,&o->ai.to,false,0,false));}
 assert(p.m_parallelBatch->accepted==2&&p.m_parallelBatch->fallbackAccepted==2&&p.hierarchicalCalls==2);
}
''')

    def test_fallback_requires_an_accepted_ordinary_failure_before_consumption(self):
        run_cpp(fixture()+r'''
int main(){for(int change=0;change<4;++change){World w;Pathfinder p;w.queue(p);
 for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();auto&job=p.m_parallelBatch->jobs[0];assert(job.fallback->ready);
 if(change==0)job.reads.overflow=true;
 if(change==1)++p.m_parallelWorldEpoch;
 if(change==2)PathOccupancy::validationLifecycleEpoch().fetch_add(1);
 if(change!=3)assert(!w.consume(p,w.a));
 // Case 3 attempts the closest phase before the ordinary phase; none may use its completion.
 assert(p.findClosestPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to,false,0,false));
 assert(p.m_parallelBatch->fallbackAccepted==0&&!job.fallbackAllowed&&!job.fallback->used);
 assert(p.m_parallelBatch->rejected==1);p.clearParallelBatch();assert(p.m_parallelBatch->fallbackUnused==2);
}}
''')

    def test_fallback_revalidates_its_own_policies_world_and_request(self):
        run_cpp(fixture()+r'''
int main(){for(int change=0;change<16;++change){World w;Pathfinder p;w.queue(p);
 for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();assert(!w.consume(p,w.a));auto&job=*p.m_parallelBatch->jobs[0].fallback;
 assert(p.m_parallelBatch->jobs[0].fallbackAllowed);bool blocked=false,moveAllies=false;Real cost=0;
 switch(change){
 case 0:blocked=true;break;
 case 1:cost=.2f;break;
 case 2:moveAllies=true;break;
 case 3:p.hierarchical=false;break;
 case 4:job.reads.corridor.matches([&](std::size_t block){if(p.restrictCorridor<0)p.restrictCorridor=int(block);return true;});assert(p.restrictCorridor>=0);break;
 case 5:mainPathfindSearchContext().m_ignoreObstacleID=57;break;
 case 6:w.a.ai.to.x-=1;break;
 case 7:w.a.ai.locomotor.downhill=true;break;
 case 8:++p.m_parallelWorldEpoch;break;
 case 9:PathOccupancy::validationLifecycleEpoch().fetch_add(1);break;
 case 10:p.storage[2][2].setPinched(true);break;
 case 11:job.reads.overflow=true;break;
 case 12:PathOccupancy::validationPaused().store(true);break;
 case 13:s_useFixedPathfinding=!s_useFixedPathfinding;break;
 case 14:p.testCenter=false;break;
 case 15:w.a.ai.existingPath=true;break;
 }
 p.findClosestPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to,blocked,cost,moveAllies);
 assert(p.m_parallelBatch->accepted==1&&p.m_parallelBatch->fallbackAccepted==0&&p.m_parallelBatch->fallbackRejected==1&&job.used);
 p.findClosestPath(&w.a,w.a.ai.locomotor,&w.a.ai.from,&w.a.ai.to,blocked,cost,moveAllies);
 assert(p.m_parallelBatch->fallbackRejected==1);s_useFixedPathfinding=true;
}}
''')

    def test_fallback_is_not_computed_after_success_or_with_an_existing_path(self):
        run_cpp(fixture()+r'''
int main(){for(int fail=0;fail<2;++fail){World w;Pathfinder p;w.queue(p);w.b.ai.existingPath=true;
 if(fail)for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();auto&batch=*p.m_parallelBatch;
 assert(batch.fallbackSearches==unsigned(fail)&&batch.jobs[0].fallback&&!batch.jobs[1].fallback);
 assert(!batch.jobs[0].fallback->fallback&&batch.jobs[0].fallback->ready==bool(fail));
 if(!fail){assert(w.consume(p,w.a));assert(!batch.jobs[0].fallbackAllowed);}
 p.clearParallelBatch();assert(batch.fallbackUnused==unsigned(fail));
}}
''')

    def test_fallback_queue_budget_and_discard_keep_original_request_order(self):
        source=fixture().replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')
        source=source.replace('else p->internalFindPath(obj,locomotor,&from,&to);',
                              'else if(!p->internalFindPath(obj,locomotor,&from,&to)&&!existingPath)p->findClosestPath(obj,locomotor,&from,&to,false,0,false);')
        run_cpp(source+r'''
int main(){World w;Pathfinder p;w.queue(p);
 for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 p.processPathfindQueue();assert((applied==std::vector<ObjectID>{1})&&p.m_queuePRHead==1&&p.m_parallelBatch->fallbackAccepted==1);
 assert(p.m_parallelBatch->unused==1&&p.m_parallelBatch->fallbackUnused==1);
 auto dispatched=p.m_exclusiveWorker->searches;p.processPathfindQueue();
 assert((applied==std::vector<ObjectID>{1,2})&&p.m_exclusiveWorker->searches==dispatched&&p.hierarchicalCalls==2);
 assert(p.m_parallelBatch->fallbackAccepted==1);
 for(auto&job:p.m_parallelBatch->jobs)if(job.fallback)assert(!job.fallback->context.m_parallelReads&&!job.fallbackAllowed&&!job.fallback->ready);
}
''')

    def test_fallback_rechecks_live_occupancy_and_height_after_ordinary_failure(self):
        run_cpp(fixture()+r'''
int main(){for(bool height:{false,true}){World w;Pathfinder p;w.queue(p);
 for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 Object third;third.id=3;logic.objects[3]=&third;p.storage[2][7].setPosUnit(3,{2,7});w.b.ai.locomotor.downhill=height;
 p.prepareParallelBatch();assert(!w.consume(p,w.b));auto&job=*p.m_parallelBatch->jobs[1].fallback;
 if(height){assert(!job.reads.heights.empty());terrain.bias=1;}
 else {w.b.relation=ALLIES;bool changed=false;
  for(const auto&q:job.reads.queries){LiveOccupancyReader live={&p,&w.b};if(!(PathOccupancy::evaluate(q.input,live)==q.result))changed=true;}
  assert(changed);
 }
 p.findClosestPath(&w.b,w.b.ai.locomotor,&w.b.ai.from,&w.b.ai.to,false,0,false);
 assert(p.m_parallelBatch->accepted==1&&p.m_parallelBatch->fallbackAccepted==0&&p.m_parallelBatch->fallbackRejected==1);
 terrain.bias=0;p.storage[2][7].setPosUnit(0,{2,7});logic.objects.erase(3);
}}
''')

    def test_fallback_reset_reuses_bounded_storage_without_old_completions(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);
 for(int y=0;y<12;++y)p.storage[6][y].setType(PathfindCell::CELL_OBSTACLE);
 p.prepareParallelBatch();auto*a=p.m_parallelBatch->jobs[0].fallback.get();auto*b=p.m_parallelBatch->jobs[1].fallback.get();
 assert(a&&b&&a->ready&&b->ready);p.clearParallelBatch();assert(p.m_parallelBatch->unused==2&&p.m_parallelBatch->fallbackUnused==2);
 for(auto*job:{a,b})assert(!job->ready&&!job->captured&&!job->used&&!job->fallbackAllowed&&!job->context.m_parallelReads);
 w.a.ai.existingPath=w.b.ai.existingPath=true;p.prepareParallelBatch();
 assert(p.m_parallelBatch->jobs[0].fallback.get()==a&&p.m_parallelBatch->jobs[1].fallback.get()==b&&!a->captured&&!b->captured);
 assert(!w.consume(p,w.a)&&!w.consume(p,w.b));
 assert(p.m_parallelBatch->fallbackSearches==2&&p.m_parallelBatch->fallbackAccepted==0);
 p.clearParallelBatch();w.a.ai.existingPath=w.b.ai.existingPath=false;p.m_queuePRHead=0;
 p.prepareParallelBatch();assert(p.m_parallelBatch->jobs[0].fallback.get()==a&&p.m_parallelBatch->jobs[1].fallback.get()==b);
 assert(a->ready&&b->ready&&!a->used&&!b->used&&p.m_parallelBatch->fallbackSearches==4);
 assert(!a->fallback&&!b->fallback);
}
''')

    def test_fallback_is_not_prepared_when_the_other_request_cannot_form_a_pair(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);w.b.ai.locomotor.surfaces=0;
 p.prepareParallelBatch();assert(p.m_parallelBatch&&!p.m_parallelBatch->jobs[1].captured);
 assert(!p.m_parallelBatch->jobs[0].fallback&&!p.m_parallelBatch->jobs[1].fallback&&p.m_parallelBatch->batches==0);
}
''')

    def test_closest_live_occupancy_is_rechecked_and_result_is_single_use(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);w.b.ai.closest=true;
 Object third;third.id=3;logic.objects[3]=&third;p.storage[2][7].setPosUnit(3,{2,7});
 p.prepareParallelBatch();assert(w.consume(p,w.a));auto&job=p.m_parallelBatch->jobs[1];
 w.b.relation=ALLIES;bool changed=false;
 for(const auto&q:job.reads.queries){LiveOccupancyReader live={&p,&w.b};if(!(PathOccupancy::evaluate(q.input,live)==q.result))changed=true;}
 assert(changed);w.consume(p,w.b);assert(p.m_parallelBatch->rejected==1&&p.m_parallelBatch->closestAccepted==0);
 w.consume(p,w.b);assert(p.m_parallelBatch->rejected==1);
 p.storage[2][7].setPosUnit(0,{2,7});logic.objects.erase(3);
}
''')

    def test_closest_pause_reset_and_unused_completion(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);w.a.ai.closest=w.b.ai.closest=true;
 PathOccupancy::validationPaused().store(true);p.prepareParallelBatch();assert(!p.m_parallelBatch);
 PathOccupancy::validationPaused().store(false);p.prepareParallelBatch();assert(p.m_parallelBatch->closestSearches==2);
 PathOccupancy::validationPaused().store(true);w.consume(p,w.a);assert(p.m_parallelBatch->rejected==1);
 p.clearParallelBatch();assert(!p.m_parallelBatch->active&&p.m_parallelBatch->unused==1);
 assert(!p.m_parallelBatch->jobs[0].context.m_parallelReads&&!p.m_parallelBatch->jobs[1].context.m_parallelReads);
 PathOccupancy::validationPaused().store(false);w.consume(p,w.b);assert(p.m_parallelBatch->closestAccepted==0);
}
''')

    def test_closest_predictor_preserves_request_and_matches_callback_precedence(self):
        ai_source=(ROOT/'GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/AIUpdate.cpp').read_text()
        a=ai_source.index('Bool AIUpdateInterface::predictClosestPath(')
        predictor=ai_source[a:ai_source.index('\n}',a)+2]
        run_cpp(r'''
#include <cassert>
#include <initializer_list>
using Bool=bool;using Real=float;
struct Coord3D{float x=0,y=0,z=0;};
struct Object{Coord3D position{10,20,30};const Coord3D*getPosition(){return &position;}};
struct AIUpdateInterface{bool m_waitingForPath=true,m_isSafePath=false,m_isApproachPath=true,m_isBlockedAndStuck=true,ground=true;
 Coord3D m_requestedDestination{80,90,123};Object obj;Object*getObject(){return &obj;}
 bool isDoingGroundMovement(){return ground;}bool predictClosestPath(Coord3D&,Coord3D&,Bool&,Real&);};
'''+predictor+r'''
int main(){AIUpdateInterface ai;Coord3D from,to;bool blocked=false;float cost=0;
 assert(ai.predictClosestPath(from,to,blocked,cost));assert(from.x==10&&from.z==30&&to.x==80&&to.z==123&&blocked&&cost==.2f);
 assert(ai.m_waitingForPath&&ai.m_isApproachPath&&ai.m_isBlockedAndStuck&&ai.m_requestedDestination.x==80);
 for(bool*flag:{&ai.m_waitingForPath,&ai.m_isApproachPath,&ai.ground}){*flag=false;to.x=999;
  assert(!ai.predictClosestPath(from,to,blocked,cost)&&to.x==999);*flag=true;}
 ai.m_isSafePath=true;assert(!ai.predictClosestPath(from,to,blocked,cost));
}
''')

    def test_safe_serial_routes_expansions_and_cleanup_match_previous_engine(self):
        for limit in [2000,3]:
            source=fixture().replace('MAX_SAFE_PATH_CELL_COUNT=2000',f'MAX_SAFE_PATH_CELL_COUNT={limit}')
            result=run_cpp(source+safe_route_cases()).stdout
            # Captured from f023ce8e9's previous monolithic safe search with these same world services.
            self.assertEqual(hashlib.sha256(result.encode()).hexdigest(),
                             {2000:'549220bfbce123c6c998b3ac08fc72b7e9ffd4712e9cdeb93ab073768966a3a2',
                              3:'9775eb34fb0bd21fe9b15e8f3007722a6dc842a8d3055976241783d62491dafd'}[limit])

    def test_safe_and_mixed_pairs_match_serial_routes_and_budget(self):
        run_cpp(fixture()+r'''
int main(){for(bool fixed:{false,true})for(int kinds:{1,2,3})for(int seed=0;seed<8;++seed){
 World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;
 w.a.ai.safe=(kinds&1)!=0;w.b.ai.safe=(kinds&2)!=0;
 w.b.ai.repulsor1=w.b.ai.from;w.b.ai.repulsor2={65,65,0};
 for(int x=0;x<12;++x)for(int y=0;y<12;++y)if((x*31+y*17+seed*13)%11==0)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.storage[2][2].setType(PathfindCell::CELL_CLEAR);p.storage[2][8].setType(PathfindCell::CELL_CLEAR);
 p.storage[9][9].setType(PathfindCell::CELL_CLEAR);p.storage[9][2].setType(PathfindCell::CELL_CLEAR);
 auto route=[](Path*path){std::vector<int>r;if(!path)return std::vector<int>{-1};for(auto c:path->route)r.push_back(c.x*100+c.y);return r;};
 auto&state=mainPathfindSearchContext();state.m_cumulativeCellsAllocated=0;
 auto a=route(w.consume(p,w.a)),b=route(w.consume(p,w.b));auto budget=state.m_cumulativeCellsAllocated;
 state.m_cumulativeCellsAllocated=0;p.serialExpansion.clear();p.prepareParallelBatch();
 assert(p.m_parallelBatch->batches==1&&p.m_exclusiveWorker->searches==1);
 assert(route(w.consume(p,w.a))==a);assert(route(w.consume(p,w.b))==b);
 assert(p.m_parallelBatch->accepted==2&&p.m_parallelBatch->rejected==0);
 assert(p.m_parallelBatch->safeSearches==unsigned(w.a.ai.safe+w.b.ai.safe));
 assert(p.m_parallelBatch->safeAccepted==p.m_parallelBatch->safeSearches);
 assert(state.m_cumulativeCellsAllocated==budget&&state.m_openList.empty()&&state.m_closedList.empty());
}}
''')

    def test_two_safe_searches_really_overlap_and_finalize_on_main(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);w.a.ai.safe=w.b.ai.safe=true;
 w.b.ai.repulsor1=w.b.ai.from;w.b.ai.repulsor2=w.b.ai.from;
 p.rendezvous=true;p.prepareParallelBatch();assert(p.arrived==2&&p.workerLoops>0&&p.callerLoops>0);
 assert(w.consume(p,w.a)&&w.consume(p,w.b));assert(p.m_parallelBatch->safeAccepted==2);
}
''')

    def test_safe_rejects_changed_repulsors_radius_request_and_live_world(self):
        run_cpp(fixture()+r'''
int main(){for(int change=0;change<11;++change){World w;Pathfinder p;w.queue(p);w.b.ai.safe=true;
 w.b.ai.repulsor1=w.b.ai.from;w.b.ai.repulsor2=w.b.ai.from;
 p.prepareParallelBatch();assert(w.consume(p,w.a));
 switch(change){
 case 0:w.b.ai.repulsor1.x+=1;break;
 case 1:w.b.ai.repulsor2.y+=1;break;
 case 2:w.b.ai.repulsorRadius+=1;break;
 case 3:w.b.ai.from.x+=1;break;
 case 4:w.b.ai.safe=false;break;
 case 5:mainPathfindSearchContext().m_ignoreObstacleID=57;break;
 case 6:mainPathfindSearchContext().m_isTunneling=true;break;
 case 7:PathOccupancy::validationLifecycleEpoch().fetch_add(1);break;
 case 8:p.storage[2][8].setPinched(true);break;
 case 9:w.b.ai.locomotor.surfaces=3;break;
 case 10:p.m_parallelBatch->jobs[1].reads.overflow=true;break;
 }
 w.consume(p,w.b);assert(p.m_parallelBatch->accepted==1&&p.m_parallelBatch->rejected==1&&p.m_parallelBatch->safeAccepted==0);
 auto searched=p.m_exclusiveWorker->searches;w.consume(p,w.b);assert(p.m_parallelBatch->rejected==1&&p.m_exclusiveWorker->searches==searched);
}}
''')

    def test_safe_queue_budget_and_inherited_ignore_are_preserved(self):
        source=fixture().replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')
        run_cpp(source+r'''
int main(){World w;Pathfinder p;w.queue(p);w.a.ai.safe=w.b.ai.safe=true;
 mainPathfindSearchContext().m_ignoreObstacleID=41;w.a.ai.ignored=77;w.b.ai.ignored=78;
 p.processPathfindQueue();assert(p.m_queuePRHead==1&&p.m_parallelBatch->safeAccepted==1&&p.m_parallelBatch->unused==1);
 assert(mainPathfindSearchContext().m_ignoreObstacleID==41);
 assert((applied==std::vector<ObjectID>{1}));
 p.processPathfindQueue();assert((applied==std::vector<ObjectID>{1,2})&&p.m_queuePRHead==2);
}
''')

    def test_two_actual_searches_and_ordered_reuse(self):
        run_cpp(fixture() + r'''
int main(){World w;Pathfinder p;w.queue(p);p.rendezvous=true;p.prepareParallelBatch();
 assert(p.m_parallelBatch&&p.m_parallelBatch->batches==1&&p.workerLoops>0&&p.callerLoops>0&&p.arrived==2);
 assert(p.m_queuePRHead==0&&mainPathfindSearchContext().m_cumulativeCellsAllocated==0);
 auto*path=w.consume(p,w.a);assert(path&&!path->route.empty());
 p.m_queuePRHead=1;p.prepareParallelBatch();assert(p.m_parallelBatch->batches==1);
 assert(w.consume(p,w.b));assert(p.m_parallelBatch->accepted==2&&p.m_parallelBatch->rejected==0);
 assert(!mainPathfindSearchContext().m_parallelReads);
}
''')

    def test_safe_prediction_copies_live_repulsors_without_mutating_ai(self):
        ai_source=(ROOT/'GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/AIUpdate.cpp').read_text()
        a=ai_source.index('Bool AIUpdateInterface::predictSafePath(')
        predictor=ai_source[a:ai_source.index('\n}',a)+2]
        run_cpp(r'''
#include <cassert>
#include <map>
using Bool=bool;using Real=float;using ObjectID=int;
struct Coord3D{float x=0,y=0,z=0;void set(float a,float b,float c){x=a;y=b;z=c;}};
struct Object{Coord3D position;float vision=50;const Coord3D*getPosition(){return &position;}float getVisionRange(){return vision;}};
struct Logic{std::map<int,Object*> objects;Object*findObjectByID(int id){auto i=objects.find(id);return i==objects.end()?nullptr:i->second;}}logic;
auto*TheGameLogic=&logic;
struct AI{struct Data{float m_repulsedDistance=25;}data;Data*getAiData(){return &data;}}ai;
auto*TheAI=&ai;
struct AIUpdateInterface{bool m_waitingForPath=true,m_isSafePath=true;int m_repulsor1=1,m_repulsor2=2;Object obj;
 Object*getObject(){return &obj;}bool predictSafePath(Coord3D&,Coord3D&,Coord3D&,Real&);};
'''+predictor+r'''
int main(){AIUpdateInterface update;update.obj.position={10,20,30};Coord3D from,r1,r2;float radius=0;
 assert(update.predictSafePath(from,r1,r2,radius));assert(from.x==10&&from.z==30&&r1.x==-1000&&r2.y==-1000&&radius==75);
 Object first,second;first.position={40,50,60};second.position={70,80,90};logic.objects[1]=&first;
 assert(update.predictSafePath(from,r1,r2,radius));assert(r1.z==60&&r2.z==60);
 logic.objects[2]=&second;assert(update.predictSafePath(from,r1,r2,radius));assert(r1.x==40&&r2.x==70);
 logic.objects.erase(1);assert(update.predictSafePath(from,r1,r2,radius));assert(r1.x==-1000&&r2.x==70);
 second.position.x=99;update.obj.vision=100;ai.data.m_repulsedDistance=5;
 assert(update.predictSafePath(from,r1,r2,radius));assert(r2.x==99&&radius==105);
 assert(update.m_waitingForPath&&update.m_isSafePath&&update.m_repulsor1==1&&update.m_repulsor2==2&&update.obj.position.x==10);
 update.m_waitingForPath=false;r1.x=123;assert(!update.predictSafePath(from,r1,r2,radius)&&r1.x==123);
 update.m_waitingForPath=true;update.m_isSafePath=false;assert(!update.predictSafePath(from,r1,r2,radius)&&r1.x==123);
}
''')

    def test_safe_pause_blocks_admission_and_reset_discards_results(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);w.a.ai.safe=w.b.ai.safe=true;
 PathOccupancy::validationPaused().store(true);p.prepareParallelBatch();assert(!p.m_parallelBatch);
 PathOccupancy::validationPaused().store(false);p.prepareParallelBatch();assert(p.m_parallelBatch->safeSearches==2);
 PathOccupancy::validationPaused().store(true);w.consume(p,w.a);assert(p.m_parallelBatch->rejected==1);
 p.clearParallelBatch();assert(!p.m_parallelBatch->active&&p.m_parallelBatch->unused==1);
 assert(!p.m_parallelBatch->jobs[0].context.m_parallelReads&&!p.m_parallelBatch->jobs[1].context.m_parallelReads);
 PathOccupancy::validationPaused().store(false);auto before=p.m_exclusiveWorker->searches;
 w.consume(p,w.b);assert(p.m_exclusiveWorker->searches==before&&p.m_parallelBatch->safeAccepted==0);
}
''')

    def test_failed_safe_completions_preserve_serial_budget_and_flags(self):
        run_cpp(fixture()+r'''
int main(){for(bool fixed:{false,true}){World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;
 w.a.ai.safe=w.b.ai.safe=true;p.rejectDestinations=true;
 auto&state=mainPathfindSearchContext();state.m_cumulativeCellsAllocated=0;
 assert(!w.consume(p,w.a)&&!w.consume(p,w.b));auto budget=state.m_cumulativeCellsAllocated;
 state.m_cumulativeCellsAllocated=0;p.prepareParallelBatch();assert(p.m_parallelBatch->safeSearches==2);
 assert(!w.consume(p,w.a)&&!w.consume(p,w.b));
 assert(p.m_parallelBatch->safeAccepted==2&&state.m_cumulativeCellsAllocated==budget&&!state.m_isTunneling);
 assert(state.m_openList.empty()&&state.m_closedList.empty());
}}
''')

    def test_safe_live_occupancy_rejection_without_cell_mutation(self):
        run_cpp(fixture()+r'''
int main(){World w;Pathfinder p;w.queue(p);w.b.ai.safe=true;
 w.b.ai.repulsor1=w.b.ai.from;w.b.ai.repulsor2=w.b.ai.from;
 Object third;third.id=3;logic.objects[3]=&third;p.storage[2][7].setPosUnit(3,{2,7});
 p.prepareParallelBatch();assert(w.consume(p,w.a));auto&job=p.m_parallelBatch->jobs[1];
 assert(!job.reads.queries.empty());
 w.b.relation=ALLIES;
 bool changed=false;for(const auto&q:job.reads.queries){LiveOccupancyReader live={&p,&w.b};
  if(!(PathOccupancy::evaluate(q.input,live)==q.result))changed=true;}
 assert(changed);w.consume(p,w.b);assert(p.m_parallelBatch->rejected==1&&p.m_parallelBatch->safeAccepted==0);
 p.storage[2][7].setPosUnit(0,{2,7});logic.objects.erase(3);
}
''')

    def test_parallel_routes_and_budget_equal_serial_in_both_retail_modes(self):
        run_cpp(fixture() + r"""
int main(){for(bool fixed:{false,true})for(int seed=0;seed<24;++seed){World w;Pathfinder p;w.queue(p);s_useFixedPathfinding=fixed;
 for(int x=0;x<12;++x)for(int y=0;y<12;++y)if((x*31+y*17+seed*13)%11==0)p.storage[x][y].setType(PathfindCell::CELL_OBSTACLE);
 p.storage[2][2].setType(PathfindCell::CELL_CLEAR);p.storage[9][9].setType(PathfindCell::CELL_CLEAR);
 p.storage[2][8].setType(PathfindCell::CELL_CLEAR);p.storage[9][2].setType(PathfindCell::CELL_CLEAR);
 auto copyRoute=[](Path*path){std::vector<int> result;if(!path){result.push_back(-1);return result;}
  for(auto pos:path->route)result.push_back(pos.x*100+pos.y);return result;};
 mainPathfindSearchContext().m_cumulativeCellsAllocated=0;
 auto serialA=copyRoute(w.consume(p,w.a));auto serialB=copyRoute(w.consume(p,w.b));
 int budget=mainPathfindSearchContext().m_cumulativeCellsAllocated;
 mainPathfindSearchContext().beginSearch();mainPathfindSearchContext().m_cumulativeCellsAllocated=0;
 p.prepareParallelBatch();assert(p.m_parallelBatch->batches==1);
 assert(copyRoute(w.consume(p,w.a))==serialA);assert(copyRoute(w.consume(p,w.b))==serialB);
 assert(p.m_parallelBatch->accepted==2&&p.m_parallelBatch->rejected==0);
 assert(mainPathfindSearchContext().m_cumulativeCellsAllocated==budget);
}}
""")

    def test_reject_changed_cells_request_policy_admission_epoch_and_lifecycle(self):
        run_cpp(fixture() + r"""
int main(){for(int change=0;change<10;++change){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();
 assert(w.consume(p,w.a));auto&job=p.m_parallelBatch->jobs[1];
 switch(change){
 case 0:p.storage[9][2].setPinched(true);break;
 case 1:w.b.ai.to.x-=10;break;
 case 2:w.b.ai.through=true;break;
 case 3:++p.m_parallelWorldEpoch;break;
 case 4:PathOccupancy::validationLifecycleEpoch().fetch_add(1);break;
 case 5:p.storage[0][0].setGoalUnit(55,{0,0});break;
 case 6:job.reads.overflow=true;break;
 case 7:job.reads.corridor.observe(0,true);mainPathfindSearchContext().setCorridorPassable(0,false);break;
 case 8:w.b.ai.locomotor.downhill=true;break;
 case 9:s_useFixedPathfinding=!s_useFixedPathfinding;break;
 }
 w.consume(p,w.b);assert(p.m_parallelBatch->accepted==1&&p.m_parallelBatch->rejected==1);
 if(change==5)p.storage[0][0].setGoalUnit(0,{0,0});
 s_useFixedPathfinding=true;
}}
""")

    def test_live_object_occupancy_rechecked_without_cell_changes(self):
        run_cpp(fixture() + r"""
int main(){World w;Pathfinder p;w.queue(p);Object third;third.id=3;logic.objects[3]=&third;
 p.storage[5][5].setPosUnit(3,{5,5});p.prepareParallelBatch();assert(w.consume(p,w.a));
 auto&job=p.m_parallelBatch->jobs[1];
 PathOccupancy::Input input;input.x=5;input.y=5;input.layer=1;input.center=true;
 LiveOccupancyReader live={&p,&w.b};auto old=PathOccupancy::evaluate(input,live);
 job.reads.query(input,old); // Also verifies the production adapter independently of route placement.
 w.b.relation=ALLIES;assert(!(PathOccupancy::evaluate(input,live)==old));
 w.consume(p,w.b);assert(p.m_parallelBatch->rejected==1&&p.m_parallelBatch->accepted==1);
 p.storage[5][5].setPosUnit(0,{5,5});logic.objects.erase(3);
}
""")

    def test_height_recheck_and_single_use(self):
        run_cpp(fixture() + r"""
int main(){World w;Pathfinder p;w.queue(p);w.b.ai.locomotor.downhill=true;
 p.prepareParallelBatch();auto&job=p.m_parallelBatch->jobs[1];assert(!job.reads.heights.empty());
 assert(w.consume(p,w.a));terrain.bias=1;
 w.consume(p,w.b);assert(p.m_parallelBatch->rejected==1&&job.used);
 terrain.bias=0;w.consume(p,w.b);assert(p.m_parallelBatch->rejected==1&&p.m_parallelBatch->accepted==1);
}
""")

    def test_ineligible_pause_debug_missing_key_and_queue_wrap(self):
        run_cpp(fixture() + r"""
int main(){World w;Pathfinder p;w.queue(p);
 w.b.ai.eligible=false;p.prepareParallelBatch();assert(!p.m_parallelBatch);w.b.ai.eligible=true;
 PathOccupancy::validationPaused().store(true);p.prepareParallelBatch();assert(!p.m_parallelBatch);PathOccupancy::validationPaused().store(false);
 global.m_debugAI=1;p.prepareParallelBatch();assert(!p.m_parallelBatch);global.m_debugAI=0;
 w.b.crusher=1;keys.present=false;p.prepareParallelBatch();assert(!p.m_parallelBatch);keys.present=true;w.b.crusher=0;
 p.m_queuePRHead=511;p.m_queuePRTail=1;p.m_queuedPathfindRequests[511]=1;p.m_queuedPathfindRequests[0]=2;
 p.prepareParallelBatch();assert(p.m_parallelBatch->jobs[0].queueIndex==511&&p.m_parallelBatch->jobs[1].queueIndex==0);
 assert(w.consume(p,w.a));p.m_queuePRHead=0;p.prepareParallelBatch();assert(p.m_parallelBatch->batches==1);
 assert(w.consume(p,w.b));assert(p.m_parallelBatch->accepted==2);
}
""")

    def test_bounded_read_overflow_rejects_and_reset_does_not_forget_mutations(self):
        run_cpp(r"""
#include "boundedsearchreads.h"
#include <cassert>
#include <array>
struct Key {int n;bool operator==(Key b)const{return n==b.n;}};
namespace std{template<>struct hash<Key>{size_t operator()(Key)const{return 0;}};}
int main(){BoundedSearchReads<Key,int,4> reads;std::array<int,6> values{{3,5,7,9,11,13}};
 for(int i=0;i<4;++i)reads.observe({i},values[i]);
 auto matches=[&]{return reads.matches([&](Key k){return values[k.n];});};
 assert(matches());reads.observe({0},99);assert(matches()); // First read is retained.
 values[0]=99;assert(!matches());values[0]=3;assert(matches());
 reads.observe({4},values[4]);assert(reads.overflow()&&!matches());
 reads.reset();assert(matches());reads.observe({0},3);assert(matches());
}
""")

    def test_lazy_dependencies_probe_once_and_keep_first_read_at_capacity(self):
        run_cpp(r"""
#include "boundedsearchreads.h"
#include <cassert>
#include <vector>
struct Key {int n;bool operator==(Key b)const{return n==b.n;}};
int hashCalls=0;
namespace std{template<>struct hash<Key>{size_t operator()(Key)const{++hashCalls;return 0;}};}
int main(){BoundedSearchReads<Key,int,4> reads;int snapshots=0;
 for(int i=0;i<4;++i){hashCalls=0;reads.observeWith({i},[&]{++snapshots;return i+10;});assert(hashCalls==1);}
 assert(snapshots==4);
 // Even a full table must recognize an existing key without recapturing a changed value.
 for(int i=0;i<4;++i){hashCalls=0;reads.observeWith({i},[&]{++snapshots;return -1;});assert(hashCalls==1);}
 assert(snapshots==4&&!reads.overflow());
 reads.observe({1},99);
 std::vector<int> order;
 assert(reads.matches([&](Key k){order.push_back(k.n);return k.n+10;}));
 assert((order==std::vector<int>{0,1,2,3}));
 assert(!reads.matches([](Key k){return k.n==2?99:k.n+10;}));
 hashCalls=0;reads.observeWith({4},[&]{++snapshots;return 14;});
 assert(hashCalls==1&&snapshots==4&&reads.overflow());
 hashCalls=0;reads.observeWith({0},[&]{++snapshots;return 10;});assert(hashCalls==0&&snapshots==4);
 assert(!reads.matches([](Key k){return k.n+10;}));
 reads.reset();assert(!reads.overflow());
 reads.observeWith({0},[&]{++snapshots;return 75;});assert(snapshots==5);
 assert(reads.matches([](Key){return 75;}));
}
""")

    def test_failed_dependency_capture_rejects_reuse_until_reset(self):
        run_cpp(r"""
#include "boundedsearchreads.h"
#include <cassert>
#include <stdexcept>
int main(){BoundedSearchReads<int,int,4> reads;bool caught=false;
 reads.observe(1,12);
 try{reads.observeWith(2,[]{throw std::runtime_error("capture failed");return 23;});}
 catch(const std::runtime_error&){caught=true;}
 assert(caught&&reads.overflow());int validations=0;
 assert(!reads.matches([&](int){++validations;return 0;})&&validations==0);
 reads.reset();reads.observeWith(2,[]{return 23;});assert(reads.matches([](int){return 23;}));
}
""")

    def test_pair_executor_joins_both_exceptions_and_preserves_environment(self):
        run_cpp(r"""
#include "exclusivesearchworker.h"
#include <atomic>
#include <cassert>
int main(){ExclusiveSearchWorker worker;std::atomic<int> ready{0},done{0};
 auto task=[&]{++ready;while(ready<2)std::this_thread::yield();++done;};
 worker.runPair(task,task);assert(done==2);
 for(int failed=0;failed<2;++failed){done=0;bool caught=false;
  auto a=[&]{++done;if(failed==0)throw std::runtime_error("worker");};
  auto b=[&]{++done;if(failed==1)throw std::runtime_error("caller");};
  try{worker.runPair(a,b);}catch(const std::runtime_error&){caught=true;}
  assert(caught&&done==2);worker.run([]{});
 }
 assert(std::fesetround(FE_DOWNWARD)==0);
 worker.runPair([]{assert(ExclusiveSearchWorker::onWorker()&&std::fegetround()==FE_DOWNWARD);},
  []{assert(!ExclusiveSearchWorker::onWorker()&&std::fegetround()==FE_DOWNWARD);});
}
""")

    def test_original_queue_checks_budget_after_each_consumed_request(self):
        source=fixture().replace('PATHFIND_CELLS_PER_FRAME=5000','PATHFIND_CELLS_PER_FRAME=1')
        run_cpp(source + r"""
int main(){World w;Pathfinder p;w.queue(p);p.processPathfindQueue();
 assert(p.m_queuePRHead==1&&p.m_queuedPathfindRequests[0]==INVALID_ID&&p.m_queuedPathfindRequests[1]==2);
 assert((applied==std::vector<ObjectID>{1}));
 assert(p.m_parallelBatch->batches==1&&p.m_parallelBatch->accepted==1&&p.m_parallelBatch->unused==1);
 assert(!p.m_parallelBatch->active&&mainPathfindSearchContext().m_cumulativeCellsAllocated>1);
 p.processPathfindQueue();assert(p.m_queuePRHead==2&&(applied==std::vector<ObjectID>{1,2}));
 assert(p.m_parallelBatch->batches==1);
}
""")

    def test_predictor_has_no_ai_state_changes(self):
        ai_source=(ROOT/'GeneralsMD/Code/GameEngine/Source/GameLogic/Object/Update/AIUpdate.cpp').read_text()
        a=ai_source.index('Bool AIUpdateInterface::predictOrdinaryPath(')
        predictor=ai_source[a:ai_source.index('\n}',a)+2]
        run_cpp(r"""
#include <cassert>
#include <initializer_list>
#include "pathsearchprediction.h"
using Bool=bool;using ObjectID=unsigned;
struct Coord3D{float x=0,y=0,z=0;};
struct Region3D{bool isInRegionNoZ(const Coord3D*p)const{return p->x>=0&&p->y>=0&&p->x<=100&&p->y<=100;}};
struct Terrain{void getMaximumPathfindExtent(Region3D*){}}terrain;auto*TheTerrainLogic=&terrain;
constexpr int AI_FOLLOW_EXITPRODUCTION_PATH=3;
struct Object{Coord3D p{10,20,0};const Coord3D*getPosition(){return &p;}};
struct State{int id=0;int getCurrentStateID(){return id;}};
struct AIUpdateInterface {
 bool m_waitingForPath=true,m_isSafePath=false,m_isApproachPath=false,m_isAttackPath=false,m_isBlockedAndStuck=false,m_isFinalGoal=true;
 bool quick=false,through=false;Coord3D m_requestedDestination{80,90,0};Object object;State state;State*m_stateMachine=&state;
 bool canComputeQuickPath(){return quick;}bool canPathThroughUnits(){return through;}Object*getObject(){return &object;}
 unsigned getIgnoredObstacleID(){return 41;}
 bool predictOrdinaryPath(Coord3D&,Coord3D&,ObjectID&,PathPredictionReason*reason=nullptr);
};
"""+predictor+r"""
int main(){AIUpdateInterface ai;Coord3D from,to;unsigned ignored=0;
 assert(ai.predictOrdinaryPath(from,to,ignored));assert(from.x==10&&to.y==90&&ignored==41&&ai.m_waitingForPath);
 for(auto flag:{&ai.m_isSafePath,&ai.m_isApproachPath,&ai.m_isAttackPath,&ai.m_isBlockedAndStuck,&ai.quick}){
  *flag=true;assert(!ai.predictOrdinaryPath(from,to,ignored));*flag=false;
 }
 ai.state.id=3;ai.through=true;assert(!ai.predictOrdinaryPath(from,to,ignored));ai.through=false;
 ai.m_requestedDestination.x=101;assert(!ai.predictOrdinaryPath(from,to,ignored));
}
""")

    def test_results_cannot_be_consumed_outside_the_queue_position(self):
        run_cpp(fixture() + r"""
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();
 p.internalFindPath(&w.b,w.b.ai.locomotor,&w.b.ai.from,&w.b.ai.to);
 assert(!p.m_parallelBatch->jobs[1].used&&p.m_parallelBatch->accepted==0);
 assert(w.consume(p,w.a));assert(w.consume(p,w.b));assert(p.m_parallelBatch->accepted==2);
}
""")

    def test_unbatched_fallback_uses_caller_without_a_worker_handoff(self):
        run_cpp(fixture() + r'''
int main(){World w;Pathfinder p;w.queue(p);p.prepareParallelBatch();
 auto dispatched=p.m_exclusiveWorker->searches;auto workerSteps=p.workerLoops.load();
 p.clearParallelBatch();assert(w.consume(p,w.a));
 assert(p.m_exclusiveWorker->searches==dispatched&&p.workerLoops==workerSteps);
}
''')

    def test_permanent_snapshot_accepts_production_signed_object_ids(self):
        source='#define GENERALS_ZH_PARALLEL_PATH_BATCH 1\nstruct PathfindParallelReads;\n'+engine_fixture()
        source=source.replace('using ObjectID=unsigned;', 'enum ObjectID : int {INVALID_ID=0};')
        source=source.replace('constexpr ObjectID INVALID_ID=0;', '')
        source+='\n'.join(function(m) for m in ['inline Bool PathfindCell::isObstacleFence(',
            'inline Bool PathfindCell::isObstacleTransparent(', 'inline ObjectID PathfindCell::getObstacleID('])
        run_cpp(source+r"""
int main(){PathfindCellInfo::allocateCellInfos();{PathfindCell cell;cell.setGoalUnit(static_cast<ObjectID>(23),{4,5});
 auto values=cell.permanentSearchValues();assert(values[11]==23&&values[14]==4&&values[15]==5);
 cell.setGoalUnit(INVALID_ID,{4,5});}mainPathfindSearchContext().releaseStorage();PathfindCellInfo::releaseCellInfos();}
""")


if __name__ == '__main__':
    if '--tsan' in sys.argv:
        sys.argv.remove('--tsan')
        run_cpp=partial(run_cpp,extra_flags=('-O1','-g','-fsanitize=thread'))
    unittest.main()
