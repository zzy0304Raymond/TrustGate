"""Resource, metadata false-positive and recovery sensitivity analysis of frozen deliveries."""
import argparse
import csv
import hashlib
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.formal.analyze import read_deliveries, load, sha
from trustgate.planning import read_plan, CONDITIONS
from trustgate.runner import require_compute

OUT = ROOT / 'results/formal/overhead'
RECOVERED = '98f0051e9f3cdb5a5daf'
METRICS = ['seconds', 'api_seconds', 'detector_seconds', 'api_calls', 'total_tokens', 'cost_usd']


def mean(values):
    return statistics.mean(values) if values else None


def paired(rows, surface, other, scope='all', exclude_recovered=False):
    selected = [r for r in rows if r['surface'] == surface and not r['error_type']
                and (scope == 'all' or r['platform_group'] == scope)
                and (not exclude_recovered or r['case_id'] != RECOVERED)]
    indexed = {(r['task'], r['slot_id'], r['repeat'], r['condition']): r for r in selected}
    pairs = []
    for (task, slot, repeat, condition), row in indexed.items():
        comparison = indexed.get((task, slot, repeat, other))
        if condition == 'trustgate' and comparison is not None:
            pairs.append((row, comparison))
    output = []
    for metric in METRICS:
        differences, base = {}, {}
        for row, comparison in pairs:
            differences.setdefault(row['task'], []).append(row[metric] - comparison[metric])
            base.setdefault(row['task'], []).append(comparison[metric])
        values = [mean(differences[t]) for t in sorted(differences)]
        rng = random.Random(421322)
        samples = sorted(mean(rng.choices(values, k=len(values))) for _ in range(2000)) if values else []
        baseline = mean([mean(v) for v in base.values()])
        delta = mean(values)
        output.append(dict(surface=surface, comparator=other, scope=scope,
                           exclude_recovered=exclude_recovered, metric=metric,
                           paired_tasks=len(values), paired_records=len(pairs),
                           task_weighted_baseline=baseline, task_weighted_difference=delta,
                           relative_difference=delta / baseline if baseline else None,
                           ci_low=samples[50] if samples else None,
                           ci_high=samples[1949] if samples else None))
    return output


