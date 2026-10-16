"""Commands are intentionally explicit: planning never calls an LLM."""
import argparse
import asyncio
import json
from pathlib import Path
from .planning import ROOT, build_plan, read_plan
from .merge import merge_results

def main():
    parser = argparse.ArgumentParser(prog='python -m trustgate')
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan', help='Write a deterministic pilot manifest; no API calls')
    plan.add_argument('--config', type=Path, default=ROOT/'configs/mvp/pilot.json')
    plan.add_argument('--workers', type=int, default=5)
    plan.add_argument('--budget-usd', type=float, default=1.0)
    plan.add_argument('--output', type=Path, default=ROOT/'runs/plans/pilot-five.json')
    inspect = commands.add_parser('inspect', help='Validate and summarize a manifest')
    inspect.add_argument('--plan', type=Path, required=True)
    run = commands.add_parser('run', help='Execute one worker; requires PBS and Group 9 API access')
    run.add_argument('--plan', type=Path, required=True)
    run.add_argument('--shard-index', type=int, required=True)
    run.add_argument('--run-id', required=True)
    run.add_argument('--output-root', type=Path)
    run.add_argument('--detector-dir', type=Path)
    merge = commands.add_parser('merge', help='Validate identity/coverage and merge worker results')
    merge.add_argument('--plan', type=Path, required=True)
    merge.add_argument('--run-root', type=Path, required=True)
    merge.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    if args.command == 'plan':
        result = build_plan(json.loads(args.config.read_text()), args.workers, args.budget_usd)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(f'Plan saved: {args.output}; {result["planned_cases"]} cases, {result["workers"]} workers; no model calls.')
    elif args.command == 'inspect':
        result = read_plan(args.plan)
        print(json.dumps(dict(plan_sha256=result['plan_sha256'], total_cases=result['planned_cases'],
              workers=[{k:s[k] for k in ('index','estimated_seconds','budget_usd')} | {'cases':len(s['cases'])} for s in result['shards']]), indent=2))
    elif args.command == 'run':
        from .runner import run_shard
        print(asyncio.run(run_shard(args.plan, args.shard_index, args.run_id, args.output_root, args.detector_dir)))
    else:
        print(json.dumps(merge_results(args.plan, args.run_root, args.allow_partial), indent=2))

if __name__ == '__main__':
    main()
