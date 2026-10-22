"""Offline public-material checks; never calls a model or changes scores."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[2]))
from release_integrity import recorded_digest
from pathlib import Path
from decimal import Decimal
import csv,hashlib,json,re
d=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
with (d/'selection.csv').open(encoding='utf-8-sig',newline='') as f:s=list(csv.DictReader(f))
assert len(s)==12 and len({x['case_id'] for x in s})==12
assert {p.stem for p in d.glob('*.json') if re.fullmatch('[0-9a-f]{20}',p.stem)}=={x['case_id'] for x in s}
for x in s:
 e=load(d/(x['case_id']+'.json'));m=e['recorded_result'];score=e['native_scoring']
 assert e['selection']==x and e['case_id']==x['case_id']
 assert str(m['native_utility'])==x['recorded_task_success'] and m['status']==x['recorded_status']
 assert len(e['tool_call_evidence'])==m['tool_calls']
 assert sum(bool(c['tool_error']) for c in e['tool_call_evidence'])==m['tool_errors']
 assert len(e['api_usage_by_logical_call'])==m['api_calls']
 assert abs(sum(Decimal(str(u['usage']['cost'])) for u in e['api_usage_by_logical_call'])-Decimal(m['cost_usd']))<Decimal('0.000000001')
 assert score['matches_original'] and score['original']==score['offline_recheck']==all(score['basis']['predicates'].values())
 assert sum(t['role']=='tool' for t in e['transcript_excerpt'])==m['tool_calls']
b=load(d/'BATCH.json');assert b['recorded']==b['unique_case_ids']==336 and b['complete'] and b['fatal_error'] is None
assert b['cost']['actual_usage_cost_usd']=='0.72108042' and b['cost']['unique_paid_responses']==1338
r=load(d/'RECOVERY.json');assert r['offline_replay_check']['passed'] and r['offline_replay_check']['paid_model_requests']==0
assert len(r['cached_step_equality_checks'])==5 and all(x['request_equal'] and x['response_equal'] for x in r['cached_step_equality_checks'])
for line in (d/'SHA256SUMS').read_text().splitlines():
 expected,name=line.split('  ',1);assert recorded_digest(hashlib.sha256((d/name).read_bytes()).hexdigest())==expected,name
assert sorted(p.name for p in d.glob('*.csv'))==['selection.csv']
print(json.dumps({'checks':'passed','selected_cases':12,'records_missing':0,'original_scores_unchanged':True,'new_paid_api_requests':0}))
