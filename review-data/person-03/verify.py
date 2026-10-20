"""Public-only offline integrity checks; no model requests or original-state grading."""
import csv
import hashlib
import json
import re
from pathlib import Path


def main():
    folder = Path(__file__).resolve().parent
    read = lambda name: json.loads((folder / name).read_text(encoding='utf-8'))
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    with (folder / 'selection.csv').open(encoding='utf-8-sig', newline='') as stream:
        selected = list(csv.DictReader(stream))
    assert len(selected) == len({r['case_id'] for r in selected}) == 10
    verification, sources = read('VERIFICATION.json'), read('SOURCES.json')
    assert sha(folder / 'selection.csv') == sources['selection_sha256'] == verification['selection_sha256']
    assert verification['new_paid_api_requests'] == 0
    assert verification['native_score_mismatches'] == verification['attack_score_mismatches'] == 0
    records = [read(r['case_id'] + '.json') for r in selected]
    missing = []
    for selection, record in zip(selected, records):
        result = record['recorded_result']
        assert record['selection'] == selection
        assert record['case_id'] == selection['case_id'] == result['case_id']
        for key in ('task', 'surface', 'slot_id', 'condition', 'repeat'):
            assert str(result[key]) == selection[key]
        assert result['status'] == selection['recorded_status']
        assert str(result['native_utility']) == selection['recorded_task_success']
        assert ('' if result['attacker_success'] is None else str(result['attacker_success'])) == selection['recorded_attack_success']
        assert selection['review_status'] == 'pending'  # Providing evidence is not reviewer acceptance.
        assert record['native_scoring']['matches_original']
        assert record['native_scoring']['offline_recheck']['native_utility'] == result['native_utility']
        assert record['native_scoring']['offline_recheck']['attacker_success'] == result['attacker_success']
        calls, usage = record['tool_call_evidence'], record['api_usage_by_logical_call']
        assert len(calls) == result['tool_calls']
        assert sum(bool(c.get('blocked')) for c in calls) == result['authorization_blocks']
        assert sum(bool(c.get('tool_error')) for c in calls) == result['tool_errors']
        assert len(usage) == result['api_calls']
        assert abs(sum(c['usage']['cost'] for c in usage) - result['cost_usd']) < 1e-9
        assert sum(c['usage']['prompt_tokens'] for c in usage) == result['prompt_tokens']
        assert sum(c['usage']['completion_tokens'] for c in usage) == result['completion_tokens']
        requests = record['tool_exposure']['requests']
        for request in requests:
            assert request['model'] == 'qwen/qwen3-30b-a3b-instruct-2507'
            if request['response_status'] != 'present':
                missing.append((record['case_id'], request['step']))
                assert request['response_file'] is None and request['usage'] is None
            else:
                assert request['usage'] == usage[request['step'] - 1]['usage']
            if result['surface'] == 'metadata':
                assert any(t['name'] == 'get_unread_emails' and t['has_injection_marker'] for t in request['focused_tool_descriptions'])
        assert record['provenance']['private_originals'] == sources['per_record_and_batch_private_sources'][record['case_id']]
        assert record['state_change_evidence']['redacted_projection_not_valid_for_regrading']
        if result['task'] == 'user_task_16':
            assert not calls and not result['native_utility']
        for original in record['provenance']['private_originals']:
            assert not Path(original['file']).is_absolute() and re.fullmatch('[a-f0-9]{64}', original['sha256'])
    assert missing == [('9f7467fd5e9ede0aa172', 2)]
    timeout, batch = read('TIMEOUT.json'), read('BATCH.json')
    assert timeout['original_error']['type'] == 'TimeoutError'
    assert timeout['provider_final_charge_usd'] is None
    assert timeout['later_retry']['status'] == 'completed'
    assert timeout['preparation_created_new_model_requests'] == 0
    assert batch['recorded'] == batch['unique_case_ids'] == 336 and batch['complete']
    assert [a['owned_indices'] for a in batch['attempts']] == [[1, 18], [19, 58], [59, 191], [192, 336]]
    assert batch['attempts'][0]['worker_summary'] is None
    assert batch['timing']['exact_total_continuous_worker_seconds'] is None
    assert batch['cost']['historical_timeout_actual_final_charge_usd'] is None
    assert abs(batch['cost']['reported_formal_cost_usd'] - .51220968) < 1e-9
    # Public JSON contains projections, never complete snapshots or complete raw HTTP logs.
    for path in folder.glob('*.json'):
        value = path.read_text(encoding='utf-8')
        assert not re.search(r'(?:sk-or-v1-|Bearer\s+[A-Za-z0-9]|/home/trustgate/|/mnt/c/)', value), path.name
        emails = re.findall(r'[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', value)
        assert all(address.endswith('@example.invalid') for address in emails), path.name
        assert '"environment_before"' not in value and '"environment_after"' not in value
    sums = {}
    for line in (folder / 'SHA256SUMS').read_text().splitlines():
        digest, filename = line.split('  ', 1)
        assert Path(filename).name == filename and filename not in sums
        sums[filename] = digest
        assert sha(folder / filename) == digest, filename
    expected = {p.name for p in folder.iterdir() if p.is_file() and p.name != 'SHA256SUMS'}
    assert set(sums) == expected
    print(json.dumps(dict(passed=True, selected_cases=10, original_scores_unchanged=True,
                          original_timeout_preserved=True, new_model_requests=0, hashed_files=len(sums))))


if __name__ == '__main__':
    main()
