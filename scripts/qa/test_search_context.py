#!/usr/bin/env python3
"""Exercise generation isolation and the production bounded cell allocator."""
# GeneralsX @test Codex 26/10/2026 Guard serial search lifetime, occupancy and allocator independence.
import unittest
from compiled_harness import ROOT, run_cpp

HEADER = (ROOT / 'Core/GameEngine/Include/GameLogic/AIPathfind.h').read_text()
SOURCE = (ROOT / 'Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp').read_text()


def function(marker):
    a = SOURCE.index(marker)
    return SOURCE[a:SOURCE.index('\n}', a) + 2]


def allocator_fixture(enabled=True):
    declarations = HEADER[HEADER.index('class PathfindCellInfo;'):HEADER.index('/**\n * This represents one cell')].replace('protected:', 'public:')
    methods = '\n'.join(function(marker) for marker in [
        'void PathfindCellInfo::allocateCellInfos()', 'void PathfindCellInfo::releaseCellInfos()',
        'PathfindCellInfo *PathfindCellInfo::getACellInfo(', 'void PathfindCellInfo::releaseACellInfo(',
    ])
    return ('#define GENERALS_ZH_SEARCH_CONTEXT 1\n' if enabled else '') + r'''
#include "stampedsearchcontext.h"
#include "boundedkeyedpool.h"
#include "boundedrecordindex.h"
#include "searchcontextbinding.h"
#include "searchadmissionwindow.h"
#include <cassert>
#include <cstdio>
#include <vector>
#define RETAIL_COMPATIBLE_PATHFINDING 1
#define MSGNEW(tag) new
#define DEBUG_ASSERTCRASH(c,m) assert(c)
using Int=int;using Bool=bool;using UnsignedInt=unsigned;using UnsignedShort=unsigned short;using ObjectID=unsigned;
constexpr ObjectID INVALID_ID=0;
struct ICoord2D{int x,y;};struct PathfindCell{};
''' + declarations + r'''
#ifdef GENERALS_ZH_SEARCH_CONTEXT
inline unsigned pathfindCellSearchIndex(const PathfindCell*){return SearchCellIndices::invalid;}
#endif
unsigned PathfindCellInfo::s_recordsInUse=0;
PathfindCellInfo*PathfindCellInfo::s_infoArray=nullptr;
PathfindCellInfo*PathfindCellInfo::s_firstFree=nullptr;
constexpr unsigned CELL_INFOS_TO_ALLOCATE=PATHFIND_RECORD_CAPACITY;
''' + methods


