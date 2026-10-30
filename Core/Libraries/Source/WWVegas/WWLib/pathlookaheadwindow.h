#pragma once
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include "pathsearchprediction.h"

// GeneralsX @performance Codex 30/10/2026 Retain a bounded inspected queue span independently of speculative result storage.
template<unsigned QueueLength>
class PathLookaheadWindow {
 static_assert(QueueLength>8,"Lookahead must be smaller than the queue ring");
 unsigned m_begin=0,m_count=0;
 std::uint64_t m_world=0,m_lifecycle=0;
public:
 static constexpr unsigned scanLimit=8;
 bool empty()const{return m_count==0;}
 void reset(){m_count=0;}
 void capture(unsigned begin,unsigned count,std::uint64_t world,std::uint64_t lifecycle){
  assert(begin<QueueLength&&count<=scanLimit);
  m_begin=begin;m_count=count;m_world=world;m_lifecycle=lifecycle;
 }
 bool contains(unsigned position,std::uint64_t world,std::uint64_t lifecycle)const{
  assert(position<QueueLength);
  return m_count && world==m_world && lifecycle==m_lifecycle &&
   (position+QueueLength-m_begin)%QueueLength<m_count;
 }
};

enum class PathLookaheadEligibility { Eligible,Duplicate,MissingObject,MissingAI,Dozer,CrusherKey,Immobile,Prediction,Count };

// GeneralsX @feature Codex 30/10/2026 Main-only bounded distributions separate inspected positions from selected result slots.
struct PathLookaheadProfile {
 std::uint64_t windows=0,retained=0,retired=0,inspected=0,eligible=0,selected=0,dispatched=0;
 std::array<std::uint64_t,9> scanCounts{},eligibleCounts{};
 std::array<std::uint64_t,8> partnerOffsets{};
 std::array<std::uint64_t,static_cast<unsigned>(PathLookaheadEligibility::Count)> skipped{};
 std::array<std::uint64_t,static_cast<unsigned>(PathPredictionReason::Count)> predictions{};
 void reject(PathLookaheadEligibility reason,PathPredictionReason prediction){
  assert(reason!=PathLookaheadEligibility::Eligible&&reason!=PathLookaheadEligibility::Count);
  ++skipped[static_cast<unsigned>(reason)];
  if(reason==PathLookaheadEligibility::Prediction)++predictions[static_cast<unsigned>(prediction)];
 }
 void record(unsigned scans,unsigned accepted,unsigned chosen,unsigned offset){
  assert(scans<=8&&accepted<=scans&&chosen<=2&&chosen<=accepted&&offset<8);
  ++windows;inspected+=scans;eligible+=accepted;selected+=chosen;
  ++scanCounts[scans];++eligibleCounts[accepted];if(chosen==2)++partnerOffsets[offset];
 }
 void report(FILE* output)const{
  if(!windows)return;
  const auto u=[](std::uint64_t n){return static_cast<unsigned long long>(n);};
  std::fprintf(output,"[PATH_LOOKAHEAD] windows=%llu retained=%llu retired=%llu inspected=%llu eligible=%llu selected=%llu dispatched=%llu\n",
   u(windows),u(retained),u(retired),u(inspected),u(eligible),u(selected),u(dispatched));
  const char* names[]={"eligible","duplicate","missing_object","missing_ai","dozer","crusher_key","immobile","prediction"};
  std::fprintf(output,"[PATH_LOOKAHEAD_SKIP]");
  for(unsigned i=1;i<skipped.size();++i)std::fprintf(output," %s=%llu",names[i],u(skipped[i]));
  std::fprintf(output,"\n[PATH_LOOKAHEAD_SCAN]");
  for(unsigned i=0;i<scanCounts.size();++i)std::fprintf(output," n%u=%llu",i,u(scanCounts[i]));
  std::fprintf(output,"\n[PATH_LOOKAHEAD_ELIGIBLE]");
  for(unsigned i=0;i<eligibleCounts.size();++i)std::fprintf(output," n%u=%llu",i,u(eligibleCounts[i]));
  std::fprintf(output,"\n[PATH_LOOKAHEAD_PARTNER]");
  for(unsigned i=1;i<partnerOffsets.size();++i)std::fprintf(output," offset%u=%llu",i,u(partnerOffsets[i]));
  const char* reasons[]={"accepted","not_waiting","safe","approach","attack","blocked","nonfinal","quick","production_exit","outside_extent"};
  std::fprintf(output,"\n[PATH_LOOKAHEAD_PREDICTION]");
  for(unsigned i=0;i<predictions.size();++i)std::fprintf(output," %s=%llu",reasons[i],u(predictions[i]));
  std::fprintf(output,"\n");
 }
};
