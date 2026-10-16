"""Deterministic manifests. The manifest, not worker completion order, defines a study."""
import copy
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = ('none', 'delimiters', 'classifier', 'trustgate', 'no_provenance', 'no_metadata', 'no_authorization')
WEIGHTS = {'W1_calendar_read': 20, 'W2_mail_read': 24, 'W3_drive_read': 28,
           'W4_calendar_write': 32, 'W5_drive_edit': 30, 'W6_mail_to_calendar': 32}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

def pilot_cases(config):
    cases = []
    for workflow, task in config['workflows'].items():
        for condition in ('none', 'trustgate'):
            for repeat in range(1, 4):
                cases.append(dict(workflow=workflow, task=task, surface='benign', condition=condition, repeat=repeat, transport='mcp'))
    for surface in ('output', 'metadata'):
        for condition in CONDITIONS:
            for repeat in range(1, 4):
                cases.append(dict(workflow='W1_calendar_read', task='user_task_1', surface=surface,
                                  condition=condition, repeat=repeat, transport='mcp'))
    for repeat in range(1, 4):
        cases.append(dict(workflow='W1_calendar_read', task='user_task_1', surface='benign',
                          condition='none', repeat=repeat, transport='local'))
    return cases

def build_plan(config, workers=5, budget_usd=1.0, seed=4213):
    if not 1 <= workers <= 5:
        raise ValueError('Choose 1–5 workers; concurrency beyond five has not been planned.')
    if budget_usd <= 0:
        raise ValueError('Budget must be positive.')
    cases = pilot_cases(config)
    for case in cases:
        case['case_id'] = digest(case)[:20]
        case['estimated_seconds'] = WEIGHTS[case['workflow']] * (1.3 if case['surface'] != 'benign' else 1)
    # Pair conditions for the same task/surface/repetition on the same worker.
    # Different repetitions are distributed; no condition is tied to a particular host.
    groups = {}
    for case in cases:
        key = (case['task'], case['surface'], case['repeat'], case['transport'])
        groups.setdefault(key, []).append(case)
    groups = list(groups.values())
    rng = random.Random(seed)
    rng.shuffle(groups)
    groups.sort(key=lambda g: -sum(c['estimated_seconds'] for c in g))
    shards = [dict(index=i, cases=[], estimated_seconds=0.0, budget_usd=budget_usd/workers)
              for i in range(workers)]
    for group in groups:
        shard = min(shards, key=lambda s: (s['estimated_seconds'], s['index']))
        shard['cases'].extend(group)
        shard['estimated_seconds'] += sum(c['estimated_seconds'] for c in group)
    for shard in shards:
        rng.shuffle(shard['cases'])
    plan = dict(schema_version=1, profile='pilot', seed=seed, config=copy.deepcopy(config),
                workers=workers, planned_cases=len(cases), budget_usd=budget_usd,
                note='New execution of the fixed pilot design; never pool with the historical 102 runs.', shards=shards)
    plan['plan_sha256'] = digest(plan)
    validate_plan(plan)
    return plan

def validate_plan(plan):
    content = {k: v for k, v in plan.items() if k != 'plan_sha256'}
    if digest(content) != plan.get('plan_sha256'):
        raise ValueError('Plan changed after hashing; regenerate it before execution.')
    if plan['schema_version'] != 1 or plan['profile'] != 'pilot':
        raise ValueError('This release executes the validated pilot only. Formal study must be frozen first.')
    shards = plan['shards']
    if len(shards) != plan['workers'] or [s['index'] for s in shards] != list(range(len(shards))):
        raise ValueError('Invalid shard indices.')
    cases = [c for shard in shards for c in shard['cases']]
    ids = [c['case_id'] for c in cases]
    if len(ids) != len(set(ids)) or len(ids) != plan['planned_cases']:
        raise ValueError('Duplicate or missing cases.')
    expected = {digest(c)[:20] for c in pilot_cases(plan['config'])}
    if set(ids) != expected or len(cases) != 81:
        raise ValueError('Pilot coverage differs from the fixed 81-case design.')
    for c in cases:
        identity = {k: c[k] for k in ('workflow', 'task', 'surface', 'condition', 'repeat', 'transport')}
        if digest(identity)[:20] != c['case_id']:
            raise ValueError('Case ID does not match its condition/task.')
    if abs(sum(s['budget_usd'] for s in shards)-plan['budget_usd']) > 1e-9:
        raise ValueError('Shard budgets must sum to the total budget.')
    return plan

def read_plan(path):
    return validate_plan(json.loads(Path(path).read_text()))
