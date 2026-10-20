"""Summarize person 3 with local denominators, using the original statistics code."""
import csv
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from trustgate.planning import read_plan, CONDITIONS


def main():
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    shard = plan['shards'][2]
    directory = ROOT / 'experiments/deliveries/person-03'
    with (directory / 'results.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    expected = {c['case_id']: c for c in shard['cases']}
    if len(rows) != 336 or {r['case_id'] for r in rows} != set(expected):
        raise ValueError('This report requires all 336 unique person-3 records')
    numeric = {'seconds', 'api_calls', 'api_seconds', 'cost_usd', 'prompt_tokens', 'completion_tokens',
               'tool_calls', 'tool_errors', 'authorization_blocks', 'authorization_checks',
               'metadata_quarantines', 'metadata_examined', 'benign_metadata_quarantines',
               'benign_metadata_examined', 'detector_seconds', 'cross_server_write_calls'}
    for row in rows:
        case = expected[row['case_id']]
        for key in ('task', 'workflow', 'surface', 'condition', 'repeat', 'transport', 'slot_id', 'attack_case_id', 'split'):
            if row[key] != ('' if case.get(key) is None else str(case[key])):
                raise ValueError('Trial identity mismatch')
        for key, value in list(row.items()):
            if value == '': row[key] = None
            elif value in ('True', 'False'): row[key] = value == 'True'
            elif key in numeric: row[key] = float(value)
        row['repeat'] = int(row['repeat'])
    spec = importlib.util.spec_from_file_location('original_summary', ROOT / 'scripts/formal/summarize.py')
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    # This is a statistics-only view, not a rehashed or executable manifest.
    view = {'plan_sha256': plan['plan_sha256'], 'shards': [shard]}
    result = original.summarize(view, rows)
    result.update(analysis_scope='person-03/shard-02 only', global_planned=plan['planned_cases'],
                  does_not_establish_global_study_completion=True,
                  task_ids=sorted({c['task'] for c in shard['cases']}))
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    result['budget'] = receipt['budget']
    result['worker_seconds'] = receipt['wall_seconds']
    (directory / 'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def fraction(n, d): return '%d/%d (%.1f%%)' % (n, d, 100 * n / d) if d else 'N/A'
    lines = ['# Person 03 formal results', '',
        'Scope: 336 records for tasks 16, 24, 27 and 35. This is one shard of the 1,680-trial study.',
        'Model/task failures are retained. Completion means record coverage, not that every task succeeded.', '',
        '| Configuration | Benign task passes | Output attack successes | Metadata attack successes |',
        '|---|---:|---:|---:|']
    cells = {(c['surface'], c['condition']): c for c in result['cells']}
    for condition in CONDITIONS:
        benign, output, metadata = [cells[(surface, condition)] for surface in ('benign', 'output', 'metadata')]
        lines.append('| %s | %s | %s | %s |' % (condition,
            fraction(benign['task_passes'], benign['planned']),
            fraction(output['attack_successes'], output['planned']),
            fraction(metadata['attack_successes'], metadata['planned'])))
    lines += ['', '- Planned/recorded: 336/336.',
        '- Infrastructure/error records: %d.' % sum(c['error_records'] for c in result['cells']),
        '- API calls: %d.' % sum(r['api_calls'] for r in rows),
        '- Reported API cost: $%.8f.' % receipt['budget']['reported_cost_usd'],
        '- Worker wall time: %.2f hours.' % (receipt['wall_seconds'] / 3600),
        '- Plan SHA256: ' + plan['plan_sha256'],
        '- Runtime, adapter provenance and limitations: ENVIRONMENT.md and platform_receipt.json.', '',
        'Rates above use all locally planned trials as denominators. Read errors and exposure counts alongside rates.',
        'analysis.json includes safe completion, valid/exposed denominators, costs, latency and paired comparisons from the original statistics function.',
        'Only four task clusters are available here; do not generalize these intervals to the whole benchmark or treat repeated runs as independent tasks.',
        'Local adapter acceptance and final Vanda/group validation remain separate from numerical coverage.', '']
    (directory / 'ANALYSIS.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(dict(scope=result['analysis_scope'], planned=336, recorded=len(rows),
                          cost_usd=receipt['budget']['reported_cost_usd'])))


if __name__ == '__main__':
    main()
