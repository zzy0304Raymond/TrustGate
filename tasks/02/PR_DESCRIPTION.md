## 本次解决的问题

第2份此前缺少可审核的实验交付。本变更提供原清单336/336条脱敏结果（实际API费用$0.72108042），仅交付一份完整results.csv；暂停前150条与恢复后186条已合并，另附精确费用和第151条缓存恢复说明。分段备份只保留本地。

本交付使用 Mac 本机 CPU。原实验源代码、任务、权限、攻击、检测器权重与模型供应商保持冻结版本。平台差异与恢复计时口径见 [正式结果说明](../../results/formal/README_ZH.md)。

## 改动与接口影响

- 新增person-02的results.csv、标准字段receipt.json、原local-receipt.json、ENVIRONMENT.md、ACCOUNTING.json、RECOVERY.json、审计与校验和；不提交分段CSV。
- 新增独立Mac启动、进度与有界缓存恢复代码；保留原Vanda脚本，不修改trustgate/及experiments/mvp/冻结源码。
- receipt.json如实记录torch 2.7.1（原为2.7.1+cu126）、无PBS及pending_team_platform_review。标准汇总脚本能读取不代表已经批准平台等效性。
- 同一试验只计一次。第151条已付费的5次响应经逐请求一致性验证后复用，从第6次请求继续；完整旧尝试仍保存在私有目录。其历史API耗时由文件时间恢复，分析延迟须标注。

## 验证

- 基准commit：30ff95593fa27ee117991ef0da5d71d3eb5294d5；Python 3.10.20；原plan SHA b1817378e174e1cd742acedc465e63620a1dbe3bdbdca92c86c70d26d01f42c6。
- 离线环境与传输检查：37项测试、24个MCP工具、60个攻击传输检查。
- 结果复核：336次原生用户任务评分、252次攻击目标评分与原记录一致；CSV全部公开字段与原始记录一致；1338个唯一API响应费用匹配$0.72108042，待结算/不确定预留均为0。
- 提交包复核：`python tasks/02/prepare_delivery.py --check`。
- 与其他四份交付的格式联检：未修改的原汇总器在临时目录读取1,680/1,680个唯一ID，complete=true；这仅验证格式与身份完整性，不代替平台验收。
- 数据清单检查：`python tasks/02/prepare_delivery.py --check --require-validated` 核对当前交付文件与正式数据清单完全一致。
- 密钥、下载模型、原始对话及邮箱/文件状态均不提交。

## 研究结果与局限

原生任务评估通过168/336；314次流程生成最终回答，20次达到调用上限，2次达到拒绝上限；失败均保留。

该分片无防护输出攻击0/18、说明攻击0/18成功，不能据此证明防护优于无防护。检测器误报正常日期工具；严格已读状态/关键词评分及单个恢复试验时延均需说明。详见AUDIT_ZH.txt和AUDIT_REPORT.json。

## 对应任务

第 2 人，experiment-2，正式清单中的 person-02 分片。
