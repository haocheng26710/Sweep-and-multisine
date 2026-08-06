# DEV-D Acquisition Plan 模板

> 本文件必须由实验负责人填写和审批。尖括号内容均为待填写；不得让软件猜测设备、方向数、样本量、阈值或重复结构。

## 1. 计划与责任

- Plan ID：`<待填写>`
- 版本/日期：`<待填写>`
- 研究负责人/操作者/安全负责人/数据保管人：`<待填写>`
- 诊断目标与明确非目标：`<待填写>`
- 批准的 Git commit、config hash、acceptance manifest hash：`<待填写>`

## 2. 设备、空间和连接

- 声卡/麦克风/前置/扬声器/功放型号与序列号：`<待填写>`
- 驱动/固件/操作系统：`<待填写>`
- 通道、极性、增益、phantom power、线缆/接地：`<待填写>`
- 空间、安装、参考位置、环境噪声与温湿度记录法：`<待填写>`
- 校准文件、来源、日期、适用范围与 SHA-256：`<待填写或 unavailable>`
- 安全声压/功率限制和停止动作：`<待填写>`

## 3. 采样、时钟与刺激

- Sample rate / bit depth / source format：`<待填写>`
- 输入输出时钟拓扑与 common-clock 证据：`<待填写>`
- 系统 DSP/AGC/EQ/resampling 状态：`<待填写>`
- Sweep 配置：`<待填写>`
- Diagnostic multisine stimulus ID/hash、tone set、period、preamble、stable/discard periods、channel：`<待填写>`
- 诊断 delay/drift/clipping/QC 接受策略及其批准来源：`<待填写>`

## 4. 预注册条件矩阵

在采集前逐行列出，不得由已存在文件反推：

| measurement_mode | configuration_id | direction_id | session_id | repeat_type | reposition_round_id | assembly_id | acquisition_block_id | expected_count | role | reason |
|---|---|---|---|---|---|---|---|---:|---|---|
| `<待填写>` | `<待填写>` | `<待填写>` | `<待填写>` | `CONT/REPOS/REASM` | `<待填写>` | `<待填写>` | `<待填写>` | `<待填写>` | `calibration/training/development/final_test` | `<待填写>` |

预注册的方向数量、样本量、session/repeat/reposition/assembly 结构和采集顺序：`<待填写并说明依据>`。

## 5. 文件与 metadata 约定

- 原始数据根目录与只读策略：`<待填写>`
- 备份 A/B 位置、校验与恢复负责人：`<待填写>`
- REW TXT 导出设置与 metadata 记录：`<待填写>`
- WAV sidecar 模板位置和 stimulus manifest 位置：`<待填写>`
- sample ID 分配规则（不得承载隐藏标签）：`<待填写>`
- provenance record URI、source hash、采集时间/操作者记录方式：`<待填写>`
- manual-review queue 负责人和 SLA：`<待填写>`

## 6. Final-test 封存与冻结点

- Final-test 分配方法和时间：`<待填写>`
- 清单/hash 保管人、访问权限和解封审批：`<待填写>`
- 开发期间可见信息与禁止访问内容：`<待填写>`
- 真实 QC threshold 冻结点：`<待填写>`
- 真实 preprocessing/tone set/minimum-tone/calibration/model/readout package 冻结点：`<待填写>`
- 冻结后变更控制和 incident 流程：`<待填写>`

## 7. 执行顺序与停止条件

- 低电平设备/通道检查：`<待填写>`
- Diagnostic sweep/multisine 顺序：`<待填写>`
- 每 block 的现场 hash/备份/QC 检查：`<待填写>`
- 削波、异常声压、hash/sample-rate/clock/metadata/备份/final-test 泄漏等停止条件：`<待填写>`
- 失败后的隔离、复测、偏差记录和人工批准规则：`<待填写>`

## 8. 人工审批记录

| Gate | 决定 | 审批人 | 日期/时间 | 证据/备注 |
|---|---|---|---|---|
| 开始 diagnostic acquisition | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |
| 进入 training/development 正式采集 | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |
| 冻结真实 tone/calibration/model | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |
| 解封 final-test | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |
