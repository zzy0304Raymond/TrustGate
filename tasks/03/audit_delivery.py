"""Audit person-03 measurements and owner-approved approximate cost reporting."""
import argparse
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/platforms/local'))
import runtime
from trustgate.planning import read_plan
from trustgate.delivery import PUBLIC_FIELDS

CASE = '9f7467fd5e9ede0aa172'
REQUEST_SHA = 'f0c204640256d9de138d5b529b746f845b67ee84c8c06f3ec2f98116440617a8'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def audit(folder, accept_estimated_costs=False):
    folder = Path(folder)
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    receipt, platform = read(folder / 'receipt.json'), read(folder / 'platform_receipt.json')
    cost, history = read(folder / 'ACCOUNTING.json'), read(folder / 'recovery_receipt.json')
    if not accept_estimated_costs:
        raise ValueError('Explicit acceptance of approximate cost reporting is required')
    if cost['status'] != 'finalized_with_owner_approved_estimate' or cost['estimates_are_provider_invoices'] is not False:
        raise ValueError('Approximate costs must not be presented as provider invoices')
    if cost['authorized_by'] != 'project_owner_in_this_chat' or cost['scope'] != 'one_retained_historical_timeout_only':
        raise ValueError('Missing bounded owner authorization')
    if cost['case_id'] != CASE or cost['request_sha256'] != REQUEST_SHA or cost['released_client_reservation_usd'] != .05:
        raise ValueError('Cost exception does not match the single authorized request')
    if receipt['plan_sha256'] != plan['plan_sha256'] or receipt['source_sha256'] != plan['source_sha256']:
        raise ValueError('Frozen plan/source mismatch')
    if receipt['person'] != 3 or receipt['shard_index'] != 2 or receipt['recorded'] != 336 or receipt['complete'] is not True:
        raise ValueError('Wrong or incomplete shard')
    if receipt['packages'] != plan['packages'] or platform['packages'] != plan['packages'] or platform['detector_sha256'] != plan['detector_sha256']:
        raise ValueError('Package/detector identity mismatch')
    if platform['system'] != 'Linux' or platform['python'] != '3.10.20' or platform['pbs_job_id'] is not None:
        raise ValueError('Unexpected platform provenance')
    if platform['adapter_sha256'] != runtime.adapter_hashes():
        raise ValueError('Local adapter differs from delivered provenance')
    if platform['plan_sha256'] != plan['plan_sha256'] or platform['shard_index'] != 2:
        raise ValueError('Platform plan/shard mismatch')
    runtime.source_check(plan)
    budget = receipt['budget']
    if budget['limit_usd'] != 2 or budget['pending_reserved_usd'] != 0 or budget['halted'] is not False:
        raise ValueError('Budget limit, in-flight state or halt mismatch')
    if budget['uncertain_reserved_usd'] != 0 or cost['reported_formal_cost_usd'] != budget['reported_cost_usd']:
        raise ValueError('Final accounting differs from reported row costs/approved reserve closure')
    if cost['raw_execution_budget']['uncertain_reserved_usd'] != .05 or cost['raw_execution_budget']['reported_cost_usd'] != budget['reported_cost_usd']:
        raise ValueError('Original execution accounting must remain preserved')
    if cost['formal_cost_rounded_usd'] != .51 or cost['formal_and_probe_cost_rounded_usd'] != .52:
        raise ValueError('Unexpected rounded cost reporting')
    if not math.isfinite(budget['reported_cost_usd']) or budget['reported_cost_usd'] < 0 or budget['reported_cost_usd'] + cost['released_client_reservation_usd'] > 2:
        raise ValueError('Invalid or exceeded cumulative allocation')
    with (folder / 'results.csv').open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != [*PUBLIC_FIELDS, 'error_type']:
            raise ValueError('Public CSV schema changed')
        rows = list(reader)
    cases = plan['shards'][2]['cases']
    if len(rows) != 336 or [r['case_id'] for r in rows] != [c['case_id'] for c in cases]:
        raise ValueError('Missing, duplicate, foreign or reordered trial')
    for row, case in zip(rows, cases):
        for name in ('workflow', 'task', 'surface', 'condition', 'repeat', 'transport', 'slot_id', 'attack_case_id', 'split'):
            if row[name] != ('' if case.get(name) is None else str(case[name])):
                raise ValueError('Trial identity mismatch')
    row_costs = [float(r['cost_usd']) for r in rows]
    if any(not math.isfinite(x) or x < 0 for x in row_costs) or abs(sum(row_costs)-budget['reported_cost_usd']) > 1e-9:
        raise ValueError('CSV/ledger cost mismatch')
    errors = [r for r in rows if r['error_type']]
    if len(errors) != 1 or errors[0]['case_id'] != CASE or errors[0]['error_type'] != 'TimeoutError':
        raise ValueError('Original TimeoutError must be retained; no new errors are waived')
    for name, expected in history['delivery_sha256'].items():
        if runtime.sha(folder / name) != expected:
            raise ValueError('Delivery bytes changed: ' + name)
    for name, expected in platform['delivery_sha256'].items():
        if runtime.sha(folder / name) != expected:
            raise ValueError('Platform-bound delivery bytes changed')
    if history['execution_history'] != platform['execution_history'] or history['recovery_entrypoint_sha256'] != runtime.sha(ROOT / 'tasks/03/resume.py'):
        raise ValueError('Recovery provenance changed')
    if history['plan_sha256'] != plan['plan_sha256']:
        raise ValueError('Recovery plan mismatch')
    cursor = 1
    for attempt in history['execution_history']:
        if attempt['start_index'] != cursor or attempt['end_index'] < cursor:
            raise ValueError('Attempt boundaries overlap or omit cases')
        cursor = attempt['end_index'] + 1
    if cursor != 337 or not (folder / 'ENVIRONMENT.md').exists():
        raise ValueError('Incomplete history/environment')
    return dict(passed=True, recorded=336, retained_timeout=True, approximate_costs_explicitly_accepted=True,
                accounting_finalized=True, reported_cost_usd=budget['reported_cost_usd'],
                formal_cost_rounded_usd=.51, total_with_probe_rounded_usd=.52,
                ready_for_team_review=True, team_vanda_acceptance=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery', type=Path, default=ROOT / 'experiments/deliveries/person-03')
    parser.add_argument('--accept-estimated-costs', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.delivery, args.accept_estimated_costs), indent=2))
