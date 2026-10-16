"""Allocate the 1,680 planned formal trials across five people by estimated duration.

This is a workload allocation, not an executable experiment manifest: permission
policies and actual held-out attack payloads must still be reviewed and frozen.
"""
import csv
import hashlib
import json
import statistics
from pathlib import Path
from .planning import ROOT, CONDITIONS, digest


def load_profiles(root=ROOT):
    with (root/'results/pilot/all_runs.csv').open() as stream:
        original = list(csv.DictReader(stream))
    with (root/'results/pilot/followup_runs.csv').open() as stream:
        development = list(csv.DictReader(stream))
    workflows = json.loads((root/'configs/mvp/pilot.json').read_text())['workflows']
    profiles = {w:[r for r in original if r['workflow']==w and r['surface']=='benign' and r['transport']=='mcp'] for w in workflows}
    profiles['W4_calendar_write'] = [r for r in development if r['workflow']=='W4_calendar_write' and r['native_utility']=='True' and r['status']=='completed']
    profiles['W5_drive_edit'] = [r for r in development if r['variant']=='json_recovery']
    return {w:statistics.mean(float(r['seconds']) for r in rows) for w,rows in profiles.items()}


def build_allocation(root=ROOT):
    study = json.loads((root/'configs/mvp/planned_full_study.json').read_text())
    metrics = json.loads((root/'results/pilot/final_metrics.json').read_text())
    profiles = load_profiles(root)
    multiplier = metrics['estimates']['seconds']['attack_observed_mean']/profiles['W1_calendar_read']
    tasks = []
    for workflow, ids in study['candidate_test_tasks'].items():
        profile = 'W6_mail_to_calendar' if workflow.startswith('W6_') else workflow
        for number in ids:
            benign = profiles[profile]
            tasks.append(dict(task=f'user_task_{number}', workflow=workflow,
                              benign_seconds=benign, attack_seconds=benign*multiplier,
                              estimated_seconds=21*(benign+3*benign*multiplier)))
    # Four task groups per person. All seven conditions for a task remain paired.
    groups = [[] for _ in range(5)]
    for task in sorted(tasks, key=lambda t:(-t['estimated_seconds'],t['task'])):
        index = min((i for i in range(5) if len(groups[i])<4),
                    key=lambda i:(sum(t['estimated_seconds'] for t in groups[i]),i))
        groups[index].append(task)
    # Pair swaps reduce duration imbalance while retaining four tasks per person.
    def load(group): return sum(t['estimated_seconds'] for t in group)
    while True:
        best = None
        for i in range(5):
            for j in range(i+1,5):
                a,b = load(groups[i]),load(groups[j])
                for x,tx in enumerate(groups[i]):
                    for y,ty in enumerate(groups[j]):
                        delta = ty['estimated_seconds']-tx['estimated_seconds']
                        gain = a*a+b*b-(a+delta)**2-(b-delta)**2
                        if gain>1e-6 and (best is None or gain>best[0]):best=(gain,i,j,x,y)
        if best is None:break
        _,i,j,x,y=best
        groups[i][x],groups[j][y]=groups[j][y],groups[i][x]
    people=[]
    for number,group in enumerate(groups,1):
        trials=[];slots=[]
        group.sort(key=lambda t:int(t['task'].rsplit('_',1)[1]))
        for position,task in enumerate(group):
            # Each person gets six output and six metadata attack slots.
            surfaces=['output','output','metadata'] if position<2 else ['output','metadata','metadata']
            counts={'output':0,'metadata':0}
            task_slots=[dict(slot_id=task['task']+'-benign',surface='benign')]
            for surface in surfaces:
                counts[surface]+=1
                task_slots.append(dict(slot_id=f"{task['task']}-{surface}-{counts[surface]}",surface=surface,
                    payload_ref=None,attack_goal_ref=None,injection_location_ref=None,
                    status='awaiting_reviewed_test_case'))
            for slot in task_slots:
                slots.append(dict(slot,task=task['task'],workflow=task['workflow'],policy_ref=None))
                for condition in CONDITIONS:
                    for repeat in range(1,4):
                        case=dict(slot_id=slot['slot_id'],task=task['task'],workflow=task['workflow'],surface=slot['surface'],condition=condition,repeat=repeat,transport='mcp')
                        case['case_id']=digest(case)[:20]
                        case['estimated_seconds']=task['benign_seconds'] if slot['surface']=='benign' else task['attack_seconds']
                        trials.append(case)
        people.append(dict(person=number,branch=f'experiment-{number}',tasks=[t['task'] for t in group],
            benign_runs=84,output_attack_runs=126,metadata_attack_runs=126,total_runs=336,
            estimated_seconds=sum(t['estimated_seconds'] for t in trials),
            budget_allocation_usd=2.0,case_slots=slots,trials=trials))
    allocation=dict(schema_version=1,profile='formal_allocation',ready_to_run=False,
        status='allocated_not_frozen_or_executed',people=people,total_runs=1680,benign_runs=420,
        attack_runs=1260,attack_slots_total=60,conditions=list(CONDITIONS),repeats=3,
        shared_api_budget_usd=10.0,
        estimated_serial_seconds=sum(p['estimated_seconds'] for p in people),
        estimated_parallel_seconds=max(p['estimated_seconds'] for p in people),
        timing_basis='Same pilot-based forecast as final_metrics.json, apportioned by workflow; successful calendar development trials are for timing only.',
        timing_excludes=['shared preparation','PBS queue','final report','unmeasured API concurrency slowdown'],
        blockers=['Review and freeze trusted permissions for the 20 formal tasks.',
                  'Fill and freeze all 60 held-out attack slots, including payload, goal and injection location.',
                  'Integrate formal-case execution into the currently pilot-only runner and validate its five-worker throughput.'])
    allocation['plan_sha256']=digest(allocation)
    validate_allocation(allocation)
    return allocation


def validate_allocation(plan):
    if plan['plan_sha256']!=digest({k:v for k,v in plan.items() if k!='plan_sha256'}):raise ValueError('Allocation hash mismatch')
    if plan['ready_to_run'] is not False:raise ValueError('Allocation-only plan must not claim execution readiness')
    trials=[t for p in plan['people'] for t in p['trials']]
    if len(trials)!=1680 or len({t['case_id'] for t in trials})!=1680:raise ValueError('Formal trials must occur exactly once')
    tasks=[t for p in plan['people'] for t in p['tasks']]
    if len(tasks)!=20 or len(set(tasks))!=20:raise ValueError('Each task must have exactly one owner')
    for person in plan['people']:
        counts={s:sum(t['surface']==s for t in person['trials']) for s in ('benign','output','metadata')}
        if counts!={'benign':84,'output':126,'metadata':126}:raise ValueError('Unbalanced experimental coverage')
        if len(person['tasks'])!=4 or len(person['case_slots'])!=16:raise ValueError('Each person needs four tasks and sixteen case slots')
    return plan


def write_allocation(output, root=ROOT):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    plan=build_allocation(root)
    (output/'allocation.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    for person in plan['people']:
        envelope=dict(profile='formal_allocation',ready_to_run=False,allocation_sha256=plan['plan_sha256'],
                      status=plan['status'],blockers=plan['blockers'],assignment=person)
        (output/f"person-{person['person']:02d}.json").write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+'\n')
    return plan
