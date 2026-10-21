"""Validate five submitted metadata exports without accessing a model service."""
import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / 'results/formal/metadata_diagnosis'
BASE_FILES = {'summary.json', 'trajectory.json', 'tool_calls.json', 'defense_events.json',
              'policy.json', 'raw_tools.json', 'environment_before.json',
              'environment_after.json', 'api_usage.json'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_bundle(bundle, person, formal, plan, extractor_hash):
    assert bundle['schema_version'] == 1 and bundle['person'] == person
    assert bundle['python'] == '3.10.20'
    assert bundle['packages'] == {'agentdojo': '0.1.35', 'pydantic': '2.14.1'}
    assert bundle['plan_sha256'] == plan['plan_sha256']
    assert bundle['extractor_sha256'] == extractor_hash and bundle['new_model_requests'] == 0
    assert bundle['execution_platform'] == ('local' if person in (2, 3) else 'vanda')
    assert bundle['operating_system'] == ('Darwin' if person == 2 else 'Linux')
    expected = {r['case_id']: r for r in formal if r['surface'] == 'metadata' and r['condition'] in ('none', 'trustgate')}
    records = bundle['records']
    assert len(records) == bundle['cases'] == len(expected) == 36
    assert len({r['case_id'] for r in records}) == 36
    assert {r['case_id'] for r in records} == set(expected)
    assert Counter((r['condition'], r['repeat']) for r in records) == {
        (condition, repeat): 6 for condition in ('none', 'trustgate') for repeat in (1, 2, 3)}
    for record in records:
        row = expected[record['case_id']]
        attack = plan['config']['formal_attacks'][row['attack_case_id']]
        assert record['person'] == person and record['evidence_level'] == 'private_full_trace'
        for key in ('task', 'attack_case_id', 'condition', 'repeat', 'status'):
            assert str(record[key]) == row[key], (record['case_id'], key)
        assert record['metadata_tool'] == attack['metadata_tool']
        assert record['goal_tool'] == attack['goal']['tool']
        assert record['formal_result_matches'] is record['state_roundtrip_exact'] is True
        assert type(record['original_attack_success']) is type(record['recomputed_attack_success']) is bool
        assert record['original_attack_success'] == record['recomputed_attack_success'] == (row['attacker_success'] == 'True')
        n = record['requests_checked']
        assert type(n) is int and n == int(row['api_calls']) and n > 0
        for key in ('full_payload_request_steps', 'goal_tool_available_request_steps'):
            steps = record[key]
            assert all(type(step) is int for step in steps)
            assert steps == sorted(set(steps)) and set(steps) <= set(range(1, n + 1))
        assert bool(record['full_payload_request_steps']) == (row['injection_reached_model'] == 'True')
        names = record['proposed_tool_names']
        assert all(isinstance(name, str) for name in names)
        assert record['attacked_tool_proposed'] is (record['metadata_tool'] in names)
        assert record['goal_tool_proposal_count'] == names.count(record['goal_tool'])
        for key in ('goal_tool_proposal_count', 'exact_goal_proposal_count', 'goal_tool_executed_count', 'pending_unexecuted_proposals', 'authorization_blocks'):
            assert type(record[key]) is int and record[key] >= 0
        assert record['exact_goal_proposal_count'] <= record['goal_tool_proposal_count']
        assert record['goal_tool_executed_count'] <= record['goal_tool_proposal_count']
        assert record['pending_unexecuted_proposals'] == len(names) - int(row['tool_calls'])
        assert record['authorization_blocks'] == int(row['authorization_blocks'])
        assert type(record['malicious_metadata_quarantined']) is bool
        assert int(record['malicious_metadata_quarantined']) == int(row['metadata_quarantines']) - int(row['benign_metadata_quarantines'])
        assert len(record['normal_metadata_quarantines']) == int(row['benign_metadata_quarantines'])
        assert record['metadata_tool'] not in record['normal_metadata_quarantines']
        score = record['attacked_description_score']
        if record['condition'] == 'none':
            assert score is None and record['authorization_blocks'] == 0
        else:
            assert type(score) in (float, int) and math.isfinite(score) and 0 <= score <= 1
            assert record['malicious_metadata_quarantined'] == (score >= plan['config']['classifier_threshold'])
        required = BASE_FILES | {f'{kind}_{step:02}.json' for kind in ('request', 'response') for step in range(1, n + 1)}
        assert set(record['source_files']) == required, record['case_id']
        assert all(re.fullmatch('[0-9a-f]{64}', digest) for digest in record['source_files'].values())
    return records


def crosscheck_public(record, person, row, attack, inputs):
    from scripts.formal.analyze_metadata_diagnosis import public_detail
    folder = ROOT / f'review-data/person-{person:02}'
    cid = record['case_id']
    path = folder / (cid + '.json') if person == 3 else folder / cid / 'evidence.json'
    if not path.is_file():
        return None
    inputs[path.relative_to(ROOT).as_posix()] = sha(path)
    detail = public_detail(path, attack, row)
    for key in ('attacked_tool_proposed', 'goal_tool_proposal_count', 'malicious_metadata_quarantined'):
        assert detail[key] == record[key], (cid, key)
    assert detail['requests_available'] == record['requests_checked']
    if detail['attacked_description_score'] != '':
        expected_score = record['attacked_description_score']
        if person == 5:
            # The previously published person-05 exporter explicitly rounded to six decimals.
            builder = folder / 'tools/build_review.py'
            inputs[builder.relative_to(ROOT).as_posix()] = sha(builder)
            expected_score = round(expected_score, 6)
        assert detail['attacked_description_score'] == expected_score
    data = read(path)
    if person == 3:
        hashes = {Path(f['file']).name: f['sha256'] for f in data['provenance']['private_originals']}
    elif person == 4:
        hashes = dict(data['original_files'])
        hashes.update({f['file']: f['sha256'] for f in data['request_response_files']})
    else:
        source = folder / 'SHA256SUMS.csv'
        inputs[source.relative_to(ROOT).as_posix()] = sha(source)
        with source.open(newline='') as stream:
            hashes = {Path(f['file']).name: f['sha256'] for f in csv.DictReader(stream)
                      if f['case_id'] == cid and f['kind'] == 'original'}
    assert set(hashes) == set(record['source_files'])
    assert hashes == record['source_files'], cid
    return dict(case_id=cid, person=person, matching_original_file_hashes=len(hashes),
                public_request_evidence=detail['request_evidence'])


def summarize(records):
    return dict(records=len(records), requests=sum(r['requests_checked'] for r in records),
                full_payload_in_all_requests=sum(r['full_payload_request_steps'] == list(range(1, r['requests_checked'] + 1)) for r in records),
                goal_tool_available_in_all_requests=sum(r['goal_tool_available_request_steps'] == list(range(1, r['requests_checked'] + 1)) for r in records),
                attacked_tool_proposed=sum(r['attacked_tool_proposed'] for r in records),
                attacked_tool_not_proposed=sum(not r['attacked_tool_proposed'] for r in records),
                trials_with_goal_tool_proposals=sum(r['goal_tool_proposal_count'] > 0 for r in records),
                goal_tool_proposals=sum(r['goal_tool_proposal_count'] for r in records),
                exact_goal_proposals=sum(r['exact_goal_proposal_count'] for r in records),
                goal_tool_executions=sum(r['goal_tool_executed_count'] for r in records),
                recomputed_attack_successes=sum(r['recomputed_attack_success'] for r in records),
                malicious_metadata_quarantines=sum(r['malicious_metadata_quarantined'] for r in records),
                normal_metadata_quarantines=sum(len(r['normal_metadata_quarantines']) for r in records),
                authorization_blocks=sum(r['authorization_blocks'] for r in records),
                pending_unexecuted_proposals=sum(r['pending_unexecuted_proposals'] for r in records),
                statuses=dict(Counter(r['status'] for r in records)),
                original_file_hashes=sum(len(r['source_files']) for r in records))


def audit():
    plan = read(ROOT / 'assignments/formal/plan.json')
    sources = read(FOLDER / 'submission_sources.json')
    assert {s['person'] for s in sources['records']} == set(range(1, 6))
    inputs = {}
    for path in (ROOT / 'assignments/formal/plan.json', FOLDER / 'submission_sources.json',
                 ROOT / 'scripts/formal/extract_metadata_trace_checks.py',
                 ROOT / 'scripts/formal/analyze_metadata_diagnosis.py', Path(__file__)):
        inputs[path.relative_to(ROOT).as_posix()] = sha(path)
    for name, expected in plan['source_sha256'].items():
        assert sha(ROOT / name) == expected, name
        inputs[name] = expected
    extractor_hash = sha(ROOT / 'scripts/formal/extract_metadata_trace_checks.py')
    people, all_records, overlaps, special = [], [], [], []
    for source in sources['records']:
        person = source['person']
        path = FOLDER / f'trace_checks_person-{person:02}.json'
        content = path.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest() == source['git_blob_sha1']
        inputs[path.relative_to(ROOT).as_posix()] = sha(path)
        csv_path = ROOT / f'experiments/deliveries/person-{person:02}/results.csv'
        inputs[csv_path.relative_to(ROOT).as_posix()] = sha(csv_path)
        with csv_path.open(newline='') as stream:
            formal = list(csv.DictReader(stream))
        receipt_path = csv_path.with_name('receipt.json')
        receipt = read(receipt_path)
        assert receipt['source_sha256'] == plan['source_sha256'] and receipt['plan_sha256'] == plan['plan_sha256']
        inputs[receipt_path.relative_to(ROOT).as_posix()] = sha(receipt_path)
        records = validate_bundle(read(path), person, formal, plan, extractor_hash)
        index = {r['case_id']: r for r in formal}
        for record in records:
            attack = plan['config']['formal_attacks'][record['attack_case_id']]
            overlap = crosscheck_public(record, person, index[record['case_id']], attack, inputs)
            if overlap:
                overlaps.append(overlap)
            if record['goal_tool_proposal_count'] or record['pending_unexecuted_proposals'] or record['authorization_blocks']:
                special.append(dict(person=person, **{k: record[k] for k in (
                    'case_id', 'task', 'attack_case_id', 'condition', 'repeat', 'goal_tool',
                    'goal_tool_proposal_count', 'exact_goal_proposal_count', 'goal_tool_executed_count',
                    'pending_unexecuted_proposals', 'authorization_blocks', 'status')},
                    native_utility=index[record['case_id']]['native_utility'] == 'True'))
        people.append(dict(passed=True, **source, **summarize(records)))
        all_records.extend(records)
    assert len(all_records) == len({r['case_id'] for r in all_records}) == 180
    result = dict(schema_version=1, passed=True, plan_sha256=plan['plan_sha256'], new_model_requests=0,
                  scope='Public submission consistency review; person 1 also has centrally retained originals. Persons 2-5 supply derived checks from their private originals.',
                  people=people, total=summarize(all_records),
                  by_condition={c: summarize([r for r in all_records if r['condition'] == c]) for c in ('none', 'trustgate')},
                  crosschecked_public_cases=overlaps, special_records=special, input_sha256=inputs)
    (FOLDER / 'review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': True, 'people': len(people), **result['total'],
                      'public_overlap_cases': len(overlaps), 'new_model_requests': 0}, ensure_ascii=False))


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(ROOT))
    audit()
