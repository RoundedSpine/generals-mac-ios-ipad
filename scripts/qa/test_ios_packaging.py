#!/usr/bin/env python3
"""Exercise iOS packaging control flow without Xcode; real Mach-O/device checks need macOS."""
# GeneralsX @build Codex 24/10/2026 Verify unsigned IPA contents and signing isolation.
import json
import hashlib
import importlib.util
import os
import plistlib
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
    (app / '_CodeSignature').mkdir(parents=True, exist_ok=True)
    (app / '_CodeSignature/CodeResources').write_text('signature')
    (app / 'embedded.mobileprovision').write_text('profile')
    (app / 'Info.plist').write_text('<plist/>')
    (app / 'GeneralsXZH').write_text('stub')
elif name == 'lipo':
    # -verify_arch consumes the following arguments as architecture names.
    # Apple lipo requires the input file before that variable-length list.
    if len(args) != 3 or not pathlib.Path(args[0]).is_file() or args[1:] != ['-verify_arch', 'arm64']:
        print('usage: lipo <input_file> -verify_arch <arch_type> ...', file=sys.stderr)
        sys.exit(1)
elif name == 'otool':
    if '-l' in args:
        print('cmd LC_BUILD_VERSION\nplatform ' + os.environ.get('IOS_PLATFORM', '2'))
        if os.environ.get('EXISTING_RPATH'):
            print('cmd LC_RPATH\npath @executable_path/Frameworks (offset 12)')
        sys.exit(0)
    print(args[-1] + ':')
    dep = '/usr/lib/libSystem.B.dylib'
    if pathlib.Path(args[-1]).name == 'GeneralsXZH':
        dep = os.environ.get('EXTRA_DEP', '/build/libSDL3.0.dylib')
    print('\t' + dep + ' (compatibility version 1.0.0, current version 1.0.0)')
elif name == 'file':
    print('Mach-O 64-bit arm64')
elif name == 'install_name_tool' and '-add_rpath' in args and os.environ.get('FAIL_RPATH'):
    sys.exit(19)
