"""Validate the public review index against its selected cases and frozen results."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[3]))
from release_integrity import recorded_digest
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parents[2]
    manifest = json.loads((folder / 'source_manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert recorded_digest(hashlib.sha256((repo / name).read_bytes()).hexdigest()) == digest, name
    for name, digest in manifest['outputs'].items():
        assert recorded_digest(hashlib.sha256((folder / name).read_bytes()).hexdigest()) == digest, name
    rows = list(csv.DictReader((folder / 'cases.csv').open(encoding='utf-8-sig')))
    assert len(rows) == len({r['case_id'] for r in rows}) == 52
    assert Counter(r['person'] for r in rows) == {'1': 9, '2': 12, '3': 10, '4': 8, '5': 13}
    formal = {}
    selected = {}
    for person in range(1, 6):
        for r in csv.DictReader((repo / f'experiments/deliveries/person-{person:02}/results.csv').open(encoding='utf-8-sig')):
            assert r['case_id'] not in formal
            formal[r['case_id']] = r
        for r in csv.DictReader((repo / f'review-data/person-{person:02}/selection.csv').open(encoding='utf-8-sig')):
            assert r['case_id'] not in selected
            selected[r['case_id']] = r
    assert len(formal) == 1680
    assert set(selected) == {r['case_id'] for r in rows}
    for row in rows:
        case = formal[row['case_id']]
        for key in ('task', 'surface', 'condition', 'repeat', 'status', 'native_utility', 'attacker_success', 'authorization_blocks'):
            assert row[key] == case[key], (row['case_id'], key)
        assert (row['normal_metadata_quarantine_observed'] == 'True') == (int(case['benign_metadata_quarantines']) > 0)
        assert (repo / row['evidence_file']).is_file()
        assert all(row[k] for k in ('category', 'observed_facts', 'interpretation_limit', 'evidence_scope'))
    p1 = json.loads((repo / 'review-data/person-01/scoring_checks.json').read_text())['records']
    assert len(p1) == 9
    for row in p1:
        assert row['native_utility'] == row['native_utility_recomputed']
        assert row['attacker_success'] == row['attack_score_recomputed']
        assert row['snapshot_roundtrip_exact'] and row['formal_csv_matches'] and row['request_response_trajectory_usage_match']
        assert row['private_originals']
        assert all(Path(x['file']).name == x['file'] and re.fullmatch('[0-9a-f]{64}', x['sha256']) for x in row['private_originals'])
    by_id = {r['case_id']: r for r in rows}
    assert by_id['d578981c28682b1c6ef0']['category'] == 'Authorized interception attack'
    assert by_id['9f7467fd5e9ede0aa172']['status'] == 'error'
    assert by_id['9f7467fd5e9ede0aa172']['native_utility'] == 'True'
    assert Counter(r['category'] for r in rows if r['task'] == 'user_task_33') == {
        'Explicit date format error.': 3, 'Date format error; additional operation.': 2, 'Wrong recipient rejected; call limit reached.': 1}
    for path in [folder / 'README_ZH.md', folder / 'cases.md', repo / 'review-data/person-01/README.md']:
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if not link.startswith(('http:', 'https:', '#')):
                assert (path.parent / link.split('#')[0]).exists(), (path, link)
    print(json.dumps({'passed': True, 'selected_cases': 52, 'formal_records': len(formal),
                      'private_state_regraded': 9, 'public_excerpt_cross_checked': 43,
                      'input_hashes': len(manifest['files']), 'new_model_requests': 0}))


if __name__ == '__main__':
    main()
