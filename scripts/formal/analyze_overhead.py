"""Resource, metadata false-positive and recovery sensitivity analysis of frozen deliveries."""
import argparse
import csv
import hashlib
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.formal.analyze import read_deliveries, load, sha
from trustgate.planning import read_plan, CONDITIONS
from trustgate.runner import require_compute

OUT = ROOT / 'results/formal/overhead'
RECOVERED = '98f0051e9f3cdb5a5daf'
METRICS = ['seconds', 'api_seconds', 'detector_seconds', 'api_calls', 'total_tokens', 'cost_usd']


def mean(values):
    return statistics.mean(values) if values else None


def paired(rows, surface, other, scope='all', exclude_recovered=False):
    selected = [r for r in rows if r['surface'] == surface and not r['error_type']
                and (scope == 'all' or r['platform_group'] == scope)
                and (not exclude_recovered or r['case_id'] != RECOVERED)]
    indexed = {(r['task'], r['slot_id'], r['repeat'], r['condition']): r for r in selected}
    pairs = []
    for (task, slot, repeat, condition), row in indexed.items():
        comparison = indexed.get((task, slot, repeat, other))
        if condition == 'trustgate' and comparison is not None:
            pairs.append((row, comparison))
    output = []
    for metric in METRICS:
        differences, base = {}, {}
        for row, comparison in pairs:
            differences.setdefault(row['task'], []).append(row[metric] - comparison[metric])
            base.setdefault(row['task'], []).append(comparison[metric])
        values = [mean(differences[t]) for t in sorted(differences)]
        rng = random.Random(421322)
        samples = sorted(mean(rng.choices(values, k=len(values))) for _ in range(2000)) if values else []
        baseline = mean([mean(v) for v in base.values()])
        delta = mean(values)
        output.append(dict(surface=surface, comparator=other, scope=scope,
                           exclude_recovered=exclude_recovered, metric=metric,
                           paired_tasks=len(values), paired_records=len(pairs),
                           task_weighted_baseline=baseline, task_weighted_difference=delta,
                           relative_difference=delta / baseline if baseline else None,
                           ci_low=samples[50] if samples else None,
                           ci_high=samples[1949] if samples else None))
    return output


