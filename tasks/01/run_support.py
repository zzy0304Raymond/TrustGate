"""Person-01 provenance and passive cost monitoring; never sends model requests."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[2]))
from release_integrity import recorded_digest
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from trustgate.formal_manifest import verify_runtime
from trustgate.planning import read_plan
from trustgate.runner import require_compute


def read_json(path):
    return json.loads(path.read_text())


def environment(stage):
    require_compute()
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    detector = Path(os.environ['TRUSTGATE_DETECTOR_DIR'])
    verify_runtime(plan, detector)
    key_path = Path(os.environ['TRUSTGATE_KEY_FILE'])
    if not key_path.is_file() or key_path.stat().st_mode & 0o077:
        raise RuntimeError('Missing credential file or unsafe credential permissions.')
    shard = plan['shards'][0]
    assert len(shard['cases']) == 336 and shard['person'] == 1
    assert shard['budget_usd'] == 2.0
    assert {c['task'] for c in shard['cases']} == {
        'user_task_0', 'user_task_12', 'user_task_17', 'user_task_31'}
    cpu_model = next((line.split(':', 1)[1].strip()
                      for line in Path('/proc/cpuinfo').read_text().splitlines()
                      if line.startswith('model name')), 'unknown')
    prep = Path(os.environ['TRUSTGATE_PREP_DIR'])
    run_dir = ROOT / 'runs/studies' / os.environ['TRUSTGATE_RUN_ID'] / 'shard-00'
    info = {
        'stage': stage,
        'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'cluster': 'Vanda', 'host': socket.gethostname(),
        'pbs_job_id': os.environ['PBS_JOBID'],
        'platform': platform.platform(), 'os_release': Path('/etc/os-release').read_text(),
        'cpu_model': cpu_model, 'requested_cpus': 2, 'requested_memory_gb': 8,
        'requested_gpus': 0, 'detector_device': 'cpu',
        'python': platform.python_version(), 'python_executable': sys.executable,
        'git_commit_at_launch': os.environ['TRUSTGATE_RUN_COMMIT'],
        'plan_sha256': plan['plan_sha256'], 'source_sha256': plan['source_sha256'],
        'packages': {name: importlib.metadata.version(name) for name in plan['packages']},
        'run_id': os.environ['TRUSTGATE_RUN_ID'], 'shard_index': 0,
        'startup_environment': {name: os.environ.get(name) for name in (
            'PYTHONHASHSEED', 'TOKENIZERS_PARALLELISM', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
            'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE')},
        'launcher_sha256': recorded_digest(hashlib.sha256((ROOT / 'tasks/01/run_person01.pbs').read_bytes()).hexdigest()),
        'support_sha256': recorded_digest(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        'frozen_runtime_verified': True, 'credential_owner_only': True,
    }
    if stage == 'completed':
        worker = read_json(run_dir / 'worker_summary.json')
        receipt = read_json(ROOT / 'experiments/deliveries/person-01/receipt.json')
        assert worker['complete'] and worker['fatal_error'] is None
        assert worker['recorded'] == receipt['recorded'] == 336
        info['worker_summary'] = worker
    (prep / f'environment_{stage}.json').write_text(json.dumps(info, indent=2) + '\n')
    print('ENVIRONMENT_CHECK=' + json.dumps({
        k: info[k] for k in ('stage', 'host', 'pbs_job_id', 'python', 'plan_sha256', 'frozen_runtime_verified')
    }), flush=True)
    if stage == 'before':
        return
    delivery = ROOT / 'experiments/deliveries/person-01'
    delivery.mkdir(parents=True, exist_ok=True)
    package_lines = '\n'.join(f'- `{name}=={version}`' for name, version in info['packages'].items())
    completion = ('336/336, `complete=true`, `fatal_error=null`.'
                  if stage == 'completed' else 'Offline check passed; formal execution and export not yet completed.')
    cost = (f"\n- Actual reported API cost: ${worker['budget']['reported_cost_usd']:.8f}.\n"
            if stage == 'completed' else '')
    text = f'''# person-01 runtime environment

- Platform: Vanda; scheduler: PBS; job `{info['pbs_job_id']}`; node `{info['host']}`.
- Operating system:`{info['platform']}`.
- CPU: {cpu_model}; Requested 2 CPU, 8 GB memory, 6 hours. Queue can adjust actual memory usage, as recorded by PBS.
- GPU: not requested, not used; detector runs on CPU.
- Conda: `dsa4213`; Python `{info['python']}`; using existing frozen environment, no dependencies installed or upgraded.
- Git base commit at startup:`{info['git_commit_at_launch']}`; branch `experiment-1`. Personal added startup and logging scripts not yet committed at startup; their SHA-256 stored separately in private environment record; frozen execution code and list are consistent.
- Final list SHA:`{info['plan_sha256']}`.
- Run ID:`{info['run_id']}`; shard:`shard-00`; personnel:`person-01`.
- Current status:{completion}
{cost}
## Key dependencies

{package_lines}

## Model and startup

- API: `qwen/qwen3-30b-a3b-instruct-2507`, supplier `SiliconFlow`, temperature=0.
- Detector:`protectai/deberta-v3-base-prompt-injection-v2`, threshold 0.5; model file hash verified through frozen list check.
- Python startup configuration `PYTHONHASHSEED=0`, `TOKENIZERS_PARALLELISM=false`, `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`.
- Personal entry point:`qsub tasks/01/run_person01.pbs`The script uses a private Group 9 key file path without including the key value.
- Perform offline checks first at the entry point, then invoke the original repository. `scripts/formal/person-1.pbs`, run only shard-00, then invoke the original export tool after completion.
- Public executor, tasks, attacks, models, dependencies, and official manifests remain unchanged. New code only records personal environment, passive monitoring costs, and schedules checks/export.
- This API budget is $2, with $0.05 reserved per request. Passive monitoring writes cost alert files and logs at $1.50, requiring monitoring personnel to read and query users; the script does not send notifications automatically. Frozen executor retains original budget stop behavior and no automatic resumption limit. After $2, further continuation requires separate review and directory deletion for rerun is not allowed.

## Validation and recording

- `pip check`, all offline unit tests, MVP MCP pre-check, parsing recovery check, and formal MCP pre-check are passed before starting the API experiment.
- Official pre-check includes 60 attack transmission checks, 20 task flow checks, 14 configuration/entry flow checks, using script responses, and does not count toward official model results.
- Source code, critical dependencies, and detector hashes are verified by the original frozen validator.
- Private prep logs and machine-readable environment records:`runs/person01-preparation/{info['pbs_job_id']}/`.
- Private official records:`runs/studies/{info['run_id']}/shard-00/`, fully preserved without submitting original requests simulated states or keys.
'''
    (delivery / 'ENVIRONMENT.md').write_text(text)


def monitor():
    require_compute()
    run_dir = ROOT / 'runs/studies' / os.environ['TRUSTGATE_RUN_ID'] / 'shard-00'
    warned = False
    previous = None
    while True:
        try:
            budget = read_json(run_dir / 'budget.json') if (run_dir / 'budget.json').exists() else {}
            rows = read_json(run_dir / 'results.json') if (run_dir / 'results.json').exists() else []
            cost = budget.get('reported_cost_usd', 0)
            state = {'recorded': len(rows), 'planned': 336, 'reported_cost_usd': cost,
                     'uncertain_reserved_usd': budget.get('uncertain_reserved_usd', 0)}
            if state != previous:
                print('PERSON01_PROGRESS=' + json.dumps(state), flush=True)
                previous = state
            if cost >= 1.50 and not warned:
                alert = {'message': 'Ask the user before any additional budget is authorized.', **state}
                Path(os.environ['TRUSTGATE_PREP_DIR'], 'budget_attention.json').write_text(json.dumps(alert, indent=2) + '\n')
                print('BUDGET_ATTENTION=' + json.dumps(alert), flush=True)
                warned = True
            if (run_dir / 'worker_summary.json').exists():
                return
        except (FileNotFoundError, json.JSONDecodeError):
            # The frozen results writer replaces the JSON contents non-atomically.
            pass
        time.sleep(30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('environment', 'monitor'))
    parser.add_argument('stage', nargs='?', choices=('before', 'preflight_passed', 'completed'))
    args = parser.parse_args()
    if args.command == 'environment':
        if args.stage is None:
            parser.error('environment requires a stage')
        environment(args.stage)
    else:
        monitor()