def calculate():
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    rows, hashes = read_deliveries(ROOT, plan, load(ROOT / 'results/formal/manifest.json'))
    for row in rows:
        row['total_tokens'] = row['prompt_tokens'] + row['completion_tokens']
        row['platform_group'] = {1: 'Vanda', 2: 'Mac', 3: 'WSL', 4: 'Vanda', 5: 'Vanda'}[row['person']]
    assert len([r for r in rows if r['case_id'] == RECOVERED]) == 1
    grouped, metadata, denials = [], [], []
    for scope in ['all', 'Vanda', 'Mac', 'WSL']:
        for surface in ['benign', 'output', 'metadata']:
            for condition in CONDITIONS:
                rs = [r for r in rows if r['surface'] == surface and r['condition'] == condition
                      and (scope == 'all' or r['platform_group'] == scope)]
                valid = [r for r in rs if not r['error_type']]
                for metric in METRICS:
                    grouped.append(dict(scope=scope, surface=surface, condition=condition, metric=metric,
                        recorded=len(rs), valid=len(valid), errors=len(rs) - len(valid),
                        all_record_mean=mean([r[metric] for r in rs]),
                        valid_mean=mean([r[metric] for r in valid]),
                        valid_median=statistics.median([r[metric] for r in valid]) if valid else None))
                if scope == 'all':
                    n = sum(int(r['benign_metadata_quarantines']) for r in rs)
                    d = sum(int(r['benign_metadata_examined']) for r in rs)
                    screening = condition in ['classifier', 'trustgate', 'no_provenance', 'no_authorization']
                    metadata.append(dict(surface=surface, condition=condition, screening_enabled=screening,
                        recorded=len(rs), normal_descriptions_seen=d, normal_descriptions_quarantined=n,
                        observed_quarantine_rate=n / d if screening and d else None,
                        independent_description_population=24 if surface == 'benign' else None))
                    if surface == 'benign':
                        checks = sum(int(r['authorization_checks']) for r in rs)
                        blocked = sum(int(r['authorization_blocks']) for r in rs)
                        denials.append(dict(condition=condition, trials=len(rs), checks=checks, denials=blocked,
                            trials_with_denial=sum(r['authorization_blocks'] > 0 for r in rs),
                            rejection_fraction=blocked / checks if checks else None,
                            is_false_positive_rate=False))
    pairs = []
    for scope in ['all', 'Vanda', 'Mac', 'WSL']:
        for surface in ['benign', 'output', 'metadata']:
            for exclude in [False, True]:
                pairs.extend(paired(rows, surface, 'none', scope, exclude))
    for other in ['delimiters', 'classifier', 'no_provenance', 'no_metadata', 'no_authorization']:
        for surface in ['benign', 'output', 'metadata']:
            pairs.extend(paired(rows, surface, other))
    outcome_sensitivity = []
    for exclude in [False, True]:
        subset = [r for r in rows if not r['error_type'] and (not exclude or r['case_id'] != RECOVERED)]
        for condition in CONDITIONS:
            for surface in ['benign', 'output', 'metadata']:
                rs = [r for r in subset if r['condition'] == condition and r['surface'] == surface]
                outcome_sensitivity.append(dict(exclude_recovered=exclude, condition=condition, surface=surface,
                    valid=len(rs), native_successes=sum(r['native_utility'] is True for r in rs),
                    attack_successes=sum(r['attacker_success'] is True for r in rs) if surface != 'benign' else None,
                    safe_completions=sum(r['safe_completion'] is True for r in rs) if surface != 'benign' else None))
    return dict(resource_by_platform=grouped, paired_resources=pairs, metadata_false_positives=metadata,
                benign_authorization_rejections=denials, recovery_sensitivity=outcome_sensitivity), hashes


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prose(tables):
    lines = ['# 开销、正常说明误报与恢复敏感性', '',
             '本分析使用全部 1,680 条冻结记录，不新增模型请求、不改原分数。', '',
             '## TrustGate 相对无防护的配对开销', '',
             '先按相同任务、载荷位置和重复编号配对，再对任务等权平均。排除基础设施错误；任务失败、拒绝和调用上限仍保留。', '',
             '| 场景 | 配对数 | 额外秒数（95% 区间） | 额外模型调用 | 额外 token |',
             '|---|---:|---:|---:|---:|']
    for surface, label in [('benign', '正常任务'), ('output', '输出攻击'), ('metadata', '说明攻击')]:
        rows = {r['metric']: r for r in tables['paired_resources'] if r['surface'] == surface
                and r['comparator'] == 'none' and r['scope'] == 'all' and not r['exclude_recovered']}
        seconds = rows['seconds']
        lines.append(f"| {label} | {seconds['paired_records']} | {seconds['task_weighted_difference']:.2f} "
                     f"[{seconds['ci_low']:.2f}, {seconds['ci_high']:.2f}] | "
                     f"{rows['api_calls']['task_weighted_difference']:.3f} | "
                     f"{rows['total_tokens']['task_weighted_difference']:.1f} |")
    lines += ['', '区间为任务聚类 bootstrap（2,000 次、种子 421322）的探索性逐项区间，未作多重比较校正。重复次数不是独立任务数。', '',
              '## 平台及计时解释', '',
              '- `resource_by_platform.csv` 同时列出全体、Vanda、Mac 和 WSL，包含所有记录均值、有效均值及中位数。',
              '- `paired_resources.csv` 列出模型调用、token、总秒数、API 秒数、检测器秒数和已返回费用的配对差值，及移除缓存恢复记录后的结果。',
              '- 每个任务的所有配置由同一组员在同一平台执行，配对可减少平台混杂；不同平台承担不同任务，不能把平台间均值差解释为硬件效果。',
              '- 单条 `seconds` 是实际任务耗时；不比较各组员不同定义的 worker 总时长。耗时同时受任务路径、远端服务和失败早停影响，不是纯网关微基准。',
              '- 模型调用及 token 只覆盖返回响应；原始超时记录仍保留在全记录统计中，无法估算其未返回 token。', '',
              '## 恢复与超时敏感性', '',
              f'- 缓存恢复记录 `{RECOVERED}` 的部分 API 计时来自文件时间。所有对无防护的配对分析同时提供含此条及排除此条两种口径；排除时删除受影响的整对。',
              '- `recovery_sensitivity.csv` 提供对应的安全性及任务效用计数。正式结果仍以原始全量为主，敏感性结果不替换它。',
              '- 原正式唯一超时不能算防护成功；有效分析排除该条，计划分母的主图继续保留其位置。', '',
              '## 两类误报须分开', '',
              '- `metadata_false_positives.csv` 统计未被攻击修改的工具说明被隔离的次数及检查分母；未开启筛查的条件标为不适用。',
              '- 正常任务反复使用相同的 24 个工具说明，运行级检查分母不代表同等数量的独立文本。另见 [独立说明与合法调用检查](../false_positives/README_ZH.md)。',
              '- `benign_authorization_rejections.csv` 是正常任务中的授权拒绝比例，包含模型自己提出的错误或越权请求，不能称为误报率。',
              '- 合法调用误拒率由冻结权限对上游参考解的独立离线检查给出；该比例的分母是参考路径中的合法调用，不等于所有实际模型提议的人工标注结果。', '',
              '## 复现', '', '在已分配的 Vanda 计算节点运行 `python scripts/formal/analyze_overhead.py --check`。',
              '生成独立副本可用 `--output runs/overhead-check`。本目录文件的 SHA256 及输入来源见 `manifest.json`。', '']
    return '\n'.join(lines)


def main(args):
    require_compute()
    tables, inputs = calculate()
    output = Path(args.output)
    if args.check:
        manifest = load(output / 'manifest.json')
        for name, expected in manifest['outputs'].items():
            assert sha(output / name) == expected, name
        assert manifest['inputs'] == inputs
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for name, records in tables.items():
                path = Path(tmp) / (name + '.csv')
                write_csv(path, records)
                assert path.read_bytes() == (output / path.name).read_bytes(), name
        assert (output / 'README_ZH.md').read_text() == prose(tables)
        assert manifest['analyzer_sha256'] == sha(Path(__file__))
        print('OVERHEAD_VERIFIED 1680')
        return
    output.mkdir(parents=True, exist_ok=True)
    for name, records in tables.items():
        write_csv(output / (name + '.csv'), records)
    (output / 'README_ZH.md').write_text(prose(tables))
    manifest = dict(inputs=inputs, analyzer_sha256=sha(Path(__file__)),
                    outputs={p.name: sha(p) for p in sorted(output.iterdir()) if p.name != 'manifest.json'})
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('OVERHEAD_WRITTEN 1680')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=OUT)
    parser.add_argument('--check', action='store_true')
    main(parser.parse_args())
