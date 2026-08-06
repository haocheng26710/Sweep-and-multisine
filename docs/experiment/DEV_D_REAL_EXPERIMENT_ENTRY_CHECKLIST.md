# DEV-D 真实设备诊断实验进入清单

本清单是进入少量、受控、诊断性 `real_experiment` 采集前的人工门禁。它不自动批准科研分析、正式部署、最终 tone set、真实校准或 final-test 解封。所有空项必须由负责人填写和签字；不得从模拟配置复制资格字段。

## 1. 软件与审批

- [ ] DEV-C16 clean-tree acceptance：T0–T3 全 pass，V2 `14/14`，manifest hash 已复核。
- [ ] Git commit、配置 snapshot、Python/依赖版本和执行机器已记录。
- [ ] 本次仅为 diagnostic acquisition；研究问题、允许动作和停止条件已获人工批准。
- [ ] `final_test` 仍封存；采集操作者不能访问其目录/标签。
- [ ] 输出和原始数据的备份、校验、恢复与访问权限负责人已指定。

## 2. 设备链与安全

- [ ] 声卡/接口、麦克风、前置放大、扬声器、功放、线缆与供电的真实型号、序列号、固件/驱动已填写。
- [ ] 输入/输出通道映射、极性、phantom power、增益旋钮位置和接地已人工复核。
- [ ] 麦克风与扬声器校准文件来源、日期、hash 和适用范围已记录；没有校准时明确标为 unavailable。
- [ ] 安全声压/功率上限、听力/设备保护措施和紧急停止动作已批准。
- [ ] 空载/低电平试放通过，无削波、啸叫、异常噪声或接线风险。

## 3. Sample rate、时钟与延迟

- [ ] 声卡输入/输出 nominal sample rate 与 bit depth 已明确并锁定。
- [ ] 是否 common clock、时钟来源和路由有证据；不能确认时 phase 不得升级为 `common_clock`。
- [ ] 系统重采样、操作系统增强、自动增益、EQ、DSP 和无线链路状态已记录并按方案禁用或审计。
- [ ] 诊断 multisine 的 preamble、period、stable/discard periods、channel 与 manifest 完全匹配。
- [ ] 先运行低电平延迟/drift 诊断；超出 provisional policy 时停止，不现场调阈值以求通过。

## 4. 文件、metadata 与 provenance

- [ ] 每个原始 TXT/WAV 只读保存，采集后立即计算 SHA-256；不重命名后猜 metadata。
- [ ] 每个 multisine WAV 有独立 sidecar，并引用精确 stimulus manifest/tone set/hash。
- [ ] `MeasurementMeta` 的 sample/configuration/direction/session/repeat、reposition/assembly/block、channel/source format 均来自采集记录。
- [ ] `data_origin=real_experiment` 只在真实采集且 provenance 完整时使用；`eligible_for_scientific_analysis` 仍由独立 gate 决定。
- [ ] 模拟、external-reference、diagnostic real、training、development、final_test 物理目录和 manifest 硬隔离。
- [ ] 无法确认的字段进入 manual review；不从文件名、顺序或邻近样本推断。

## 5. 角色与 final-test 封存

- [ ] 每个 sample 在采集前分配 `calibration`、`training`、`development` 或 `final_test`，并记录分配依据。
- [ ] training/development 可用于真实阈值、tone/model/calibration 冻结；final-test 不得参与任何选择、拟合或 QC 阈值调整。
- [ ] final-test 清单、hash、密封时间、保管人、访问控制和解封审批已记录。
- [ ] 任何意外 final-test 访问立即停止流程、记录 incident 并使当前验收失效。

## 6. 采集前备份和 dry-run

- [ ] 空白 acquisition plan、metadata/sidecar 模板、配置、stimulus/manifest 已版本化并备份。
- [ ] 用非研究 diagnostic sample 完整走通写盘、hash、P1/P2/P8、失败报告和恢复流程。
- [ ] 主存储与独立备份均有足够空间；时钟同步、系统时间和时区已记录。
- [ ] 原始数据目录禁止 pipeline 覆盖；输出采用新 run-id。

## 7. 停止条件

出现以下任一情况立即停止，不继续采集或现场放宽阈值：数字/模拟削波、异常声压、啸叫、通道/极性错误、sample-rate/period/hash 不匹配、无法解释的 drift、缺失 sidecar/manifest、设备状态变化、provenance 中断、备份失败、final-test 泄漏或人工安全疑虑。

## 8. 从模拟 artifact 替换为真实 artifact

1. 复制 acquisition plan 模板并由负责人填满、审批；不要修改模拟 evidence 伪装成真实。
2. 生成本次真实 stimulus manifest/config snapshot，记录设备和采集角色。
3. 采集原始 REW TXT 或 WAV+sidecar，立即只读、hash、双份备份。
4. 先运行 P1/P2-A/P8 单测量诊断；保留 warning/exclude/manual review，不自动删除。
5. 仅在显式真实 dataset scope 和预期条件矩阵批准后运行 P2-B。
6. 只用 training/development 依序重跑 P3/P4/P5/P6/P9；所有真实阈值、tone、校准和模型重新冻结并单独审批。
7. final-test 保持封存，直到研究方案规定的唯一正式评估点。

## 人工批准记录

- 计划 ID：`<待填写>`
- 负责人：`<待填写>`
- 安全审核：`<待填写>`
- 数据管理审核：`<待填写>`
- final-test 保管人：`<待填写>`
- 批准时间与签名：`<待填写>`
- 备注/未解决项：`<待填写>`
