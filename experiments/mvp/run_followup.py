"""Eighteen separate development trials motivated by failures in the frozen pilot."""
import asyncio,contextlib,datetime,hashlib,importlib.metadata,json,os,platform,random,socket,time
from pathlib import Path
import run_matrix_v2 as runner
from detector import Detector
ROOT=runner.ROOT

async def main():
    if not os.environ.get('PBS_JOBID') or platform.python_version()!='3.10.20':raise SystemExit('PBS/Python requirement')
    os.umask(0o077)
    plan=json.loads((ROOT/'configs/mvp/followup.json').read_text());cfg=json.loads((ROOT/'configs/mvp/pilot.json').read_text());cfg['execution_stage']='followup';cfg['max_total_cost_usd']=0.15
    tag=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+os.environ['PBS_JOBID']+'_followup'
    out=ROOT/'runs/mvp'/tag;out.mkdir();runner.dump(out/'config.json',cfg);runner.dump(out/'followup_plan.json',plan)
    manifest={'host':socket.gethostname(),'pbs_job_id':os.environ['PBS_JOBID'],'python':platform.python_version(),'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}};runner.dump(out/'manifest.json',manifest)
    snapshot=out/'source_snapshot';snapshot.mkdir()
    for p in Path(__file__).parent.glob('*.py'):(snapshot/p.name).write_bytes(p.read_bytes())
    start=time.monotonic();suite=runner.get_suite('v1.2.2','workspace');detector=Detector(ROOT/'models/prompt_injection_detector',cfg['classifier_threshold']);key=(ROOT/'.secrets/openrouter_group9.key').read_text().strip()
    experiment=runner.Experiment(cfg,out,suite,detector,key);base_loader=runner.load_system_message;base_authorize=runner.authorize
    def explanatory_authorize(policy,name,args):
        ok,reason=base_authorize(policy,name,args)
        if not ok and name in policy['writes']:
            reason += '; permitted constraints from the user request: '+json.dumps(policy['writes'][name])
        return ok,reason
    matrix=[]
    for variant in ['normal_prompt_repair','metadata_dependency_probe','json_recovery']:
        for condition in ['none','trustgate']:
            for repeat in range(1,4):matrix.append({'variant':variant,'workflow':{'normal_prompt_repair':'W4_calendar_write','metadata_dependency_probe':'W1_calendar_read','json_recovery':'W5_drive_edit'}[variant],'task':plan[variant]['task'],'surface':'metadata' if variant=='metadata_dependency_probe' else 'benign','condition':condition,'repeat':repeat,'transport':'mcp'})
    random.Random(4214).shuffle(matrix);runner.dump(out/'matrix.json',matrix)
    async with contextlib.AsyncExitStack() as stack:
        await experiment.start(stack)
        for i,case in enumerate(matrix,1):
            variant=plan[case['variant']];extra=variant.get('extra_system_text','')
            runner.load_system_message=lambda x,extra=extra:base_loader(x)+extra
            runner.authorize=explanatory_authorize if case['variant']=='normal_prompt_repair' else base_authorize
            experiment.cfg={**cfg,'payload':variant.get('payload',cfg['payload'])}
            row=await experiment.run_case(case,i)
            runner.dump(Path(row['result_dir'])/'followup_configuration.json',variant)
    runner.load_system_message=base_loader;runner.authorize=base_authorize
    runner.dump(out/'batch_summary.json',{'planned_runs':18,'completed_records':len(experiment.rows),'wall_seconds':time.monotonic()-start,'sum_task_seconds':sum(r['seconds'] for r in experiment.rows),'reported_api_cost_usd':experiment.total_cost})
    print('FOLLOWUP_RESULT '+str(out),flush=True)

if __name__=='__main__':asyncio.run(main())
