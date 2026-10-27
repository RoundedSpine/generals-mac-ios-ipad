#!/usr/bin/env python3
"""Exercise explicit scratch ownership with real cell/list/corridor operations."""
# GeneralsX @refactor Codex 27/10/2026 Verify independent selected contexts and captured admission on actual records.
import sys
import unittest
from functools import partial
from compiled_harness import run_cpp
from test_search_record_pool import engine_fixture
from test_search_context import function


def fixture():
    return engine_fixture() + r'''
#include <atomic>
#include <memory>
#include <thread>
#include <stdexcept>
using Binding=SearchContextBinding<PathfindSearchContext>;
'''


class BindingTests(unittest.TestCase):
    def test_cell_records_nested_bindings_and_exception_restore(self):
        run_cpp(fixture() + r'''
int main(){PathfindCellInfo::allocateCellInfos();
 auto a=std::make_unique<PathfindSearchContext>(),b=std::make_unique<PathfindSearchContext>();
 PathfindCell cell;assert(&activePathfindSearchContext()==&mainPathfindSearchContext());
 assert(cell.allocateSearchInfo({2,3}));cell.setCostSoFar(11);
 {
  Binding first(*a);PathfindSearchContext::AdmissionScope admission(*a,0);
  assert(cell.allocateSearchInfo({2,3}));cell.setCostSoFar(21);
  {Binding same(*a);assert(cell.getCostSoFar()==21);}
  try{Binding second(*b);assert(cell.allocateSearchInfo({2,3}));cell.setCostSoFar(31);throw std::runtime_error("leave");}
  catch(const std::runtime_error&){}
  assert(&activePathfindSearchContext()==a.get()&&cell.getCostSoFar()==21);
  cell.releaseSearchInfo();assert(!a->m_records.size());
 }
 assert(cell.getCostSoFar()==11&&!a->m_hasAdmissionSnapshot);
 {Binding second(*b);assert(cell.getCostSoFar()==31);cell.releaseSearchInfo();}
 assert(!Binding::current());cell.releaseSearchInfo();
 mainPathfindSearchContext().releaseStorage();PathfindCellInfo::releaseCellInfos();
}
''')

    def test_one_context_rejects_another_thread_then_can_transfer(self):
        run_cpp(fixture() + r'''
int main(){auto context=std::make_unique<PathfindSearchContext>();std::atomic<bool> rejected{false},transferred{false};
 {
  Binding owned(*context);
  std::thread other([&]{try{Binding conflict(*context);}catch(const std::logic_error&){rejected=true;}assert(!Binding::current());});
  other.join();assert(rejected&&Binding::current()==context.get());
 }
 std::thread next([&]{Binding owned(*context);transferred=Binding::current()==context.get();});next.join();
 assert(transferred&&!Binding::current()&&!context->m_ownership.owner.load());
}
''')

    def test_parallel_private_records_do_not_read_live_pool_admission(self):
        run_cpp(fixture() + r'''
int main(){PathfindCellInfo::allocateCellInfos();
 PathfindCell one,two,mainCell;
 auto a=std::make_unique<PathfindSearchContext>(),b=std::make_unique<PathfindSearchContext>();
 std::atomic<unsigned> ready{0};std::atomic<bool> go{false};
 auto search=[&](PathfindSearchContext&context,unsigned count,unsigned cost){
  Binding selected(context);PathfindSearchContext::AdmissionScope admission(context,count);
  ++ready;while(!go.load())std::this_thread::yield();
  for(unsigned i=0;i<2000;++i){context.beginSearch();
   assert(one.allocateSearchInfo({3,4}));one.setCostSoFar(cost);
   if(count==PATHFIND_RECORD_CAPACITY-1)assert(!two.allocateSearchInfo({4,4}));
   else{assert(two.allocateSearchInfo({4,4}));two.setParentCell(&one);assert(two.getParentCell()==&one);two.releaseSearchInfo();}
   assert(one.getCostSoFar()==cost);one.releaseSearchInfo();
  }
 };
 std::thread first(search,std::ref(*a),PATHFIND_RECORD_CAPACITY-2,17);
 std::thread second(search,std::ref(*b),PATHFIND_RECORD_CAPACITY-1,29);
 while(ready.load()!=2)std::this_thread::yield();go=true;
 // Different permanent cell: global permanent allocation churn must not be read by captured admission.
 for(int i=0;i<20000;++i){assert(mainCell.allocateInfo({8,8}));mainCell.releaseInfo();}
 first.join();second.join();assert(!one.m_info&&!two.m_info);
 assert(!a->m_records.size()&&!b->m_records.size()&&PathfindSearchContext::permanentRecordsInUse()==0);
 PathfindCellInfo::releaseCellInfos();
}
''')

    def test_admission_scope_restores_and_survives_generation_changes(self):
        run_cpp(fixture() + r'''
int main(){PathfindCellInfo::allocateCellInfos();auto context=std::make_unique<PathfindSearchContext>();PathfindCell cell,other;
 bool rejected=false;
 try{PathfindSearchContext::AdmissionScope unbound(*context,0);}catch(const std::logic_error&){rejected=true;}
 assert(rejected&&!context->m_hasAdmissionSnapshot);
 Binding selected(*context);assert(!context->m_hasAdmissionSnapshot);
 rejected=false;try{PathfindSearchContext::AdmissionScope invalid(*context,PATHFIND_RECORD_CAPACITY+1);}catch(const std::invalid_argument&){rejected=true;}
 assert(rejected&&!context->m_hasAdmissionSnapshot);
 {PathfindSearchContext::AdmissionScope outer(*context,PATHFIND_RECORD_CAPACITY);context->beginSearch();
  assert(!cell.allocateSearchInfo({1,1}));
  {PathfindSearchContext::AdmissionScope inner(*context,0);assert(cell.allocateSearchInfo({1,1}));cell.releaseSearchInfo();}
  assert(context->m_hasAdmissionSnapshot&&context->m_permanentAdmission==PATHFIND_RECORD_CAPACITY);
  assert(!cell.allocateSearchInfo({1,1}));
  // Permanent metadata can still obtain a shadow at the limit; it does not consume transient credit.
  assert(other.allocateInfo({2,2}));assert(other.allocateSearchInfo({2,2}));other.releaseSearchInfo();other.releaseInfo();
 }
 assert(!context->m_hasAdmissionSnapshot&&cell.allocateSearchInfo({1,1}));cell.releaseSearchInfo();
 context->releaseStorage();PathfindCellInfo::releaseCellInfos();
}
''')

    def test_actual_corridor_helpers_select_bound_context(self):
        methods = '\n'.join(function(marker) for marker in [
            'void PathfindZoneManager::clearPassableFlags()', 'void PathfindZoneManager::setAllPassable()',
            'void PathfindZoneManager::setPassable(', 'Bool PathfindZoneManager::isPassable(',
            'Bool PathfindZoneManager::clipIsPassable('])
        run_cpp(fixture() + r'''
struct PathfindZoneManager{
 enum{ZONE_BLOCK_SIZE=10};ICoord2D m_zoneBlockExtent{2,2};
 void clearPassableFlags();void setAllPassable();void setPassable(int,int,bool);
 bool isPassable(int,int)const;bool clipIsPassable(int,int)const;
};
''' + methods + r'''
int main(){auto a=std::make_unique<PathfindSearchContext>(),b=std::make_unique<PathfindSearchContext>();
 a->resizeCorridor(4);b->resizeCorridor(4);mainPathfindSearchContext().resizeCorridor(4);PathfindZoneManager zones;
 {Binding selected(*a);zones.clearPassableFlags();zones.setPassable(12,2,true);assert(zones.isPassable(12,2)&&!zones.isPassable(2,12));}
 {Binding selected(*b);assert(zones.isPassable(2,12));zones.setPassable(12,2,false);assert(!zones.clipIsPassable(12,2));}
 {Binding selected(*a);assert(zones.isPassable(12,2)&&!zones.clipIsPassable(2,12));zones.setAllPassable();}
 assert(zones.isPassable(12,2)&&zones.isPassable(2,12));mainPathfindSearchContext().releaseStorage();
}
''')


if __name__ == '__main__':
    if '--tsan' in sys.argv:
        sys.argv.remove('--tsan')
        run_cpp = partial(run_cpp, extra_flags=('-O1', '-g', '-fsanitize=thread'))
    unittest.main()
