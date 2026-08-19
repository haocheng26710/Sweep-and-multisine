# FORMAL-2：正式采集包与采集前预检门禁

状态：采集基础设施完成；`ready_for_B01=false`；禁止开始正式测量

日期：2026-08-19

分支：`feature/v2-dual-input`

## 目标与权威边界

本轮依据且未修改：

- `docs/experiment/RESEARCH_PROTOCOL_REV002.md`
- `docs/experiment/FORMAL_ACQUISITION_PLAN_REV001.md`
- `docs/progress/FORMAL_1_LOG_GRID_PREPROCESSING.md`

目标是建立代码仓库之外的空白正式数据目录、从唯一冻结计划机械生成 96 行 manifest、提供现场填写模板、hash 基线及 fail-closed 备份/人工预检门禁。本轮没有采集、导入或分析任何真实数据，没有读取 pilot 或 final-test，也没有修改研究问题、阈值、对数网格、96 样本矩阵或采集顺序。

## 完成内容

新增 `acoustic_encoder.formal_acquisition` 深模块和命令：

```powershell
python scripts/prepare_formal_acquisition_package.py --root "D:\Bristol course\dissertation\formal_experiment_data\FORMAL-U4-4DIR-SWEEP-REV001"
```

公开能力包括：

- 从冻结 Markdown 表读取并验证唯一 96 行计划；
- 创建/复核幂等目录与不可覆盖模板；
- 验证 configuration × direction × CONT × REPOS × REASM 的 96 个唯一组合；
- 验证每个 sample ID 与行内身份、session、block 一致；
- 生成正式 manifest 与 B01 现场表；
- 显式校准文件复制与 hash；缺失时阻塞，不伪造；
- 生成和复核 `SHA256SUMS.json`/`.txt`；
- 验证 primary/backup_A/backup_B 的路径和物理介质声明；
- 拒绝把同一磁盘的目录/分区或 GitHub 冒充独立正式原始数据备份；
- 对不含实验数据的小型 simulated 文件执行不可覆盖的复制、SHA-256 核对和恢复演练；
- 保留全部人工项为空，不自动签署或推断通过。

## 正式数据根目录

实际创建并连续运行两次验证幂等性的根目录：

```text
D:\Bristol course\dissertation\formal_experiment_data\FORMAL-U4-4DIR-SWEEP-REV001\
```

目录包括：

- `00_protocol_and_manifests`
- `01_calibration`
- `02_photos_and_geometry`
- `03_environment_logs`
- `04_raw_rew_mdat/S01` 至 `S04`
- `05_exported_rew_txt/S01` 至 `S04`
- `06_metadata_sidecars/S01` 至 `S04`
- `07_hashes`
- `08_deviations_and_manual_review`

两次运行结果相同，没有删除或覆盖文件。当前 `.mdat=0`、REW TXT=0、sidecar=0；正式测量尚未开始。

该整个根目录位于 Git 仓库之外，不提交到 Git，也不得把未来正式原始数据上传 GitHub。

## 96 行 manifest 验证

`00_protocol_and_manifests/formal_sample_manifest.csv` 直接从冻结表生成：

- 行数：96/96；
- sequence：001–096 连续且顺序不变；
- unique sample_id：96/96；
- unique condition combinations：96/96；
- configuration：U4SYM/U4ENC；
- direction：0/90/180/270；
- CONT：C01/C02/C03；
- REPOS：RP01/RP02；
- REASM：AS01/AS02；
- session/block/role：逐行保持冻结计划；
- `measurement_mode=rew_sweep`；
- `data_origin=real_experiment` 仅作为未来正式样本的预注册身份；当前没有真实样本文件；
- `dataset_role=development`、`experiment_role=formal_pilot`；
- `eligible_for_scientific_analysis=false`、`final_test=false`。

任何缺行、重复 sample_id、重复/缺失条件组合、sample ID 与字段不一致或 role 改变均 fail closed。

