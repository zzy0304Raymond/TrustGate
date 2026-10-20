"""Explicit bounded continuation; preserve old batch and reuse cached paid responses."""
import argparse
import asyncio
import contextlib
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts/platforms'), str(ROOT/'scripts/platforms/local')]
import person2 as original
import person2_supervisor as supervisor
from trustgate.budget import Budget
from trustgate.planning import read_plan, digest
from agentdojo.task_suite.load_suites import get_suite
from detector import Detector

STATE = ROOT/'runs/local-person2'
OLD_ID = 'local-person2-20261019-001'
NEW_ID = OLD_ID+'-resume01'
OLD = ROOT/'runs/studies'/OLD_ID/'shard-01'
NEW = ROOT/'runs/studies'/NEW_ID/'shard-01'
CHECK = STATE/'resume01-replay-check.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory():
    manifest = original.verify_prepared()
    plan = read_plan(original.PLAN)
    rows = json.loads((OLD/'results.json').read_text())
    cases = plan['shards'][1]['cases']
    original.check(len(rows)==150 and [r['case_id'] for r in rows]==[c['case_id'] for c in cases[:150]],
                   'Paused prefix changed; stop rather than repeat trials.')
    for row,case in zip(rows,cases):
        original.check(all(row.get(k)==v for k,v in case.items()), 'Old result identity mismatch.')
    budget = json.loads((OLD/'budget.json').read_text())
    original.check(not budget['halted'] and not budget['pending_reserved_usd'] and not budget['uncertain_reserved_usd'],
                   'Unresolved prior billing; do not resume.')
    trial = OLD/'151_W5_drive_edit_benign_none_r1'
    original.check(cases[150]['case_id']=='98f0051e9f3cdb5a5daf' and cases[150]['condition']=='none', 'Unexpected interrupted trial.')
    cached = []
    for step in range(1,6):
        request = trial/f'request_{step:02d}.json'
        response = trial/f'response_{step:02d}.json'
        answer = json.loads(response.read_text())
        original.check(answer['model']==plan['config']['model'] and answer['provider']==plan['config']['provider'], 'Cached routing changed.')
        cached.append((json.loads(request.read_text()), answer, max(0,response.stat().st_mtime-request.stat().st_mtime)))
    original.check(len(list(trial.glob('request_*.json')))==5 and len(list(trial.glob('response_*.json')))==5,
                   'Unexpected unrecorded requests.')
    total = sum(r['cost_usd'] for r in rows)+sum(c[1]['usage']['cost'] for c in cached)
    original.check(abs(total-budget['reported_cost_usd'])<1e-9, 'Prior recorded and cached API costs do not reconcile.')
    pause = json.loads((STATE/'pause-request.json').read_text())
    boundary = max(dt.datetime.fromisoformat(pause['signal_sent_at']).timestamp(),
                   max(p.stat().st_mtime for p in trial.glob('response_*.json')))
    elapsed = max(0,boundary-(trial/'environment_before.json').stat().st_mtime)
    files = [OLD/'results.json',OLD/'budget.json',OLD/'worker_summary.json',
             *sorted(trial.glob('request_*.json')),*sorted(trial.glob('response_*.json'))]
    info = dict(schema='trustgate_explicit_continuation_v1',original_run_id=OLD_ID,continuation_run_id=NEW_ID,
        upstream_plan_sha256=plan['plan_sha256'],local_execution_sha256=manifest['local_execution_sha256'],
        completed_prefix=150,remaining_cases=[c['case_id'] for c in cases[150:]],
        cached_response_steps=5,prior_cost_usd=budget['reported_cost_usd'],stop_budget_usd=2,
        prior_trial_elapsed_seconds=elapsed,remaining_trial_seconds=plan['config']['max_task_seconds']-elapsed,
        prior_file_sha256={str(p.relative_to(ROOT)):sha(p) for p in files},
        continuation_source_sha256=sha(__file__),supervisor_source_sha256=sha(supervisor.__file__),
        recovery='Rebuild only simulated state using the five cached responses, checking each entire outgoing '
                 'request for exact equality. Cached responses are not charged again. New API calls begin at step six. '
                 'Original trial call budget is retained; elapsed pre-pause time is deducted from its timeout. '
                 'Historical API durations for trial 151 are recovered from file timestamps and must be flagged in latency analysis.')
    original.check(info['remaining_trial_seconds']>0,'Interrupted task already exhausted its time limit.')
    info['continuation_sha256']=digest(info)
    return manifest,plan,rows,cached,info


class OfflineBoundary(RuntimeError):
    pass


