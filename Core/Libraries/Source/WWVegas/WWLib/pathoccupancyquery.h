#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>

// GeneralsX @refactor Codex 27/10/2026 Occupancy decisions consume an explicit reader, never engine globals.
namespace PathOccupancy {
enum class Op {
 HasMover, HasAI, IgnoreID, Aircraft, MoverID, Cell, AircraftGoal, GoalAircraft,
 CellType, ObstaclePresent, CellFlags, GoalUnit, Resolve, Allied, CanCrush,
 PosUnit, UnitID, MoverInfantry, UnitInfantry, UnitHasAI, UnitIdle
};
struct Input {
 bool destination=false;
 int x=0,y=0,layer=0,radius=0;
 bool center=false,considerTransient=false,legacy=false,infantryThroughInfantry=false;
 std::uint32_t invalidID=0;
};
struct Result {
 bool allowed=false;
 int allyFixedCount=0;
 bool allyMoving=false,allyGoal=false,enemyFixed=false;
 bool operator==(const Result& b) const {
  return allowed==b.allowed && allyFixedCount==b.allyFixedCount && allyMoving==b.allyMoving &&
         allyGoal==b.allyGoal && enemyFixed==b.enemyFixed;
 }
};
// Numeric values are checked against PathfindCell where the engine adapter is defined.
enum { NoUnits=0, UnitGoal=1, Moving=2, Fixed=3, GoalOtherMoving=5, Obstacle=4, Impassable=6, BridgeImpassable=5 };

template<class Reader>
Result evaluate(const Input& input, Reader& source) {
 auto read=[&](Op op, std::uint32_t a=0, std::uint32_t b=0, std::uint32_t c=0) {
  return source.read(op,a,b,c);
 };
 Result result;
 auto finish=[&](bool allowed){result.allowed=allowed;return result;};
 const bool hasMover=read(Op::HasMover)!=0;
 std::uint32_t ignore=input.invalidID, mover=input.invalidID;
 bool aircraft=false;
 if (input.destination) {
  if (hasMover && read(Op::HasAI)) {
   ignore=read(Op::IgnoreID);
   aircraft=read(Op::Aircraft)!=0;
   mover=read(Op::MoverID);
  }
 } else {
  if (!hasMover) return finish(true);
  if (read(Op::HasAI)) ignore=read(Op::IgnoreID);
 }
 std::array<std::uint32_t,5> allies{};
 std::size_t numAllies=0;
 const int above=input.radius+(input.center?1:0);
 for(int x=input.x-input.radius;x<input.x+above;++x) {
  for(int y=input.y-input.radius;y<input.y+above;++y) {
   if(!read(Op::Cell,static_cast<std::uint32_t>(input.layer),static_cast<std::uint32_t>(x),static_cast<std::uint32_t>(y))) return finish(false);
   if(input.destination) {
    if(aircraft) {
     if(!read(Op::AircraftGoal)) continue;
     if(read(Op::GoalAircraft)==mover) continue;
     return finish(false);
    }
    if(read(Op::CellType)==Obstacle) {
     if(read(Op::ObstaclePresent,ignore)) continue;
     return finish(false);
    }
    if(!input.legacy) {
     const auto type=read(Op::CellType);
     if(type==Impassable || type==BridgeImpassable) return finish(false);
    }
    if(read(Op::CellFlags)==NoUnits) continue;
    const auto goal=read(Op::GoalUnit);
    if(goal==mover || goal==ignore || goal==input.invalidID) continue;
    if(!hasMover) return finish(false);
    if(!read(Op::Resolve,goal)) continue;
    if(read(Op::Allied)) return finish(false);
    if(read(Op::CellFlags)==Fixed && !read(Op::CanCrush)) return finish(false);
   } else {
    const auto flags=read(Op::CellFlags);
    if(flags==UnitGoal || flags==GoalOtherMoving) result.allyGoal=true;
    else if(flags==NoUnits) continue;
    const auto unit=read(Op::PosUnit);
    if(unit==read(Op::MoverID) || unit==ignore) continue;
    bool check=false,exists=false;
    if(flags==Moving || flags==GoalOtherMoving) {
     exists=read(Op::Resolve,unit)!=0;
     if(exists && read(Op::Allied)) result.allyMoving=true;
     if(input.considerTransient) check=true;
    }
    if(flags==Fixed) {check=true;exists=read(Op::Resolve,unit)!=0;}
    if(check && exists) {
     if(read(Op::HasAI)) {
      const auto currentIgnore=read(Op::IgnoreID);
      const auto currentUnit=read(Op::UnitID);
      if(currentIgnore==currentUnit) check=false;
     }
    }
    if(!check || !exists) continue;
    if(input.infantryThroughInfantry && read(Op::MoverInfantry) && read(Op::UnitInfantry)) continue;
    if(read(Op::Allied)) {
     if(!read(Op::UnitHasAI)) return finish(false);
     if(input.legacy && !read(Op::UnitIdle)) return finish(false);
     bool found=false;
     for(std::size_t i=0;i<numAllies;++i) if(allies[i]==read(Op::UnitID)) {found=true;break;}
     if(!found) {
      ++result.allyFixedCount;
      if(numAllies<allies.size()) allies[numAllies++]=read(Op::UnitID);
     }
    } else if(!read(Op::CanCrush)) result.enemyFixed=true;
   }
  }
 }
 return finish(true);
}

// GeneralsX @feature Codex 27/10/2026 A bounded, pointer-free record of the exact live query reads.
// This is a historical query transcript, not a reusable world snapshot or a search result.
struct Event {
 Op op{};
 std::uint32_t a=0,b=0,c=0,value=0;
};
struct Transcript {
 static constexpr std::size_t capacity=512;
 Input input{};
 Result expected{};
 std::array<Event,capacity> events{};
 std::size_t count=0;
 bool overflow=false;
 void record(Op op,std::uint32_t a,std::uint32_t b,std::uint32_t c,std::uint32_t value) {
  if(count==events.size()){overflow=true;return;}
  events[count++]={op,a,b,c,value};
 }
};
struct Replay {
 const Transcript& transcript;
 std::size_t position=0;
 std::uint32_t read(Op op,std::uint32_t a,std::uint32_t b,std::uint32_t c) {
  if(position==transcript.count) throw std::runtime_error("Occupancy transcript exhausted");
  const auto& e=transcript.events[position++];
  if(e.op!=op || e.a!=a || e.b!=b || e.c!=c) throw std::runtime_error("Occupancy read dependency mismatch");
  return e.value;
 }
};
inline bool validate(const Transcript& transcript) {
 if(transcript.overflow) return false;
 Replay replay{transcript};
 return evaluate(transcript.input,replay)==transcript.expected && replay.position==transcript.count;
}
}