## B01 的 12 个 sample IDs

`B01_ACQUISITION_SHEET.csv` 只包含冻结计划前 12 行，顺序为 0°、90°、180°、270°，每个方向三次 CONT：

1. `F002-SWEEP-U4SYM-D000-AS01-RP01-C01-S01-B01`
2. `F002-SWEEP-U4SYM-D000-AS01-RP01-C02-S01-B01`
3. `F002-SWEEP-U4SYM-D000-AS01-RP01-C03-S01-B01`
4. `F002-SWEEP-U4SYM-D090-AS01-RP01-C01-S01-B01`
5. `F002-SWEEP-U4SYM-D090-AS01-RP01-C02-S01-B01`
6. `F002-SWEEP-U4SYM-D090-AS01-RP01-C03-S01-B01`
7. `F002-SWEEP-U4SYM-D180-AS01-RP01-C01-S01-B01`
8. `F002-SWEEP-U4SYM-D180-AS01-RP01-C02-S01-B01`
9. `F002-SWEEP-U4SYM-D180-AS01-RP01-C03-S01-B01`
10. `F002-SWEEP-U4SYM-D270-AS01-RP01-C01-S01-B01`
11. `F002-SWEEP-U4SYM-D270-AS01-RP01-C02-S01-B01`
12. `F002-SWEEP-U4SYM-D270-AS01-RP01-C03-S01-B01`

所有采集状态、操作者、时间、文件路径、hash、clipping 和 manual-review 列保持空白。

## 模板与预检覆盖

已生成：

- `preflight_checklist.md`
- `geometry_record.csv`
- `environment_log.csv`
- `session_log.csv`
- `deviation_log.csv`
- `backup_verification.json`
- `measurement_metadata_template.json`
- `B01_ACQUISITION_SHEET.csv`
- `ENABLE_EXTERNAL_BACKUP_CHECKLIST_ZH.md`

preflight 清单全部为未勾选 `- [ ]`，覆盖 REW 5.31.3、48 kHz、256k、1 repetition、No timing reference、IR peak、200–8000 Hz、-30 dBFS、Windows 50、iMM-6C 100、增强/AGC/EQ/空间音效关闭、校准加载、旋钮、距离、麦克风深度/高度、0° 基准、开放通道、线缆、房间、低电平静音测试及听力保护。

软件没有自动签名、填写 reviewer/operator 或把空白字段当作 pass。

## 校准状态

在 `D:\Bristol course\dissertation` 树中只读搜索 `CMM29939.txt`，未找到文件。因此：

- `01_calibration/CMM29939.txt` 不存在；
- 未复制或伪造 calibration；
- `calibration_file_missing` 保持 blocker；
- `calibration_load_evidence_missing` 也保持 blocker。

后续必须由用户提供明确来源文件，按字节复制并核对 hash，还须另行记录 REW 实际加载证据。

## 备份门禁与当前决定

用户决定本轮暂不配置外置备份。`backup_verification.json` 明确记录：

- `status=not_configured`
- primary/backup_A/backup_B 路径与物理介质 ID 全部为空；
- copy/restore hash verification 均为 false；
- `external_backup_not_configured` 位于 `unresolved_blockers`；
- `backup_restore_drill_not_completed` 位于 `unresolved_blockers`；
- `ready_for_B01=false`。

后续操作清单位于 `07_hashes/ENABLE_EXTERNAL_BACKUP_CHECKLIST_ZH.md`。只有填写三个位置和物理介质 ID、确认 A/B 独立且至少一个不同物理介质、使用非实验小文件完成双份复制/hash/恢复演练并由人工签署后，才可重新评估备份 gate。GitHub 永远不能用来保存正式原始实验数据。

## 当前 blockers 与 B01 决策

`preflight_status.json` 的准确未解决项为：

