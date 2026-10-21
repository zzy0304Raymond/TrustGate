"""Bounded local/MCP transport validation using the frozen formal agent loop."""
import argparse
import asyncio
import contextlib
import copy
import csv
import hashlib
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from trustgate.planning import digest
from trustgate.runner import require_compute, get_key, dump
from trustgate.budget import Budget
from trustgate.formal_engine import FormalExperiment
from trustgate.formal_manifest import verify_runtime
from trustgate.formal_data import attack_success
import run_matrix_v2 as engine
from simulation_runtime import read_state
from agentdojo.task_suite.load_suites import get_suite

PUBLIC = ROOT / 'assignments/transport_validation'
RESULTS = ROOT / 'results/transport_validation'
TASKS = [0, 17, 27, 12, 31, 18]
FIELDS = ['case_id', 'task', 'workflow', 'surface', 'attack_case_id', 'repeat', 'transport',
          'status', 'native_utility', 'attacker_success', 'safe_completion',
          'injection_reached_model', 'seconds', 'api_calls', 'api_seconds',
          'prompt_tokens', 'completion_tokens', 'cost_usd', 'tool_calls', 'tool_errors']


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TransportExperiment(FormalExperiment):
    """Add the same one-shot output injector to native execution, without changing core files."""
    async def run_case(self, case, index):
        native = engine.run_native
        attack = self.cfg['formal_attacks'].get(case.get('attack_case_id'))
        consumed = False

        def injected(runtime, env, name, args):
            nonlocal consumed
            result, error = native(runtime, env, name, args)
            if (case['surface'] == 'output' and attack and not consumed
                    and not error and name in attack['output_tools']):
                result = engine.tool_result_to_str(result) + '\n\n' + attack['payload']
                consumed = True
            return result, error

        # Cases run sequentially. MCP uses its unchanged server-side injector.
        if case['transport'] == 'local':
            engine.run_native = injected
        try:
            return await super().run_case(case, index)
        finally:
            engine.run_native = native


def prepare():
    require_compute()
    formal = read(ROOT / 'assignments/formal/plan.json')
    verify_runtime(formal, os.environ['TRUSTGATE_DETECTOR_DIR'])
    cases = []
    scenarios = [(f'user_task_{n}', 'benign', None) for n in TASKS]
    scenarios += [(f'user_task_{n}', 'output', f'user_task_{n}-output-1') for n in [0, 17]]
    assert len({formal['config']['formal_tasks'][t]['workflow'][:2] for t, _, _ in scenarios}) == 6
    for task, surface, aid in scenarios:
        for repeat in [1, 2, 3]:
            pair = []
            for transport in ['local', 'mcp']:
                case = dict(task=task, workflow=formal['config']['formal_tasks'][task]['workflow'],
                            surface=surface, attack_case_id=aid, repeat=repeat,
                            condition='none', transport=transport, split='transport_validation')
                case['case_id'] = digest(case)[:20]
                pair.append(case)
            cases.append(pair)
    rng = random.Random(421322)
    rng.shuffle(cases)
    for pair in cases:
        rng.shuffle(pair)
    cfg = copy.deepcopy(formal['config'])
    cfg['max_total_cost_usd'] = 1.0
    plan = dict(schema_version=1, purpose='Post-hoc transport validation, separate from formal test scores',
                original_plan_sha256=formal['plan_sha256'], planned_cases=48, max_requests=384,
                budget_usd=1.0, config=cfg, cases=[c for pair in cases for c in pair],
                source_sha256={str(p.relative_to(ROOT)): sha(p) for p in
                               [Path(__file__), PUBLIC / 'PROTOCOL_ZH.md']})
    plan['plan_sha256'] = digest(plan)
    path = PUBLIC / 'plan.json'
    if path.exists():
        raise FileExistsError('Frozen transport plan already exists')
    dump(path, plan)
    print('PLAN_FROZEN', plan['plan_sha256'], flush=True)


def checked():
    plan = read(PUBLIC / 'plan.json')
    assert plan['plan_sha256'] == digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
    assert len(plan['cases']) == len({c['case_id'] for c in plan['cases']}) == 48
    for c in plan['cases']:
        assert c['case_id'] == digest({k: v for k, v in c.items() if k != 'case_id'})[:20]
    for path, expected in plan['source_sha256'].items():
        assert sha(ROOT / path) == expected, path
    return plan


