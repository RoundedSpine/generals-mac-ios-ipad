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
    source=source.replace('inline unsigned pathfindCellSearchIndex(const PathfindCell*){return SearchCellIndices::invalid;}','')
    source=source.replace('unsigned PathfindCellInfo::s_recordsInUse=0;',
        '#ifdef GENERALS_ZH_SEARCH_CONTEXT\ninline unsigned pathfindCellSearchIndex(const PathfindCell* cell){return cell->searchIndex();}\n#endif\nunsigned PathfindCellInfo::s_recordsInUse=0;')
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
    if enabled:markers.append('void PathfindCell::registerSearchCells(')
    return source + '\n'.join(function(marker) for marker in markers) + methods + operations


# GeneralsX @test Codex 29/10/2026 Reconstruct the preceding split storage around unchanged production kernels for differential checks.
def split_storage(source):
    start=source.index('struct PathfindSearchNode : PathfindSearchState {')
    end=source.index('\n};',start)+3
    former=r'''struct PathfindSearchNode {
 PathfindCell* m_cell=nullptr;
 PathfindSearchState* m_searchState=nullptr;
 PathfindSearchNode* m_nextFree=nullptr;
 ICoord2D m_pos{};
 ObjectID m_goalUnitID=0,m_posUnitID=0,m_goalAircraftID=0,m_obstacleID=0;
 unsigned m_isFree:1,m_searchCharged:1,m_obstacleIsFence:1,m_obstacleIsTransparent:1;
 PathfindSearchState& search()const{assert(m_searchState);return *m_searchState;}
};'''
    source=source[:start]+former+source[end:]
    before='struct PathfindSearchContext :\n#ifndef GENERALS_ZH_SEARCH_CONTEXT\n PathfindSearchNodes,\n#endif\n PathfindSearchBookkeeping {'
    assert before in source
    source=source.replace(before,'struct PathfindSearchContext : PathfindSearchNodes, PathfindSearchBookkeeping {',1)
    source=source.replace('#ifdef GENERALS_ZH_SEARCH_CONTEXT\n Bool m_searchCharged=false;\n#endif','',1)
    source=source.replace('record->m_searchCharged = !persistent;',
        'record->m_searchState=&resetSlot(m_records.index(record));record->m_searchCharged = !persistent;',1)
    source=source.replace('m_records.beginGeneration(); m_transientRecords = 0;',
        'PathfindSearchNodes::beginSearch();m_records.beginGeneration(); m_transientRecords = 0;',1)
    # Match the old permanent record's unused state pointer too, for a layout check.
    source=source.replace('PathfindCellInfo* m_nextFree;',
        'PathfindSearchState* m_searchState=nullptr;PathfindCellInfo* m_nextFree;',1)
    return source


