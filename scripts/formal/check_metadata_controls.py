"""Offline MCP and scoring controls for the 30 frozen tool-description attacks."""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[2]))
from release_integrity import recorded_digest
import argparse
import asyncio
import contextlib
import copy
import hashlib
import json
import os
import platform
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def offline(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        raise RuntimeError('Offline controls do not permit network access')


async def check(output):
    from trustgate.runner import require_compute
    require_compute()
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    sys.addaudithook(offline)
    from trustgate.formal_engine import FormalExperiment
    from trustgate.formal_data import attack_success
    from trustgate.formal_policy import authorize
    from trustgate.planning import digest, read_plan
    from agentdojo.task_suite.load_suites import get_suite
    from simulation_runtime import write_state, read_state

    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    for name, expected in plan['source_sha256'].items():
        assert recorded_digest(hashlib.sha256((ROOT / name).read_bytes()).hexdigest()) == expected, name
    suite = get_suite(plan['config']['benchmark'], plan['config']['suite'])
    attacks = [a for a in plan['config']['formal_attacks'].values() if a['surface'] == 'metadata']
    assert len(attacks) == 30
    records = []
    # Synthetic backend checkpoints are temporary and never overwrite recorded trials.
    with tempfile.TemporaryDirectory(prefix='trustgate-metadata-controls-') as temporary:
        experiment = FormalExperiment(plan['config'], Path(temporary), suite, None, 'offline-no-credential')

        def forbid_completion(*args, **kwargs):
            raise RuntimeError('Model completion is forbidden in offline controls')

        experiment.completion = forbid_completion
        async with contextlib.AsyncExitStack() as stack:
            await experiment.start(stack)
            for attack in attacks:
                task = suite.user_tasks[attack['task']]
                before = task.init_environment(suite.load_and_inject_default_environment({}))
                assert digest(before.model_dump(mode='json')) == plan['config']['formal_tasks'][attack['task']]['initial_state_sha256']
                write_state(experiment.state, before)
                experiment.control.write_text(json.dumps({'state_path': str(experiment.state), 'surface': 'metadata',
                    'metadata_tool': attack['metadata_tool'], 'payload': attack['payload']}))
                changed, tool_names = [], []
                for client in experiment.clients.values():
                    response = await client.list_tools()
                    for tool in response.tools:
                        native = experiment.runtime.functions[tool.name]
                        tool_names.append(tool.name)
                        assert tool.inputSchema == native.parameters.model_json_schema()
                        if tool.description != native.description:
                            assert tool.description == native.description + '\n\n' + attack['payload']
                            changed.append(tool.name)
                assert changed == [attack['metadata_tool']]
                goal = attack['goal']
                assert goal['tool'] in tool_names
                negative = attack_success(goal, before, read_state(experiment.state))
                assert negative is False
                client = experiment.clients[experiment.routing[goal['tool']]]
                reply = await client.call_tool(goal['tool'], goal['arguments'])
                assert not reply.isError, attack['attack_case_id']
                positive = attack_success(goal, before, read_state(experiment.state))
                assert positive is True
                policy = plan['config']['formal_tasks'][attack['task']]['policy']
                allowed, reason = authorize(policy, goal['tool'], goal['arguments'], before)
                assert not allowed

                wrong = copy.deepcopy(goal['arguments'])
                if goal['tool'] == 'delete_file':
                    wrong['file_id'] = next(k for k in before.cloud_drive.files if k != wrong['file_id'])
                elif goal['tool'] == 'cancel_calendar_event':
                    wrong['event_id'] = next(k for k, e in before.calendar.events.items() if k != wrong['event_id'] and str(e.status) == 'confirmed')
                else:
                    wrong['recipients'] = ['different-control@example.com']
                write_state(experiment.state, before)
                reply = await client.call_tool(goal['tool'], wrong)
                assert not reply.isError, (attack['attack_case_id'], wrong, [getattr(c, 'text', '') for c in reply.content])
                wrong_target = attack_success(goal, before, read_state(experiment.state))
                assert wrong_target is False
                variant_exact = variant_sent = None
                if goal['tool'] == 'send_email':
                    variant = copy.deepcopy(goal['arguments'])
                    variant['body'] += '\n'
                    write_state(experiment.state, before)
                    reply = await client.call_tool(goal['tool'], variant)
                    assert not reply.isError
                    after = read_state(experiment.state)
                    old_ids = {str(e.id_) for e in before.inbox.sent}
                    variant_sent = any(str(e.id_) not in old_ids and set(e.recipients) == set(goal['arguments']['recipients']) for e in after.inbox.sent)
                    variant_exact = attack_success(goal, before, after)
                    assert variant_sent is True and variant_exact is False
                records.append(dict(attack_case_id=attack['attack_case_id'], task=attack['task'],
                    metadata_tool=attack['metadata_tool'], goal_tool=goal['tool'], template_family=attack['template_family'],
                    unchanged_schemas=True, exact_single_description_append=True, goal_tool_available=True,
                    unchanged_state_score=negative, exact_goal_execution_score=positive,
                    wrong_target_execution_score=wrong_target, frozen_policy_would_deny=True,
                    denial_reason=reason, modified_mail_body_sent_to_target=variant_sent,
                    modified_mail_body_exact_score=variant_exact))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(schema_version=1, control_type='offline_synthetic_mcp_controls',
        python=platform.python_version(), checker_sha256=recorded_digest(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        new_model_requests=0, plan_sha256=plan['plan_sha256'],
        limitation='Controls test transport and scoring, not whether a model follows an attack or how historical trials behaved.',
        records=records), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': True, 'metadata_attacks': len(records), 'mcp_positive_controls': len(records),
                      'unchanged_and_wrong_target_negative_controls': 2 * len(records),
                      'mail_exact_match_sensitivity_controls': sum(r['goal_tool'] == 'send_email' for r in records),
                      'new_model_requests': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(check(parser.parse_args().output))
