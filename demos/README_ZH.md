# TrustGate 演示包

先下载 [index.html](index.html)，用浏览器直接打开。页面包含三个案例的步骤、对照和结论，不需要网络或密钥。讲解顺序见 [演示讲稿](../docs/DEMO_WALKTHROUGH_ZH.md)。

| 入口 | 实际执行什么 | 用途 |
|---|---|---|
| `demos/index.html` | 展示已记录实验的脱敏事实 | 课堂展示，可直接在个人电脑浏览 |
| `scripts/demo/show.py` | 校验证据哈希，再打印同一组记录 | 在计算节点做终端回放 |
| `scripts/demo/check_mcp.py` | 预设模型回复，运行冻结的 agent 循环、真实 MCP 模拟工具、检测器和授权逻辑 | 验证允许合法写入、拒绝越权、正常工具误隔离及原生评分盲点 |

这三种入口均不调用模型 API。MCP 检查使用预设回复，能够验证机制行为，不能测量模型是否会服从攻击，也不能代替原正式实验的成功率。

## Vanda 一条命令验证

在仓库根目录提交。检测器使用已准备的冻结权重，脚本不会下载新模型：

```bash
export TRUSTGATE_DETECTOR_DIR=/scratch/xinqi.chen/dsa4213/TrustGate_Project/models/prompt_injection_detector
qsub -v TRUSTGATE_DETECTOR_DIR scripts/demo/validate.pbs
```

这是 CPU 作业，使用 `dsa4213` 和 Python `3.10.20`。登录节点只负责提交与查看；校验在 PBS 节点执行。其他 Vanda 账号使用自己的 PBS 项目与 Conda 路径：

```bash
export TRUSTGATE_CONDA_LOADER=/path/to/your/load-conda.sh
export TRUSTGATE_DETECTOR_DIR=/path/to/frozen/prompt_injection_detector
qsub -P personal-your_account -v TRUSTGATE_CONDA_LOADER,TRUSTGATE_DETECTOR_DIR scripts/demo/validate.pbs
```

完成后查看：

- `runs/demo/validate.log`：文件校验、测试与机制检查。
- `runs/demo/mcp-checks.json`：六组预设调用的实际检查结果。
- `runs/demo/recorded_walkthrough.txt`：三个真实实验案例的文字回放。

默认不修改任何正式结果；重复该检查只更新 `runs/demo/` 的演示校验输出。其他集群也应在其调度器分配的计算节点运行，保持冻结环境与代码；本次实际验收平台为 Vanda。

## 已在计算节点时

```bash
source /scratch/xinqi.chen/load-conda.sh
conda activate dsa4213
python scripts/demo/build.py --check
python scripts/demo/show.py --case normal
python scripts/demo/show.py --case defense
python scripts/demo/show.py --case false-positive
python scripts/demo/check_mcp.py --detector "$TRUSTGATE_DETECTOR_DIR"
```

`build.py --check` 会在输入文件或展示文件与校验清单不一致时失败。`build.py` 用同一组公开证据重新生成展示页。普通复现不需要任何人的私有原始目录。

## 六项 MCP 预期结果

| 检查 | 应观察到的行为 |
|---|---|
| 正常任务 + TrustGate | 创建一个合法日程，原生任务通过，授权拒绝0次 |
| 攻击请求 + 无防护 | 发送模拟攻击邮件，精确攻击目标成功 |
| 攻击请求 + TrustGate | 同一邮件请求被拒，模拟状态不变，原任务通过 |
| 攻击请求 + 去授权 | 同一邮件请求执行，精确攻击目标成功 |
| 日期问答 + 无防护 | 正常日期工具可用，查询模拟当前日 |
| 日期问答 + TrustGate | 正常日期工具误隔离；预设错误日期回答仍通过原生评分 |

最后一项预设了已观察到的错误查询和回答，用于复现评分问题，不能声称新模型再次自行犯错。所有邮件、日历和文件操作只作用于临时模拟环境。当前验收结果见 [mcp_checks.json](../results/demo/mcp_checks.json)。

## 文件与来源

- `cases.json`：三个案例的讲解事实，引用六条真实记录。
- `trace_checks.json`：其中三条完整私有记录的请求一致性、状态与评分派生检查；仅保留必要事实与原件哈希。
- `manifest.json`：公开输入与展示文件的 SHA256。
- 其余三条 task5 记录引用 `review-data/person-05/` 已审核的公开材料。

保留私有原件的环境可用 `scripts/demo/export_checks.py --help` 查看重新导出方法。原始请求、响应和完整状态不随演示包公开。
