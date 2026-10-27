#!/usr/bin/env python3
"""Compile ordinary fine search and expansion against captured/live movement settings."""
# GeneralsX @refactor Codex 27/10/2026 Compare route ordering and capture ownership without enabling workers.
import unittest
from compiled_harness import ROOT, run_cpp

SOURCE = (ROOT / 'Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp').read_text()
HEADER = (ROOT / 'Core/GameEngine/Include/GameLogic/AIPathfind.h').read_text()


def function(marker):
    a = SOURCE.index(marker)
    return SOURCE[a:SOURCE.index('\n}', a) + 2]


def block(text, marker):
    a = text.index(marker)
    return text[a:text.index('\n};', a) + 3]


def fixture(enabled):
    return ('#define GENERALS_ZH_SEARCH_CONTEXT 1\n' if enabled else '') + r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>
using Int=int;using Bool=bool;using Real=float;using UnsignedInt=unsigned;using ObjectID=int;
using LocomotorSurfaceTypeMask=int;using PathfindLayerEnum=int;
struct Coord3D{float x,y,z;};struct ICoord2D{int x,y;};
#define DEBUG_LOG(m) ((void)0)
#define DEBUG_ASSERTCRASH(c,m) assert(c)
#define RETAIL_COMPATIBLE_PATHFINDING 1
#define RTS_GENERALS 0
#define REAL_TO_INT(v) int(v)
const int LAYER_GROUND=1,LAYER_WALL=2,PLAYER_COMPUTER=2,KINDOF_DOZER=1,KINDOF_VEHICLE=2,ENEMIES=3;
const int COST_ORTHOGONAL=10,COST_DIAGONAL=15,PATHFIND_CELL_SIZE=10;
const float PATHFIND_CELL_SIZE_F=10;
bool s_useFixedPathfinding=true;
struct Player{int type=1;int getPlayerType()const{return type;}};
struct AI{bool through=false;bool canPathThroughUnits()const{return through;}};
struct Object{
 int layer=1,crusher=0,kind=2,relation=ENEMIES;Player player;AI ai;mutable int scalarReads=0,worldReads=0;bool hasAI=true,hasPlayer=true;
 const Player*getControllingPlayer()const{++scalarReads;return hasPlayer?&player:nullptr;}
 const AI*getAIUpdateInterface()const{++scalarReads;return hasAI?&ai:nullptr;}
 int getLayer()const{++scalarReads;return layer;}int getCrusherLevel()const{++scalarReads;return crusher;}
 bool isKindOf(int k)const{++scalarReads;return kind==k;}
 int getRelationship(Object*)const{++worldReads;return relation;}
};
struct LocomotorSet{
 int surfaces=1;bool downhill=false;mutable int reads=0;
 int getValidSurfaces()const{++reads;return surfaces;}bool isDownhillOnly()const{++reads;return downhill;}
};
''' + block(HEADER, 'struct PathfindMovementSettings {') + r'''
struct PathfindMovementInput;
struct PathfindCell;
struct CellList{
 std::vector<PathfindCell*> cells;
 bool empty(){return cells.empty();}PathfindCell*getHead(){return cells.front();}
 void reset(){cells.clear();}void reset(PathfindCell*c){cells={c};}
};
struct PathfindCell{
 enum{CELL_OBSTACLE=1,CELL_CLIFF=2};
 int x=0,y=0,type=0,surface=1,zone=1,layer=1,obstacle=0;
 bool open=false,closed=false,info=false,blocked=false,pinched=false;
 unsigned cost=0,total=0;PathfindCell*parent=nullptr;
 int getXIndex(){return x;}int getYIndex(){return y;}int getLayer(){return layer;}int getType(){return type;}int getZone(){return zone;}
 bool getPinched(){return pinched;}bool hasSearchInfo(){return info;}bool getOpen(){return open;}bool getClosed(){return closed;}
 bool allocateSearchInfo(ICoord2D){info=true;return true;}void releaseSearchInfo(){info=false;}
 bool isObstaclePresent(int ignore){return obstacle&&obstacle!=ignore;}int getObstacleID(){return obstacle;}
 void setBlockedByAlly(bool b){blocked=b;}void setParentCell(PathfindCell*p){parent=p;}
 unsigned getCostSoFar(){return cost;}void setCostSoFar(unsigned v){cost=v;}void setTotalCost(unsigned v){total=v;}
 unsigned costToGoal(PathfindCell*g){return (abs(x-g->x)+abs(y-g->y))*COST_ORTHOGONAL;}
 unsigned costSoFar(PathfindCell*p){return p->cost+((x!=p->x&&y!=p->y)?COST_DIAGONAL:COST_ORTHOGONAL);}
 void startPathfind(PathfindCell*){cost=total=0;parent=nullptr;}
 void putOnSortedOpenList(CellList&l){open=true;auto at=l.cells.begin();while(at!=l.cells.end()&&(*at)->total<=total)++at;l.cells.insert(at,this);}
 void removeFromOpenList(CellList&l){open=false;l.cells.erase(std::find(l.cells.begin(),l.cells.end(),this));}
 void putOnClosedList(CellList&l){closed=true;l.cells.push_back(this);}
 void removeFromClosedList(CellList&l){closed=false;l.cells.erase(std::find(l.cells.begin(),l.cells.end(),this));}
};
struct TCheckMovementInfo{ICoord2D cell;int layer,radius,acceptableSurfaces;bool centerInCell,considerTransient;
 bool enemyFixed=false,allyMoving=false,allyGoal=false;int allyFixedCount=0;};