class RecoveryExperiment(original.LocalExperiment):
    def __init__(self,*args,cached,info,ledger,live,**kwargs):
        super().__init__(*args,**kwargs)
        self.cached,self.info,self.ledger,self.live=cached,info,ledger,live
        self.active_index=None
        self.replayed=[]

    def case_config(self,case):
        cfg=super().case_config(case)
        if case['case_id']=='98f0051e9f3cdb5a5daf':
            cfg={**cfg,'max_task_seconds':self.info['remaining_trial_seconds']}
        return cfg

    def completion(self,messages,tools,folder,step):
        if self.active_index==151 and step<=5:
            expected,answer,seconds=self.cached[step-1]
            actual={'model':self.cfg['model'],'messages':messages,'tools':tools,'temperature':self.cfg['temperature'],
                'max_tokens':self.cfg['max_output_tokens'],'provider':{'order':[self.cfg['provider']],
                    'allow_fallbacks':False,'require_parameters':True},'stream':False}
            original.check(actual==expected, f'Replay request mismatch at step {step}; no API call made.')
            original.dump(folder/f'request_{step:02d}.json',expected)
            original.dump(folder/f'response_{step:02d}.json',answer)
            self.replayed.append(step)
            record={'seconds':seconds,'usage':answer['usage'],'provider':answer.get('provider'),
                    'model':answer['model'],'finish_reason':answer['choices'][0].get('finish_reason'),
                    'reused_prior_response':True,'timing_source':'request_response_file_timestamps'}
            return answer['choices'][0]['message'],record
        if not self.live:
            raise OfflineBoundary('Reached uncached next request; offline validation sends no API request.')
        self.ledger.reserve()
        original.dump(self.out/'budget.json',self.ledger.snapshot())
        try:
            answer,record=super().completion(messages,tools,folder,step)
            self.ledger.reconcile(record['usage']['cost'])
            return answer,record
        except BaseException:
            if self.ledger.pending:self.ledger.unknown()
            raise
        finally:
            original.dump(self.out/'budget.json',self.ledger.snapshot())

    async def run_case(self,case,index):
        self.active_index=index
        row=await super().run_case(case,index)
        if index==151:
            row['seconds']+=self.info['prior_trial_elapsed_seconds']
            row['continuation_recovery']={'cached_steps':self.replayed,'prior_cost_included_once':True,
                'api_seconds_from_file_timestamps':True,'prior_active_seconds':self.info['prior_trial_elapsed_seconds']}
            original.dump(Path(row['result_dir'])/'summary.json',row)
            original.dump(self.out/'results.json',self.rows)
        return row


async def validate():
    manifest,plan,rows,cached,info=inventory()
    out=STATE/('replay-validation-'+str(time.time_ns()))
    out.mkdir()
    experiment=RecoveryExperiment(plan['config'],out,get_suite('v1.2.2','workspace'),None,'offline-replay-only',
        cached=cached,info=info,ledger=None,live=False)
    async with contextlib.AsyncExitStack() as stack:
        await experiment.start(stack)
        row=await experiment.run_case(plan['shards'][1]['cases'][150],151)
    original.check(experiment.replayed==[1,2,3,4,5], 'Not all paid responses replayed identically.')
    original.check(row['error'] and row['error']['type']=='OfflineBoundary', 'Replay did not reach the exact continuation boundary.')
    report=dict(passed=True,paid_model_requests=0,cached_steps_verified=5,
        continuation_sha256=info['continuation_sha256'],next_live_step=6,case_id=row['case_id'])
    original.dump(CHECK,report)
    return report


async def run():
    manifest,plan,rows,cached,info=inventory()
    verified=json.loads(CHECK.read_text())
    original.check(verified['passed'] and verified['continuation_sha256']==info['continuation_sha256'],'Replay validation stale.')
    NEW.mkdir(parents=True)
    original.dump(NEW/'local-manifest.json',manifest)
    original.dump(NEW/'continuation-manifest.json',info)
    original.dump(NEW/'plan.json',plan)
    cfg={**plan['config'],'max_total_cost_usd':2.0}
    original.dump(NEW/'config.json',cfg)
    original.dump(NEW/'results.json',rows)
    ledger=Budget(2.0,cfg['per_request_reservation_usd'])
    ledger.reported=info['prior_cost_usd']
    original.dump(NEW/'budget.json',ledger.snapshot())
    original.dump(STATE/'latest.json',{'run_id':NEW_ID,'folder':str(NEW),'original_run_id':OLD_ID})
    experiment=None;fatal=None;started=time.monotonic()
    try:
        experiment=RecoveryExperiment(cfg,NEW,get_suite(cfg['benchmark'],cfg['suite']),
            Detector(original.DETECTOR,cfg['classifier_threshold']),original.get_key(),
            cached=cached,info=info,ledger=ledger,live=True)
        experiment.rows=copy.deepcopy(rows)
        async with contextlib.AsyncExitStack() as stack:
            await experiment.start(stack)
            for index,case in enumerate(plan['shards'][1]['cases'][150:],151):
                row=await experiment.run_case(case,index)
                original.dump(NEW/'progress.json',{'recorded':len(experiment.rows),'planned':336,'budget':ledger.snapshot()})
                if ledger.halted or (row['error'] and row['error']['type'] in
                    ('HTTPError','URLError','TimeoutError','BudgetExceeded','BrokenResourceError','EndOfStream','RuntimeError')):
                    fatal=row['error'] or {'type':'BudgetHalted','message':'Uncertain cost; stopped.'}
                    break
    except BaseException as exc:
        fatal={'type':type(exc).__name__,'message':str(exc).replace(original.get_key(),'[REDACTED]')}
    finally:
        current=experiment.rows if experiment else rows
        original.dump(NEW/'worker_summary.json',dict(execution_mode='local',shard_index=1,planned=336,
            recorded=len(current),complete=len(current)==336 and fatal is None,fatal_error=fatal,
            upstream_plan_sha256=plan['plan_sha256'],local_execution_sha256=manifest['local_execution_sha256'],
            continuation_sha256=info['continuation_sha256'],budget=ledger.snapshot(),
            wall_seconds=json.loads((OLD/'worker_summary.json').read_text())['wall_seconds']+time.monotonic()-started,
            continuation_wall_seconds=time.monotonic()-started))
    original.check(fatal is None,'Continuation stopped; preserve all records, no automatic retry.')