elif name == 'codesign':
    # Explicit model of command flow only; macOS CI verifies real Mach-O signatures.
    import plistlib
    state_file = pathlib.Path(os.environ['SIGNATURE_STATE'])
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    binary = str(pathlib.Path(args[-1]).resolve())
    if '--remove-signature' in args:
        state.pop(binary, None)
    elif '--sign' in args:
        if args[args.index('--sign') + 1] == '-' and os.environ.get('FAIL_ADHOC'):
            sys.exit(23)
        request = {}
        if '--entitlements' in args:
            with open(args[args.index('--entitlements') + 1], 'rb') as source:
                request = plistlib.load(source)
        state[binary] = request
    elif '--entitlements' in args:
        request = dict(state.get(binary, {}))
        if os.environ.get('DROP_MEMORY_REQUEST'):
            request.pop('com.apple.developer.kernel.increased-memory-limit', None)
        print(plistlib.dumps(request).decode())
    state_file.write_text(json.dumps(state))
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
        shutil.copy2(SCRIPT.parents[3] / 'ios/GeneralsXZH.entitlements', self.root / 'ios/GeneralsXZH.entitlements')
        config = self.root / 'ios/config'
        config.mkdir()
        (config / 'dxvk.conf').write_text('d3d9.forceSamplerTypeSpecConstants = False\n')
        (config / 'Options.ini').write_text('StaticGameLOD = High\n')
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
                        GX_MOLTENVK=str(framework), TOOL_LOG=str(self.root / 'tools.jsonl'),
                        SIGNATURE_STATE=str(self.root / 'signatures.json'))

    def run_package(self, *args):
        return subprocess.run(['bash', str(self.script), *args], env=self.env,
                              text=True, capture_output=True)

    # GeneralsX @test Codex 02/11/2026 Patch resources must match both the configured engine and staged source hash.
    def patch_resources(self, enabled=True):
        helper = SCRIPT.with_name('stage-community-patch.py')
        shutil.copy2(helper, self.script.with_name(helper.name))
        spec = importlib.util.spec_from_file_location('packaging_patch_stage', helper)
        stage = importlib.util.module_from_spec(spec); spec.loader.exec_module(stage)
        build = self.root / 'build/ios-vulkan'
        (build / 'CMakeCache.txt').write_text('GENERALS_COMMUNITY_PATCH:BOOL=' + ('ON' if enabled else 'OFF') + '\n')
        config = json.loads((SCRIPT.parents[3] / 'ios/community-patch/source.json').read_text())
        (build / 'community-patch-source.json').write_text(json.dumps(config))
        patch = self.root / 'patch'; patch.mkdir()
        payload = self.root / 'payload'; payload.write_bytes(b'compiled-data-fixture')
        entries = [('data/ini/gamedata.ini', payload, 0, payload.stat().st_size),
                   ('data/english/generals.csf', payload, 0, payload.stat().st_size)]
        stage.write_big(entries, patch / 'CommunityPatch.big')
        (patch / 'manifest.json').write_text(json.dumps(dict(config, entries=len(entries),
            archive_sha256=hashlib.sha256((patch / 'CommunityPatch.big').read_bytes()).hexdigest())))
        (patch / 'Notices').mkdir()
        for name in ['Notices/LICENSE.txt', 'TERMS.txt', 'UPSTREAM-README.md']:
            (patch / name).write_text('fixture notice')
        self.env['GX_COMMUNITY_PATCH_DIR'] = str(patch)
        return patch

    def test_patch_resources_are_bundled_with_existing_memory_requests(self):
        patch = self.patch_resources()
        result = self.run_package('--dev', '--unsigned')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        ipa = self.root / 'build/ios-package/GeneralsXZH-unsigned.ipa'
        with zipfile.ZipFile(ipa) as archive:
            bundled = archive.read('Payload/GeneralsXZH.app/CommunityPatch/CommunityPatch.big')
            self.assertEqual((patch / 'CommunityPatch.big').read_bytes(), bundled)
            self.assertIn('Payload/GeneralsXZH.app/CommunityPatch/Notices/LICENSE.txt', archive.namelist())
        carried = ipa.parent / 'GeneralsXZH-embedded-entitlements.plist'
        with carried.open('rb') as source:
            self.assertEqual(plistlib.load(source), {
                'com.apple.developer.kernel.increased-memory-limit': True,
                'com.apple.developer.kernel.extended-virtual-addressing': True,
            })

    def test_patch_enabled_engine_requires_resources(self):
        self.patch_resources()
        del self.env['GX_COMMUNITY_PATCH_DIR']
        result = self.run_package('--dev', '--unsigned')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('requires GX_COMMUNITY_PATCH_DIR', result.stderr)

    def test_patch_payload_cannot_be_bundled_into_vanilla_engine(self):
        self.patch_resources(enabled=False)
        result = self.run_package('--dev', '--unsigned')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('require a GENERALS_COMMUNITY_PATCH=ON engine', result.stderr)

    def test_corrupted_or_mismatched_patch_stops_packaging(self):
        patch = self.patch_resources()
        with (patch / 'CommunityPatch.big').open('ab') as file:
            file.write(b'corrupt')
        result = self.run_package('--dev', '--unsigned')
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.root / 'build/ios-package/GeneralsXZH-unsigned.ipa').exists())

    def test_patch_profile_matches_configured_engine_not_changed_source(self):
        patch = self.patch_resources()
        manifest = json.loads((patch / 'manifest.json').read_text()); manifest['commit'] = 'f' * 40
        (patch / 'manifest.json').write_text(json.dumps(manifest))
        result = self.run_package('--dev', '--unsigned')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('manifest does not match', result.stderr)

    def test_unsigned_archive_carries_requests_without_profiles_or_retail_data(self):
        result = self.run_package('--dev', '--unsigned')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        ipa = self.root / 'build/ios-package/GeneralsXZH-unsigned.ipa'
        with (ipa.parent / 'GeneralsXZH.entitlements').open('rb') as file:
            entitlements = plistlib.load(file)
        self.assertEqual(entitlements, {
            'com.apple.developer.kernel.increased-memory-limit': True,
            'com.apple.developer.kernel.extended-virtual-addressing': True,
        })
        with (ipa.parent / 'GeneralsXZH-embedded-entitlements.plist').open('rb') as file:
            self.assertEqual(plistlib.load(file), entitlements)
        with zipfile.ZipFile(ipa) as archive:
            names = archive.namelist()
            base = 'Payload/GeneralsXZH.app/'
            self.assertEqual(archive.read(base + 'GeneralsXZH'), b'engine fixture')
            self.assertIn(base + 'Frameworks/MoltenVK.framework/MoltenVK', names)
            self.assertIn(base + 'Frameworks/libopenal.1.dylib', names)
            self.assertIn(b'forceSamplerTypeSpecConstants = False', archive.read(base + 'dxvk.conf'))
            self.assertIn(base + 'DefaultOptions.ini', names)
            self.assertFalse(any('_CodeSignature' in n or 'mobileprovision' in n or 'GameData/' in n for n in names))
        calls = [json.loads(line) for line in (self.root / 'tools.jsonl').read_text().splitlines()]
        xcode = next(call for call in calls if call[0] == 'xcodebuild')
        self.assertIn('CODE_SIGNING_ALLOWED=NO', xcode)
        self.assertNotIn('-allowProvisioningUpdates', xcode)
        signing = [call for call in calls if call[0] == 'codesign' and '--sign' in call]
        self.assertEqual(len(signing), 1)
        self.assertEqual(signing[0][signing[0].index('--sign') + 1], '-')
        self.assertEqual(Path(signing[0][-1]), ipa.parent / 'GeneralsXZH.app/GeneralsXZH')
        self.assertEqual(Path(signing[0][signing[0].index('--entitlements') + 1]), ipa.parent / 'GeneralsXZH.entitlements')
        removals = [i for i, call in enumerate(calls) if '--remove-signature' in call]
        self.assertLess(max(removals), calls.index(signing[0]))
        self.assertTrue(any('--remove-signature' in call for call in calls))
        self.assertTrue(any('@rpath/libSDL3.0.dylib' in call for call in calls))

    def test_missing_embedded_memory_request_stops_packaging(self):
        self.env['DROP_MEMORY_REQUEST'] = '1'
        result = self.run_package('--dev', '--unsigned')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('did not retain the requested iOS entitlements', result.stderr)
        self.assertFalse((self.root / 'build/ios-package/GeneralsXZH-unsigned.ipa').exists())

    def test_failed_adhoc_signature_stops_packaging(self):
        self.env['FAIL_ADHOC'] = '1'
        result = self.run_package('--dev', '--unsigned')
        self.assertEqual(result.returncode, 23)
        self.assertFalse((self.root / 'build/ios-package/GeneralsXZH-unsigned.ipa').exists())

    def test_architecture_check_rejects_filename_after_architecture_list(self):
        binary = self.root / 'build/ios-vulkan/GeneralsMD/GeneralsXZH.app/GeneralsXZH'
        result = subprocess.run(['lipo', '-verify_arch', 'arm64', str(binary)],
                                env=self.env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('usage: lipo', result.stderr)

    def test_arm64_host_or_simulator_library_is_rejected(self):
        for platform in ('1', '7', 'MACOS', 'IOSSIMULATOR'):
            self.env['IOS_PLATFORM'] = platform
            result = self.run_package('--dev', '--unsigned')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('expected iOS device platform', result.stderr)

    def test_real_rpath_failure_stops_packaging(self):
        self.env['FAIL_RPATH'] = '1'
        result = self.run_package('--dev', '--unsigned')
        self.assertEqual(result.returncode, 19)

    def test_existing_framework_rpath_is_not_added_again(self):
        self.env['FAIL_RPATH'] = '1'
        self.env['EXISTING_RPATH'] = '1'
        result = self.run_package('--dev', '--unsigned')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
