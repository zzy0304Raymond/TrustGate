# person-01 运行环境

- 平台：Vanda；调度器：PBS；作业 `1462633.stdct-mgmt-02`；节点 `CN-016`。
- 操作系统：Red Hat Enterprise Linux 9.4；`Linux-5.14.0-427.134.1.el9_4.x86_64-x86_64-with-glibc2.34`。
- CPU：Intel(R) Xeon(R) Platinum 8452Y；申请 2 CPU、8 GB 内存、6 小时；PBS 实际分配 2 CPU、13 GB 内存。
- GPU：未申请、未使用；检测器在 CPU 上运行。
- Conda：`dsa4213`；Python `3.10.20`；使用既有冻结环境，没有安装或升级依赖。
- 启动时 Git 基准 commit：`92888fc2fbd09ef967f1af25a657df94d3e42d56`；分支 `experiment-1`。本人新增启动与记录脚本在启动时尚未提交，其 SHA-256 另存于私有环境记录；冻结执行代码与清单一致。
- 正式清单 SHA：`b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6`。
- 运行编号：`formal-v1-001`；分片：`shard-00`；人员：`person-01`。
- 当前状态：336/336，`complete=true`，`fatal_error=null`。
- 实际已报告 API 费用：$0.71732400。
- PBS 开始：2026-10-16 23:08:25 SGT；结束：2026-10-17 02:04:04 SGT；PBS 记录墙钟时间 2 小时 55 分 38 秒。
- 正式执行器计时：10,415.43 秒（约 2 小时 53 分 35 秒）；其余为检查及导出等开销。
- 费用账本无未决或未知费用，未触发预算停止；上述费用仅属于本份正式实验，不是共享 API 账号累计费用。

## 关键依赖

- `agentdojo==0.1.35`
- `mcp==1.26.0`
- `transformers==4.53.3`
- `torch==2.7.1+cu126`
- `pydantic==2.14.1`
- `openai==3.31.0`

## 模型与启动

- API：`qwen/qwen3-30b-a3b-instruct-2507`，供应商 `SiliconFlow`，temperature=0。
- 检测器：`protectai/deberta-v3-base-prompt-injection-v2`，阈值 0.5；模型文件哈希通过冻结清单校验。
- Python 启动前设置 `PYTHONHASHSEED=0`、`TOKENIZERS_PARALLELISM=false`、`OMP_NUM_THREADS=2`、`MKL_NUM_THREADS=2`。
- 本人入口：`qsub tasks/01/run_person01.pbs`。脚本使用私有 Group 9 密钥文件路径，不包含密钥值。
- 入口先做离线检查，再调用仓库原有 `scripts/formal/person-1.pbs`，仅运行 shard-00，完成后调用原有导出工具。
- 公共执行器、任务、攻击、模型、依赖和正式清单均未修改。新增代码仅记录本人环境、被动监控费用和安排检查/导出。
- 本份 API 预算 $2，每次请求预留 $0.05。被动监控在 $1.50 写入费用提醒文件和日志，需由监控人员读取后向用户询问；该脚本不会自行发送通知。冻结执行器仍保留原预算停止行为及无自动续跑限制。$2 后继续需要单独审查，不能删除目录重跑。

## 验证与记录

- `pip check`、33 项离线单元测试、MVP MCP 预检、解析恢复检查、正式 MCP 预检均通过后才启动 API 实验。
- 正式预检包含 60 个攻击传输检查、20 个任务流程检查、14 个配置/入口流程检查，使用脚本回复，不计入正式模型结果。
- 源代码、关键依赖、检测器哈希由原冻结校验器验证。
- 原导出工具已验证 336 个试验 ID 与本人清单完全匹配、无重无漏；包含 84 次正常实验、126 次输出攻击和 126 次说明攻击。任务答错、拒绝与单次调用次数耗尽的记录均原样保留；记录完整不代表模型全部答对。
- 私有准备日志及机器可读环境记录：`runs/person01-preparation/1462633.stdct-mgmt-02/`。
- 私有正式记录：`runs/studies/formal-v1-001/shard-00/`，完整保留，不提交原始请求、模拟状态或密钥。
