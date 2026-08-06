# DEV-C15 / P9-D — 冻结模型包驱动的离线单次快速读取

## 状态、日期、分支与科研资格

- 状态：完成；代码、测试、实际链路验证和本报告属于同一提交。
- 日期：2026-08-06。
- 分支：`feature/v2-dual-input`。
- Commit 边界：`feat(readout): add frozen offline direction inference`。
- 数据资格：`simulated / software_validation / scientifically_ineligible`。
- 固定门禁：`final_test_read=false`、`scientifically_eligible=false`、`deployment_eligible=false`、`canonical_analysis=false`。

“完成”仅表示离线软件读取切片通过验证，不表示模型已获得部署批准，也不表示形成科研结论。

## 目标与验收标准

P9-D 将已经持久化的 P8 `SpectrumData`、P2 单测量 QC、P7 tone manifest 与一个冻结、哈希绑定的读取包组合为单次方向预测。正式推理入口不得读取 WAV、生成刺激、重跑 P8、训练模型、扫描目录、插值缺失 tone，或把 final-test 用作选择/校准信息。

验收要求包括：独立构建和推理 CLI；冻结方向模型和完整读取包；P8→P3-C→QC→可选 P9-C→预测的唯一数据流；输入、authority、tone、预处理和模型契约 fail closed；不可变成功/失败审计输出；确定性重复；以及实际模拟 P7→S3→P8 输入经持久化后再离线读取。

## 完成范围

- 新增 `FrozenDirectionModel` schema 1.0，保存 nearest-centroid 的训练后 scaler、centroid、方向顺序、特征/tone 契约、训练 membership/hash、P2/P4/P5/P9 authority、final-test seal 和生命周期。CV 临时模型不能转换成推理权威。
- 将 P5 已有 correlation、centroid、logistic 预测数学语义抽到共享底层；P9-D 只允许预注册并冻结的 `nearest_centroid`，避免另建一套评分定义。
- 新增 `FrozenReadoutPackage` schema 1.0，绑定 P7 stimulus manifest 的文件及语义哈希、WAV/tone-set、sample rate、period、stable/discard 周期、P3 快照与 `preprocessing_id`、QC policy、模型文件/语义哈希及全部 authority。
- 新增 persisted-only `run_offline_readout(...)`：验证输入后复用 P3-C multisine tone FeatureSet 构造；不重新 FFT、不平滑 sparse tones、不插值、不以零补缺失 tone。
- 审计 synchronization、clock drift、clipping、P8 aggregate、phase、周期数、required-tone coverage、P2 QC 和人工有效性。`blocked > invalid > unavailable > warning > valid`，所有原因保留。
- phase 为 `relative_unreliable`/`unavailable` 时只产生“phase 未参与 magnitude-only 模型”的 warning；绝不升级为 `common_clock`。
- 可选校准只接受明确的 P9-C `frozen_readout` authority，且必须匹配方向、tone 顺序/频率、单位、quantity/reference、normalization、训练与 final-test seal。现有 outer-fold 临时模型明确拒绝。
- 输出 top-1、top-2、best score、second score 和 margin；nearest-centroid 分数为较小更优的标准化欧氏距离，`margin=second_score-best_score`。这些值只作描述性判别余量，不称为概率或 confidence。
- 新增 package-build CLI、offline-inference CLI 与实际链路 validation CLI。推理 CLI 不包含训练路径。
- 成功包与读取结果均拒绝覆盖，记录所有文件 SHA-256、语义 hash 和 manifest self-hash；失败路径保存 blocked audit，不写虚假成功标记。
- 单测量 `run_manifest` schema 1.15 新增 `P9_D=frozen_readout_package_required` 阶段门。

## 明确非范围

- 不实现 GUI、实时流、声卡采集、WAV 读取或在线 P8。
- 不批准真实实验模型、P9-C calibration 或部署包，不打开 final-test。
- 不做模型/阈值/tone/平滑参数优化，不增加研究问题或 DEV-C16 功能切片。
- 不改变 Measurement schema 2.4 或 FeatureSet schema 2.3。
- 不生成科研结论、置信概率、真实系统延迟声明或部署性能声明。

## 架构与权威边界

```text
package build（显式 training/development FeatureSet + 冻结 authorities）
  -> FrozenDirectionModel
  -> FrozenReadoutPackage + immutable hashes

offline inference（显式 persisted P8 SpectrumData + P2 QC + P7 manifest）
  -> package/input/authority audit
  -> existing P3-C multisine tone FeatureSet builder
  -> optional approved frozen-readout P9-C mapping
  -> shared frozen direction predictor
  -> immutable QC/feature/calibration/prediction/result bundle
```