class SearchContextTest(unittest.TestCase):
    # GeneralsX @test Codex 28/10/2026 Allocation resets publish stable state with exactly one initialization, including stamp rollover.
    def test_explicit_reset_initializes_once_and_keeps_address(self):
        run_cpp(r'''
#include "stampedsearchcontext.h"
#include <cassert>
struct Node{
 int cost=0;static unsigned assignments;
 Node&operator=(const Node&other){cost=other.cost;++assignments;return *this;}
};
unsigned Node::assignments=0;
int main(){StampedSearchContext<Node,8,unsigned char> c;
 auto*state=&c.resetSlot(3);assert(Node::assignments==1 && c.active(3));
 state->cost=91;assert(&c.get(3)==state && c.get(3).cost==91 && Node::assignments==1);
 for(unsigned i=0;i<600;++i){c.beginSearch();assert(!c.active(3));
  unsigned before=Node::assignments;
  assert(&c.resetSlot(3)==state && Node::assignments==before+1 && c.active(3));
  assert(!state->cost && &c.get(3)==state && Node::assignments==before+1);
  state->cost=i+1;
 }
 unsigned before=Node::assignments;
 assert(&c.resetSlot(3)==state && !state->cost && Node::assignments==before+1);
}
''')

    def test_lazy_reset_and_generation_rollover(self):
        run_cpp(r'''
#include "stampedsearchcontext.h"
#include "boundedkeyedpool.h"
#include "searchcontextbinding.h"
#include <cassert>
struct Node{int cost=0;void*parent=nullptr;bool open=false;};
int main(){StampedSearchContext<Node,8,unsigned char> c;
 auto*n=&c.get(0);n->cost=42;n->parent=n;n->open=true;
 c.beginSearch();assert(!c.active(0));assert(c.get(0).cost==0 && !c.get(0).open && !c.get(0).parent);
 c.get(7).cost=99;
 for(int i=0;i<254;++i)c.beginSearch();
 assert(!c.active(7));assert(c.get(7).cost==0);
 assert(&c.get(0)==n && c.capacity()==8);
}
''')

    def test_persistent_records_and_freelist_survive_generations(self):
        run_cpp(allocator_fixture() + r'''
int main(){
 PathfindCellInfo::allocateCellInfos();PathfindCell a,b;
 auto*one=PathfindCellInfo::getACellInfo(&a,{3,4});auto*two=PathfindCellInfo::getACellInfo(&b,{5,6});
 one->m_goalUnitID=17;one->m_posUnitID=18;one->m_obstacleID=19;one->m_obstacleIsFence=true;
 auto*node=mainPathfindSearchContext().allocateRecord(&a,{3,4},true);
 node->search().m_totalCost=99;node->search().m_pathParent=node;node->search().m_open=true;
 mainPathfindSearchContext().beginSearch();
 assert(one->m_goalUnitID==17 && one->m_posUnitID==18 && one->m_obstacleID==19 && one->m_obstacleIsFence);
 assert(one->m_pos.x==3 && one->m_pos.y==4 && one->m_cell==&a);
 node=mainPathfindSearchContext().allocateRecord(&a,{3,4},true);
 assert(node->search().m_totalCost==0 && node->search().m_pathParent==nullptr && !node->search().m_open && node->search().m_openIndex==-1);
 PathfindCellInfo::releaseACellInfo(one);PathfindCellInfo::releaseACellInfo(two);
 mainPathfindSearchContext().beginSearch();
 auto*reused=PathfindCellInfo::getACellInfo(&a,{7,8});assert(reused==two && reused->m_goalUnitID==INVALID_ID);
 PathfindCellInfo::releaseACellInfo(reused);PathfindCellInfo::releaseCellInfos();
 printf("record=%zu search-state=%zu context=%zu capacity=%u\n",sizeof(PathfindCellInfo),sizeof(PathfindSearchState),sizeof(PathfindSearchContext),PATHFIND_RECORD_CAPACITY);
}
''')

    def test_pool_capacity_exhaustion_recycling_and_map_reset(self):
        run_cpp(allocator_fixture() + r'''
int main(){for(int pass=0;pass<2;++pass){
 PathfindCellInfo::allocateCellInfos();PathfindCell cell;std::vector<PathfindCellInfo*> records;
 for(unsigned i=0;i<PATHFIND_RECORD_CAPACITY;++i){auto*p=PathfindCellInfo::getACellInfo(&cell,{int(i),0});assert(p && !p->m_searchState);records.push_back(p);}
 assert(PathfindCellInfo::getACellInfo(&cell,{0,0})==nullptr);
 mainPathfindSearchContext().beginSearch();
 for(auto*p:records){assert(!p->m_searchState);PathfindCellInfo::releaseACellInfo(p);}
 PathfindCellInfo::releaseCellInfos();
}}
''')

    def test_search_boundary_cleans_before_incrementing_generation(self):
        body = function('void Pathfinder::beginSearchState()')
        run_cpp(r'''
#define GENERALS_ZH_SEARCH_CONTEXT 1
#include "stampedsearchcontext.h"
#include "boundedkeyedpool.h"
#include "searchcontextbinding.h"
#include <cassert>
#define DEBUG_ASSERTCRASH(c,m) assert(c)
struct Node{int value=0;};
StampedSearchContext<Node,8>&mainPathfindSearchContext(){static StampedSearchContext<Node,8> c;return c;}
auto&activePathfindSearchContext(){return mainPathfindSearchContext();}
struct List{bool occupied=false;bool empty(){return !occupied;}};
struct Pathfinder{
 List m_openList,m_closedList;unsigned previous=0;int cleaned=0;
 void cleanOpenAndClosedLists(){assert(mainPathfindSearchContext().generation()==previous);++cleaned;m_openList.occupied=m_closedList.occupied=false;}
 Pathfinder& searchState(){return *this;}
 void beginSearchState();
};
''' + body + r'''
int main(){Pathfinder p;auto&c=mainPathfindSearchContext();p.previous=c.generation();
 c.get(2).value=91;p.m_openList.occupied=true;p.m_closedList.occupied=true;p.beginSearchState();
 assert(p.cleaned==1 && c.generation()==p.previous+1 && !c.active(2));
 p.previous=c.generation();p.beginSearchState();assert(p.cleaned==1 && c.generation()==p.previous+1);
}
''')

    def test_synthetic_routes_match_context_disabled_baseline(self):
        from test_pathfind_heap import fixture
        def routes(enabled):
            source = fixture(1, True, enabled).replace('int main(){randomized()', 'void unused_regression(){randomized()')
            source += r'''
#include <cstdio>
int main(){unsigned long long hash=1469598103934665603ull;
 for(unsigned seed=0;seed<100;++seed){
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 mainPathfindSearchContext().beginSearch();
#endif
 for(int value:gridSearch(true,seed)){hash^=static_cast<unsigned>(value);hash*=1099511628211ull;}}
 printf("%llu\n",hash);
}
'''
            return run_cpp(source).stdout
        self.assertEqual(routes(False), routes(True))

    def test_disabled_mode_preserves_free_parent_alias(self):
        run_cpp(allocator_fixture(False) + r'''
int main(){PathfindCellInfo::allocateCellInfos();PathfindCell cell;
 auto*p=PathfindCellInfo::getACellInfo(&cell,{1,2});assert(&p->freeLink()==&p->search().m_pathParent);
 PathfindCellInfo::releaseACellInfo(p);PathfindCellInfo::releaseCellInfos();}
''')


    def test_context_state_survives_node_generation_changes(self):
        run_cpp(allocator_fixture() + r"""
int main(){
 auto&c=mainPathfindSearchContext();c.resizeCorridor(12);
 for(unsigned i=0;i<12;++i)assert(c.corridorPassable(i));
 c.setCorridorPassable(7,false);c.m_ignoreObstacleID=91;c.m_isTunneling=true;c.m_cumulativeCellsAllocated=4999;
 c.get(2).m_totalCost=41;auto generation=c.generation();c.beginSearch();
 assert(c.generation()==generation+1 && c.get(2).m_totalCost==0);
 // Coarse/fine boundaries invalidate nodes only, preserving the corridor and caller's control state.
 assert(c.m_ignoreObstacleID==91 && c.m_isTunneling && c.m_cumulativeCellsAllocated==4999);
 for(unsigned i=0;i<12;++i)assert(c.corridorPassable(i)==(i!=7));
 auto*other=new PathfindSearchContext;other->resizeCorridor(12);
 other->get(2).m_totalCost=99;other->setCorridorPassable(1,false);
 assert(c.get(2).m_totalCost==0 && c.corridorPassable(1) && !c.corridorPassable(7));
 assert(other->m_ignoreObstacleID==INVALID_ID && !other->m_isTunneling && !other->m_cumulativeCellsAllocated);
 assert(other->corridorPassable(7) && other->m_openList.empty() && other->m_closedList.empty());delete other;
 // Loading a map with the same or different dimensions must discard its old corridor.
 for(unsigned size:{12u,3u,0u,9u}){c.resizeCorridor(size);assert(c.m_corridor.size()==size);
  for(unsigned i=0;i<size;++i)assert(c.corridorPassable(i));}
 c.resizeCorridor(0);assert(c.m_corridor.capacity()==0);
}
""")

    def test_zone_corridor_matches_legacy_through_map_resets(self):
        # Compile actual allocation, bounds checks and corridor methods in both modes.
        markers = ['void PathfindZoneManager::freeBlocks()',
                   'void PathfindZoneManager::allocateBlocks(',
                   'void PathfindZoneManager::clearPassableFlags()',
                   'void PathfindZoneManager::setAllPassable()',
                   'void PathfindZoneManager::setPassable(',
                   'Bool PathfindZoneManager::isPassable(',
                   'Bool PathfindZoneManager::clipIsPassable(']
        methods = '\n'.join(function(marker) for marker in markers)
        def result(enabled):
            return run_cpp(allocator_fixture(enabled) + r"""
#include <random>
#define DEBUG_CRASH(m) (++boundsErrors)
struct IRegion2D{ICoord2D lo,hi;};
struct ZoneBlock{bool pass=true;void setPassable(bool v){pass=v;}bool isPassable(){return pass;}};
using ZoneBlockP=ZoneBlock*;
struct PathfindZoneManager{
 enum{ZONE_BLOCK_SIZE=10};int boundsErrors=0;
 ICoord2D m_zoneBlockExtent{0,0};ZoneBlock*m_blockOfZoneBlocks=nullptr;ZoneBlock**m_zoneBlocks=nullptr;
 void freeBlocks();void allocateBlocks(const IRegion2D&);void clearPassableFlags();void setAllPassable();
 void setPassable(int,int,bool);bool isPassable(int,int)const;bool clipIsPassable(int,int)const;
};
""".replace('int boundsErrors=0;', 'mutable int boundsErrors=0;') + methods + r"""
int main(){PathfindZoneManager p;std::mt19937 random(174);unsigned long long hash=0;
 for(int pass=0;pass<4;++pass){
  int width=pass%2?81:131,height=pass%2?113:87;
  p.allocateBlocks({{0,0},{width-1,height-1}});
  for(int i=0;i<1000;++i){int x=random()%width,y=random()%height;
   if(i%29==0)p.clearPassableFlags();else if(i%31==0)p.setAllPassable();else p.setPassable(x,y,random()%2);
   for(int n=0;n<5;++n){int a=random()%width,b=random()%height;
    bool v=p.isPassable(a,b);assert(v==p.clipIsPassable(a,b));hash=hash*131+v;}
  }
  // Preserve the retail integer-division semantics at negative coordinates.
  assert(p.clipIsPassable(-1,0)==p.clipIsPassable(0,0));
  assert(!p.clipIsPassable(-10,0) && !p.clipIsPassable(width+10,0));
  p.setPassable(-10,0,true);assert(p.boundsErrors==pass+1);
  p.freeBlocks();assert(!p.m_zoneBlocks && !p.m_blockOfZoneBlocks);
#ifdef GENERALS_ZH_SEARCH_CONTEXT
  assert(mainPathfindSearchContext().m_corridor.empty() && !mainPathfindSearchContext().m_corridor.capacity());
#endif
 }
 printf("%llu\n",hash);
}
""").stdout
        self.assertEqual(result(False), result(True))

    def test_context_heap_storage_is_released_before_shutdown(self):
        from test_pathfind_heap import fixture
        source = fixture(1, True, True).replace('int main(){randomized()', 'void unused_regression(){randomized()')
        source += r"""
int main(){Arena a(true,16);auto&c=mainPathfindSearchContext();
 for(int i=0;i<16;++i){a.info[i].search().m_totalCost=i;a.cells[i].putOnSortedOpenList(c.m_openList);}
 assert(!c.m_openList.empty() && c.m_openList.m_heap.capacity());
 c.resizeCorridor(64);c.m_ignoreObstacleID=17;c.m_isTunneling=true;c.m_cumulativeCellsAllocated=99;
 c.releaseStorage();assert(c.m_openList.empty() && !c.m_openList.m_heap.capacity());
 assert(c.m_closedList.empty() && !c.m_closedList.m_heap.capacity() && c.m_corridor.empty() && !c.m_corridor.capacity());
 assert(c.m_ignoreObstacleID==INVALID_ID && !c.m_isTunneling && !c.m_cumulativeCellsAllocated);
 // A new engine can reuse the static context and restore normal heap ordering.
 for(int i=0;i<16;++i){a.info[i].search()=PathfindSearchState{};a.info[i].search().m_totalCost=15-i;
  a.cells[i].putOnSortedOpenList(c.m_openList);}
 assert(c.m_openList.getHead()->id==15);c.releaseStorage();
}
"""
        run_cpp(source)


    def test_queue_order_and_original_per_request_budget(self):
        accessor_start=HEADER.index(' PathfindSearchBookkeeping& searchState() const {')
        accessor=HEADER[accessor_start:HEADER.index('\n }',accessor_start)+3]
        def result(enabled):
            return run_cpp(allocator_fixture(enabled) + r"""
#include <cmath>
#define PROFILER_PLOT(k,v) ((void)0)
#define REAL_TO_INT_FLOOR(v) static_cast<int>(std::floor(v))
constexpr float PATHFIND_CELL_SIZE_F=10;
constexpr int PATHFIND_CELLS_PER_FRAME=5000,PATHFIND_QUEUE_LEN=512;
struct IRegion2D{ICoord2D lo,hi;};
struct Coord3D{float x,y,z;};struct Region3D{Coord3D lo,hi;};
struct Terrain{void getExtent(Region3D*p){*p={{0,0,0},{1000,1000,0}};}}terrain;
auto*TheTerrainLogic=&terrain;
struct Pathfinder;
std::vector<int> processed;
struct AIUpdateInterface{int id,cost;void doPathfind(Pathfinder*);};
struct Object{AIUpdateInterface*ai;AIUpdateInterface*getAIUpdateInterface(){return ai;}};
struct Logic{AIUpdateInterface a[6]{{1,3000},{2,2500},{3,5000},{4,10},{5,10},{6,100}};
 Object objects[6]{{&a[0]},{&a[1]},{&a[2]},{&a[3]},{nullptr},{&a[5]}};
 Object*findObjectByID(unsigned id){assert(id>=1 && id<=6);return id==4?nullptr:&objects[id-1];}}logic;
auto*TheGameLogic=&logic;
struct ZoneManager{bool dirty=false;bool needToCalculateZones(){return dirty;}
 void calculateZones(void*,int*,IRegion2D){dirty=false;}};
struct Pathfinder{
 mutable PathfindSearchBookkeeping m_legacySearchState;
 bool m_isMapReady=true;ZoneManager m_zoneManager;void*m_map=nullptr;int*m_layers=nullptr;
 IRegion2D m_extent{},m_logicalExtent{};
 unsigned m_queuedPathfindRequests[512]{};int m_queuePRHead=510,m_queuePRTail=4;
 void processPathfindQueue();void beginSearchState();
 void cleanOpenAndClosedLists(){assert(false);}
""" + accessor + '\n};\n' + function('void Pathfinder::beginSearchState()') +
 function('void Pathfinder::processPathfindQueue()') + r"""
void AIUpdateInterface::doPathfind(Pathfinder*p){
 // Nested coarse/fine search boundaries must not reset frame accounting.
 auto count=p->searchState().m_cumulativeCellsAllocated;
 p->beginSearchState();p->beginSearchState();assert(count==p->searchState().m_cumulativeCellsAllocated);
 p->searchState().m_cumulativeCellsAllocated+=cost;processed.push_back(id);
}
int main(){Pathfinder p;for(int i=0;i<6;++i)p.m_queuedPathfindRequests[(510+i)%512]=i+1;
 p.m_isMapReady=false;p.processPathfindQueue();assert(processed.empty() && p.m_queuePRHead==510);
 p.m_isMapReady=true;p.m_zoneManager.dirty=true;p.processPathfindQueue();assert(processed.empty());
 p.processPathfindQueue();assert((processed==std::vector<int>{1,2}) && p.m_queuePRHead==0);
 assert(p.searchState().m_cumulativeCellsAllocated==5500);
 p.processPathfindQueue();assert((processed==std::vector<int>{1,2,3}) && p.m_queuePRHead==1);
 assert(p.searchState().m_cumulativeCellsAllocated==5000);
 p.processPathfindQueue();assert((processed==std::vector<int>{1,2,3,6}) && p.m_queuePRHead==4);
 assert(p.searchState().m_cumulativeCellsAllocated==100);
 for(int i=0;i<6;++i)assert(p.m_queuedPathfindRequests[(510+i)%512]==INVALID_ID);
 assert(p.m_logicalExtent.hi.x==99 && p.m_logicalExtent.hi.y==99);
 p.processPathfindQueue();assert(p.searchState().m_cumulativeCellsAllocated==0);
 for(int id:processed)printf("%d ",id);
}
""").stdout
        self.assertEqual(result(False),result(True))


if __name__ == '__main__':
    unittest.main()
