#!/usr/bin/env python3
"""Exercise the real cache-reset helper against temporary filesystem trees."""
# GeneralsX @test Codex 26/10/2026 Verify opt-in deletion scope, request consumption and symlink handling.
import unittest
from compiled_harness import run_cpp

PREFIX = r'''
#include "dxvkcachemaintenance.h"
#include <cassert>
#include <chrono>
using namespace gxcache;
struct Fixture {
 fs::path home,docs,cache;
 Fixture(){home=fs::temp_directory_path()/("gx-cache-reset-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));assert(fs::create_directory(home));docs=home/"Documents";cache=home/"Library/Caches";fs::create_directories(docs);fs::create_directories(cache);}
 ~Fixture(){fs::remove_all(home);}
 void put(const fs::path&p){fs::create_directories(p.parent_path());std::ofstream(p)<<"preserve";}
 void request(){fs::create_directory(docs/"Clear DXVK Cache");}
};
'''


class CacheResetTest(unittest.TestCase):
    def test_explicit_request_clears_only_managed_cache_files(self):
        run_cpp(PREFIX + r'''
int main(){Fixture f;
 auto standard=f.cache/"GeneralsXZH.dxvk-cache",test=f.cache/"dxvk-test-123/Game.dxvk-cache";
 f.put(standard);f.put(test);f.put(f.cache/"unrelated.bin");f.put(f.cache/"dxvk-test-123/keep.txt");
 f.put(f.cache/"other/Game.dxvk-cache");f.put(f.cache/"dxvk-test-123/deeper/Game.dxvk-cache");
 f.put(f.docs/"Options.ini");f.put(f.docs/"save.sav");f.put(f.docs/"TexturesZH.big");
 auto nothing=clearRequested(f.home,f.cache);assert(!nothing.requested && fs::exists(standard));
 f.request();auto r=clearRequested(f.home,f.cache/"dxvk-test-123");assert(r.completed && r.removed==2);
 assert(!fs::exists(standard) && !fs::exists(test) && !fs::exists(f.docs/"Clear DXVK Cache"));
 assert(fs::exists(f.cache/"unrelated.bin") && fs::exists(f.cache/"other/Game.dxvk-cache"));
 assert(fs::exists(f.cache/"dxvk-test-123/keep.txt") && fs::exists(f.cache/"dxvk-test-123/deeper/Game.dxvk-cache"));
 assert(fs::exists(f.docs/"Options.ini") && fs::exists(f.docs/"save.sav") && fs::exists(f.docs/"TexturesZH.big"));
 assert(fs::exists(f.docs/"DXVK Cache Reset Result.txt"));
 assert(!clearRequested(f.home,f.cache).requested);
}
''')

    def test_symlinked_files_directories_and_report_are_not_followed(self):
        run_cpp(PREFIX + r'''
int main(){Fixture f;auto outside=f.home/"outside/keep.dxvk-cache";f.put(outside);
 fs::create_symlink(outside,f.cache/"link.dxvk-cache");
 fs::create_directory_symlink(outside.parent_path(),f.cache/"dxvk-test-link");
 fs::create_symlink(outside,f.docs/"DXVK Cache Reset Result.txt");
 f.request();auto r=clearRequested(f.home,f.cache);assert(r.completed && r.removed==0 && fs::exists(outside));
 std::ifstream in(outside);std::string text;in>>text;assert(text=="preserve");
}
''')

    def test_nonempty_or_symlinked_request_does_not_clear(self):
        run_cpp(PREFIX + r'''
int main(){Fixture f;auto file=f.cache/"Game.dxvk-cache";f.put(file);f.request();f.put(f.docs/"Clear DXVK Cache/keep.txt");
 auto r=clearRequested(f.home,f.cache);assert(!r.completed && r.errors && fs::exists(file));
 fs::remove_all(f.docs/"Clear DXVK Cache");fs::create_directory_symlink(f.cache,f.docs/"Clear DXVK Cache");
 r=clearRequested(f.home,f.cache);assert(!r.completed && fs::exists(file));
}
''')

    def test_external_override_and_cache_root_symlink_are_not_deleted(self):
        run_cpp(PREFIX + r'''
int main(){Fixture f;auto outside=f.home/"outside/keep.dxvk-cache";f.put(outside);f.request();
 auto r=clearRequested(f.home,outside.parent_path());assert(!r.completed && fs::exists(outside) && fs::exists(f.docs/"Clear DXVK Cache"));
 fs::remove_all(f.cache);fs::create_directory_symlink(outside.parent_path(),f.cache);
 r=clearRequested(f.home,f.cache);assert(!r.completed && fs::exists(outside));
}
''')

    def test_empty_cache_and_regular_file_request(self):
        run_cpp(PREFIX + r'''
int main(){Fixture f;f.put(f.docs/"Clear DXVK Cache");auto r=clearRequested(f.home,f.cache);assert(r.completed && r.removed==0 && !fs::exists(f.docs/"Clear DXVK Cache"));}
''')


if __name__ == '__main__':
    unittest.main()
