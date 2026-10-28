#!/usr/bin/env python3
"""Compare production heap/list operations without changing search or allocation rules."""
# GeneralsX @test Codex 26/10/2026 Check stable ties, changed-cost removal, retail fallback and reuse.
import unittest
import re
from compiled_harness import ROOT, run_cpp

HEADER = (ROOT / 'Core/GameEngine/Include/GameLogic/AIPathfind.h').read_text()
SOURCE = (ROOT / 'Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp').read_text()


def function(marker):
    start = SOURCE.index(marker)
    return SOURCE[start:SOURCE.index('\n}', start) + 2]


def fixture(retail, fixed, context=False):
    state = HEADER[HEADER.index('class PathfindCellInfo;'):HEADER.index('class PathfindCellInfo\n')]
    info = HEADER[HEADER.index('class PathfindCellInfo\n'):HEADER.index('// TheSuperHackers @info The PathfindCellList')]
    queue = HEADER[HEADER.index('class PathfindCellList\n'):HEADER.index('/**\n * This represents one cell')]
    # Expose fields only in the fixture for independent invariant checks.
    info = info.replace('protected:', 'public:')
    queue = queue.replace('private:', 'public:')
    methods = SOURCE[SOURCE.index('Bool PathfindCellList::before('):SOURCE.index('//-----------------------------------------------------------------------------------', SOURCE.index('Bool PathfindCellList::before('))]
    operations = SOURCE[SOURCE.index('#if RETAIL_COMPATIBLE_PATHFINDING\n// Retail compatible insertion sort'):SOURCE.index('/// remove all cells from "closed" list', SOURCE.index('// Retail compatible insertion sort'))]
    source = ('#define GENERALS_ZH_SEARCH_CONTEXT 1\n' if context else '') + f'#define RETAIL_COMPATIBLE_PATHFINDING {retail}\n' + r'''
#include <vector>
#include <random>
#include <cassert>
#include <set>
#include <algorithm>
#include <cstdlib>
#define FALSE false
#define TRUE true
#define DEBUG_ASSERTCRASH(c,m) assert(c)
using Bool=bool; using Int=int; using UnsignedInt=unsigned; using UnsignedShort=unsigned short; using ObjectID=unsigned;
constexpr ObjectID INVALID_ID=0;
struct ICoord2D {int x,y;};
class PathfindCell;
constexpr unsigned PATHFIND_CELLS_PER_FRAME=5000;
bool s_useFixedPathfinding=''' + ('true' if fixed else 'false') + '; bool s_forceCleanCells=false;\n' + '#include "stampedsearchcontext.h"\n#include "boundedkeyedpool.h"\n#include "searchcontextbinding.h"\n' + state + info + queue + r'''
class PathfindCell {
public:
 PathfindCellInfo* m_info=nullptr;
 PathfindCellInfo*searchInfo(){return m_info;}
 void releaseSearchInfo(){releaseInfo();}
 int id=0, releases=0;
 PathfindCell* getNextOpen(){return m_info->m_nextOpen?m_info->m_nextOpen->m_cell:nullptr;}
 PathfindCell* getPrevOpen(){return m_info->m_prevOpen?m_info->m_prevOpen->m_cell:nullptr;}
 unsigned getTotalCostDifference(PathfindCell& c) const {return std::abs(int(m_info->m_totalCost)-int(c.m_info->m_totalCost));}
 void forwardInsertionSortRetailCompatible(PathfindCellList&);
 void forwardInsertionSort(PathfindCellList&);
 void reverseInsertionSort(PathfindCellList&);
 void putOnSortedOpenList(PathfindCellList&);
 void removeFromOpenList(PathfindCellList&);
 static Int releaseOpenList(PathfindCellList&);
 void releaseInfo(){++releases; assert(!m_info->m_open);}
};
''' + methods + operations + r'''
struct Arena {
 std::vector<PathfindCell> cells;
 std::vector<PathfindCellInfo> info;
 PathfindCellList queue;
 Arena(bool heap, int n):cells(n),info(n),queue(heap){
  for(int i=0;i<n;++i){cells[i].id=i;cells[i].m_info=&info[i];
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 static unsigned nextSlot=0;info[i].m_searchState=&mainPathfindSearchNodes().resetSlot((nextSlot++)%PATHFIND_RECORD_CAPACITY);
#endif
info[i].m_cell=&cells[i];info[i].m_openIndex=-1;}
 }
 void insert(int i,unsigned cost){info[i].m_totalCost=cost;cells[i].putOnSortedOpenList(queue);}
 void remove(int i){cells[i].removeFromOpenList(queue);}
 int head(){return queue.empty()?-1:queue.getHead()->id;}
 void check(){
  if(queue.m_heapActive){
   for(size_t i=0;i<queue.m_heap.size();++i){assert(queue.m_heap[i]->m_openIndex==int(i));if(i)assert(!queue.before(queue.m_heap[i],queue.m_heap[(i-1)/2]));}
  }
 }
};
void compare(Arena& a,Arena& b){assert(a.head()==b.head());a.check();}
void randomized(){
 for(unsigned seed=0;seed<8;++seed){
  std::mt19937 random(seed);Arena heap(true,512),list(false,512);
  for(int step=0;step<8000;++step){
   int id=random()%512;unsigned cost=random()%64;
   if(heap.info[id].m_open){
    // Engine callers can update cost before removing the existing node.
    heap.info[id].m_totalCost=list.info[id].m_totalCost=cost;
    heap.remove(id);list.remove(id);
   }
   if(random()%4){heap.insert(id,cost);list.insert(id,cost);}
   compare(heap,list);
   if(!heap.queue.empty() && random()%3==0){int id=heap.head();heap.remove(id);list.remove(id);}
   compare(heap,list);
  }
  while(!heap.queue.empty()){compare(heap,list);int id=heap.head();heap.remove(id);list.remove(id);}
  assert(list.queue.empty());
 }
}
void threshold(){
 Arena heap(true,6100),list(false,6100);
 // Equal high costs force the retail cap to insert before the old tail.
 for(int i=0;i<6100;++i){heap.insert(i,60000);list.insert(i,60000);compare(heap,list);}
#if RETAIL_COMPATIBLE_PATHFINDING
 if(!s_useFixedPathfinding)assert(!heap.queue.m_heapActive);
 else assert(heap.queue.m_heapActive);
#else
 assert(heap.queue.m_heapActive);
#endif
 for(int step=0;step<1000;++step){
  int id=(step*37)%6100;unsigned cost=(step*29)%65536;
  heap.info[id].m_totalCost=list.info[id].m_totalCost=cost;
  heap.remove(id);list.remove(id);heap.insert(id,cost);list.insert(id,cost);compare(heap,list);
 }
 while(!heap.queue.empty()){compare(heap,list);int id=heap.head();heap.remove(id);list.remove(id);}
 heap.queue.reset();list.queue.reset();
 assert(heap.queue.m_heapActive);
 for(int i=0;i<20;++i){heap.insert(i,20-i);list.insert(i,20-i);}
 std::set<int> seen;
 for(auto* cell=heap.queue.getHead();cell;cell=heap.queue.getNextForDisplay(cell))assert(seen.insert(cell->id).second);
 assert(seen.size()==20);
 assert(PathfindCell::releaseOpenList(heap.queue)==20);
 assert(PathfindCell::releaseOpenList(list.queue)==20);
 for(int i=0;i<20;++i){assert(heap.cells[i].releases==1);assert(!heap.info[i].m_open);}
 assert(heap.queue.empty());
#if RETAIL_COMPATIBLE_PATHFINDING
 heap.info[0].m_open=list.info[0].m_open=true;
 heap.queue.reset(&heap.cells[0]);list.queue.reset(&list.cells[0]);
 assert(heap.head()==list.head());
 heap.remove(0);list.remove(0);assert(heap.queue.empty() && list.queue.empty());
#endif
}
std::vector<int> gridSearch(bool useHeap, unsigned seed){
 const int width=24, count=width*width;
 Arena a(useHeap,count);
 std::mt19937 random(seed);
 std::vector<bool> blocked(count), closed(count);
 std::vector<int> distance(count,1000000),parent(count,-1),result;
 for(int i=0;i<count;++i)blocked[i]=random()%5==0;
 blocked[0]=blocked[count-1]=false;
 distance[0]=0;a.insert(0,10*(2*width-2));
 while(!a.queue.empty()){
  int id=a.head();a.remove(id);closed[id]=true;result.push_back(id);
  if(id==count-1)break;
  for(int d:{-width,-1,1,width}){
   int next=id+d;
   if(next<0 || next>=count || (std::abs(d)==1 && id/width!=next/width) || blocked[next] || closed[next])continue;
   int candidate=distance[id]+10;
   if(candidate>=distance[next])continue;
   distance[next]=candidate;parent[next]=id;
   a.info[next].m_totalCost=candidate+10*((width-1-next%width)+(width-1-next/width));
   if(a.info[next].m_open)a.remove(next);
   a.cells[next].putOnSortedOpenList(a.queue);
  }
 }
 result.push_back(-2);
 for(int id=count-1;id!=-1;id=parent[id])result.push_back(id);
 PathfindCell::releaseOpenList(a.queue);
 return result;
}
void reused_record(){
 Arena heap(true,32),list(false,32);
 for(int pass=0;pass<20;++pass){
  heap.queue.reset();list.queue.reset();
  for(int i=0;i<32;++i){heap.insert(i,42);list.insert(i,42);}
  for(int i=0;i<32;++i){compare(heap,list);assert(heap.head()==i);heap.remove(i);list.remove(i);}
 }
}
int main(){randomized();threshold();reused_record();for(unsigned seed=0;seed<100;++seed)assert(gridSearch(true,seed)==gridSearch(false,seed));}
'''

    fields = 'm_nextOpen|m_prevOpen|m_pathParent|m_openSequence|m_openIndex|m_totalCost|m_costSoFar|m_open|m_closed'
    source = re.sub(r'->(' + fields + r')\b', lambda m: '->search().' + m[1], source)
    source = re.sub(r'(?<!search\(\))\.(' + fields + r')\b', lambda m: '.search().' + m[1], source)
    return source.replace("m_search.search().", "m_search.")


class PathfindHeapTest(unittest.TestCase):
    def test_retail_order_and_capped_fallback(self):
        run_cpp(fixture(1, False))

    def test_fixed_order_with_retail_support(self):
        run_cpp(fixture(1, True))

    def test_generation_context_heap_and_list_order(self):
        run_cpp(fixture(1, False, True))
        run_cpp(fixture(1, True, True))

    def test_fixed_order_without_retail_support(self):
        run_cpp(fixture(0, True))


if __name__ == '__main__':
    unittest.main()
