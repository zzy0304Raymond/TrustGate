"""Run the prepared person-2 batch once and stage allowlisted review files."""
import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'runs/local-person2'
OUTPUT = ROOT / 'output'
LOCAL = ROOT / 'scripts/platforms/local'


def now():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds')


def read(path, default=None):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def stage(run_id):
    OUTPUT.mkdir(exist_ok=True)
    manifest = read(STATE / 'execution.json')
    if manifest is None:
        raise RuntimeError('Prepared execution manifest missing.')
    target = OUTPUT / 'platform-local'
    target.mkdir(exist_ok=True)
    for path in LOCAL.iterdir():
        if path.is_file():
            shutil.copy2(path, target / path.name)
    shutil.copy2(__file__, target / 'person2_supervisor.py')
    (OUTPUT / 'README_ZH.md').write_text(
        '# 第 2 人实验：本地检查文件\n\n'
        '该目录由已授权的本地实验自动整理，目前仅供本人检查，不自动上传。\n\n'
        '- `STATUS.md`、`progress.json`：当前进度与本批次实际 API 费用。\n'
        '- `partial_results.csv`：运行中的脱敏记录，不是完整正式结果。\n'
        '- `results.csv`、`local-receipt.json`：仅全部 336 条完整记录通过核验后生成。\n'
        '- `cost_summary.json`：本批次 API 报告费用、待结算和不确定预留，区别于全组账户余额。\n'
        '- `ENVIRONMENT.md`：真实 Mac 环境、原始清单与本地配置指纹。\n'
        '- `platform-local/`：本地适配源码与依赖配置；使用时按原项目目录结构放回。\n\n'
        '本次 CPU Torch 构建与 Vanda 的 CUDA 构建不同，PBS 启动方式也不同。'
        '原始冻结源代码、任务、权限、攻击和 336 个 ID 保持不变。'
        '本地凭据使用 local-receipt.json，不能冒充原平台 receipt.json；'
        '与全组正式结果合并前需要统一版本验收。原集群入口保持完整。\n\n'
        '密钥、完整请求回复、模拟邮箱/日历/文件状态不在此目录中。\n', encoding='utf-8')
    package_text = '\n'.join(f'- {k}: `{v}`' for k, v in manifest['packages'].items())
    (OUTPUT / 'ENVIRONMENT.md').write_text(
        '# Person 02 execution environment\n\n'
        f'- Run ID: `{run_id}`\n- Person: 2; shard index: 1\n'
        f'- Platform: {manifest["system"]} {manifest["machine"]}; OS release {manifest["os_release"]}\n'
        '- Scheduler: none (local process); detector on CPU, two threads; GPU unused\n'
        f'- Python: {manifest["python"]}\n- Upstream commit: `{manifest["upstream_commit"]}`\n'
        f'- Upstream plan SHA256: `{manifest["upstream_plan_sha256"]}`\n'
        f'- Local execution SHA256: `{manifest["local_execution_sha256"]}`\n'
        '- Model: qwen/qwen3-30b-a3b-instruct-2507; provider: SiliconFlow; temperature 0\n'
        '- Scope: original person-02 336 trials, original ordering and case IDs\n'
        '- API stop budget: USD 2; request reservation USD 0.05; no automatic retries\n'
        '- Startup: `bash scripts/platforms/local/person2.sh run --run-id ' + run_id + '`\n'
        '- Offline checks: 37 tests; 24 MCP tools; 60 attack transport checks; pinned detector hashes verified\n'
        '- Platform difference: native torch 2.7.1 in place of 2.7.1+cu126. '
        'Frozen upstream execution code is unchanged; the local adapter starts identical MCP services without PBS.\n'
        '- Vanda equivalence and team acceptance: unverified, requires review before pooling results\n\n'
        '## Key package versions\n\n' + package_text + '\n', encoding='utf-8')


