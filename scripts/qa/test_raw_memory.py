#!/usr/bin/env python3
"""Compile the production raw-DMA snapshot with allocator and native-size providers."""
# GeneralsX @test Codex 01/11/2026 Verify lock-safe live-list coverage, size buckets, wide totals and release/reset accounting without changing allocation paths.
import unittest
from compiled_harness import ROOT, run_cpp


def fixture():
    source = (ROOT / 'Core/GameEngine/Source/Common/System/GameMemory.cpp').read_text()
    start = source.index('void MemoryPoolFactory::getRawMemoryUsage(')
    body = source[start:source.index('\n}', start) + 2]
    return r'''
#include "Common/MemoryPoolUsage.h"
#include <cassert>
#include <cstring>
#include <vector>
#include <mutex>
#include <thread>
#include <atomic>
std::mutex TheDmaCriticalSection;thread_local unsigned held=0;
struct ScopedCriticalSection{std::lock_guard<std::mutex>lock;
 explicit ScopedCriticalSection(std::mutex&mutex):lock(mutex){assert(!held);++held;}
 ~ScopedCriticalSection(){--held;}};
struct MemoryPoolSingleBlock{MemoryPoolSingleBlock*next=nullptr;size_t nativeSize=0;
 MemoryPoolSingleBlock*getNextRawBlock(){assert(held==1);return next;}};
struct DynamicMemoryAllocator{DynamicMemoryAllocator*next=nullptr;MemoryPoolSingleBlock*head=nullptr;
 DynamicMemoryAllocator*getNextDmaInList(){assert(held==1);return next;}
 MemoryPoolSingleBlock*getFirstRawBlock()const{assert(held==1);return head;}};
struct MemoryPoolFactory{DynamicMemoryAllocator*m_firstDmaInFactory=nullptr;
 void getRawMemoryUsage(RawMemoryUsage&,MemoryAllocationSizeQuery=nullptr);};
size_t calls=0;std::vector<const void*>allowed;
size_t nativeSize(const void*address){assert(held==1);
 bool base=false;for(auto*p:allowed)if(p==address)base=true;assert(base);++calls;
 return static_cast<const MemoryPoolSingleBlock*>(address)->nativeSize;}
BODY
'''.replace('BODY', body)


