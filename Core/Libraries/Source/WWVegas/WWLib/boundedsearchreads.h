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
  if(m_overflow || m_entries.find(key)) return;
  auto* entry=m_entries.acquire(key);
  if(!entry){m_overflow=true;return;}
  entry->key=key;entry->value=value;m_order.push_back(entry);
 }
 bool overflow() const {return m_overflow;}
 template<class Reader> bool matches(Reader read) const {
  if(m_overflow) return false;
  for(const auto* entry:m_order) if(!(read(entry->key)==entry->value)) return false;
  return true;
 }
};
