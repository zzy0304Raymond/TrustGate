"""Recompute report-only summaries from the frozen TrustGate v1.0.1 release.
Python standard library only; no network, model calls, or source-data writes.
"""
import argparse
import csv
import hashlib
import itertools
import json
import random
import statistics
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

CONDITIONS = ('none', 'delimiters', 'classifier', 'trustgate', 'no_provenance',
              'no_metadata', 'no_authorization')
SURFACES = ('benign', 'output', 'metadata')
NUMERIC = {'repeat','seconds','api_calls','api_seconds','cost_usd','prompt_tokens',
           'completion_tokens','tool_calls','tool_errors','authorization_blocks',
           'authorization_checks','metadata_quarantines','metadata_examined',
           'benign_metadata_quarantines','benign_metadata_examined','detector_seconds',
           'cross_server_write_calls'}

def require(condition, message):
    if not condition:
        raise SystemExit(message)

def valid(r):
    return not r.get('error_type')

def task_differences(rows, left, right, surface, metric):
    index={(r['task'],r['slot_id'],r['repeat'],r['condition']):r for r in rows if valid(r)}
    grouped=defaultdict(list)
    for (task,slot,repeat,c),r in index.items():
        pair=index.get((task,slot,repeat,right))
        if c==left and r['surface']==surface and pair is not None:
            grouped[task].append(int(r[metric])-int(pair[metric]))
    return [Fraction(sum(grouped[t]),len(grouped[t])) for t in sorted(grouped)]

def exact(values):
    # Zero differences can be omitted: each sign pattern then has equal multiplicity.
    nonzero=[v for v in values if v]
    if not nonzero: return 1.0
    observed=abs(sum(nonzero))
    extreme=sum(abs(sum(v*s for v,s in zip(nonzero, signs)))>=observed
                for signs in itertools.product((-1,1),repeat=len(nonzero)))
    return extreme/(2**len(nonzero))

