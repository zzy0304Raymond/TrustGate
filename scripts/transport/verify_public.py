"""Dependency-free verification and paired summaries for the transport study."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[2]))
from release_integrity import recorded_digest
import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/transport_validation'


def read(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def sha(path):
    return recorded_digest(hashlib.sha256(Path(path).read_bytes()).hexdigest())


def verify():
    plan = read(ROOT / 'assignments/transport_validation/plan.json')
    assert plan['plan_sha256'] == digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
    formal = read(ROOT / 'assignments/formal/plan.json')
    assert plan['original_plan_sha256'] == formal['plan_sha256']
    assert set(c['condition'] for c in plan['cases']) == {'none'}
    assert len({c['workflow'][:2] for c in plan['cases']}) == 6
    for path, expected in plan['source_sha256'].items():
        assert sha(ROOT / path) == expected, path
    for path, expected in read(OUT / 'manifest.json')['files_sha256'].items():
        assert sha(ROOT / path) == expected, path
    rows = list(csv.DictReader((OUT / 'trials.csv').open()))
    assert len(rows) == len({r['case_id'] for r in rows}) == 48
    assert [r['case_id'] for r in rows] == [r['case_id'] for r in plan['cases']]
    for row, case in zip(rows, plan['cases']):
        assert case['case_id'] == digest({k: v for k, v in case.items() if k != 'case_id'})[:20]
        for key in ['task', 'workflow', 'surface', 'attack_case_id', 'repeat', 'transport']:
            assert row[key] == ('' if case[key] is None else str(case[key])), key
        for field in ['native_utility', 'attacker_success', 'safe_completion', 'injection_reached_model']:
            row[field] = {'True': True, 'False': False, '': None}[row[field]]
        for field in ['seconds', 'api_seconds', 'cost_usd', 'api_calls', 'prompt_tokens', 'completion_tokens']:
            row[field] = float(row[field])
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
    summary = read(OUT / 'summary.json')
    assert summary['groups'] == groups
    assert summary['worker']['complete'] and summary['worker']['recorded'] == 48
    assert math.isclose(sum(r['cost_usd'] for r in rows), summary['worker']['budget']['reported_cost_usd'], abs_tol=1e-9)
    checks = read(OUT / 'checks.json')
    assert checks['passed'] and checks['controls']['passed'] and checks['controls']['model_requests'] == 0
    assert len(checks['controls']['records']) == 8
    assert {r['case_id'] for r in checks['records']} == {r['case_id'] for r in rows}
    assert all(r['request_response_count_matches'] and r['initial_state_matches'] for r in checks['records'])
    for rec in checks['records']:
        assert all(len(h) == 64 and set(h) <= set('0123456789abcdef') for h in rec['source_files'].values())
    indexed = {(r['task'], r['surface'], r['repeat'], r['transport']): r for r in rows}
    pairs = []
    for (task, surface, repeat, transport), local in indexed.items():
        if transport != 'local':
            continue
        mcp = indexed[(task, surface, repeat, 'mcp')]
        pairs.append(dict(task=task, surface=surface, repeat=repeat,
            local_case_id=local['case_id'], mcp_case_id=mcp['case_id'],
            native_outcome_agrees=local['native_utility'] == mcp['native_utility'],
            attack_outcome_agrees=local['attacker_success'] == mcp['attacker_success'] if surface == 'output' else None,
            exposure_agrees=local['injection_reached_model'] == mcp['injection_reached_model'],
            mcp_minus_local_seconds=mcp['seconds'] - local['seconds']))
    assert len(pairs) == 24
    return groups, pairs, summary


def write():
    groups, pairs, summary = verify()
    with (OUT / 'pairs.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    lines = ['# Local tools compared with MCP', '',
        '48 real model validations under fixed checklist completed independently from original 1,680 formal studies. Six categories of normal tasks 36 items, two existing output attacks 12 items; local and MCP use same model, tools, payload, initial state and budget, three trials per cell.', '',
        '| Scenario | entry point | Valid/Preset | Native task success | Attack succeeds | Attack exposure | Average seconds |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in groups:
        attack = '—' if r['attack_successes'] is None else f"{r['attack_successes']}/{r['valid']}"
        exposure = '—' if r['surface'] == 'benign' else f"{r['exposed']}/{r['recorded']}"
        lines.append(f"| {r['surface']} | {r['transport']} | {r['valid']}/{r['recorded']} | "
                     f"{r['native_successes']}/{r['valid']} | {attack} | {exposure} | {r['mean_seconds']:.2f} |")
    agreement = sum(p['native_outcome_agrees'] for p in pairs)
    attack_pairs = [p for p in pairs if p['surface'] == 'output']
    lines += ['', f"24 paired sets with consistent native task outcomes {agreement}/24; output attack outcomes were consistent "
              f"{sum(p['attack_outcome_agrees'] for p in attack_pairs)}/{len(attack_pairs)}.Pairwise IDs and differences are listed `pairs.csv`.", '',
              'Eight preset response checks passed: local/MCP tool definitions, model-visible trajectories, read results, payload injection, and pre/post states fully consistent. This validates adaptation implementation; outcome comparisons of real models reflect this batch sample and do not imply statistical equivalence.', '',
              'This batch is entirely unshielded and adapted for isolated transmission. The original input injection is achieved through an independent thin adapter to achieve the same one-append behavior as MCP; the official executor and 1,680 scores remain unchanged. Preset reply checks are not included in the above 48 real model trials.', '',
              'This batch’s backup official task and existing attacks are post-adaptation diagnostic checks, not new generalization tests. A model temperature of zero does not guarantee identical responses; adjacent pairs and random intra-order cannot fully eliminate service fluctuations. Duration includes tool selection path and remote response time and cannot be considered pure MCP protocol overhead.', '',
              f"Number of requests attempted in this batch {summary['worker']['attempted_requests']}; Valid records and actual runtime are listed `summary.json`. All failures are retained.", '',
              '## Reproduction', '',
              '- Unmodelled requests:`python scripts/transport/verify_public.py` Verification checklist completeness metrics and sources.',
              '- Real MCP adaptation check: run on PBS compute nodes `python scripts/transport/study.py controls --controls runs/transport-check-new`.',
              '- Re-run model: configure private credential path in a freshly checked-out directory, submit `scripts/transport/run.pbs`; Reuse the published list without overwriting the already run directory.', '',
              'Frozen design see [PROTOCOL_ZH.md](../../assignments/transport_validation/PROTOCOL_ZH.md). Original requests, responses, and workspace states are retained in private directories, while public files contain only metrics and check hashes.', '']
    (OUT / 'README_ZH.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.write:
        write()
    else:
        _, pairs, _ = verify()
        with (OUT / 'pairs.csv').open() as stream:
            stored = list(csv.DictReader(stream))
        assert stored == [{k: '' if v is None else str(v) for k, v in r.items()} for r in pairs]
    print('TRANSPORT_VERIFIED 48')
