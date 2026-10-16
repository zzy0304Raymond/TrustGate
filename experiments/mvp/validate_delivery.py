"""Check delivered counts, cost ledger, frozen sources, local links and credential hygiene."""
import collections,datetime,hashlib,json,os,re,stat,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'runs/mvp/analysis'
if not os.environ.get('PBS_JOBID'):raise SystemExit('PBS required')
s=json.loads((OUT/'summary.json').read_text());f=json.loads((OUT/'final_metrics.json').read_text())
batches=[Path(p) for p in s['batches']]+[Path(f['followup_batch']),Path(f['binding_batch'])]
rows=[];response_count=0;cost=0;providers=set();models=set();metadata_deliveries=0
for batch in batches:
    rs=json.loads((batch/'results.json').read_text());rows.extend(rs)
    manifest=json.loads((batch/'manifest.json').read_text())
    assert manifest['python']=='3.10.20'
    for rel,sha in manifest['sources'].items():
        source=batch/'source_snapshot'/Path(rel).name
        assert source.exists() and hashlib.sha256(source.read_bytes()).hexdigest()==sha,(batch,rel)
    (batch/'detector_manifest.json').write_bytes((ROOT/'models/detector_manifest.json').read_bytes())
    for r in rs:
        d=Path(r['result_dir']);responses=sorted(d.glob('response_*.json'));assert len(responses)==r['api_calls']
        subtotal=0
        for p in responses:
            answer=json.loads(p.read_text());subtotal+=answer['usage']['cost'];providers.add(answer.get('provider'));models.add(answer.get('model'))
        assert abs(subtotal-r['cost_usd'])<1e-10
        response_count+=len(responses);cost+=subtotal
        for name in ['summary.json','trajectory.json','tool_calls.json','defense_events.json','environment_before.json','environment_after.json']:assert (d/name).exists()
        if r['surface']=='metadata' and r['condition']=='none':
            request=json.loads((d/'request_01.json').read_text());desc=next(t['function']['description'] for t in request['tools'] if t['function']['name']=='get_day_calendar_events')
            assert 'Workspace integrity checkpoint:' in desc or 'CALENDAR CONNECTOR V2' in desc
            assert r['injection_reached_model'];metadata_deliveries+=1
assert len(rows)==102 and response_count==293 and abs(cost-f['reported_api_cost_usd'])<1e-10
assert providers=={'SiliconFlow'} and models=={'qwen/qwen3-30b-a3b-instruct-2507'},(providers,models)
keys=[(r.get('variant','fixed'),r['workflow'],r['surface'],r['condition'],r['repeat'],r['transport']) for r in rows];assert len(set(keys))==102
cells=collections.Counter((r.get('variant','fixed'),r['workflow'],r['surface'],r['condition'],r['transport']) for r in rows);assert set(cells.values())=={3}
plan=json.loads((ROOT/'configs/mvp/planned_full_study.json').read_text());testids=[f'user_task_{x}' for v in plan['candidate_test_tasks'].values() for x in v]
assert len(testids)==len(set(testids))==20 and not set(testids)&set(plan['pilot_development_tasks'])
assert 81+126+36+420+1260==1923 and 1923-102==1821 and 1923+185==2108
assert (ROOT/'models/detector_revision.txt').read_text().strip()==json.loads((ROOT/'models/detector_manifest.json').read_text())['revision']
key=(ROOT/'.secrets/openrouter_group9.key').read_bytes().strip();assert key.startswith(b'sk-or-v1-')
assert stat.S_IMODE((ROOT/'.secrets/openrouter_group9.key').stat().st_mode)==0o600
leaks=[];checked=0
for p in ROOT.rglob('*'):
    if '.secrets' in p.parts or not p.is_file() or p.suffix not in {'.py','.md','.json','.jsonl','.log','.txt','.csv','.pbs'}:continue
    if key in p.read_bytes():leaks.append(str(p))
    checked+=1
assert not leaks,'Credential found in public artifact'
missing=[]
for p in [ROOT/'README_ZH.md',ROOT/'docs/WORKFLOW_MVP_FEASIBILITY_ZH.md',ROOT/'docs/NEXT_STEP_ZH.md',ROOT/'docs/DEMO_WALKTHROUGH_ZH.md',ROOT/'docs/PROJECT_PLAN_ZH.md']:
    for target in re.findall(r'\]\((<?/[^\n]+?)\)',p.read_text()):
        target=target.strip('<>')
        if not Path(target).exists():missing.append({'file':str(p),'target':target})
assert not missing,missing
try:
    request=urllib.request.Request('https://openrouter.ai/api/v1/key',headers={'Authorization':'Bearer '+key.decode()})
    with urllib.request.urlopen(request,timeout=20) as response:data=json.load(response)['data']
    balance={k:data.get(k) for k in ['limit','limit_remaining','usage','usage_daily','usage_monthly']}
    (OUT/'key_balance_snapshot.json').write_text(json.dumps({'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'values':balance,'note':'This is a separate provider quota snapshot, not a replacement for the per-response cost ledger.'},indent=2)+'\n')
except Exception as exc:balance={'unavailable':type(exc).__name__}
result={'passed':True,'real_runs':len(rows),'cells_with_three_repeats':len(cells),'real_api_calls':response_count,'reported_cost_usd':cost,'providers':sorted(providers),'models':sorted(models),'unprotected_metadata_deliveries_verified':metadata_deliveries,'public_text_files_checked_for_key':checked,'credential_leaks':0,'missing_deliverable_links':0,'source_snapshots_verified':True,'test_tasks_disjoint_from_development':True,'pbs_job_id':os.environ['PBS_JOBID'],'key_quota_snapshot':balance}
(OUT/'delivery_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
