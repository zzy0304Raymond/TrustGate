"""Continue only never-started cases after a reviewed infrastructure stop."""
import argparse
import asyncio
import contextlib
import os
import socket
import sys
import time
from pathlib import Path
from study import ROOT, PUBLIC, read, sha, dump, digest, checked_plan
from trustgate.runner import require_compute, get_key
from trustgate.formal_manifest import verify_runtime
from trustgate.formal_engine import FormalExperiment
from trustgate.budget import Budget
from agentdojo.task_suite.load_suites import get_suite
from detector import Detector

MANIFEST = PUBLIC / 'continuation-01.json'


def prepare(prior):
    require_compute()
    parent = checked_plan(prior / 'plan.json')
    rows = read(prior / 'results.json')
    worker = read(prior / 'worker_summary.json')
    assert parent['stage'] == 'evaluation' and not worker['complete']
    assert worker['fatal_error']['type'] == 'TimeoutError'
    assert len(rows) == 128 and rows[-1]['error']['type'] == 'TimeoutError'
    assert [r['case_id'] for r in rows] == [c['case_id'] for c in parent['cases'][:len(rows)]]
    assert all(r['error'] is None for r in rows[:-1])
    remaining = parent['cases'][len(rows):]
    assert len(remaining) == 16
    budget_left = parent['budget_usd'] - worker['budget']['reported_cost_usd'] - worker['budget']['uncertain_reserved_usd']
    plan = dict(schema_version=1, parent_plan_sha256=parent['plan_sha256'],
                prior_results_sha256=sha(prior / 'results.json'), prior_worker_sha256=sha(prior / 'worker_summary.json'),
                prior_recorded=len(rows), preserved_failure_case_id=rows[-1]['case_id'],
                cases=remaining, budget_usd=min(1.0, budget_left), max_requests=len(remaining) * parent['config']['max_model_calls'],
                original_budget_remaining_after_reservation=budget_left,
                rationale='Retain the timed-out case; execute only the 16 never-started cases, in original order. No replacement or retry.',
                source_sha256=sha(Path(__file__)))
    plan['continuation_sha256'] = digest(plan)
    if MANIFEST.exists():
        raise FileExistsError('Do not overwrite a frozen continuation')
    dump(MANIFEST, plan)
    print('CONTINUATION_FROZEN', len(remaining), plan['continuation_sha256'], flush=True)


async def run(prior, folder):
    require_compute()
    assert not sys.flags.hash_randomization
    plan = read(MANIFEST)
    assert plan['continuation_sha256'] == digest({k: v for k, v in plan.items() if k != 'continuation_sha256'})
    assert plan['source_sha256'] == sha(Path(__file__))
    assert sha(prior / 'results.json') == plan['prior_results_sha256']
    assert sha(prior / 'worker_summary.json') == plan['prior_worker_sha256']
    parent = checked_plan(prior / 'plan.json')
    assert parent['plan_sha256'] == plan['parent_plan_sha256']
    assert plan['cases'] == parent['cases'][plan['prior_recorded']:]
    assert plan['preserved_failure_case_id'] not in {c['case_id'] for c in plan['cases']}
    verify_runtime(read(ROOT / 'assignments/formal/plan.json'), os.environ['TRUSTGATE_DETECTOR_DIR'])
    os.umask(0o077)
    folder.mkdir(parents=True, exist_ok=False)
    dump(folder / 'continuation.json', plan)
    cfg = dict(parent['config'], max_total_cost_usd=plan['budget_usd'])
    ledger = Budget(plan['budget_usd'], 0.05)
    key = get_key()
    requests = 0

    class Bounded(FormalExperiment):
        def completion(self, messages, tools, trial_folder, step):
            nonlocal requests
            assert requests < plan['max_requests']
            ledger.reserve()
            requests += 1
            dump(folder / 'budget.json', ledger.snapshot())
            try:
                message, record = super().completion(messages, tools, trial_folder, step)
                ledger.reconcile(record['usage']['cost'])
                return message, record
            except Exception:
                if ledger.pending:
                    ledger.unknown()
                raise
            finally:
                dump(folder / 'budget.json', ledger.snapshot())

    started, experiment, fatal = time.monotonic(), None, None
    try:
        detector = Detector(Path(os.environ['TRUSTGATE_DETECTOR_DIR']), cfg['classifier_threshold'])
        experiment = Bounded(cfg, folder, get_suite(cfg['benchmark'], cfg['suite']), detector, key)
        async with contextlib.AsyncExitStack() as stack:
            await experiment.start(stack)
            for index, case in enumerate(plan['cases'], plan['prior_recorded'] + 1):
                row = await experiment.run_case(case, index)
                if row['error']:
                    fatal = row['error']
                    break
    except Exception as exc:
        fatal = dict(type=type(exc).__name__, message=str(exc).replace(key, '[REDACTED]'))
    finally:
        rows = experiment.rows if experiment else []
        dump(folder / 'worker_summary.json', dict(plan_sha256=parent['plan_sha256'],
             continuation_sha256=plan['continuation_sha256'], planned=len(plan['cases']), recorded=len(rows),
             complete=len(rows) == len(plan['cases']) and fatal is None, wall_seconds=time.monotonic() - started,
             fatal_error=fatal, attempted_requests=requests, budget=ledger.snapshot(), host=socket.gethostname(),
             pbs_job_id=os.environ['PBS_JOBID']))
    if fatal:
        raise RuntimeError('Continuation stopped; keep failures. No automatic retry.')
    print('CONTINUATION_COMPLETE', len(rows), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'run'])
    parser.add_argument('prior', type=Path)
    parser.add_argument('output', type=Path, nargs='?')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.prior)
    else:
        asyncio.run(run(args.prior, args.output))
