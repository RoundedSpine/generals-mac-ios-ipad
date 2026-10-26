#!/usr/bin/env python3
"""Check quad geometry/attributes and actual water upload/draw branches."""
# GeneralsX @test Codex 26/10/2026 Preserve strip triangles, winding, upload bounds and HRESULTs.
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from compiled_harness import ROOT

HEADER = ROOT / 'Core/Libraries/Source/WWVegas/WW3D2/quadlist.h'
WATER = (ROOT / 'Core/GameEngineDevice/Source/W3DDevice/GameClient/Water/W3DWaterTracks.cpp').read_text()
a = WATER.index('#ifdef GENERALS_QUAD_LISTS\n\t\tconst UnsignedShort strip[4]')
WATER_FILL = WATER[a:WATER.index('\t\tGX_STRIP_WATER_CAPTURE', a)]
a = WATER.index('// GeneralsX @feature Codex 26/10/2026 The verified water-track quad')
WATER_DRAW = WATER[a:WATER.index('\n#endif', a) + len('\n#endif')]
STUB = '''#pragma once
constexpr unsigned D3DPT_TRIANGLELIST=4,D3DPT_TRIANGLESTRIP=5;
struct IDirect3DIndexBuffer8{void Release(){}};
'''
PREFIX = r'''
#include <cassert>
#include <cstring>
#include "d3d8.h"
struct Vertex{float x,y,z,u,v;unsigned color;};
struct Device{
 int calls=0,queries=0;unsigned topology=0,primitives=0;Vertex output[6]{};
 long GetIndices(IDirect3DIndexBuffer8**out,unsigned*base){++queries;*out=nullptr;*base=0;return 0;}
 long DrawPrimitiveUP(unsigned t,unsigned p,const void*data,unsigned stride){
  ++calls;topology=t;primitives=p;assert(stride==sizeof(Vertex));
  std::memcpy(output,data,(t==4?6:4)*stride);return -23;
 }
};
'''


def run_case(body, lists=True, diagnostics=False):
    with tempfile.TemporaryDirectory() as directory:
        p = Path(directory)
        (p / 'd3d8.h').write_text(STUB)
        source = ('#define GENERALS_QUAD_LISTS 1\n' if lists else '')
        source += ('#define GENERALS_STRIP_DIAGNOSTICS 1\n' if diagnostics else '')
        (p / 'test.cpp').write_text(source + PREFIX + f'\n#include "{HEADER}"\n' + body)
        subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-pthread', '-fsanitize=address,undefined',
                        '-I', str(p), str(p / 'test.cpp'), '-o', str(p / 'test')], check=True, text=True, capture_output=True)
        return subprocess.run([str(p / 'test')], check=True, text=True, capture_output=True, timeout=10)


class QuadListTest(unittest.TestCase):
    def test_screen_winding_attributes_and_return(self):
        run_case(r'''
float area(const Vertex&a,const Vertex&b,const Vertex&c){return (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);}
int main(){
 Vertex strip[4]={{1,1,2,1,1,11},{1,0,3,1,0,22},{0,1,4,0,1,33},{0,0,5,0,0,44}};
 Vertex original[4];std::memcpy(original,strip,sizeof(strip));Device d;
 assert(gxquad::draw(&d,strip)==-23 && d.calls==1 && d.topology==4 && d.primitives==2);
 const unsigned reference[6]={0,1,2,2,1,3};
 for(int i=0;i<6;++i){const auto&a=d.output[i];const auto&b=strip[reference[i]];
  assert(a.x==b.x && a.y==b.y && a.z==b.z && a.u==b.u && a.v==b.v && a.color==b.color);
 }
 assert(area(d.output[0],d.output[1],d.output[2])==area(strip[0],strip[1],strip[2]));
 assert(area(d.output[3],d.output[4],d.output[5])==area(strip[2],strip[1],strip[3]));
 assert(area(d.output[0],d.output[1],d.output[2])*area(d.output[3],d.output[4],d.output[5])>0);
 assert(std::memcmp(original,strip,sizeof(strip))==0);
}
''')

    def test_disabled_retains_original_strip(self):
        run_case(r'''
int main(){Vertex v[4]{};Device d;assert(gxquad::draw(&d,v)==-23);assert(d.topology==5 && d.primitives==2 && d.calls==1 && d.queries==0);}
''', lists=False)

    def test_list_path_does_not_generate_strip_diagnostics(self):
        result = run_case(r'''
int main(){Vertex v[4]{};Device d;assert(gxquad::draw(&d,v)==-23);assert(d.topology==4 && d.queries==0);}
''', diagnostics=True)
        self.assertEqual(result.stderr, '')

    def test_actual_water_fill_and_draw_branches(self):
        body = r'''
using UnsignedShort=unsigned short;using Int=int;
struct DX8Wrapper{
 static unsigned topology,count,vertices;
 static void Draw_Triangles(unsigned start,unsigned n,unsigned min,unsigned v){assert(start==0 && min==0);topology=4;count=n;vertices=v;}
 static void Draw_Strip(unsigned start,unsigned n,unsigned min,unsigned v){assert(start==0 && min==0);topology=5;count=n;vertices=v;}
};
unsigned DX8Wrapper::topology=0,DX8Wrapper::count=0,DX8Wrapper::vertices=0;
int main(){
 const int m_stripSizeX=2,m_stripSizeY=2,m_x=2,m_y=2;
 Int i=0,j=0,k=0,idxCount=4;
 unsigned short storage[8];for(auto&v:storage)v=0xBEEF;auto*ib=storage+1;
''' + WATER_FILL + WATER_DRAW + r'''
#ifdef GENERALS_QUAD_LISTS
 const unsigned short reference[]={2,0,3,3,0,1};
 for(int n=0;n<6;++n)assert(ib[n]==reference[n]);
 assert(storage[0]==0xBEEF && storage[7]==0xBEEF && DX8Wrapper::topology==4);
#else
 const unsigned short reference[]={2,0,3,1};
 for(int n=0;n<4;++n)assert(ib[n]==reference[n]);
 assert(storage[0]==0xBEEF && storage[5]==0xBEEF && DX8Wrapper::topology==5);
#endif
 assert(DX8Wrapper::count==2 && DX8Wrapper::vertices==4);
}
'''
        run_case(body)
        run_case(body, lists=False)


if __name__ == '__main__':
    unittest.main()
