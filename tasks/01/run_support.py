"""Person-01 provenance and passive cost monitoring; never sends model requests."""
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from trustgate.formal_manifest import verify_runtime
from trustgate.planning import read_plan
from trustgate.runner import require_compute


def read_json(path):
    return json.loads(path.read_text())


def environment(stage):
    require_compute()
    plan = read_plan(ROOT / 'assignments/formal/plan.json')
    detector = Path(os.environ['TRUSTGATE_DETECTOR_DIR'])
    verify_runtime(plan, detector)
    key_path = Path(os.environ['TRUSTGATE_KEY_FILE'])
    if not key_path.is_file() or key_path.stat().st_mode & 0o077:
        raise RuntimeError('Missing credential file or unsafe credential permissions.')
    shard = plan['shards'][0]
    assert len(shard['cases']) == 336 and shard['person'] == 1
    assert shard['budget_usd'] == 2.0
    assert {c['task'] for c in shard['cases']} == {
        'user_task_0', 'user_task_12', 'user_task_17', 'user_task_31'}
    cpu_model = next((line.split(':', 1)[1].strip()
                      for line in Path('/proc/cpuinfo').read_text().splitlines()
                      if line.startswith('model name')), 'unknown')
    prep = Path(os.environ['TRUSTGATE_PREP_DIR'])
    run_dir = ROOT / 'runs/studies' / os.environ['TRUSTGATE_RUN_ID'] / 'shard-00'
    info = {
        'stage': stage,
        'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'cluster': 'Vanda', 'host': socket.gethostname(),
        'pbs_job_id': os.environ['PBS_JOBID'],
        'platform': platform.platform(), 'os_release': Path('/etc/os-release').read_text(),
        'cpu_model': cpu_model, 'requested_cpus': 2, 'requested_memory_gb': 8,
        'requested_gpus': 0, 'detector_device': 'cpu',
        'python': platform.python_version(), 'python_executable': sys.executable,
        'git_commit_at_launch': os.environ['TRUSTGATE_RUN_COMMIT'],
        'plan_sha256': plan['plan_sha256'], 'source_sha256': plan['source_sha256'],
        'packages': {name: importlib.metadata.version(name) for name in plan['packages']},
        'run_id': os.environ['TRUSTGATE_RUN_ID'], 'shard_index': 0,
        'startup_environment': {name: os.environ.get(name) for name in (
            'PYTHONHASHSEED', 'TOKENIZERS_PARALLELISM', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
            'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE')},
        'launcher_sha256': hashlib.sha256((ROOT / 'tasks/01/run_person01.pbs').read_bytes()).hexdigest(),
        'support_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'frozen_runtime_verified': True, 'credential_owner_only': True,
    }
    if stage == 'completed':
        worker = read_json(run_dir / 'worker_summary.json')
        receipt = read_json(ROOT / 'experiments/deliveries/person-01/receipt.json')
        assert worker['complete'] and worker['fatal_error'] is None
        assert worker['recorded'] == receipt['recorded'] == 336
        info['worker_summary'] = worker
    (prep / f'environment_{stage}.json').write_text(json.dumps(info, indent=2) + '\n')
    print('ENVIRONMENT_CHECK=' + json.dumps({
        k: info[k] for k in ('stage', 'host', 'pbs_job_id', 'python', 'plan_sha256', 'frozen_runtime_verified')
    }), flush=True)
    if stage == 'before':
        return
    delivery = ROOT / 'experiments/deliveries/person-01'
    delivery.mkdir(parents=True, exist_ok=True)
    package_lines = '\n'.join(f'- `{name}=={version}`' for name, version in info['packages'].items())
    completion = ('336/336，`complete=true`，`fatal_error=null`。'
                  if stage == 'completed' else '离线检查通过；正式运行及导出尚未完成。')
    cost = (f"\n- 实际已报告 API 费用：${worker['budget']['reported_cost_usd']:.8f}。\n"
            if stage == 'completed' else '')
    text = f'''# person-01 运行环境

- 平台：Vanda；调度器：PBS；作业 `{info['pbs_job_id']}`；节点 `{info['host']}`。
- 操作系统：`{info['platform']}`。
- CPU：{cpu_model}；申请 2 CPU、8 GB 内存、6 小时。队列可调整实际内存，以 PBS 记录为准。
- GPU：未申请、未使用；检测器在 CPU 上运行。
- Conda：`dsa4213`；Python `{info['python']}`；使用既有冻结环境，没有安装或升级依赖。
- 启动时 Git 基准 commit：`{info['git_commit_at_launch']}`；分支 `experiment-1`。本人新增启动与记录脚本在启动时尚未提交，其 SHA-256 另存于私有环境记录；冻结执行代码与清单一致。
- 正式清单 SHA：`{info['plan_sha256']}`。
- 运行编号：`{info['run_id']}`；分片：`shard-00`；人员：`person-01`。
- 当前状态：{completion}
{cost}
## 关键依赖

{package_lines}

## 模型与启动

- API：`qwen/qwen3-30b-a3b-instruct-2507`，供应商 `SiliconFlow`，temperature=0。
- 检测器：`protectai/deberta-v3-base-prompt-injection-v2`，阈值 0.5；模型文件哈希通过冻结清单校验。
- Python 启动前设置 `PYTHONHASHSEED=0`、`TOKENIZERS_PARALLELISM=false`、`OMP_NUM_THREADS=2`、`MKL_NUM_THREADS=2`。
- 本人入口：`qsub tasks/01/run_person01.pbs`。脚本使用私有 Group 9 密钥文件路径，不包含密钥值。
- 入口先做离线检查，再调用仓库原有 `scripts/formal/person-1.pbs`，仅运行 shard-00，完成后调用原有导出工具。
- 公共执行器、任务、攻击、模型、依赖和正式清单均未修改。新增代码仅记录本人环境、被动监控费用和安排检查/导出。
- 本份 API 预算 $2，每次请求预留 $0.05。被动监控在 $1.50 写入费用提醒文件和日志，需由监控人员读取后向用户询问；该脚本不会自行发送通知。冻结执行器仍保留原预算停止行为及无自动续跑限制。$2 后继续需要单独审查，不能删除目录重跑。

## 验证与记录

- `pip check`、全部离线单元测试、MVP MCP 预检、解析恢复检查、正式 MCP 预检均通过后才启动 API 实验。
- 正式预检包含 60 个攻击传输检查、20 个任务流程检查、14 个配置/入口流程检查，使用脚本回复，不计入正式模型结果。
- 源代码、关键依赖、检测器哈希由原冻结校验器验证。
- 私有准备日志及机器可读环境记录：`runs/person01-preparation/{info['pbs_job_id']}/`。
- 私有正式记录：`runs/studies/{info['run_id']}/shard-00/`，完整保留，不提交原始请求、模拟状态或密钥。
'''
    (delivery / 'ENVIRONMENT.md').write_text(text)


