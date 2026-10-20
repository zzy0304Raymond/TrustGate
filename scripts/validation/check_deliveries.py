"""Validate the five experiment datasets, including provenance and costs."""
import ast
import csv
import hashlib
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from trustgate.planning import read_plan
from trustgate.formal_manifest import source_hashes
from trustgate.runner import require_compute


def main():
    require_compute()
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    assert source_hashes() == plan['source_sha256']
    fields = next(ast.literal_eval(n.value) for n in ast.parse(
        (ROOT / 'trustgate/delivery.py').read_text()).body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'PUBLIC_FIELDS' for t in n.targets))
    checks, all_ids = [], []
    for person in range(1, 6):
        folder = ROOT / f'experiments/deliveries/person-{person:02d}'
        receipt = json.loads((folder / 'receipt.json').read_text())
        with (folder / 'results.csv').open(newline='') as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == [*fields, 'error_type']
            rows = list(reader)
        cases = plan['shards'][person - 1]['cases']
        assert len(rows) == 336 and receipt['recorded'] == 336 and receipt['complete'] is True
        assert receipt['person'] == person and receipt['shard_index'] == person - 1
        assert receipt['plan_sha256'] == plan['plan_sha256']
        assert receipt['source_sha256'] == plan['source_sha256']
        assert (folder / 'ENVIRONMENT.md').is_file()
        ids = [r['case_id'] for r in rows]
        assert ids == [c['case_id'] for c in cases] and len(set(ids)) == 336
        all_ids.extend(ids)
        for row, case in zip(rows, cases):
            for key in ('slot_id', 'task', 'workflow', 'surface', 'condition',
                        'repeat', 'transport', 'attack_case_id', 'split'):
                assert row[key] == ('' if case.get(key) is None else str(case[key]))
            for key in ('seconds', 'api_calls', 'api_seconds', 'cost_usd',
                        'prompt_tokens', 'completion_tokens', 'tool_calls'):
                value = float(row[key])
                assert math.isfinite(value) and value >= 0
            assert int(row['api_calls']) <= plan['config']['max_model_calls']
            for key in ('native_utility', 'attacker_success', 'safe_completion'):
                assert row[key] in ('True', 'False', '')
        assert Counter(r['surface'] for r in rows) == dict(benign=84, output=126, metadata=126)
        assert set(Counter(r['condition'] for r in rows).values()) == {48}
        expected_packages = dict(plan['packages'])
        if person == 2:
            expected_packages['torch'] = '2.7.1'  # Disclosed Mac CPU build exception.
        assert set(receipt['packages']) >= {'agentdojo', 'mcp', 'transformers', 'torch'}
        assert all(v == expected_packages[k] for k, v in receipt['packages'].items())
        total = sum((Decimal(row['cost_usd']) for row in rows), Decimal(0))
        budget = receipt['budget']
        assert abs(total - Decimal(str(budget['reported_cost_usd']))) < Decimal('0.000000001')
        assert budget['limit_usd'] == 2 and budget['pending_reserved_usd'] == 0
        assert budget['uncertain_reserved_usd'] == 0 and budget['halted'] is False
        assert 0 <= total < 2
        checks.append(dict(person=person, recorded=336, passed=True,
            statuses=dict(Counter(r['status'] for r in rows)),
            errors=dict(Counter(r['error_type'] for r in rows if r['error_type'])),
            reported_cost_usd=str(total.quantize(Decimal('0.00000001'))),
            delivery_sha256={p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(folder.rglob('*')) if p.is_file()}))
    assert len(all_ids) == len(set(all_ids)) == plan['planned_cases'] == 1680
    cost = sum(Decimal(row['reported_cost_usd']) for row in checks)
    result = dict(passed=True, recorded=1680, unique_ids=1680, missing=0,
        plan_sha256=plan['plan_sha256'], people=checks, reported_formal_cost_usd=str(cost),
        invoice_reconciliation_complete=False,
        retained_accounting_exception='Person 3 has one timed-out request without a returned charge. '
            'The historical $0.05 reservation was released for submission, not proven to be zero actual cost.',
        platform_exception='Person 2 ran CPU Torch 2.7.1 on Mac; other recorded critical versions match the plan.',
        timing_exceptions=['Person 2 trial 151 reconstructs pre-pause API time from file timestamps.',
                           'Person 3 wall_seconds sums case durations; do not compare it directly to full worker wall time.'])
    output = ROOT / 'runs/validation/delivery-checks.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': True, 'recorded': 1680, 'reported_cost_usd': str(cost)}))


if __name__ == '__main__':
    main()
