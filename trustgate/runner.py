"""Run one independent manifest shard on a PBS compute node."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[1]))
from release_integrity import recorded_digest
import asyncio
import contextlib
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import socket
import sys
import time
from pathlib import Path
from .planning import ROOT, read_plan
from .budget import Budget, BudgetExceeded

def dump(path, data):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str)+'\n')
    temporary.replace(path)

def require_compute():
    if not os.environ.get('PBS_JOBID') or platform.python_version() != '3.10.20':
        raise RuntimeError('Run through PBS with the dsa4213 environment (Python 3.10.20).')

def get_key():
    value = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not value:
        path = Path(os.environ.get('TRUSTGATE_KEY_FILE', ROOT/'.secrets/openrouter_group9.key'))
        if path.stat().st_mode & 0o077:
            raise RuntimeError('Credential file must be readable only by its owner (chmod 600).')
        value = path.read_text().strip()
    if not value:
        raise RuntimeError('Missing Group 9 API credential.')
    return value

async def run_shard(plan_path, shard_index, run_id, output_root=None, detector_dir=None):
    require_compute()
    plan = read_plan(plan_path)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', run_id):
        raise ValueError('run-id must be a short filename-safe identifier.')
    if not 0 <= shard_index < plan['workers']:
        raise ValueError('Shard index outside the plan.')
    shard = plan['shards'][shard_index]
    os.umask(0o077)
    os.environ['PYTHONHASHSEED'] = '0'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    # Python's own hash seed must be set before process startup, not merely here.
    if sys.flags.hash_randomization:
        raise RuntimeError('Start Python with PYTHONHASHSEED=0 for deterministic native state ordering.')
    key = get_key()
    cfg = dict(plan['config'])
    cfg['max_total_cost_usd'] = shard['budget_usd']
    detector_path = Path(detector_dir or os.environ.get('TRUSTGATE_DETECTOR_DIR', ROOT/'models/prompt_injection_detector'))
    needs_detector = any(c['condition'] not in ('none', 'delimiters', 'no_metadata') for c in shard['cases'])
    if needs_detector and not (detector_path/'model.safetensors').exists():
        raise RuntimeError('Pinned detector is missing; run experiments/mvp/prepare_detector.py once first.')
    if plan.get('profile') in ('formal_v1','formal_development_v1'):
        from .formal_manifest import verify_runtime
        verify_runtime(plan,detector_path)
    folder = Path(output_root or ROOT/'runs/studies')/run_id/('shard-%02d' % shard_index)
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.mkdir()  # Deliberately fail if rerun: never overwrite or double-spend silently.
    dump(folder/'plan.json', plan)
    dump(folder/'config.json', cfg)
    sources = {str(p.relative_to(ROOT)):recorded_digest(hashlib.sha256(p.read_bytes()).hexdigest())
               for base in ('trustgate','experiments/mvp') for p in (ROOT/base).glob('*.py')}
    dump(folder/'manifest.json', dict(plan_sha256=plan['plan_sha256'], shard_index=shard_index,
         run_id=run_id, host=socket.gethostname(), pbs_job_id=os.environ['PBS_JOBID'],
         python=platform.python_version(), source_sha256=sources,
         packages={p:importlib.metadata.version(p) for p in ('agentdojo','mcp','transformers','torch')},
         classifier_revision=(ROOT/'models/detector_revision.txt').read_text().strip()))
    sys.path.insert(0, str(ROOT/'experiments/mvp'))
    from run_matrix_v2 import Experiment, Detector
    from agentdojo.task_suite.load_suites import get_suite
    if plan.get('profile') in ('formal_v1','formal_development_v1'):
        from .formal_engine import FormalExperiment
        Experiment = FormalExperiment
    ledger = Budget(shard['budget_usd'], cfg.get('per_request_reservation_usd', 0.05))

    class BudgetedExperiment(Experiment):
        def completion(self, messages, tools, trial_folder, step):
            ledger.reserve()
            dump(folder/'budget.json', ledger.snapshot())
            try:
                answer, record = super().completion(messages, tools, trial_folder, step)
                ledger.reconcile(record['usage']['cost'])
                return answer, record
            except Exception:
                if ledger.pending:
                    ledger.unknown()
                raise
            finally:
                dump(folder/'budget.json', ledger.snapshot())

    started = time.monotonic()
    experiment = None
    fatal = None
    try:
        suite = get_suite(cfg['benchmark'], cfg['suite'])
        detector = Detector(detector_path, cfg['classifier_threshold']) if needs_detector else None
        experiment = BudgetedExperiment(cfg, folder, suite, detector, key)
        async with contextlib.AsyncExitStack() as stack:
            await experiment.start(stack)
            for index, case in enumerate(shard['cases'], 1):
                row = await experiment.run_case(case, index)
                if row['error'] and row['error']['type'] in ('HTTPError','URLError','TimeoutError','BudgetExceeded'):
                    fatal = row['error']
                    break
    except Exception as exc:
        fatal = dict(type=type(exc).__name__, message=str(exc).replace(key, '[REDACTED]'))
    finally:
        rows = experiment.rows if experiment else []
        dump(folder/'worker_summary.json', dict(plan_sha256=plan['plan_sha256'], shard_index=shard_index,
             planned=len(shard['cases']), recorded=len(rows), complete=len(rows)==len(shard['cases']) and fatal is None,
             wall_seconds=time.monotonic()-started, fatal_error=fatal, budget=ledger.snapshot()))
    if fatal:
        raise RuntimeError('Worker stopped; inspect its private worker_summary.json before retrying.')
    return str(folder)
