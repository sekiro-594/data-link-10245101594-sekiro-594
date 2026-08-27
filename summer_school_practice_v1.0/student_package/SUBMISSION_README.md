# M6 综合运行说明

## 基本信息

- 姓名：茆宇航
- 学号：10245101594
- GitHub 用户名：sekiro-594
- Python 版本：3.10 及以上
- SQLite：已实现，用于 M3 接收记录持久化验证
- M4 候选来源：课程预生成候选，最终规则经过人工核验

## 安装与运行

在 `summer_school_practice_v1.0` 目录按 `environment/README_environment.md` 创建课程 `.venv`，然后执行：

```powershell
.\.venv\Scripts\python.exe student_package\src_skeleton\run_all.py
```

## 程序入口与调用顺序

统一入口为 `student_package/src_skeleton/run_all.py`，依次执行：OpenSky 解析、TeachingLink 编码、接收解码与校验、多时刻航迹/当前态势、人工核验映射、统一消息、一致性检查和结果汇总。

## 输入文件

- M2：`data/raw_states.json`、`schema/teaching_message_spec.md`
- M3：`data/partner_messages_multitime.bin`
- M4：`data/m4/partner_current_situation.csv`、字段定义、统一模型与预生成候选
- M5：`data/m5/anomaly_cases.csv`、`data/m5/anomaly_rules.csv`

## 关键输出

- M2：`encoded_messages.bin`、`decoded_partner_states.csv`、`validation_log.csv`、`roundtrip_report.csv`
- M3：`decoded_multitime.csv`、`track_table.csv`、`current_situation.csv`、`states.db`
- M4：`llm_mapping_candidate.csv`、`verified_mapping_table.csv`、`unified_situation.ndjson`
- M5：`alert_log.csv`、`quality_situation.csv`
- M6：`experiment_summary.json` 及 `docs/M6_presentation.pptx`

## 实验结果

- 原始状态向量：5 条；满足必需字段与量程并成功编码：3 条。
- TeachingLink 输出：3 帧，共 123 字节；成功解码 3 帧。
- 多时刻输入：9 帧，共 369 字节；形成 3 个目标航迹和 3 条当前态势。
- 统一消息：6 条（OpenSky/TeachingLink 两类来源）。
- 一致性告警：5 条，其中 HIGH 1 条、MEDIUM 4 条。
- 所有 CSV、JSON、NDJSON 可重新读取；SQLite 写入后可查询。

## 协议与质量语义

TeachingLink 是课程自定义教学协议。`message_valid` 只表示一帧通过长度、头字段、保留位、标志一致性和校验和检查；可选字段是否存在由有效位决定；缺失、延迟、重复和越界由 M5 业务规则判断。

## 已知限制

- 不包含底层信号、真实网络传输、传感器融合或生产数据库/Web 系统。
- 固定帧边界已对齐；按手册要求处理不完整尾帧，但不实现失步重同步。
- 映射只适用于课程给定字段定义，不能外推为真实装备协议。
- 姓名需由本人确认；最终 commit ID 以课程登记表中的提交记录为准。

## 最终提交信息

- 仓库链接：https://github.com/sekiro-594/data-link-10245101594-sekiro-594
- 最终 commit ID：以课程登记表中的最终提交记录为准
- 最后检查日期：2026-08-28
