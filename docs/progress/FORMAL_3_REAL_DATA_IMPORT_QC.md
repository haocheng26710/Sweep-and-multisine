# FORMAL-3：正式实验精简数据导入、预处理与 QC

状态：完成；可以安全进入下一阶段正式分析，但本轮不具备科学结论资格

日期：2026-08-20

分支：`feature/v2-dual-input`

## 目标与明确非范围

本轮只对人工冻结的正式实验精简 ZIP 执行只读导入、成员/身份核对、逐文件 QC、既有 FORMAL-1 对数网格预处理、重复性描述和 hash 审计。

本轮没有自动改变 ACTIVE/EXCLUDED 决定，没有修改、覆盖或重新打包 ZIP，没有要求重测或增加采集轮次，没有执行分类、方向判定、假设检验、训练或科研结论，也没有读取 final-test。

## 权威输入与命名差异

用户给出的拆分目录路径在磁盘上不存在。只读搜索找到的实际文件是：

```text
D:\Firefly\Desktop\毕业论文相关\球体修改版\正式实验_精简版_REV003.zip
```

其 SHA-256 精确匹配冻结值，因此采用该文件：

```text
cfbaa7a3c300b8443d934462386e9a5faad74d2b2cf0a50292d8c08423f7b4cb
```

文件大小为 `13,454,996 bytes`。运行前后 hash 相同，ZIP 未被修改或重打包。

ZIP 内部根目录仍为：

```text
正式实验_精简版_REV002
```

该差异按人工冻结事实记录为非阻塞 warning：

```text
internal_rev002_name_under_rev003_authority
```

外层 REV003 文件名和冻结 ZIP SHA-256 是来源权威；没有静默重命名内部目录。ZIP 内数据选择记录 SHA-256 为：

```text
7aa30d9d35d6772a2030272222243d31294888714e9135dcc55efd45aa83bcba
```

## 冻结 selection 与身份核对

| ACTIVE group | configuration | assembly | 数量 |
|---|---|---|---:|
| `B01_U4SYM_AS01` | U4SYM | AS01 | 12 |
| `B02_U4SYM_AS01` | U4SYM | AS01 | 12 |
| `B03_U4ENC_AS01` | U4ENC | AS01 | 12 |
| `B04_U4ENC_AS01` | U4ENC | AS01 | 12 |
| `B05_U4ENC_AS02` | U4ENC | AS02 | 12 |
| `B07_U4SYM_AS02` | U4SYM | AS02 | 12 |

核对结果：

- ACTIVE：`72/72`；
- EXCLUDED：`19/19`；
- 每个 ACTIVE block 有 4 个方向，每方向 3 次 CONT；
- 方向集合严格为 `000/090/180/270`；
- ACTIVE sample identity 唯一：72；
- EXCLUDED identity 唯一：19；
- 重复 ZIP member path：0；
- 重复 measurement content SHA-256：0；
- 重复/缺失/无法解析身份：0；
- ACTIVE 与 EXCLUDED identity 交叉：0。

selection 完全来自冻结目录成员关系。没有根据曲线、文件质量或结果重新选择样本。

## 逐文件 QC

ACTIVE 的准确汇总：

| 状态 | 数量 | 原因 |
|---|---:|---|
| pass | 0 | 所有 TXT 都缺少逐文件 calibration filename header，因此不记纯 pass |
| warning | 72 | 仅 `calibration_file_header_unavailable` |
| fail | 0 | 无结构性失败 |

EXCLUDED 的 19 份也完成只读 parse/header 审计，均只有相同 calibration-header warning；其 QC 不会改变排除决定。

72 份 ACTIVE 的共同检查结果：

- REW：`V5.31.3`；
- sweep level：`-30.0 dBFS`；
- timing reference：`none`；
- raw smoothing：`None`；
- 原始点数：每份 `21,300`；
- 原始频率范围：每份 `199.951172–7999.877930 Hz`；
- 数值：finite；
- frequency：严格递增且无重复；
- TXT decoding：GB18030（ASCII REW 字段和中文设备名混合）；
- calibration filename in header：`unavailable`，没有从邻近文件或既有登记中伪造。

8000 Hz 覆盖按离散导出 bin 定义检查：首 bin 必须 `<=200`，末 bin 加最后一个局部步长必须 `>=8000`。实际末 bin 为 7999.877930 Hz、局部步长约 0.366211 Hz，因此满足冻结采集频带；不是放宽分析上限。

结构性 parse、非有限值、频率不递增、覆盖不足、REW 版本、sweep level、timing reference 或 raw smoothing 不匹配都会 fail closed。普通重复曲线 outlier 只增加 flag，不删除数据、不改变人工 selection、不要求重测。

## FORMAL-1 预处理

每个 ACTIVE 文件调用既有 `preprocess_formal_sweep`，契约固定为：

- `grid_type=logarithmic`；
- `points_per_octave=48`；
- `frequency_min_hz=200`；
- `frequency_max_hz=8000`；
- primary band：200–4000 Hz；
- secondary band：4000–8000 Hz；
- smoothing：1/12 octave、dB 域；
- algorithm：`formal_log_grid_v1`。

未提供线性网格或自动替代入口；错误网格、PPO、频带、smoothing 和任何内部 missing/invalid gap 均失败。测试明确证明内部缺口会在最终输出发布前 fail closed。

FORMAL-1 按冻结顺序先选择 `>=200 Hz` 源点。实际首 bin 为 199.951172 Hz，下一个为 200.317383 Hz，因此目标网格的第 0 点 200.0 Hz 保持 invalid；没有外推、填充或改变 FORMAL-1。其余 255/256 点全部有效，72 份一致。只允许首/末端点保留此类边缘 invalid，任何内部 invalid 都是结构性失败。该事实记录在每份 preprocessing manifest 和 run manifest。

