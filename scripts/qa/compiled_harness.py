"""Compile isolated production-code regression harnesses."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / 'Core/Libraries/Source/WWVegas/WWLib'


# GeneralsX @build Codex 27/10/2026 Keep the default deadlock guard while allowing bounded larger sanitizer workloads.
def run_cpp(source, extra_flags=(), timeout=10):
    with tempfile.TemporaryDirectory() as temporary:
        code = Path(temporary) / 'test.cpp'
        binary = Path(temporary) / 'test'
        code.write_text(source)
        result = subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-pthread',
                                 '-D_UNIX', *extra_flags, '-I', str(LIB), str(code), '-o', str(binary)], text=True, capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        return subprocess.run([str(binary)], text=True, capture_output=True, check=True, timeout=timeout)

