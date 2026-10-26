#pragma once

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>

// GeneralsX @feature Codex 26/10/2026 A single-thread-owned bounded search arena; no map-sized arrays or workers.
template<class State, std::size_t Capacity, class Generation = std::uint32_t>
class StampedSearchContext {
 struct Entry { State state{}; Generation stamp = 0; };
 std::array<Entry, Capacity> m_entries{};
 Generation m_generation = 1;
public:
 static constexpr std::size_t capacity() { return Capacity; }
 Generation generation() const { return m_generation; }
 void beginSearch() {
  if (m_generation == std::numeric_limits<Generation>::max()) {
   for (auto& entry : m_entries) entry.stamp = 0;
   m_generation = 1;
  } else ++m_generation;
 }
 bool active(std::size_t slot) const { assert(slot < Capacity); return m_entries[slot].stamp == m_generation; }
 State& get(std::size_t slot) {
  assert(slot < Capacity);
  auto& entry = m_entries[slot];
  if (entry.stamp != m_generation) {
   entry.state = State{};
   entry.stamp = m_generation;
  }
  return entry.state;
 }
 void resetSlot(std::size_t slot) { get(slot) = State{}; }
};