def watch():
    env={**os.environ,'PYTHONHASHSEED':'0','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2',
         'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
    with (STATE/'resume01-runner.log').open('x') as log:
        process=subprocess.Popen(['/usr/bin/caffeinate','-i',sys.executable,str(Path(__file__).resolve()),'run'],
            cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        original.dump(STATE/'resume-process.json',dict(run_id=NEW_ID,original_run_id=OLD_ID,
            supervisor_pid=os.getpid(),runner_pid=process.pid,started_at=supervisor.now()))
        while True:
            supervisor.refresh(NEW_ID,process)
            if process.poll() is not None:break
            time.sleep(30)
    report=supervisor.refresh(NEW_ID,process)
    if report['complete']:
        original.export_local(NEW,ROOT/'output')
        receipt=json.loads((ROOT/'output/local-receipt.json').read_text())
        receipt['continuation']=json.loads((NEW/'continuation-manifest.json').read_text())
        # File names and hashes only; no prompts or private backend state are exported.
        original.dump(ROOT/'output/local-receipt.json',receipt)
        (ROOT/'output/PROGRESS.md').write_text('# 第2人本地实验交付\n\n336个唯一ID均已记录。150条原记录原样保留；'
            '第151条通过逐步校验缓存响应恢复，前5次API不重复调用。后续只运行原清单剩余部分。'
            '全部费用累计统计。第151条旧API耗时由文件时间恢复，延迟分析需标注。'
            '本地结果等待本人检查及全组平台验收，未上传GitHub。\n',encoding='utf-8')
    original.dump(STATE/'resume-exit.json',dict(run_id=NEW_ID,finished_at=supervisor.now(),
        runner_returncode=process.returncode,complete=report['complete'],recorded=report['recorded']))


def start():
    manifest,plan,rows,cached,info=inventory()
    check=json.loads(CHECK.read_text())
    original.check(check['passed'] and check['continuation_sha256']==info['continuation_sha256'],'Validate offline first.')
    lock=STATE/'resume01-start.json'
    original.check(not lock.exists() and not NEW.exists(),'Continuation already claimed; do not start twice.')
    with lock.open('x') as stream:json.dump(info,stream,ensure_ascii=False,indent=2)
    shutil.copy2(__file__,ROOT/'output/platform-local/person2_resume.py')
    with (ROOT/'output/ENVIRONMENT.md').open('a') as stream:
        stream.write('\n## Explicit continuation after user pause\n\n'
            f'- Continuation run: `{NEW_ID}`\n- Continuation manifest: `{info["continuation_sha256"]}`\n'
            '- Original 150 records retained unchanged. Trial 151 restores its first five paid responses only '
            'after exact request comparison in a no-API replay. Subsequent calls retain the original 8-call budget.\n'
            '- Total USD 2 cap includes prior USD 0.34221672. Cached responses are not billed twice.\n'
            '- Trial 151 latency includes pre-pause active time; old API durations use file timestamps and '
            'must be flagged in statistical latency comparisons. Pause duration is excluded.\n')
    paused=ROOT/'output/PAUSED.txt'
    if paused.exists():paused.rename(ROOT/'output/PAUSED_history_1542.txt')
    (ROOT/'output/RESUMED.txt').write_text('已按用户指令续跑。前150条不重跑；第151条复用已付费的缓存响应恢复；'
        '其后仅运行未完成部分。费用包含暂停前的累计消费。\n',encoding='utf-8')
    env={**os.environ,'PYTHONHASHSEED':'0','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2'}
    with (STATE/'resume01-supervisor.log').open('x') as log:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'watch'],cwd=ROOT,env=env,
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    print(json.dumps({'started':True,'run_id':NEW_ID,'supervisor_pid':process.pid,'prior_cost_usd':info['prior_cost_usd']}))


if __name__=='__main__':
    os.umask(0o077)
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('validate','start','watch','run'));args=parser.parse_args()
    if args.command=='validate':print(json.dumps(asyncio.run(validate()),ensure_ascii=False,indent=2))
    elif args.command=='start':start()
    elif args.command=='watch':watch()
    else:asyncio.run(run())