- `B01_manual_authorization_missing`
- `backup_restore_drill_not_completed`
- `calibration_file_missing`
- `calibration_load_evidence_missing`
- `environment_record_incomplete`
- `external_backup_not_configured`
- `geometry_record_incomplete`
- `preflight_manual_checks_incomplete`
- `protocol_signatures_missing`

因此 `ready_for_B01=false`。这不是 warning，也不能由 SIM-1、软件测试或文档提交替代人工解决。正式测量不得开始。

## SHA-256 结果

`SHA256SUMS.json` 列出 13 个非循环基线 artifact；实际复核为 13/13 存在且 SHA-256 匹配。关键 hash：

| Artifact | SHA-256 |
|---|---|
| `formal_sample_manifest.csv` | `19cfc986eb19a9edbb6187cb81e86498873c569185043c2c4820447b2ab92c5c` |
| `B01_ACQUISITION_SHEET.csv` | `cb9c97e19c5a0995109da05ad0ffe8e7fd3a526263844d86e9dff57f0504b484` |
| `RESEARCH_PROTOCOL_REV002.md` copy | `35a2158a9af05f4a77d487b2e9262a078fac55716ca3a60ece3ed90bea9cf246` |
| `FORMAL_ACQUISITION_PLAN_REV001.md` copy | `127dafa248e7402dbef0877d8565e571b5b1ff22e0af95db435e4f5f7147475e` |
| `SHA256SUMS.json` | `c2dd0b943f6301046bbf2d2c402182ad8216fa1ed46c7c1a0ab22442df502697` |
| `SHA256SUMS.txt` | `5eaadf3ef8f489fed5004583f89151c3f3e66da68ca3c89aef50f4e60d2b6c22` |

校准文件因缺失不在 hash 清单中。将来加入后必须通过显式新基线流程记录，不能覆盖本次缺失证据。

## TDD 与实际验证

TDD 的代表性 RED 依次包括：缺少 `formal_acquisition` 模块、缺少采集包入口、缺少 backup plan validator、缺少 restore drill 和缺少 package hash verifier。每个公开行为先失败，再做最小实现并重跑。

实际验证：

```powershell
python -m pytest -q tests/test_formal_acquisition.py
```

结果：`8 passed in 0.20s`，退出码 0。

```powershell
python -m pytest -q
```

结果：`878 passed in 223.25s (0:03:43)`，退出码 0。

```powershell
python -m compileall -q src scripts
```

结果：退出码 0，无输出。

实际包生成命令连续运行两次，均退出 0、`artifact_count=13`、`verified=true`、`ready_for_B01=false`，证明在内容未改变时幂等。测试另验证现有 artifact 被篡改时生成器拒绝覆盖，hash verifier 明确失败。

提交前执行 `git diff --check`，准确结果在最终交付回复中记录。

## 修改文件与 Git 边界

代码和测试：

- `src/acoustic_encoder/formal_acquisition.py`
- `scripts/prepare_formal_acquisition_package.py`
- `tests/test_formal_acquisition.py`

文档：

- `docs/progress/FORMAL_2_PREFLIGHT_PACKAGE.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`

外置 `formal_experiment_data` 不在 Git 提交内。没有修改 P1–P9 科研算法、schema、配置、UI、冻结协议/计划或测试数据。单一本地提交建议标题为 `feat(acquisition): add formal preflight package gate`；不 push，不创建 tag/release。

## 数据资格与下一步

本轮没有数据可以取得科研资格。目录清单中的 `real_experiment` 是未来正式采集身份约束，不代表真实样本已存在。备份演练单元测试仅使用 `simulated/software_validation/scientifically_eligible=false` 小文件。

`formal_measurement_started=false`、`final_test_read=false`。下一步不是采集：必须先提供并验证 `CMM29939.txt`、完成几何/环境/REW/安全人工清单与协议签名，配置物理独立的备份 A/B 并完成 restore drill，最后由人工明确批准 B01。所有 blocker 清零之前必须保持 `ready_for_B01=false`。
