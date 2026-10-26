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
    declarations = HEADER[HEADER.index('class PathfindCellInfo;'):HEADER.index('// TheSuperHackers @info The PathfindCellList')].replace('protected:', 'public:')
    methods = '\n'.join(function(marker) for marker in [
        'void PathfindCellInfo::allocateCellInfos()', 'void PathfindCellInfo::releaseCellInfos()',
        'PathfindCellInfo *PathfindCellInfo::getACellInfo(', 'void PathfindCellInfo::releaseACellInfo(',
    ])
    return ('#define GENERALS_ZH_SEARCH_CONTEXT 1\n' if enabled else '') + r'''
#include "stampedsearchcontext.h"
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
PathfindCellInfo*PathfindCellInfo::s_infoArray=nullptr;
PathfindCellInfo*PathfindCellInfo::s_firstFree=nullptr;
constexpr unsigned CELL_INFOS_TO_ALLOCATE=PATHFIND_RECORD_CAPACITY;
''' + methods


class SearchContextTest(unittest.TestCase):
    def test_lazy_reset_and_generation_rollover(self):
        run_cpp(r'''
#include "stampedsearchcontext.h"
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
 one->search().m_totalCost=99;one->search().m_pathParent=two;one->search().m_open=true;
 mainPathfindSearchContext().beginSearch();
 assert(one->m_goalUnitID==17 && one->m_posUnitID==18 && one->m_obstacleID==19 && one->m_obstacleIsFence);
 assert(one->m_pos.x==3 && one->m_pos.y==4 && one->m_cell==&a);
 assert(one->search().m_totalCost==0 && one->search().m_pathParent==nullptr && !one->search().m_open && one->search().m_openIndex==-1);
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
 for(unsigned i=0;i<PATHFIND_RECORD_CAPACITY;++i){auto*p=PathfindCellInfo::getACellInfo(&cell,{int(i),0});assert(p && p->m_searchSlot==i);records.push_back(p);}
 assert(PathfindCellInfo::getACellInfo(&cell,{0,0})==nullptr);
 mainPathfindSearchContext().beginSearch();
 for(auto*p:records){assert(p->search().m_totalCost==0);PathfindCellInfo::releaseACellInfo(p);}
 PathfindCellInfo::releaseCellInfos();
}}
''')

    def test_search_boundary_cleans_before_incrementing_generation(self):
        body = function('void Pathfinder::beginSearchState()')
        run_cpp(r'''
#define GENERALS_ZH_SEARCH_CONTEXT 1
#include "stampedsearchcontext.h"
#include <cassert>
#define DEBUG_ASSERTCRASH(c,m) assert(c)
struct Node{int value=0;};
StampedSearchContext<Node,8>&mainPathfindSearchContext(){static StampedSearchContext<Node,8> c;return c;}
struct List{bool occupied=false;bool empty(){return !occupied;}};
struct Pathfinder{
 List m_openList,m_closedList;unsigned previous=0;int cleaned=0;
 void cleanOpenAndClosedLists(){assert(mainPathfindSearchContext().generation()==previous);++cleaned;m_openList.occupied=m_closedList.occupied=false;}
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


if __name__ == '__main__':
    unittest.main()
