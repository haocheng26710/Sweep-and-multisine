# FORMAL-1：正式 Sweep 对数公共网格预处理

状态：完成（实现与软件验证；尚未读取或分析真实实验数据）

日期：2026-08-19

分支：`feature/v2-dual-input`

## 目标与冻结依据

本轮只实现 `RESEARCH_PROTOCOL_REV002.md` 与 `FORMAL_ACQUISITION_PLAN_REV001.md` 已冻结的正式 Sweep 预处理契约：200–8000 Hz、48 points/octave 公共对数网格，200–4000 Hz 主频带，4000–8000 Hz 次要频带，以及公共网格插值后的 dB 域 1/12-octave smoothing。

本轮没有修改研究问题、`G_demeaned` 或其他判定阈值、96 样本矩阵、正式采集顺序、数据资格规则或 final-test 门禁。

## 完成内容

- 新增隔离的 `acoustic_encoder.formal_preprocessing` 模块；既有 P3-A/P3-B 线性 Hz 软件验证路径保持原样。
- `frozen_formal_preprocessing_contract()` 返回唯一允许的 rev-002 契约；正式入口要求调用方显式提交完整契约。
- `build_formal_log_grid()` 严格生成

  ```text
  f_n = 200 * 2**(n/48), f_n <= 8000 Hz
  ```

  共 256 个严格递增 lattice 点。由于 4000 Hz 与 8000 Hz 不是该公式的整数 `n` 点，代码不扭曲 48-PPO lattice，也不人为插点；主/次频带按协议要求的数值闭区间选取。
- `preprocess_formal_sweep()` 只接受 `rew_sweep + dense_spectrum`，执行固定顺序：选择 200–8000 Hz 目标 → 对数频率坐标上线性插值 dB → 连续有效段内 1/12-octave dB 平滑。
- 显式无效点会切断插值。即使文件中直接缺少频率行，相邻有效源点跨距大于 `2/48 octave` 也会形成断层；该固定规则进入算法版本和 manifest，不根据数据结果调节。
- smoothing 的解析范围为 `fc * 2**(-1/24)` 到 `fc * 2**(1/24)`，对落在范围内的公共网格 dB 点等权平均。在完整 48-PPO 内部，一个 1/12-octave 核为 5 点（中心及左右各 2 点）。
- 每个最大连续有效段独立 smoothing。边缘只在本段内 truncate 并重新平均；invalid 值不填零，缺口两侧不互相贡献。
- `write_formal_preprocessing_result()` 以不可覆盖目录写出 `formal_spectrum.npz`、`preprocessing_manifest.json` 和 `artifact_manifest.json`，并记录/复核文件 SHA-256。

## fail-closed 契约

以下字段必须完整存在且精确匹配，未知字段也被拒绝：

| 字段 | 冻结值 |
|---|---|
| `grid_type` | `logarithmic` |
| `points_per_octave` | `48` |
| `frequency_min_hz` | `200.0` |
| `frequency_max_hz` | `8000.0` |
| `primary_band_hz` | `[200.0, 4000.0]` |
| `secondary_band_hz` | `[4000.0, 8000.0]` |
| `smoothing_fraction_octave` | `1/12` |

因此线性网格、错误 PPO、错误上下限、错误主/次频带或错误 smoothing 均抛出 `FormalPreprocessingContractError`；正式入口不会静默替换为默认值。输入模式或 representation 错误也会明确失败。

## manifest 与 hash

每个结果 manifest 固定记录：

- `grid_type`、`points_per_octave`、`frequency_min_hz`、`frequency_max_hz`；
- `primary_band_hz`、`secondary_band_hz`；
- `smoothing_fraction_octave`；
- `preprocessing_algorithm_version=formal_log_grid_v1`；
- 固定处理顺序、插值域/方法/最大断层、有效段数量；
- smoothing 域、权重、边界策略和上下界公式；
- 网格点数、有效点数；
- 对规范化输入内容计算的 `input_sha256`；
- 对输出 frequency/magnitude/valid-mask 计算的 `output_sha256`。

