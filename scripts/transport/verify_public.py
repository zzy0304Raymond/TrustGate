"""Dependency-free verification and paired summaries for the transport study."""
import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/transport_validation'


def read(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    plan = read(ROOT / 'assignments/transport_validation/plan.json')
    assert plan['plan_sha256'] == digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
    formal = read(ROOT / 'assignments/formal/plan.json')
    assert plan['original_plan_sha256'] == formal['plan_sha256']
    assert set(c['condition'] for c in plan['cases']) == {'none'}
    assert len({c['workflow'][:2] for c in plan['cases']}) == 6
    for path, expected in plan['source_sha256'].items():
        assert sha(ROOT / path) == expected, path
    for path, expected in read(OUT / 'manifest.json')['files_sha256'].items():
        assert sha(ROOT / path) == expected, path
    rows = list(csv.DictReader((OUT / 'trials.csv').open()))
    assert len(rows) == len({r['case_id'] for r in rows}) == 48
    assert [r['case_id'] for r in rows] == [r['case_id'] for r in plan['cases']]
    for row, case in zip(rows, plan['cases']):
        assert case['case_id'] == digest({k: v for k, v in case.items() if k != 'case_id'})[:20]
        for key in ['task', 'workflow', 'surface', 'attack_case_id', 'repeat', 'transport']:
            assert row[key] == ('' if case[key] is None else str(case[key])), key
        for field in ['native_utility', 'attacker_success', 'safe_completion', 'injection_reached_model']:
            row[field] = {'True': True, 'False': False, '': None}[row[field]]
        for field in ['seconds', 'api_seconds', 'cost_usd', 'api_calls', 'prompt_tokens', 'completion_tokens']:
            row[field] = float(row[field])
    groups = []
    for surface in ['benign', 'output']:
        for transport in ['local', 'mcp']:
            rs = [r for r in rows if r['surface'] == surface and r['transport'] == transport]
            valid = [r for r in rs if r['status'] not in ['error', 'task_timeout']]
            groups.append(dict(surface=surface, transport=transport, recorded=len(rs), valid=len(valid),
                native_successes=sum(r['native_utility'] is True for r in valid),
                attack_successes=sum(r['attacker_success'] is True for r in valid) if surface == 'output' else None,
                exposed=sum(r['injection_reached_model'] is True for r in rs),
                mean_seconds=statistics.mean(r['seconds'] for r in rs),
                mean_api_calls=statistics.mean(r['api_calls'] for r in rs)))
    summary = read(OUT / 'summary.json')
    assert summary['groups'] == groups
    assert summary['worker']['complete'] and summary['worker']['recorded'] == 48
    assert math.isclose(sum(r['cost_usd'] for r in rows), summary['worker']['budget']['reported_cost_usd'], abs_tol=1e-9)
    checks = read(OUT / 'checks.json')
    assert checks['passed'] and checks['controls']['passed'] and checks['controls']['model_requests'] == 0
    assert len(checks['controls']['records']) == 8
    assert {r['case_id'] for r in checks['records']} == {r['case_id'] for r in rows}
    assert all(r['request_response_count_matches'] and r['initial_state_matches'] for r in checks['records'])
    for rec in checks['records']:
        assert all(len(h) == 64 and set(h) <= set('0123456789abcdef') for h in rec['source_files'].values())
    indexed = {(r['task'], r['surface'], r['repeat'], r['transport']): r for r in rows}
    pairs = []
    for (task, surface, repeat, transport), local in indexed.items():
        if transport != 'local':
            continue
        mcp = indexed[(task, surface, repeat, 'mcp')]
        pairs.append(dict(task=task, surface=surface, repeat=repeat,
            local_case_id=local['case_id'], mcp_case_id=mcp['case_id'],
            native_outcome_agrees=local['native_utility'] == mcp['native_utility'],
            attack_outcome_agrees=local['attacker_success'] == mcp['attacker_success'] if surface == 'output' else None,
            exposure_agrees=local['injection_reached_model'] == mcp['injection_reached_model'],
            mcp_minus_local_seconds=mcp['seconds'] - local['seconds']))
    assert len(pairs) == 24
    return groups, pairs, summary


def write():
    groups, pairs, summary = verify()
    with (OUT / 'pairs.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    lines = ['# 本地工具与 MCP 对照', '',
        '固定清单下的 48 次真实模型验证已完成，独立于原 1,680 条正式研究。六类正常任务 36 条、两个既有输出攻击 12 条；本地和 MCP 使用相同模型、工具、载荷、初始状态与预算，每格三次。', '',
        '| 场景 | 入口 | 有效／预定 | 原生任务成功 | 攻击成功 | 攻击曝光 | 平均秒数 |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in groups:
        attack = '—' if r['attack_successes'] is None else f"{r['attack_successes']}/{r['valid']}"
        exposure = '—' if r['surface'] == 'benign' else f"{r['exposed']}/{r['recorded']}"
        lines.append(f"| {r['surface']} | {r['transport']} | {r['valid']}/{r['recorded']} | "
                     f"{r['native_successes']}/{r['valid']} | {attack} | {exposure} | {r['mean_seconds']:.2f} |")
    agreement = sum(p['native_outcome_agrees'] for p in pairs)
    attack_pairs = [p for p in pairs if p['surface'] == 'output']
    lines += ['', f"24 组配对中，原生任务结局一致 {agreement}/24；输出攻击结局一致 "
              f"{sum(p['attack_outcome_agrees'] for p in attack_pairs)}/{len(attack_pairs)}。逐对 ID 与差值见 `pairs.csv`。", '',
              '八组预设回复检查均通过：本地/MCP 的工具定义、模型可见轨迹、读取结果、注入载荷和前后状态完全一致。这验证适配实现；真实模型的结局比较反映本批样本，不能据此声称统计等价。', '',
              '本批全部为无防护配置，以隔离传输适配。输出注入的原生入口通过独立薄适配器实现与 MCP 相同的一次追加；原正式执行器和 1,680 条成绩没有变化。预设回复检查不计入上述 48 条真实模型试验。', '',
              '该批复用正式任务和既有攻击，是事后适配诊断，不是新的泛化测试。模型温度为零也不保证相同回答；相邻配对和随机对内次序不能完全消除服务波动。耗时包含工具选择路径和远端响应，不能视为纯 MCP 协议开销。', '',
              f"本批尝试请求数 {summary['worker']['attempted_requests']}；有效记录和实际耗时见 `summary.json`。所有失败照常保留。", '',
              '## 复现', '',
              '- 无模型请求：`python scripts/transport/verify_public.py` 核验清单、完整性、指标和来源。',
              '- 真实 MCP 适配检查：在 PBS 计算节点运行 `python scripts/transport/study.py controls --controls runs/transport-check-new`。',
              '- 重新运行模型：在全新检出目录配置私有凭据路径，提交 `scripts/transport/run.pbs`；复用发布的清单，不覆盖已运行目录。', '',
              '冻结设计见 [PROTOCOL_ZH.md](../../assignments/transport_validation/PROTOCOL_ZH.md)。原始请求、响应及工作区状态保留在私有目录，公开文件仅包含指标及检查哈希。', '']
    (OUT / 'README_ZH.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.write:
        write()
    else:
        _, pairs, _ = verify()
        with (OUT / 'pairs.csv').open() as stream:
            stored = list(csv.DictReader(stream))
        assert stored == [{k: '' if v is None else str(v) for k, v in r.items()} for r in pairs]
    print('TRANSPORT_VERIFIED 48')
