# DEV-UI4-FIX6：模拟练习步骤04～07端到端工作流

状态：实现及提交前验证完成；等待从本步 clean commit 构建 Windows one-folder

日期：2026-08-13

分支：`feature/v2-dual-input`

科研资格：`data_origin=simulated`、`dataset_role=software_validation`、`run_purpose=software_validation`、`scientifically_eligible=false`。本步不读取 final-test，不开放真实 Multisine/P8，不形成科研结论。

## 目标与验收范围

本步一次性补齐模拟练习路线的步骤04～07：从步骤03的不可变计划 revision 生成 P7 刺激，按显式 expected sample matrix 生成 32 个 S3 模拟录音，通过后台 worker 逐样本调用现有 P1/P8/P2-A pipeline 并保存 UI session，最后自动登记并审计 32/32 数据集完整性。实现不得扫描 outputs、不得从文件名猜身份、不得复制 P7/P8 算法、不得把 sparse tones 冒充 dense FeatureSet。

验收计划固定覆盖两个 configuration（U4SYM/U4ENC）、四个角度（0/90/180/270°）以及独立的 CONT、REPOS、REASM；总数为 32。步骤03 revision 只读，所有后续引用由路径和 SHA-256 绑定。

## 完成内容

### 步骤04：计划绑定刺激

- 新增正式 `StimulusPage`，替代通用 placeholder。
- 可从步骤03保存事件接收计划，也可由用户显式选择已有 revision；后者用于升级新版 EXE 后继续旧工作区，不扫描 plan/output 目录。
- 使用现有 `load_config` 和 `stimulus_multisine.generate_multisine`，固定读取 `config/stimulus_multisine_broadband.yaml`。
- 计划中的 `stimulus_id`、`tone_set_id`、`sample_rate_hz` 与 P7 resolved config/manifest 必须完全一致，否则 fail closed。
- 生成/复核 `stimulus.wav`、`stimulus_manifest.json`、`tones.csv`、P7 preview/hash 及 `artifact_hashes.json`。
- 输出目录存在时不覆盖；只有完整 hash 复核通过的同一不可变刺激才可复用。

### 步骤05：显式 32 样本模拟采集

- 新增正式 `AcquisitionPage`。模拟路线无需外部设备；官方参考路线禁止生成伪造录音；真实路线仅显示外部采集说明和既有 P8 硬阻塞。
- 新增公开 S3 边界 `simulate_multisine_recording_waveform`，UI 编排复用 `mock_data` 中的已知 H(f) 和模拟算法。
- 严格遍历 plan revision 的 expected samples，不扫描目录、不解析超长文件名。
- 每个样本写出可读 float WAV、sidecar、known-transfer CSV；批次写出 `acquisition_manifest.json` 及 SHA-256。
- sidecar 身份逐字段来自 expected sample：configuration、angle、session、repeat type/ID、reposition round、assembly、acquisition block、stimulus/tone set/sample rate/audio channel。
- 默认随机种子 `20260813`，每个样本按稳定排序派生种子；默认前置非周期延迟 1379 samples，继续覆盖 P8 同步路径。
- 相同计划/种子只复核已有不可变批次；不覆盖不完整或不一致目录。

### 步骤06：后台批量预检、处理与登记

- 新增 `SimulatedBatchPage` 和 `SimulatedBatchWorker`。QProcess 的程序与参数分开传入，源代码版和 frozen 版使用同一 worker entry。
- 输入只能是步骤05显式 acquisition manifest。进入处理前复核 plan、stimulus、manifest、WAV、sidecar、truth 文件及身份/hash。
- 每样本调用现有 `MeasurementDraftService.preflight_multisine`、UI session save、`execute_measurement_run`；P1/P8/P2-A 不在 UI 重算。
- 生成 32 个 `outputs/ui_sessions/<sample_id>/rev-001` 与各自 pipeline output；保存 run evidence、run manifest、QC、P8 CSV/图、`spectrum_data.json/.npz`。
- sparse Multisine 明确记录 `feature_set_status=not_applicable_sparse`，不生成 `processed/` dense FeatureSet。
- 页面显示当前样本、总进度、warning/失败数；合作式取消使用显式 cancel 文件，worker 在样本边界停止并写 `status=cancelled` 的 processing manifest，不伪造 passed。
- 每次 GUI 执行生成唯一 processing ID；已有输出目录拒绝覆盖。