struct Terrain{int getLayerForDestination(const Coord3D*){return 1;}float getGroundHeight(float x,float y){return x*0.03f+y*0.02f;}}terrain;
Terrain*TheTerrainLogic=&terrain;
struct Global{int m_debugAI=0;}global;Global*TheGlobalData=&global;const int AI_DEBUG_PATHS=1;
struct Logic{Object obstacle;Object*findObjectByID(int){return &obstacle;}}logic;Logic*TheGameLogic=&logic;
struct Path{std::vector<ICoord2D>route;bool blocked=false;};
struct Pathfinder{
 enum{NO_ATTACK=0};
 bool m_isMapReady=true,mutate=false,mutated=false,allied=false;
 Object*sourceObject=nullptr;LocomotorSet*sourceLoco=nullptr;
 struct{ICoord2D lo{0,0},hi{11,11};}m_logicalExtent;
 struct Zones{
  int getEffectiveZone(int,bool,int z){return z;}int getEffectiveTerrainZone(int z){return z;}
  bool isPassable(int,int){return true;}
 }m_zoneManager;
 struct State{bool m_isTunneling=false;int m_ignoreObstacleID=0;CellList m_openList,m_closedList;}state;
 State&searchState(){return state;}
 PathfindCell cells[12][12];Path result;std::vector<ICoord2D>expansion;
 Pathfinder(){for(int y=0;y<12;++y)for(int x=0;x<12;++x){cells[y][x].x=x;cells[y][x].y=y;}}
 void beginSearchState(){assert(state.m_openList.empty()&&state.m_closedList.empty());}
 void getRadiusAndCenter(const Object*,int&r,bool&c){r=0;c=true;}
 PathfindMovementSettings captureMovementSettings(const Object*,const LocomotorSet&,int,bool,bool);
 bool validMovementPosition(bool crusher,int surfaces,PathfindCell*to,PathfindCell* =nullptr){return to&&(to->surface&surfaces)&&(to->type!=PathfindCell::CELL_OBSTACLE||crusher);}
 bool validMovementPosition(bool,int,const PathfindMovementInput&,const Coord3D*);
 PathfindCell*getCell(int layer,int x,int y){
  if(mutate&&!mutated){mutated=true;sourceObject->layer=2;sourceObject->crusher=2;sourceObject->ai.through=true;sourceLoco->surfaces=2;sourceLoco->downhill=true;}
  return layer==1&&x>=0&&x<12&&y>=0&&y<12?&cells[y][x]:nullptr;
 }
 PathfindCell*getCell(int layer,const Coord3D*p){return getCell(layer,int(p->x/10),int(p->y/10));}
 PathfindCell*getClippedCell(int layer,const Coord3D*p){return getCell(layer,p);}
 void worldToCell(const Coord3D*p,ICoord2D*c){*c={int(p->x/10),int(p->y/10)};}
 void clip(Coord3D*,Coord3D*){}
 bool checkDestination(const Object*,int,int,int,int,bool){return true;}
 bool checkForMovement(const Object*o,TCheckMovementInfo&i){
  if(o)++o->worldReads;i.allyFixedCount=allied?1:0;return true;
 }
 bool checkCellOutsideExtents(ICoord2D&c){return c.x<0||c.x>11||c.y<0||c.y>11;}
 void checkChangeLayers(PathfindCell*c){expansion.push_back({c->x,c->y});}
 void cleanOpenAndClosedLists(){for(auto&row:cells)for(auto&c:row)c.open=c.closed=false;state.m_openList.reset();state.m_closedList.reset();}
 void debugShowSearch(bool){}
 Path*buildActualPath(const Object*,int,const Coord3D*,PathfindCell*c,bool,bool){
  for(;c;c=c->parent){result.route.push_back({c->x,c->y});result.blocked|=c->blocked;}return &result;
 }
 using Callback=int(*)(Pathfinder*,PathfindCell*,PathfindCell*,int,int,void*);
 void iterateCellsAlongLine(ICoord2D start,ICoord2D end,int layer,Callback cb,void* data){
  // Controlled line traversal drives the production line callback; not a terrain implementation.
  auto*from=getCell(layer,start.x,start.y);
  int x=start.x,y=start.y;
  while(x!=end.x||y!=end.y){if(x!=end.x)x+=(x<end.x?1:-1);if(y!=end.y)y+=(y<end.y?1:-1);
   auto*to=getCell(layer,x,y);if(cb(this,from,to,x,y,data))break;from=to;}
 }
 static int examineCellsCallback(Pathfinder*,PathfindCell*,PathfindCell*,int,int,void*);
 int examineNeighboringCells(PathfindCell*,PathfindCell*,const LocomotorSet&,bool,bool,int,const ICoord2D&,const Object*,int);
 int examineNeighboringCellsWithMovement(PathfindCell*,PathfindCell*,const PathfindMovementInput&,bool,bool,int,const ICoord2D&,const Object*,int);
 Path*internalFindPath(Object*,const LocomotorSet&,const Coord3D*,const Coord3D*);
};
''' + block(SOURCE, 'struct PathfindMovementInput {') + '\n' + block(SOURCE, 'struct ExamineCellsStruct\n') + '\n' + '\n'.join(function(m) for m in [
        'PathfindMovementSettings Pathfinder::captureMovementSettings(',
        'Bool Pathfinder::validMovementPosition(Bool crusher, PathfindLayerEnum layer,',
        '/*static*/ Int Pathfinder::examineCellsCallback(',
        'Int Pathfinder::examineNeighboringCells(',
        'Int Pathfinder::examineNeighboringCellsWithMovement(',
        'Path *Pathfinder::internalFindPath('])


class MovementTests(unittest.TestCase):
    def test_scalar_snapshot_survives_source_changes(self):
        run_cpp(fixture(True) + r'''
