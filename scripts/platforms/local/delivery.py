"""Extra delivery checks and provenance, compatible with the original CSV/receipt."""
import argparse
import csv
import json
import math
from pathlib import Path
from runtime import ROOT, adapter_hashes, sha, write_json
from trustgate.planning import read_plan

IDENTITY = ('workflow', 'task', 'surface', 'condition', 'repeat', 'transport',
            'slot_id', 'attack_case_id', 'split')


def validate(plan, folder, approved_adapter=None):
    folder = Path(folder)
    receipt = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
    index = receipt['shard_index']
    if type(index) is not int or not 0 <= index < plan['workers']:
        raise ValueError('Invalid shard index')
    shard = plan['shards'][index]
    if receipt['plan_sha256'] != plan['plan_sha256'] or receipt['source_sha256'] != plan['source_sha256']:
        raise ValueError('Frozen version mismatch')
    if receipt.get('complete') is not True or receipt.get('recorded') != len(shard['cases']):
        raise ValueError('Incomplete delivery')
    if receipt.get('person') != index + 1:
        raise ValueError('Person/shard mismatch')
    # Legacy PBS receipts recorded four packages. New local receipts record all six.
    for name in ('agentdojo', 'mcp', 'transformers', 'torch'):
        if receipt.get('packages', {}).get(name) != plan['packages'][name]:
            raise ValueError('Package mismatch: ' + name)
    for name, version in receipt.get('packages', {}).items():
        if name in plan['packages'] and version != plan['packages'][name]:
            raise ValueError('Package mismatch: ' + name)
    budget = receipt.get('budget', {})
    if budget.get('limit_usd') != shard['budget_usd'] or budget.get('halted') is not False:
        raise ValueError('Budget limit/state mismatch')
    for key in ('uncertain_reserved_usd', 'pending_reserved_usd'):
        if budget.get(key) != 0:
            raise ValueError('Unresolved API charge')
    cost = budget.get('reported_cost_usd')
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or not 0 <= cost <= shard['budget_usd']:
        raise ValueError('Invalid reported cost')
    with (folder / 'results.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    expected = {c['case_id']: c for c in shard['cases']}
    if len(rows) != len(expected) or {r['case_id'] for r in rows} != set(expected):
        raise ValueError('Missing, duplicate, or incorrectly assigned trial')
    for row in rows:
        for field in IDENTITY:
            target = expected[row['case_id']].get(field)
            if row.get(field) != ('' if target is None else str(target)):
                raise ValueError('Trial identity mismatch: ' + field)
    row_costs = [float(r['cost_usd']) for r in rows]
    if any(not math.isfinite(v) or v < 0 for v in row_costs) or abs(sum(row_costs) - cost) > 1e-9:
        raise ValueError('Row costs differ from budget ledger')
    if not (folder / 'ENVIRONMENT.md').is_file():
        raise ValueError('ENVIRONMENT.md is required')
    provenance_path = folder / 'platform_receipt.json'
    backend = 'legacy-pbs-receipt'
    if provenance_path.exists():
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        backend = provenance['execution_backend']
        if backend != 'local-linux-v1' or approved_adapter is None:
            raise ValueError('Local adapter needs an explicitly reviewed adapter-hash JSON file')
        if provenance['adapter_sha256'] != approved_adapter:
            raise ValueError('Unapproved local adapter version')
        if provenance['plan_sha256'] != plan['plan_sha256'] or provenance['shard_index'] != index:
            raise ValueError('Platform provenance identity mismatch')
        if provenance['packages'] != plan['packages'] or provenance['detector_sha256'] != plan['detector_sha256']:
            raise ValueError('Platform model/package mismatch')
        if provenance['system'] != 'Linux' or provenance['python'] != '3.10.20' or provenance['pbs_job_id'] is not None:
            raise ValueError('Invalid local platform provenance')
        for name in ('results.csv', 'receipt.json'):
            if provenance['delivery_sha256'][name] != sha(folder / name):
                raise ValueError('Delivery bytes changed after export')
    # A missing sidecar cannot prove that a legacy receipt was produced on PBS.
    return dict(shard_index=index, recorded=len(rows), checked=True, execution_backend=backend,
                note='Legacy platform origin still requires human ENVIRONMENT.md/private-manifest review.')


def export_local(plan_path, worker_dir, destination):
    from trustgate.delivery import export_delivery
    plan = read_plan(plan_path)
    worker_dir, destination = Path(worker_dir), Path(destination)
    manifest = json.loads((worker_dir / 'manifest.json').read_text(encoding='utf-8'))
    provenance = manifest['platform']
    if manifest['shard_index'] != 2 or provenance['execution_backend'] != 'local-linux-v1':
        raise ValueError('Expected person-3 local execution')
    if provenance['adapter_sha256'] != adapter_hashes():
        raise ValueError('Adapter changed since execution; export using the recorded adapter version')
    if destination.exists() and any((destination / name).exists() for name in ('results.csv', 'receipt.json', 'platform_receipt.json')):
        raise FileExistsError('Refusing to overwrite a delivery')
    result = export_delivery(plan_path, worker_dir, destination)
    # csv.writer emits CRLF even on Linux; Git forces results.csv to LF.
    # Canonicalize only line endings before binding bytes so a Git round trip
    # does not invalidate otherwise unchanged public measurements.
    for name in ('results.csv', 'receipt.json'):
        path = destination / name
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
    write_json(destination / 'platform_receipt.json', dict(provenance,
        plan_sha256=plan['plan_sha256'], shard_index=2,
        delivery_sha256={name: sha(destination / name) for name in ('results.csv', 'receipt.json')}))
    environment_path = destination / 'ENVIRONMENT.md'
    if not environment_path.exists():
        summary = json.loads((worker_dir / 'worker_summary.json').read_text(encoding='utf-8'))
        document = '\n'.join([
            '# Person 03 actual runtime environment', '',
            '- Platform: Linux / local adapter (WSL when kernel release contains microsoft).',
            '- Kernel: ' + provenance.get('release', 'not recorded'),
            '- Python: ' + provenance['python'],
            '- Git base commit: ' + provenance.get('git_commit', 'not recorded'),
            '- Extra executable adapter: see adapter_sha256 in platform_receipt.json.',
            '- Frozen plan SHA256: ' + plan['plan_sha256'],
            '- Run ID: ' + manifest['run_id'],
            '- Shard/person: 2 / 3; expected trials: 336.',
            '- Scheduler: none; PBS_JOBID was not set or fabricated.',
            '- Detector inference: CPU; no GPU requested by the experiment.',
            '- Hardware: ' + json.dumps(provenance.get('hardware', {}), sort_keys=True),
            '- Thread settings: ' + json.dumps(provenance.get('thread_environment', {}), sort_keys=True),
            '- Packages: ' + json.dumps(provenance['packages'], sort_keys=True),
            '- Launch: python scripts/platforms/local/run.py --execute --detector-dir <pinned-cache> --run-id <above-run-id>',
            '- Completion: ' + str(summary['complete']) + '; recorded: ' + str(summary['recorded']),
            '- Budget ledger: ' + json.dumps(summary['budget'], sort_keys=True),
            '- Environment, frozen source/package/model verification runs before API access.',
            '- Offline verification reports: runs/local-offline/ (private; retain for review).',
            '- Vanda validation: NOT performed by this adapter. Team acceptance remains separate.',
            '- Full traces, credentials and simulated backend state remain private.', '',
        ])
        environment_path.write_text(document, encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=ROOT / 'assignments/formal/plan.json')
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export')
    export.add_argument('--worker-dir', type=Path, required=True)
    export.add_argument('--destination', type=Path, required=True)
    audit = sub.add_parser('audit')
    audit.add_argument('--deliveries', type=Path, required=True)
    audit.add_argument('--approved-adapter', type=Path)
    audit.add_argument('--require-complete', action='store_true', help='Reject until all five shards are present')
    args = parser.parse_args()
    if args.command == 'export':
        result = export_local(args.plan, args.worker_dir, args.destination)
    else:
        plan = read_plan(args.plan)
        approved = json.loads(args.approved_adapter.read_text(encoding='utf-8')) if args.approved_adapter else None
        folders = [p for p in sorted(args.deliveries.glob('person-*')) if (p / 'receipt.json').exists()]
        if not folders:
            raise ValueError('No deliveries found')
        checks = [validate(plan, p, approved) for p in folders]
        indices = [c['shard_index'] for c in checks]
        if len(set(indices)) != len(indices):
            raise ValueError('Duplicate shard receipts')
        result = dict(checked=checks, complete=set(indices) == set(range(plan['workers'])))
        if args.require_complete and not result['complete']:
            raise ValueError('All five reviewed deliveries are required before final aggregation')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