P8 是 synchronization、drift、clipping、tone quality 和 phase status 的权威；P3-C 是 tone FeatureSet 构造权威；P2 QC 是人工 valid 与单测量 aggregate 的权威；P9-C（若启用）是唯一跨模式校准权威；`FrozenDirectionModel` 是预测参数权威。CSV 仅是 JSON 对象的审计视图。

## 状态与失败语义

- Authority、provenance、hash、stimulus、tone、sample-rate、period、model 或 preprocessing 契约错误：`blocked`，无预测。
- P2/P8 exclude 或人工 `valid=false`：`invalid`，无预测，不篡改原数据。
- required tone 缺失、无足够有效特征或必须 QC 无证据：`unavailable`，无插值/填零/预测。
- magnitude 路径可用但 phase 未获共同采样时钟资格，或上游仅 warning：`warning`，保留预测及全部警告。
- 所有必需检查合格：`valid`。

无论何种状态，输入与检查原因都保存在审计对象；只有 `valid` 或 `warning` 才能产生预测。

## Schema、配置与 API 变化

- Pipeline：`2.0.0-dev.20 -> 2.0.0-dev.21`。
- Config schema：`2.19.0 -> 2.20.0`。
- Run manifest：`1.14.0 -> 1.15.0`。
- Measurement / FeatureSet：保持 `2.4.0 / 2.3.0`。
- 新增 `FrozenDirectionModel`、`FrozenReadoutPackage`、offline readout/result/output manifest schema，均为 `1.0.0`。
- `offline_fast_readout` 默认 disabled，配置固定允许模型、QC 接受状态、required P8 checks、phase 使用策略、缺失 tone 行为、可选 calibration policy、final-test 与 eligibility 约束。
- 2.19 配置只在内存迁移：加入 disabled 的 P9-D block 并发出 warning，不重写原 YAML，也不静默启用。

主要 API：

```text
build_readout_package_from_manifest(...)
execute_offline_readout_from_manifest(...)
run_offline_readout(spectrum, measurement_qc, stimulus_manifest, package, ...)
write_readout_package(...) / load_readout_package(...)
write_offline_readout_outputs(...) / load_offline_readout_bundle(...)
```

## 修改文件

- 模型与推理核心：`direction_models.py`、`classification.py`、`offline_readout.py`。
- 不可变输出与 CLI：`offline_readout_outputs.py`、`offline_readout_cli.py`、`scripts/build_readout_package.py`、`scripts/run_offline_readout.py`。
- 实际验证：`offline_readout_validation.py`、`scripts/run_offline_readout_validation.py`、`config/validation_dev_c15_p9d.yaml`。
- 版本/配置/门禁：`config.py`、`version.py`、`run_execution.py`、`matched_tone_validation.py`、`config/default.yaml`、`config/schema_versions.yaml`。
- 测试：`test_direction_models.py`、`test_offline_readout.py`、`test_offline_readout_outputs.py`、`test_offline_readout_cli.py`、`test_offline_readout_validation_e2e.py`，以及 config/pipeline regression 更新。
- 文档：本报告、进度索引、README、迁移文档和 changelog。

## 数据来源、provenance 与科研资格

验证使用 6 个训练样本（方向 0°/90°/180° × session S01/S02）和一个未参与训练的 90°/S03 单次读取样本。每条链都通过实际 deterministic P7 刺激、S3 模拟录音、P8 同步/transfer/QC 和 P3-C 构造；正式离线推理随后只读取已保存的 P8 `SpectrumData`、P2 QC 和 P7 manifest。

tone set 为 1000、2000、4000、5000、6000 Hz。所有数据固定为 `data_origin=simulated`、`run_purpose=software_validation`、`eligible_for_scientific_analysis=false`。final-test 仅以 unread seal 表示；没有 final-test FeatureSet 被读取。validation 中 P2/P4/P5/P9 authority 是明确的非科研、非部署 snapshot，不能晋升为真实批准。

## 验证命令与准确结果

