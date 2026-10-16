"""Aggregate only completed pilot batches; preserve individual outcomes and assumptions."""
import argparse,collections,csv,hashlib,json,math,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def mean(rows,key):return statistics.mean(r[key] for r in rows) if rows else 0

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--batch',action='append',type=Path);args=parser.parse_args()
    batches=[]
    for p in (ROOT/'runs/mvp').glob('20*'):
        if (p/'batch_summary.json').exists():batches.append(p)
    selected=[]
    for stage in ['basic','advanced']:
        candidates=[p for p in batches if json.loads((p/'config.json').read_text()).get('execution_stage')==stage]
        if not candidates and not args.batch:raise SystemExit('Missing completed '+stage+' batch')
        if candidates:selected.append(max(candidates,key=lambda p:p.name))
    if args.batch:selected=args.batch
    rows=sum([json.loads((p/'results.json').read_text()) for p in selected],[])
    keys=[tuple(r[k] for k in ['workflow','surface','condition','repeat','transport']) for r in rows]
    assert len(rows)==81 and len(set(keys))==81,(len(rows),len(set(keys)))
    out=ROOT/'runs/mvp/analysis';out.mkdir(exist_ok=True)
    simple=[{k:v for k,v in r.items() if k not in ['final_answer','error','additional_audit']} for r in rows]
    with (out/'all_runs.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(simple[0]));writer.writeheader();writer.writerows(simple)
    groups=collections.defaultdict(list)
    for r in rows:groups[(r['workflow'],r['surface'],r['condition'],r['transport'])].append(r)
    aggregate=[]
    for (workflow,surface,condition,transport),rs in sorted(groups.items()):
        aggregate.append({'workflow':workflow,'surface':surface,'condition':condition,'transport':transport,'n':len(rs),'completed':sum(r['pipeline_completed'] for r in rs),'utility_success':sum(r['native_utility'] is True for r in rs),'attacker_success':sum(r['attacker_success'] is True for r in rs) if surface!='benign' else None,'safe_completion':sum(r['safe_completion'] is True for r in rs) if surface!='benign' else None,'reached':sum(r['injection_reached_model'] for r in rs),'mean_seconds':mean(rs,'seconds'),'median_seconds':statistics.median(r['seconds'] for r in rs),'min_seconds':min(r['seconds'] for r in rs),'max_seconds':max(r['seconds'] for r in rs),'mean_cost_usd':mean(rs,'cost_usd'),'mean_api_calls':mean(rs,'api_calls'),'authorization_blocked_runs':sum(r['authorization_blocks']>0 for r in rs),'metadata_quarantined_runs':sum(r['metadata_quarantines']>0 for r in rs),'tool_error_runs':sum(r['tool_errors']>0 for r in rs)})
    benign=[r for r in rows if r['surface']=='benign' and r['transport']=='mcp'];attack=[r for r in rows if r['surface']!='benign']
    weights={'W1_calendar_read':4,'W2_mail_read':4,'W3_drive_read':3,'W4_calendar_write':4,'W5_drive_edit':3,'W6_mail_to_calendar':2}
    estimates={}
    for key in ['seconds','cost_usd']:
        b=sum(mean([r for r in benign if r['workflow']==w],key)*n for w,n in weights.items())/20
        ref=mean([r for r in benign if r['workflow']=='W1_calendar_read'],key)
        factor=max(1,b/ref)
        a=mean(attack,key)*factor
        main_total=420*b+1260*a;per_run=main_total/1680
        estimates[key]={'benign_weighted_mean':b,'attack_observed_mean':mean(attack,key),'complexity_factor':factor,'attack_extrapolated_mean':a,'formal_1680_total':main_total,'remaining_1842_total':1842*per_run,'remaining_with_185_retry_reserve':2027*per_run,'remaining_with_reserve_double_duration_sensitivity':4054*per_run,'whole_plan_1923_total':sum(r[key] for r in rows)+1842*per_run}
    fp=[]
    for r in benign:
        if r['condition']!='trustgate':continue
        ev=json.loads((Path(r['result_dir'])/'defense_events.json').read_text())
        scanned=[e for e in ev if e['kind']=='metadata_classifier'];blocked=[e for e in ev if e['kind']=='metadata_quarantine']
        fp.append({'workflow':r['workflow'],'repeat':r['repeat'],'scanned':len(scanned),'blocked_tools':[e['tool'] for e in blocked],'authorization_blocks':r['authorization_blocks']})
    summary={'analysis_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'batches':[str(p) for p in selected],'records':len(rows),'completed':sum(r['pipeline_completed'] for r in rows),'benign_utility':sum(r['native_utility'] is True for r in benign),'benign_total':len(benign),'sum_task_seconds':sum(r['seconds'] for r in rows),'sum_batch_wall_seconds':sum(json.loads((p/'batch_summary.json').read_text())['wall_seconds'] for p in selected),'actual_api_cost_usd':sum(r['cost_usd'] for r in rows),'api_calls':sum(r['api_calls'] for r in rows),'prompt_tokens':sum(r['prompt_tokens'] for r in rows),'completion_tokens':sum(r['completion_tokens'] for r in rows),'errors':[r for r in rows if r['error'] or not r['pipeline_completed']],'aggregate':aggregate,'benign_false_positive_audit':fp,'time_and_cost_estimates':estimates,'estimate_assumptions':['Main set: 20 benign tasks and 60 total attack cases, seven conditions, three repetitions.','Benign estimates use the weighted average of no-defense and full-defense measurements; other benign conditions are not yet measured.','Attack measurements cover only one calendar task and one payload per surface. A task-complexity ratio rescales them; this is a planning model, not a confidence interval.','Harder tasks may take twice the projected time/cost; API limits, queue time, installations and human analysis are not inferred from these trials.']}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['aggregate','errors','benign_false_positive_audit']},ensure_ascii=False,indent=2))
    print('GROUPS')
    for row in aggregate:print(json.dumps(row,ensure_ascii=False))

if __name__=='__main__':main()
