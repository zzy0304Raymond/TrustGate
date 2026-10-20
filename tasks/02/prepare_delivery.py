"""Prepare/recheck the person-02 sanitized delivery. Never starts an experiment."""
import argparse
import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'experiments/deliveries/person-02'
sys.path.insert(0,str(ROOT))
from trustgate.planning import read_plan
from trustgate.delivery import PUBLIC_FIELDS


def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def rows_from(path):
    with path.open(newline='') as stream:return list(csv.DictReader(stream))
def money(value):return format(Decimal(value).quantize(Decimal('0.00000001')),'f')
def validated_delivery(folder, manifest_path, plan_sha):
    """Match the published dataset manifest to the exact delivery files and plan."""
    if not manifest_path.exists():
        return False
    manifest = load(manifest_path)
    if manifest.get('schema_version') != 1 or manifest.get('plan_sha256') != plan_sha:
        return False
    people = [p for p in manifest.get('shards', []) if p.get('person') == 2]
    if len(people) != 1 or people[0].get('recorded') != 336:
        return False
    actual = {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
    if actual != people[0].get('delivery_sha256'):
        raise ValueError('Person-02 files differ from the published dataset manifest')
    return True

def csv_write(path,rows):
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=[*PUBLIC_FIELDS,'error_type'],lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def prepare():
    source=ROOT/'output';receipt=load(source/'local-receipt.json');worker=receipt['worker'];manifest=receipt['manifest']
    audit=load(source/'AUDIT_REPORT.json');plan=read_plan(ROOT/'assignments/formal/plan.json')
    assert worker['complete'] and worker['fatal_error'] is None and worker['recorded']==336
    assert manifest['upstream_plan_sha256']==plan['plan_sha256']
    assert manifest['source_sha256']==plan['source_sha256']
    assert not audit['integrity']['native_score_mismatches'] and not audit['integrity']['attack_score_mismatches']
    rows=rows_from(source/'results.csv');cases=plan['shards'][1]['cases']
    assert len(rows)==336 and [r['case_id'] for r in rows]==[c['case_id'] for c in cases]
    DEST.mkdir(parents=True,exist_ok=True)
    csv_write(DEST/'results.csv',rows)
    for name in ('local-receipt.json','ENVIRONMENT.md','AUDIT_REPORT.json','verification.json'):
        shutil.copy2(source/name,DEST/name)
    shutil.copy2(source/'结果复核与问题说明.txt',DEST/'AUDIT_ZH.txt')
    delivered_audit=load(DEST/'AUDIT_REPORT.json')
    delivered_audit['submission_format_update']={'standard_receipt_added':True,'original_local_receipt_retained':True,'platform_review':'pending','note':'Original audit in output is preserved. This submission now includes standard receipt fields with truthful local-platform provenance; parser readability does not approve Vanda equivalence.'}
    delivered_audit['issues'][0]['finding']='Mac Torch 2.7.1 and local execution differ from Vanda. A standard-field receipt.json is now supplied with actual package versions and explicit pending_team_platform_review; local-receipt.json remains unchanged. Standard collector readability does not validate platform equivalence.'
    write_json(DEST/'AUDIT_REPORT.json',delivered_audit)
    audit_text=(DEST/'AUDIT_ZH.txt').read_text()
    audit_text=audit_text.replace('标准正式交付收集器寻找receipt.json，目前本地提供local-receipt.json，不会被自动当作原Vanda交付读入。','原审计时仅有local-receipt.json；本提交另生成标准字段receipt.json，明确保留实际Mac包版本和待平台审核状态。原local-receipt保持不变。共享汇总程序可读取，不代表平台已通过验收。')
    (DEST/'AUDIT_ZH.txt').write_text(audit_text,encoding='utf-8')
    before=sum((Decimal(x['cost_usd']) for x in rows[:150]),Decimal(0))
    after=sum((Decimal(x['cost_usd']) for x in rows[150:]),Decimal(0))
    prior=Decimal(str(receipt['continuation']['prior_cost_usd'])).quantize(Decimal('0.00000001'))
    total=Decimal(audit['integrity']['actual_cost_usd'])
    cached=prior-before
    assert abs(before+after-total)<Decimal('0.000000001')
    recovery={'original_run_id':receipt['continuation']['original_run_id'],
        'continuation_run_id':receipt['continuation']['continuation_run_id'],
        'before_pause_recorded':150,'after_resume_recorded':186,'combined_unique_records':336,
        'partition_basis':'Original row indices 1-150 and 151-336 within the single results.csv. Separate partition backups remain private locally.',
        'interrupted_trial':{'index':151,'case_id':rows[150]['case_id'],'status':rows[150]['status'],
            'cached_paid_responses_reused':5,'new_live_requests_begin_at_step':6,
            'max_model_calls_including_cached':8,'cached_cost_usd':money(cached),
            'cached_requests_and_responses_compared_exactly':True,
            'historical_api_duration_source':'file timestamps; flag/exclude this trial in latency sensitivity analysis'},
        'original150_unchanged':True,'continuation_sha256':receipt['continuation']['continuation_sha256'],
        'previous_attempt_preserved':True,'retries_until_success':False,
        'evidence':'Original private run, pause-request, replay-check and continuation manifests retained locally; raw requests are not public.'}
    write_json(DEST/'RECOVERY.json',recovery)
    accounting={'currency':'USD','basis':'Actual API usage.cost, unique response IDs; no estimate or manual release of reservations.',
        'total_api_cost_usd':money(total),'before_pause_recorded150_cost_usd':money(before),
        'interrupted_trial_paid_before_pause_usd':money(cached),'charged_before_pause_usd':money(prior),
        'after_resume186_row_cost_usd':money(after),'new_api_charges_after_resume_usd':money(total-prior),
        'row_partition_note':'The after-resume row partition includes the already-paid cached part of trial151. It is not an extra charge.',
        'unique_api_responses':1338,'copied_cached_response_files_not_charged_again':5,
        'pending_reserved_usd':0,'uncertain_reserved_usd':0,'stop_budget_usd':2}
    write_json(DEST/'ACCOUNTING.json',accounting)
    adapters={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'scripts/platforms/local').iterdir()) if p.is_file()}
    for name in ('person2_supervisor.py','person2_resume.py'):
        p=ROOT/'scripts/platforms'/name;adapters[str(p.relative_to(ROOT))]=sha(p)
    standard={'plan_sha256':plan['plan_sha256'],'source_sha256':manifest['source_sha256'],
        'shard_index':1,'person':2,'recorded':336,'complete':True,'budget':worker['budget'],
        'packages':manifest['packages'],'wall_seconds':worker['wall_seconds'],
        'data_scope':'Allowlisted numeric/categorical metrics only. Full traces remain private.',
        'receipt_format':'Standard measurement fields plus explicit local-platform and recovery provenance; not a Vanda approval.',
        'execution_mode':'local_macos','platform':{'system':manifest['system'],'machine':manifest['machine'],
            'os_release':manifest['os_release'],'python':manifest['python'],'scheduler':None,'detector_device':'cpu'},
        'local_execution_sha256':manifest['local_execution_sha256'],'adapter_sha256':adapters,
        'continuation_sha256':receipt['continuation']['continuation_sha256'],
        'acceptance':{'status':'pending_team_platform_review','vanda_validated':False,
            'matches_published_package_pins':False,'differences':['Native torch 2.7.1 rather than 2.7.1+cu126','Local adapter without PBS','Explicit cached-response continuation after a user pause'],
            'warning':'The existing summary collector only checks source/plan identity, not platform approval. Review this acceptance block before pooling results.'},
        'cost_accounting':'Exact total $0.72108042; see ACCOUNTING.json. No duplicated cache billing.',
        'recovery_provenance':'RECOVERY.json and original local-receipt.json retained.',
        'latency_note':'Trial151 historical API durations recovered from file timestamps. Worker wall_seconds is summed active worker periods, excluding the pause.'}
    write_json(DEST/'receipt.json',standard)
    readme='''# Person 02 delivery — local Mac, pending platform review

This delivery provides the original assigned 336 unique trial records and exact total API cost **$0.72108042**. All failures remain. There were 168 native task passes, 20 model-call-budget stops and two denial-budget stops; Python exception rows are zero.

## Data and pause recovery

- `results.csv`: canonical 336-row dataset, normalized to LF without changing field values.
- This delivery contains exactly one result CSV. Before-pause and after-resume partition backups remain private locally.
- `ACCOUNTING.json`: distinguishes logical row partitions from when API charges occurred. The recovered trial's five cached responses were paid before the pause and are included exactly once.
- `RECOVERY.json`: trial151 exact-request replay, preserved eight-call/time bounds and latency caveat. Original private attempt remains intact.

## Receipts and required review

`receipt.json` supplies standard measurement fields so the shared tooling can read the data. It explicitly records **actual Mac/CPU Torch 2.7.1, no PBS, pending team review**, plus adapter and continuation hashes. This is a newly generated truthful measurement receipt, not a renamed or falsified Vanda credential. The original `local-receipt.json` remains alongside it.

The existing summary collector checks plan/source identity but does not enforce platform approval. Its ability to read this receipt must not be interpreted as Vanda acceptance. Team review remains required before pooling or merging. Frozen source, payloads, permissions, task IDs, detector weights and model/provider are unchanged.

## Validation and limitations

Run `python tasks/02/prepare_delivery.py --check` for identity, partition, cost, hashes and privacy checks. Add `--require-platform-approved` to test the acceptance gate; it intentionally fails while team platform review is pending.

`AUDIT_REPORT.json` and `AUDIT_ZH.txt` preserve the observed false-positive classifier, native grading limitations, weak unprotected attack baseline and trial151 timing warning. Zero attack success in a cell does not establish general defense superiority.

Credentials, model weights, full dialogues, simulated email/file states and private logs are excluded. Nothing is uploaded automatically. PR review and main merge remain human actions.
'''
    (DEST/'README.md').write_text(readme,encoding='utf-8')
    with (DEST/'ENVIRONMENT.md').open('a',encoding='utf-8') as stream:
        stream.write('\n## Submission-format receipt\n\n`receipt.json` is generated from the verified completed measurements with actual Mac package versions and an explicit pending-team-review acceptance block. `local-receipt.json` is preserved unchanged. Standard parser compatibility does not certify Vanda equivalence.\n')
    files=[p for p in DEST.rglob('*') if p.is_file() and p.name!='SHA256SUMS']
    (DEST/'SHA256SUMS').write_text('\n'.join(sha(p)+'  '+str(p.relative_to(DEST)) for p in sorted(files))+'\n')
    return check(False)


