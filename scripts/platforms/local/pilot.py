"""Four held-out development cases, $0.20 cap; never execute formal test IDs."""
import argparse
import asyncio
import copy
import json
import sys
from pathlib import Path
from runtime import ROOT, verify, write_json
from trustgate.planning import digest, read_plan


def build_plan(development, formal):
    if development['profile'] != 'formal_development_v1':
        raise ValueError('Expected the existing development split')
    plan = copy.deepcopy(development)
    selected = plan['shards'][2]['cases']
    formal_ids = {c['case_id'] for s in formal['shards'] for c in s['cases']}
    formal_tasks = set(formal['config']['formal_tasks'])
    if len(selected) != 4 or any(c['split'] != 'development' or c['task'] in formal_tasks or c['case_id'] in formal_ids for c in selected):
        raise ValueError('Pilot must use four development-only cases')
    for field in ('source_sha256', 'packages', 'detector_sha256'):
        if development[field] != formal[field]:
            raise ValueError('Development runtime differs from formal freeze')
    for shard in plan['shards']:
        if shard['index'] != 2:
            shard.update(cases=[], budget_usd=0, estimated_seconds=0)
        else:
            shard['budget_usd'] = 0.20
    plan.update(planned_cases=4, budget_usd=0.20,
        parent_development_sha256=development['plan_sha256'], parent_formal_sha256=formal['plan_sha256'],
        note='Local paid readiness probe only. Four development cases, max 32 model calls, $0.20 stop budget. Never pool with formal results.')
    plan['config']['max_total_cost_usd'] = 0.20
    plan['plan_sha256'] = digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
    from trustgate.formal_manifest import validate_formal_plan
    return validate_formal_plan(plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detector-dir', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    from run import execute, experiment_class
    from api_check import probe
    from trustgate.runner import get_key
    formal = verify(ROOT / 'assignments/formal/plan.json', args.detector_dir)
    development = read_plan(ROOT / 'configs/development/readiness-plan.json')
    plan = build_plan(development, formal)
    path = ROOT / 'runs/plans' / (args.run_id + '.json')
    import re
    if not re.fullmatch(r'local-pilot-[A-Za-z0-9_.-]{1,64}', args.run_id):
        raise ValueError('Use a filename-safe local-pilot- run ID')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if read_plan(path)['plan_sha256'] != plan['plan_sha256']:
            raise ValueError('Existing pilot manifest differs')
    else:
        write_json(path, plan)
    print(json.dumps(dict(manifest=str(path), plan_sha256=plan['plan_sha256'], cases=4,
                         max_model_calls=32, stop_budget_usd=0.20)), flush=True)
    if not args.execute:
        return
    sys.path.insert(0, str(ROOT / 'experiments/mvp'))
    from agentdojo.task_suite.load_suites import get_suite
    from detector import Detector
    key = get_key()
    print(json.dumps(probe(key)), flush=True)
    suite = get_suite(plan['config']['benchmark'], plan['config']['suite'])
    detector = Detector(args.detector_dir, plan['config']['classifier_threshold'])
    result = asyncio.run(execute(plan, args.detector_dir, args.run_id, ROOT / 'runs/local-pilots',
                                 key, experiment_class(), suite, detector))
    print(result)


if __name__ == '__main__':
    main()
