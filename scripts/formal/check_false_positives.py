"""Evaluate frozen screening and permissions on unmodified descriptions and reference calls.

Upstream reference solutions are used only by this post-hoc evaluator, after policy
freezing. They are never inputs to policy compilation, prompts or model requests.
"""
import sys as _release_sys
from pathlib import Path as _ReleasePath
_release_sys.path.insert(0, str(_ReleasePath(__file__).resolve().parents[2]))
from release_integrity import recorded_digest
import argparse
import hashlib
import inspect
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from trustgate.runner import require_compute
from trustgate.planning import read_plan, digest
from trustgate.formal_manifest import verify_runtime
from trustgate.formal_policy import authorize, READ
from trustgate.formal_engine import FormalExperiment
from scripts.demo.export_checks import offline
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.functions_runtime import FunctionsRuntime
from simulation_runtime import run_native
from detector import Detector
from run_matrix_v2 import RULE

OUT = ROOT / 'results/formal/false_positives'


def sha(path):
    return recorded_digest(hashlib.sha256(Path(path).read_bytes()).hexdigest())


def evaluate(detector_dir):
    require_compute()
    sys.addaudithook(offline)
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    verify_runtime(plan, detector_dir)
    suite = get_suite('v1.2.2', 'workspace')
    runtime = FunctionsRuntime(suite.tools)
    detector = Detector(detector_dir, plan['config']['classifier_threshold'])
    descriptions = []
    for tool in suite.tools:
        text = json.dumps(dict(name=tool.name, description=tool.description,
                               inputSchema=tool.parameters.model_json_schema()))
        score = detector.score(text)
        rule = bool(RULE.search(tool.description))
        descriptions.append(dict(tool=tool.name, input_sha256=recorded_digest(hashlib.sha256(text.encode()).hexdigest()),
                                 score=score['score'], classifier_blocked=score['blocked'],
                                 rule_blocked=rule, quarantined=score['blocked'] or rule))
    quarantined = {r['tool'] for r in descriptions if r['quarantined']}
    records, sources = [], {}
    for tid in sorted(plan['config']['formal_tasks']):
        task = suite.user_tasks[tid]
        clean = task.init_environment(suite.load_and_inject_default_environment({}))
        frozen = plan['config']['formal_tasks'][tid]
        assert task.PROMPT == frozen['prompt'] and digest(clean.model_dump(mode='json')) == frozen['initial_state_sha256']
        # Only evaluate the already-published policy; never recompile from reference calls.
        policy = frozen['policy']
        before_policy = digest(policy)
        reference = task.ground_truth(clean.model_copy(deep=True))
        env = clean.model_copy(deep=True)
        source = Path(inspect.getfile(type(task)))
        sources[type(task).__module__] = sha(source)
        for index, call in enumerate(reference, 1):
            allowed, reason = authorize(policy, call.function, call.args, env)
            # Advance a separate reference environment even if the gateway would deny;
            # this measures per-call decisions on valid reference states, not a live rollout.
            _, error = run_native(runtime, env, call.function, call.args)
            records.append(dict(task=tid, step=index, tool=call.function,
                arguments_sha256=digest(call.args), is_write=call.function not in READ,
                reference_executable=not bool(error), reference_error=error,
                authorization_allowed=allowed, authorization_reason=reason,
                metadata_quarantined=call.function in quarantined,
                gateway_would_block=not allowed or call.function in quarantined))
        assert digest(policy) == before_policy
    valid = [r for r in records if r['reference_executable']]
    counts = dict(tasks=20, reference_calls=len(records), executable_reference_calls=len(valid),
                  nonexecutable_reference_calls=len(records) - len(valid),
                  authorization_false_rejections=sum(not r['authorization_allowed'] for r in valid),
                  metadata_blocked_reference_calls=sum(r['metadata_quarantined'] for r in valid),
                  gateway_blocked_reference_calls=sum(r['gateway_would_block'] for r in valid),
                  unique_legitimate_descriptions=len(descriptions),
                  quarantined_legitimate_descriptions=len(quarantined))
    return dict(plan_sha256=plan['plan_sha256'], new_model_requests=0, evaluator_source_sha256=sha(Path(__file__)),
                reference_source_sha256=sources, counts=counts, descriptions=descriptions, reference_calls=records,
                scope='Post-hoc reference-path evaluation; not model proposal population',
                policies_unchanged=True, reference_answers_sent_to_model=False)


def report(result):
    c = result['counts']
    names = ', '.join(r['tool'] for r in result['descriptions'] if r['quarantined'])
    return f'''# False positives for legitimate declarations and legitimate calls

This inspection uses offline frozen detectors thresholds permissions and the original 20 official tasks. No new model requests were made and no strategy modifications or original experiment results were adjusted based on inspection results.

| Metrics | Numerator/Denominator | denominator meaning |
|---|---:|---|
| legitimate tool instruction mis-isolation | {c['quarantined_legitimate_descriptions']}/{c['unique_legitimate_descriptions']} | non-repeating original tool instruction |
| legitimate call mis-rejection at authorization layer | {c['authorization_false_rejections']}/{c['executable_reference_calls']} | executable calls in upstream reference path |
| reference calls indicating isolation impact | {c['metadata_blocked_reference_calls']}/{c['executable_reference_calls']} | same group of reference calls |
| reference calls fully blocked by gateway | {c['gateway_blocked_reference_calls']}/{c['executable_reference_calls']} | Authorization denied or explanation quarantine union |

Original explanation of misquarantined: `{names}`. Rechecking the same explanation in the original task does not increase the count of independent text samples.

Legitimate call sources are fixed upstream reference solutions from AgentDojo versions, independent of this project’s permission rules. First verify the official initial state against existing permissions, then gradually read the reference path; only execute reference calls within the quarantined evaluation environment, record whether tool execution is effective, and check whether permissions were granted at that moment. Even if a call is rejected by policy, the reference environment still proceeds along the reference path, so this is a per-call compatibility diagnosis, not pretending the model bypasses rejection and continues execution.

Total {c['reference_calls']} reference calls,{c['nonexecutable_reference_calls']} reference calls that cannot be executed listed separately, not included in the denominator of legitimate calls.`checks.json` Provide for each task, tool, parameter hash, rejection reason, and source code hash of the reference; during reproducibility, read the reference solution again from fixed dependencies without exposing the full workspace state.

The reference solution is used only by this evaluator after official freezing, not for generating permissions, modifying prompts, or sending to the model. This false rejection rate only describes the reference path; it is not the overall false positive rate obtained by manually labeling every actual model proposal, nor can it be inferred that all valid expressions are allowed from zero false rejections. Total rejections in normal model tasks are documented elsewhere. [Overhead and false positive statistics](../overhead/README_ZH.md).

Running on compute node `python scripts/formal/check_false_positives.py --output runs/false-positive-check` Can be recomputed, requires configuration `TRUSTGATE_DETECTOR_DIR`. The main result retains a fixed version, and detector loading and inference are executed on CPU.
'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--detector', type=Path, default=Path(os.environ.get('TRUSTGATE_DETECTOR_DIR', ROOT / 'models/prompt_injection_detector')))
    args = parser.parse_args()
    result = evaluate(args.detector)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (args.output / 'README_ZH.md').write_text(report(result))
    print(json.dumps(result['counts']))
