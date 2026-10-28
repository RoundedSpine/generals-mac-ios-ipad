#pragma once
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

// GeneralsX @performance Codex 28/10/2026 Index existing observation storage; keep first-seen order without duplicating keys.
struct ObservationWordsHash {
 template<class Words>std::size_t operator()(const Words& words)const{
  std::uint64_t hash=1469598103934665603ull;
  for(auto word:words){hash^=static_cast<std::uint64_t>(word);hash*=1099511628211ull;}
  hash^=hash>>32;hash^=hash>>16;
  return static_cast<std::size_t>(hash);
 }
};

// Append-only within a generation. A repeated key consumes no entry; contradictory values invalidate the log.
template<class Value,std::size_t Capacity,class KeyOf,class SameValue,
         class Hash=ObservationWordsHash,class Generation=std::uint16_t>
class BoundedObservationLog {
 static_assert(Capacity>0 && Capacity<=std::numeric_limits<std::uint16_t>::max(),"observation index exceeds slot width");
 static constexpr std::size_t tableSize(){std::size_t n=1;while(n<Capacity*2)n*=2;return n;}
 struct Bucket{std::uint16_t slot=0;Generation stamp=0;};
 std::array<Bucket,tableSize()> m_buckets{};
 std::vector<Value> m_values;
 Generation m_generation=1;
 std::uint64_t m_observations=0;
 bool m_full=false,m_conflict=false,m_failed=false;
public:
 BoundedObservationLog()=default;
 BoundedObservationLog(const BoundedObservationLog&)=delete;
 BoundedObservationLog& operator=(const BoundedObservationLog&)=delete;
 bool observe(const Value& value){
  ++m_observations;
  if(invalid())return false;
  try {
   const auto key=KeyOf{}(value);
   auto bucket=Hash{}(key)&(tableSize()-1);
   for(std::size_t probes=0;probes<tableSize();++probes,bucket=(bucket+1)&(tableSize()-1)){
    auto& entry=m_buckets[bucket];
    if(entry.stamp!=m_generation){
     if(m_values.size()==Capacity){m_full=true;return false;}
     m_values.push_back(value);
     entry={static_cast<std::uint16_t>(m_values.size()-1),m_generation};
     return true;
    }
    const auto& previous=m_values[entry.slot];
    if(KeyOf{}(previous)==key){
     if(!SameValue{}(previous,value))m_conflict=true;
     return !m_conflict;
    }
   }
   assert(false && "observation table cannot fill before its entry bound");
   m_full=true;return false;
  }catch(...){m_failed=true;throw;}
 }
 void clear(){
  m_values.clear();m_observations=0;m_full=m_conflict=m_failed=false;
  if(m_generation==std::numeric_limits<Generation>::max()){
   for(auto& entry:m_buckets)entry.stamp=0;
   m_generation=1;
  }else ++m_generation;
 }
 bool invalid()const{return m_full||m_conflict||m_failed;}
 bool full()const{return m_full;}
 bool conflict()const{return m_conflict;}
 std::uint64_t observations()const{return m_observations;}
 std::size_t size()const{return m_values.size();}
 bool empty()const{return m_values.empty();}
 auto begin()const{return m_values.begin();}
 auto end()const{return m_values.end();}
};
