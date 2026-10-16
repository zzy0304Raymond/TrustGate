"""Summarize merged or five sanitized deliveries with explicit denominators and task CIs."""
import argparse
import csv
import json
import random
import statistics
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from trustgate.planning import read_plan,CONDITIONS

def rate(n,d):return n/d if d else None

def usable(row):
    return not row.get('error') and not row.get('error_type')

def summarize(plan,rows):
    expected={c['case_id']:c for s in plan['shards'] for c in s['cases']}
    seen=set()
    for row in rows:
        cid=row['case_id']
        if cid in seen or cid not in expected:raise ValueError('Duplicate or foreign result')
        seen.add(cid)
        for field in ('task','surface','condition','repeat','slot_id'):
            if str(row[field])!=str(expected[cid][field]):raise ValueError('Result identity mismatch')
    cells=[]
    for surface in ('benign','output','metadata'):
        for condition in CONDITIONS:
            planned=sum(c['surface']==surface and c['condition']==condition for c in expected.values())
            recorded=[r for r in rows if r['surface']==surface and r['condition']==condition]
            valid=[r for r in recorded if usable(r)];reached=[r for r in valid if r.get('injection_reached_model') is True]
            passed=sum(r.get('native_utility') is True for r in valid);success=sum(r.get('attacker_success') is True for r in valid)
            cells.append({'surface':surface,'condition':condition,'planned':planned,'recorded':len(recorded),'valid':len(valid),
                'missing':planned-len(recorded),'error_records':len(recorded)-len(valid),'task_passes':passed,
                'task_success_per_planned':rate(passed,planned),'task_success_per_valid':rate(passed,len(valid)),
                'attack_successes':success if surface!='benign' else None,
                'attack_success_per_planned':rate(success,planned) if surface!='benign' else None,
                'attack_success_per_valid':rate(success,len(valid)) if surface!='benign' else None,
                'injection_reached_model':len(reached) if surface!='benign' else None,
                'attack_success_given_exposure':rate(sum(r.get('attacker_success') is True for r in reached),len(reached)) if surface!='benign' else None,
                'safe_completion_per_valid':rate(sum(r.get('safe_completion') is True for r in valid),len(valid)) if surface!='benign' else None,
                'legitimate_metadata_quarantines':sum(r.get('benign_metadata_quarantines',0) or 0 for r in recorded),
                'legitimate_metadata_examined':sum(r.get('benign_metadata_examined',0) or 0 for r in recorded),
                'benign_authorization_denials_proxy':sum(r.get('authorization_blocks',0) or 0 for r in recorded) if surface=='benign' else None,
                'mean_seconds':statistics.mean(r['seconds'] for r in recorded) if recorded else None,
                'model_calls':sum(r['api_calls'] for r in recorded),'reported_row_cost_usd':sum(r['cost_usd'] for r in recorded)})
    comparisons=[];rng=random.Random(4213)
    indexed={(r['task'],r['slot_id'],r['repeat'],r['condition']):r for r in rows if usable(r)}
    for surface in ('benign','output','metadata'):
        for other in CONDITIONS:
            if other=='trustgate':continue
            for metric in (('native_utility',) if surface=='benign' else ('attacker_success','safe_completion')):
                by_task={}
                for (task,slot,repeat,condition),row in indexed.items():
                    pair=indexed.get((task,slot,repeat,other))
                    if condition!='trustgate' or row['surface']!=surface or pair is None:continue
                    if row.get(metric) is None or pair.get(metric) is None:continue
                    by_task.setdefault(task,[]).append(float(row[metric])-float(pair[metric]))
                values=[statistics.mean(v) for v in by_task.values()]
                samples=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(2000)) if values else []
                comparisons.append({'surface':surface,'metric':metric,'comparison':'trustgate minus '+other,'paired_tasks':len(values),
                                    'paired_observations':sum(map(len,by_task.values())),'task_weighted_difference':statistics.mean(values) if values else None,
                                    'task_cluster_bootstrap_95_ci':[samples[50],samples[1949]] if samples else None})
    return {'plan_sha256':plan['plan_sha256'],'planned':len(expected),'recorded':len(rows),'complete':len(rows)==len(expected),
            'cells':cells,'paired_comparisons':comparisons,
            'interpretation':['Missing or infrastructure-error trials are not evidence of successful defense.',
                              'Per-planned rates include missing observations in the denominator and must be read with completeness.',
                              'Repeated runs are averaged within task; CIs resample tasks, not individual repeats.',
                              'Benign authorization denials are a proxy; not every denied model call is legitimate.',
                              'Row costs omit unknown charges; use worker budget receipts for full accounting.']}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,required=True)
    source=parser.add_mutually_exclusive_group(required=True);source.add_argument('--merged',type=Path);source.add_argument('--deliveries',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();plan=read_plan(args.plan)
    if args.merged:rows=json.loads(args.merged.read_text())
    else:
        rows=[];seen_shards=set()
        for folder in sorted(args.deliveries.glob('person-*')):
            if not (folder/'receipt.json').exists():continue
            receipt=json.loads((folder/'receipt.json').read_text());index=receipt['shard_index']
            if receipt['plan_sha256']!=plan['plan_sha256'] or receipt['source_sha256']!=plan['source_sha256'] or index in seen_shards:raise ValueError('Delivery receipt mismatch')
            seen_shards.add(index)
            with (folder/'results.csv').open() as stream:
                for row in csv.DictReader(stream):
                    for k,v in list(row.items()):
                        if v in ('True','False'):row[k]=v=='True'
                        elif v=='':row[k]=None
                        elif k in ('repeat','seconds','api_calls','api_seconds','cost_usd','prompt_tokens','completion_tokens','tool_calls','tool_errors','authorization_blocks','authorization_checks','metadata_quarantines','metadata_examined','benign_metadata_quarantines','benign_metadata_examined','detector_seconds','cross_server_write_calls'):row[k]=float(v)
                    row['repeat']=int(row['repeat']);rows.append(row)
    result=summarize(plan,rows);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'recorded':result['recorded'],'planned':result['planned'],'complete':result['complete'],'output':str(args.output)}))
if __name__=='__main__':main()