int main(){Pathfinder p;Object o;LocomotorSet loco;o.crusher=1;o.kind=1;o.ai.through=true;
 auto settings=p.captureMovementSettings(&o,loco,2,false,false);
 static_assert(std::is_trivially_copyable<PathfindMovementSettings>::value,"Value settings");
 const auto copy=settings;PathfindMovementInput captured{&o,loco,&copy},live{&o,loco,nullptr};
 int reads=o.scalarReads,locoreads=loco.reads;
 o.layer=2;o.crusher=0;o.kind=2;o.ai.through=false;loco.surfaces=4;loco.downhill=true;
 assert(captured.getLayer()==1&&captured.isCrusher()&&captured.isDozer()&&!captured.isVehicle());
 assert(captured.getValidSurfaces()==1&&!captured.isDownhillOnly()&&captured.canPathThroughUnits());
 assert(copy.radius==2&&!copy.centerInCell&&!copy.human);
 assert(o.scalarReads==reads&&loco.reads==locoreads);
 assert(live.getLayer()==2&&!live.isCrusher()&&!live.isDozer()&&live.isVehicle());
 assert(live.getValidSurfaces()==4&&live.isDownhillOnly()&&!live.canPathThroughUnits());
 auto empty=p.captureMovementSettings(nullptr,loco,0,true,true);
 assert(empty.layer==LAYER_GROUND&&!empty.crusher&&!empty.throughUnits&&!empty.dozer&&!empty.vehicle);
}
''')

    def test_real_fine_search_route_and_expansion_match_both_modes(self):
        main = r'''
