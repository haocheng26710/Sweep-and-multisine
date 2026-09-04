# COMSOL 3A P04D RETRY_01 — PA–TV 耦合作用域修复

## 最终技术状态

`P04D RETRY_01 BLOCKED_BY_SOLVER`

唯一允许的 coupling-scope 修复已经执行。单频 1650 Hz in-memory smoke 在方程装配阶段仍出现与原始 P04D 同类的 `acpr.p_t` 作用域错误，因此按冻结停止规则没有运行正式频段，也不会进行 RETRY_02 或继续修复全热黏性 S1 分支。

没有科学分类：正式 31 点频段未运行，没有 full-TV energy、transfer、phase 或 peak 数据。

## 权威和冻结合同

- 原始 P04D 永久保留为 `P04D BLOCKED_BY_SOLVER`，原目录未修改。
- 原始 P04D `SHA256SUMS` 重新验证为 24/24 匹配。
- P04B-N HR03 authority SHA-256：`33bf573dddc0c0b163e7f0a5e177fc227d16aa541479606e971cb4a3a9398db7`。
- RETRY_01 `repair_contract.json` 在 smoke 前冻结，SHA-256：`2cd45b0a15faa652c301574b50216fbee9ec5e39c10705cb9790ec5cda1fb60f`。
- `final_test_read=false`。

## 修复配置回读

- 唯一 PA–TV coupling：`atb_p04d`。
- COMSOL 类型：`AcousticThermoacousticBoundary`。
- selection：`All boundaries`；COMSOL 实际过滤并回读 10 个 crossing boundaries。
- `Acoustics_physics=acpr`。
- `Thermoacoustics_physics=ta`。
- `StudyStep=std_freq/step1`。
- 不存在重复 PA–TV coupling；不存在第三个声学 physics。
- `std_freq/step1` 回读 `acpr=true`、`ta=true`；activate property 为 `acpr, on, ta, on, ...`。

实际 PA–TV crossing identity 与冻结合同完全一致：

- inner：`262, 263, 264, 265, 279`；
- outer：`257, 259, 260, 261, 284`。

## 唯一 smoke

- 频率：1650 Hz。
- 模型：从未修改 P04B-N authority 全新加载；只存在内存中；未保存。
- 网格：与原 P04D 规定一致，2020 elements，minimum quality 0.01064。
- study run 次数：1。
- 方程装配：失败。

COMSOL 报告：

- `comp1.acpr.p_t` 在 TV domain 45 未定义；
- `mean(comp1.acpr.p_t)` 无法在全部 10 个 crossing boundaries 上计算；
- `comp1.atb_p04d.sigman` 因而无法定义；
- 无 cavity、chamber 或 microphone 数值返回；
- PA/TV 求解自由度门禁无法完成。

这说明将两个局部 coupling 合并为单一 All-boundaries coupling，并显式激活 `acpr` 与 `ta`，仍未消除当前 COMSOL 6.4 工具链中的耦合方程作用域失败。

## 停止边界

- 正式频段运行次数：0。
- 未保存正式 MPH。
- 未生成 `compartment_energy.csv`、`complex_transfer_and_phase.csv` 或 `peak_inventory.csv`，因为这些文件只允许在正式求解成功时生成。
- 未使用 pair coupling、Form Assembly、whole-S1 full TV、第二网格、救援求解或 RETRY_02。
- P04C `TOPOLOGY HYBRIDIZATION SUPPORTED` 保持不变，但本重试未验证或推翻其机理；仍不授权 U4。
- 未开始 P05、P06 或 U4。

本研究接受“全热黏性 S1 增强验证在当前工具链中不可执行”为技术限制，并在此停止等待验收。