相同输入与契约产生相同数值结果和相同语义 hash。写出层另以 `artifact_manifest.json` 记录 NPZ 与 JSON 文件字节 hash；输出目录已存在时拒绝覆盖。

## API 与修改文件

公开 API：

```python
contract = frozen_formal_preprocessing_contract()
grid = build_formal_log_grid(contract)
result = preprocess_formal_sweep(spectrum_data, contract)
paths = write_formal_preprocessing_result(result, new_output_directory)
```

修改文件：

- `src/acoustic_encoder/formal_preprocessing.py`
- `tests/test_formal_preprocessing.py`
- `docs/progress/FORMAL_1_LOG_GRID_PREPROCESSING.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`

未修改 schema、默认/实验 YAML、P1–P9 既有算法、UI、研究协议、采集计划或任何数据文件。

## 数据来源、科研资格与 final-test

FORMAL-1 专项测试只使用测试代码内新建的 `SpectrumData` synthetic fixtures，明确标记为：

- `data_origin=simulated`
- `dataset_role=software_validation`
- `eligible_for_scientific_analysis=false`

本轮没有读取真实实验数据、diagnostic pilot、现有预实验文件或 final-test。全量回归会继续运行仓库既有的 simulated/external-reference 软件测试，但没有把这些数据提升为科研证据。`final_test_read=false`，本轮不能支持科研结论。

## TDD 与实际验证

先建立网格/契约测试，首次运行准确失败于 `ModuleNotFoundError: acoustic_encoder.formal_preprocessing`；最小网格实现后为 `8 passed`。随后加入预处理公开行为测试，首次准确失败于缺少 `preprocess_formal_sweep`；实现分段插值、平滑、hash 与写出后专项为 `17 passed`。最后新增“带外 0 Hz 行必须在 log 运算前被选出”的回归，先以 `RuntimeWarning: divide by zero` 失败，再修复为显式频带选择；最终专项为 18 项。

最终实际命令与结果：

```powershell
python -m pytest -q tests/test_formal_preprocessing.py
```

结果：`18 passed in 0.16s`，退出码 0。

```powershell
python -m pytest -q tests/test_formal_preprocessing.py tests/test_preprocessing.py tests/test_dense_smoothing.py tests/test_features.py tests/test_feature_outputs.py
```

结果：`64 passed in 0.40s`，退出码 0。

一次直接执行 `pytest -q` 在 collection 阶段因 Windows `pytest.exe` 的 namespace-package 路径解析未找到已存在且受 Git 跟踪的 `scripts/build_acceptance_assets.py` 而退出 1；未修改代码规避。改用本项目文档和既有报告采用的模块入口：

```powershell
python -m pytest -q
```

结果：`870 passed in 224.09s (0:03:44)`，退出码 0。

```powershell
python -m compileall -q src scripts
```

结果：退出码 0，无输出。

提交前另执行 `git diff --check`；准确结果记录在最终交付回复中。

## 已知边界与下一步门槛

- 本轮只交付正式 preprocessing 核心与不可覆盖序列化，不导入任何 formal-pilot 数据，也不宣称 96 样本已采集或 QC 通过。
- `2/48 octave` 缺失行断层规则是 `formal_log_grid_v1` 的固定、可审计软件规则；未来若真实 REW 导出分辨率不满足该前置条件，必须在查看正式结果之前提出有版本的协议/算法偏差处理，不能静默放宽。
- smoothing 使用等权公共网格 dB 平均与段内 truncate；这些语义已进入 manifest，不能在正式运行中由用户调整。
- 旧 P3 软件验证仍使用其原有线性 Hz 配置；它不能被误称为 rev-002 正式路径。
- 正式样本进入下游前仍须经过 provenance、P1、P2-A/P2-B、人工 QC 与 canonical scope 门禁。实现 FORMAL-1 本身不授予 scientific、canonical、freeze 或 deployment 资格。

本报告、实现、测试与索引/README/CHANGELOG 位于同一提交，建议标题为 `feat(preprocessing): add formal log-grid preprocessing`。不 push，不创建 tag/release。