class RawMemoryTests(unittest.TestCase):
    def test_empty_allocators_clear_the_previous_sample(self):
        run_cpp(fixture() + r'''
int main(){MemoryPoolFactory factory;RawMemoryUsage usage;std::memset(&usage,0xff,sizeof(usage));
 factory.getRawMemoryUsage(usage,nativeSize);
 assert(usage.allocators==0&&usage.liveBlocks==0&&usage.allocatedBytes==0&&usage.largestBlock==0&&usage.unmeasuredBlocks==0);
 for(auto n:usage.sizeBuckets)assert(n==0);assert(calls==0&&held==0);
 DynamicMemoryAllocator a,b;a.next=&b;factory.m_firstDmaInFactory=&a;factory.getRawMemoryUsage(usage,nativeSize);
 assert(usage.allocators==2&&usage.liveBlocks==0&&usage.allocatedBytes==0&&calls==0);}
''', ['-I', str(ROOT / 'Core/GameEngine/Include')])

    def test_multiple_allocator_lists_cover_each_base_pointer_and_wide_totals(self):
        run_cpp(fixture() + r'''
int main(){MemoryPoolFactory factory;DynamicMemoryAllocator a,b;MemoryPoolSingleBlock x,y,z;
 x.next=&y;x.nativeSize=8192;y.nativeSize=5ull*1024*1024*1024;z.nativeSize=16384;
 a.next=&b;a.head=&x;b.head=&z;factory.m_firstDmaInFactory=&a;allowed={&x,&y,&z};
 RawMemoryUsage usage{};factory.getRawMemoryUsage(usage,nativeSize);
 assert(usage.allocators==2&&usage.liveBlocks==3&&calls==3&&held==0);
 assert(usage.allocatedBytes==5ull*1024*1024*1024+24576&&usage.largestBlock==y.nativeSize);
 assert(usage.unmeasuredBlocks==0&&usage.sizeBuckets[1]==2&&usage.sizeBuckets[5]==1);
 assert(a.head==&x&&x.next==&y&&b.head==&z);}
''', ['-I', str(ROOT / 'Core/GameEngine/Include')])

    def test_size_bucket_boundaries_use_usable_size_including_headers(self):
        run_cpp(fixture() + r'''
int main(){const size_t sizes[]={4096,4097,16384,16385,65536,65537,262144,262145,1048576,1048577};
 MemoryPoolSingleBlock blocks[10];size_t total=0;
 for(size_t i=0;i<10;++i){blocks[i].nativeSize=sizes[i];blocks[i].next=i+1<10?&blocks[i+1]:nullptr;allowed.push_back(&blocks[i]);total+=sizes[i];}
 DynamicMemoryAllocator allocator;allocator.head=blocks;MemoryPoolFactory factory;factory.m_firstDmaInFactory=&allocator;
 RawMemoryUsage usage{};factory.getRawMemoryUsage(usage,nativeSize);
 assert(usage.liveBlocks==10&&usage.allocatedBytes==total&&usage.largestBlock==1048577&&calls==10);
 const size_t expected[]={1,2,2,2,2,1};for(size_t i=0;i<6;++i)assert(usage.sizeBuckets[i]==expected[i]);}
''', ['-I', str(ROOT / 'Core/GameEngine/Include')])

    def test_missing_or_unmeasurable_sizes_preserve_counts_and_report_partial_coverage(self):
        run_cpp(fixture() + r'''
int main(){MemoryPoolSingleBlock x,y;x.next=&y;x.nativeSize=0;y.nativeSize=4096;allowed={&x,&y};
 DynamicMemoryAllocator allocator;allocator.head=&x;MemoryPoolFactory factory;factory.m_firstDmaInFactory=&allocator;
 RawMemoryUsage usage{};factory.getRawMemoryUsage(usage);
 assert(usage.liveBlocks==2&&usage.unmeasuredBlocks==2&&usage.allocatedBytes==0&&usage.largestBlock==0&&calls==0);
 factory.getRawMemoryUsage(usage,nativeSize);
 assert(usage.liveBlocks==2&&usage.unmeasuredBlocks==1&&usage.allocatedBytes==4096&&usage.largestBlock==4096&&calls==2);
 assert(usage.sizeBuckets[0]==1);for(size_t i=1;i<6;++i)assert(usage.sizeBuckets[i]==0);}
''', ['-I', str(ROOT / 'Core/GameEngine/Include')])

    def test_unlink_free_and_allocator_teardown_do_not_leave_stale_totals(self):
        run_cpp(fixture() + r'''
int main(){MemoryPoolFactory factory;DynamicMemoryAllocator allocator;factory.m_firstDmaInFactory=&allocator;
 auto*x=new MemoryPoolSingleBlock;auto*y=new MemoryPoolSingleBlock;x->nativeSize=8192;y->nativeSize=32768;x->next=y;
 allocator.head=x;allowed={x,y};RawMemoryUsage usage{};factory.getRawMemoryUsage(usage,nativeSize);assert(usage.liveBlocks==2);
 {ScopedCriticalSection lock(TheDmaCriticalSection);allocator.head=y;delete x;}
 allowed={y};factory.getRawMemoryUsage(usage,nativeSize);assert(usage.liveBlocks==1&&usage.allocatedBytes==32768);
 {ScopedCriticalSection lock(TheDmaCriticalSection);allocator.head=nullptr;delete y;}
 allowed.clear();factory.getRawMemoryUsage(usage,nativeSize);assert(usage.liveBlocks==0&&usage.allocatedBytes==0&&usage.largestBlock==0);
 factory.m_firstDmaInFactory=nullptr;factory.getRawMemoryUsage(usage,nativeSize);assert(usage.allocators==0);}
''', ['-I', str(ROOT / 'Core/GameEngine/Include')])

    def test_snapshot_and_allocator_mutation_share_the_same_lock(self):
        run_cpp(fixture() + r'''
int main(){MemoryPoolFactory factory;DynamicMemoryAllocator allocator;factory.m_firstDmaInFactory=&allocator;
 MemoryPoolSingleBlock block;block.nativeSize=8192;allowed={&block};std::atomic<bool>go{false};
 std::thread writer([&]{while(!go.load())std::this_thread::yield();for(unsigned i=0;i<10000;++i){
  ScopedCriticalSection lock(TheDmaCriticalSection);allocator.head=i%2?&block:nullptr;}});
 go=true;for(unsigned i=0;i<10000;++i){RawMemoryUsage usage{};factory.getRawMemoryUsage(usage,nativeSize);
  assert(usage.liveBlocks<=1&&usage.allocatedBytes==usage.liveBlocks*8192&&usage.unmeasuredBlocks==0);}
 writer.join();assert(held==0);}
''', ['-I', str(ROOT / 'Core/GameEngine/Include')])


if __name__ == '__main__':
    unittest.main()
