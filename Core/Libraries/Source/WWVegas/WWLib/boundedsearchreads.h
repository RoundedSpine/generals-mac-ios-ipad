#pragma once
#include "boundedkeyedpool.h"
#include <vector>

// GeneralsX @feature Codex 27/10/2026 Exact, bounded read dependencies; overflow rejects reuse, never truncates validation.
template<class Key, class Value, std::size_t Capacity>
class BoundedSearchReads {
 struct Entry { Key key{}; Value value{}; };
 BoundedKeyedPool<Key, Entry, Capacity> m_entries;
 std::vector<Entry*> m_order;
 bool m_overflow=false;
public:
 void reset() {m_entries.beginGeneration();m_order.clear();m_overflow=false;}
 bool contains(Key key) {return m_overflow || m_entries.find(key)!=nullptr;}
 void observe(Key key, const Value& value) {
  observeWith(key,[&value]{return value;});
 }
 // GeneralsX @performance Codex 27/10/2026 Acquire once and capture only a new key's first value; duplicates keep the original dependency.
 template<class Reader> void observeWith(Key key, Reader read) {
  if(m_overflow) return;
  const auto previousSize=m_entries.size();
  auto* entry=m_entries.acquire(key);
  if(!entry){m_overflow=true;return;}
  if(m_entries.size()==previousSize) return;
  try {
   entry->key=key;entry->value=read();m_order.push_back(entry);
  } catch (...) {
   // A partial dependency must never appear valid if the caller handles an allocation/reader failure.
   m_overflow=true;throw;
  }
 }
 bool overflow() const {return m_overflow;}
 template<class Reader> bool matches(Reader read) const {
  if(m_overflow) return false;
  for(const auto* entry:m_order) if(!(read(entry->key)==entry->value)) return false;
  return true;
 }
};
