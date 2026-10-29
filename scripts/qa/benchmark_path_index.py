#!/usr/bin/env python3
"""Measure production search getters with indexed versus keyed record lookup.

Run locally with a C++17 compiler: python3 scripts/qa/benchmark_path_index.py.
This controlled host microbenchmark does not measure iOS frame time or FPS.
No performance threshold is used as a test. Output is JSON for repeatable review.
"""
# GeneralsX @performance Codex 29/10/2026 Measure unchanged getter work and checksums, preserving the production bounded allocator.
import argparse
import json
import statistics
from compiled_harness import run_cpp
from test_search_record_pool import engine_fixture


def benchmark(records, iterations, repeats):
    main=r'''
#include <chrono>
#include <cstdint>
int main(){PathfindCellInfo::allocateCellInfos();{
 constexpr unsigned records=RECORD_COUNT,iterations=ITERATION_COUNT,repeats=REPEAT_COUNT;
 auto cells=std::make_unique<PathfindCell[]>(records);PathfindCell::registerSearchCells(cells.get(),records);
 auto&context=mainPathfindSearchContext();context.beginSearch();
 for(unsigned i=0;i<records;++i){if(!cells[i].allocateSearchInfo({int(i),int(i%31)}))return 2;
  cells[i].setCostSoFar(i%251);cells[i].setTotalCost(i%499);}
 printf("{\"type\":\"layout\",\"cell_bytes\":%zu,\"record_bytes\":%zu,\"state_bytes\":%zu,\"context_bytes\":%zu,\"index_bytes\":%zu}\n",
  sizeof(PathfindCell),sizeof(PathfindCellInfo),sizeof(PathfindSearchState),sizeof(PathfindSearchContext),context.m_recordIndex.bytes());
 volatile std::uint64_t sink=0;
 for(unsigned pattern=0;pattern<2;++pattern)for(unsigned sample=0;sample<repeats;++sample){
  std::uint64_t checksum=0,random=7919;
  const auto start=std::chrono::steady_clock::now();
  for(unsigned n=0;n<iterations;++n){random=random*6364136223846793005ull+1;
   const unsigned index=pattern?unsigned((random>>32)%records):n%records;auto&cell=cells[index];
   checksum+=cell.getXIndex()+cell.getYIndex()+cell.getCostSoFar()+cell.getTotalCost();
  }
  const auto elapsed=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
  sink=checksum;printf("{\"type\":\"sample\",\"pattern\":%u,\"sample\":%u,\"ns\":%lld,\"checksum\":%llu}\n",
   pattern,sample,static_cast<long long>(elapsed),static_cast<unsigned long long>(checksum));
 }
 assert(sink);context.releaseStorage();}
 pathfindSearchCellIndices().reset();PathfindCellInfo::releaseCellInfos();
}
'''
    main=main.replace('RECORD_COUNT',str(records)).replace('ITERATION_COUNT',str(iterations)).replace('REPEAT_COUNT',str(repeats))
    indexed=engine_fixture()
    keyed=indexed.replace('if(!m_recordIndex.covers(index))return m_records.find(cell);','return m_records.find(cell);')
    if indexed==keyed:
        raise RuntimeError('Production lookup changed; update the keyed comparison before benchmarking.')
    results={}
    for name,source in [('keyed',keyed),('indexed',indexed)]:
        output=run_cpp(source+main,extra_flags=('-O2','-DNDEBUG'),timeout=120)
        results[name]=[json.loads(line) for line in output.stdout.splitlines()]
    # Setup checks allocations explicitly, so -DNDEBUG never removes initialization.
    checksums={name:[row['checksum'] for row in rows if row['type']=='sample'] for name,rows in results.items()}
    if checksums['keyed']!=checksums['indexed']:
        raise RuntimeError('Lookup variants returned different values.')
    report={'records':records,'iterations':iterations,'repeats':repeats,'optimization':'-O2 -DNDEBUG',
            'scope':'host production getter groups; unchanged allocator; not device FPS',
            'layout':results['indexed'][0],'patterns':{}}
    for pattern,label in [(0,'sequential'),(1,'random')]:
        row={}
        for name,rows in results.items():
            values=[sample['ns']/iterations for sample in rows if sample['type']=='sample' and sample['pattern']==pattern]
            row[name]={'median_ns_per_group':statistics.median(values),'min_ns_per_group':min(values),'max_ns_per_group':max(values)}
        row['keyed_over_indexed']=row['keyed']['median_ns_per_group']/row['indexed']['median_ns_per_group']
        report['patterns'][label]=row
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records',type=int,default=8192)
    parser.add_argument('--iterations',type=int,default=1000000)
    parser.add_argument('--repeats',type=int,default=7)
    args=parser.parse_args()
    if not 1<=args.records<=30000 or args.iterations<1 or args.repeats<1:
        parser.error('records must be 1..30000; iterations and repeats must be positive')
    print(json.dumps(benchmark(args.records,args.iterations,args.repeats),indent=2))


if __name__=='__main__':
    main()