生成 72 个 `dense_raw_spl` FeatureSet。这里 `raw` 延续既有定义：经过 1/12-octave smoothing、但未做 sample normalization；不是未平滑原始 TXT。

## 重复性和 outlier flag

输出覆盖 6 block × 4 direction = 24 个同条件 CONT 组，每组 3 个样本、3 个配对。

- 组内 median pairwise primary-band RMS 的最小值：`0.239273684862618 dB`；
- 所有组 maximum pairwise primary-band RMS 的最大值：`1.25685614924595 dB`；
- outlier 方法：曲线到组内点位中位曲线的 RMS，大于 `median + 3 × 1.4826 × MAD` 时 flag；
- warning 组：10/24；
- 被 flag 的曲线：10/72；
- 自动删除：0；
- 自动重测：0。

这些只是进入后续正式分析前的曲线离散度 flag，不是方向效应、假设检验或排除结论。

## EXCLUDED 未进入分析的证据

- `excluded_manifest.csv` 的 19 行均为 `analysis_included=false`；
- ACTIVE manifest 与 FeatureSet index 集合精确相同：72/72；
- EXCLUDED sample ID 出现在 FeatureSet index：0；
- EXCLUDED sample ID 出现在 repeatability summary：0；
- 只生成 72 组 FeatureSet NPZ/JSON 和 72 份 preprocessing manifest；
- run manifest 固定 `automatic_selection_change_allowed=false` 和 `excluded_entered_features_statistics_training_or_results=false`。

## Provenance 与门禁

本轮产物固定记录：

```text
data_origin=real_experiment
dataset_role=research_analysis
run_purpose=research_analysis
scientifically_eligible=false
final_test_read=false
```

为保存冻结的 `dataset_role=research_analysis`，类型化 `DatasetRole` 增加该值；旧的 `research_input` 路径继续兼容。Measurement 字段布局和 version quartet 未改变。既有 research hard gate 仍要求 `eligible_for_scientific_analysis=true`，所以这些 FeatureSet 当前不能进入科学结论或 final-test。

本轮只回答数据能否安全进入下一阶段正式分析，不等于分析已完成，也不授予 canonical、freeze、deployment 或科研结论资格。

## 输出和 hash

权威输出目录：

```text
outputs/formal/FORMAL-3_REAL_IMPORT_QC/
```

主要产物：

- `active_manifest.csv`
- `excluded_manifest.csv`
- `file_qc.csv`
- `group_qc.csv`
- `feature_index.csv`
- `repeatability_summary.csv`
- `run_manifest.json`
- `preprocessed/features/*.npz|*.json`（72 对）
- `preprocessed/manifests/*.json`（72）
- `group_coverage.png`
- `repeat_dispersion.png`
- `artifact_manifest.json`
- `SHA256SUMS`

hash 结果：

- 受管 artifact：`225/225` 验证通过；
- `artifact_manifest.json` SHA-256：`9aa329a730066f4487ac4a77f8700dca40862fec71a46d53817a7dc4d8d9e850`；
- `SHA256SUMS` SHA-256：`0b47e82057cfe59d55e3504487fb195f470025b683fbb6cae5a3e49e9e652af6`；
- `run_manifest.json` SHA-256：`1ecf1179d66f654f1dadd0fc58eba60cdb956f92ca9c74983d7d6fb00c27afe9`。

`artifact_manifest.json` 列出并验证所有业务输出；`SHA256SUMS` 额外登记 artifact manifest 自身。清单文件不能包含自身 hash，属于唯一明确的非循环例外。

在最终 manifest 字段补齐前生成的受控验证输出被保留于 `outputs/formal/_superseded_pre_final/`，没有覆盖或删除；它不是权威结果。

## 测试与验证

TDD 专项：

```powershell
python -m pytest -q tests/test_formal_real_import_qc.py
```

结果：`9 passed`。

相关回归：

```powershell
python -m pytest -q tests/test_formal_real_import_qc.py tests/test_formal_preprocessing.py tests/test_schemas.py tests/test_research_gate.py tests/test_features.py tests/test_feature_outputs.py tests/test_io_rew.py
```

结果：`89 passed in 3.95s`。

全量：

```powershell
python -m pytest -q
```

结果：`892 passed in 296.89s (0:04:56)`，退出码 0。

字节码检查：

```powershell
python -m compileall -q src scripts
```

结果：无输出，退出码 0。

差异检查：

```powershell
git diff --check
```

结果：无输出，退出码 0；文档最终写入后在提交前再次执行。

## 修改文件

- `src/acoustic_encoder/formal_real_import.py`
- `src/acoustic_encoder/schemas.py`
- `scripts/run_formal3_import_qc.py`
- `tests/test_formal_real_import_qc.py`
- `docs/progress/FORMAL_3_REAL_DATA_IMPORT_QC.md`
- `docs/progress/INDEX.md`

原始 ZIP 和 `outputs/` 均不进入 Git。

## 下一阶段结论

```text
ready_for_formal_analysis=true
```

理由：冻结 ZIP/hash/72+19 membership 和六组身份均匹配；72 个 ACTIVE 文件无结构性失败；EXCLUDED 完全隔离；全部 ACTIVE 已通过冻结 FORMAL-1 契约生成 hash-audited FeatureSet；内部 gap 为 0。

非阻塞 warning 是 TXT header 未逐文件列出 calibration filename、已知内部 REV002 名称，以及 10 个只 flag 不删除的重复曲线 outlier。下一阶段必须保留这些 warning 和 valid_mask，不得把 `ready_for_formal_analysis` 解释为科学假设通过或 `scientifically_eligible=true`。
