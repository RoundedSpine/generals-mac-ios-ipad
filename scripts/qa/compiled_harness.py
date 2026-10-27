"""Compile isolated production-code regression harnesses."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / 'Core/Libraries/Source/WWVegas/WWLib'


def run_cpp(source, extra_flags=()):
    with tempfile.TemporaryDirectory() as temporary:
        code = Path(temporary) / 'test.cpp'
        binary = Path(temporary) / 'test'
        code.write_text(source)
        result = subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-pthread',
                                 '-D_UNIX', *extra_flags, '-I', str(LIB), str(code), '-o', str(binary)], text=True, capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        return subprocess.run([str(binary)], text=True, capture_output=True, check=True, timeout=10)

