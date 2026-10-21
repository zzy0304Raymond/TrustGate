"""Verify committed study data and reproduce statistics; never call a model API."""
import argparse
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(*args):
    print('CHECK', ' '.join(args), flush=True)
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def check_links():
    # Ignore unavailable private-run links; those are outside the public artifact.
    paths = subprocess.check_output(['git', 'ls-files', '-z', '--', '*.md'], cwd=ROOT).decode().split('\0')
    checked, broken = 0, []
    for relative in paths:
        path = ROOT / relative
        if not relative or not path.is_file():
            continue
        text = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
        for target in re.findall(r'\]\(([^)]+)\)', text):
            target = target.split('#', 1)[0].strip('<>')
            if not target or re.match(r'^[a-zA-Z]+:', target) or 'PRIVATE_RUN_ARCHIVE' in target:
                continue
            candidate = (path.parent / target).resolve()
            if ROOT / 'runs' in candidate.parents:
                continue
            checked += 1
            if not candidate.exists():
                broken.append(f'{relative}: {target}')
    if broken:
        raise ValueError('Broken public links:\n' + '\n'.join(broken))
    return checked


def public(output):
    from scripts.formal import analyze as analysis
    from scripts.formal import analyze_overhead as overhead
    from trustgate.formal_manifest import source_hashes
    from trustgate.planning import read_plan
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    assert source_hashes() == plan['source_sha256']
    rows, inputs = analysis.read_deliveries(ROOT, plan, read(ROOT / 'results/formal/manifest.json'))
    summary = analysis.original_summary_module().summarize(plan, rows)
    assert summary == read(ROOT / 'results/formal/analysis.json')
    (output / 'analysis.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    tables = analysis.build_tables(plan, rows, summary)
    (output / 'tables').mkdir(exist_ok=True)
    for name, records in tables.items():
        path = output / 'tables' / (name + '.csv')
        analysis.write_csv(path, records)
        assert path.read_bytes() == (ROOT / 'results/formal/analysis/tables' / path.name).read_bytes(), name
    overhead_tables, overhead_inputs = overhead.calculate()
    assert overhead_inputs == inputs
    (output / 'overhead').mkdir(exist_ok=True)
    for name, records in overhead_tables.items():
        path = output / 'overhead' / (name + '.csv')
        overhead.write_csv(path, records)
        assert path.read_bytes() == (ROOT / 'results/formal/overhead' / path.name).read_bytes(), name
    overhead_manifest = read(ROOT / 'results/formal/overhead/manifest.json')
    assert overhead_manifest['inputs'] == inputs
    assert overhead_manifest['analyzer_sha256'] == sha(ROOT / 'scripts/formal/analyze_overhead.py')
    for name, expected in overhead_manifest['outputs'].items():
        assert sha(ROOT / 'results/formal/overhead' / name) == expected, name
    command('results/formal/review/verify.py')
    command('scripts/formal/review_metadata_checks.py')
    command('results/formal/metadata_diagnosis/verify.py')
    command('scripts/supplement/verify_public.py')
    command('scripts/formal/analyze_mechanisms.py', '--check')
    command('scripts/demo/build.py', '--check')
    # Transport public verification has its own dependency-free validator.
    command('scripts/transport/verify_public.py')
    fp = read(ROOT / 'results/formal/false_positives/checks.json')
    assert fp['plan_sha256'] == plan['plan_sha256'] and fp['new_model_requests'] == 0
    assert fp['evaluator_source_sha256'] == sha(ROOT / 'scripts/formal/check_false_positives.py')
    assert fp['counts']['tasks'] == len({r['task'] for r in fp['reference_calls']}) == 20
    valid = [r for r in fp['reference_calls'] if r['reference_executable']]
    assert fp['counts']['authorization_false_rejections'] == sum(not r['authorization_allowed'] for r in valid)
    assert fp['counts']['gateway_blocked_reference_calls'] == sum(r['gateway_would_block'] for r in valid)
    return dict(formal_records=len(rows), valid_formal_records=sum(not r['error_type'] for r in rows),
                public_tables=len(tables), overhead_tables=len(overhead_tables),
                core_source_files=len(source_hashes()), public_markdown_links=check_links())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='Also run tests, real MCP and pinned detector checks on PBS')
    parser.add_argument('--plots', action='store_true', help='Regenerate the six scientific figures; requires matplotlib')
    parser.add_argument('--output', type=Path, default=ROOT / 'runs/reproduce')
    args = parser.parse_args()
    if platform.python_version() != '3.10.20':
        raise RuntimeError('Use Python 3.10.20 for the published reproduction')
    args.output.mkdir(parents=True, exist_ok=True)
    # A failed run must not leave an earlier success receipt at the same location.
    receipt = args.output / 'verification.json'
    receipt.unlink(missing_ok=True)
    result = public(args.output)
    if args.plots:
        from scripts.formal import analyze as analysis
        from trustgate.planning import read_plan
        plan = read_plan(ROOT / 'assignments/formal/plan.json')
        rows, _ = analysis.read_deliveries(ROOT, plan, read(ROOT / 'results/formal/manifest.json'))
        tables = analysis.build_tables(plan, rows, read(ROOT / 'results/formal/analysis.json'))
        result['figures'] = analysis.make_figures(tables, args.output)
    if args.full:
        from trustgate.runner import require_compute
        require_compute()
        if not os.environ.get('TRUSTGATE_DETECTOR_DIR'):
            raise RuntimeError('Set TRUSTGATE_DETECTOR_DIR to the pinned detector')
        command('-m', 'pip', 'check')
        command('-m', 'unittest', 'discover', '-s', 'tests', '-v')
        command('scripts/validation/check_deliveries.py')
        command('tasks/02/prepare_delivery.py', '--check', '--require-validated')
        command('experiments/mvp/preflight.py')
        command('experiments/mvp/test_parser_recovery.py')
        command('scripts/formal/preflight.py')
        fp_output = args.output / 'false_positives'
        command('scripts/formal/check_false_positives.py', '--output', str(fp_output))
        # Hashes, decisions and counts are stable on the reference runtime.
        assert read(fp_output / 'checks.json') == read(ROOT / 'results/formal/false_positives/checks.json')
        command('scripts/transport/study.py', 'controls', '--controls', str(args.output / 'transport-controls'))
        command('scripts/demo/check_mcp.py', '--output', str(args.output / 'mcp-demo.json'))
        result.update(regression_suite=True, reference_call_checks=True, transport_controls=8, mcp_demo_controls=6)
    result.update(passed=True, new_model_requests=0, python=platform.python_version(), full=args.full,
                  reproduction_source_sha256=sha(Path(__file__)),
                  commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip())
    receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
