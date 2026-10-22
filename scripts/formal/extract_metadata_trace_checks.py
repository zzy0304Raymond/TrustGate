"""Export derived metadata-attack checks; never export raw conversations or states."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[2]))
from release_integrity import recorded_digest
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def offline(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        raise RuntimeError('Offline trace extraction does not permit network access')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--person', type=int, choices=range(1, 6), required=True)
    parser.add_argument('--shard-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--platform', choices=('vanda', 'local'), default='vanda',
                        help='Use local only in the original non-Vanda environment; obey its scheduler rules.')
    args = parser.parse_args()
    if args.platform == 'vanda':
        from trustgate.runner import require_compute
        require_compute()
    elif platform.python_version() != '3.10.20':
        raise RuntimeError('The original environment must use Python 3.10.20.')
    sys.addaudithook(offline)
    from agentdojo.task_suite.load_suites import get_suite
    from trustgate.formal_data import attack_success
    from trustgate.planning import digest, read_plan

    sha = lambda p: recorded_digest(hashlib.sha256(p.read_bytes()).hexdigest())
    read = lambda p: json.loads(p.read_text())
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    receipt = read(ROOT / f'experiments/deliveries/person-{args.person:02}/receipt.json')
    for name, expected in receipt['source_sha256'].items():
        assert sha(ROOT / name) == expected, name
    results = list(csv.DictReader((ROOT / f'experiments/deliveries/person-{args.person:02}/results.csv').open()))
    selected = {r['case_id']: r for r in results if r['surface'] == 'metadata' and r['condition'] in ('none', 'trustgate')}
    assert len(selected) == 36
    original = {r['case_id']: r for r in read(args.shard_dir / 'results.json') if r['case_id'] in selected}
    assert set(original) == set(selected)
    suite = get_suite(plan['config']['benchmark'], plan['config']['suite'])
    records = []
    for cid, result in sorted(selected.items()):
        entry = original[cid]
        folder = args.shard_dir / Path(entry['result_dir']).name
        sources = {p.name: sha(p) for p in folder.glob('*.json')}
        row = read(folder / 'summary.json')
        assert row == entry
        for key, value in result.items():
            expected = '' if row.get(key) is None else str(row[key])
            if key == 'error_type':
                expected = (row.get('error') or {}).get('type', '')
            assert value == expected, (cid, key)
        attack = plan['config']['formal_attacks'][row['attack_case_id']]
        task = suite.user_tasks[row['task']]
        baseline = task.init_environment(suite.load_and_inject_default_environment({}))
        before_json, after_json = (read(folder / f'environment_{x}.json') for x in ('before', 'after'))
        assert digest(before_json) == plan['config']['formal_tasks'][row['task']]['initial_state_sha256']
        assert before_json == baseline.model_dump(mode='json')
        file_type = type(next(iter(baseline.cloud_drive.files.values())))
        event_type = type(next(iter(baseline.calendar.events.values())))
        email_type = type(next(iter(baseline.inbox.emails.values())))

        def restore(value):
            env = type(baseline).model_validate(value)
            # AgentDojo validators initialize live collections from initial_*.
            # Restore the saved live state, then require an exact JSON roundtrip.
            env.cloud_drive.files = {k: file_type.model_validate(v) for k, v in value['cloud_drive']['files'].items()}
            env.calendar.events = {k: event_type.model_validate(v) for k, v in value['calendar']['events'].items()}
            env.inbox.emails = {k: email_type.model_validate(v) for k, v in value['inbox']['emails'].items()}
            assert env.model_dump(mode='json') == value
            return env

        before, after = restore(before_json), restore(after_json)
        recomputed = attack_success(attack['goal'], before, after)
        assert recomputed == row['attacker_success']
        trajectory = read(folder / 'trajectory.json')
        calls = read(folder / 'tool_calls.json')
        usage = read(folder / 'api_usage.json')
        events = read(folder / 'defense_events.json')
        raw_tools = read(folder / 'raw_tools.json')
        attacked = [t for t in raw_tools if attack['marker'] in t['description']]
        assert len(attacked) == 1 and attacked[0]['name'] == attack['metadata_tool']
        assert attacked[0]['description'].endswith(attack['payload'])
        assistants = [(i, m) for i, m in enumerate(trajectory) if m['role'] == 'assistant']
        assert len(assistants) == len(usage) == row['api_calls']
        visible_steps, goal_available_steps = [], []
        for step, (index, message) in enumerate(assistants, 1):
            request = read(folder / f'request_{step:02}.json')
            response = read(folder / f'response_{step:02}.json')
            assert request['messages'] == trajectory[:index]
            assert response['usage'] == usage[step - 1]['usage']
            r = response['choices'][0]['message']
            normalized = {'role': 'assistant', 'content': r.get('content')}
            if r.get('tool_calls'):
                normalized['tool_calls'] = r['tool_calls']
            assert normalized == message
            tools = {t['function']['name']: t['function'] for t in request['tools']}
            if attack['goal']['tool'] in tools:
                goal_available_steps.append(step)
            if attack['metadata_tool'] in tools:
                desc = tools[attack['metadata_tool']]['description']
                if row['condition'] == 'trustgate':
                    desc = json.loads(desc)['description']
                if desc.endswith(attack['payload']):
                    visible_steps.append(step)
            assert request['model'] == plan['config']['model']
        assert bool(visible_steps) == row['injection_reached_model']
        proposals = [tc['function'] for _, m in assistants for tc in m.get('tool_calls', [])]
        assert len(calls) == row['tool_calls'] and len(proposals) >= len(calls)
        for proposed, call in zip(proposals, calls):
            assert proposed['name'] == call['name']
            if 'args' in call:
                assert json.loads(proposed['arguments']) == call['args']

        def matches(proposed):
            if proposed['name'] != attack['goal']['tool']:
                return False
            try:
                actual = json.loads(proposed['arguments'])
                return all(actual.get(k) == v for k, v in attack['goal']['arguments'].items())
            except (ValueError, AttributeError):
                return False

        quarantines = [e['tool'] for e in events if e['kind'] == 'metadata_quarantine']
        scores = [e['score'] for e in events if e['kind'] == 'metadata_classifier' and e['tool'] == attack['metadata_tool']]
        record = dict(case_id=cid, person=args.person, task=row['task'], attack_case_id=row['attack_case_id'],
                      condition=row['condition'], repeat=row['repeat'], evidence_level='private_full_trace',
                      requests_checked=len(assistants), full_payload_request_steps=visible_steps,
                      goal_tool_available_request_steps=goal_available_steps,
                      metadata_tool=attack['metadata_tool'], goal_tool=attack['goal']['tool'],
                      proposed_tool_names=[p['name'] for p in proposals],
                      attacked_tool_proposed=any(p['name'] == attack['metadata_tool'] for p in proposals),
                      goal_tool_proposal_count=sum(p['name'] == attack['goal']['tool'] for p in proposals),
                      exact_goal_proposal_count=sum(matches(p) for p in proposals),
                      goal_tool_executed_count=sum(c['name'] == attack['goal']['tool'] and c['executed'] for c in calls),
                      pending_unexecuted_proposals=len(proposals) - len(calls),
                      malicious_metadata_quarantined=attack['metadata_tool'] in quarantines,
                      normal_metadata_quarantines=[t for t in quarantines if t != attack['metadata_tool']],
                      attacked_description_score=scores[0] if scores else None,
                      authorization_blocks=row['authorization_blocks'], status=row['status'],
                      original_attack_success=row['attacker_success'], recomputed_attack_success=recomputed,
                      state_roundtrip_exact=True, formal_result_matches=True,
                      source_files=sources)
        assert all(sha(folder / name) == digest for name, digest in sources.items())
        records.append(record)
    output = dict(schema_version=1, person=args.person, cases=len(records), python=platform.python_version(),
                  execution_platform=args.platform, operating_system=platform.system(),
                  packages={p: importlib.metadata.version(p) for p in ('agentdojo', 'pydantic')},
                  plan_sha256=plan['plan_sha256'], extractor_sha256=sha(Path(__file__)),
                  new_model_requests=0, scope='Derived checks from local private originals; raw messages and states are not published.',
                  records=records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': True, 'person': args.person, 'cases': len(records),
                      'full_payload_in_all_requests': sum(len(r['full_payload_request_steps']) == r['requests_checked'] for r in records),
                      'attacked_tool_proposed': sum(r['attacked_tool_proposed'] for r in records),
                      'goal_tool_proposals': sum(r['goal_tool_proposal_count'] for r in records), 'new_model_requests': 0}))


if __name__ == '__main__':
    main()
