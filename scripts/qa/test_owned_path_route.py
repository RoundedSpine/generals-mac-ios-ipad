#!/usr/bin/env python3
"""Compare the production parent walk with immediate and deferred engine-node creation."""
# GeneralsX @test Codex 27/10/2026 Preserve route layers, cliff optimization, patched tails and failover behavior.
import unittest
from compiled_harness import ROOT, run_cpp

SOURCE = (ROOT / 'Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp').read_text()


def function(marker):
    start = SOURCE.index(marker)
    return SOURCE[start:SOURCE.index('\n}', start) + 2]


def fixture(enabled, retail=1, owned=True):
    collector = function('void Pathfinder::prependRouteCells(')
    collector = collector.replace('{\n', '{\n CollectionScope collection;\n', 1)
    return ('#define GENERALS_ZH_SEARCH_CONTEXT 1\n' if enabled else '') + ('#define GENERALS_OWNED_PATH_ROUTE 1\n' if owned and enabled else '') + f'#define RETAIL_COMPATIBLE_PATHFINDING {retail}\n' + r'''
#include "ownedpathroute.h"
#include <cassert>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
using Int=int;using Bool=bool;using PathfindLayerEnum=int;
const int LAYER_GROUND=1,PATHFIND_RECORD_CAPACITY=30000;
#define DEBUG_ASSERTCRASH(c,m) assert(c)
bool s_useFixedPathfinding=true,collecting=false;
int allocationsDuringWalk=0,allocations=0;
struct CollectionScope{CollectionScope(){assert(!collecting);collecting=true;}~CollectionScope(){collecting=false;}};
struct Coord3D{float x=0,y=0,z=0;};
struct Node{
 Coord3D pos;int layer=0;bool canOptimize=false;
 const Coord3D*getPosition(){return &pos;}int getLayer(){return layer;}bool getCanOptimize(){return canOptimize;}
 void setLayer(int v){layer=v;}void setCanOptimize(bool v){canOptimize=v;}
};
struct Path{
 std::vector<Node> nodes;bool blocked=false;
 Node*getFirstNode(){return nodes.empty()?nullptr:&nodes.back();}
 void prependNode(const Coord3D*p,int layer){++allocations;if(collecting)++allocationsDuringWalk;nodes.push_back({*p,layer,false});}
 void setBlockedByAlly(bool value){blocked=value;}
};
struct PathfindCell{
 enum{CELL_CLIFF=2};int x=0,y=0,layer=LAYER_GROUND,type=0;bool blocked=false,info=true;PathfindCell*parent=nullptr;
 PathfindCell*getParentCell(){return parent;}int getXIndex(){return x;}int getYIndex(){return y;}
 int getLayer(){return layer;}int getType(){return type;}bool isBlockedByAlly(){return blocked;}
 void clearParentCell(){parent=nullptr;}bool hasSearchInfo(){return info;}
};
struct Pathfinder{
 struct Zones{std::vector<std::pair<int,int>>marked;void setPassable(int x,int y,bool value){assert(value);marked.push_back({x,y});}}m_zoneManager;
 std::vector<PathfindCell>*cells=nullptr;int failovers=0;
 template<class RouteSink>void prependRouteCells(RouteSink*,const Coord3D*,PathfindCell*,bool);
 void prependCells(Path*,const Coord3D*,PathfindCell*,bool);
 void adjustCoordToCell(int x,int y,bool center,Coord3D&p,int layer){p={float(x*10+(center?5:0)),float(y*10+(center?5:0)),float(layer*20)};}
 void forceCleanCells(){++failovers;for(auto&c:*cells){c.x=c.y=-999;c.parent=nullptr;}}
};
''' + 'template<class RouteSink>\n' + collector + '\n' + function('void Pathfinder::prependCells(') + r'''
std::string exercise(int scenario,bool fixed){
 s_useFixedPathfinding=fixed;allocations=allocationsDuringWalk=0;
 std::vector<PathfindCell> cells(3);for(int i=0;i<3;++i){cells[i].x=i;cells[i].y=1;if(i)cells[i].parent=&cells[i-1];}
 PathfindCell*goal=&cells[2];Coord3D from{1,2,20};Path path;Pathfinder finder;finder.cells=&cells;
 if(scenario==1){goal=&cells[0];from={5,15,20};}
 if(scenario==2){cells[2].x=cells[1].x;cells[2].layer=2;}
 if(scenario==3)cells[1].type=PathfindCell::CELL_CLIFF;
 if(scenario==4)cells[1].blocked=true;
 if(scenario==5){Coord3D tail{99,99,40};path.prependNode(&tail,2);path.getFirstNode()->setCanOptimize(true);path.blocked=true;}
 if(scenario==6){goal=&cells[0];}
 if(scenario==7)cells[2].type=PathfindCell::CELL_CLIFF;
 if(scenario==8)cells[0].info=false;
 allocations=0;finder.prependCells(&path,&from,goal,true);
#if defined(GENERALS_ZH_SEARCH_CONTEXT) && defined(GENERALS_OWNED_PATH_ROUTE)
 assert(!allocationsDuringWalk);
#else
 assert(allocationsDuringWalk);
#endif
 if(scenario==1){assert(path.nodes.size()==1 && !path.nodes[0].canOptimize);}
 if(scenario==2){assert(path.nodes.size()==2 && path.nodes[0].layer==2);}
 if(scenario==3){assert(!path.nodes[0].canOptimize);}
 if(scenario==4){assert(path.blocked);}
 if(scenario==5){assert(path.nodes.front().pos.x==99 && path.nodes.front().canOptimize && path.blocked);}
 if(scenario==8){assert(finder.failovers==1 && s_useFixedPathfinding);}
 std::ostringstream out;out<<allocations<<':'<<path.blocked<<':'<<finder.failovers;
 for(auto&n:path.nodes)out<<'|'<<n.pos.x<<','<<n.pos.y<<','<<n.pos.z<<','<<n.layer<<','<<n.canOptimize;
 for(auto mark:finder.m_zoneManager.marked)out<<'/'<<mark.first<<','<<mark.second;
 for(auto&c:cells)out<<';'<<(c.parent?1:0);
 return out.str();
}
'''


