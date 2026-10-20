# 第 5 人运行环境

- 集群：NUS Vanda（PBS），队列 batch_cpu（经 auto 路由），运行主机 CN-017，作业号 1465592.stdct-mgmt-02
- 系统：Red Hat Enterprise Linux 9.4；CPU 节点 72 核，作业只用 2 核、未申请 GPU（select=1:ncpus=2:mem=8gb，调度器实际分配 13GB）
- Python 3.10.20，自建 Miniforge 环境（/scratch/<用户>/miniforge3，环境名 dsa4213）；torch==2.7.1+cu126 按 docs/REPRODUCE_ZH.md 安装，其余按 requirements-runtime-constraints.txt 安装，pip check 无冲突
- 关键依赖：agentdojo 0.1.35、mcp 1.26.0、transformers 4.53.3、torch 2.7.1+cu126（见同目录 receipt.json，与冻结清单一致，启动时已通过校验）
- Git commit：ac919b6fe569984eb822c70a47e2a1400468e2fd；分支 experiment-5
- 清单 SHA：b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6；运行编号 formal-v1-001；分片 shard-04
- 检测器：protectai/deberta-v3-base-prompt-injection-v2，revision 90c9989b1a342275dd0d1a95aad283c04e075671，用 huggingface_hub 直接下载到私有缓存，文件哈希经启动校验
- 启动脚本：scripts/platforms/vanda-tangjiayi/person-5.pbs，由 scripts/formal/person-5.pbs 复制而来，只改了两处：conda 加载路径换成自建 Miniforge；在正式运行前加入离线检查（unittest 和 scripts/formal/preflight.py），检查失败则不调用 API
- 启动方式（不含密钥值）：在仓库根目录设置 TRUSTGATE_RUN_ID、TRUSTGATE_KEY_FILE（权限 600 的私有文件）、TRUSTGATE_DETECTOR_DIR 后 `qsub -v TRUSTGATE_RUN_ID,TRUSTGATE_KEY_FILE,TRUSTGATE_DETECTOR_DIR scripts/platforms/vanda-tangjiayi/person-5.pbs`
- 开跑前另行在计算节点 CN-017 做过无 API 检查：33 个单元测试通过，formal preflight 通过，trustgate inspect 与 formal_manifest.verify_runtime 通过
- 未修改任何 .py 文件、配置或清单
- 结果：336/336 记录，336 个 case_id 唯一且与清单 shard-04 完全一致，complete=true，fatal_error=null；墙钟约 9,343 秒；API 报告费用 $0.670（预算 $2，未触发停止）
- 记录状态：completed 302 次，model_call_budget 34 次（达到每试验 8 次调用上限），均按原样保留
- 导出：在计算节点 CN-016 运行 `python -m trustgate export`（作业 1465907），生成本目录 results.csv 与 receipt.json
