#!/usr/bin/env python3
"""Compare optimized zone tables with the original merger; --benchmark measures a controlled large rebuild."""
# GeneralsX @performance Codex 30/10/2026 Verify exact minimum labels, canonical fallback and production rebuild output.
import json
import sys
import unittest
from functools import partial
from compiled_harness import run_cpp
from test_path_movement_inputs import function
from test_parallel_path_batch import zone_rebuild_fixture


def merge_fixture():
    return r'''
#include "minimumzoneequivalence.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <random>
#include <vector>
using Int=int;using zoneStorageType=unsigned short;
#define __fastcall
#define DEBUG_ASSERTCRASH(condition, message) assert(condition)
'''+function('static void __fastcall resolveZones(')+'\n'


class ZoneMergeTests(unittest.TestCase):
    def test_randomized_minimum_labels_match_flat_merges_after_each_batch(self):
        run_cpp(merge_fixture()+r'''
int main(){std::mt19937 random(1937);
 for(unsigned size:{2,17,257,4823}){std::vector<zoneStorageType> flat(size),tree(size);
  for(unsigned i=0;i<size;++i)flat[i]=tree[i]=i;
  MinimumZoneEquivalence<zoneStorageType> merging(tree.data(),size);
  for(unsigned batch=0;batch<40;++batch){for(unsigned j=0;j<128;++j){
   unsigned a=1+random()%(size-1),b=1+random()%(size-1);
   resolveZones(a,b,flat.data(),size);merging.merge(a,b);
  }
  for(unsigned i=0;i<size;++i)assert(merging.find(i)==flat[i]);
  merging.materialize();assert(tree==flat);
  }
 }
}
''',timeout=30)

    def test_flatten_matches_original_for_exhaustive_descending_tables(self):
        flatten=function('static void flattenZones(')
        source=merge_fixture()+'\n#undef GENERALS_ZH_FAST_ZONE_MERGES\n'+flatten.replace('flattenZones(', 'baselineFlatten(',1)
        source+='\n#define GENERALS_ZH_FAST_ZONE_MERGES 1\n'+flatten.replace('flattenZones(', 'fastFlatten(',1)
        run_cpp(source+r'''
int main(){constexpr unsigned size=6;unsigned fallbackCases=0;
 // All positive descending mappings, including noncanonical intermediates.
 for(unsigned aCode=0;aCode<120;++aCode)for(unsigned hCode=0;hCode<120;++hCode){
  std::array<zoneStorageType,size> a{},h{};unsigned encodedA=aCode,encodedH=hCode;
  for(unsigned i=1;i<size;++i){a[i]=1+encodedA%i;encodedA/=i;h[i]=1+encodedH%i;encodedH/=i;}
  auto expected=a,actual=a;
  baselineFlatten(expected.data(),h.data(),size);fastFlatten(actual.data(),h.data(),size);assert(actual==expected);
  auto copy=a;const bool optimized=MinimumZoneEquivalence<zoneStorageType>::flattenCanonical(copy.data(),h.data(),size);
  if(!optimized){++fallbackCases;assert(copy==a);}
 }
 assert(fallbackCases>0);
}
''',timeout=30)

    def test_production_rebuild_labels_and_all_tables_match_with_bridges_and_fences(self):
        source=zone_rebuild_fixture(9,7,3)+r'''
#include <random>
int main(){std::mt19937 random(7182);
 for(unsigned seed=0;seed<128;++seed){PathfindZoneManager zones;PathfindCell storage[9][7];PathfindCell*map[9];
  PathfindLayer layers[4];IRegion2D bounds;bounds.hi={8,6};
  for(int x=0;x<9;++x){map[x]=storage[x];for(int y=0;y<7;++y){
   storage[x][y].type=static_cast<PathfindCell::CellType>(seed%4==0?(x+y)%5:seed%4==1?(x/3+y/2)%5:seed%4==2?0:random()%5);
   storage[x][y].fence=random()%2;
  }}
  if(seed%3==0){layers[3].unused=false;
   storage[1][1].type=storage[7][5].type=PathfindCell::CELL_CLEAR;storage[1][1].connect=storage[7][5].connect=3;
  }
  zones.calculateZones(map,layers,bounds);
  for(int x=0;x<9;++x)for(int y=0;y<7;++y)printf("%d,",storage[x][y].getZone());
  for(auto&layer:layers)printf("L%d;",layer.getZone());
  for(int i=0;i<zones.m_zonesAllocated;++i)printf("%d,%d,%d,%d,%d,%d;",zones.m_groundCliffZones[i],zones.m_groundWaterZones[i],
   zones.m_groundRubbleZones[i],zones.m_terrainZones[i],zones.m_crusherZones[i],zones.m_hierarchicalZones[i]);puts("");
 }
}
'''
        baseline=run_cpp(source,timeout=30).stdout
        self.assertEqual(baseline,run_cpp('#define GENERALS_ZH_FAST_ZONE_MERGES 1\n'+source,timeout=30).stdout)
        self.assertEqual(baseline,run_cpp('#define GENERALS_ZH_FAST_ZONE_MERGES 1\n#define GENERALS_ZH_PATH_TIMING 1\n'+source,
                                       timeout=30).stdout)


def benchmark():
    source=zone_rebuild_fixture(527,521,10,8192)+r'''
#include <chrono>
#include <vector>
int main(){std::vector<PathfindCell> cells(527*521);PathfindCell*map[527];PathfindLayer layers[4];IRegion2D bounds;bounds.hi={526,520};
 PathfindZoneManager zones;
 for(int x=0;x<527;++x){map[x]=cells.data()+x*521;for(int y=0;y<521;++y)map[x][y].type=static_cast<PathfindCell::CellType>((x/32+y/27)%5);}
 for(unsigned repeat=0;repeat<10;++repeat){const auto start=std::chrono::steady_clock::now();zones.calculateZones(map,layers,bounds);
  const auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
  unsigned long long checksum=0;for(int i=0;i<zones.m_maxZone;++i)checksum=checksum*131+zones.m_terrainZones[i]+zones.m_hierarchicalZones[i];
  if(repeat)printf("%lld %d %llu\n",static_cast<long long>(ns),zones.m_maxZone,checksum);
 }
}
'''
    variants=[('baseline',''),('minimum_root','#define GENERALS_ZH_FAST_ZONE_MERGES 1\n')]
    if '--reverse' in sys.argv:variants.reverse()
    for name,prefix in variants:
        rows=run_cpp(prefix+source,extra_flags=('-O2',),timeout=60).stdout.splitlines()
        values=[list(map(int,row.split())) for row in rows]
        times=sorted(row[0]/1000000 for row in values)
        print(json.dumps({'case':name,'median_ms':times[len(times)//2],'range_ms':[times[0],times[-1]],
                          'zones':values[0][1],'checksums':sorted(set(row[2] for row in values))}))


if __name__=='__main__':
    if '--benchmark' in sys.argv:
        benchmark()
    else:
        if '--tsan' in sys.argv:
            sys.argv.remove('--tsan');run_cpp=partial(run_cpp,extra_flags=('-fsanitize=thread','-g','-O1'))
        unittest.main()