class OwnedPathRouteTest(unittest.TestCase):
    def compare(self, retail, fixed, scenarios):
        def run(enabled):
            source = fixture(enabled,retail) + '\n#include <iostream>\nint main(){\n'
            for scenario in scenarios:
                source += f'std::cout<<exercise({scenario},{str(fixed).lower()})<<"\\n";\n'
            return run_cpp(source+'}\n').stdout
        self.assertEqual(run(False),run(True))

    def test_fixed_normal_short_bridge_cliff_ally_and_existing_tail(self):
        self.compare(1,True,range(8))

    def test_retail_normal_and_forced_cleanup(self):
        self.compare(1,False,range(9))

    def test_without_retail_support(self):
        self.compare(0,True,range(8))

    def test_default_context_finalizes_directly_with_identical_route(self):
        def routes(enabled):
            return run_cpp(fixture(enabled,owned=False)+'\n#include <iostream>\nint main(){for(int i=0;i<9;++i)std::cout<<exercise(i,false)<<"\\n";}').stdout
        self.assertEqual(routes(False),routes(True))

    def test_owned_values_survive_source_changes_and_apply_is_deferred(self):
        run_cpp(fixture(True) + r'''
int main(){Path path;Coord3D original{3,4,5};
 auto result=OwnedPathRoute<Coord3D,int,8>::fromPath(path);
 result.prependNode(&original,2);result.getFirstNode()->setCanOptimize(true);result.setBlockedByAlly(true);
 original={99,99,99};assert(path.nodes.empty() && !allocations);
 result.materialize(path);assert(allocations==1 && path.nodes[0].pos.x==3 && path.nodes[0].layer==2 && path.nodes[0].canOptimize && path.blocked);
}
''')

    def test_bounded_result_does_not_partially_modify_destination(self):
        run_cpp(fixture(True) + r'''
int main(){Path path;Coord3D pos{1,2,3};
 auto result=OwnedPathRoute<Coord3D,int,3>::fromPath(path);
 for(int i=0;i<3;++i)result.prependNode(&pos,1);
 bool failed=false;try{result.prependNode(&pos,1);}catch(const std::length_error&){failed=true;}
 assert(failed && result.size()==3 && path.nodes.empty() && !allocations);
 result.materialize(path);assert(allocations==3 && path.nodes.size()==3);
}
''')

    def test_seed_edits_and_copy_are_owned(self):
        run_cpp(fixture(True) + r'''
int main(){Path original;Coord3D pos{9,8,7};original.prependNode(&pos,2);
 auto result=OwnedPathRoute<Coord3D,int,8>::fromPath(original);
 result.getFirstNode()->setLayer(3);result.getFirstNode()->setCanOptimize(true);
 auto copied=result;result.getFirstNode()->setLayer(4);
 assert(original.getFirstNode()->layer==2 && !original.getFirstNode()->canOptimize);
 copied.materialize(original);assert(original.getFirstNode()->layer==3 && original.getFirstNode()->canOptimize);
}
''')


if __name__ == '__main__':
    unittest.main()
