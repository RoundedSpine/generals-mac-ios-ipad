#!/usr/bin/env python3
"""Exercise bounded lookup and production cell/search allocation separation."""
# GeneralsX @test Codex 26/10/2026 Verify capacity, record ownership, cleanup and stable search order.
import unittest
from compiled_harness import ROOT, run_cpp
from test_search_context import allocator_fixture, function, HEADER, SOURCE


def engine_fixture(enabled=True):
    source = allocator_fixture(enabled)
    source = source.replace('struct PathfindCell{};', 'class PathfindCell; class Object;\nusing UnsignedByte=unsigned char;using zoneStorageType=unsigned short;using PathfindLayerEnum=int;')
    cell = HEADER[HEADER.index('class PathfindCell\n'):HEADER.index('typedef PathfindCell *PathfindCellP;')].replace('private:', 'public:')
    source = source.replace('unsigned PathfindCellInfo::s_recordsInUse=0;', cell + '\nunsigned PathfindCellInfo::s_recordsInUse=0;')
    source += r'''
#include <cmath>
#include <climits>
#include <random>
#define FALSE false
#define TRUE true
#define DEBUG_LOG(m) ((void)0)
#define DEBUG_CRASH(m) assert(false)
#define REAL_TO_INT_FLOOR(v) static_cast<int>(std::floor(v))
const int LAYER_INVALID=0,LAYER_GROUND=1,COST_ORTHOGONAL=10,COST_DIAGONAL=15,PATHFIND_CELLS_PER_FRAME=5000;
bool s_useFixedPathfinding=true,s_forceCleanCells=false;
'''
    markers = ['PathfindCell::PathfindCell()', 'PathfindCell::~PathfindCell()',
               'void PathfindCell::reset()', 'Bool PathfindCell::allocateInfo(',
               'void PathfindCell::releaseInfo()', 'void PathfindCell::releaseSearchInfo()',
               'void PathfindCell::setGoalUnit(', 'void PathfindCell::setGoalAircraft(',
               'void PathfindCell::setPosUnit(', 'Bool PathfindCell::startPathfind(',
               'void PathfindCell::setParentCell(', 'void PathfindCell::setParentCellHierarchical(',
               'void PathfindCell::clearParentCell(', 'UnsignedInt PathfindCell::costToGoal(',
               'UnsignedInt PathfindCell::costToHierGoal(', 'UnsignedInt PathfindCell::costSoFar(',
               'inline UnsignedInt PathfindCell::getTotalCostDifference(',
               'inline Bool PathfindCell::isBlockedByAlly()', 'inline void PathfindCell::setBlockedByAlly(']
    methods = SOURCE[SOURCE.index('Bool PathfindCellList::before('):SOURCE.index('//-----------------------------------------------------------------------------------', SOURCE.index('Bool PathfindCellList::before('))]
    operations = SOURCE[SOURCE.index('#if RETAIL_COMPATIBLE_PATHFINDING\n// Retail compatible insertion sort'):SOURCE.index('inline Bool PathfindCell::isObstaclePresent')]
    return source + '\n'.join(function(marker) for marker in markers) + methods + operations


