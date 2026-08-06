# 从模拟验证到真实实验数据的替换指南

## 原则

替换的是输入 artifact 和经批准的真实 authority，不是 provenance 标签。`simulated`、`external_reference` 和 `real_experiment` 必须保持目录、metadata、manifest 与用途硬隔离；禁止复制 mock 的 `eligible_for_scientific_analysis`、QC、calibration、tone-set 或 model 资格字段到真实样本。

## 必须替换的模拟输入

- P7/S3 模拟 recording → 真实采集 WAV 与逐文件 sidecar。
- synthetic dense sweep → 真实 REW frequency-response TXT 与真实 MeasurementMeta。
- simulated device/configuration/direction/session/repeat IDs → acquisition plan 中预注册并在现场记录的真实 ID。
- simulated P2-B scope/expected matrix → 真实实验预期条件矩阵和明确 training/development/final_test role。
- simulated thresholds、P6 calibration、P9 tone selection、P9-C mapping、P9-D package → 仅由真实 training/development 数据重新估计、冻结并人工批准的 authority。

三份 REW official sample 继续只作为 `external_reference/parser_fixture`，不能替换成项目真实测量，也不能进入研究 cohort。

## 保持不变的契约

- `MeasurementMeta`、`SpectrumData`、`FeatureSet` schema 和双入口 adapter 边界。
- P1 的 hash/type/manual-review 门禁，P8 的同步/drift/QC 权威，P2-A/P2-B 的可审计状态机。
- P3 的 preprocessing/tone contract，P4 FeatureSet-only，P5/P9 的 train-only 与 final-test seal。
- 不可覆盖输出、稳定排序、CSV/JSON 同源、artifact/manifest SHA-256 和 loader round-trip。
- `exclude_candidate` 不等于人工删除；`MeasurementMeta.valid` 只能由人工审计变更。

## real_experiment 必填信息

每个真实样本至少需要真实且可追溯的 sample ID、measurement mode、source format、source SHA-256、provenance record、configuration、direction、session、repeat type/index，以及方案要求的 reposition round、assembly、acquisition block。multisine 还必须明确 stimulus ID/hash、tone set、sample rate、period/stable/discard periods 和 audio channel。设备链、校准、操作者、采集时间、软件/驱动、原始文件位置和 role 必须在 acquisition record 中可查。

`data_origin=real_experiment` 不自动意味着科研合格。只有 provenance 完整、人工 valid、P2 gates 和当前研究方案全部通过，且 run purpose 为受批准的 `research_analysis`，才可能进入 canonical 分析。

## 目录与角色隔离

建议物理隔离：

```text
data/real_experiment/calibration/
data/real_experiment/training/
data/real_experiment/development/
data/real_experiment/final_test_sealed/
outputs/real_experiment/software_validation/
outputs/real_experiment/research_analysis/
```

模拟与参考数据继续位于各自根目录。任何 manifest 只能显式列出当前 scope 的文件；禁止扫描目录采用全部文件。final-test 清单和 hash 可由保管流程保存，但内容在冻结前不得供 pipeline 或开发者读取。

## 真实数据重跑顺序

1. P1 导入与 provenance/manual-review；multisine 通过现有 P1 adapter 调用 P8。
2. P2-A 单测量 QC；保留 unavailable、warning、exclude 和人工 valid。
3. P2-B 显式 dataset scope、预期条件完整性、同条件离群和 CONT/REPOS/REASM 稳定性。
4. P3-A/B dense sweep 与 P3-C matched-tone FeatureSets；不得 sparse-to-dense。
5. P4-A/B 描述性/跨模式指标；canonical 分析必须引用精确 P2-B result/hash。
6. P5-A/B 仅用 training/development 做分组分类验证和模型/阈值选择。
7. P6-A/B 用真实 sweep calibration authority 约束 multisine HR readout。
8. P9-A/B/C 用 train-only folds 重新选择 tone、最小 tone 数和可选 cross-mode calibration。
9. 人工冻结真实 tone set、预处理、QC 阈值、calibration 和 readout package；记录 approval。
10. 仅在方案规定点一次性解封 final-test；不再调参，并保留完整审计。

## 禁止事项

- 不把模拟 hash、资格、阈值、设备 ID 或方向标签复制进真实 sidecar。
- 不因文件名看似匹配而静默配对，不用另一重复类型替代缺失重复。
- 不用 final-test 调阈值、标准化、选 tone、拟合 calibration/model 或处理 missing features。
- 不把当前 simulated P9-C calibration 或 P9-D package 称为 approved real artifact。
- 不把 DEV-C16 ready 状态描述为科学、canonical、部署或性能资格。
