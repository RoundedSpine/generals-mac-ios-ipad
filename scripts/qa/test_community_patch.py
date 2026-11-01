#!/usr/bin/env python3
"""Verify compiled patch staging, archive priority and retail-root exclusion."""
# GeneralsX @test Codex 26/10/2026 Test the patch as an overlay, never a replacement retail asset root.
import importlib.util
import json
import os
import re
import sys
from types import SimpleNamespace
from pathlib import Path
import struct
import subprocess
import hashlib
import tempfile
import unittest
from unittest.mock import patch
from compiled_harness import ROOT, run_cpp

spec = importlib.util.spec_from_file_location('patch_stage', ROOT / 'scripts/build/ios/stage-community-patch.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
build_spec = importlib.util.spec_from_file_location('patch_build', ROOT / 'scripts/build/ios/build-community-patch.py')
patch_build = importlib.util.module_from_spec(build_spec)
build_spec.loader.exec_module(patch_build)
SOURCE = (ROOT / 'Core/GameEngineDevice/Source/StdDevice/Common/StdBIGFileSystem.cpp').read_text()


def function(marker):
    a = SOURCE.index(marker)
    return SOURCE[a:SOURCE.index('\n}', a) + 2]


class CommunityPatchTest(unittest.TestCase):
    def test_blender_install_path_is_data_not_python_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            directory = source / 'Patch104pZH/Scripts/Windows'
            directory.mkdir(parents=True)
            original = {'tools': {'list': [{'name': 'blender', 'files': [{'sha256': 'keep-this-hash', 'callList': [
                {'call':'{TOOLS_DIR}/blender.exe','callArgs':{'--background':'','--python-expr':'old path expression'}}]}]}]}}
            path = directory / 'WindowsTools.json'
            path.write_text(json.dumps(original))
            with patch.dict(os.environ):
                generated = json.loads(patch_build.prepare_tools(source).read_text())
                self.assertEqual(json.loads(path.read_text()), original)
                file = generated['tools']['list'][0]['files'][0]
                self.assertEqual(file['sha256'], 'keep-this-hash')
                args = file['callList'][0]['callArgs']
                self.assertEqual(args['--python-exit-code'], '1')
                self.assertLess(list(args).index('--python-exit-code'), list(args).index('--python-expr'))
                windows_path = r"D:\a\new\test\quote's dir\io_mesh_w3d.zip"
                os.environ[patch_build.ADDON_ENV] = windows_path
                seen = []
                bpy = SimpleNamespace(ops=SimpleNamespace(preferences=SimpleNamespace(addon_install=lambda **kwargs: seen.append(kwargs))))
                with patch.dict(sys.modules, {'bpy': bpy}):
                    exec(args['--python-expr'], {})
                self.assertEqual(seen, [{'overwrite': True, 'filepath': windows_path}])
                self.assertFalse(any(ord(char)<32 for char in seen[0]['filepath']))

    def test_only_selected_pack_metadata_without_install_or_run(self):
        config = {'commit':'a'*40,'builder_commit':'b'*40,'pack':'FullEnglish'}
        calls = []
        with patch.object(patch_build.subprocess, 'check_output', side_effect=['a'*40,'b'*40]), patch.object(patch_build, 'prepare_tools', return_value=Path('adapted-tools.json')):
            patch_build.build(Path('source'), config, lambda **kwargs: calls.append(kwargs))
        self.assertEqual(calls[0]['buildList'], ['FullEnglish'])
        self.assertEqual(calls[0]['installList'], ['FullEnglish'])
        for operation in ['install', 'uninstall', 'run']:
            self.assertFalse(calls[0][operation])
        self.assertTrue(calls[0]['build'] and calls[0]['release'])
        def fail(**kwargs): raise RuntimeError('conversion failed')
        with patch.object(patch_build.subprocess, 'check_output', side_effect=['a'*40,'b'*40]), patch.object(patch_build, 'prepare_tools', return_value=Path('adapted-tools.json')):
            with self.assertRaisesRegex(RuntimeError, 'conversion failed'):
                patch_build.build(Path('source'), config, fail)


    def test_big_roundtrip_and_invalid_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / 'data'; data.write_bytes(b'0123456789')
            big = root / 'patch.big'
            stage.write_big([('data/ini/a.ini', data, 2, 4)], big)
            entries = stage.read_big(big)
            self.assertEqual(entries[0][0], 'data/ini/a.ini')
            self.assertEqual(big.read_bytes()[entries[0][2]:], b'2345')
            for name in ['../evil', '/evil', 'C:/evil', 'data/../evil', 'data//a', 'data/./a']:
                with self.assertRaises(ValueError): stage.normalized(name)
            broken = bytearray(big.read_bytes()); broken[16:20] = struct.pack('>I', 0)
            big.write_bytes(broken)
            with self.assertRaises(ValueError): stage.read_big(big)

    def test_staging_priority_manifest_notices_and_incomplete_pack(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'source'; source.mkdir()
            project = source / 'Patch104pZH'; project.mkdir()
            (project / 'ModJsonFiles.json').write_text(json.dumps({'build': {'files': ['items.json']}}))
            (project / 'items.json').write_text(json.dumps({'bundles': {'items': [
                {'name':'OptionalINI','big':True,'namePrefix':'600_899_'},
                {'name':'CoreINI','big':True,'namePrefix':'600_900_'}],
                'packs':[{'name':'FullEnglish','itemNames':['OptionalINI','CoreINI']}]}}))
            for name in ['LICENSE.txt', 'TERMS.txt', 'README.md']: (source / name).write_text('notice')
            pack = root / 'pack'; pack.mkdir()
            core = root / 'core'; core.write_bytes(b'core')
            optional = root / 'optional'; optional.write_bytes(b'optional')
            stage.write_big([('data/ini/gamedata.ini', core, 0, 4), ('data/cursors/c.ani', core, 0, 4),
                             ('data/english/generals.csf', core, 0, 4)], pack / '600_900_CoreINI.big')
            stage.write_big([('data/ini/gamedata.ini', optional, 0, 8)], pack / '600_899_OptionalINI.big')
            cursor = pack / 'Data/Cursors/c.ani'; cursor.parent.mkdir(parents=True); cursor.write_bytes(b'cursor')
            config = {'repository':'example','commit':'a'*40,'builder_commit':'b'*40,'pack':'FullEnglish'}
            def git(args, **kwargs): return (config['commit'] if args[-1] == 'HEAD' else config['builder_commit']) + '\n'
            with patch.object(stage.subprocess, 'check_output', side_effect=git):
                output = root / 'output'; stage.stage(source, pack, output, config)
                content = (output / 'CommunityPatch.big').read_bytes()
                entries = {name:content[offset:offset+size] for name,_,offset,size in stage.read_big(output / 'CommunityPatch.big')}
                self.assertEqual(entries['data/ini/gamedata.ini'], b'optional')
                self.assertEqual(entries['data/cursors/c.ani'], b'cursor')
                self.assertTrue((output / 'Notices/LICENSE.txt').is_file())
                manifest = json.loads((output / 'manifest.json').read_text())
                self.assertEqual(manifest['commit'], config['commit'])
                self.assertEqual(manifest['entries'], 3)
                stage.verify(output, config)
                (output / 'unexpected-link').symlink_to(core)
                with self.assertRaisesRegex(ValueError, 'regular files'):
                    stage.verify(output, config)
                (output / 'unexpected-link').unlink()
                with self.assertRaises(ValueError): stage.verify(output, dict(config, commit='c'*40))
                with self.assertRaises(ValueError): stage.stage(source, pack, output, config)
                # RawBundlePacks links to BigBundleItems and raw loose source files in the project.
                linked_archive = project / '.Build/BigBundleItems/optional.big'
                linked_archive.parent.mkdir(parents=True)
                original_archive = pack / '600_899_OptionalINI.big'
                original_archive.rename(linked_archive)
                original_archive.symlink_to(linked_archive)
                linked_cursor = project / 'GameFilesEdited/Data/Cursors/c.ani'
                linked_cursor.parent.mkdir(parents=True)
                cursor.rename(linked_cursor)
                cursor.symlink_to(linked_cursor)
                linked_output = root / 'linked-output'
                stage.stage(source, pack, linked_output, config)
                self.assertEqual((linked_output / 'CommunityPatch.big').read_bytes(), content)
                self.assertFalse(any(path.is_symlink() for path in linked_output.rglob('*')))
                stage.verify(linked_output, config)
                original_archive.unlink()
                original_archive.symlink_to(core)
                with self.assertRaisesRegex(ValueError, 'outside-project'):
                    stage.stage(source, pack, root / 'outside-output', config)
                (pack / '600_899_OptionalINI.big').unlink()
                with self.assertRaises(ValueError): stage.stage(source, pack, root / 'incomplete', config)

    def test_build_links_reject_broken_directories_and_escape_chains(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / 'project'; project.mkdir()
            link = project / 'link'
            link.symlink_to(project / 'missing')
            with self.assertRaisesRegex(ValueError, 'Broken'):
                stage.pack_input(link, project)
            link.unlink(); link.symlink_to(project, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'not a regular file'):
                stage.pack_input(link, project)
            link.unlink()
            external = root / 'external'; external.write_text('outside')
            chain = project / 'chain'; chain.symlink_to(external)
            link.symlink_to(chain)
            with self.assertRaisesRegex(ValueError, 'outside-project'):
                stage.pack_input(link, project)


    def test_current_worker_profile_and_explicit_patch_build(self):
        workflow = (ROOT / '.github/workflows/build-ios.yml').read_text()
        profiles = json.loads(re.search(r"GX_MOD_TESTING_PROFILE:.*fromJSON\('([^']+)'\)", workflow)[1])
        for branch, expected in [('experiment/ios-mod-testing', 'ON'), ('experiment/ios-community-patch', 'ON'), ('main', 'OFF')]:
            self.assertEqual('ON' if branch in profiles else 'OFF', expected)
        flags = re.findall(r'-D(GENERALS_[A-Z_]+)=\$\{\{ env.GX_MOD_TESTING_PROFILE \}\}', workflow)
        for flag in ['SEARCH_CONTEXT', 'OCCUPANCY_WORKER', 'PARALLEL_PATH_BATCH', 'COMPLETE_PATH_WORKER',
                     'REUSE_PATH_CONTEXTS', 'PATH_WORKER_POOL', 'PATH_FOUR_REQUESTS', 'PATH_LOOKAHEAD',
                     'FAST_ZONE_MERGES', 'FROZEN_OCCUPANCY_CACHE', 'PATH_TIMING', 'EXCLUSIVE_PATH_WORKER', 'QUAD_LISTS']:
            self.assertIn('GENERALS_' + flag, flags)
        self.assertIn('experiment/ios-community-patch', workflow.split('workflow_dispatch:', 1)[0])
        self.assertIn("github.event_name == 'workflow_dispatch' || contains(github.event.head_commit.message, '[build community patch]')", workflow)
        self.assertIn('needs: community-patch', workflow)
        self.assertIn("needs.community-patch.result == 'success'", workflow)
        self.assertIn('stage-community-patch.py --verify build/community-patch', workflow)
        self.assertIn('macos-15', workflow)

    def test_cmake_profile_provenance_and_compile_definitions(self):
        source = (ROOT / 'CMakeLists.txt').read_text()
        block = source[source.index('option(GENERALS_COMMUNITY_PATCH '):source.index('# GeneralsX @build Codex 26/10/2026 Keep the bounded')]
        config = json.loads((ROOT / 'ios/community-patch/source.json').read_text())
        for mode in ['on', 'off', 'bad_pin', 'bad_profile']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); (root / 'ios/community-patch').mkdir(parents=True)
                expected = dict(config)
                if mode == 'bad_pin': expected['commit'] = 'a' * 39
                if mode == 'bad_profile': expected['pack'] = 'CoreEnglish'
                (root / 'ios/community-patch/source.json').write_text(json.dumps(expected))
                main = '#include <cassert>\n#include <string>\nint main(){\n'
                if mode == 'off':
                    main += '#ifdef GENERALS_COMMUNITY_PATCH\n#error patch enabled unexpectedly\n#endif\n'
                else:
                    main += 'assert(std::string(GENERALS_COMMUNITY_PATCH_PROFILE)=="FullEnglish");\n'
                    main += 'assert(std::string(GENERALS_COMMUNITY_PATCH_COMMIT)=="' + config['commit'] + '");\n'
                (root / 'main.cpp').write_text(main + '}\n')
                (root / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.25)\nproject(profile CXX)\n' + block +
                                                   '\nadd_executable(check main.cpp)\n')
                result = subprocess.run(['cmake', '-S', str(root), '-B', str(root / 'build'),
                    '-DGENERALS_COMMUNITY_PATCH=' + ('OFF' if mode == 'off' else 'ON')], text=True, capture_output=True)
                if mode.startswith('bad_'):
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn('Invalid pinned Community Patch', result.stderr)
                    continue
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                saved = root / 'build/community-patch-source.json'
                self.assertEqual(mode != 'off', saved.exists())
                if saved.exists(): self.assertEqual(config, json.loads(saved.read_text()))
                built = subprocess.run(['cmake', '--build', str(root / 'build')], text=True, capture_output=True)
                self.assertEqual(0, built.returncode, built.stdout + built.stderr)
                subprocess.run([str(root / 'build/check')], check=True)

    def test_pinned_profile_is_full_english(self):
        config = json.loads((ROOT / 'ios/community-patch/source.json').read_text())
        self.assertEqual(config['repository'], 'https://github.com/TheSuperHackers/GeneralsGamePatch.git')
        self.assertEqual(config['pack'], 'FullEnglish')
        self.assertRegex(config['commit'], r'^[0-9a-f]{40}$')
        self.assertRegex(config['builder_commit'], r'^[0-9a-f]{40}$')

    def test_valid_hash_cannot_hide_missing_english_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); payload = root / 'payload'; payload.write_bytes(b'game data')
            stage.write_big([('data/ini/gamedata.ini', payload, 0, 9)], root / 'CommunityPatch.big')
            config = {'pack': 'FullEnglish'}
            (root / 'manifest.json').write_text(json.dumps(dict(config, entries=1,
                archive_sha256=hashlib.sha256((root / 'CommunityPatch.big').read_bytes()).hexdigest())))
            with self.assertRaisesRegex(ValueError, 'missing required English'):
                stage.verify(root, config)

    def test_loose_files_keep_precedence_over_patch_and_retail(self):
        source = (ROOT / 'Core/GameEngine/Source/Common/System/FileSystem.cpp').read_text()
        start = source.index('File*\t\tFileSystem::openFile(')
        body = source[start:source.index('\n}', start) + 2]
        run_cpp(r'''
#include <cassert>
#include <cstddef>
#define USE_PERF_TIMER(x)
#define ENABLE_FILESYSTEM_EXISTENCE_CACHE 0
using Char=char;using Int=int;using FileInstance=unsigned;
struct File{};File loose,patched,retail;
bool hasLoose=true;int archiveReads=0;
struct Local{bool doesFileExist(const char*){return hasLoose;}
 File*openFile(const char*,int,size_t){return hasLoose?&loose:nullptr;}}local;
struct Archives{File*openFile(const char*,int,FileInstance i){++archiveReads;return i?&retail:&patched;}}archives;
auto*TheLocalFileSystem=&local;auto*TheArchiveFileSystem=&archives;
struct FileSystem{File*openFile(const char*,int,size_t,FileInstance);};
''' + body + r'''
int main(){FileSystem fs;assert(fs.openFile("data/ini/gamedata.ini",0,0,0)==&loose&&archiveReads==0);
 assert(fs.openFile("data/ini/gamedata.ini",0,0,1)==&patched);
 assert(fs.openFile("data/ini/gamedata.ini",0,0,2)==&retail);
 hasLoose=false;assert(fs.openFile("data/ini/gamedata.ini",0,0,0)==&patched);
 assert(fs.openFile("data/ini/gamedata.ini",0,0,1)==&retail);}
''')

    def test_mount_after_both_retail_sets_and_exclude_recursive_scan(self):
        prefix = r'''
#include <string>
#include <vector>
#include <map>
#include <memory>
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#define RTS_ZEROHOUR 1
#define TRUE true
#define FALSE false
#define GENERALS_COMMUNITY_PATCH_PROFILE "FullEnglish"
#define GENERALS_COMMUNITY_PATCH_COMMIT "6c7f40d6af6a4babb77a33a4502ec7656446c13e"
#define DEBUG_ASSERTCRASH(c,m) ((void)0)
#define DEBUG_LOG(m) ((void)0)
using Bool=bool;
struct AsciiString{std::string value;AsciiString(const char*s=""):value(s){}
 const char*str()const{return value.c_str();}bool isNotEmpty()const{return !value.empty();}
 void concat(const char*s){value+=s;}bool operator<(const AsciiString&b)const{return value<b.value;}
 static std::string lower(std::string v){for(auto&c:v)c=static_cast<char>(tolower(static_cast<unsigned char>(c)));return v;}
 int compareNoCase(const char*s)const{return lower(value).compare(lower(s));}
 bool endsWithNoCase(const char*s)const{std::string suffix(s);return value.size()>=suffix.size() && lower(value.substr(value.size()-suffix.size()))==lower(suffix);}};
using FilenameList=std::vector<AsciiString>;using FilenameListIter=FilenameList::iterator;
std::vector<std::string> calls;bool retail=true,base=true,exists=true,openFails=false,mountThrows=false;
FilenameList inputs;int alive=0;
struct Local{void setAssetRootPath(const AsciiString&){calls.push_back("root");}
 bool doesFileExist(const char*){return exists;}
 void getFileListInDirectory(AsciiString,const char*,AsciiString,FilenameList&out,bool){out=inputs;}}local;
auto*TheLocalFileSystem=&local;
struct ArchiveFile{ArchiveFile(){++alive;}~ArchiveFile(){--alive;}};
struct StdBIGFileSystem{
 std::map<AsciiString,ArchiveFile*>m_archiveFileMap;
 ~StdBIGFileSystem(){for(auto&p:m_archiveFileMap)delete p.second;}
 void init();bool loadBigFilesFromDirectory(AsciiString,AsciiString,bool=false);
 void add(const char*name){if(!m_archiveFileMap.count(name))m_archiveFileMap.emplace(name,new ArchiveFile);}
 ArchiveFile*openArchiveFile(const char*path){calls.push_back(path);return openFails?nullptr:new ArchiveFile;}
 void loadIntoDirectoryTree(ArchiveFile*,bool overwrite){calls.push_back(overwrite?"overlay":"retail");if(mountThrows)throw std::runtime_error("directory failed");}
};
bool loadPrimaryGameAssets(StdBIGFileSystem*f,AsciiString*path){calls.push_back("primary");*path=AsciiString("Documents");
 if(retail){f->add("/Documents/INIZH.big");f->add("/Documents/TexturesZH.big");f->add("/Documents/W3DZH.big");}return retail;}
void loadBaseGeneralsAssetsForZH(StdBIGFileSystem*f,AsciiString){calls.push_back("base");
 if(base){f->add("/Documents/ZH_Generals/INI.big");f->add("/Documents/ZH_Generals/Textures.big");f->add("/Documents/ZH_Generals/W3D.big");}}
bool getExecutableDirectory(AsciiString&path){path=AsciiString("/App");return true;}
'''
        body = function('void StdBIGFileSystem::init()') + function('Bool StdBIGFileSystem::loadBigFilesFromDirectory(')
        for enabled in [False, True]:
            run_cpp(('#define GENERALS_COMMUNITY_PATCH 1\n' if enabled else '') + prefix + body + r'''
int main(){{StdBIGFileSystem fs;fs.init();
#ifdef GENERALS_COMMUNITY_PATCH
 assert(calls.back()=="overlay" && calls[2]=="base");assert(fs.m_archiveFileMap.size()==7);
 bool failed=false;try{fs.init();}catch(const std::runtime_error&){failed=true;}assert(failed&&alive==7);
#else
 assert(fs.m_archiveFileMap.size()==6);
#endif
}assert(!alive);
#ifdef GENERALS_COMMUNITY_PATCH
 for(int failure=0;failure<5;++failure){exists=failure!=0;retail=failure!=1;base=failure!=2;openFails=failure==3;mountThrows=failure==4;
 {StdBIGFileSystem fs;bool failed=false;try{fs.init();}catch(const std::runtime_error&){failed=true;}assert(failed);}
 assert(!alive);}
 exists=retail=base=true;openFails=mountThrows=false;
 for(const char*path:{"/App/CommunityPatch/CommunityPatch.big","C:\\App\\CommunityPatch\\CommunityPatch.big"}){
 inputs={AsciiString(path)};calls.clear();StdBIGFileSystem fs;assert(!fs.loadBigFilesFromDirectory("/App","*.big")&&calls.empty());}
#endif
 {inputs={AsciiString("/Documents/INIZH.big")};calls.clear();StdBIGFileSystem fs;
 assert(fs.loadBigFilesFromDirectory("/Documents","*.big")&&calls.size()==2&&calls[1]=="retail");}assert(!alive);
}
''')


if __name__ == '__main__':
    unittest.main()
