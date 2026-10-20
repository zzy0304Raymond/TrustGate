"""Bounded person-03 recovery; keeps original trials, cumulative cost and provenance."""
import argparse
import asyncio
import contextlib
import copy
import csv
import datetime
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/platforms/local'))
import runtime
import run as local_run
import delivery
from trustgate.budget import Budget
from trustgate.planning import digest, read_plan

IDENTITY = ('case_id', 'slot_id', 'task', 'workflow', 'surface', 'condition',
            'repeat', 'transport', 'attack_case_id', 'split')
STOP = False
STATUS_PATH = None


def publish_status(folder, state, recorded, budget, fatal=None):
    if STATUS_PATH is not None:
        runtime.write_json(STATUS_PATH, dict(observed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            state=state, attempt_id=folder.parent.name, recorded=recorded, planned=336,
            reported_cost_usd=budget['reported_cost_usd'],
            uncertain_reserved_usd=budget['uncertain_reserved_usd'],
            pending_reserved_usd=budget['pending_reserved_usd'], total_budget_usd=budget['limit_usd'],
            fatal_error_type=fatal['type'] if fatal else None, worker_directory=str(folder), pid=os.getpid()))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def durable(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    if os.name == 'posix':
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def check_rows(plan, rows):
    expected = plan['shards'][2]['cases']
    if not 0 < len(rows) <= len(expected):
        raise ValueError('Invalid person-03 prefix length')
    for row, case in zip(rows, expected):
        if any(row.get(k) != case.get(k) for k in IDENTITY):
            raise ValueError('Results must be the exact original ordered person-03 prefix')
        if not isinstance(row['cost_usd'], (float, int)) or not math.isfinite(row['cost_usd']) or row['cost_usd'] < 0:
            raise ValueError('Invalid row cost')


def check_ledger(plan, rows, ledger, allowed_uncertain=0.0, allow_halted=False):
    expected = Budget(plan['shards'][2]['budget_usd'], plan['config']['per_request_reservation_usd']).snapshot()
    expected['reported_cost_usd'] = ledger['reported_cost_usd']
    expected['uncertain_reserved_usd'] = allowed_uncertain
    expected['halted'] = ledger['halted'] if allow_halted else False
    if ledger != expected or not math.isfinite(ledger['reported_cost_usd']):
        raise ValueError('Unresolved, halted or changed budget')
    if not 0 <= ledger['reported_cost_usd'] + allowed_uncertain < ledger['limit_usd']:
        raise ValueError('No remaining budget')
    if abs(sum(r['cost_usd'] for r in rows) - ledger['reported_cost_usd']) > 1e-9:
        raise ValueError('Result and ledger cost mismatch')


def check_traces(plan, rows, allow_recorded_timeout=False):
    """Read only numeric/model metadata; never emit requests, answers or state."""
    allowed = (ROOT / 'runs').resolve()
    unresolved = []
    for row in rows:
        folder = Path(row['result_dir']).resolve()
        if allowed not in folder.parents:
            raise ValueError('Trace directory is outside private runs')
        requests = sorted(folder.glob('request_*.json'))
        responses = sorted(folder.glob('response_*.json'))
        missing = len(requests) - len(responses)
        timed_out = (row.get('error') or {}).get('type') == 'TimeoutError'
        if missing and not (allow_recorded_timeout and timed_out and missing == 1):
            raise ValueError('Unaccounted request requires explicit timeout continuation authorization')
        if len(responses) != row['api_calls']:
            raise ValueError('Unaccounted request/response files')
        if missing:
            unresolved.append(dict(case_id=row['case_id'], request_name=requests[-1].name,
                request_sha256=runtime.sha(requests[-1]),
                uncertain_reserved_usd=plan['config']['per_request_reservation_usd']))
        for request_path in requests:
            request = read(request_path)
            if request['model'] != plan['config']['model'] or request['provider'] != {
                    'order': [plan['config']['provider']], 'allow_fallbacks': False, 'require_parameters': True}:
                raise ValueError('Request model/provider differs from freeze')
            if request['temperature'] != plan['config']['temperature'] or request['max_tokens'] != plan['config']['max_output_tokens']:
                raise ValueError('Request generation settings changed')
        costs = []
        for request_path, response_path in zip(requests, responses):
            if request_path.stem.removeprefix('request_') != response_path.stem.removeprefix('response_'):
                raise ValueError('Unpaired request/response')
            request, response = read(request_path), read(response_path)
            if request['model'] != plan['config']['model'] or response['model'] != plan['config']['model']:
                raise ValueError('Actual API model differs from frozen model')
            if request['provider'] != {'order': [plan['config']['provider']], 'allow_fallbacks': False, 'require_parameters': True} or response['provider'] != plan['config']['provider']:
                raise ValueError('Actual API provider differs from frozen provider')
            if request['temperature'] != plan['config']['temperature'] or request['max_tokens'] != plan['config']['max_output_tokens']:
                raise ValueError('API generation settings changed')
            costs.append(response['usage']['cost'])
        if abs(sum(costs) - row['cost_usd']) > 1e-9:
            raise ValueError('Trace costs differ from persisted row')
    return unresolved


def inspect_source(plan, source, traces=True, allow_recorded_timeout=False):
    source = Path(source).resolve()
    manifest = read(source / 'manifest.json')
    rows, ledger = read(source / 'results.json'), read(source / 'budget.json')
    paused = (source / 'PAUSE_CHECKPOINT.json').exists()
    if paused:
        checkpoint = read(source / 'PAUSE_CHECKPOINT.json')
        if checkpoint['status'] != 'paused_by_user':
            raise ValueError('Unexpected checkpoint status')
    else:
        summary = read(source / 'worker_summary.json')
        if not allow_recorded_timeout or summary.get('complete') or (summary.get('fatal_error') or {}).get('type') != 'TimeoutError':
            raise ValueError('Only an explicitly authorized recorded timeout may continue')
        if summary['recorded'] != len(rows) or summary['budget'] != ledger or ledger['halted'] is not True:
            raise ValueError('Failed-attempt summary/ledger mismatch')
        previous_bound = read(source / 'recovery.json')
        if previous_bound['recovery_sha256'] != digest({k:v for k,v in previous_bound.items() if k != 'recovery_sha256'}):
            raise ValueError('Previous recovery manifest changed')
        if runtime.sha(source / 'recovery_source.py') != previous_bound['recovery_entrypoint_sha256']:
            raise ValueError('Previous execution source snapshot changed')
        if manifest['recovery_sha256'] != previous_bound['recovery_sha256']:
            raise ValueError('Previous attempt provenance mismatch')
        checkpoint = dict(manifest, adapter_sha256=manifest['platform']['adapter_sha256'],
            results_sha256=runtime.sha(source / 'results.json'), budget=ledger,
            completed_count=len(rows), completed_case_ids=[r['case_id'] for r in rows],
            remaining_count=336-len(rows), remaining_case_ids=[c['case_id'] for c in plan['shards'][2]['cases'][len(rows):]],
            interrupted_case_requests=0)
    if manifest['shard_index'] != 2:
        raise ValueError('Only an explicitly paused person-03 attempt can resume')
    for item in (checkpoint, manifest):
        if item['plan_sha256'] != plan['plan_sha256'] or item['source_sha256'] != plan['source_sha256']:
            raise ValueError('Paused attempt differs from the frozen plan/source')
    if read(source / 'plan.json') != plan or manifest['packages'] != plan['packages']:
        raise ValueError('Paused plan/packages changed')
    if checkpoint['adapter_sha256'] != runtime.adapter_hashes() or manifest['platform']['adapter_sha256'] != runtime.adapter_hashes():
        raise ValueError('Original local adapter changed; review before recovery')
    if manifest['platform']['detector_sha256'] != plan['detector_sha256']:
        raise ValueError('Detector identity changed')
    if runtime.sha(source / 'results.json') != checkpoint['results_sha256'] or ledger != checkpoint['budget']:
        raise ValueError('Paused results/ledger changed since checkpoint')
    check_rows(plan, rows)
    unresolved = check_traces(plan, rows, allow_recorded_timeout) if traces else []
    uncertain = sum(item['uncertain_reserved_usd'] for item in unresolved)
    check_ledger(plan, rows, ledger, allowed_uncertain=uncertain, allow_halted=not paused)
    done = [r['case_id'] for r in rows]
    remaining = [c['case_id'] for c in plan['shards'][2]['cases'][len(rows):]]
    if not remaining or done != checkpoint['completed_case_ids'] or remaining != checkpoint['remaining_case_ids']:
        raise ValueError('Checkpoint selection mismatch')
    if checkpoint['completed_count'] != len(done) or checkpoint['remaining_count'] != len(remaining):
        raise ValueError('Checkpoint count mismatch')
    if checkpoint['interrupted_case_requests'] != 0:
        raise ValueError('Interrupted paid request requires separate reconciliation')
    # Unfinished trial directories must have zero requests, even if the checkpoint says zero.
    for folder in source.iterdir():
        if folder.is_dir() and folder.name[:3].isdigit() and int(folder.name[:3]) > len(rows):
            if list(folder.glob('request_*.json')) or list(folder.glob('response_*.json')):
                raise ValueError('Unrecorded attempted trial; cannot silently rerun')
    return rows, ledger, manifest


def build_bound(plan, source, attempt_id, traces=True, allow_recorded_timeout=False):
    if not __import__('re').fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', attempt_id):
        raise ValueError('Invalid attempt ID')
    source = Path(source).resolve()
    rows, ledger, manifest = inspect_source(plan, source, traces, allow_recorded_timeout)
    source_files = ['results.json', 'budget.json', 'manifest.json', 'plan.json']
    source_files += (['PAUSE_CHECKPOINT.json'] if (source / 'PAUSE_CHECKPOINT.json').exists()
                     else ['worker_summary.json', 'recovery.json', 'recovery_source.py'])
    bound = dict(schema='person03-recovery-v2', attempt_id=attempt_id, person=3, shard_index=2,
        formal_plan_sha256=plan['plan_sha256'], original_run_id=manifest['run_id'],
        source_directory=str(source), source_file_sha256={n: runtime.sha(source / n) for n in source_files},
        recovery_entrypoint_sha256=runtime.sha(__file__), adapter_sha256=runtime.adapter_hashes(),
        preserved_case_ids=[r['case_id'] for r in rows],
        remaining_case_ids=[c['case_id'] for c in plan['shards'][2]['cases'][len(rows):]],
        carried_cost_usd=ledger['reported_cost_usd'], total_budget_usd=ledger['limit_usd'],
        carried_uncertain_reserved_usd=ledger['uncertain_reserved_usd'],
        allow_recorded_timeout=allow_recorded_timeout,
        unresolved_requests=check_traces(plan, rows, allow_recorded_timeout) if traces else [],
        remaining_budget_usd=ledger['limit_usd'] - ledger['reported_cost_usd'] - ledger['uncertain_reserved_usd'],
        max_new_model_calls=(336-len(rows))*plan['config']['max_model_calls'],
        retry_policy='No retry, no result replacement; retain all model failures.',
        created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    bound['recovery_sha256'] = digest(bound)
    return bound


def verify_bound(plan, bound, traces=True):
    if bound['recovery_sha256'] != digest({k: v for k, v in bound.items() if k != 'recovery_sha256'}):
        raise ValueError('Recovery manifest hash mismatch')
    fresh = build_bound(plan, bound['source_directory'], bound['attempt_id'], traces,
                        bound.get('allow_recorded_timeout', False))
    for key in fresh:
        if key not in ('created_at_utc', 'recovery_sha256') and fresh[key] != bound[key]:
            raise ValueError('Recovery input changed: ' + key)


def public_history(bound, platform, count):
    return dict(attempt_id=bound['attempt_id'], start_index=len(bound['preserved_case_ids'])+1,
        end_index=count, recovery_sha256=bound['recovery_sha256'],
        recovery_entrypoint_sha256=bound['recovery_entrypoint_sha256'],
        adapter_sha256=platform['adapter_sha256'],
        carried_cost_usd=bound['carried_cost_usd'], total_budget_usd=bound['total_budget_usd'],
        carried_uncertain_reserved_usd=bound['carried_uncertain_reserved_usd'])


async def execute(plan, bound, output_root, key, experiment_type, suite, detector):
    verify_bound(plan, bound)
    source = Path(bound['source_directory'])
    rows, old_ledger, original_manifest = inspect_source(plan, source,
        allow_recorded_timeout=bound.get('allow_recorded_timeout', False))
    folder = Path(output_root) / bound['attempt_id'] / 'shard-02'
    folder.parent.mkdir(parents=True, exist_ok=True)
    os.umask(0o077)
    # Permanent claim: a concurrent launcher or accidental repeat cannot spend twice.
    with (source / 'RESUME_CLAIM.json').open('x', encoding='utf-8') as stream:
        json.dump({'recovery_sha256': bound['recovery_sha256'], 'destination': str(folder)}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    folder.mkdir()
    durable(folder / 'recovery.json', bound)
    (folder / 'recovery_source.py').write_bytes(Path(__file__).read_bytes())
    cfg = dict(plan['config'], max_total_cost_usd=bound['total_budget_usd'])
    provenance = runtime.environment()
    provenance['detector_sha256'] = plan['detector_sha256']
    provenance['execution_history'] = original_manifest['platform'].get('execution_history', [
        dict(attempt_id=original_manifest['run_id'], start_index=1, end_index=len(rows),
             adapter_sha256=original_manifest['platform']['adapter_sha256'],
             results_sha256=bound['source_file_sha256']['results.json'],
             pause_checkpoint_sha256=bound['source_file_sha256'].get('PAUSE_CHECKPOINT.json'))])
    provenance['execution_history'] = copy.deepcopy(provenance['execution_history'])
    provenance['execution_history'].append(public_history(bound, provenance, len(rows)))
    manifest = dict(original_manifest, platform=provenance, recovery_sha256=bound['recovery_sha256'],
                    attempt_id=bound['attempt_id'])
    for name, value in (('manifest.json', manifest), ('plan.json', plan), ('config.json', cfg), ('results.json', rows)):
        durable(folder / name, value)
    ledger = Budget(bound['total_budget_usd'], cfg['per_request_reservation_usd'])
    ledger.reported = old_ledger['reported_cost_usd']
    # New authorized attempt, with old halt evidence unchanged in its own directory.
    # The old unknown reservation remains charged against the $2 cumulative allocation.
    ledger.uncertain = bound['carried_uncertain_reserved_usd']
    durable(folder / 'budget.json', ledger.snapshot())
    publish_status(folder, 'running', len(rows), ledger.snapshot())

    class Budgeted(experiment_type):
        def completion(self, messages, tools, trial_folder, step):
            ledger.reserve()
            durable(folder / 'budget.json', ledger.snapshot())
            try:
                answer, record = super().completion(messages, tools, trial_folder, step)
                ledger.reconcile(record['usage']['cost'])
                if record.get('model') != cfg['model'] or record.get('provider') != cfg['provider']:
                    raise RuntimeError('API response model/provider mismatch; preserve charge and stop')
                return answer, record
            except Exception:
                if ledger.pending:
                    ledger.unknown()
                raise
            finally:
                durable(folder / 'budget.json', ledger.snapshot())

    started, fatal, paused = time.monotonic(), None, False
    experiment = None
    try:
        experiment = Budgeted(cfg, folder, suite, detector, key)
        experiment.rows = copy.deepcopy(rows)
        experiment.total_cost = ledger.reported
        async with contextlib.AsyncExitStack() as stack:
            await experiment.start(stack)
            for index, case in enumerate(plan['shards'][2]['cases'][len(rows):], len(rows)+1):
                if STOP or (folder / 'STOP_AFTER_CASE').exists():
                    paused = True
                    break
                if runtime.sha(__file__) != bound['recovery_entrypoint_sha256'] or runtime.adapter_hashes() != bound['adapter_sha256']:
                    raise RuntimeError('Recovery code changed while running')
                row = await experiment.run_case(case, index)
                durable(folder / 'results.json', experiment.rows)
                publish_status(folder, 'running', len(experiment.rows), ledger.snapshot())
                print(json.dumps(dict(recorded=len(experiment.rows), planned=336,
                    reported_cost_usd=ledger.reported, pending_usd=ledger.pending,
                    status=row['status'])), flush=True)
                # Any infrastructure/implementation error stops the recovery; valid model failures remain rows.
                if row.get('error'):
                    fatal = {'type': row['error']['type'], 'message': 'See retained private trial record'}
                    break
                if ledger.halted or ledger.pending or ledger.uncertain != bound['carried_uncertain_reserved_usd']:
                    raise RuntimeError('Unresolved cost ledger')
    except Exception as exc:
        fatal = dict(type=type(exc).__name__, message=str(exc).replace(key, '[REDACTED]'))
    finally:
        current = experiment.rows if experiment else rows
        durable(folder / 'results.json', current)
        try:
            check_rows(plan, current)
            check_ledger(plan, current, ledger.snapshot(), bound['carried_uncertain_reserved_usd'])
        except Exception as exc:
            fatal = fatal or dict(type=type(exc).__name__, message=str(exc))
        # Previous worker wall time was lost on forced termination. Report task time consistently,
        # and record this attempt's exact worker time separately; exclude the overnight pause.
        summary = dict(plan_sha256=plan['plan_sha256'], shard_index=2, planned=336,
            recorded=len(current), complete=len(current)==336 and fatal is None,
            fatal_error=fatal, paused=paused, budget=ledger.snapshot(),
            cost_reconciled=ledger.pending == 0 and ledger.uncertain == 0,
            delivery_ready=len(current)==336 and fatal is None and ledger.uncertain == 0,
            wall_seconds=sum(r['seconds'] for r in current),
            wall_seconds_basis='Sum of case seconds across attempts; excludes startup and overnight pause.',
            recovery_worker_seconds=time.monotonic()-started,
            preserved_records=len(rows), newly_recorded=len(current)-len(rows))
        durable(folder / 'worker_summary.json', summary)
        manifest['platform']['execution_history'][-1]['end_index'] = len(current)
        durable(folder / 'manifest.json', manifest)
        state = ('failed' if fatal else 'paused' if paused else
                 'completed_needs_cost_review' if summary['complete'] and ledger.uncertain else
                 'completed' if summary['complete'] else 'stopped')
        publish_status(folder, state, len(current), ledger.snapshot(), fatal)
        if paused and fatal is None:
            durable(folder / 'PAUSE_CHECKPOINT.json', dict(status='paused_by_user',
                paused_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                plan_sha256=plan['plan_sha256'], source_sha256=plan['source_sha256'],
                adapter_sha256=runtime.adapter_hashes(), budget=ledger.snapshot(),
                completed_count=len(current), completed_case_ids=[r['case_id'] for r in current],
                remaining_count=336-len(current), remaining_case_ids=[c['case_id'] for c in plan['shards'][2]['cases'][len(current):]],
                results_sha256=runtime.sha(folder / 'results.json'), interrupted_case_requests=0))
    if fatal:
        raise RuntimeError('Recovery stopped; retain files and review worker_summary.json. No automatic retry.')
    return folder


def export(plan_path, folder, destination):
    plan = read_plan(plan_path)
    bound, rows, summary = read(folder / 'recovery.json'), read(folder / 'results.json'), read(folder / 'worker_summary.json')
    verify_bound(plan, bound)
    old = read(Path(bound['source_directory']) / 'results.json')
    if rows[:len(old)] != old:
        raise ValueError('Preserved rows changed')
    check_rows(plan, rows)
    check_ledger(plan, rows, summary['budget'])
    check_traces(plan, rows)
    if len(rows) != 336 or not summary['complete'] or summary['fatal_error']:
        raise ValueError('Cannot export incomplete recovery')
    result = delivery.export_local(plan_path, folder, destination)
    platform = read(destination / 'platform_receipt.json')
    proof = dict(schema='person03-recovery-delivery-v1', plan_sha256=plan['plan_sha256'],
        recovery_sha256=bound['recovery_sha256'], recovery_entrypoint_sha256=bound['recovery_entrypoint_sha256'],
        preserved_case_ids=bound['preserved_case_ids'], new_case_ids=bound['remaining_case_ids'],
        preserved_records=len(old), new_records=336-len(old),
        carried_cost_usd=bound['carried_cost_usd'], total_cost_usd=summary['budget']['reported_cost_usd'],
        total_budget_usd=bound['total_budget_usd'], execution_history=platform['execution_history'],
        wall_seconds_basis=summary['wall_seconds_basis'], recovery_worker_seconds=summary['recovery_worker_seconds'],
        private_source_file_sha256=bound['source_file_sha256'],
        delivery_sha256={n: runtime.sha(destination / n) for n in ('results.csv', 'receipt.json', 'platform_receipt.json')})
    durable(destination / 'recovery_receipt.json', proof)
    with (destination / 'ENVIRONMENT.md').open('a', encoding='utf-8') as stream:
        stream.write('\n## Recovery provenance\n\n'
            '- Original 18 records were retained byte-for-byte as parsed rows; 318 previously uncalled cases ran in a separate attempt.\n'
            '- Recovery entrypoint: tasks/03/resume.py; hash and both attempt records are in recovery_receipt.json.\n'
            '- Cumulative formal budget remains $2, including the prior $0.03507135; no automatic retries.\n'
            '- receipt.wall_seconds is the sum of case seconds across attempts, excluding startup and the overnight pause. It is not full uninterrupted worker wall time.\n'
            '- Required additional review: python tasks/03/resume.py audit --destination <folder> --approved-code-sha <reviewed SHA256>.\n'
            '- The base local delivery audit alone does not establish acceptance of this recovery entrypoint. Vanda/team acceptance remains pending.\n')
    audit(plan, destination, runtime.sha(__file__))
    return result


def audit(plan, destination, approved_code_sha):
    proof, platform = read(destination / 'recovery_receipt.json'), read(destination / 'platform_receipt.json')
    if proof['recovery_entrypoint_sha256'] != approved_code_sha:
        raise ValueError('Unreviewed recovery code')
    delivery.validate(plan, destination, runtime.adapter_hashes())
    if proof['plan_sha256'] != plan['plan_sha256'] or proof['execution_history'] != platform['execution_history']:
        raise ValueError('Recovery provenance mismatch')
    for name, expected in proof['delivery_sha256'].items():
        if runtime.sha(destination / name) != expected:
            raise ValueError('Recovery delivery changed')
    ids = [c['case_id'] for c in plan['shards'][2]['cases']]
    if proof['preserved_case_ids'] + proof['new_case_ids'] != ids:
        raise ValueError('Recovery coverage changed')
    with (destination / 'results.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    count = proof['preserved_records']
    if count != len(proof['preserved_case_ids']) or proof['new_records'] != 336-count:
        raise ValueError('Recovery count mismatch')
    if [r['case_id'] for r in rows] != ids or abs(sum(float(r['cost_usd']) for r in rows[:count])-proof['carried_cost_usd']) > 1e-9:
        raise ValueError('Preserved delivery rows/cost mismatch')
    receipt = read(destination / 'receipt.json')
    if proof['total_budget_usd'] != 2 or proof['total_cost_usd'] != receipt['budget']['reported_cost_usd']:
        raise ValueError('Recovery budget mismatch')
    return dict(passed=True, recorded=336, recovery_provenance_checked=True, team_acceptance=False)


def main():
    global STOP, STATUS_PATH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'check', 'execute', 'export', 'audit'))
    parser.add_argument('--plan', type=Path, default=ROOT / 'assignments/formal/plan.json')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--attempt-id', default='formal-v1-001-resume-01')
    parser.add_argument('--bound', type=Path, default=ROOT / 'runs/plans/formal-v1-001-resume-01.json')
    parser.add_argument('--detector-dir', type=Path, default=ROOT / 'models/prompt_injection_detector')
    parser.add_argument('--worker-dir', type=Path)
    parser.add_argument('--destination', type=Path, default=ROOT / 'experiments/deliveries/person-03')
    parser.add_argument('--approved-code-sha')
    parser.add_argument('--status-file', type=Path, help='Optional sanitized progress mirror for local monitoring')
    parser.add_argument('--allow-recorded-timeout', action='store_true',
        help='Explicit authorization to retain recorded timeouts and carry their uncertain reservations; never retry them')
    args = parser.parse_args()
    STATUS_PATH = args.status_file
    plan = read_plan(args.plan)
    if args.command == 'audit':
        print(json.dumps(audit(plan, args.destination, args.approved_code_sha)))
        return
    if args.command == 'export':
        print(json.dumps(export(args.plan, args.worker_dir, args.destination)))
        return
    runtime.verify(args.plan, args.detector_dir)
    if args.command == 'prepare':
        if args.source is None:
            parser.error('--source is required')
        bound = build_bound(plan, args.source, args.attempt_id,
                            allow_recorded_timeout=args.allow_recorded_timeout)
        args.bound.parent.mkdir(parents=True, exist_ok=True)
        with args.bound.open('x', encoding='utf-8') as stream:
            json.dump(bound, stream, indent=2)
        print(json.dumps(dict(prepared=True, remaining=len(bound['remaining_case_ids']),
            carried_cost_usd=bound['carried_cost_usd'], remaining_budget_usd=bound['remaining_budget_usd'],
            max_new_model_calls=bound['max_new_model_calls'], recovery_sha256=bound['recovery_sha256'])))
        return
    bound = read(args.bound)
    verify_bound(plan, bound)
    if args.command == 'check':
        print(json.dumps(dict(passed=True, remaining=len(bound['remaining_case_ids']), paid_calls=0)))
        return
    from api_check import probe
    from trustgate.runner import get_key
    key = get_key()
    metadata = probe(key)
    if not metadata['key_cap_covers_two_dollars']:
        raise RuntimeError('Shared key cap below $2; review available funds before running')
    print(json.dumps(metadata), flush=True)
    from agentdojo.task_suite.load_suites import get_suite
    sys.path.insert(0, str(ROOT / 'experiments/mvp'))
    from detector import Detector
    def stop_after_case(signum, frame):
        global STOP
        STOP = True
    signal.signal(signal.SIGTERM, stop_after_case)
    signal.signal(signal.SIGINT, stop_after_case)
    folder = asyncio.run(execute(plan, bound, ROOT / 'runs/recoveries', key,
        local_run.experiment_class(), get_suite(plan['config']['benchmark'], plan['config']['suite']),
        Detector(args.detector_dir, plan['config']['classifier_threshold'])))
    summary = read(folder / 'worker_summary.json')
    if summary['complete'] and not summary['cost_reconciled']:
        print(json.dumps(dict(data_collection_complete=True, recorded=336, delivery_ready=False,
            uncertain_reserved_usd=summary['budget']['uncertain_reserved_usd'],
            action='Reconcile the retained timeout charge before final export/merge; no automatic retry.')), flush=True)
    elif summary['complete']:
        print(json.dumps(export(args.plan, folder, args.destination)), flush=True)
        import subprocess
        subprocess.run([sys.executable, str(ROOT / 'tasks/03/analyze_delivery.py')], check=True)
    else:
        print(json.dumps(dict(paused=True, folder=str(folder))), flush=True)


if __name__ == '__main__':
    main()
