#pragma once
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <limits>
#include <memory>
#include <new>

// GeneralsX @performance Codex 29/10/2026 Register immutable map-cell identities independently of search allocation limits.
class SearchCellIndices {
 unsigned m_count=0;
public:
 static constexpr unsigned invalid=std::numeric_limits<unsigned>::max();
 unsigned size()const{return m_count;}
 unsigned reserve(unsigned count){
  if(count>invalid-m_count)return invalid;
  const unsigned base=m_count;m_count+=count;return base;
 }
 void reset(){m_count=0;}
};

// GeneralsX @performance Codex 29/10/2026 A bounded direct cell-index to existing-record-slot lookup; never a second node allocator.
template<unsigned RecordCapacity,unsigned MaxCells=262144,class Generation=std::uint16_t>
class BoundedRecordIndex {
 static_assert(RecordCapacity>0 && RecordCapacity<65535,"record slot must fit the packed index");
 static_assert(std::numeric_limits<Generation>::max()<=65535,"generation must fit the packed index");
 std::unique_ptr<std::uint32_t[]> m_entries;
 unsigned m_size=0;
 Generation m_generation=1;
public:
 static constexpr unsigned missing=65535;
 static constexpr unsigned maximumCells=MaxCells;
 bool beginSearch(unsigned cells){
  if(m_generation==std::numeric_limits<Generation>::max()){
   std::fill_n(m_entries.get(),m_size,0);m_generation=1;
  }else ++m_generation;
  const unsigned needed=std::min(cells,MaxCells);
  if(needed<=m_size)return true;
  try {auto entries=std::make_unique<std::uint32_t[]>(needed);m_entries=std::move(entries);m_size=needed;return true;}
  catch(const std::bad_alloc&){return false;} // Existing prefix remains valid; uncovered cells keep their keyed lookup.
 }
 bool covers(unsigned cell)const{return cell<m_size;}
 unsigned find(unsigned cell)const{
  assert(covers(cell));const auto entry=m_entries[cell];
  return (entry>>16)==m_generation?(entry&65535):missing;
 }
 void publish(unsigned cell,unsigned slot){
  assert(covers(cell)&&slot<RecordCapacity);
  m_entries[cell]=(std::uint32_t(m_generation)<<16)|slot;
 }
 void erase(unsigned cell){if(covers(cell))m_entries[cell]=0;}
 void releaseStorage(){m_entries.reset();m_size=0;}
 std::size_t size()const{return m_size;}
 std::size_t bytes()const{return m_size*sizeof(std::uint32_t);}
};
