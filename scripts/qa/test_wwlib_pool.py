#!/usr/bin/env python3
"""Compile the production WWLib pool with platform locks replaced by std::mutex."""
# GeneralsX @test Codex 01/11/2026 Cover aligned payloads, chunk links, reuse, destruction and concurrent borrowers.
import re
import unittest
from compiled_harness import ROOT, run_cpp


def fixture():
    source = (ROOT / 'Core/Libraries/Source/WWVegas/WWLib/mempool.h').read_text()
    source = re.sub(r'^#(?:include|pragma once)[^\n]*', '', source, flags=re.M)
    return r'''
#include <new>
#include <cstdint>
#include <cstddef>
#include <cassert>
#include <mutex>
#include <vector>
#include <array>
#include <thread>
#include <atomic>
#define WWASSERT(value) assert(value)
struct FastCriticalSectionClass {
 std::mutex mutex;
 struct LockClass {std::lock_guard<std::mutex> lock;explicit LockClass(FastCriticalSectionClass&cs):lock(cs.mutex){}};
};
''' + source + r'''
template<class T,int Count>struct Pool:ObjectPoolClass<T,Count>{
 int capacity()const{return this->TotalObjectCount;}
 int freeCount()const{return this->FreeObjectCount;}
 unsigned chunks()const{unsigned count=0;for(auto*b=this->BlockListHead;b;b=b->Next)++count;return count;}
};
'''


class PoolTests(unittest.TestCase):
    def test_alignment_chunk_links_payloads_and_peak_reuse(self):
        run_cpp(fixture() + r'''
template<unsigned Alignment>struct alignas(Alignment) Node{std::uint64_t value=0;};
template<unsigned Alignment>void exercise(){
 Pool<Node<Alignment>,7> pool;
 std::vector<Node<Alignment>*> nodes;
 for(unsigned i=0;i<100;++i){auto*n=pool.Allocate_Object();
  assert(reinterpret_cast<std::uintptr_t>(n)%alignof(Node<Alignment>)==0);
  n->value=i+1;nodes.push_back(n);}
 assert(pool.capacity()==105&&pool.chunks()==15&&pool.freeCount()==5);
 for(unsigned i=0;i<nodes.size();++i){assert(nodes[i]->value==i+1);pool.Free_Object(nodes[i]);}
 assert(pool.freeCount()==105);
 for(unsigned i=0;i<10000;++i){auto*n=pool.Allocate_Object();assert(n->value==0);pool.Free_Object(n);}
 assert(pool.capacity()==105&&pool.chunks()==15&&pool.freeCount()==105);
}
int main(){exercise<8>();exercise<16>();exercise<64>();}
''')

    def test_byte_aligned_slot_still_aligns_free_list_pointers(self):
        run_cpp(fixture() + r'''
struct Node{unsigned char bytes[sizeof(void*)+1];};
int main(){Pool<Node,3> pool;std::array<Node*,10> nodes;
 for(auto&n:nodes){n=pool.Allocate_Object();assert(reinterpret_cast<std::uintptr_t>(n)%alignof(void*)==0);}
 for(auto*n:nodes)pool.Free_Object(n);
 assert(pool.freeCount()==pool.capacity());}
''')

    def test_auto_pool_runs_destructors_and_supports_multiple_chunks(self):
        run_cpp(fixture() + r'''
struct alignas(32) AutoNode:AutoPoolClass<AutoNode,4>{
 static unsigned live;std::uint64_t value=12;
 AutoNode(){++live;}~AutoNode(){assert(value==12);--live;}
};
unsigned AutoNode::live=0;
DEFINE_AUTO_POOL(AutoNode,4);
int main(){std::array<AutoNode*,53> nodes;
 for(auto&n:nodes){n=new AutoNode;assert(reinterpret_cast<std::uintptr_t>(n)%alignof(AutoNode)==0);}
 assert(AutoNode::live==53);for(auto*n:nodes)delete n;assert(AutoNode::live==0);
 for(unsigned i=0;i<10000;++i){auto*n=new AutoNode;delete n;}assert(AutoNode::live==0);}
''')

    def test_concurrent_allocate_free_preserves_all_slots(self):
        run_cpp(fixture() + r'''
struct alignas(16) Node{std::uint64_t value=0;};
int main(){Pool<Node,8> pool;std::array<std::thread,4> threads;std::atomic<bool> go{false};
 for(unsigned id=0;id<threads.size();++id)threads[id]=std::thread([&,id]{
  while(!go.load())std::this_thread::yield();
  for(unsigned i=0;i<10000;++i){auto*n=pool.Allocate_Object();n->value=id;
   assert(n->value==id);pool.Free_Object(n);}});
 go=true;for(auto&t:threads)t.join();assert(pool.capacity()==8&&pool.freeCount()==8&&pool.chunks()==1);}
''')


if __name__ == '__main__':
    unittest.main()