def monitor():
    require_compute()
    run_dir = ROOT / 'runs/studies' / os.environ['TRUSTGATE_RUN_ID'] / 'shard-00'
    warned = False
    previous = None
    while True:
        try:
            budget = read_json(run_dir / 'budget.json') if (run_dir / 'budget.json').exists() else {}
            rows = read_json(run_dir / 'results.json') if (run_dir / 'results.json').exists() else []
            cost = budget.get('reported_cost_usd', 0)
            state = {'recorded': len(rows), 'planned': 336, 'reported_cost_usd': cost,
                     'uncertain_reserved_usd': budget.get('uncertain_reserved_usd', 0)}
            if state != previous:
                print('PERSON01_PROGRESS=' + json.dumps(state), flush=True)
                previous = state
            if cost >= 1.50 and not warned:
                alert = {'message': 'Ask the user before any additional budget is authorized.', **state}
                Path(os.environ['TRUSTGATE_PREP_DIR'], 'budget_attention.json').write_text(json.dumps(alert, indent=2) + '\n')
                print('BUDGET_ATTENTION=' + json.dumps(alert), flush=True)
                warned = True
            if (run_dir / 'worker_summary.json').exists():
                return
        except (FileNotFoundError, json.JSONDecodeError):
            # The frozen results writer replaces the JSON contents non-atomically.
            pass
        time.sleep(30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('environment', 'monitor'))
    parser.add_argument('stage', nargs='?', choices=('before', 'preflight_passed', 'completed'))
    args = parser.parse_args()
    if args.command == 'environment':
        if args.stage is None:
            parser.error('environment requires a stage')
        environment(args.stage)
    else:
        monitor()