def calculate():
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    rows, hashes = read_deliveries(ROOT, plan, load(ROOT / 'results/formal/manifest.json'))
    for row in rows:
        row['total_tokens'] = row['prompt_tokens'] + row['completion_tokens']
        row['platform_group'] = {1: 'Vanda', 2: 'Mac', 3: 'WSL', 4: 'Vanda', 5: 'Vanda'}[row['person']]
    assert len([r for r in rows if r['case_id'] == RECOVERED]) == 1
    grouped, metadata, denials = [], [], []
    for scope in ['all', 'Vanda', 'Mac', 'WSL']:
        for surface in ['benign', 'output', 'metadata']:
            for condition in CONDITIONS:
                rs = [r for r in rows if r['surface'] == surface and r['condition'] == condition
                      and (scope == 'all' or r['platform_group'] == scope)]
                valid = [r for r in rs if not r['error_type']]
                for metric in METRICS:
                    grouped.append(dict(scope=scope, surface=surface, condition=condition, metric=metric,
                        recorded=len(rs), valid=len(valid), errors=len(rs) - len(valid),
                        all_record_mean=mean([r[metric] for r in rs]),
                        valid_mean=mean([r[metric] for r in valid]),
                        valid_median=statistics.median([r[metric] for r in valid]) if valid else None))
                if scope == 'all':
                    n = sum(int(r['benign_metadata_quarantines']) for r in rs)
                    d = sum(int(r['benign_metadata_examined']) for r in rs)
                    screening = condition in ['classifier', 'trustgate', 'no_provenance', 'no_authorization']
                    metadata.append(dict(surface=surface, condition=condition, screening_enabled=screening,
                        recorded=len(rs), normal_descriptions_seen=d, normal_descriptions_quarantined=n,
                        observed_quarantine_rate=n / d if screening and d else None,
                        independent_description_population=24 if surface == 'benign' else None))
                    if surface == 'benign':
                        checks = sum(int(r['authorization_checks']) for r in rs)
                        blocked = sum(int(r['authorization_blocks']) for r in rs)
                        denials.append(dict(condition=condition, trials=len(rs), checks=checks, denials=blocked,
                            trials_with_denial=sum(r['authorization_blocks'] > 0 for r in rs),
                            rejection_fraction=blocked / checks if checks else None,
                            is_false_positive_rate=False))
    pairs = []
    for scope in ['all', 'Vanda', 'Mac', 'WSL']:
        for surface in ['benign', 'output', 'metadata']:
            for exclude in [False, True]:
                pairs.extend(paired(rows, surface, 'none', scope, exclude))
    for other in ['delimiters', 'classifier', 'no_provenance', 'no_metadata', 'no_authorization']:
        for surface in ['benign', 'output', 'metadata']:
            pairs.extend(paired(rows, surface, other))
    outcome_sensitivity = []
    for exclude in [False, True]:
        subset = [r for r in rows if not r['error_type'] and (not exclude or r['case_id'] != RECOVERED)]
        for condition in CONDITIONS:
            for surface in ['benign', 'output', 'metadata']:
                rs = [r for r in subset if r['condition'] == condition and r['surface'] == surface]
                outcome_sensitivity.append(dict(exclude_recovered=exclude, condition=condition, surface=surface,
                    valid=len(rs), native_successes=sum(r['native_utility'] is True for r in rs),
                    attack_successes=sum(r['attacker_success'] is True for r in rs) if surface != 'benign' else None,
                    safe_completions=sum(r['safe_completion'] is True for r in rs) if surface != 'benign' else None))
    return dict(resource_by_platform=grouped, paired_resources=pairs, metadata_false_positives=metadata,
                benign_authorization_rejections=denials, recovery_sensitivity=outcome_sensitivity), hashes


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prose(tables):
    lines = ['# Overhead normal explanation false positives and recovery sensitivity', '',
             'This analysis uses all 1,680 frozen records without adding new model requests or modifying original scores.', '',
             '## TrustGate relative overhead compared to unprotected pairing', '',
             'First pair by identical task, payload position, and repetition number; then average tasks equally. Exclude infrastructure errors; task failures, rejections, and call limits are still retained.', '',
             '| Scenario | Pair count | Additional seconds (95% interval) | Additional model calls | Additional tokens |',
             '|---|---:|---:|---:|---:|']
    for surface, label in [('benign', 'Normal task'), ('output', 'Output attack'), ('metadata', 'Instruction attack')]:
        rows = {r['metric']: r for r in tables['paired_resources'] if r['surface'] == surface
                and r['comparator'] == 'none' and r['scope'] == 'all' and not r['exclude_recovered']}
        seconds = rows['seconds']
        lines.append(f"| {label} | {seconds['paired_records']} | {seconds['task_weighted_difference']:.2f} "
                     f"[{seconds['ci_low']:.2f}, {seconds['ci_high']:.2f}] | "
                     f"{rows['api_calls']['task_weighted_difference']:.3f} | "
                     f"{rows['total_tokens']['task_weighted_difference']:.1f} |")
    lines += ['', 'Interval is exploratory per-item interval from task clustering bootstrap (2,000 iterations, seed 421322) without multiple comparison correction. Number of repetitions is not the number of independent tasks.', '',
              '## Platform and timing explanation', '',
              '- `resource_by_platform.csv` List all, Vanda, Mac, and WSL together, including mean, effective mean, and median for all records.',
              '- `paired_resources.csv` List paired differences for model calls, token count, total seconds, API seconds, detector seconds, and returned cost, as well as results after removing cached recovery records.',
              '- Each task’s all configurations are executed by the same team member on the same platform, pairing reduces platform confounding; different platforms handle different tasks, so mean differences between platforms cannot be interpreted as hardware effects.',
              '- Single record `seconds` It is actual task duration; do not compare total durations defined differently by different team members. Duration is affected by task path, remote services, and early termination due to failure, not a pure gateway micro-benchmark.',
              '- Model calls and token counts only cover returned responses; original timeout records remain in full record statistics, making it impossible to estimate tokens for non-returned responses.', '',
              '## Recovery and timeout sensitivity', '',
              f'Cache recovery log `{RECOVERED}` Part of the API timing comes from file time. All unguarded pair analyses provide both inclusive and exclusive views of this entry; when excluded, the entire affected pair is removed.',
              '- `recovery_sensitivity.csv` Provide corresponding safety and task utility counts. Final results remain based on original full data; sensitivity results do not replace them.',
              '- Original official single timeout cannot be counted as protective success; effective analysis excludes this entry, but the main plot of the planned denominator retains its position.', '',
              '## Two types of false positives must be separated', '',
              '- `metadata_false_positives.csv` Count the number of times unattacked tool instructions were isolated and check the denominator; conditions with screening disabled are marked as not applicable.',
              '- Normal tasks repeatedly use the same 24 tool instructions; run-level check denominator does not represent an equivalent number of independent texts. See also [Distinct benign descriptions and legitimate-call checks](../false_positives/README_ZH.md).',
              '- `benign_authorization_rejections.csv` is the rate of authorization rejection in normal tasks, including errors or over-privileged requests proposed by the model itself, which cannot be considered false positive rate.',
              '- Legitimate call rejection rate is determined by independent offline inspection of upstream reference solutions with frozen permissions; the denominator of this ratio is legitimate calls in the reference path, not equal to all actual model-proposed manually annotated results.', '',
              '## Reproduction', '', 'Running on allocated Vanda computing nodes `python scripts/formal/analyze_overhead.py --check`.',
              'Independent replica generation available `--output runs/overhead-check`. The SHA256 and input source of this directory file are listed in `manifest.json`.', '']
    return '\n'.join(lines)


def main(args):
    require_compute()
    tables, inputs = calculate()
    output = Path(args.output)
    if args.check:
        manifest = load(output / 'manifest.json')
        for name, expected in manifest['outputs'].items():
            assert sha(output / name) == expected, name
        assert manifest['inputs'] == inputs
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for name, records in tables.items():
                path = Path(tmp) / (name + '.csv')
                write_csv(path, records)
                assert path.read_bytes() == (output / path.name).read_bytes(), name
        assert (output / 'README_ZH.md').read_text() == prose(tables)
        assert manifest['analyzer_sha256'] == sha(Path(__file__))
        print('OVERHEAD_VERIFIED 1680')
        return
    output.mkdir(parents=True, exist_ok=True)
    for name, records in tables.items():
        write_csv(output / (name + '.csv'), records)
    (output / 'README_ZH.md').write_text(prose(tables))
    manifest = dict(inputs=inputs, analyzer_sha256=sha(Path(__file__)),
                    outputs={p.name: sha(p) for p in sorted(output.iterdir()) if p.name != 'manifest.json'})
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('OVERHEAD_WRITTEN 1680')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=OUT)
    parser.add_argument('--check', action='store_true')
    main(parser.parse_args())
