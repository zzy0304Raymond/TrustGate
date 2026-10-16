"""Export a complete worker's allowlisted measurements, never prompts or backend data."""
import csv
import json
from pathlib import Path
from .planning import read_plan

PUBLIC_FIELDS=('case_id','slot_id','attack_case_id','split','workflow','task','surface','condition','repeat','transport',
               'status','native_utility','attacker_success','safe_completion','injection_point_reached','injection_reached_model',
               'seconds','api_calls','api_seconds','cost_usd','prompt_tokens','completion_tokens','tool_calls','tool_errors',
               'authorization_blocks','authorization_checks','metadata_quarantines','metadata_examined',
               'benign_metadata_quarantines','benign_metadata_examined','detector_seconds','cross_server_write_calls')

def export_delivery(plan_path,folder,destination):
    plan=read_plan(plan_path);folder=Path(folder);destination=Path(destination)
    manifest=json.loads((folder/'manifest.json').read_text());worker=json.loads((folder/'worker_summary.json').read_text())
    if manifest['plan_sha256']!=plan['plan_sha256'] or manifest['source_sha256']!=plan['source_sha256']:raise ValueError('Version mismatch')
    if not worker['complete'] or worker['fatal_error']:raise ValueError('Worker incomplete; retain its private files and diagnose first')
    shard=plan['shards'][manifest['shard_index']];expected={c['case_id']:c for c in shard['cases']}
    rows=json.loads((folder/'results.json').read_text())
    if len(rows)!=len(expected) or {r['case_id'] for r in rows}!=set(expected):raise ValueError('Worker coverage mismatch')
    clean=[]
    for row in rows:
        case=expected[row['case_id']]
        for key in ('task','surface','condition','repeat','slot_id','attack_case_id','split'):
            if row.get(key)!=case.get(key):raise ValueError('Result identity mismatch')
        clean.append({**{key:row.get(key) for key in PUBLIC_FIELDS},'error_type':row.get('error',{}).get('type') if row.get('error') else None})
    destination.mkdir(parents=True,exist_ok=True)
    for name in ('results.csv','receipt.json'):
        if (destination/name).exists():raise FileExistsError('Refusing to overwrite an existing delivery: '+name)
    with (destination/'results.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=[*PUBLIC_FIELDS,'error_type']);writer.writeheader();writer.writerows(clean)
    receipt={'plan_sha256':plan['plan_sha256'],'source_sha256':manifest['source_sha256'],'shard_index':shard['index'],
             'person':shard.get('person',shard['index']+1),'recorded':len(rows),'complete':True,'budget':worker['budget'],
             'packages':manifest['packages'],'wall_seconds':worker['wall_seconds'],
             'data_scope':'Allowlisted numeric/categorical metrics only. Full traces remain private.'}
    (destination/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    return {'destination':str(destination),'recorded':len(rows),'plan_sha256':plan['plan_sha256']}
