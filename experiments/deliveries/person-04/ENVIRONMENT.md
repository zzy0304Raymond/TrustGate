# 第 4 人运行环境

- 集群：NUS Vanda（PBS），运行主机 CN-016，作业号 1462590.stdct-mgmt-02
- 系统：Red Hat Enterprise Linux 9.4；CPU：Intel Xeon Platinum 8452Y；只用 CPU，未申请 GPU（select=1:ncpus=2:mem=8gb）
- Python 3.10.20，自建 Miniforge 环境（/scratch/<用户>/miniforge3，环境名 dsa4213），按 requirements-runtime-constraints.txt 安装
- 关键依赖：见同目录 receipt.json 的 packages 字段（与冻结清单一致，启动时已通过校验）
- Git commit：a37fc06258e80ffb0d63298e1fab0c11b4065dca；分支 experiment-4
- 清单 SHA：b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6；运行编号 formal-v1-001；分片 shard-03
- 检测器：protectai/deberta-v3-base-prompt-injection-v2，revision 90c9989b1a342275dd0d1a95aad283c04e075671，用 huggingface_hub 直接下载，文件哈希经启动校验
- 启动脚本：scripts/platforms/vanda-jingfangxue/person-4.pbs，由 scripts/formal/person-4.pbs 复制而来，只改了两处：conda 加载路径换成自建 Miniforge；在正式运行前加入离线检查（unittest 和 scripts/formal/preflight.py），检查失败则不调用 API
- 未修改任何 .py 文件、配置或清单
- 结果：336/336 记录，complete=true，fatal_error=null；墙钟约 7,213 秒；API 报告费用 $0.455