class SearchRecordPoolTest(unittest.TestCase):
    def test_compact_pool_churn_and_credit_match_split_storage(self):
        source=engine_fixture().replace(
            'BoundedKeyedPool<const PathfindCell*, PathfindSearchRecord, PATHFIND_RECORD_CAPACITY> m_records;',
            'BoundedKeyedPool<const PathfindCell*, PathfindSearchRecord, PATHFIND_RECORD_CAPACITY,unsigned char> m_records;')
        source=source.replace('constexpr unsigned PATHFIND_RECORD_CAPACITY = 30000;','constexpr unsigned PATHFIND_RECORD_CAPACITY = 16;')
        main=r'''
int main(){PathfindCellInfo::allocateCellInfos();{PathfindCell cells[24];PathfindCell::registerSearchCells(cells,24);
 auto&c=mainPathfindSearchContext();SearchContextBinding<PathfindSearchContext> binding(c);std::mt19937 random(611);unsigned long long hash=0;
 const auto mix=[&](unsigned value){hash=hash*131+value;};
 for(unsigned phase=0;phase<600;++phase){c.beginSearch();PathfindSearchContext::AdmissionScope allowance(c,4);
  for(unsigned n=0;n<80;++n){unsigned key=random()%24,op=random()%5;
   if(op==0)c.releaseRecord(&cells[key]);
   else if(op==1){if(key<8)cells[key].setGoalUnit(cells[key].getGoalUnit()==INVALID_ID?17:INVALID_ID,{int(key),0});}
   else {auto*node=c.allocateRecord(&cells[key],{int(key),3},cells[key].m_info!=nullptr);
    mix(node!=nullptr);if(node){mix(c.m_records.index(node));mix(node->search().m_totalCost);mix(node->search().m_openSequence);
     node->search().m_totalCost=static_cast<UnsignedShort>(n*13);node->search().m_openSequence=n+1;
    }
   }
   mix(c.m_transientRecords);mix(c.m_records.size());
   for(unsigned k=0;k<24;++k){auto*node=c.findRecord(&cells[k]);mix(node!=nullptr);
    if(node){mix(c.m_records.index(node));mix(node->m_searchCharged);mix(node->search().m_totalCost);mix(node->search().m_openSequence);}
   }
  }
 }
 for(unsigned k=0;k<24;++k)cells[k].setGoalUnit(INVALID_ID,{int(k),0});
 c.releaseStorage();printf("%llu\n",hash);}
 pathfindSearchCellIndices().reset();PathfindCellInfo::releaseCellInfos();}
'''
        self.assertEqual(run_cpp(split_storage(source)+main,timeout=30).stdout,
                         run_cpp(source+main,timeout=30).stdout)

    # GeneralsX @test Codex 29/10/2026 Direct lookup changes identity resolution, never allocation order, credit or lifetime.
    def test_index_randomized_pool_equivalence_and_rollover(self):
        run_cpp(r'''
#include "boundedrecordindex.h"
#include "boundedkeyedpool.h"
#include <random>
struct Node{unsigned key=0;};
int main(){BoundedKeyedPool<unsigned,Node,32>pool;BoundedRecordIndex<32,64,unsigned char>index;
 std::mt19937 random(147);for(unsigned generation=0;generation<600;++generation){
  pool.beginGeneration();assert(index.beginSearch(128)&&index.size()==64&&index.bytes()==256);
  for(unsigned n=0;n<100;++n){unsigned key=random()%128;
   if(random()%3==0){pool.release(key);index.erase(key);}
   else if(auto*node=pool.acquire(key)){node->key=key;if(index.covers(key))index.publish(key,pool.index(node));}
   for(unsigned k=0;k<128;++k){auto*expected=pool.find(k);Node*actual=nullptr;
    if(!index.covers(k))actual=pool.find(k);
    else {auto slot=index.find(k);if(slot!=index.missing)actual=pool.atSlot(slot);}
    assert(actual==expected);if(actual)assert(actual->key==k);
   }
  }
 }
 index.releaseStorage();assert(!index.size()&&!index.bytes()&&!index.covers(0));
 BoundedRecordIndex<30000>maximum;assert(maximum.beginSearch(SearchCellIndices::invalid));
 assert(maximum.size()==262144&&maximum.bytes()==1048576);
}
''',timeout=30)

    def test_index_growth_failure_keeps_bounded_prefix_and_invalidates_old_slots(self):
        run_cpp(r'''
#include "boundedrecordindex.h"
#include <cstdlib>
bool failArray=false;
void*operator new[](std::size_t bytes){if(failArray)throw std::bad_alloc();if(auto*p=std::malloc(bytes))return p;throw std::bad_alloc();}
void operator delete[](void*p)noexcept{std::free(p);}
void operator delete[](void*p,std::size_t)noexcept{std::free(p);}
int main(){BoundedRecordIndex<32,128>index;assert(index.beginSearch(8));index.publish(3,7);assert(index.find(3)==7);
 failArray=true;assert(!index.beginSearch(64));failArray=false;
 assert(index.size()==8&&index.find(3)==index.missing&&!index.covers(8));
 index.publish(3,4);assert(index.find(3)==4);assert(index.beginSearch(64));
 assert(index.size()==64&&index.find(3)==index.missing);index.publish(63,31);assert(index.find(63)==31);
 SearchCellIndices ids;assert(ids.reserve(3)==0&&ids.reserve(2)==3&&ids.size()==5);
 assert(ids.reserve(SearchCellIndices::invalid)==SearchCellIndices::invalid&&ids.size()==5);
 ids.reset();assert(ids.reserve(2)==0&&ids.size()==2);
}
''')

    def test_index_registered_layers_recycling_admission_and_fallback(self):
        source=engine_fixture().replace('BoundedRecordIndex<PATHFIND_RECORD_CAPACITY> m_recordIndex;',
                                         'BoundedRecordIndex<PATHFIND_RECORD_CAPACITY,4> m_recordIndex;')
        run_cpp(source+r'''
int main(){PathfindCellInfo::allocateCellInfos();{
 PathfindCell ground[4],bridge[4],outside;PathfindCell::registerSearchCells(ground,4);PathfindCell::registerSearchCells(bridge,4);
 assert(ground[0].searchIndex()!=bridge[0].searchIndex());const auto id=ground[0].searchIndex();
 ground[0].reset();assert(ground[0].searchIndex()==id&&outside.searchIndex()==SearchCellIndices::invalid);
 auto&c=mainPathfindSearchContext();c.beginSearch();assert(c.m_recordIndex.size()==4);
 for(auto*cell:{ground,bridge,&outside}){auto*r=c.allocateRecord(cell,{3,4},false);assert(r);r->search().m_totalCost=cell==ground?11:22;}
 assert(ground[0].getTotalCost()==11&&bridge[0].getTotalCost()==22&&outside.getTotalCost()==22);
 auto*recycled=c.findRecord(ground);c.releaseRecord(ground);assert(!c.findRecord(ground));
 auto*next=c.allocateRecord(&ground[1],{5,6},false);assert(next==recycled&&!next->search().m_totalCost);
 assert(c.m_transientRecords==3);c.beginSearch();assert(!c.findRecord(&ground[1])&&!c.findRecord(bridge)&&!c.findRecord(&outside));
 ground[0].setGoalUnit(17,{3,4});assert(ground[0].allocateSearchInfo({3,4}));assert(!c.m_transientRecords);
 const auto*permanent=ground[0].m_info;assert(static_cast<const void*>(c.findRecord(ground))!=permanent&&ground[0].getGoalUnit()==17);
 ground[0].setGoalUnit(0,{3,4});c.releaseRecord(ground);
 c.releaseStorage();assert(!c.m_recordIndex.size()&&!c.m_recordIndex.bytes());
 }pathfindSearchCellIndices().reset();mainPathfindSearchContext().beginSearch();PathfindCellInfo::releaseCellInfos();
}
''')

    # GeneralsX @test Codex 29/10/2026 Private nodes own embedded state and cannot alias permanent records or move while linked.
    def test_compact_binding_and_context_stay_immovable(self):
        run_cpp(engine_fixture() + r'''
#include <type_traits>
struct FormerRecord{
 PathfindCell*cell;unsigned slot;PathfindSearchNodes*owner;bool charged;
 PathfindCellInfo*next;ICoord2D pos;ObjectID goal,posUnit,aircraft,obstacle;
 unsigned isFree:1;unsigned fence:1;unsigned transparent:1;
};
static_assert(!std::is_copy_constructible<PathfindSearchContext>::value,"bound states cannot move");
static_assert(!std::is_move_constructible<PathfindSearchContext>::value,"bound states cannot move");
static_assert(!std::is_base_of<PathfindSearchNodes,PathfindSearchContext>::value,"compact contexts must not retain the split state arena");
static_assert(sizeof(PathfindSearchRecord)<=64,"host fixture nodes should fit 64 bytes");
static_assert(sizeof(PathfindSearchContext)<3*1024*1024,"the redundant state arena must be removed");
static_assert(sizeof(PathfindCellInfo)<sizeof(FormerRecord),"direct binding must reduce record storage");
int main(){PathfindCellInfo::allocateCellInfos();
 {PathfindCell cell;cell.setGoalUnit(17,{2,3});auto*permanent=cell.m_info;
  static_assert(!std::is_same<PathfindSearchRecord,PathfindCellInfo>::value,"permanent and private storage must be different types");
  auto&c=mainPathfindSearchContext();auto*r=cell.searchInfo();
  assert(static_cast<void*>(r)!=permanent);
  assert(static_cast<PathfindSearchState*>(r)==&r->search() && !r->m_searchCharged);
  r->search().m_totalCost=91;assert(cell.getTotalCost()==91 && cell.getGoalUnit()==17);
  cell.setGoalUnit(0,{2,3});assert(!cell.m_info && cell.getTotalCost()==91);
  cell.releaseSearchInfo();assert(!c.m_records.size());
 }
 mainPathfindSearchContext().releaseStorage();PathfindCellInfo::releaseCellInfos();
 printf("former_record=%zu record=%zu state=%zu context=%zu\n",sizeof(FormerRecord),sizeof(PathfindCellInfo),sizeof(PathfindSearchState),sizeof(PathfindSearchContext));
}
''')

    def test_direct_state_recycling_and_generation_do_not_leak_search_flags(self):
        run_cpp(engine_fixture() + r'''
int main(){PathfindCellInfo::allocateCellInfos();auto&c=mainPathfindSearchContext();
 {PathfindCell a,b;
  for(unsigned pass=0;pass<600;++pass){c.beginSearch();
   auto*first=c.allocateRecord(&a,{2,3},false);assert(first);auto*state=&first->search();
   assert(!state->m_pathParent && !state->m_open && !state->m_closed && state->m_openIndex==-1);
   state->m_totalCost=44;state->m_blockedByAlly=true;state->m_openSequence=99;
   c.releaseRecord(&a);assert(!c.findRecord(&a) && !c.m_transientRecords);
   auto*recycled=c.allocateRecord(&b,{4,5},false);
   assert(recycled==first && &recycled->search()==state && !state->m_totalCost && !state->m_blockedByAlly && !state->m_openSequence);
   assert(static_cast<PathfindSearchState*>(recycled)==&recycled->search());
   state->m_closed=true;state->m_openIndex=17;state->m_pathParent=recycled;
   c.beginSearch();assert(!c.findRecord(&b) && !c.m_records.size() && !c.m_transientRecords);
   auto*next=c.allocateRecord(&a,{7,8},false);
   assert(next==first && &next->search()==state && !state->m_closed && state->m_openIndex==-1 && !state->m_pathParent);
   c.releaseRecord(&a);
  }
 }
 c.releaseStorage();PathfindCellInfo::releaseCellInfos();
}
''')

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
  auto*persistent=unit.m_info;assert(persistent && unit.hasSearchInfo());
  auto*search=unit.searchInfo();assert(static_cast<void*>(search)!=persistent);
  unit.setTotalCost(44);unit.setBlockedByAlly(true);
  assert(empty.allocateSearchInfo({8,8}));empty.setTotalCost(99);
  empty.setGoalUnit(27,{8,8});assert(empty.m_info && empty.m_info!=static_cast<void*>(empty.searchInfo()));
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
