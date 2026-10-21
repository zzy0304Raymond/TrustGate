"""Check the published supplement without API access or private trajectories."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/metadata_supplement'
PLANS = ROOT / 'assignments/metadata_supplement'
CONDITIONS = {'none', 'delimiters', 'classifier', 'trustgate', 'no_provenance', 'no_metadata', 'no_authorization'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def truth(value):
    assert value in ('True', 'False', '')
    return None if value == '' else value == 'True'


def verify():
    summary = read(OUT / 'summary.json')
    total = 0
    for stage in ('development', 'evaluation'):
        plan = read(PLANS / (stage + '.json'))
        assert plan['plan_sha256'] == digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
        for name, expected in plan['supplement_source_sha256'].items():
            assert sha(ROOT / name) == expected
        check = read(OUT / (stage + '_checks.json'))
        assert check['passed'] and check['new_api_requests'] == 0
        assert check['plan_sha256'] == plan['plan_sha256']
        assert check['analysis_sha256'] == sha(ROOT / 'scripts/supplement/analyze.py')
        with (OUT / (stage + '_trials.csv')).open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        ids = {c['case_id'] for c in plan['cases']}
        assert len(rows) == len(ids) == plan['planned_cases']
        assert {r['case_id'] for r in rows} == {r['case_id'] for r in check['records']} == ids
        matrix = Counter((r['task'], r['family'], r['condition'], int(r['repeat'])) for r in rows)
        tasks = set(plan['config']['formal_tasks'])
        families = {a['template_family'] for a in plan['config']['formal_attacks'].values()}
        conditions = {'none'} if stage == 'development' else CONDITIONS
        repeats = [1] if stage == 'development' else [1, 2, 3]
        expected = Counter((task, family, condition, repeat) for task in tasks for family in families
                           for condition in conditions for repeat in repeats)
        if stage == 'evaluation':
            expected.update((task, 'clean', condition, repeat) for task in tasks
                            for condition in ('none', 'trustgate') for repeat in repeats)
        assert matrix == expected
        by_id = {r['case_id']: r for r in rows}
        for rec in check['records']:
            row = by_id[rec['case_id']]
            assert rec['state_roundtrip_exact'] and rec['request_response_trajectory_match']
            assert rec['recomputed_attacker_success'] == truth(row['attacker_success'])
            assert len(rec['full_payload_request_steps']) == int(row['full_payload_requests'])
            for field in ('full_payload_request_steps', 'goal_tool_available_request_steps'):
                steps = rec[field]
                assert steps == sorted(set(steps)) and set(steps) <= set(range(1, int(row['request_attempts']) + 1))
            assert len(rec['unreturned_request_steps']) == int(row['unreturned_requests'])
            assert rec['valid_for_comparison'] == truth(row['valid_for_comparison'])
            assert int(row['request_attempts']) == int(row['api_calls']) + int(row['unreturned_requests'])
            assert len(rec['normal_metadata_quarantines']) == int(row['benign_metadata_quarantines'])
            assert len(rec['output_classifier_blocked_tools']) == int(row['output_classifier_blocks'])
            assert len(rec['proposed_tool_names']) == int(row['tool_calls']) + int(row['pending_proposals'])
            for kind in ('request', 'response'):
                for step in range(1, int(row['api_calls']) + 1):
                    assert f'{kind}_{step:02}.json' in rec['source_files']
            for value in rec['source_files'].values():
                assert len(value) == 64 and all(c in '0123456789abcdef' for c in value)
        controls = read(PLANS / (stage + '_controls.json'))
        assert controls['passed'] and controls['api_requests'] == 0 and controls['plan_sha256'] == plan['plan_sha256']
        assert {r['attack_case_id'] for r in controls['records']} == set(plan['config']['formal_attacks'])
        assert all(r['mcp_positive_control'] and r['permission_denies_goal'] and not r['negative_control'] for r in controls['records'])
        worker = next(s for s in summary['stages'] if s['stage'] == stage)
        assert worker['complete'] and worker['recorded'] == len(rows)
        assert math.isclose(sum(float(r['cost_usd']) for r in rows), worker['budget']['reported_cost_usd'], abs_tol=1e-9)
        assert sum(int(r['request_attempts']) for r in rows) == worker['attempted_requests']
        assert sum(not truth(r['valid_for_comparison']) for r in rows) == worker['infrastructure_errors']
        groups = summary['development'] if stage == 'development' else summary['evaluation']
        for name, group in groups.items():
            selected = [r for r in rows if r['family'] == name] if stage == 'development' else [r for r in rows if r['surface'] == 'metadata' and r['condition'] == name]
            assert len(selected) == group['trials']
            valid = [r for r in selected if truth(r['valid_for_comparison'])]
            assert len(valid) == group['valid_trials']
            assert sum(truth(r['attacker_success']) is True for r in valid) == group['exact_attack_successes']
            assert sum(truth(r['native_utility']) is True for r in valid) == group['utility_successes']
            assert Counter(r['status'] for r in selected) == group['statuses']
        if stage == 'evaluation':
            for condition, group in summary['clean'].items():
                clean = [r for r in rows if r['surface'] == 'benign' and r['condition'] == condition]
                assert len(clean) == group['trials'] == 9
                assert sum(truth(r['native_utility']) is True for r in clean) == group['utility_successes']
        total += len(rows)
    original = read(ROOT / 'assignments/formal/plan.json')
    for name, expected in original['source_sha256'].items():
        assert sha(ROOT / name) == expected
    dev = read(PLANS / 'development.json')
    evaluation = read(PLANS / 'evaluation.json')
    for plan in (dev, evaluation):
        assert plan['original_formal_plan_sha256'] == original['plan_sha256']
        for key, value in original['config'].items():
            if key not in {'formal_tasks', 'formal_attacks', 'max_total_cost_usd'}:
                assert plan['config'][key] == value, key
    assert not set(evaluation['config']['formal_tasks']) & (set(dev['config']['formal_tasks']) | set(original['config']['formal_tasks']))
    selected = evaluation['selection']
    assert selected['development_plan_sha256'] == dev['plan_sha256']
    assert selected['selected'] == ['tool_contract', 'worked_call_sequence']
    assert total == 156
    continuation = read(PLANS / 'continuation-01.json')
    assert continuation['continuation_sha256'] == digest({k: v for k, v in continuation.items() if k != 'continuation_sha256'})
    assert continuation['source_sha256'] == sha(ROOT / 'scripts/supplement/continue_remaining.py')
    assert continuation['cases'] == evaluation['cases'][128:]
    assert continuation['preserved_failure_case_id'] == evaluation['cases'][127]['case_id']
    assert continuation['budget_usd'] <= continuation['original_budget_remaining_after_reservation']
    with (OUT / 'evaluation_trials.csv').open(newline='') as stream:
        failed = [r for r in csv.DictReader(stream) if not truth(r['valid_for_comparison'])]
    assert len(failed) == 1 and failed[0]['case_id'] == continuation['preserved_failure_case_id']
    assert failed[0]['error_type'] == 'TimeoutError' and failed[0]['unreturned_requests'] == '1'
    audit = read(OUT / 'posthoc_calendar_summary.json')
    assert audit['posthoc'] and audit['primary_scores_unchanged'] and audit['new_api_requests'] == 0
    assert audit['audit_source_sha256'] == sha(ROOT / 'scripts/supplement/audit_calendar.py')
    with (OUT / 'posthoc_calendar_audit.csv').open(newline='') as stream:
        calendar = list(csv.DictReader(stream))
    assert len(calendar) == len({r['case_id'] for r in calendar}) == audit['cases'] == 48
    assert set(audit['confirmed_cases']) == {r['case_id'] for r in calendar if truth(r['native_pass_with_confirmed_conflict'])}
    manifest_path = OUT / 'manifest.json'
    if manifest_path.exists():
        manifest = read(manifest_path)
        for name, expected in manifest['files_sha256'].items():
            assert sha(ROOT / name) == expected, name
    print(json.dumps(dict(passed=True, verified_trials=total, original_runtime_unchanged=True,
                          complete_development_and_evaluation=True, new_api_requests=0)))


if __name__ == '__main__':
    verify()