def check(require_approval):
    plan=read_plan(ROOT/'assignments/formal/plan.json');receipt=load(DEST/'receipt.json');rows=rows_from(DEST/'results.csv')
    before,after=rows[:150],rows[150:]
    assert len(before)==150 and len(after)==186 and len(rows)==336
    assert list(DEST.rglob('*.csv'))==[DEST/'results.csv'], 'Only the canonical results.csv belongs in the public delivery'
    cases=plan['shards'][1]['cases'];assert [r['case_id'] for r in rows]==[c['case_id'] for c in cases]
    assert len({r['case_id'] for r in rows})==336
    for row,case in zip(rows,cases):
        for key in ('task','surface','condition','repeat','slot_id','attack_case_id','split'):
            assert row[key]==('' if case.get(key) is None else str(case[key])),(row['case_id'],key)
    assert receipt['plan_sha256']==plan['plan_sha256'] and receipt['source_sha256']==plan['source_sha256']
    assert receipt['complete'] and receipt['recorded']==336 and receipt['person']==2 and receipt['shard_index']==1
    cost=sum((Decimal(row['cost_usd']) for row in rows),Decimal(0));accounting=load(DEST/'ACCOUNTING.json')
    assert money(cost)==accounting['total_api_cost_usd']=='0.72108042'
    assert money(sum((Decimal(row['cost_usd']) for row in before),Decimal(0)))==accounting['before_pause_recorded150_cost_usd']
    assert money(sum((Decimal(row['cost_usd']) for row in after),Decimal(0)))==accounting['after_resume186_row_cost_usd']
    assert not receipt['budget']['pending_reserved_usd'] and not receipt['budget']['uncertain_reserved_usd']
    for line in (DEST/'SHA256SUMS').read_text().splitlines():
        expected,name=line.split('  ',1);assert sha(DEST/name)==expected,name
    forbidden={'messages','final_answer','trajectory','result_dir','raw_result','state_path','request','response'}
    assert not forbidden.intersection(rows[0])
    files=[p for p in DEST.rglob('*') if p.is_file()]
    secret=ROOT/'.secrets/openrouter_group9.key'
    if secret.exists():
        value=secret.read_text().strip().encode();assert all(value not in p.read_bytes() for p in files)
    assert not any(p.suffix in ('.key','.pickle') or p.name.startswith(('request_','response_','trajectory')) for p in files)
    accepted = validated_delivery(DEST, ROOT/'results/formal/manifest.json', plan['plan_sha256'])
    if require_approval and not accepted:
        raise SystemExit('Person-02 delivery does not match a published dataset manifest.')
    return {'structural_checks':'passed','records':336,'before_pause_rows':150,'after_resume_rows':186,
        'cost_usd':money(cost),'receipt_format':'standard_fields_with_explicit_local_platform_provenance',
        'dataset_manifest':'matched' if accepted else 'unavailable_or_mismatched',
        'network_write_performed_by_this_command':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--require-validated','--require-platform-approved',dest='require_validated',action='store_true',help='Require exact agreement with the published dataset manifest.');args=parser.parse_args()
    result=check(args.require_validated) if args.check else prepare()
    print(json.dumps(result,ensure_ascii=False,indent=2))