class SearchRecordPoolTest(unittest.TestCase):
    def test_production_visibility_in_both_modes(self):
        # Other fixtures expose fields for invariant checks; this one keeps production access control.
        declarations = HEADER[HEADER.index('class PathfindCellInfo;'):HEADER.index('/**\n * This represents one cell')]
        cell = HEADER[HEADER.index('class PathfindCell\n'):HEADER.index('typedef PathfindCell *PathfindCellP;')]
        for enabled in [False, True]:
            source = engine_fixture(enabled).replace(declarations.replace('protected:', 'public:'), declarations)
            source = source.replace(cell.replace('private:', 'public:'), cell)
            run_cpp(source + r'''
int main(){PathfindCellInfo::allocateCellInfos();
 {PathfindCell cell;cell.setGoalUnit(17,{2,3});assert(cell.allocateSearchInfo({2,3}));
  cell.setTotalCost(42);assert(cell.getTotalCost()==42 && cell.getGoalUnit()==17);
  cell.releaseSearchInfo();cell.setGoalUnit(0,{2,3});}
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 mainPathfindSearchContext().releaseStorage();
#endif
 PathfindCellInfo::releaseCellInfos();
}
''')


    def test_collision_churn_exhaustion_and_rollover(self):
        run_cpp(r'''
#include "boundedkeyedpool.h"
#include <cassert>
#include <unordered_map>
#include <random>
struct Key{unsigned id;bool operator==(const Key&b)const{return id==b.id;}};
namespace std{template<>struct hash<Key>{size_t operator()(const Key&)const{return 0;}};}
struct Node{unsigned value=0;};
int main(){
BoundedKeyedPool<Key,Node,32,unsigned char> pool;std::unordered_map<unsigned,Node*> live;std::mt19937 random(39);
for(unsigned i=0;i<32;++i){auto*p=pool.acquire({i});assert(p);p->value=i+11;live[i]=p;}
assert(!pool.acquire({99}) && pool.size()==32);
for(unsigned step=0;step<40000;++step){unsigned key=random()%200;
 auto it=live.find(key);
 if(it!=live.end()){assert(pool.find({key})==it->second && pool.acquire({key})==it->second && it->second->value==key+11);
  assert(pool.release({key}));live.erase(it);assert(!pool.find({key}) && !pool.release({key}));}
 else {auto*p=pool.acquire({key});if(live.size()==32)assert(!p);else{assert(p && p->value==0);p->value=key+11;live[key]=p;}}
 assert(pool.size()==live.size());for(auto entry:live)assert(pool.find({entry.first})==entry.second && entry.second->value==entry.first+11);
 if(step%97==0){pool.beginGeneration();live.clear();assert(!pool.size());for(unsigned i=0;i<200;++i)assert(!pool.find({i}));}
}
for(unsigned i=0;i<300;++i){pool.beginGeneration();assert(!pool.find({800}));auto*p=pool.acquire({800});assert(p && !p->value);p->value=44;}
}
''')

    def test_search_allocation_never_attaches_permanent_records(self):
        run_cpp(engine_fixture() + r'''
int main(){PathfindCellInfo::allocateCellInfos();auto&c=mainPathfindSearchContext();c.beginSearch();
 {PathfindCell a,b;assert(!a.m_info && !b.m_info);
  assert(a.allocateSearchInfo({3,4}) && b.allocateSearchInfo({4,4}));
  assert(!a.m_info && !b.m_info && PathfindCellInfo::s_recordsInUse==0 && c.m_transientRecords==2);
  a.setCostSoFar(10);b.setParentCell(&a);b.setCostSoFar(20);assert(b.getParentCell()==&a);
  a.putOnSortedOpenList(c.m_openList);b.putOnClosedList(c.m_closedList);
  assert(PathfindCell::releaseOpenList(c.m_openList)==1 && PathfindCell::releaseClosedList(c.m_closedList)==1);
  assert(!a.hasSearchInfo() && !b.hasSearchInfo() && !c.m_records.size() && !c.m_transientRecords);
  assert(!PathfindCellInfo::s_recordsInUse);
 }
 c.releaseStorage();PathfindCellInfo::releaseCellInfos();
}
''')

    def test_occupancy_updates_do_not_reset_or_alias_search_state(self):
        run_cpp(engine_fixture() + r'''
int main(){PathfindCellInfo::allocateCellInfos();auto&c=mainPathfindSearchContext();c.beginSearch();
 {PathfindCell unit,empty;unit.setGoalUnit(17,{7,8});unit.setPosUnit(17,{7,8});unit.setGoalAircraft(19,{7,8});
  auto*persistent=unit.m_info;assert(persistent && !persistent->m_searchOwner && unit.hasSearchInfo());
  auto*search=unit.searchInfo();assert(search!=persistent && search->m_searchOwner==&c);
  unit.setTotalCost(44);unit.setBlockedByAlly(true);
  assert(empty.allocateSearchInfo({8,8}));empty.setTotalCost(99);
  empty.setGoalUnit(27,{8,8});assert(empty.m_info && empty.m_info!=empty.searchInfo());
  assert(empty.getTotalCost()==99 && unit.getTotalCost()==44 && unit.isBlockedByAlly());
  unit.releaseSearchInfo();assert(unit.m_info==persistent && unit.getGoalUnit()==17 && unit.getPosUnit()==17 && unit.getGoalAircraft()==19);
  c.beginSearch();assert(unit.m_info==persistent && unit.getTotalCost()==0 && !unit.isBlockedByAlly());
  assert(unit.getXIndex()==7 && unit.getYIndex()==8);
  unit.setPosUnit(0,{7,8});unit.setGoalUnit(0,{7,8});unit.setGoalAircraft(0,{7,8});assert(!unit.m_info);
  empty.setGoalUnit(0,{8,8});assert(!empty.m_info);
 }
 c.releaseStorage();assert(!PathfindCellInfo::s_recordsInUse);PathfindCellInfo::releaseCellInfos();
}
''')

    def test_capacity_admission_and_independent_contexts(self):
        run_cpp(engine_fixture() + r'''
int main(){PathfindCellInfo::allocateCellInfos();auto&c=mainPathfindSearchContext();c.beginSearch();
 {std::vector<PathfindCell> cells(PATHFIND_RECORD_CAPACITY+1);
  cells[0].setGoalUnit(12,{0,0});
  assert(cells[0].hasSearchInfo() && c.m_transientRecords==0);
  for(unsigned i=1;i<PATHFIND_RECORD_CAPACITY;++i)assert(cells[i].allocateSearchInfo({int(i),1}));
  assert(c.m_records.size()==PATHFIND_RECORD_CAPACITY && c.m_transientRecords==PATHFIND_RECORD_CAPACITY-1);
  assert(!cells.back().allocateSearchInfo({1,1}));
  cells[1].releaseSearchInfo();assert(cells.back().allocateSearchInfo({1,1}));
  c.beginSearch();assert(!c.m_records.size() && !c.m_transientRecords && cells[0].getGoalUnit()==12);
  auto*other=new PathfindSearchContext;
  auto*a=c.allocateRecord(&cells[1],{1,1},false);auto*b=other->allocateRecord(&cells[1],{1,1},false);
  assert(a && b && a!=b);a->search().m_totalCost=11;b->search().m_totalCost=29;
  assert(a->search().m_totalCost==11 && b->search().m_totalCost==29);
  other->beginSearch();assert(a->search().m_totalCost==11 && !other->findRecord(&cells[1]));delete other;
 }
 c.releaseStorage();assert(!PathfindCellInfo::s_recordsInUse);PathfindCellInfo::releaseCellInfos();
}
''')

    def test_full_permanent_pool_allows_only_its_shadow_records(self):
        run_cpp(engine_fixture() + r'''
int main(){PathfindCellInfo::allocateCellInfos();auto&c=mainPathfindSearchContext();c.beginSearch();
 {std::vector<PathfindCell> cells(PATHFIND_RECORD_CAPACITY+1);
  for(unsigned i=0;i<PATHFIND_RECORD_CAPACITY;++i)cells[i].setGoalUnit(i+1,{int(i),0});
  assert(PathfindCellInfo::s_recordsInUse==PATHFIND_RECORD_CAPACITY);
  for(unsigned i=0;i<PATHFIND_RECORD_CAPACITY;++i){assert(cells[i].hasSearchInfo());cells[i].setTotalCost(i%65536);}
  assert(c.m_records.size()==PATHFIND_RECORD_CAPACITY && !c.m_transientRecords);
  assert(!cells.back().allocateSearchInfo({0,1}));
  // Permanent pool reuse cannot reset the independent record using the same old pool slot.
  cells[0].setGoalUnit(0,{0,0});assert(!cells[0].m_info);
  cells.back().setGoalUnit(77,{0,1});assert(cells.back().m_info);
  assert(cells[1].getTotalCost()==1);
  c.beginSearch();assert(!c.m_records.size());assert(cells.back().hasSearchInfo() && cells.back().getGoalUnit()==77);
 }
 c.releaseStorage();assert(!PathfindCellInfo::s_recordsInUse);PathfindCellInfo::releaseCellInfos();
}
''')


    def test_production_cell_routes_match_disabled_mode(self):
        def routes(enabled):
            return run_cpp(engine_fixture(enabled) + r'''
#include <cstdio>
int main(){PathfindCellInfo::allocateCellInfos();unsigned long long hash=1469598103934665603ull;
 for(unsigned seed=0;seed<50;++seed){
  std::vector<PathfindCell> cells(24*24);PathfindCellList open(true),closed;
#ifdef GENERALS_ZH_SEARCH_CONTEXT
  mainPathfindSearchContext().beginSearch();
#endif
  std::mt19937 random(seed);std::vector<bool> blocked(cells.size());std::vector<int> distance(cells.size(),1000000);
  for(unsigned i=0;i<cells.size();++i){blocked[i]=random()%5==0;if(i%23==0)cells[i].setGoalUnit(i+1,{int(i%24),int(i/24)});}
  blocked[0]=blocked.back()=false;
  assert(cells[0].allocateSearchInfo({0,0}));distance[0]=0;cells[0].setTotalCost(460);cells[0].putOnSortedOpenList(open);
  while(!open.empty()){
   auto*cell=open.getHead();int id=static_cast<int>(cell-cells.data());cell->removeFromOpenList(open);cell->putOnClosedList(closed);
   hash^=id;hash*=1099511628211ull;
   if(id==575){for(auto*p=cell;p;p=p->getParentCell()){hash^=static_cast<unsigned>(p-cells.data());hash*=1099511628211ull;}break;}
   for(int d:{-24,-1,1,24}){int n=id+d;if(n<0 || n>=576 || (std::abs(d)==1 && id/24!=n/24) || blocked[n])continue;
    auto&next=cells[n];if(next.hasSearchInfo() && next.getClosed())continue;int cost=distance[id]+10;if(cost>=distance[n])continue;
    assert(next.allocateSearchInfo({n%24,n/24}));if(next.getOpen())next.removeFromOpenList(open);
    distance[n]=cost;next.setParentCell(cell);next.setCostSoFar(cost);next.setTotalCost(cost+10*(46-n%24-n/24));next.putOnSortedOpenList(open);
   }
  }
  PathfindCell::releaseOpenList(open);PathfindCell::releaseClosedList(closed);
 }
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 mainPathfindSearchContext().releaseStorage();
#endif
 assert(!PathfindCellInfo::s_recordsInUse);PathfindCellInfo::releaseCellInfos();printf("%llu\n",hash);
}
''').stdout
        self.assertEqual(routes(False), routes(True))


if __name__ == '__main__':
    unittest.main()
