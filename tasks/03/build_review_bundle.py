"""Export allowlisted person-03 measurements for review, without a final receipt."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tasks/03'))
import resume
from trustgate.delivery import PUBLIC_FIELDS


def build(worker, destination):
    worker, destination = Path(worker), Path(destination)
    plan = resume.read_plan(ROOT / 'assignments/formal/plan.json')
    bound = resume.read(worker / 'recovery.json')
    resume.verify_bound(plan, bound)
    rows, summary = resume.read(worker / 'results.json'), resume.read(worker / 'worker_summary.json')
    manifest = resume.read(worker / 'manifest.json')
    resume.check_rows(plan, rows)
    resume.check_ledger(plan, rows, summary['budget'], bound['carried_uncertain_reserved_usd'])
    unresolved = resume.check_traces(plan, rows, allow_recorded_timeout=True)
    if len(rows) != 336 or summary['complete'] is not True or summary['fatal_error']:
        raise ValueError('Requires complete collection, preserving recorded failures')
    if sum(item['uncertain_reserved_usd'] for item in unresolved) != summary['budget']['uncertain_reserved_usd']:
        raise ValueError('Unresolved reservations do not match retained requests')
    destination.mkdir(parents=True, exist_ok=False)
    fields = [*PUBLIC_FIELDS, 'error_type']
    clean = [{**{key: row.get(key) for key in PUBLIC_FIELDS},
              'error_type': (row.get('error') or {}).get('type')} for row in rows]
    with (destination / 'results.csv').open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(clean)
    spec = importlib.util.spec_from_file_location('original_summary', ROOT / 'scripts/formal/summarize.py')
    statistics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(statistics)
    analysis = statistics.summarize({'plan_sha256': plan['plan_sha256'], 'shards': [plan['shards'][2]]}, clean)
    analysis.update(scope='person-03 only, 336/1680 global trials', budget=summary['budget'],
                    review_only=True, final_delivery_ready=False)
    resume.durable(destination / 'analysis.json', analysis)
    proof = dict(schema='person03-review-only-v1', status='completed_needs_cost_review',
        final_delivery_ready=False, team_vanda_acceptance=False,
        plan_sha256=plan['plan_sha256'], source_sha256=plan['source_sha256'],
        person=3, shard_index=2, recorded=336, unique_assigned_ids_verified=True,
        budget=summary['budget'], packages=manifest['packages'],
        platform=manifest['platform'], recovery_sha256=bound['recovery_sha256'],
        recovery_entrypoint_sha256=bound['recovery_entrypoint_sha256'],
        unresolved_requests=unresolved, sum_case_seconds=summary['wall_seconds'],
        timing_basis=summary['wall_seconds_basis'],
        data_scope='Original PUBLIC_FIELDS plus categorical error_type; no prompts, answers, raw requests or backend state.',
        delivery_sha256={name: resume.runtime.sha(destination / name) for name in ('results.csv', 'analysis.json')})
    resume.durable(destination / 'review_receipt.json', proof)
    (destination / '.gitattributes').write_text('*.csv text eol=lf\n*.json text eol=lf\n*.md text eol=lf\n', encoding='utf-8')
    (destination / 'README.md').write_text(
        '# Person 03 review bundle — not a final delivery\n\n'
        'All 336 formal measurements are included. There is no final receipt.json: the strict final-export gate remains unchanged.\n\n'
        '- Actual platform: local WSL2 Linux, Python 3.10.20, CPU detector; no PBS impersonation.\n'
        '- Reported formal API cost: $0.51220968. Historical uncertain reservation: $0.05; this is not an actual-charge claim.\n'
        '- One TimeoutError and twelve model_call_budget records remain included. Coverage does not mean all tasks passed.\n'
        '- The original five-shard aggregator must not consume this review-only bundle as an accepted delivery.\n'
        '- Reconcile the timeout charge and review adapter/recovery provenance, then complete Vanda/team acceptance before final export.\n'
        '- See review_receipt.json for version, platform, attempt history, cost state and file hashes; ENVIRONMENT.md for human review.\n',
        encoding='utf-8')
    (destination / 'ENVIRONMENT.md').write_text(
        '# Actual person-03 runtime and acceptance status\n\n'
        '- Platform: WSL2 / Ubuntu 22.04.5; CPU only; no GPU used by the experiment.\n'
        '- Python: ' + manifest['platform']['python'] + '\n'
        '- Kernel: ' + manifest['platform']['release'] + '\n'
        '- Frozen plan SHA256: ' + plan['plan_sha256'] + '\n'
        '- Frozen model/provider: ' + plan['config']['model'] + ' / ' + plan['config']['provider'] + '; temperature=0.\n'
        '- Packages: ' + json.dumps(manifest['packages'], sort_keys=True) + '\n'
        '- Detector files: SHA256 pins verified; actual hashes are in review_receipt.json.\n'
        '- Hardware: ' + json.dumps(manifest['platform']['hardware'], sort_keys=True) + '\n'
        '- Random seed/thread environment: ' + json.dumps(manifest['platform']['thread_environment'], sort_keys=True) + '\n'
        '- Original 25 frozen Python files and original executable plan unchanged. Seven extra local adapter hashes are recorded separately.\n'
        '- Entry points: scripts/platforms/local/run.py, then tasks/03/resume.py; all attempt boundaries and entrypoint hashes are preserved.\n'
        '- Historical pause/resume: initial 18 records; first recovery to 58 with one timeout; second recovery to 191, safe user pause; final recovery to 336. No case was retried.\n'
        '- Cost: reported $0.51220968; uncertain reservation $0.05; pending request reservation $0. No running experiment or MCP process remains.\n'
        '- Timing: 6750.4345 seconds is the sum of case seconds across attempts, excluding startup, export and user pauses. It is not uninterrupted worker wall time.\n'
        '- Verification: real WSL offline unit tests, 116 dependency pins, 60 attack transport checks, 34 scripted loops and real CPU detector smoke checks.\n'
        '- Collection complete=true; cost_reconciled=false; final_delivery_ready=false; Vanda/team acceptance not performed.\n'
        '- Group 9 credentials, group CSV, original requests/responses, model weights and simulated backend state remain private.\n', encoding='utf-8')
    cells = {(c['surface'], c['condition']): c for c in analysis['cells']}
    lines = ['# Person 03 observed results (review only)', '',
        'Each row has 12 benign, 18 output-attack and 18 metadata-attack planned trials. Attack success is an undesired outcome.', '',
        '| Configuration | Benign task passes | Output attack successes | Metadata attack successes |',
        '|---|---:|---:|---:|']
    for condition in statistics.CONDITIONS:
        benign, output, metadata = [cells[(surface, condition)] for surface in ('benign', 'output', 'metadata')]
        lines.append('| %s | %d/12 | %d/18 | %d/18 |' % (condition,
            benign['task_passes'], output['attack_successes'], metadata['attack_successes']))
    lines += ['', 'One output/trustgate trial has a TimeoutError. Do not interpret this infrastructure error as successful defense.',
        'Zero observed attacks under the undefended baseline limits evidence of additional defense benefit in this shard.',
        'analysis.json preserves error/exposure denominators and task-cluster paired comparisons from the original statistics function.',
        'Only four task clusters are present; this is not the whole study. No parameter or attack was changed using these test results.',
        'Fees remain unresolved as disclosed above; this bundle is for review and is not final merge acceptance.', '']
    (destination / 'ANALYSIS.md').write_text('\n'.join(lines), encoding='utf-8')
    # Verify every public CSV value against its allowlisted private measurement.
    with (destination / 'results.csv').open(encoding='utf-8', newline='') as stream:
        exported = list(csv.DictReader(stream))
    if len(exported) != 336 or any(set(row) != set(fields) for row in exported):
        raise ValueError('Review CSV field/count mismatch')
    for actual, expected in zip(exported, clean):
        if any(actual[key] != ('' if expected[key] is None else str(expected[key])) for key in fields):
            raise ValueError('Review CSV differs from original measurement')
    return dict(review_only=True, recorded=336, cost_reconciled=False, destination=str(destination))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-dir', type=Path, required=True)
    parser.add_argument('--destination', type=Path, default=ROOT / 'tasks/03/delivery_pending')
    args = parser.parse_args()
    print(json.dumps(build(args.worker_dir, args.destination)))
