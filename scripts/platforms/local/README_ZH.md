# experiment-2 本机配置

本目录为 macOS arm64 的独立运行入口。当前仅配置与离线验证，未启动正式试验，也未调用付费模型 API。

## 文件位置

- `person2.sh`：启动入口，固定随机种子、CPU 线程和项目 Python 环境。
- `person2.py`：第 2 人本地适配器；复用原始实验循环、数据、策略和 MCP 服务，不伪造 PBS 环境。
- `requirements.txt`、`constraints-macos.txt`：本地依赖配置。
- `tests_local.py`：离线检查，包括防重复启动、网络失败时停止计费、脱敏导出。
- 仓库根目录 `.venv/`：Python 3.10.20 实验环境。
- 仓库根目录 `.runtime/`、`.bootstrap/`：环境管理器、Python 安装和下载缓存，仅本机保存。
- 仓库根目录 `models/prompt_injection_detector/`：固定 revision 的检测器文件，已按原清单校验。
- 仓库根目录 `.secrets/openrouter_group9.key`：私有凭据；仅本人读写，不提交 Git。
- 仓库根目录 `runs/local-person2/execution.json`：本次本地配置指纹。
- 仓库根目录 `runs/local-person2/offline-check.json`：离线验证结果，不是正式模型实验结果。

## 保留的实验设置

只运行原始 `assignments/formal/plan.json` 的第 2 份（索引 1），原顺序的 336 个 ID：84 个正常、126 个输出攻击、126 个说明攻击。模型、SiliconFlow 供应商、温度、七配置、重复次数、检测器阈值与权重均保留。

API 停止预算 2 美元，每次请求预留 0.05 美元；费用未知或网络故障停止，不自动重试。失败记录保留。准备好的同一批次只能领取一次，不支持自动续跑，禁止删除记录后重复整份。

## 平台差异

原始冻结源代码、数据和 plan 均未修改；Vanda 的 PBS 入口保留。Mac 使用 CPU `torch==2.7.1`，原平台为 `2.7.1+cu126`；其他关键包版本相同。平台专用适配器单独校验，保留自己的配置指纹，不能直接将其当作通过 Vanda 验收的原环境结果。正式合并前仍需与全组协调平台版本并完成验收。

本地导出使用 `local-receipt.json`，不生成可被上游汇总误当作原版结果的 `receipt.json`。

## 配置检查（不调用模型 API）

在仓库根目录运行：

```bash
bash scripts/platforms/local/person2.sh status
bash scripts/platforms/local/person2.sh check
```

离线测试：

```bash
PYTHONHASHSEED=0 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  .venv/bin/python scripts/platforms/local/tests_local.py
```

## 以后明确启动时使用

以下命令会调用模型 API；本次配置未执行此命令。

```bash
bash scripts/platforms/local/person2.sh run --run-id local-person2-20261019-001
```

保持机器唤醒、网络稳定，运行期间不要修改配置或实验文件。进度和完整私有轨迹保存在 `runs/studies/<运行编号>/shard-01/`。可以在另一个终端执行 `status` 查看进度。中断、费用或网络错误出现时，保留全部记录，另行确定后续方案，不重新执行整份。

完成后可按需导出到独立的本地交付目录：

```bash
bash scripts/platforms/local/person2.sh export \
  --folder runs/studies/local-person2-20261019-001/shard-01 \
  --destination experiments/deliveries/person-02-local
```

准备、检查和状态命令不会启动模型试验。`account` 为可选的只读 API 身份检查，本次也未执行。
