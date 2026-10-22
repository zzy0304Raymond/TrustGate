"""Auditable Linux/WSL launch support; the frozen experiment sources stay intact."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[3]))
from release_integrity import recorded_digest
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from trustgate.planning import read_plan


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return recorded_digest(h.hexdigest())


def adapter_hashes():
    return {p.relative_to(ROOT).as_posix(): sha(p)
            for p in sorted(Path(__file__).parent.glob('*.py'))}


def source_check(plan):
    # Compare exact bytes, never silently normalize a modified source file.
    actual = {p.relative_to(ROOT).as_posix(): sha(p)
              for base in ('trustgate', 'experiments/mvp')
              for p in (ROOT / base).glob('*.py')}
    if actual != plan['source_sha256']:
        raise RuntimeError('Frozen sources differ. Use an unchanged Linux checkout with LF line endings.')
    return actual


def require_local():
    if platform.system() != 'Linux' or platform.python_version() != '3.10.20':
        raise RuntimeError('Local adapter requires Linux/WSL and Python 3.10.20.')
    if os.environ.get('PBS_JOBID'):
        raise RuntimeError('Inside PBS use the original python -m trustgate entry point.')
    if os.environ.get('PYTHONHASHSEED') != '0' or sys.flags.hash_randomization:
        raise RuntimeError('Start Python with PYTHONHASHSEED=0.')
    for name in ('TOKENIZERS_PARALLELISM', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        expected = 'false' if name == 'TOKENIZERS_PARALLELISM' else '2'
        if os.environ.get(name) != expected:
            raise RuntimeError('Set %s=%s before Python starts.' % (name, expected))


def verify(plan_path, detector_dir):
    require_local()
    plan = read_plan(plan_path)
    if plan['profile'] != 'formal_v1':
        raise ValueError('This adapter only executes the published formal manifest.')
    source_check(plan)
    from trustgate.formal_manifest import verify_runtime
    verify_runtime(plan, detector_dir)
    return plan


def environment():
    from trustgate.formal_manifest import PACKAGES
    hardware = dict(logical_cpus=os.cpu_count())
    for path, prefix, key in (('/proc/cpuinfo', 'model name', 'cpu_model'),
                              ('/proc/meminfo', 'MemTotal', 'memory_total')):
        if Path(path).exists():
            hardware[key] = next((line.split(':', 1)[1].strip()
                for line in Path(path).read_text().splitlines() if line.startswith(prefix)), 'unknown')
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    return dict(execution_backend='local-linux-v1', system=platform.system(),
                release=platform.release(), python=platform.python_version(),
                git_commit=commit, hardware=hardware,
                thread_environment={name: os.environ.get(name) for name in
                    ('PYTHONHASHSEED', 'TOKENIZERS_PARALLELISM', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')},
                pbs_job_id=None, adapter_sha256=adapter_hashes(),
                packages={p: importlib.metadata.version(p) for p in PACKAGES},
                acceptance='Requires team review of adapter and real environment; not Vanda validation.')


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    temporary.replace(path)
