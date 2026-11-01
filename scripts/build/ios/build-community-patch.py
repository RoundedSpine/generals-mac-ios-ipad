#!/usr/bin/env python3
"""Run the pinned Windows Mod Builder API without PC installation or Python path literals."""
# GeneralsX @bugfix Codex 27/10/2026 Scope build metadata to the chosen pack and pass Blender paths as data.
import argparse
import json
import os
from pathlib import Path
import subprocess
import traceback

ROOT = Path(__file__).resolve().parents[3]
ADDON_ENV = 'GX_COMMUNITY_PATCH_ADDON_ZIP'


def prepare_tools(source):
    directory = source / 'Patch104pZH/Scripts/Windows'
    config = json.loads((directory / 'WindowsTools.json').read_text())
    adapted = 0
    for tool in config['tools']['list']:
        if tool['name'] != 'blender':
            continue
        for file in tool['files']:
            for instruction in file.get('callList', []):
                if '--python-expr' in instruction.get('callArgs', {}):
                    # A Windows path such as D:\a must never appear inside a Python string literal.
                    instruction['callArgs'] = {
                        '--background': '',
                        '--python-exit-code': '1',
                        '--python-expr': "import bpy, os; bpy.ops.preferences.addon_install(overwrite=True, filepath=os.environ['" + ADDON_ENV + "'])",
                    }
                    adapted += 1
    if adapted != 1:
        raise ValueError(f'Expected one pinned Blender add-on installer, got {adapted}')
    # Keep this beside the original so {THIS_DIR} and relative tool paths retain their meaning.
    output = directory / 'WindowsTools.ios-ci.json'
    output.write_text(json.dumps(config, indent=2) + '\n')
    os.environ[ADDON_ENV] = str(directory / '.tools/io_mesh_w3d.zip')
    return output


def build(source, config, run_builder=None):
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    builder = subprocess.check_output(['git', '-C', str(source / 'Tools/GeneralsModBuilder'), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != config['commit'] or builder != config['builder_commit']:
        raise ValueError('Patch or Mod Builder checkout differs from the pinned source')
    tools = prepare_tools(source)
    if run_builder is None:
        from generalsmodbuilder.buildfunctions import RunWithConfig
        run_builder = RunWithConfig
    # Upstream otherwise marks ALL packs installable, including packs not in buildList,
    # and its pre-build structure then asserts because those packs have no build output.
    # Selecting install metadata is separate from enabling an installation operation.
    run_builder(configPaths=[str(source / 'Patch104pZH/ModJsonFiles.json'), str(tools)],
                buildList=[config['pack']], installList=[config['pack']],
                build=True, release=True, install=False, uninstall=False, run=False,
                verboseLogging=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args.source.resolve(), json.loads((ROOT / 'ios/community-patch/source.json').read_text()))
    except Exception:
        # Publish the specific failure in public Actions annotations as well as the full job log.
        detail = traceback.format_exc()[-6000:].replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::error title=Community Patch build::' + detail, flush=True)
        raise
