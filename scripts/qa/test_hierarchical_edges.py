#!/usr/bin/env python3
"""Compile the production region-edge helper with controlled cells and allocation failures."""
# GeneralsX @test Codex 26/10/2026 Verify late allocation and cleanup ownership without engine data.
import unittest
from compiled_harness import ROOT, run_cpp

SOURCE = (ROOT / 'Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp').read_text()
START = SOURCE.index('void Pathfinder::processHierarchicalCell(')
HELPER = SOURCE[START:SOURCE.index('\n}', START) + 2]


def fixture(retail, zero_hour=1):
    prefix = f'#define RETAIL_COMPATIBLE_PATHFINDING {retail}\n#define RTS_ZEROHOUR {zero_hour}\n#define RTS_GENERALS {1-zero_hour}\n'
    return prefix + r'''
#include <cassert>
#include <vector>
using Int=int;using Bool=bool;using zoneStorageType=unsigned short;
struct ICoord2D{int x,y;};
const int LAYER_GROUND=0,LOCOMOTORSURFACE_GROUND=0,COST_ORTHOGONAL=10;
bool s_useFixedPathfinding=false;
struct PathfindCell{
 bool info=false,open=false,closed=false,pinched=false,fail=false;
 int zone=1,allocations=0,cost=0,total=0;PathfindCell*parent=nullptr;
 bool hasInfo(){return info;}
 bool getOpen(){assert(info);return open;}bool getClosed(){assert(info);return closed;}
 bool allocateInfo(const ICoord2D&){if(info)return true;if(fail)return false;info=true;++allocations;return true;}
 int getZone(){return zone;}bool getPinched(){return pinched;}
 void putOnClosedList(std::vector<PathfindCell*>&q){assert(info && !open && !closed);closed=true;q.push_back(this);}
 void putOnSortedOpenList(std::vector<PathfindCell*>&q){assert(info && !open && !closed);open=true;q.push_back(this);}
 int costToHierGoal(PathfindCell*){return 10;}int getCostSoFar(){assert(info);return cost;}
 void setCostSoFar(int c){assert(info);cost=c;}void setTotalCost(int c){assert(info);total=c;}
 void setParentCellHierarchical(PathfindCell*p){assert(info);parent=p;}
};
struct PathfindZoneManager{
 static const int UNINITIALIZED_ZONE=0;
 bool mismatch=false;
 int getBlockZone(int,bool,int x,int,void*){return x==0?1:2;}
 int getEffectiveZone(int,bool,int zone){return mismatch?zone:1;}
};
struct Pathfinder{
 struct {ICoord2D lo{0,0},hi{1,0};}m_extent;
 PathfindZoneManager m_zoneManager;void*m_map=nullptr;
 std::vector<PathfindCell*>m_closedList,m_openList;
 PathfindCell border,adjacent;
 PathfindCell*getCell(int,int x,int){assert(x>=0 && x<=1);return x==0?&border:&adjacent;}
 void processHierarchicalCell(const ICoord2D&,const ICoord2D&,PathfindCell*,PathfindCell*,zoneStorageType,zoneStorageType*,Int&,Bool,Int&);
 void cleanup(){for(auto*q:{&m_closedList,&m_openList}){for(auto*c:*q){c->open=c->closed=false;if(c->allocations)c->info=false;}q->clear();}}
};
''' + HELPER + r'''
void exercise(int scenario){
 Pathfinder p;PathfindCell parent,goal;parent.info=goal.info=true;parent.cost=7;
 ICoord2D scan{0,0},delta{1,0};zoneStorageType parentZone=1,zones[16]={};int n=0,count=0;
 if(scenario==1)p.border.info=true;
 if(scenario==2)p.m_zoneManager.mismatch=true;
 if(scenario==3)p.border.fail=true;
 if(scenario==4)p.adjacent.fail=true;
 if(scenario==5){zones[0]=2;n=1;}
 if(scenario==6)p.border.zone=3;
 if(scenario==7)delta.x=2;
 if(scenario==8)parentZone=0;
 if(scenario==9)scan.x=-1;
 if(scenario==10){p.border.info=true;p.border.closed=true;}
 if(scenario==11){p.adjacent.info=true;p.adjacent.open=true;}
 if(scenario==12)p.border.pinched=true;
 if(scenario==13){p.adjacent.info=true;p.adjacent.cost=999;}
 p.processHierarchicalCell(scan,delta,&parent,&goal,parentZone,zones,n,false,count);
#if RTS_ZEROHOUR
 const bool success=scenario==0 || scenario==1 || scenario==12 || scenario==13;
 if(success){
  assert(count==1 && p.m_openList.size()==1 && p.m_closedList.size()==1);
  assert(p.adjacent.parent==&parent && p.adjacent.cost==(scenario==12?37:17));
  assert(p.adjacent.total==(scenario==12?47:27));
  assert(n==(scenario==12?0:1));
  int allocated=p.border.allocations+p.adjacent.allocations;
  p.processHierarchicalCell(scan,delta,&parent,&goal,parentZone,zones,n,false,count);
  assert(count==1 && allocated==p.border.allocations+p.adjacent.allocations);
 }else{
  assert(count==0 && p.adjacent.allocations==0 && p.m_openList.empty());
  if(scenario==4){assert(p.border.allocations==1 && p.border.closed && p.m_closedList.size()==1);}
  else assert(p.border.allocations==0 && p.m_closedList.empty());
 }
 p.cleanup();
 if(p.border.allocations)assert(!p.border.info);
 if(p.adjacent.allocations)assert(!p.adjacent.info);
#else
 // Keep base-game eligibility unchanged in both compile configurations.
 if(scenario==1)assert(count==1);
 if(scenario==0)assert(count==(RETAIL_COMPATIBLE_PATHFINDING?1:0));
#endif
}
int main(){
#if RTS_ZEROHOUR
 for(int fixed=0;fixed<2;++fixed){s_useFixedPathfinding=fixed;for(int scenario=0;scenario<14;++scenario)exercise(scenario);}
#else
 exercise(0);exercise(1);
#endif
}
'''


class HierarchicalEdgeTest(unittest.TestCase):
    def test_zero_hour_retail_and_fixed_paths(self):
        run_cpp(fixture(1))

    def test_zero_hour_without_retail_support(self):
        run_cpp(fixture(0))

    def test_base_game_retail_eligibility(self):
        run_cpp(fixture(1, 0))

    def test_base_game_fixed_eligibility(self):
        run_cpp(fixture(0, 0))


if __name__ == '__main__':
    unittest.main()