async def controls(output):
    require_compute()
    plan = checked()
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    experiment = TransportExperiment(plan['config'], folder, get_suite('v1.2.2', 'workspace'), None, 'offline')
    scenarios = list(dict.fromkeys((c['task'], c['surface'], c['attack_case_id']) for c in plan['cases']))
    records = []
    async with contextlib.AsyncExitStack() as stack:
        await experiment.start(stack)
        for task, surface, aid in scenarios:
            snapshots = {}
            for transport in ['local', 'mcp']:
                case = dict(task=task, workflow=plan['config']['formal_tasks'][task]['workflow'],
                            surface=surface, attack_case_id=aid, repeat=1, condition='none', transport=transport)
                name = plan['config']['formal_tasks'][task]['output_tools'][0]
                args = {} if name == 'list_files' else {'query': ''}
                def completion(messages, tools, trial_folder, step):
                    if step == 1:
                        return dict(content=None, tool_calls=[dict(id='probe', type='function',
                            function=dict(name=name, arguments=json.dumps(args)))]), dict(usage={'cost': 0}, seconds=0)
                    return dict(content='Transport equivalence check.'), dict(usage={'cost': 0}, seconds=0)
                experiment.completion = completion
                row = await experiment.run_case(case, len(experiment.rows) + 1)
                assert row['status'] == 'completed' and row['tool_errors'] == 0
                if surface == 'output':
                    assert row['injection_reached_model']
                trial = Path(row['result_dir'])
                snapshots[transport] = {name: read(trial / (name + '.json')) for name in
                                        ['raw_tools', 'trajectory', 'environment_before', 'environment_after']}
            assert snapshots['local'] == snapshots['mcp'], (task, surface)
            records.append(dict(task=task, surface=surface, attack_case_id=aid,
                                identical_tools_requests_results_and_state=True))
    dump(folder / 'checks.json', dict(passed=True, plan_sha256=plan['plan_sha256'],
                                     model_requests=0, scripted=True, records=records))
    print('TRANSPORT_CONTROLS_PASSED', len(records), flush=True)


async def run(output):
    require_compute()
    if sys.flags.hash_randomization:
        raise RuntimeError('Start Python with PYTHONHASHSEED=0')
    plan = checked()
    verify_runtime(read(ROOT / 'assignments/formal/plan.json'), os.environ['TRUSTGATE_DETECTOR_DIR'])
    os.umask(0o077)
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=False)
    dump(folder / 'plan.json', plan)
    ledger, count = Budget(plan['budget_usd']), 0
    key = get_key()
    class Bounded(TransportExperiment):
        def completion(self, messages, tools, trial_folder, step):
            nonlocal count
            if count >= plan['max_requests']:
                raise RuntimeError('Request limit reached')
            ledger.reserve()
            count += 1
            dump(folder / 'budget.json', ledger.snapshot())
            try:
                answer, record = super().completion(messages, tools, trial_folder, step)
                ledger.reconcile(record['usage']['cost'])
                return answer, record
            finally:
                if ledger.pending:
                    ledger.unknown()
                dump(folder / 'budget.json', ledger.snapshot())
    started = time.monotonic()
    experiment = Bounded(plan['config'], folder, get_suite('v1.2.2', 'workspace'), None, key)
    fatal = None
    try:
        async with contextlib.AsyncExitStack() as stack:
            await experiment.start(stack)
            for i, case in enumerate(plan['cases'], 1):
                row = await experiment.run_case(case, i)
                if row['error']:
                    fatal = row['error']
                    break
    except Exception as exc:
        fatal = dict(type=type(exc).__name__, message=str(exc).replace(key, '[REDACTED]'))
    finally:
        dump(folder / 'worker_summary.json', dict(plan_sha256=plan['plan_sha256'],
             planned=48, recorded=len(experiment.rows), complete=len(experiment.rows) == 48 and fatal is None,
             wall_seconds=time.monotonic() - started, fatal_error=fatal, attempted_requests=count,
             budget=ledger.snapshot()))
    if fatal:
        raise RuntimeError('Transport batch stopped; retain all records and do not retry completed cases')