int main(){for(bool fixed:{false,true})for(int scenario=0;scenario<24;++scenario){
 s_useFixedPathfinding=fixed;
 Pathfinder p;Object o;LocomotorSet loco;o.kind=scenario%2?1:2;o.crusher=scenario%3==0;o.ai.through=scenario%4==0;
 o.player.type=scenario%2?PLAYER_COMPUTER:1;loco.downhill=scenario%5==0;p.allied=scenario%3==1;
 for(int y=1;y<11;++y)if(y!=scenario%9+1){p.cells[y][6].type=PathfindCell::CELL_OBSTACLE;}
 Coord3D from{25,25,0},to{95,95,0};
 auto*path=p.internalFindPath(&o,loco,&from,&to);
 if(path){assert(path->route.front().x==9&&path->route.front().y==9);assert(path->route.back().x==2&&path->route.back().y==2);}
 std::ostringstream out;out<<scenario<<':'<<(path?1:0)<<':';
 for(auto c:p.result.route)out<<c.x<<','<<c.y<<';';out<<" E ";for(auto c:p.expansion)out<<c.x<<','<<c.y<<';';
 out<<" B "<<p.result.blocked<<'\n';std::fputs(out.str().c_str(),stdout);
 assert(o.worldReads>0);assert(p.state.m_openList.empty()&&p.state.m_closedList.empty());
}}
'''
        self.assertEqual(run_cpp(fixture(False) + main).stdout, run_cpp(fixture(True) + main).stdout)

    def test_captured_search_uses_policy_after_live_scalar_mutation(self):
        run_cpp(fixture(True) + r'''
int main(){Pathfinder p;Object o;LocomotorSet loco;p.mutate=true;p.sourceObject=&o;p.sourceLoco=&loco;
 Coord3D from{25,25,0},to{95,95,0};auto*path=p.internalFindPath(&o,loco,&from,&to);
 assert(p.mutated&&o.layer==2&&loco.surfaces==2);assert(path&&!path->route.empty());assert(o.worldReads>0);
}
''')

    def test_legacy_search_retains_live_policy_reads(self):
        run_cpp(fixture(False) + r'''
int main(){Pathfinder p;Object o;LocomotorSet loco;p.mutate=true;p.sourceObject=&o;p.sourceLoco=&loco;
 Coord3D from{25,25,0},to{95,95,0};assert(!p.internalFindPath(&o,loco,&from,&to));assert(p.mutated);
}
''')

    def test_other_search_callers_keep_live_neighbor_policy(self):
        main = r''' 
int main(){for(int attack:{0,10,20})for(bool through:{false,true}){
 Pathfinder p,q;Object o;LocomotorSet loco;o.ai.through=through;p.allied=q.allied=true;
 auto settings=p.captureMovementSettings(&o,loco,0,true,true);
 PathfindMovementInput movement{&o,loco,&settings};
 auto*parent=&p.cells[2][2];auto*goal=&p.cells[9][9];parent->allocateSearchInfo({2,2});
 auto*otherParent=&q.cells[2][2];auto*otherGoal=&q.cells[9][9];otherParent->allocateSearchInfo({2,2});
 assert(p.examineNeighboringCellsWithMovement(parent,goal,movement,true,true,0,{2,2},&o,attack)==
        q.examineNeighboringCells(otherParent,otherGoal,loco,true,true,0,{2,2},&o,attack));
 for(int y=0;y<12;++y)for(int x=0;x<12;++x){auto&a=p.cells[y][x];auto&b=q.cells[y][x];
  assert(a.open==b.open&&a.closed==b.closed&&a.cost==b.cost&&a.total==b.total&&a.blocked==b.blocked);}
}}
'''
        for enabled in (False, True):
            run_cpp(fixture(enabled) + main)

    def test_relationships_remain_explicit_live_dependencies(self):
        run_cpp(fixture(True) + r'''
int main(){for(bool enemy:{false,true}){
 Pathfinder p;Object o;LocomotorSet loco;o.kind=KINDOF_DOZER;
 const auto settings=p.captureMovementSettings(&o,loco,0,true,true);
 o.relation=enemy?ENEMIES:0; // Change relationship after scalar capture.
 PathfindMovementInput movement{&o,loco,&settings};
 auto*parent=&p.cells[2][2];parent->allocateSearchInfo({2,2});
 p.cells[2][3].type=PathfindCell::CELL_OBSTACLE;p.cells[2][3].obstacle=7;
 p.examineNeighboringCellsWithMovement(parent,nullptr,movement,true,true,0,{2,2},&o,0);
 assert(p.cells[2][3].open==!enemy);assert(o.worldReads>0);
}}
''')

    def test_coordinate_overload_preserves_truncation(self):
        run_cpp(fixture(True) + r'''
int main(){Pathfinder p;Object o;LocomotorSet loco;auto settings=p.captureMovementSettings(&o,loco,0,true,true);
 PathfindMovementInput movement{&o,loco,&settings};Coord3D justOutside{-1,-1,0},outside{-11,0,0};
 assert(p.validMovementPosition(false,LAYER_GROUND,movement,&justOutside));
 assert(!p.validMovementPosition(false,LAYER_GROUND,movement,&outside));}
''')


if __name__ == '__main__':
    unittest.main()
