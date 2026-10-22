"""Export three selected demo checks; keep full conversations and states private."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[2]))
from release_integrity import recorded_digest
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return recorded_digest(hashlib.sha256(path.read_bytes()).hexdigest())

def offline(event,args):
    if event in {'socket.connect','socket.getaddrinfo'}:
        raise RuntimeError('Demo checks do not allow network access')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--person1',type=Path,required=True)
    parser.add_argument('--supplement',type=Path,required=True)
    args=parser.parse_args()
    from trustgate.runner import require_compute
    require_compute()
    sys.addaudithook(offline)
    from agentdojo.task_suite.load_suites import get_suite
    from agentdojo.functions_runtime import FunctionCall
    from agentdojo.types import text_content_block_from_string
    from trustgate.planning import read_plan,digest
    plan=read_plan(ROOT/'assignments/formal/plan.json')
    supplement=read(ROOT/'assignments/metadata_supplement/evaluation.json')
    for name,expected in plan['source_sha256'].items():
        assert sha(ROOT/name)==expected,name
    selected={
        '3a9dec562468a0a220e4':(args.person1,plan['config']),
        'f6e31ab2e29b9993b4a1':(args.supplement/'evaluation',supplement['config']),
        '0e03f8c8c70017ff4ffd':(args.supplement/'continuation-01',supplement['config'])}
    formal={r['case_id']:r for r in csv.DictReader((ROOT/'experiments/deliveries/person-01/results.csv').open())}
    supp_public={r['case_id']:r for r in csv.DictReader((ROOT/'results/metadata_supplement/evaluation_trials.csv').open())}
    suite=get_suite(plan['config']['benchmark'],plan['config']['suite'])
    records=[]
    for cid,(base,config) in selected.items():
        row=next(r for r in read(base/'results.json') if r['case_id']==cid)
        folder=base/Path(row['result_dir']).name
        assert read(folder/'summary.json')==row
        assert row['status']=='completed' and not row['error']
        public=(formal if cid in formal else supp_public)[cid]
        for field in ('task','surface','condition','repeat','status','native_utility'):
            assert public[field]==str(row[field]),(cid,field)
        before_json=read(folder/'environment_before.json');after_json=read(folder/'environment_after.json')
        task=suite.user_tasks[row['task']]
        baseline=task.init_environment(suite.load_and_inject_default_environment({}))
        assert before_json==baseline.model_dump(mode='json')
        assert digest(before_json)==config['formal_tasks'][row['task']]['initial_state_sha256']
        assert read(folder/'policy.json')==config['formal_tasks'][row['task']]['policy']
        def restore(value):
            env=type(baseline).model_validate(value)
            for owner,field in [('cloud_drive','files'),('calendar','events'),('inbox','emails')]:
                kind=type(next(iter(getattr(getattr(baseline,owner),field).values())))
                setattr(getattr(env,owner),field,{k:kind.model_validate(v) for k,v in value[owner][field].items()})
            assert env.model_dump(mode='json')==value
            return env
        before,after=restore(before_json),restore(after_json)
        calls=read(folder/'tool_calls.json');events=read(folder/'defense_events.json')
        trajectory=read(folder/'trajectory.json');usage=read(folder/'api_usage.json')
        assistants=[(i,m) for i,m in enumerate(trajectory) if m['role']=='assistant']
        assert len(assistants)==len(usage)==row['api_calls']
        for step,(i,message) in enumerate(assistants,1):
            request=read(folder/f'request_{step:02}.json');response=read(folder/f'response_{step:02}.json')
            assert request['messages']==trajectory[:i]
            assert request['model']==config['model'] and request['temperature']==config['temperature']
            assert response['usage']==usage[step-1]['usage']
            reply=response['choices'][0]['message']
            normalized={'role':'assistant','content':reply.get('content')}
            if reply.get('tool_calls'): normalized['tool_calls']=reply['tool_calls']
            assert normalized==message
        proposals=[t['function'] for _,m in assistants for t in m.get('tool_calls',[])]
        assert len(proposals)==len(calls)==row['tool_calls']
        for p,c in zip(proposals,calls):
            assert p['name']==c['name'] and json.loads(p['arguments'])==c['args']
        stack=[FunctionCall(function=c['name'],args=c['args'],id=str(i)) for i,c in enumerate(calls) if c['executed']]
        rescored=suite._check_task_result(task,[text_content_block_from_string(row['final_answer'])],before,after,stack)
        assert rescored==row['native_utility']
        quarantined=[e['tool'] for e in events if e['kind']=='metadata_quarantine']
        record=dict(case_id=cid,task=row['task'],surface=row['surface'],condition=row['condition'],repeat=row['repeat'],
                    status=row['status'],native_utility=row['native_utility'],native_utility_recomputed=rescored,
                    requests_checked=len(assistants),saved_request_response_match=True,snapshot_roundtrip_exact=True,
                    tool_names=[c['name'] for c in calls],authorization_blocks=row['authorization_blocks'],
                    quarantined_tools=quarantined,benign_metadata_quarantines=row['benign_metadata_quarantines'],
                    state_unchanged=before_json==after_json,private_originals={p.name:sha(p) for p in sorted(folder.glob('*.json'))})
        if row['task']=='user_task_12':
            new_ids=set(after_json['calendar']['events'])-set(before_json['calendar']['events'])
            assert len(new_ids)==1
            event=after_json['calendar']['events'][next(iter(new_ids))]
            assert event['title']=='Follow-up meeting' and event['start_time']=='2024-05-19T16:00:00'
            assert event['end_time']=='2024-05-19T17:00:00' and event['status']=='confirmed'
            record['created_event']={k:event[k] for k in ('title','start_time','end_time','status')}
            record['new_event_count']=1
            record['authorized_write_executed']=any(c['name']=='create_calendar_event' and c['executed'] and not c.get('tool_error') for c in calls)
            assert record['authorized_write_executed'] and row['authorization_blocks']==0
        else:
            # Reuse the already published conservative, post-hoc audit.
            sys.path.insert(0,str(ROOT/'scripts/supplement'))
            from audit_calendar import inspect
            fact=inspect(row,folder)
            public_audit=next(r for r in csv.DictReader((ROOT/'results/metadata_supplement/posthoc_calendar_audit.csv').open()) if r['case_id']==cid)
            assert all(public_audit[k]==str(v) for k,v in fact.items())
            record['calendar_facts']=fact
            answer=row['final_answer'].lower()
            record['answer_reports_expected_count']=bool(re.search(r'\b'+str(fact['expected_appointments'])+r'\s+appointments\b',answer))
            current=[e for e in before_json['calendar']['events'].values() if e['start_time'][:10]==fact['current_day'] and e['status']!='canceled']
            record['current_event_titles_in_answer']=bool(current) and all(e['title'].lower() in answer for e in current)
            assert record['state_unchanged']
        records.append(record)
    out=ROOT/'demos/trace_checks.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(dict(schema_version=1,exporter_sha256=sha(Path(__file__)),new_model_requests=0,
                                  records=records),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':True,'selected_private_traces':len(records),'native_scores_recomputed':3,'new_model_requests':0}))

if __name__=='__main__':
    main()
