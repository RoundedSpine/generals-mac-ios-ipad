#!/usr/bin/env python3
"""Validate the native UIKit diagnostic boundary without claiming device latency."""
# GeneralsX @test Codex 25/10/2026 Check patch safety, native clock calculations, pairing and C bridge ABI.
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
import unittest
from test_hitch_diagnostics import run_cpp, LIB

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / 'cmake/patch-sdl3-ios-touch-probe.cmake'
CALLBACKS = [('touchesBegan', 'SDL_SendTouch', 'SDL_EVENT_FINGER_DOWN'),
             ('touchesEnded', 'SDL_SendTouch', 'SDL_EVENT_FINGER_UP'),
             ('touchesCancelled', 'SDL_SendTouch', 'SDL_EVENT_FINGER_CANCELED'),
             ('touchesMoved', 'SDL_SendTouchMotion', 'SDL_EVENT_FINGER_MOTION')]
# Reviewed callback signatures/send shape from pinned SDL 3.4.2 SDL_uikitview.m.
# https://github.com/libsdl-org/SDL/blob/release-3.4.2/src/video/uikit/SDL_uikitview.m
VIEW = '// retained source prefix\n@implementation SDL_uikitview\n'
for name, send, kind in CALLBACKS:
    args = '\n                      touchId, (SDL_FingerID)(uintptr_t)touch, sdlwindow,\n'
    if send == 'SDL_SendTouch':
        args += '                      ' + kind + ', locationInView.x, locationInView.y, pressure);\n'
    else:
        args += '                      locationInView.x, locationInView.y, pressure);\n'
    VIEW += ('- (void)' + name + ':(NSSet *)touches withEvent:(UIEvent *)event\n{\n'
             '    for (UITouch *touch in touches) {\n'
             '        ' + send + '(UIKit_GetEventTimestamp([event timestamp]),' + args + '    }\n}\n')
VIEW += '@end\n'


def apply(directory):
    return subprocess.run(['cmake', '-DSDL3_SOURCE_DIR=' + str(directory), '-P', str(PATCH)],
                          text=True, capture_output=True, timeout=30)


