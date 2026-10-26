#pragma once
#include <cassert>
#include <cstddef>
#include <stdexcept>
#include <vector>

// GeneralsX @refactor Codex 27/10/2026 Own unoptimized route values before allocating engine PathNodes.
// Points are stored in prepend order (goal towards start), not in final start-to-goal order.
// No search cells, engine nodes or object pointers survive in this result.
template<class Position, class Layer, std::size_t MaxPoints>
class OwnedPathRoute {
public:
 struct Point {
  Position position{};
  Layer layer{};
  bool canOptimize=false; // Match PathNode's constructor, including the exact start-position node.
  const Position* getPosition() const { return &position; }
  void setLayer(Layer value) { layer=value; }
  void setCanOptimize(bool value) { canOptimize=value; }
 };
private:
 std::vector<Point> m_points;
 Point m_seed{};
 bool m_hasSeed=false;
 bool m_blockedByAlly=false;
public:
 template<class Path>
 static OwnedPathRoute fromPath(Path& path) {
  OwnedPathRoute result;
  if (auto* head=path.getFirstNode()) {
   result.m_seed={*head->getPosition(),head->getLayer(),head->getCanOptimize()};
   result.m_hasSeed=true;
  }
  return result;
 }
 Point* getFirstNode() { return m_points.empty() ? (m_hasSeed ? &m_seed : nullptr) : &m_points.back(); }
 void prependNode(const Position* position, Layer layer) {
  if (m_points.size()==MaxPoints) throw std::length_error("Path route exceeds bounded search-record capacity");
  m_points.push_back({*position,layer,false});
 }
 void setBlockedByAlly(bool value) { m_blockedByAlly=value; }
 std::size_t size() const { return m_points.size(); }
 template<class Path>
 void materialize(Path& path) const {
  assert(static_cast<bool>(path.getFirstNode())==m_hasSeed);
  if (m_hasSeed) {
   path.getFirstNode()->setLayer(m_seed.layer);
   path.getFirstNode()->setCanOptimize(m_seed.canOptimize);
  }
  for (const auto& point:m_points) {
   path.prependNode(&point.position,point.layer);
   path.getFirstNode()->setCanOptimize(point.canOptimize);
  }
  if (m_blockedByAlly) path.setBlockedByAlly(true);
 }
};
