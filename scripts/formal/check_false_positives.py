"""Evaluate frozen screening and permissions on unmodified descriptions and reference calls.

Upstream reference solutions are used only by this post-hoc evaluator, after policy
freezing. They are never inputs to policy compilation, prompts or model requests.
"""
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
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
        descriptions.append(dict(tool=tool.name, input_sha256=hashlib.sha256(text.encode()).hexdigest(),
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
    return f'''# 合法说明和合法调用的误报

本检查离线使用冻结的检测器、阈值、权限以及原正式 20 个任务。没有新增模型请求，没有根据检查结果修改策略或原实验成绩。

| 指标 | 分子／分母 | 分母含义 |
|---|---:|---|
| 合法工具说明误隔离 | {c['quarantined_legitimate_descriptions']}/{c['unique_legitimate_descriptions']} | 不重复的原始工具说明 |
| 授权层合法调用误拒 | {c['authorization_false_rejections']}/{c['executable_reference_calls']} | 上游参考路径中可执行的调用 |
| 说明隔离影响的参考调用 | {c['metadata_blocked_reference_calls']}/{c['executable_reference_calls']} | 同一组参考调用 |
| 完整网关会阻止的参考调用 | {c['gateway_blocked_reference_calls']}/{c['executable_reference_calls']} | 授权拒绝或说明隔离的并集 |

被误隔离的原始说明：`{names}`。原任务中重复检查同一说明不能扩大独立文本样本数。

合法调用来源是固定 AgentDojo 版本的上游参考解，独立于本项目权限规则。先核对正式初始状态与既有权限，再逐步读取参考路径；只在隔离的评估环境执行参考调用，记录工具执行是否有效，并检查该时刻权限是否放行。即便某调用被策略拒绝，参考环境仍按参考路径前进，因此这是逐调用兼容性诊断，不是假装模型绕过拒绝后继续执行。

共 {c['reference_calls']} 个参考调用，{c['nonexecutable_reference_calls']} 个无法执行的参考调用另列，不纳入合法调用分母。`checks.json` 提供每个任务、工具、参数哈希、拒绝原因和来源源码哈希；复现时从固定依赖重新读取参考解，不公开完整工作区状态。

参考解仅在正式冻结后用于本评估器，不用于生成权限、修改提示或发送给模型。该误拒率只描述参考路径；它不是对全部实际模型提议逐条人工标注所得的总体误报率，也不能由零误拒推导所有合法表达都被允许。正常模型任务中的总拒绝数另见 [开销与误报统计](../overhead/README_ZH.md)。

在计算节点运行 `python scripts/formal/check_false_positives.py --output runs/false-positive-check` 可重新计算，需配置 `TRUSTGATE_DETECTOR_DIR`。主结果保留固定版本，检测器加载及推断都在 CPU 上执行。
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