### 步骤07：数据集完整性与正确路线

- `DatasetQCPage` 可一次加载 processing manifest，自动登记 32 个 UI sessions；不再要求用户手工登记 32 次。
- 使用既有 `SampleRegistry` 验证 expected/observed 身份、重复、缺失、意外样本、source/output hash、QC、SpectrumData 与 FeatureSet 状态。
- clean 路径显示 `32/32 expected_and_present`。
- 纯 sparse Multisine 计划明确显示 `P2-B=not_applicable_sparse`，禁用 DENSE_RAW_SPL P2-B 按钮并路由到 `tone_p8_dataset_quality`；这不是伪造 P2-B pass。
- measurement 级 warning 保留为 warning；exclude candidate/处理失败不能提升为 passed。

### 状态恢复与路线安全

- `outputs/ui_simulated_flow/workflow_state.json` 及 SHA-256 是步骤01～07唯一状态指针；启动时只读取该 manifest 明确列出的 plan/stimulus/acquisition/processing/dataset artifacts。
- 不递归扫描 outputs，不认领未登记结果；任何状态或 artifact hash 不匹配都会阻止恢复并给出说明。
- 步骤01/02 presentation 状态、步骤03 revision、04～07 artifact 指针均可恢复；步骤03 revision 不被修改。
- official reference 仍仅允许官方 REW 文件选择和 software validation；不生成录音。
- real experiment 仍使用外部采集/登记路径；真实 Multisine/P8 门禁没有绕过入口。
- `final_test_read=false` 始终写入 FIX6 manifests，final-test 保持 sealed。

## 数据流与权威边界

`plan revision → P7 stimulus → explicit S3 acquisition manifest → background P1/P8/P2-A per sample → UI session registrations → sparse dataset integrity audit`

计划是身份矩阵权威；P7 manifest 是刺激权威；P8/`SpectrumData.quality_metrics` 是同步、drift、tone QC 与 phase status 权威；UI manifests 只编排、引用和审计，不建立第二套科研状态。P2-B 仍是 FeatureSet cohort QC，因而不会被强用于 sparse-only 计划。

## 新增/修改文件

- `src/acoustic_encoder/ui/simulated_flow.py`
- `src/acoustic_encoder/ui/simulated_flow_pages.py`
- `src/acoustic_encoder/ui/main_window.py`
- `src/acoustic_encoder/ui/dataset_page.py`
- `src/acoustic_encoder/ui/workers.py`
- `src/acoustic_encoder/ui/worker_entry.py`
- `src/acoustic_encoder/mock_data.py`
- `src/acoustic_encoder/run_execution.py`
- `scripts/run_gui.py`
- `tests/test_ui4_fix6_simulated_flow.py`
- `docs/progress/DEV-UI4_FIX6_SIMULATED_FLOW_04_07.md`
- `docs/progress/INDEX.md`

## schema、API 与 artifact 变化

科研 schema 和 P1～P9 schema/version 未修改。新增 UI orchestration schema `simulated_flow_schema_version=1.0.0`，用于以下非科研资格 manifests：

- `workflow_state.json`：显式状态和 artifact 指针；
- `artifact_hashes.json`：步骤04计划绑定与刺激 artifacts；
- `acquisition_manifest.json`：步骤05 expected identity、输入路径和 hashes；
- `processing_manifest.json`：步骤06 UI sessions、pipeline outputs、QC/representation 状态；
- `dataset_flow_manifest.json`：步骤07 32/32、QC rollup、P2-B applicability 和 downstream route。