class UIKitProbeTest(unittest.TestCase):
    def fixture(self, directory, content=VIEW):
        source = Path(directory) / 'src/video/uikit/SDL_uikitview.m'
        source.parent.mkdir(parents=True)
        source.write_text(content)
        return source

    def test_patch_is_idempotent_and_preserves_original_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.fixture(temporary)
            result = apply(temporary)
            self.assertEqual(result.returncode, 0, result.stderr)
            patched = source.read_text()
            self.assertTrue(patched.startswith('// retained source prefix\n'))
            self.assertEqual(patched.count('UIKit_GetEventTimestamp([event timestamp])'), 4)
            self.assertEqual(patched.count('const Uint64 gxCallbackNS'), 4)
            self.assertEqual(patched.count('NSProcessInfo.processInfo.systemUptime'), 4)
            # Removing ONLY diagnostic inserts recovers all original callback code.
            recovered = patched[patched.index('@implementation SDL_uikitview'):]
            recovered = recovered.replace('    const Uint64 gxCallbackNS = SDL_GetTicksNS();\n'
                                          '    const NSTimeInterval gxCallbackUptime = NSProcessInfo.processInfo.systemUptime;\n', '')
            for name, send, kind in CALLBACKS:
                insert = ('const Uint64 gxSourceNS = UIKit_GetEventTimestamp([event timestamp]);\n'
                          '        GXRecordUIKitTouch(' + kind + ', gxSourceNS, touch, event, gxCallbackNS, gxCallbackUptime);\n'
                          '        ' + send + '(gxSourceNS,')
                self.assertIn(insert, recovered)
                recovered = recovered.replace(insert, send + '(UIKit_GetEventTimestamp([event timestamp]),', 1)
            self.assertEqual(recovered, VIEW[VIEW.index('@implementation'):])
            self.assertEqual((source.parent / 'GeneralsXUIKitTouchProbe.h').read_bytes(),
                             (LIB / 'iosuikittouchprobe.h').read_bytes())
            self.assertEqual(apply(temporary).returncode, 0)
            self.assertEqual(source.read_text(), patched)

    def test_changed_send_context_fails_without_partial_source_edit(self):
        with tempfile.TemporaryDirectory() as temporary:
            original = VIEW.replace('SDL_SendTouchMotion(UIKit_GetEventTimestamp([event timestamp]),',
                                    'SDL_SendTouchMotion(0,')
            source = self.fixture(temporary, original)
            result = apply(temporary)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('context changed', result.stderr)
            self.assertEqual(source.read_text(), original)

    def test_native_clock_ages_and_output_cap(self):
        result = run_cpp(r'''
#include "uikittouchtiming.h"
#include <cassert>
int main() {
 GXUIKitTouchSample sample{1000000000,42,2000000000,100.0,98.0,99.9,1,0};
 assert(UIKitNativeAgeMs(0,10)==-1.0 && UIKitNativeAgeMs(20,10)==-1.0);
 TraceUIKitTouchTiming(&sample,1,sample.source_ns,2003000000,2002000000,0,true);
 for(int i=0;i<270;++i) TraceUIKitTouchTiming(nullptr,1,0,1,0,2,true);
}
''')
        self.assertIn('event_age_ms=2000.00 touch_age_ms=100.00 converted_age_ms=1000.00 callback_to_watch_ms=2.00', result.stderr)
        self.assertIn('matched=0 kind=-1', result.stderr)
        self.assertEqual(result.stderr.count('matched='), 256)
        self.assertEqual(result.stderr.count('further native messages suppressed'), 1)

    def test_native_tracker_fifo_overwrite_and_cross_thread_pairing(self):
        result = run_cpp(r'''
#include "uikittouchtiming.h"
#include <cassert>
#include <thread>
int main() {
 UIKitTouchTiming tracker; GXUIKitTouchSample a{10,42,20,100,99,99.5,1,0},b=a,out{};
 uint64_t lost=0; b.callback_ns=30;tracker.Record(a);tracker.Record(b);
 assert(!tracker.Take(1,10,43,out,lost));
 assert(tracker.Take(1,10,42,out,lost) && out.callback_ns==20);
 assert(tracker.Take(1,10,42,out,lost) && out.callback_ns==30);
 assert(!tracker.Take(1,10,42,out,lost));
 for(unsigned i=0;i<2050;++i) { a.source_ns=100+i;tracker.Record(a); }
 assert(!tracker.Take(1,100,42,out,lost) && lost==2);
 UIKitTouchTiming concurrent;std::atomic<unsigned> published{0},consumed{0};
 std::thread delivery([&] {
   for(unsigned i=1;i<=3000;++i) {
     while(consumed.load()!=i-1) std::this_thread::yield();
     a.source_ns=i; concurrent.Record(a);published=i;
   }
 });
 for(unsigned i=1;i<=3000;++i) {
   while(published.load()!=i) std::this_thread::yield();
   assert(concurrent.Take(1,i,42,out,lost) && !lost && out.source_ns==i);consumed=i;
 }
 delivery.join();
}
''')
        self.assertEqual(result.returncode, 0)

    def test_bridge_header_compiles_as_c(self):
        with tempfile.TemporaryDirectory() as temporary:
            code = Path(temporary) / 'bridge.c'
            binary = Path(temporary) / 'bridge'
            code.write_text('#pragma pack(push,4)\n#include "iosuikittouchprobe.h"\n#pragma pack(pop)\n#include <stddef.h>\n'
                            '_Static_assert(sizeof(GXUIKitTouchSample)==56, "stable sample ABI");\n'
                            '_Static_assert(offsetof(GXUIKitTouchSample,type)==48, "stable type offset");\n'
                            'static void record(const GXUIKitTouchSample* s) { (void)s; }\n'
                            'int main(void) { GXUIKitTouchProbe p={record}; GXUIKitTouchSample s={0}; p.record(&s); return 0; }\n')
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Werror', '-I', str(LIB),
                            str(code), '-o', str(binary)], check=True, capture_output=True, timeout=30)
            subprocess.run([str(binary)], check=True, timeout=10)

    @unittest.skipUnless(sys.platform == 'darwin', 'UIKit syntax requires the Apple iOS SDK')
    def test_actual_objective_c_probe_helper_with_ios_sdk(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = self.fixture(temporary)
            self.assertEqual(apply(temporary).returncode, 0)
            patched = source.read_text()
            helper = patched[patched.index('static void GXRecordUIKitTouch'):patched.index('@implementation')]
            code = Path(temporary) / 'native.m'
            code.write_text('#import <UIKit/UIKit.h>\n#include "iosuikittouchprobe.h"\n'
                            'typedef uint32_t Uint32; typedef uint64_t Uint64; typedef uint32_t SDL_PropertiesID;\n'
                            'extern SDL_PropertiesID SDL_GetGlobalProperties(void);\n'
                            'extern void* SDL_GetPointerProperty(SDL_PropertiesID,const char*,void*);\n' + helper)
            sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
            result = subprocess.run(['xcrun', '--sdk', 'iphoneos', 'clang', '-fsyntax-only', '-fobjc-arc',
                                     '-target', 'arm64-apple-ios16.0', '-isysroot', sdk, '-I', str(LIB), str(code)],
                                    text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
