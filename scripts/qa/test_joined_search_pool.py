#!/usr/bin/env python3
"""Verify bounded dynamic claims, joined failures, FP propagation and pool lifecycle; add --tsan or --asan."""
# GeneralsX @feature Codex 31/10/2026 Test pool contracts independently of engine fixtures and physical task assignment.
import sys
import unittest
from functools import partial
from compiled_harness import run_cpp

PREFIX=r'''
#include "joinedsearchpool.h"
#include <cassert>
#include <vector>
'''


class JoinedSearchPoolTests(unittest.TestCase):
    def test_bounded_exactly_once_claims_and_zero_worker_equivalence(self):
        run_cpp(PREFIX+r'''
int main(){for(unsigned workers:{0,1,2}){JoinedSearchPool pool(workers);
 for(unsigned repeat=0;repeat<1000;++repeat){std::array<std::atomic<unsigned>,4> calls{};std::array<unsigned,4>values{};
  pool.run(4,[&](unsigned job,unsigned participant){assert(participant<=workers);assert(ExclusiveSearchWorker::onWorker()==(participant!=0));
   ++calls[job];values[job]=(job+1)*2654435761u;});
  unsigned sum=0;for(unsigned p=0;p<=workers;++p)sum+=pool.completedBy(p);assert(sum==4);
  for(unsigned j=0;j<4;++j)assert(calls[j]==1&&pool.completed(j)&&values[j]==(j+1)*2654435761u&&pool.participant(j)<=workers);
 }
 pool.run(0,{});for(unsigned p=0;p<=workers;++p)assert(pool.completedBy(p)==0);
}}
''',timeout=45)

    def test_three_participants_overlap_and_claim_successive_jobs(self):
        run_cpp(PREFIX+r'''
int main(){JoinedSearchPool pool(2);std::atomic<unsigned> entered{0};std::atomic<bool> last{false};
 pool.run(4,[&](unsigned job,unsigned){
  if(job<3){++entered;while(entered.load()<3)std::this_thread::yield();if(job==0)while(!last.load())std::this_thread::yield();}
  else last=true;
 });
 assert(last&&entered==3);unsigned busy=0;for(unsigned p=0;p<3;++p){assert(pool.completedBy(p)>0);if(pool.completedBy(p)>1)++busy;}
 assert(busy==1);
}
''')

    def test_errors_join_all_work_then_choose_logical_job_order(self):
        run_cpp(PREFIX+r'''
int main(){JoinedSearchPool pool(2);std::atomic<bool> second{false};std::atomic<unsigned> successes{0};bool caught=false;
 try{pool.run(4,[&](unsigned job,unsigned){
  if(job==0){while(!second.load())std::this_thread::yield();throw std::logic_error("logical zero");}
  if(job==1){second=true;throw std::bad_alloc();}++successes;
 });}catch(const std::logic_error&e){caught=std::string(e.what())=="logical zero";}
 assert(caught&&successes==2&&!pool.completed(0)&&!pool.completed(1)&&pool.completed(2)&&pool.completed(3));
 pool.run(4,[](unsigned,unsigned){});for(unsigned j=0;j<4;++j)assert(pool.completed(j));
}
''')

    def test_fp_changes_propagate_per_job_and_restore_through_errors(self):
        run_cpp(PREFIX+r'''
int main(){JoinedSearchPool pool(2);for(int mode:{FE_DOWNWARD,FE_UPWARD,FE_TONEAREST}){
 std::fesetround(mode);pool.run(4,[&](unsigned,unsigned){assert(std::fegetround()==mode);std::fesetround(FE_TOWARDZERO);});
 assert(std::fegetround()==mode);
 bool caught=false;try{pool.run(4,[&](unsigned job,unsigned){assert(std::fegetround()==mode);std::fesetround(FE_TOWARDZERO);if(job==1)throw 19;});}
 catch(int n){caught=n==19;}assert(caught&&std::fegetround()==mode&&!ExclusiveSearchWorker::onWorker());
}}
''')

    def test_cancellation_skips_unstarted_work_but_joins_started_callbacks(self):
        run_cpp(PREFIX+r'''
int main(){JoinedSearchPool pool(2);std::atomic<bool> allow{true};std::atomic<unsigned> entered{0},exited{0};
 pool.run(4,[&](unsigned job,unsigned){assert(job<3);++entered;while(entered.load()<3)std::this_thread::yield();allow=false;++exited;},[&]{return allow.load();});
 assert(pool.cancelled()&&exited==3&&!pool.completed(3));for(unsigned j=0;j<3;++j)assert(pool.completed(j));
 allow=true;pool.run(4,[](unsigned,unsigned){},[&]{return allow.load();});assert(!pool.cancelled());
}
''')

    def test_owner_nesting_stop_and_bounds(self):
        run_cpp(PREFIX+r'''
int main(){JoinedSearchPool pool(1),other(0);bool caught=false;
 std::thread foreign([&]{try{pool.run(1,[](unsigned,unsigned){});}catch(const std::logic_error&){caught=true;}});foreign.join();assert(caught);
 pool.run(2,[&](unsigned,unsigned){bool nested=false;try{other.run(1,[](unsigned,unsigned){});}catch(const std::logic_error&){nested=true;}assert(nested);});
 caught=false;try{pool.run(5,[](unsigned,unsigned){});}catch(const std::invalid_argument&){caught=true;}assert(caught);
 caught=false;try{pool.run(1,{});}catch(const std::invalid_argument&){caught=true;}assert(caught);
 caught=false;try{JoinedSearchPool invalid(3);}catch(const std::invalid_argument&){caught=true;}assert(caught);
 pool.stop();pool.stop();caught=false;try{pool.run(1,[](unsigned,unsigned){});}catch(const std::logic_error&){caught=true;}assert(caught);
}
''')

    def test_partial_thread_construction_joins_before_unwinding(self):
        run_cpp(PREFIX+r'''
int main(){std::atomic<unsigned> alive{0};unsigned created=0;bool caught=false;
 try{JoinedSearchPool pool(2,[&](std::function<void()> entry){
  if(created++==1)throw std::system_error(std::make_error_code(std::errc::resource_unavailable_try_again));
  return std::thread([&,entry=std::move(entry)]{++alive;entry();--alive;});
 });}catch(const std::system_error&){caught=true;}
 assert(caught&&created==2&&alive==0);
 caught=false;try{JoinedSearchPool pool(1,[](std::function<void()>){return std::thread{};});}catch(const std::logic_error&){caught=true;}assert(caught);
}
''')


if __name__=='__main__':
    if '--tsan' in sys.argv:run_cpp=partial(run_cpp,extra_flags=('-fsanitize=thread','-g','-O1'))
    if '--asan' in sys.argv:run_cpp=partial(run_cpp,extra_flags=('-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-O1'))
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(JoinedSearchPoolTests))
    sys.exit(not result.wasSuccessful())
