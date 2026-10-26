#!/usr/bin/env python3
"""Compile opt-in strip probes with a CPU-only D3D8 stand-in."""
# GeneralsX @test Codex 26/10/2026 Check observation bounds, return values and incomplete index coverage.
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from compiled_harness import ROOT

HEADER = ROOT / 'Core/Libraries/Source/WWVegas/WW3D2/stripdiagnostics.h'
STUB = r'''
#pragma once
struct IDirect3DIndexBuffer8 {int refs=0;void Release(){--refs;}};
'''
PREFIX = r'''
#include <cassert>
#include <thread>
#include <vector>
#include <cstdio>
#include "d3d8.h"
struct Device {
 IDirect3DIndexBuffer8 index;int calls=0,queries=0;
 long GetIndices(IDirect3DIndexBuffer8**out,unsigned*base){++queries;*out=&index;++index.refs;*base=70000;return 0;}
 long DrawPrimitiveUP(unsigned t,unsigned p,const void*data,unsigned stride){++calls;assert(t==5 && p>=2 && !data && stride==16);return -7;}
 long DrawIndexedPrimitive(unsigned t,unsigned minimum,unsigned vertices,unsigned start,unsigned p){++calls;assert(t==5 && minimum==0 && vertices==4 && start==0 && p==2);return -9;}
};
'''


def compile_run(body, enabled=True, sanitizers=False):
    with tempfile.TemporaryDirectory() as temporary:
        p = Path(temporary)
        (p / 'd3d8.h').write_text(STUB)
        (p / 'test.cpp').write_text(('#define GENERALS_STRIP_DIAGNOSTICS 1\n' if enabled else '') + PREFIX + f'\n#include "{HEADER}"\n' + body)
        cmd = [os.environ.get('CXX', 'c++'), '-std=c++17', '-pthread', '-Werror=format', '-I', str(p), str(p / 'test.cpp'), '-o', str(p / 'test')]
        if sanitizers:
            cmd += ['-fsanitize=address,undefined']
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return subprocess.run([str(p / 'test')], capture_output=True, text=True, check=True, timeout=10)


class StripDiagnosticTest(unittest.TestCase):
    def test_nonindexed_and_return_preservation(self):
        r = compile_run(r'''
int main(){Device d;for(int i=0;i<100;++i){assert(GX_STRIP_UP(&d,5,2,nullptr,16)==-7);}assert(d.calls==100 && d.queries==0);}
''')
        self.assertEqual(r.stderr.count('[STRIP_DRAW_BEGIN]'), 1)
        self.assertEqual(r.stderr.count('[STRIP_DRAW_END]'), 1)
        self.assertIn('sentinel16=not_indexed', r.stderr)

    def test_indexed_hit_and_reference_balance(self):
        r = compile_run(r'''
int main(){Device d;unsigned short data[]={0,1,65535,3};gxstrip::capture(&d.index,0,data,4);assert(GX_STRIP_INDEXED(&d,5,0,4,0,2)==-9);assert(d.calls==1 && d.queries==1 && d.index.refs==0);}
''', sanitizers=True)
        self.assertIn('sentinel16=present', r.stderr)
        self.assertIn('base=70000', r.stderr)
        self.assertIn('sentinel16=1', r.stderr)

    def test_partial_coverage_invalidation_and_truncation(self):
        r = compile_run(r'''
int main(){Device d;unsigned short data[80]={};for(int i=0;i<40;++i)data[i]=65535;
gxstrip::capture(&d.index,0,data,80);
gxstrip::describe({1},"fixture",1,"main",5,2,true,&d.index,50,0,0,4);
gxstrip::capture(&d.index,20,data,4);
gxstrip::describe({2},"fixture",2,"main",5,2,true,&d.index,0,0,0,4);
gxstrip::forget(&d.index);
gxstrip::describe({3},"fixture",3,"main",5,2,true,&d.index,20,0,0,4);
}
''')
        self.assertIn('sentinel16=unknown_truncated', r.stderr)
        self.assertEqual(r.stderr.count('sentinel16=unknown '), 2)

    def test_budgets_and_deduplication(self):
        r = compile_run(r'''
int main(){Device d;
 for(unsigned i=0;i<1000;++i)GX_STRIP_UP(&d,5,i+2,nullptr,16);
 assert(d.calls==1000 && gxstrip::state().drawCount==64);
 std::vector<unsigned short> data(gxstrip::ScanBudget,1);
 gxstrip::capture(&d.index,0,data.data(),data.size());
 assert(gxstrip::state().scanned==gxstrip::ScanBudget);
 unsigned short changed[]={65535};gxstrip::capture(&d.index,0,changed,1);
 gxstrip::describe({1},"fixture",1,"main",5,2,true,&d.index,0,0,0,4);
 assert(gxstrip::state().scanned==gxstrip::ScanBudget);
}
''')
        self.assertEqual(r.stderr.count('[STRIP_DRAW_BEGIN]'), 65)
        self.assertEqual(r.stderr.count('[STRIP_DRAW_END]'), 64)
        self.assertIn('sentinel16=unknown ', r.stderr)

    def test_origins_and_upload_report_bound(self):
        r = compile_run(r'''
void submit(Device&d){GX_STRIP_UP(&d,5,2,nullptr,16);}
int main(){Device d;{GX_STRIP_ORIGIN("model");submit(d);{GX_STRIP_ORIGIN("water");submit(d);}assert(std::strcmp(gxstrip::origin(),"model")==0);}submit(d);
 unsigned short index[]={65535};for(int i=0;i<1000;++i)gxstrip::capture(&d.index,0,index,1);
 assert(gxstrip::state().indexReports==64);
}
''')
        self.assertEqual(r.stderr.count('[STRIP_INDEX]'), 64)
        self.assertEqual(r.stderr.count('[STRIP_DRAW_BEGIN]'), 3)

    def test_disabled_preserves_calls_without_logging(self):
        r = compile_run(r'''
int main(){Device d;GX_STRIP_ORIGIN("off");GX_STRIP_CAPTURE(nullptr,0,nullptr,0);GX_STRIP_FORGET(nullptr);assert(GX_STRIP_UP(&d,5,2,nullptr,16)==-7);assert(GX_STRIP_INDEXED(&d,5,0,4,0,2)==-9);assert(d.calls==2 && d.queries==0);}
''', enabled=False)
        self.assertEqual(r.stderr, '')


if __name__ == '__main__':
    unittest.main()
