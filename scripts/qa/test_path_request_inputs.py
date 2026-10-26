#!/usr/bin/env python3
"""Compile ordinary request dispatch to verify endpoint ownership and stage ordering."""
# GeneralsX @refactor Codex 27/10/2026 Exercise the actual public entry and serial dispatcher in both modes.
import unittest
from compiled_harness import ROOT, run_cpp

SOURCE = (ROOT / 'Core/GameEngine/Source/GameLogic/AI/AIPathfind.cpp').read_text()
HEADER = (ROOT / 'Core/GameEngine/Include/GameLogic/AIPathfind.h').read_text()


def function(marker):
    start = SOURCE.index(marker)
    return SOURCE[start:SOURCE.index('\n}', start) + 2]


def fixture(enabled):
    start = HEADER.index('\tstruct OrdinaryPathRequest {')
    request = HEADER[start:HEADER.index('\n\t};', start) + 4]
    return ('#define GENERALS_ZH_SEARCH_CONTEXT 1\n' if enabled else '') + r'''
#include <cassert>
#include <string>
#include <vector>
using Bool=bool;
struct Coord3D {float x,y,z;};
struct Player {int getPlayerType(){return 2;}};
const int PLAYER_COMPUTER=2;
struct Object {Player player;Player* getControllingPlayer(){return &player;}};
struct LocomotorSet {};
struct Path {int value;};
int deleted=0;
void deleteInstance(Path* p){assert(p->value==1);++deleted;}
struct Pathfinder {
''' + request + r'''
 struct Zones {std::string* calls;void clearPassableFlags(){*calls+='c';}void setAllPassable(){*calls+='a';}} m_zoneManager;
 std::string calls;
 Coord3D* callerFrom=nullptr;Coord3D* callerTo=nullptr;
 bool mutate=false,quick=true,hierarchy=true,success=true;
 std::vector<Coord3D> seen;
 Path coarse{1},fine{2};
 Pathfinder():m_zoneManager{&calls}{}
 virtual Path* findPath(Object*,const LocomotorSet&,const Coord3D*,const Coord3D*);
 Path* findPathWithInputs(Object*,const LocomotorSet&,const Coord3D*,const Coord3D*);
 bool clientSafeQuickDoesPathExist(const LocomotorSet&,const Coord3D* f,const Coord3D* t){
  calls+='q';seen.push_back(*f);seen.push_back(*t);
  if(mutate){*callerFrom={90,91,92};*callerTo={80,81,82};}
  return quick;
 }
 Path* findHierarchicalPath(bool human,const LocomotorSet&,const Coord3D* f,const Coord3D* t,bool crusher){
  assert(!human&&!crusher);calls+='h';seen.push_back(*f);seen.push_back(*t);return hierarchy?&coarse:nullptr;
 }
 virtual Path* internalFindPath(Object*,const LocomotorSet&,const Coord3D* f,const Coord3D* t){
  calls+='i';seen.push_back(*f);seen.push_back(*t);return success?&fine:nullptr;
 }
};
''' + function('Path *Pathfinder::findPath( Object *obj,') + '\n' + function('Path *Pathfinder::findPathWithInputs(')


class RequestTests(unittest.TestCase):
    def test_normal_dispatch_and_failure_order_in_both_modes(self):
        for enabled in (False, True):
            run_cpp(fixture(enabled) + r'''
int main(){
 for(int scenario=0;scenario<4;++scenario){
  Pathfinder p;Object obj;LocomotorSet loco;Coord3D f{1,2,3},t{4,5,6};
  p.quick=scenario!=1;p.hierarchy=scenario!=2;p.success=scenario!=3;
  deleted=0;auto* result=p.findPath(&obj,loco,&f,&t);
  assert(result==((scenario==1||scenario==3)?nullptr:&p.fine));
  assert(p.calls==(scenario==1?"q":scenario==2?"qchai":"qchi"));
  assert(deleted==(scenario!=1&&scenario!=2));
  for(unsigned i=0;i<p.seen.size();++i){auto v=p.seen[i];assert(v.x==(i%2?4:1)&&v.y==(i%2?5:2)&&v.z==(i%2?6:3));}
 }
}
''')

    def test_experiment_owns_endpoints_across_search_stages(self):
        run_cpp(fixture(True) + r'''
int main(){
 for(bool alias:{false,true}){
  Pathfinder p;Object obj;LocomotorSet loco;Coord3D f{1,2,3},t{4,5,6};
  p.callerFrom=&f;p.callerTo=alias?&f:&t;p.mutate=true;
  assert(p.findPath(&obj,loco,&f,p.callerTo)==&p.fine);
  assert(p.seen.size()==6);
  for(unsigned i=0;i<6;++i){auto v=p.seen[i];bool start=alias||i%2==0;assert(v.x==(start?1:4)&&v.y==(start?2:5)&&v.z==(start?3:6));}
  assert(f.x!=(1)); // Mutating caller storage does not mutate captured inputs.
 }
}
''')

    def test_disabled_mode_retains_original_pointer_semantics(self):
        run_cpp(fixture(False) + r'''
int main(){
 Pathfinder p;Object obj;LocomotorSet loco;Coord3D f{1,2,3},t{4,5,6};
 p.callerFrom=&f;p.callerTo=&t;p.mutate=true;
 p.findPath(&obj,loco,&f,&t);
 assert(p.seen[0].x==1&&p.seen[1].x==4);
 assert(p.seen[2].x==90&&p.seen[3].x==80);
 assert(p.seen[4].x==90&&p.seen[5].x==80);
}
''')

    def test_internal_virtual_override_still_receives_owned_values(self):
        run_cpp(fixture(True) + r'''
struct Derived:Pathfinder{
 Path* internalFindPath(Object*,const LocomotorSet&,const Coord3D* f,const Coord3D* t)override{
  assert(f->x==1&&t->x==4);calls+='v';return &fine;
 }
};
int main(){Derived p;Object obj;LocomotorSet loco;Coord3D f{1,2,3},t{4,5,6};p.callerFrom=&f;p.callerTo=&t;p.mutate=true;
 Pathfinder& base=p;assert(base.findPath(&obj,loco,&f,&t)==&p.fine);assert(p.calls=="qchv");}
''')


if __name__ == '__main__':
    unittest.main()