def summarize(rows):
    groups = []
    for surface in ['benign', 'output']:
        for transport in ['local', 'mcp']:
            rs = [r for r in rows if r['surface'] == surface and r['transport'] == transport]
            valid = [r for r in rs if r['status'] not in ['error', 'task_timeout']]
            groups.append(dict(surface=surface, transport=transport, recorded=len(rs), valid=len(valid),
                native_successes=sum(r['native_utility'] is True for r in valid),
                attack_successes=sum(r['attacker_success'] is True for r in valid) if surface == 'output' else None,
                exposed=sum(r['injection_reached_model'] is True for r in rs),
                mean_seconds=statistics.mean(r['seconds'] for r in rs),
                mean_api_calls=statistics.mean(r['api_calls'] for r in rs)))
    return groups


def export(output, control):
    require_compute()
    plan = checked()
    folder = Path(output)
    worker = read(folder / 'worker_summary.json')
    rows = read(folder / 'results.json')
    assert worker['complete'] and len(rows) == 48
    assert [r['case_id'] for r in rows] == [c['case_id'] for c in plan['cases']]
    sources, records = {}, []
    for row in rows:
        trial = Path(row['result_dir'])
        before, after = read(trial / 'environment_before.json'), read(trial / 'environment_after.json')
        task = get_suite('v1.2.2', 'workspace').user_tasks[row['task']]
        env = task.init_environment(get_suite('v1.2.2', 'workspace').load_and_inject_default_environment({}))
        assert digest(before) == digest(env.model_dump(mode='json'))
        requests = sorted(trial.glob('request_*.json'))
        responses = sorted(trial.glob('response_*.json'))
        assert len(requests) == len(responses) == row['api_calls']
        hashes = {p.name: sha(p) for p in sorted(trial.glob('*.json'))}
        records.append(dict(case_id=row['case_id'], source_files=hashes,
                            request_response_count_matches=True, initial_state_matches=True))
        sources[row['case_id']] = hashes
    controls_result = read(Path(control) / 'checks.json')
    assert controls_result['passed'] and controls_result['plan_sha256'] == plan['plan_sha256']
    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / 'trials.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({k: r[k] for k in FIELDS} for r in rows)
    dump(RESULTS / 'summary.json', dict(plan_sha256=plan['plan_sha256'], groups=summarize(rows), worker=worker))
    dump(RESULTS / 'checks.json', dict(records=records, controls=controls_result, passed=True))
    dump(RESULTS / 'manifest.json', dict(files_sha256={str(p.relative_to(ROOT)): sha(p) for p in
         [PUBLIC / 'plan.json', PUBLIC / 'PROTOCOL_ZH.md', Path(__file__),
          RESULTS / 'trials.csv', RESULTS / 'summary.json', RESULTS / 'checks.json']}))
    print('TRANSPORT_EXPORTED', len(rows), flush=True)


def verify():
    plan = checked()
    for path, expected in read(RESULTS / 'manifest.json')['files_sha256'].items():
        assert sha(ROOT / path) == expected, path
    rows = list(csv.DictReader((RESULTS / 'trials.csv').open()))
    assert [r['case_id'] for r in rows] == [c['case_id'] for c in plan['cases']]
    assert len(rows) == 48
    for row in rows:
        for field in ['native_utility', 'attacker_success', 'safe_completion', 'injection_reached_model']:
            row[field] = {'True': True, 'False': False, '': None}[row[field]]
        for field in ['seconds', 'api_calls']:
            row[field] = float(row[field])
    assert summarize(rows) == read(RESULTS / 'summary.json')['groups']
    print('TRANSPORT_PUBLIC_VERIFIED', len(rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'controls', 'run', 'export', 'verify'])
    parser.add_argument('--output', default='runs/transport_validation/live')
    parser.add_argument('--controls', default='runs/transport_validation/controls')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'controls':
        asyncio.run(controls(args.controls))
    elif args.command == 'run':
        asyncio.run(run(args.output))
    elif args.command == 'export':
        export(args.output, args.controls)
    else:
        verify()