新增 public S3 helper 与 UI application-service/page/worker 边界。`run_execution._git_state` 增加 frozen runtime 的 build manifest fallback；它只读取 clean-build provenance，不放宽 dirty/research gate。

## TDD 与实际验证

RED 证据依次包括：缺少 `simulated_flow` 模块；缺少步骤05 batch API；缺少步骤06 process API；缺少步骤07 dataset audit API；frozen/source worker 首次运行因 `workspace_root` 被提前释放而结构化失败。每个失败都先由测试复现，再进行最小实现并回归。

实际执行结果：

- `python -m pytest -q --disable-warnings tests/test_ui4_fix6_simulated_flow.py`：`11 passed in 77.76s (0:01:17)`。
- FIX6 中步骤04/05核心首次 green：`2 passed in 2.20s`。
- FIX6 中步骤06核心：`2 passed, 2 deselected in 22.14s`。
- FIX6 中步骤07核心：`2 passed, 4 deselected in 37.27s`。
- Qt 后台 32 样本步骤03→07 E2E：`1 passed, 7 deselected in 20.63s`。
- Qt E2E + cooperative cancellation：`2 passed, 7 deselected in 22.22s`。
- 代表性 UI 回归：首次发现旧 UI2 页面断言冲突，调整为“无步骤05批次时保留旧单样本页、有批次时进入 FIX6 批量页”后，相关复核 `2 passed, 13 deselected in 2.06s`。
- 全量 `python -m pytest -q --disable-warnings`：`832 passed in 199.64s (0:03:19)`。
- `python -m compileall -q src scripts`：exit 0，无输出。
- `git diff --check`：exit 0，无 whitespace error。

以上均为实际执行结果。文档加入后仍需在提交前执行最终 compileall/diff check；Windows clean-build、dist smoke 与 packaged acceptance 只能在本报告所在 commit 创建且工作树 clean 后执行，不能在报告中预先声称。

## 生成输出

工作区内的 FIX6 输出根目录为：

- `outputs/ui_simulated_flow/workflow_state.json`
- `outputs/ui_simulated_flow/stimuli/<stimulus_id>/`
- `outputs/ui_simulated_flow/acquisitions/<batch_id>/`
- `outputs/ui_simulated_flow/processing/<processing_id>/`
- `outputs/ui_simulated_flow/dataset_audits/<audit_id>/`
- `outputs/ui_sessions/<sample_id>/rev-001/`
- `outputs/ui_pipeline_runs/simulated/software_validation/<run_id>/`

所有原始 stimulus/WAV/sidecar/manifest 只读引用；验证 artifacts 含 SHA-256。测试输出位于 pytest 临时目录，不作为科研数据或正式交付数据。

## 已知限制与明确非范围

- 本步只完成 simulated/software-validation 练习路线，不冻结真实采集阈值。
- 真实 Multisine/P8 仍 blocked；真实设备播放、录音和 calibration 不在本步实现。
- official reference 不产生 synthetic WAV。
- sparse-only dataset 不运行 FeatureSet-only P2-B/P4/P5；其后续 tone/P8 数据集分析仍须遵守已有冻结/scope 门禁。
- 取消在“样本边界”生效，不中断一个正在执行的 P8 FFT 写出；这避免半写单样本被标为成功。
- 不修改 P1～P9 数学、QC 阈值、provenance/research gate、scientific eligibility 或 final-test 定义。

## Git commit 与 clean-build 门槛

本报告与实现置于同一提交，建议标题：`feat(ui): complete simulated workflow steps 04 to 07`。正式 one-folder 必须从该 clean commit 构建；构建后需核对 `source_git_dirty=false`、`software_integration_ready=true`、`final_test_read=false`，并报告 EXE 路径/SHA-256。不得 push、创建 tag 或 release。

