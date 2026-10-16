"""Merge only matching manifests; incomplete experiments cannot silently look complete."""
import csv
import json
from pathlib import Path
from .planning import read_plan

def merge_results(plan_path, run_root, allow_partial=False):
    plan = read_plan(plan_path)
    root = Path(run_root)
    rows, seen, absent, unfinished = [], set(), [], []
    budgets = []
    source_versions = set()
    expected = {c['case_id']: (s['index'], c) for s in plan['shards'] for c in s['cases']}
    for shard in plan['shards']:
        folder = root / ('shard-%02d' % shard['index'])
        if not (folder/'manifest.json').exists():
            absent.append(shard['index']); continue
        manifest = json.loads((folder/'manifest.json').read_text())
        if not manifest.get('source_sha256'):
            raise ValueError('Worker source hashes are missing.')
        source_versions.add(json.dumps(manifest['source_sha256'], sort_keys=True))
        if len(source_versions) > 1:
            raise ValueError('Workers used different source versions.')
        if plan.get('source_sha256') and manifest['source_sha256']!=plan['source_sha256']:
            raise ValueError('Worker code differs from the frozen plan.')
        if manifest['plan_sha256'] != plan['plan_sha256'] or manifest['shard_index'] != shard['index']:
            raise ValueError('Worker used another plan or shard index.')
        if not (folder/'worker_summary.json').exists():
            unfinished.append(shard['index'])
        else:
            worker = json.loads((folder/'worker_summary.json').read_text())
            if worker.get('complete') is False or worker.get('fatal_error') or (plan['profile'].startswith('formal_') and worker.get('complete') is not True):
                unfinished.append(shard['index'])
            if worker.get('budget'):
                budgets.append(worker['budget'])
        for row in json.loads((folder/'results.json').read_text()) if (folder/'results.json').exists() else []:
            cid = row['case_id']
            if cid in seen or cid not in expected or expected[cid][0] != shard['index']:
                raise ValueError('Duplicate, foreign, or incorrectly assigned case: '+cid)
            case = expected[cid][1]
            for field in ('workflow','task','surface','condition','repeat','transport'):
                if row[field] != case[field]:
                    raise ValueError('Result identity differs from manifest: '+cid)
            for field in ('slot_id','attack_case_id','split'):
                if field in case and row.get(field)!=case[field]:
                    raise ValueError('Formal result identity differs: '+cid)
            seen.add(cid); rows.append(row)
    missing = sorted(set(expected)-seen)
    if (missing or unfinished) and not allow_partial:
        raise ValueError(f'Incomplete study: {len(missing)} missing results; unfinished workers {unfinished}. Use --allow-partial only for monitoring.')
    rows.sort(key=lambda row: row['case_id'])
    summary = dict(plan_sha256=plan['plan_sha256'], planned=len(expected), recorded=len(rows),
                   complete=not missing and not unfinished, absent_shards=absent, unfinished_shards=unfinished,
                   missing_case_ids=missing, api_calls=sum(r['api_calls'] for r in rows),
                   reported_cost_usd=sum(r['cost_usd'] for r in rows),
                   sum_task_seconds=sum(r['seconds'] for r in rows),
                   task_passes=sum(r['native_utility'] is True for r in rows),
                   attack_successes=sum(r['attacker_success'] is True for r in rows))
    if budgets:
        summary['result_rows_cost_usd'] = summary['reported_cost_usd']
        summary['reported_cost_usd'] = sum(b['reported_cost_usd'] for b in budgets)
        summary['uncertain_reserved_usd'] = sum(b.get('uncertain_reserved_usd', 0)+b.get('pending_reserved_usd', 0) for b in budgets)
        summary['cost_accounting_complete'] = len(budgets)==len(plan['shards']) and summary['uncertain_reserved_usd']==0 and abs(summary['reported_cost_usd']-summary['result_rows_cost_usd']) < 1e-9
    output = root/'merged'; output.mkdir(exist_ok=True)
    (output/'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    fields = ['case_id','workflow','task','surface','condition','repeat','transport','status','native_utility','attacker_success','safe_completion','injection_point_reached','injection_reached_model','seconds','api_calls','cost_usd','result_dir']
    with (output/'results.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)
    return summary