def refresh(run_id, process=None):
    folder = ROOT / 'runs/studies' / run_id / 'shard-01'
    summary = read(folder / 'worker_summary.json')
    budget = read(folder / 'budget.json', {})
    rows = read(folder / 'results.json', [])
    expected = read(ROOT / 'assignments/formal/plan.json')['shards'][1]['cases']
    lookup = {c['case_id']: c for c in expected}
    if len({r['case_id'] for r in rows}) != len(rows):
        raise RuntimeError('Duplicate case IDs in results.')
    for row in rows:
        if row['case_id'] not in lookup or any(row.get(k) != v for k, v in lookup[row['case_id']].items()):
            raise RuntimeError('Result identity mismatch.')
    from trustgate.delivery import PUBLIC_FIELDS
    if rows:
        tmp = OUTPUT / 'partial_results.csv.tmp'
        with tmp.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=[*PUBLIC_FIELDS, 'error_type'])
            writer.writeheader()
            for row in rows:
                writer.writerow({**{k: row.get(k) for k in PUBLIC_FIELDS},
                    'error_type': row['error']['type'] if row.get('error') else None})
        tmp.replace(OUTPUT / 'partial_results.csv')
    alive = process is not None and process.poll() is None
    if summary:
        status = 'completed' if summary['complete'] else 'stopped'
    else:
        status = 'running' if alive else 'starting_or_needs_check'
    reported = budget.get('reported_cost_usd', 0)
    cost = dict(reported_cost_usd=reported,
        uncertain_reserved_usd=budget.get('uncertain_reserved_usd', 0),
        pending_reserved_usd=budget.get('pending_reserved_usd', 0), stop_budget_usd=2,
        projected_cost_usd=reported * 336 / len(rows) if rows else None,
        projection_note='Rough extrapolation by completed trials; conditions differ in call counts. Not a guarantee.',
        api_calls=sum(r.get('api_calls', 0) for r in rows),
        accounting='This batch API usage.cost only; not the shared account balance or other members usage.')
    if summary:
        cost.update({k: summary['budget'].get(k, cost.get(k, 0)) for k in
                     ('reported_cost_usd', 'uncertain_reserved_usd', 'pending_reserved_usd')})
    report = dict(updated_at=now(), run_id=run_id, status=status, recorded=len(rows), planned=336,
        completion_percent=round(len(rows) / 336 * 100, 2), cost=cost,
        task_successes=sum(r.get('native_utility') is True for r in rows),
        errored_records=sum(bool(r.get('error')) for r in rows),
        last_result_age_seconds=round(time.time() - (folder / 'results.json').stat().st_mtime) if rows else None,
        complete=bool(summary and summary['complete']),
        fatal_error_type=summary['fatal_error']['type'] if summary and summary.get('fatal_error') else None)
    save(OUTPUT / 'progress.json', report)
    save(OUTPUT / 'cost_summary.json', cost)
    (OUTPUT / 'STATUS.md').write_text(
        '# 实验进度\n\n'
        f'- 更新时间：{report["updated_at"]}\n- 状态：{status}\n'
        f'- 已记录：{len(rows)} / 336（{report["completion_percent"]}%）\n'
        f'- API 已报告费用：${cost["reported_cost_usd"]:.8f}\n'
        f'- 待结算预留：${cost["pending_reserved_usd"]:.2f}\n'
        f'- 不确定费用预留：${cost["uncertain_reserved_usd"]:.2f}\n'
        f'- 错误记录：{report["errored_records"]}；失败保留，不自动重复\n\n'
        '只有 complete=true 才表示本份记录完整，不表示每个用户任务均成功。\n', encoding='utf-8')
    return report


def watch(run_id):
    env = os.environ.copy()
    env.update(PYTHONHASHSEED='0', TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
    log = (STATE / (run_id + '.log')).open('x')
    process = subprocess.Popen(['/usr/bin/caffeinate', '-i', '/bin/bash',
        str(LOCAL / 'person2.sh'), 'run', '--run-id', run_id], cwd=ROOT,
        env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    save(STATE / 'supervisor-process.json', dict(run_id=run_id, supervisor_pid=os.getpid(),
        runner_pid=process.pid, started_at=now()))
    while True:
        refresh(run_id, process)
        if process.poll() is not None:
            break
        time.sleep(30)
    log.close()
    report = refresh(run_id, process)
    if report['complete']:
        sys.path.insert(0, str(LOCAL))
        from person2 import export_local
        export_local(ROOT / 'runs/studies' / run_id / 'shard-01', OUTPUT)
        # The in-progress copy remains labeled, and the validated final CSV is separate.
        (OUTPUT / 'PROGRESS.md').write_text(
            '# 第 2 人本地实验交付\n\n'
            '- 已运行原始 336 个唯一试验 ID，完整性检查通过。\n'
            '- 完整私有轨迹保留；脱敏 results.csv 和 local-receipt.json 已导出。\n'
            '- 实际平台为 Mac，本地适配与 Vanda 验收差异见 ENVIRONMENT.md。\n'
            '- 待本人检查；未提交 GitHub 或 PR，未合并其他分支。\n', encoding='utf-8')
    save(STATE / 'supervisor-exit.json', dict(finished_at=now(), runner_returncode=process.returncode,
        complete=report['complete'], recorded=report['recorded']))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('start', 'watch', 'status'))
    parser.add_argument('--run-id', default='local-person2-20261019-001')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    if args.command == 'start':
        if list(STATE.glob('claim-*.json')) or (STATE / 'supervisor-start.json').exists():
            raise RuntimeError('Batch already claimed or supervisor already launched; no repeat spending.')
        stage(args.run_id)
        with (STATE / 'supervisor-start.json').open('x') as stream:
            json.dump(dict(run_id=args.run_id, requested_at=now()), stream)
        env = os.environ.copy()
        env.update(PYTHONHASHSEED='0', TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
        with (STATE / 'supervisor.log').open('x') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'watch', '--run-id', args.run_id],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
        print(json.dumps(dict(started=True, supervisor_pid=process.pid, output=str(OUTPUT))))
    elif args.command == 'watch':
        watch(args.run_id)
    else:
        print(json.dumps(read(OUTPUT / 'progress.json', {'started': False}), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
