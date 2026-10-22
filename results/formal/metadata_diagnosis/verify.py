"""Verify metadata diagnostics against frozen results, evidence and file hashes."""
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
    root = folder.parents[2]
    load = lambda name: json.loads((folder / name).read_text())

    def rows(name):
        with (folder / name).open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))

    manifest = load('manifest.json')
    for base, mapping in ((root, manifest['inputs']), (folder, manifest['outputs'])):
        for name, expected in mapping.items():
            assert recorded_digest(hashlib.sha256((base / name).read_bytes()).hexdigest()) == expected, name
    plan = json.loads((root / 'assignments/formal/plan.json').read_text())
    assert plan['plan_sha256'] == manifest['plan_sha256']
    attacks = {k: a for k, a in plan['config']['formal_attacks'].items() if a['surface'] == 'metadata'}
    assert len(attacks) == 30
    formal = {}
    for person in range(1, 6):
        with (root / f'experiments/deliveries/person-{person:02}/results.csv').open(encoding='utf-8-sig') as stream:
            for record in csv.DictReader(stream):
                assert record['case_id'] not in formal
                formal[record['case_id']] = record
    selected = {k: r for k, r in formal.items() if r['surface'] == 'metadata' and r['condition'] in ('none', 'trustgate')}
    trials = rows('trials.csv')
    by_id = {r['case_id']: r for r in trials}
    assert len(trials) == len(by_id) == 180 and set(by_id) == set(selected)
    trace_columns = ('requests_available', 'requests_with_payload_evidence', 'goal_tool_available',
                     'attacked_tool_proposed', 'goal_tool_proposal_count', 'exact_goal_proposal_count',
                     'pending_unexecuted_proposals', 'malicious_metadata_quarantined',
                     'attacked_description_score', 'recomputed_attack_success')
    for record in trials:
        source = selected[record['case_id']]
        for key in ('task', 'attack_case_id', 'condition', 'repeat', 'status', 'native_utility', 'attacker_success'):
            assert record[key] == source[key], (record['case_id'], key)
        attack = attacks[record['attack_case_id']]
        assert record['metadata_tool'] == attack['metadata_tool'] and record['goal_tool'] == attack['goal']['tool']
        assert record['reported_injection_reached_model'] == source['injection_reached_model']
        assert int(record['reported_malicious_metadata_quarantines']) == int(source['metadata_quarantines']) - int(source['benign_metadata_quarantines'])
        if record['evidence_level'] == 'summary_only':
            assert all(record[k] == '' for k in trace_columns), record['case_id']
            assert record['request_evidence'] == 'reported_flag_only' and record['source'] == ''
        else:
            assert (root / record['source']).is_file()
            assert 0 < int(record['requests_with_payload_evidence']) <= int(record['requests_available'])
            assert int(record['requests_available']) == int(source['api_calls'])
            if record['request_evidence'] == 'public_full_description_first_request':
                assert record['requests_with_payload_evidence'] == '1'
    pairs = rows('pairs.csv')
    assert len(pairs) == len({(r['attack_case_id'], r['repeat']) for r in pairs}) == 90
    assert {r[k] for r in pairs for k in ('none_case_id', 'trustgate_case_id')} == set(selected)
    for pair in pairs:
        for condition in ('none', 'trustgate'):
            trial = by_id[pair[condition + '_case_id']]
            assert trial['condition'] == condition and trial['repeat'] == pair['repeat'] and trial['attack_case_id'] == pair['attack_case_id']
            assert pair[condition + '_goal_tool_proposals'] == trial['goal_tool_proposal_count']
            assert pair[condition + '_attack_success'] == trial['attacker_success']
    gaps = rows('evidence_gaps.csv') if (folder / 'evidence_gaps.csv').is_file() else []
    assert len(gaps) == len({r['case_id'] for r in gaps})
    assert {r['case_id'] for r in gaps} == {r['case_id'] for r in trials if r['evidence_level'] == 'summary_only'}
    summary = load('summary.json')
    review = load('review.json')
    assert review['passed'] and review['total']['records'] == len(trials)
    for name, expected in review['input_sha256'].items():
        assert recorded_digest(hashlib.sha256((root / name).read_bytes()).hexdigest()) == expected, name
    detailed = [r for r in trials if r['evidence_level'] != 'summary_only']
    assert summary['evidence_levels'] == dict(Counter(r['evidence_level'] for r in trials))
    assert summary['request_evidence_levels'] == dict(Counter(r['request_evidence'] for r in trials))
    assert summary['gaps_by_person'] == dict(Counter(r['person'] for r in gaps))
    assert summary['first_repeat_gaps'] == sum(r['repeat'] == '1' for r in gaps)
    assert summary['detailed_trials'] == len(detailed)
    assert summary['attacked_tool_proposed'] == sum(r['attacked_tool_proposed'] == 'True' for r in detailed)
    assert summary['attacked_tool_not_proposed'] == sum(r['attacked_tool_proposed'] == 'False' for r in detailed)
    assert summary['detailed_trials_with_goal_tool_proposals'] == sum(int(r['goal_tool_proposal_count']) > 0 for r in detailed)
    assert summary['detailed_trials_with_exact_goal_proposals'] == sum(int(r['exact_goal_proposal_count']) > 0 for r in detailed)
    assert summary['review_basis'] == dict(Counter(r['review_basis'] for r in trials))
    assert review['total']['exact_goal_proposals'] == sum(int(r['exact_goal_proposal_count']) for r in detailed)
    assert review['total']['attacked_tool_proposed'] == summary['attacked_tool_proposed']
    assert review['total']['goal_tool_proposals'] == sum(int(r['goal_tool_proposal_count']) for r in detailed)
    assert len(review['crosschecked_public_cases']) == 6
    controls = load('controls.json')
    assert len(controls['records']) == 30 and {r['attack_case_id'] for r in controls['records']} == set(attacks)
    for record in controls['records']:
        assert all(record[k] is True for k in ('unchanged_schemas', 'exact_single_description_append', 'goal_tool_available', 'exact_goal_execution_score', 'frozen_policy_would_deny'))
        assert record['unchanged_state_score'] is record['wrong_target_execution_score'] is False
        if record['goal_tool'] == 'send_email':
            assert record['modified_mail_body_sent_to_target'] is True
            assert record['modified_mail_body_exact_score'] is False
        else:
            assert record['modified_mail_body_sent_to_target'] is record['modified_mail_body_exact_score'] is None
    for bundle_path in folder.glob('trace_checks_person-*.json'):
        bundle = json.loads(bundle_path.read_text())
        assert bundle['new_model_requests'] == 0 and bundle['cases'] == len(bundle['records']) == 36
        assert bundle['plan_sha256'] == plan['plan_sha256']
        for record in bundle['records']:
            assert record['formal_result_matches'] and record['state_roundtrip_exact']
            assert record['original_attack_success'] == record['recomputed_attack_success']
            assert all(Path(n).name == n and re.fullmatch('[0-9a-f]{64}', h) for n, h in record['source_files'].items())
    assert controls['new_model_requests'] == summary['new_model_requests'] == 0
    for path in (folder / 'README_ZH.md', folder / 'EXPORT_ZH.md'):
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if not link.startswith(('http:', 'https:', '#')):
                assert (path.parent / link.split('#')[0]).exists(), (path, link)
    print(json.dumps({'passed': True, 'pairs': len(pairs), 'trial_records': len(trials),
                      'detailed_records': len(detailed), 'missing_trace_records': len(gaps),
                      'positive_controls': 30, 'negative_controls': 60, 'new_model_requests': 0}))


if __name__ == '__main__':
    main()
