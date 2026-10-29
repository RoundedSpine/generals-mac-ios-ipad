#pragma once
#include <cassert>
#include <cstddef>

// GeneralsX @performance Codex 30/10/2026 Merge minimum-label components in existing table storage, then publish flat labels.
template<class Zone>
class MinimumZoneEquivalence {
 Zone* m_parent;
 std::size_t m_size;
public:
 MinimumZoneEquivalence(Zone* parent,std::size_t size):m_parent(parent),m_size(size){}
 Zone find(std::size_t zone){
  assert(zone<m_size);
  while(m_parent[zone]!=zone){
   const auto parent=m_parent[zone];
   assert(parent<zone && m_parent[parent]<=parent);
   m_parent[zone]=m_parent[parent];zone=parent;
  }
  return static_cast<Zone>(zone);
 }
 void merge(std::size_t a,std::size_t b){
  const auto left=find(a),right=find(b);
  if(left<right)m_parent[right]=left;
  else if(right<left)m_parent[left]=right;
 }
 void materialize(){for(std::size_t i=0;i<m_size;++i)m_parent[i]=find(i);}
 // The original flattening pass can produce noncanonical intermediate tables.
 // Optimize only the flat minimum-label case; leave all other cases to the original merger.
 static bool flattenCanonical(Zone* values,const Zone* hierarchical,std::size_t size){
  for(std::size_t i=0;i<size;++i)
   if(values[i]>i || values[i]>=size || values[values[i]]!=values[i] || hierarchical[i]>=size)return false;
  MinimumZoneEquivalence table(values,size);
  for(std::size_t i=0;i<size;++i)table.merge(i,hierarchical[i]);
  table.materialize();return true;
 }
};
