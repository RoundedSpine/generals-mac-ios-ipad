#pragma once
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <limits>
#include <type_traits>

// GeneralsX @feature Codex 26/10/2026 Stable-address bounded records with a generation-stamped private lookup.
// Hash placement affects lookup only, never allocation order or search iteration.
template<class Key, class Value, std::size_t Capacity, class Generation = std::uint32_t>
class BoundedKeyedPool {
 static_assert(std::is_trivially_destructible<Value>::value, "generation reset requires non-owning records");
 static_assert(Capacity > 0 && Capacity < std::numeric_limits<unsigned>::max(), "invalid record capacity");
 static constexpr std::size_t tableSize() { std::size_t n=1; while(n<Capacity*2) n*=2; return n; }
 static constexpr unsigned none = std::numeric_limits<unsigned>::max();
 struct Bucket { unsigned slot=none; Generation stamp=0; };
 std::array<Bucket, tableSize()> m_buckets{};
 std::array<Value, Capacity> m_values{};
 std::array<Key, Capacity> m_keys{};
 std::array<unsigned, Capacity> m_freeNext{};
 Generation m_generation=1;
 unsigned m_next=0, m_free=none, m_size=0;
 std::size_t hash(const Key& key) const {
  auto h=std::hash<Key>{}(key); h ^= h>>7; h ^= h>>17; return h & (tableSize()-1);
 }
public:
 BoundedKeyedPool()=default;
 BoundedKeyedPool(const BoundedKeyedPool&)=delete;
 BoundedKeyedPool& operator=(const BoundedKeyedPool&)=delete;
 static constexpr std::size_t capacity() { return Capacity; }
 std::size_t size() const { return m_size; }
 unsigned index(const Value* value) const { assert(value>=m_values.data() && value<m_values.data()+Capacity); return static_cast<unsigned>(value-m_values.data()); }
 Value* find(const Key& key) {
  auto b=hash(key);
  for(std::size_t n=0;n<tableSize();++n,b=(b+1)&(tableSize()-1)) {
   const auto& entry=m_buckets[b];
   if(entry.stamp!=m_generation) return nullptr;
   if(entry.slot!=none && m_keys[entry.slot]==key) return &m_values[entry.slot];
  }
  return nullptr;
 }
 Value* acquire(const Key& key) {
  auto b=hash(key); std::size_t insert=tableSize();
  for(std::size_t n=0;n<tableSize();++n,b=(b+1)&(tableSize()-1)) {
   const auto& entry=m_buckets[b];
   if(entry.stamp!=m_generation) { if(insert==tableSize()) insert=b; break; }
   if(entry.slot==none) { if(insert==tableSize()) insert=b; }
   else if(m_keys[entry.slot]==key) return &m_values[entry.slot];
  }
  if(m_size==Capacity) return nullptr;
  assert(insert!=tableSize());
  unsigned slot;
  if(m_free!=none) { slot=m_free; m_free=m_freeNext[slot]; }
  else { assert(m_next<Capacity); slot=m_next++; }
  m_values[slot]=Value{}; m_keys[slot]=key;
  m_buckets[insert]={slot,m_generation}; ++m_size;
  return &m_values[slot];
 }
 bool release(const Key& key) {
  auto b=hash(key);
  for(std::size_t n=0;n<tableSize();++n,b=(b+1)&(tableSize()-1)) {
   auto& entry=m_buckets[b];
   if(entry.stamp!=m_generation) return false;
   if(entry.slot!=none && m_keys[entry.slot]==key) {
    auto slot=entry.slot; entry.slot=none; m_freeNext[slot]=m_free; m_free=slot; --m_size; return true;
   }
  }
  return false;
 }
 void beginGeneration() {
  m_next=m_size=0; m_free=none;
  if(m_generation==std::numeric_limits<Generation>::max()) {
   for(auto& entry:m_buckets) entry.stamp=0;
   m_generation=1;
  } else ++m_generation;
 }
};