- `pytest -q tests/test_direction_models.py tests/test_classification.py`：`13 passed in 1.62s`。
- `pytest -q tests/test_direction_models.py tests/test_offline_readout.py tests/test_offline_readout_outputs.py tests/test_offline_readout_cli.py tests/test_offline_readout_validation_e2e.py`：`23 passed in 5.35s`。
- `pytest -q tests/test_config.py -k "dev_c15 or offline_fast_readout or config_219"`：`8 passed, 146 deselected in 0.43s`。
- `pytest -q tests/test_direction_models.py tests/test_offline_readout.py tests/test_offline_readout_outputs.py tests/test_offline_readout_cli.py tests/test_offline_readout_validation_e2e.py tests/test_tone_features.py tests/test_classification.py tests/test_classification_validation.py tests/test_cross_mode_bridge.py tests/test_cross_mode_bridge_outputs.py tests/test_stimulus_multisine.py tests/test_multisine_qc.py tests/test_pipeline_e2e.py`：`122 passed in 28.31s`。
- `python -m pytest -q --disable-warnings`：`673 passed in 83.67s (0:01:23)`。
- `python -m compileall -q src scripts tests`：exit 0，无输出。
- `git diff --check`：exit 0，无输出。
- `$env:PYTHONPATH='src'; python scripts/run_offline_readout_validation.py --project-root . --config config/validation_dev_c15_p9d.yaml --output-root outputs --run-id dev-c15-p9d-validation-20260806-v1`：exit 0；两次离线读取语义结果一致，`deterministic_repeat=true`。
- `$env:PYTHONPATH='src'; python -c "...load_readout_package_bundle(...); load_offline_readout_bundle(...)..."`：exit 0；重新验证 package/model/preprocessing/QC snapshot、全部 artifact、两个 manifest self-hash 和 readout result semantic hash，返回 `completed_with_warnings 90.0 False False False`。
- 首次直接运行同一 validation script 未设置 `PYTHONPATH=src`，因无法导入本地包而失败；该失败不计入完成证据，随后以上述明确环境命令成功执行。

实际读取结果：真实标签 90°，top-1 90°，top-2 0°；best score `0.0011917553936179536`，second score `2.978826000944456`，margin `2.977634245550838`。QC 为 `warning`，处理状态为 `completed_with_warnings`，原因是 magnitude-only 模型明确不使用不可靠相位，而不是伪造共同采样时钟。

关键哈希：

- Frozen model semantic SHA-256：`sha256:b6f0c3cb8d147323d9394316bf69c692afd2b62ca560ad8e592c289a167610f4`。
- Readout package semantic SHA-256：`sha256:188044abc16c2b3f124120e15e1e6943206b0703d6b67d801616fbe65646d6d4`。
- Package manifest content SHA-256：`sha256:f9799e990f110ae6cbd1a9dbf0f3618ff6d48569378e302ce19438a49282bd8c`。
- Readout result SHA-256：`sha256:608d042bca8adf33352045ed56760530114275ce01eefa4d077c70d113031674`。
- Readout manifest content SHA-256：`sha256:0f4611097f099a5bf4c9bad7f86f3b573b82fd6fa9789e93d7118f074474009c`。

TDD 中先观察到缺少共享模型、读取核心、输出层、配置字段以及 calibration tone 顺序门禁等预期 red failure；这些失败不算作成功测试结果。

## 生成物

验证根目录：

`outputs/simulated/software_validation/dev-c15-p9d-validation-20260806-v1/`

冻结包位于 `readout_package/`，包含 `readout_package.json`、`frozen_direction_model.json`、`preprocessing_snapshot.json`、`qc_policy_snapshot.json`、`package_input_manifest.json`、self-hashed `package_manifest.json`。单次结果位于 `offline_readout/`，包含 `input_audit.json`、QC CSV/JSON、feature CSV/JSON、calibration audit、prediction、result 及 self-hashed readout manifest。`offline_readout_repeat/` 是确定性复核输出；`c/` 保留 7 条实际 P7/S3/P8/P3-C 链路证据。

## 已知限制与 provisional 参数

- 仅验证 3 个方向、5 个 tone、6 个训练样本和一个单次读取样本；不是性能估计。
- nearest-centroid 是本切片唯一可冻结模型；分数和 margin 不是概率、置信度或不确定度。
- 没有共同采样时钟时 phase 仍不可靠；当前模型完全不使用 phase。
- 没有真实实验 acquisition、approved calibration、外部复现、实时延迟/资源测试或长期漂移证据。
- validation authority 与阈值都是 provisional software-validation 证据；不得迁移为 real-experiment approval。

## Commit 与最终验收入口

本报告和代码属于一个本地提交 `feat(readout): add frozen offline direction inference`，本步不 push。

DEV-C15 是最终验收前的最后一个功能切片。进入最终验收至少要求：工作树干净；本提交及历史报告可追溯；全量 pytest/compileall 通过；package/result loader 重新验证所有 hash；真实数据仍未被冒用；final-test 仍封存；并由独立验收步骤明确决定是否允许任何 real-experiment、canonical、scientific 或 deployment 状态。DEV-C15 本身不打开这些门禁。
