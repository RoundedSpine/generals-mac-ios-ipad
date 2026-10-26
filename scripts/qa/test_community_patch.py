#!/usr/bin/env python3
"""Verify compiled patch staging, archive priority and retail-root exclusion."""
# GeneralsX @test Codex 26/10/2026 Test the patch as an overlay, never a replacement retail asset root.
import importlib.util
import json
import os
import sys
from types import SimpleNamespace
from pathlib import Path
import struct
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
            stage.write_big([('data/ini/gamedata.ini', core, 0, 4), ('data/cursors/c.ani', core, 0, 4)], pack / '600_900_CoreINI.big')
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
                self.assertEqual(manifest['entries'], 2)
                stage.verify(output, config)
                with self.assertRaises(ValueError): stage.verify(output, dict(config, commit='c'*40))
                with self.assertRaises(ValueError): stage.stage(source, pack, output, config)
                (pack / '600_899_OptionalINI.big').unlink()
                with self.assertRaises(ValueError): stage.stage(source, pack, root / 'incomplete', config)

    def test_pinned_profile_is_full_english(self):
        config = json.loads((ROOT / 'ios/community-patch/source.json').read_text())
        self.assertEqual(config['pack'], 'FullEnglish')
        self.assertRegex(config['commit'], r'^[0-9a-f]{40}$')
        self.assertRegex(config['builder_commit'], r'^[0-9a-f]{40}$')

    def test_mount_after_retail_and_exclude_recursive_scan(self):
        prefix = r'''
#include <string>
#include <vector>
#include <map>
#include <cassert>
#include <cstdio>
#include <stdexcept>
#define RTS_ZEROHOUR 1
#define TRUE true
#define FALSE false
#define DEBUG_ASSERTCRASH(c,m) ((void)0)
#define DEBUG_LOG(m) ((void)0)
using Bool=bool;
struct AsciiString{std::string value;AsciiString(const char*s=""):value(s){}
 const char*str()const{return value.c_str();}bool isNotEmpty()const{return !value.empty();}
 void concat(const char*s){value+=s;}bool operator<(const AsciiString&b)const{return value<b.value;}
 bool endsWithNoCase(const char*s)const{std::string suffix(s);return value.size()>=suffix.size() && value.compare(value.size()-suffix.size(),suffix.size(),suffix)==0;}};
using FilenameList=std::vector<AsciiString>;using FilenameListIter=FilenameList::iterator;
std::vector<std::string> calls;bool retail=true,exists=true;FilenameList inputs;
struct Local{void setAssetRootPath(const AsciiString&){calls.push_back("root");}
 bool doesFileExist(const char*){return exists;}
 void getFileListInDirectory(AsciiString,const char*,AsciiString,FilenameList&out,bool){out=inputs;}}local;
auto*TheLocalFileSystem=&local;
struct ArchiveFile{};
struct StdBIGFileSystem{
 std::map<AsciiString,ArchiveFile*>m_archiveFileMap;ArchiveFile archive;
 void init();bool loadBigFilesFromDirectory(AsciiString,AsciiString,bool=false);
 ArchiveFile*openArchiveFile(const char*path){calls.push_back(path);return &archive;}
 void loadIntoDirectoryTree(ArchiveFile*,bool overwrite){calls.push_back(overwrite?"overlay":"retail");}
};
bool loadPrimaryGameAssets(StdBIGFileSystem*,AsciiString*path){calls.push_back("primary");*path=AsciiString("Documents");return retail;}
void loadBaseGeneralsAssetsForZH(StdBIGFileSystem*,AsciiString){calls.push_back("base");}
bool getExecutableDirectory(AsciiString&path){path=AsciiString("/App");return true;}
'''
        body = function('void StdBIGFileSystem::init()') + function('Bool StdBIGFileSystem::loadBigFilesFromDirectory(')
        for enabled in [False, True]:
            run_cpp(('#define GENERALS_COMMUNITY_PATCH 1\n' if enabled else '') + prefix + body + r'''
int main(){StdBIGFileSystem fs;fs.init();
#ifdef GENERALS_COMMUNITY_PATCH
 assert(calls.back()=="overlay" && calls[2]=="base");
 assert(fs.m_archiveFileMap.size()==1);
 exists=false;bool failed=false;try{fs.init();}catch(const std::runtime_error&){failed=true;}assert(failed);
 exists=true;retail=false;failed=false;try{fs.init();}catch(const std::runtime_error&){failed=true;}assert(failed);retail=true;
 inputs={AsciiString("/App/CommunityPatch/CommunityPatch.big")};calls.clear();
 assert(!fs.loadBigFilesFromDirectory("/App","*.big") && calls.empty());
#endif
 inputs={AsciiString("/Documents/INIZH.big")};calls.clear();
 assert(fs.loadBigFilesFromDirectory("/Documents","*.big") && calls.size()==2 && calls[1]=="retail");
}
''')


if __name__ == '__main__':
    unittest.main()
