"""Freeze and verify formal data, execution code, model files and software versions."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[1]))
from release_integrity import recorded_digest
import copy
import hashlib
import importlib.metadata
import json
import random
from pathlib import Path
from .planning import ROOT,CONDITIONS,digest

PACKAGES=('agentdojo','mcp','transformers','torch','pydantic','openai')

def source_hashes():
    paths=[p for base in ('trustgate','experiments/mvp') for p in (ROOT/base).glob('*.py')]
    return {str(p.relative_to(ROOT)):recorded_digest(hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(paths)}

def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return recorded_digest(h.hexdigest())

def detector_hashes(folder):
    names=('model.safetensors','config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','spm.model')
    return {n:file_sha(Path(folder)/n) for n in names}

def build_formal_plan(allocation,tasks,attacks,detector_dir):
    config=json.loads((ROOT/'configs/mvp/pilot.json').read_text())
    for name in ('payload','attack_task','attack_vector','workflows'):config.pop(name,None)
    config.update(version='formal-v1',formal_tasks=tasks['tasks'],formal_attacks=attacks['attacks'],
                  max_total_cost_usd=10.0,per_request_reservation_usd=0.05)
    shards=[];rng=random.Random(42130)
    for person in allocation['people']:
        cases=copy.deepcopy(person['trials'])
        for case in cases:
            case['attack_case_id']=case['slot_id'] if case['surface']!='benign' else None
            case['split']='test'
        rng.shuffle(cases)
        shards.append(dict(index=person['person']-1,person=person['person'],branch=person['branch'],cases=cases,
                           budget_usd=2.0,estimated_seconds=person['estimated_seconds']))
    plan=dict(schema_version=2,profile='formal_v1',ready_to_run=True,seed=42130,workers=5,planned_cases=1680,budget_usd=10.0,
              config=config,shards=shards,allocation_sha256=allocation['plan_sha256'],
              test_template_families=attacks['test_template_families'],development_template_families=attacks['development_template_families'],
              source_sha256=source_hashes(),detector_sha256=detector_hashes(detector_dir),
              packages={name:importlib.metadata.version(name) for name in PACKAGES},
              retry_policy='No automatic retries. Preserve infrastructure failures; any replacement requires a new explicit bounded manifest and separate attempt records.',
              note='Prepared and frozen, not executed. Three repeats per task/payload are clustered, not independent attack families.')
    plan['plan_sha256']=digest(plan)
    return validate_formal_plan(plan)

def validate_formal_plan(plan):
    if plan.get('schema_version')!=2 or plan.get('profile') not in ('formal_v1','formal_development_v1') or not plan.get('ready_to_run'):raise ValueError('Invalid executable formal manifest')
    if plan.get('plan_sha256')!=digest({k:v for k,v in plan.items() if k!='plan_sha256'}):raise ValueError('Formal manifest hash mismatch')
    if set(plan['test_template_families']) & set(plan['development_template_families']):raise ValueError('Development/test template overlap')
    if plan['workers']!=5 or [s['index'] for s in plan['shards']]!=list(range(5)):raise ValueError('Expected five distinct workers')
    cases=[c for s in plan['shards'] for c in s['cases']]
    if len(cases)!=plan['planned_cases'] or len({c['case_id'] for c in cases})!=len(cases):raise ValueError('Duplicate/missing trials')
    if abs(sum(s['budget_usd'] for s in plan['shards'])-plan['budget_usd'])>1e-9:raise ValueError('Budget allocations do not sum')
    tasks=plan['config']['formal_tasks'];attacks=plan['config']['formal_attacks']
    for case in cases:
        if case['task'] not in tasks or case['condition'] not in CONDITIONS:raise ValueError('Unknown task/condition')
        identity={k:case[k] for k in ('slot_id','task','workflow','surface','condition','repeat','transport')}
        if digest(identity)[:20]!=case['case_id']:raise ValueError('Case identity changed')
        if case['surface']!='benign':
            attack=attacks[case['attack_case_id']]
            if attack['task']!=case['task'] or attack['surface']!=case['surface'] or attack['split']!=case['split']:raise ValueError('Attack identity mismatch')
    if plan['profile']=='formal_v1':
        if len(tasks)!=20 or len(attacks)!=60 or len(cases)!=1680:raise ValueError('Formal corpus size changed')
        owner_tasks=[]
        for shard in plan['shards']:
            local=shard['cases'];owner_tasks.extend(set(c['task'] for c in local))
            if len(local)!=336 or {surface:sum(c['surface']==surface for c in local) for surface in ('benign','output','metadata')}!={'benign':84,'output':126,'metadata':126}:raise ValueError('Unequal formal shard')
            slots={c['slot_id'] for c in local}
            if len(slots)!=16:raise ValueError('Incomplete slots')
            for slot in slots:
                if {(c['condition'],c['repeat']) for c in local if c['slot_id']==slot}!={(condition,repeat) for condition in CONDITIONS for repeat in (1,2,3)}:raise ValueError('Unpaired trial design')
        if len(owner_tasks)!=20 or len(set(owner_tasks))!=20:raise ValueError('Task assigned more than once')
        dev={f'user_task_{i}' for i in (1,14,26,6,29,15)}
        if set(tasks)&dev or any(c['split']!='test' for c in cases):raise ValueError('Development/test task overlap')
    if not plan.get('source_sha256') or not plan.get('detector_sha256') or not plan.get('packages'):raise ValueError('Missing reproducibility pins')
    return plan

def verify_runtime(plan,detector_dir):
    if source_hashes()!=plan['source_sha256']:raise RuntimeError('Code differs from frozen manifest; use the published experiment version')
    if {name:importlib.metadata.version(name) for name in PACKAGES}!=plan['packages']:raise RuntimeError('Package versions differ from frozen environment')
    if detector_hashes(detector_dir)!=plan['detector_sha256']:raise RuntimeError('Detector files differ from frozen version')
