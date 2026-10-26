#!/usr/bin/env python3
"""Merge the upstream compiled pack into one deterministic iOS BIG overlay.

Usage: stage-community-patch.py --source CHECKOUT --pack-dir BUILT_PACK --output DIRECTORY
Build the pack with its pinned Windows Mod Builder first. Never package raw PSD/STR/BLEND sources.
"""
# GeneralsX @build Codex 26/10/2026 Preserve upstream archive priority and notices without retail installations.
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def normalized(name):
    name = name.replace('\\', '/')
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ':' in name or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError(f'Unsafe archive path: {name!r}')
    name.encode('ascii')
    if len(name) >= 240:
        raise ValueError(f'Archive path exceeds engine buffer: {name}')
    return name.lower()


def read_big(path):
    total = path.stat().st_size
    with path.open('rb') as file:
        header = file.read(16)
        if len(header) != 16 or header[:4] != b'BIGF':
            raise ValueError(f'Not a compiled BIGF archive: {path}')
        declared, = struct.unpack('<I', header[4:8])
        count, end = struct.unpack('>II', header[8:])
        if declared != total or not 16 <= end <= total or count > (end - 16) // 10:
            raise ValueError(f'Invalid BIG header: {path}')
        result, seen = [], set()
        for _ in range(count):
            entry = file.read(8)
            if len(entry) != 8:
                raise ValueError('Truncated BIG entry')
            offset, size = struct.unpack('>II', entry)
            name = bytearray()
            while file.tell() < end:
                byte = file.read(1)
                if byte == b'\0':
                    break
                name.extend(byte)
            else:
                raise ValueError('Unterminated BIG name')
            key = normalized(name.decode('ascii'))
            if offset < end or offset + size > total or file.tell() > end:
                raise ValueError(f'Out-of-bounds BIG entry: {key}')
            if key in seen:
                raise ValueError(f'Duplicate path inside BIG: {key}')
            seen.add(key)
            result.append((key, path, offset, size))
        return result


def write_big(entries, output):
    entries = sorted(entries, key=lambda e: e[0])
    index_size = 16 + sum(8 + len(name.encode('ascii')) + 1 for name, *_ in entries)
    total = index_size + sum(size for _, _, _, size in entries)
    if total >= 2**31:
        raise ValueError('Overlay exceeds engine signed 32-bit file size')
    with output.open('wb') as file:
        file.write(b'BIGF' + struct.pack('<I', total) + struct.pack('>II', len(entries), index_size))
        offset = index_size
        for name, _, _, size in entries:
            file.write(struct.pack('>II', offset, size) + name.replace('/', '\\').encode('ascii') + b'\0')
            offset += size
        for _, source, offset, size in entries:
            with source.open('rb') as data:
                data.seek(offset)
                remaining = size
                while remaining:
                    block = data.read(min(remaining, 1024 * 1024))
                    if not block:
                        raise ValueError(f'Truncated source: {source}')
                    file.write(block)
                    remaining -= len(block)


def expected_archives(source, config):
    project = source / 'Patch104pZH'
    files = json.loads((project / 'ModJsonFiles.json').read_text())['build']['files']
    items, packs = {}, {}
    prefix = suffix = ''
    for name in files:
        bundles = json.loads((project / name).read_text()).get('bundles', {})
        prefix = bundles.get('itemsPrefix', prefix)
        suffix = bundles.get('itemsSuffix', suffix)
        for item in bundles.get('items', []):
            items[item['name']] = (item, prefix, suffix)
        for pack in bundles.get('packs', []):
            packs[pack['name']] = pack
    result = []
    for name in packs[config['pack']]['itemNames']:
        item, prefix, suffix = items[name]
        if item.get('big', False):
            result.append((item.get('namePrefix') or prefix) + name + (item.get('nameSuffix') or suffix) + '.big' + item.get('bigSuffix', ''))
    return sorted(result, key=str.lower)


def stage(source, pack_dir, output, config):
    def revision(*args):
        return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()
    if revision('rev-parse', 'HEAD') != config['commit']:
        raise ValueError('Patch checkout does not match the pinned commit')
    builder = revision('rev-parse', 'HEAD:Tools/GeneralsModBuilder')
    if builder != config['builder_commit']:
        raise ValueError('Unexpected upstream Mod Builder pin')
    if output.exists():
        raise ValueError('Refusing to overwrite an existing staged patch')
    archives = sorted(pack_dir.glob('*.big'), key=lambda p: p.name.lower())
    if not archives:
        raise ValueError('No compiled BIG archives in the selected pack')
    expected = expected_archives(source, config)
    if [p.name.lower() for p in archives] != [name.lower() for name in expected]:
        raise ValueError(f'Compiled pack archives do not match {config["pack"]}: expected {expected}')
    selected = {}
    # Installed loose data has priority over all archives. Only runtime assets enter the overlay.
    for path in sorted(pack_dir.rglob('*')):
        relative = path.relative_to(pack_dir).as_posix()
        if path.is_symlink():
            raise ValueError(f'Symlink in built pack: {relative}')
        if path.is_file() and relative.split('/')[0].lower() in ('data', 'art', 'maps', 'window'):
            if path.suffix.lower() in ('.ani', '.ini', '.csf', '.dds', '.tga', '.w3d', '.wav', '.mp3', '.wnd', '.map', '.str', '.scb', '.pso', '.vso'):
                selected.setdefault(normalized(relative), (normalized(relative), path, 0, path.stat().st_size))
    # Original loader uses the first archive in filename order. Optional 600_899 precedes Core 600_900.
    for archive in archives:
        for entry in read_big(archive):
            selected.setdefault(entry[0], entry)
    if 'data/ini/gamedata.ini' not in selected:
        raise ValueError('Patch has no compiled GameData.ini')
    output.mkdir(parents=True)
    archive = output / 'CommunityPatch.big'
    write_big(selected.values(), archive)
    notices = output / 'Notices'
    for path in sorted(source.rglob('LICENSE.txt')):
        if '.git' in path.parts or 'Tools' in path.relative_to(source).parts:
            continue
        dest = notices / path.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    shutil.copy2(source / 'TERMS.txt', output / 'TERMS.txt')
    shutil.copy2(source / 'README.md', output / 'UPSTREAM-README.md')
    digest = hashlib.sha256()
    with archive.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    manifest = dict(config, entries=len(selected), archive_sha256=digest.hexdigest(),
                    archives=[p.name for p in archives])
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f"Staged {config['pack']}: {len(selected)} entries, {archive.stat().st_size} bytes")


def verify(directory, config):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if any(manifest.get(key) != value for key, value in config.items()):
        raise ValueError('Staged patch manifest does not match the pinned source/profile')
    archive = directory / 'CommunityPatch.big'
    digest = hashlib.sha256()
    with archive.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != manifest['archive_sha256'] or len(read_big(archive)) != manifest['entries']:
        raise ValueError('Staged patch archive verification failed')
    for name in ['Notices/LICENSE.txt', 'TERMS.txt', 'UPSTREAM-README.md']:
        if not (directory / name).is_file():
            raise ValueError(f'Missing patch notice: {name}')
    print(f"Verified {config['pack']} at {config['commit']}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--pack-dir', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    config = json.loads((ROOT / 'ios/community-patch/source.json').read_text())
    if args.verify:
        verify(args.verify.resolve(), config)
    elif args.source and args.pack_dir and args.output:
        stage(args.source.resolve(), args.pack_dir.resolve(), args.output.resolve(), config)
    else:
        parser.error('provide --verify DIRECTORY or --source, --pack-dir and --output')
