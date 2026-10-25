#!/usr/bin/env python3
"""Check the iOS-only SDL pump experiment without claiming UIKit device behavior."""
# GeneralsX @test Codex 25/10/2026 Validate fail-closed patching and execute the patched upstream pump with CF stubs.
from pathlib import Path
import os
import hashlib
import shutil
import tarfile
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / 'cmake/patch-sdl3-ios-event-pump.cmake'
# SDL 3.4.2, src/video/uikit/SDL_uikitevents.m, UIKit_PumpEvents:
# https://github.com/libsdl-org/SDL/blob/release-3.4.2/src/video/uikit/SDL_uikitevents.m
# Retain its control flow; comments are omitted except for the patch anchor.
UPSTREAM = r'''
void UIKit_PumpEvents(SDL_VideoDevice *_this)
{
    if (!UIKit_EventPumpEnabled) {
        return;
    }
    const CFTimeInterval seconds = 0.000002;

    // Pump most event types.
    SInt32 result;
    do {
        result = CFRunLoopRunInMode(kCFRunLoopDefaultMode, seconds, TRUE);
    } while (result == kCFRunLoopRunHandledSource);

    do {
        result = CFRunLoopRunInMode((CFStringRef)UITrackingRunLoopMode, seconds, TRUE);
    } while (result == kCFRunLoopRunHandledSource);
}
'''


def patch(directory):
    return subprocess.run(['cmake', '-DSDL3_SOURCE_DIR=' + str(directory), '-P', str(PATCH)],
                          capture_output=True, text=True, timeout=30)


class IOSEventPumpTest(unittest.TestCase):
    def fixture(self, temporary, text=UPSTREAM):
        path = Path(temporary) / 'src/video/uikit/SDL_uikitevents.m'
        path.parent.mkdir(parents=True)
        path.write_text(text)
        return path

    def test_patch_is_idempotent_and_preserves_tracking_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.fixture(temporary, '// unrelated prefix\n' + UPSTREAM + '// unrelated suffix\n')
            self.assertEqual(patch(temporary).returncode, 0)
            first = path.read_text()
            self.assertIn('CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.001, FALSE);', first)
            self.assertIn('CFRunLoopRunInMode((CFStringRef)UITrackingRunLoopMode, seconds, TRUE);', first)
            self.assertTrue(first.startswith('// unrelated prefix\n'))
            self.assertTrue(first.endswith('// unrelated suffix\n'))
            self.assertEqual(patch(temporary).returncode, 0)
            self.assertEqual(path.read_text(), first)

    def test_changed_upstream_context_fails_without_modification(self):
        with tempfile.TemporaryDirectory() as temporary:
            original = UPSTREAM.replace('seconds, TRUE', 'seconds, FALSE')
            path = self.fixture(temporary, original)
            result = patch(temporary)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('context changed', result.stderr)
            self.assertEqual(path.read_text(), original)

    def test_production_fetchcontent_declaration_patches_only_ios(self):
        cmake_source = (ROOT / 'cmake/sdl3.cmake').read_text()
        start = cmake_source.index('    set(_sdl3_ios_patch_args)')
        declaration = cmake_source[start:cmake_source.index('    # Configure SDL3 build options', start)]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / 'mock-sdl'
            self.fixture(source)
            (source / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.21)\nproject(MockSDL NONE)\n')
            archive = base / 'sdl.tar.gz'
            with tarfile.open(archive, 'w:gz') as package:
                package.add(source, arcname='mock-sdl')
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            project = base / 'project'
            project.mkdir()
            shutil.copyfile(PATCH, project / PATCH.name)
            for platform in ['iOS', 'Linux']:
                (project / 'CMakeLists.txt').write_text(
                    'cmake_minimum_required(VERSION 3.21)\nproject(PumpPatch NONE)\ninclude(FetchContent)\n'
                    + 'set(CMAKE_SYSTEM_NAME "' + platform + '")\n'
                    + 'set(SDL3_URL "' + archive.as_uri() + '")\n'
                    + 'set(SDL3_URL_HASH "SHA256=' + digest + '")\n'
                    + declaration + '\nFetchContent_MakeAvailable(SDL3)\n')
                build = base / ('build-' + platform)
                result = subprocess.run(['cmake', '-S', str(project), '-B', str(build)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                populated = (build / '_deps/sdl3-src/src/video/uikit/SDL_uikitevents.m').read_text()
                if platform == 'iOS':
                    self.assertIn('kCFRunLoopDefaultMode, 0.001, FALSE', populated)
                else:
                    self.assertEqual(populated, UPSTREAM)

    def test_patched_pump_executes_one_default_slice_and_honors_disabled_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.fixture(temporary)
            self.assertEqual(patch(temporary).returncode, 0)
            harness = r'''
#include <cassert>
#include <cmath>
struct SDL_VideoDevice {};
using CFTimeInterval=double; using SInt32=int; using CFStringRef=const char*;
constexpr bool TRUE=true,FALSE=false;
const char* kCFRunLoopDefaultMode="default";
const char* UITrackingRunLoopMode="tracking";
constexpr int kCFRunLoopRunHandledSource=1, TimedOut=2;
bool UIKit_EventPumpEnabled=true;
int defaults=0,tracking=0;
int CFRunLoopRunInMode(const char* mode,double seconds,bool afterSource) {
 if(mode==kCFRunLoopDefaultMode) {
   ++defaults; assert(std::fabs(seconds-.001)<1e-12 && !afterSource);
   return TimedOut;
 }
 assert(mode==UITrackingRunLoopMode && std::fabs(seconds-.000002)<1e-12 && afterSource);
 return ++tracking==1 ? kCFRunLoopRunHandledSource : TimedOut;
}
BODY
int main() {
 UIKit_EventPumpEnabled=false; UIKit_PumpEvents(nullptr); assert(!defaults && !tracking);
 UIKit_EventPumpEnabled=true; UIKit_PumpEvents(nullptr); assert(defaults==1 && tracking==2);
}
'''.replace('BODY', path.read_text())
            code = Path(temporary) / 'pump.cpp'
            binary = Path(temporary) / 'pump'
            code.write_text(harness)
            result = subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', str(code), '-o', str(binary)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
