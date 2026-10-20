"""Explicit local launcher. No PBS impersonation or changes to frozen algorithms."""
import argparse
import asyncio
import contextlib
import json
import os
import re
import sys
import time
from pathlib import Path
from runtime import ROOT, environment, verify, write_json


def experiment_class():
    from trustgate.formal_engine import FormalExperiment
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    class LocalExperiment(FormalExperiment):
        # The only experiment override: identical three MCP servers without PBS env.
        async def start(self, stack):
            for name in ('calendar', 'mail', 'drive'):
                log = stack.enter_context((self.out / ('mcp_%s.stderr' % name)).open('w'))
                params = StdioServerParameters(command=sys.executable,
                    args=[str(ROOT / 'experiments/mvp/mcp_workspace_server.py'), name, str(self.control)],
                    env={'PYTHONUNBUFFERED': '1', 'PYTHONHASHSEED': '0'})
                streams = await stack.enter_async_context(stdio_client(params, errlog=log))
                client = await stack.enter_async_context(ClientSession(*streams))
                init = await client.initialize()
                self.clients[name] = client
                write_json(self.out / ('mcp_%s_initialize.json' % name), init.model_dump(mode='json'))
    return LocalExperiment


async def execute(plan, detector_dir, run_id, output_root, key, experiment_type, suite, detector):
    from trustgate.budget import Budget
    shard = plan['shards'][2]  # Person 3 only; never launch another person's cases.
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', run_id):
        raise ValueError('Invalid run ID.')
    os.umask(0o077)
    folder = Path(output_root) / run_id / 'shard-02'
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.mkdir()  # No overwrite/resume, including incomplete previous attempts.
    cfg = dict(plan['config'], max_total_cost_usd=shard['budget_usd'])
    provenance = environment()
    from trustgate.formal_manifest import detector_hashes
    provenance['detector_sha256'] = detector_hashes(detector_dir)
    manifest = dict(plan_sha256=plan['plan_sha256'], source_sha256=plan['source_sha256'],
                    shard_index=2, run_id=run_id, python=provenance['python'],
                    packages=provenance['packages'], pbs_job_id=None,
                    classifier_revision=(ROOT / 'models/detector_revision.txt').read_text().strip(),
                    platform=provenance)
    write_json(folder / 'manifest.json', manifest)
    write_json(folder / 'plan.json', plan)
    write_json(folder / 'config.json', cfg)
    ledger = Budget(shard['budget_usd'], cfg.get('per_request_reservation_usd', 0.05))
    write_json(folder / 'budget.json', ledger.snapshot())

    class BudgetedExperiment(experiment_type):
        def completion(self, messages, tools, trial_folder, step):
            ledger.reserve()
            write_json(folder / 'budget.json', ledger.snapshot())
            try:
                answer, record = super().completion(messages, tools, trial_folder, step)
                ledger.reconcile(record['usage']['cost'])
                return answer, record
            except Exception:
                if ledger.pending:
                    ledger.unknown()
                raise
            finally:
                write_json(folder / 'budget.json', ledger.snapshot())

    started = time.monotonic()
    experiment = None
    fatal = None
    try:
        experiment = BudgetedExperiment(cfg, folder, suite, detector, key)
        async with contextlib.AsyncExitStack() as stack:
            await experiment.start(stack)
            for index, case in enumerate(shard['cases'], 1):
                row = await experiment.run_case(case, index)
                if row['error'] and row['error']['type'] in ('HTTPError', 'URLError', 'TimeoutError', 'BudgetExceeded'):
                    fatal = row['error']
                    break
    except Exception as exc:
        fatal = dict(type=type(exc).__name__, message=str(exc).replace(key, '[REDACTED]'))
    finally:
        rows = experiment.rows if experiment else []
        if fatal is None and (ledger.halted or ledger.pending or ledger.uncertain):
            fatal = dict(type='BudgetExceeded', message='Unresolved or halted cost ledger')
        if fatal is None and abs(sum(r.get('cost_usd', 0) for r in rows) - ledger.reported) > 1e-9:
            fatal = dict(type='CostAccountingError', message='Result costs differ from the request ledger')
        write_json(folder / 'worker_summary.json', dict(plan_sha256=plan['plan_sha256'], shard_index=2,
            planned=len(shard['cases']), recorded=len(rows), complete=len(rows) == len(shard['cases']) and fatal is None,
            wall_seconds=time.monotonic() - started, fatal_error=fatal, budget=ledger.snapshot()))
    if fatal:
        raise RuntimeError('Worker stopped. Keep all files and inspect worker_summary.json before a separately planned recovery.')
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT / 'assignments/formal/plan.json')
    parser.add_argument('--detector-dir', type=Path, required=True)
    parser.add_argument('--run-id')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'runs/studies')
    parser.add_argument('--check', action='store_true', help='Verify frozen runtime only; no API or credentials')
    parser.add_argument('--execute', action='store_true', help='Explicitly execute the 336-case, $2 person-3 shard')
    args = parser.parse_args()
    if args.check == args.execute:
        parser.error('Choose exactly one of --check or --execute.')
    if args.execute and not args.run_id:
        parser.error('--execute requires --run-id agreed with the team.')
    plan = verify(args.plan, args.detector_dir)
    if args.check:
        print(json.dumps(dict(passed=True, api_calls=0, platform=environment()), indent=2))
        return
    from trustgate.runner import get_key
    from agentdojo.task_suite.load_suites import get_suite
    sys.path.insert(0, str(ROOT / 'experiments/mvp'))
    from detector import Detector
    key = get_key()
    from api_check import probe
    print(json.dumps(probe(key)), flush=True)
    suite = get_suite(plan['config']['benchmark'], plan['config']['suite'])
    detector = Detector(args.detector_dir, plan['config']['classifier_threshold'])
    result = asyncio.run(execute(plan, args.detector_dir, args.run_id, args.output_root,
                                 key, experiment_class(), suite, detector))
    print(result)


if __name__ == '__main__':
    main()
