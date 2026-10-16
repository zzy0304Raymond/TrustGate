"""Compile reviewed task permissions and deterministic held-out attack cases; no LLM."""
import argparse
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from trustgate.planning import ROOT
from trustgate.formal_data import build_data
from trustgate.formal_manifest import build_formal_plan
from trustgate.runner import require_compute

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--refresh-before-launch",action="store_true")
    args=parser.parse_args()
    if (ROOT/"assignments/formal/plan.json").exists() and not args.refresh_before_launch:
        parser.error("正式清单已存在；组员不要重新生成。维护者在正式启动前显式使用 --refresh-before-launch。")
    require_compute()
    if os.environ.get('PYTHONHASHSEED')!='0':raise RuntimeError('Set PYTHONHASHSEED=0 before Python starts')
    allocation=json.loads((ROOT/'assignments/formal/allocation.json').read_text())
    tasks,attacks=build_data(allocation)
    for name,value in [('tasks',tasks),('attacks',attacks)]:
        (ROOT/f'data/formal/{name}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    plan=build_formal_plan(allocation,tasks,attacks,os.environ.get('TRUSTGATE_DETECTOR_DIR',ROOT/'models/prompt_injection_detector'))
    (ROOT/'assignments/formal/plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    config={k:v for k,v in plan['config'].items() if not k.startswith('formal_')}
    (ROOT/'configs/formal/frozen.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    for shard in plan['shards']:
        value=dict(profile='formal_v1',ready_to_run=True,plan_sha256=plan['plan_sha256'],plan_path='assignments/formal/plan.json',assignment=shard)
        (ROOT/f"assignments/formal/person-{shard['person']:02d}.json").write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(tasks=len(tasks['tasks']),attacks=len(attacks['attacks']),trials=plan['planned_cases'],plan_sha256=plan['plan_sha256'])))
if __name__=='__main__':main()