def comparison(rows,left,right,surface,metric):
    vals=task_differences(rows,left,right,surface,metric)
    rng=random.Random(4213)
    draws=sorted(float(sum(rng.choices(vals,k=len(vals)))/len(vals))*100 for _ in range(2000))
    direction=-1 if metric=='attacker_success' else 1
    return dict(surface=surface,metric=metric,comparison=f'{left} minus {right}',
                tasks=len(vals),difference_pp=float(sum(vals)/len(vals))*100,
                favour_left=sum(v*direction>0 for v in vals),
                favour_right=sum(v*direction<0 for v in vals),exact_p=exact(vals),
                bootstrap_low_pp=draws[50],bootstrap_high_pp=draws[1949])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); root=args.release.resolve();out=args.output.resolve()
    if out==root or root in out.parents:
        raise SystemExit('Choose an output directory outside the release checkout.')
    out.mkdir(parents=True,exist_ok=True)
    hashes={}
    def read(relative):
        p=root/relative;b=p.read_bytes();hashes[relative]=hashlib.sha256(b).hexdigest()
        return b.decode('utf-8-sig')
    def save(name,records):
        records=list(records)
        require(bool(records), f'No records to write: {name}')
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    plan=json.loads(read('assignments/formal/plan.json'))
    expected={c['case_id']:c for shard in plan['shards'] for c in shard['cases']}
    rows=[]
    for person in range(1,6):
        raw=read(f'experiments/deliveries/person-{person:02d}/results.csv')
        for source in csv.DictReader(raw.splitlines()):
            r={k:(v=='True' if v in ('True','False') else None if v=='' else
                  float(v) if k in NUMERIC else v) for k,v in source.items()}
            r['repeat']=int(r['repeat']);r['person']=person;rows.append(r)
            e=expected[r['case_id']]
            for k in ('task','slot_id','surface','condition','repeat'):
                require(str(r[k])==str(e[k]),f"Identity mismatch: {r['case_id']} {k}")
    require(len(rows)==1680 and len({r['case_id'] for r in rows})==1680, 'Expected 1680 unique records')
    require({r['case_id'] for r in rows}==set(expected), 'Plan coverage mismatch')
    require(sum(map(valid,rows))==1679, 'Expected 1679 valid records')
    attacks=json.loads(read('data/formal/attacks.json'))['attacks']
    main_counts=[];resources=[];activity=[];failures=[];exposure=[];status=[]
    for surface in SURFACES:
        for c in CONDITIONS:
            allrows=[r for r in rows if r['surface']==surface and r['condition']==c]
            good=[r for r in allrows if valid(r)]
            main_counts.append(dict(surface=surface,condition=c,recorded=len(allrows),valid=len(good),
                task_passes=sum(r['native_utility'] is True for r in good),
                attack_successes=sum(r['attacker_success'] is True for r in good),
                safe_completions=sum(r['safe_completion'] is True for r in good)))
            if surface=='output':
                point=[r for r in good if r['injection_point_reached']]
                reached=[r for r in good if r['injection_reached_model']]
                exposure.append(dict(condition=c,injection_point_reached=len(point),reached_model=len(reached),
                    filtered_before_model=len(point)-len(reached),
                    successes_given_exposure=sum(r['attacker_success'] is True for r in reached)))
                activity.append(dict(condition=c,denials=int(sum(r['authorization_blocks'] for r in good)),
                    denial_trials=sum(r['authorization_blocks']>0 for r in good),
                    denial_limit_stops=sum(r['status']=='denial_budget' for r in good)))
    for c in CONDITIONS:
        group=[r for r in rows if r['condition']==c]
        avg={k:statistics.mean(r[k] for r in group) for k in ('seconds','api_seconds','detector_seconds','api_calls')}
        resources.append(dict(condition=c,n=len(group),**avg,other_seconds=avg['seconds']-avg['api_seconds']-avg['detector_seconds']))
        for s,n in sorted(Counter(r['status'] for r in group).items()):
            status.append(dict(condition=c,status=s,count=n))
        counts=Counter()
        for r in group:
            if r['surface']!='benign' or r['native_utility']:continue
            if r['status']!='completed': category='Stopped at call or denial limit'
            elif r['authorization_blocks']>0: category='Completed, authorization denial'
            elif r['tool_errors']>0: category='Completed, at least one tool error'
            else:category='Completed, failed native check'
            counts[category]+=1
        for category in ('Stopped at call or denial limit','Completed, at least one tool error',
                         'Completed, authorization denial','Completed, failed native check'):
            failures.append(dict(condition=c,category=category,count=counts[category]))
    save('main_counts.csv',main_counts);save('resources_by_condition.csv',resources)
    save('gateway_activity_output.csv',activity);save('attack_exposure.csv',exposure)
    save('benign_failure_modes.csv',failures);save('status_counts.csv',status)
    tests=[]
    for c in CONDITIONS:
        if c=='trustgate':continue
        for surface,metric in [('output','attacker_success'),('output','safe_completion'),('benign','native_utility')]:
            item=comparison(rows,'trustgate',c,surface,metric)
            item.pop('bootstrap_low_pp');item.pop('bootstrap_high_pp');tests.append(item)
    save('exact_sign_flip_tests.csv',tests)
    baseline=[]
    for c in ('delimiters','classifier'):
        item=comparison(rows,c,'none','output','attacker_success')
        index={(r['task'],r['slot_id'],r['repeat'],r['condition']):r for r in rows if valid(r)}
        joint=Counter()
        for r in rows:
            if r['surface']=='output' and r['condition']==c:
                n=index[(r['task'],r['slot_id'],r['repeat'],'none')]
                joint[(bool(n['attacker_success']),bool(r['attacker_success']))]+=1
        item.update(both=joint[(True,True)],none_only=joint[(True,False)],defense_only=joint[(False,True)])
        baseline.append(item)
    save('baselines_vs_none.csv',baseline)
    vanda=[r for r in rows if r['person'] in (1,4,5)]
    save('sensitivity_vanda_only.csv',[comparison(vanda,'trustgate','none','output','attacker_success')])
    grouped=[];classifier=[]
    for field in ('template_family','goal_tool','server_boundary'):
        def label(a):
            return a['template_family'] if field=='template_family' else a['goal']['tool'] if field=='goal_tool' else ('same' if a['source_server']==a['target_server'] else 'cross')
        labels=sorted({label(a) for a in attacks.values() if a['surface']=='output'})
        for value in labels:
            ids={aid for aid,a in attacks.items() if a['surface']=='output' and label(a)==value}
            for c in CONDITIONS:
                group=[r for r in rows if r['condition']==c and r['attack_case_id'] in ids and valid(r)]
                grouped.append(dict(dimension=field,label=value,condition=c,cases=len(ids),valid=len(group),
                                    successes=sum(r['attacker_success'] for r in group)))
                if field=='template_family' and c=='classifier':
                    point=[r for r in group if r['injection_point_reached']]
                    classifier.append(dict(template=value,injection_point_reached=len(point),
                        blocked=sum(not r['injection_reached_model'] for r in point),
                        successes=sum(r['attacker_success'] for r in point)))
    save('attack_by_group.csv',grouped);save('classifier_by_template.csv',classifier)
    # Check primary counts against the published independent analysis table.
    published=list(csv.DictReader(read('results/formal/analysis/tables/main_metrics.csv').splitlines()))
    primary_matches=[]
    for result in main_counts:
        p=next(p for p in published if p['surface']==result['surface'] and p['condition']==result['condition'])
        for k in ('recorded','valid','task_passes'):
            primary_matches.append(int(p[k])==result[k])
            require(primary_matches[-1],f"Primary count mismatch: {result['surface']} {result['condition']} {k}")
        if result['surface']!='benign':
            for k in ('attack_successes','safe_completions'):
                primary_matches.append(int(p[k])==result[k])
                require(primary_matches[-1],f"Primary count mismatch: {result['surface']} {result['condition']} {k}")
    (out/'check_receipt.json').write_text(json.dumps(dict(recorded=len(rows),valid=sum(map(valid,rows)),
        primary_counts_match=all(primary_matches),input_sha256=hashes,
        exact_method='All sign patterns on nonzero task differences; exact rational arithmetic; two-sided.',
        bootstrap_method='2000 equal-weight task resamples, seed 4213 reset per comparison; sorted task IDs; order-statistic endpoints 50 and 1949 (zero-based).',
        scope='Supplementary report analysis. This does not replace the release integrity verifier or rerun models.'),indent=2)+'\n')
    print(f'Checked {len(rows)} records; primary counts match. Outputs: {out}')

if __name__=='__main__':main()
