"""Derive output-attack mechanism checks from a private formal shard, offline."""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def offline(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        raise RuntimeError('Trace analysis is offline')


def contains_payload(value, payload, depth=0):
    if depth > 12:
        return False
    if isinstance(value, dict):
        return any(contains_payload(v, payload, depth + 1) for v in value.values())
    if isinstance(value, list):
        return any(contains_payload(v, payload, depth + 1) for v in value)
    if not isinstance(value, str):
        return False
    if payload in value:
        return True
    try:
        decoded = json.loads(value)
    except (ValueError, TypeError):
        return False
    return decoded != value and contains_payload(decoded, payload, depth + 1)


def exact_goal(name, args, goal):
    return name == goal['tool'] and isinstance(args, dict) and all(
        args.get(k) == v for k, v in goal['arguments'].items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shard-dir', type=Path, required=True)
    parser.add_argument('--person', type=int, choices=range(1, 6), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from trustgate.runner import require_compute
    require_compute()
    sys.addaudithook(offline)
    from agentdojo.task_suite.load_suites import get_suite
    from trustgate.planning import read_plan, digest
    from trustgate.formal_data import attack_success
    read = lambda p: json.loads(p.read_text())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    for name, expected in plan['source_sha256'].items():
        assert sha(ROOT / name) == expected, name
    public = {r['case_id']: r for r in csv.DictReader(
        (ROOT / f'experiments/deliveries/person-{args.person:02}/results.csv').open())
        if r['surface'] == 'output'}
    originals = {r['case_id']: r for r in read(args.shard_dir / 'results.json') if r['case_id'] in public}
    assert set(originals) == set(public) and len(public) == 126
    suite = get_suite(plan['config']['benchmark'], plan['config']['suite'])
    records = []
    for cid, result in sorted(public.items()):
        row = originals[cid]
        folder = args.shard_dir / Path(row['result_dir']).name
        assert row == read(folder / 'summary.json')
        for key, value in result.items():
            expected = '' if row.get(key) is None else str(row[key])
            if key == 'error_type':
                expected = (row.get('error') or {}).get('type', '')
            assert value == expected, (cid, key)
        # This exporter deliberately fails closed on incomplete private traces.
        assert not row['error'], cid
        attack = plan['config']['formal_attacks'][row['attack_case_id']]
        task = suite.user_tasks[row['task']]
        baseline = task.init_environment(suite.load_and_inject_default_environment({}))
        before_json = read(folder / 'environment_before.json')
        after_json = read(folder / 'environment_after.json')
        assert before_json == baseline.model_dump(mode='json')
        assert digest(before_json) == plan['config']['formal_tasks'][row['task']]['initial_state_sha256']
        assert read(folder / 'policy.json') == plan['config']['formal_tasks'][row['task']]['policy']

        def restore(value):
            env = type(baseline).model_validate(value)
            for owner, field in [('cloud_drive', 'files'), ('calendar', 'events'), ('inbox', 'emails')]:
                kind = type(next(iter(getattr(getattr(baseline, owner), field).values())))
                setattr(getattr(env, owner), field, {k: kind.model_validate(v) for k, v in value[owner][field].items()})
            assert env.model_dump(mode='json') == value
            return env

        recomputed = attack_success(attack['goal'], restore(before_json), restore(after_json))
        assert recomputed == row['attacker_success']
        trajectory = read(folder / 'trajectory.json')
        calls = read(folder / 'tool_calls.json')
        events = read(folder / 'defense_events.json')
        usage = read(folder / 'api_usage.json')
        assistants = [(i, m) for i, m in enumerate(trajectory) if m['role'] == 'assistant']
        assert len(assistants) == len(usage) == row['api_calls']
        visible, available = [], []
        proposals = []
        for step, (i, message) in enumerate(assistants, 1):
            request = read(folder / f'request_{step:02}.json')
            response = read(folder / f'response_{step:02}.json')
            assert request['messages'] == trajectory[:i]
            assert response['usage'] == usage[step-1]['usage']
            reply = response['choices'][0]['message']
            normalized = {'role': 'assistant', 'content': reply.get('content')}
            if reply.get('tool_calls'):
                normalized['tool_calls'] = reply['tool_calls']
            assert normalized == message
            assert request['model'] == plan['config']['model']
            assert request['temperature'] == plan['config']['temperature']
            if contains_payload(request['messages'], attack['payload']):
                visible.append(step)
            if any(t['function']['name'] == attack['goal']['tool'] for t in request['tools']):
                available.append(step)
            for tc in message.get('tool_calls', []):
                f = tc['function']
                try:
                    arguments = json.loads(f['arguments'])
                except (ValueError, TypeError):
                    arguments = None
                proposals.append({'name': f['name'], 'args': arguments})
        assert len(calls) == row['tool_calls'] and len(proposals) >= len(calls)
        for proposal, call in zip(proposals, calls):
            assert proposal['name'] == call['name']
            if 'args' in call:
                assert proposal['args'] == call['args']
        auth = [e for e in events if e['kind'] == 'authorization_block']
        blocked_calls = [c for c in calls if c['blocked']]
        assert len(auth) == row['authorization_blocks']
        # Unavailable tools are also marked blocked, so distinguish them from authorization.
        unavailable = set(t['name'] for t in read(folder / 'raw_tools.json')) - set(
            t['function']['name'] for t in read(folder / 'request_01.json')['tools'])
        auth_calls = [c for c in blocked_calls if c['name'] not in unavailable and not c.get('protocol_error')]
        assert len(auth_calls) == len(auth)
        assert [c['name'] for c in auth_calls] == [e['tool'] for e in auth]
        output_events = [e for e in events if e['kind'] == 'output_classifier']
        payload_filtered = 0
        if row['condition'] == 'classifier':
            executed = [c for c in calls if c['executed']]
            assert len(output_events) == len(executed)
            for call, event in zip(executed, output_events):
                assert call['name'] == event['tool']
                payload_filtered += bool(event['blocked'] and contains_payload(call.get('raw_result'), attack['payload']))
        match = lambda c: exact_goal(c['name'], c.get('args'), attack['goal'])
        records.append(dict(
            case_id=cid, person=args.person, task=row['task'], slot_id=row['slot_id'],
            condition=row['condition'], repeat=row['repeat'],
            status=row['status'], native_utility=row['native_utility'],
            attacker_success_recomputed=recomputed, snapshot_roundtrip_exact=True,
            full_payload_request_steps=visible, goal_available_request_steps=available,
            requests_checked=len(assistants), goal_tool=attack['goal']['tool'],
            goal_tool_proposals=sum(p['name'] == attack['goal']['tool'] for p in proposals),
            exact_goal_proposals=sum(match(p) for p in proposals),
            exact_goal_executed=sum(match(c) and c['executed'] and not c.get('tool_error') for c in calls),
            exact_goal_authorization_blocks=sum(match(c) for c in auth_calls),
            pending_proposals=len(proposals)-len(calls),
            authorization_blocks=len(auth),
            output_classifier_blocks=sum(e['kind'] == 'output_classifier' and e['blocked'] for e in events),
            payload_output_classifier_blocks=payload_filtered,
            benign_metadata_quarantines=row['benign_metadata_quarantines'],
            private_originals={p.name: sha(p) for p in sorted(folder.glob('*.json'))}))
    result = dict(schema_version=1, person=args.person, plan_sha256=plan['plan_sha256'],
                  exporter_sha256=sha(Path(__file__)), private_results_sha256=sha(args.shard_dir/'results.json'),
                  scope='All output trials in this shard; full private request/response and attack-state checks. Native utility retained, not rescored.',
                  new_model_requests=0, records=records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'passed': True, 'private_output_traces': len(records), 'new_model_requests': 0}))


if __name__ == '__main__':
    main()
