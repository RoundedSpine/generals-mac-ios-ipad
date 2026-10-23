#!/usr/bin/env python3
"""Exercise iOS packaging control flow without Xcode; real Mach-O/device checks need macOS."""
# GeneralsX @build Codex 24/10/2026 Verify unsigned IPA contents and signing isolation.
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / 'build/ios/package-ios-zh.sh'
MOCK = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, zipfile
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['TOOL_LOG'], 'a') as log:
    log.write(json.dumps([name, *args]) + '\n')
if name == 'xcodebuild':
    if os.environ.get('FAIL_XCODE'):
        sys.exit(17)
    root = pathlib.Path(args[args.index('-derivedDataPath') + 1])
    app = root / 'Build/Products/Release-iphoneos/GeneralsXZH.app'
    (app / '_CodeSignature').mkdir(parents=True)
    (app / '_CodeSignature/CodeResources').write_text('signature')
    (app / 'embedded.mobileprovision').write_text('profile')
    (app / 'Info.plist').write_text('<plist/>')
    (app / 'GeneralsXZH').write_text('stub')
elif name == 'otool':
    print(args[-1] + ':')
    dep = '/usr/lib/libSystem.B.dylib'
    if pathlib.Path(args[-1]).name == 'GeneralsXZH':
        dep = os.environ.get('EXTRA_DEP', '/build/libSDL3.0.dylib')
    print('\t' + dep + ' (compatibility version 1.0.0, current version 1.0.0)')
elif name == 'file':
    print('Mach-O 64-bit arm64')
elif name == 'codesign' and '--entitlements' in args:
    print('<plist><dict/></plist>')
elif name == 'ditto':
    source, destination = pathlib.Path(args[-2]), pathlib.Path(args[-1])
    with zipfile.ZipFile(destination, 'w') as archive:
        for path in source.rglob('*'):
            if path.is_file():
                archive.write(path, str(path))
'''


class PackagingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        script = self.root / 'scripts/build/ios/package-ios-zh.sh'
        script.parent.mkdir(parents=True)
        shutil.copy2(SCRIPT, script)
        self.script = script
        (self.root / 'ios').mkdir()
        build = self.root / 'build/ios-vulkan'
        for relative in (
            'GeneralsMD/GeneralsXZH.app/GeneralsXZH',
            '_deps/dxvk-build-macos/src/d3d8/libdxvk_d3d8.0.dylib',
            '_deps/dxvk-build-macos/src/d3d9/libdxvk_d3d9.0.dylib',
            '_deps/sdl3-build/libSDL3.0.dylib',
            '_deps/sdl3_image-build/libSDL3_image.0.dylib',
            '_deps/openal_soft-build/libopenal.1.24.2.dylib',
        ):
            target = build / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('engine fixture')
        framework = self.root / 'MoltenVK.framework'
        framework.mkdir()
        (framework / 'MoltenVK').write_text('framework fixture')
        tools = self.root / 'tools'
        tools.mkdir()
        for tool in ('xcodegen', 'xcodebuild', 'lipo', 'otool', 'install_name_tool', 'file', 'codesign', 'ditto'):
            path = tools / tool
            path.write_text(MOCK)
            path.chmod(0o755)
        self.env = dict(os.environ, PATH=f'{tools}:{os.environ["PATH"]}',
                        GX_MOLTENVK=str(framework), TOOL_LOG=str(self.root / 'tools.jsonl'))

    def run_package(self, *args):
        return subprocess.run(['bash', str(self.script), *args], env=self.env,
                              text=True, capture_output=True)

    def test_unsigned_archive_has_payload_and_no_signatures_or_retail_data(self):
        result = self.run_package('--dev', '--unsigned')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        ipa = self.root / 'build/ios-package/GeneralsXZH-unsigned.ipa'
        with zipfile.ZipFile(ipa) as archive:
            names = archive.namelist()
            base = 'Payload/GeneralsXZH.app/'
            self.assertEqual(archive.read(base + 'GeneralsXZH'), b'engine fixture')
            self.assertIn(base + 'Frameworks/MoltenVK.framework/MoltenVK', names)
            self.assertIn(base + 'Frameworks/libopenal.1.dylib', names)
            self.assertFalse(any('_CodeSignature' in n or 'mobileprovision' in n or 'GameData/' in n for n in names))
        calls = [json.loads(line) for line in (self.root / 'tools.jsonl').read_text().splitlines()]
        xcode = next(call for call in calls if call[0] == 'xcodebuild')
        self.assertIn('CODE_SIGNING_ALLOWED=NO', xcode)
        self.assertNotIn('-allowProvisioningUpdates', xcode)
        self.assertFalse(any('--sign' in call for call in calls))
        self.assertTrue(any('--remove-signature' in call for call in calls))
        self.assertTrue(any('@rpath/libSDL3.0.dylib' in call for call in calls))

    def test_unsigned_install_is_rejected(self):
        result = self.run_package('--unsigned', '--install')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cannot be combined', result.stderr)

    def test_missing_runtime_library_fails(self):
        (self.root / 'build/ios-vulkan/_deps/sdl3-build/libSDL3.0.dylib').unlink()
        result = self.run_package('--dev', '--unsigned')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('required dylib not built', result.stdout)

    def test_unbundled_host_dependency_fails(self):
        self.env['EXTRA_DEP'] = '/opt/homebrew/lib/libhost.dylib'
        result = self.run_package('--dev', '--unsigned')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unbundled dependency', result.stderr)

    def test_xcode_failure_propagates(self):
        self.env['FAIL_XCODE'] = '1'
        self.assertNotEqual(self.run_package('--dev', '--unsigned').returncode, 0)

    def test_default_mode_still_signs_an_app(self):
        result = self.run_package('--dev')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / 'build/ios-package/GeneralsXZH.app').is_dir())
        calls = [json.loads(line) for line in (self.root / 'tools.jsonl').read_text().splitlines()]
        self.assertTrue(any('--sign' in call for call in calls))
        self.assertTrue(any('-allowProvisioningUpdates' in call for call in calls))


if __name__ == '__main__':
    unittest.main()
