#!/usr/bin/env python3
"""Measure production getters or closest searches with selectable storage.

Run locally with a C++17 compiler: python3 scripts/qa/benchmark_path_index.py.
Add --storage for split/compact getter storage, or --search for closest API calls.
This controlled host microbenchmark does not measure iOS frame time or FPS.
No performance threshold is used as a test. Output is JSON for repeatable review.
"""
# GeneralsX @performance Codex 29/10/2026 Measure unchanged getter work and checksums, preserving the production bounded allocator.
import argparse
import json
import statistics
from compiled_harness import run_cpp
from test_search_record_pool import engine_fixture, split_storage
from test_parallel_path_batch import large_closest_fixture


def search_benchmark(repeats):
    """Compare the same complete closest calls with controlled terrain/Path services."""
    main=r'''
#include <chrono>
int main(){for(bool fixed:{false,true})for(bool hierarchy:{false,true}){World w;Pathfinder p;s_useFixedPathfinding=fixed;
 p.hierarchical=hierarchy;w.a.ai.closest=true;w.a.ai.from={25,645,0};w.a.ai.pathCostMultiplier=0;
 p.storage[64][64].setType(PathfindCell::CELL_OBSTACLE);mainPathfindSearchContext().beginSearch();
 for(unsigned repeat=0;repeat<=REPEAT_COUNT;++repeat){w.a.ai.to={645,645,9};mainPathfindSearchContext().m_cumulativeCellsAllocated=0;farPrunes=limitPrunes=0;
  const auto start=std::chrono::steady_clock::now();auto*path=w.consume(p,w.a);
  const auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();if(!path)return 2;
  unsigned long long hash=0;for(auto c:path->route)hash=hash*131+unsigned(c.x*1000+c.y);
  printf("{\"fixed\":%u,\"hierarchy\":%u,\"sample\":%u,\"ns\":%lld,\"checksum\":%llu,\"charged\":%d,\"far_tests\":%d,\"over_2000\":%d}\n",
   fixed,hierarchy,repeat,static_cast<long long>(ns),hash,mainPathfindSearchContext().m_cumulativeCellsAllocated,farPrunes,limitPrunes);
 }
}}
'''.replace('REPEAT_COUNT',str(repeats))
    source=large_closest_fixture().replace('#define GENERALS_ZH_PATH_TIMING 1\n','',1)
    # Keep fixture expansion collection out of the timed API call; fingerprints still check final paths/work.
    source=source.replace('if(!activePathfindSearchContext().m_parallelReads)serialExpansion.push_back({cell->getXIndex(),cell->getYIndex()});','')
    results={}
    for name,code in [('split',split_storage(source)),('compact',source)]:
        output=run_cpp(code+main,extra_flags=('-O2','-DNDEBUG'),timeout=120)
        results[name]=[json.loads(line) for line in output.stdout.splitlines()]
    semantic=lambda rows:[{k:v for k,v in row.items() if k!='ns'} for row in rows]
    if semantic(results['split'])!=semantic(results['compact']):
        raise RuntimeError('Storage variants returned different paths, work or accounting.')
    report={'repeats':repeats,'optimization':'-O2 -DNDEBUG','scope':'controlled complete closest API calls; not device FPS',
            'comparison':'split versus compact indexed storage','cases':{}}
    for fixed in [0,1]:
        for hierarchy in [0,1]:
            case={}
            for name,rows in results.items():
                values=[r['ns']/1000000 for r in rows if r['fixed']==fixed and r['hierarchy']==hierarchy and r['sample']>0]
                case[name]={'median_ms':statistics.median(values),'min_ms':min(values),'max_ms':max(values)}
            report['cases'][f'fixed={fixed} hierarchy={hierarchy}']=case
    return report


def benchmark(records, iterations, repeats, storage=False):
    main=r'''
#include <chrono>
#include <cstdint>
int main(){PathfindCellInfo::allocateCellInfos();{
 constexpr unsigned records=RECORD_COUNT,iterations=ITERATION_COUNT,repeats=REPEAT_COUNT;
 auto cells=std::make_unique<PathfindCell[]>(records);PathfindCell::registerSearchCells(cells.get(),records);
 auto&context=mainPathfindSearchContext();context.beginSearch();
 for(unsigned i=0;i<records;++i){if(!cells[i].allocateSearchInfo({int(i),int(i%31)}))return 2;
  cells[i].setCostSoFar(i%251);cells[i].setTotalCost(i%499);}
 printf("{\"type\":\"layout\",\"cell_bytes\":%zu,\"permanent_record_bytes\":%zu,\"search_node_bytes\":%zu,\"state_bytes\":%zu,\"context_bytes\":%zu,\"index_bytes\":%zu}\n",
  sizeof(PathfindCell),sizeof(PathfindCellInfo),sizeof(PathfindSearchRecord),sizeof(PathfindSearchState),sizeof(PathfindSearchContext),context.m_recordIndex.bytes());
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
    variants=[('split',split_storage(indexed)),('compact',indexed)] if storage else [('keyed',keyed),('indexed',indexed)]
    baseline,optimized=variants[0][0],variants[1][0]
    results={}
    for name,source in variants:
        output=run_cpp(source+main,extra_flags=('-O2','-DNDEBUG'),timeout=120)
        results[name]=[json.loads(line) for line in output.stdout.splitlines()]
    # Setup checks allocations explicitly, so -DNDEBUG never removes initialization.
    checksums={name:[row['checksum'] for row in rows if row['type']=='sample'] for name,rows in results.items()}
    if checksums[baseline]!=checksums[optimized]:
        raise RuntimeError('Lookup variants returned different values.')
    report={'records':records,'iterations':iterations,'repeats':repeats,'optimization':'-O2 -DNDEBUG',
            'scope':'host production getter groups; unchanged allocator; not device FPS',
            'comparison':'split versus compact indexed storage' if storage else 'keyed versus indexed lookup',
            'layout':results[optimized][0],'layouts':{name:rows[0] for name,rows in results.items()},'patterns':{}}
    for pattern,label in [(0,'sequential'),(1,'random')]:
        row={}
        for name,rows in results.items():
            values=[sample['ns']/iterations for sample in rows if sample['type']=='sample' and sample['pattern']==pattern]
            row[name]={'median_ns_per_group':statistics.median(values),'min_ns_per_group':min(values),'max_ns_per_group':max(values)}
        row[baseline+'_over_'+optimized]=row[baseline]['median_ns_per_group']/row[optimized]['median_ns_per_group']
        report['patterns'][label]=row
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records',type=int,default=8192)
    parser.add_argument('--iterations',type=int,default=1000000)
    parser.add_argument('--repeats',type=int,default=7)
    parser.add_argument('--storage',action='store_true',help='compare previous split storage with compact nodes; both use indexed lookup')
    parser.add_argument('--search',action='store_true',help='compare split/compact complete closest calls instead of getter groups; uses --repeats')
    args=parser.parse_args()
    if not 1<=args.records<=30000 or args.iterations<1 or args.repeats<1:
        parser.error('records must be 1..30000; iterations and repeats must be positive')
    report=search_benchmark(args.repeats) if args.search else benchmark(args.records,args.iterations,args.repeats,args.storage)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
