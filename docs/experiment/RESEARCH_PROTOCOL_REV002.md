# 真实设备正式实验研究协议 rev-002

协议版本：`rev-002`

冻结日期：2026-08-19（Europe/London）

状态：正式 pilot 开始前冻结；这是 rev-001 允许的唯一一次修订

前序协议：[`RESEARCH_QUESTION_AND_DECISION_RULES.md`](./RESEARCH_QUESTION_AND_DECISION_RULES.md) `rev-001`

配套采集计划：[`FORMAL_ACQUISITION_PLAN_REV001.md`](./FORMAL_ACQUISITION_PLAN_REV001.md)

## 1. 修订授权与不可变边界

本文件在有边界压力模拟完成、正式 pilot 尚未开始时建立，使用 rev-001 第 7 节唯一允许的 `rev-002` 窗口。自本文件冻结后，不得根据正式 pilot 结果修改主研究问题、主指标、成功阈值、确认性方向、主频带或重复结构。新增分析必须标记为探索性。

- 修订原因：把 rev-001 的研究问题与判定门槛落实为可执行的真实 Sweep 采集参数、确认性频带、重复结构和文件/停止门禁。
- 修改前：rev-001 已冻结 U4ENC/U4SYM、四方向、`G_demeaned` 和判定门槛，但真实 REW 参数、主分析频带和 96 样本矩阵尚未形成唯一正式计划。
- 修改后：本协议和配套计划冻结这些实施细节；主研究问题、主指标和成功门槛不变。
- 修改依据：项目负责人于 2026-08-19 发出的 FORMAL-0 指令；最终人工签名人须在首次正式采集前填入采集计划审批表。
- 对既有数据的影响：现有所有预实验文件均为 `diagnostic_pilot`，与正式数据不兼容，不得合并、补写身份或重新标记为正式样本。
- final-test：继续 `sealed`；本批正式 pilot 数据不分配为 final-test。

本文件不声称 FORMAL-0 已执行真实测量，也不因 SIM-1 通过而授予任何真实数据科研资格。

## 2. 确认性研究范围

1. 确认性比较固定为 `U4ENC` 对 `U4SYM`。
2. 确认性方向只包括 `0°`、`90°`、`180°`、`270°`。
3. 八方向只能作为独立、明确标记的探索性扩展，不得进入四方向主结果，不得替代缺失的确认性方向，也不得改变主门槛。
4. 单麦克风测量保持不变。
5. Sweep 是正式真实实验的主测量方式。
6. Multisine/P8 暂不进入正式真实数据分析；真实 Multisine 仍需独立批准，不能由本协议、SIM-1 或 UI 软件验证自动开放。
7. 现有及正式批次开始前产生的所有预实验文件必须标为 `diagnostic_pilot`，物理目录、manifest 和分析 scope 均与正式数据隔离。

主研究问题、H0/H1、`CONT`/`REPOS`/`REASM` 语义以及物理指标优先于分类准确率的规则，继续引用 rev-001，不作修改。

## 3. 冻结采集参数

| 项目 | 冻结值 |
|---|---|
| 软件 | REW `V5.31.3` |
| 测量方式 | Sweep |
| sample rate | `48 kHz` |
| sweep length | `256k` |
| repetitions | `1` |
| timing reference | `No timing reference` |
| `t=0` | `IR peak` |
| capture frequency | `200–8000 Hz` |
| sweep level | `-30 dBFS` |
| Windows 输出音量 | `50` |
| iMM-6C 输入音量 | `100` |
| iMM-6C 校准文件 | `CMM29939.txt` |
| Windows DSP | 音频增强、AGC、EQ、空间音效全部关闭 |
| 扬声器—装置中心距离 | 目标约 `0.8 m`；正式采集前实测并记录，不得用“约 0.8 m”替代实测值 |

正式采集前还必须冻结并拍照：扬声器/音箱旋钮位置、开放通道数量、麦克风插入深度、结构高度、房间内扬声器/装置/麦克风基准位置。照片须带拍摄时间、sample-plan ID 和 SHA-256；任何状态改变均触发停止和新偏差记录。

`No timing reference` 意味着不得把 phase 宣称为 common-clock 绝对相位。`t=0=IR peak` 必须保留在每次 REW 项目/导出记录中。

## 4. 冻结分析规则

### 4.1 数据保存、频带和网格

- 每次测量必须保留完整 `200–8000 Hz` 原始 REW 数据和导出 TXT；不得只保存裁剪后的主频带。
- 确认性主分析频带固定为 `200–4000 Hz`。
- `4000–8000 Hz` 只作为次要/敏感性分析，必须明确注明更容易受环境、对准和装置微小变化影响；其结果不得推翻主频带的否定结果。
- 公共对数频率网格固定为每 octave 48 点：

  \[
  f_n = 200 \times 2^{n/48},\quad f_n \le 8000\ \mathrm{Hz}
  \]

  主分析使用该网格落在 `200–4000 Hz` 的点，敏感性分析使用 `4000–8000 Hz` 的点；端点按数值区间包含，不能跨 invalid gap 插值。
- smoothing 固定为 `1/12 octave`、dB 域、公共网格插值之后执行；每个连续有效频段独立处理，不跨无效缺口。

本 FORMAL-0 只冻结规则，不修改软件。当前 P3 dense preprocessing 的既有正式实现使用均匀线性 Hz 网格；因此在 formal-pilot 数据进入确认性分析前，必须单独实现、测试并 hash 绑定上述 48 点/octave 对数网格，或明确停止分析。不得用现有线性网格静默替代，也不得先查看正式频谱结果再选择网格。现有 fractional-octave smoothing 能力也必须与新网格一起重新验证。

### 4.2 主指标和报告义务

主指标仍为 rev-001 的：

\[
G_{\mathrm{demeaned}} =
\frac{\operatorname{median}(d_{\mathrm{between\ direction}})}
{\operatorname{median}(d_{\mathrm{within\ direction,\ REPOS}})}
\]

以下门槛不变，也不得因预实验或正式结果放宽：

- `G_demeaned(U4ENC) > 1`；
- `G_demeaned(U4ENC) > G_demeaned(U4SYM)`；
- `ΔG_demeaned > 0`；
- demean 和 z-score 后方向差异仍存在；
- U4ENC 方向间差异大于 REASM 同方向变化；
- 四方向 grouped balanced accuracy 实用目标至少 `50%`，机会水平 `25%`。

必须同时报告 `G_raw`、`G_demeaned`、`G_zscore`、CONT/REPOS/REASM 分层结果、U4ENC–U4SYM 差值、95% CI、grouped balanced accuracy 和 macro-F1。95% CI 和 grouped validation 必须把同一物理状态的三次 CONT 作为技术重复整体保留，不能把 CONT 当作独立科学样本或跨训练/验证边界随机拆分。

### 4.3 工程解释规则

诊断预实验观察到的约 `0.8 dB` 工程扰动界限只用于解释、故障定位和测量稳定性诊断，不替代任何正式研究成功门槛：

- 单个效果 `<1.0 dB`：不能与当前工程扰动可靠区分；
- `1.0–1.5 dB`：暂定工程证据；
- `>1.5 dB` 且跨 CONT、REPOS、REASM 稳定：较强工程证据。

上述分档是辅助描述，不是新的主终点，不得用它绕过 `G_demeaned`、结构差值、REASM、95% CI 或 QC 门槛。

## 5. 冻结正式采集设计

- configurations：`U4SYM`、`U4ENC`
- directions：`0°`、`90°`、`180°`、`270°`
- 每个固定物理状态：三次连续 `CONT`
- 每个 configuration、每个 assembly：两轮独立 `REPOS`
- 每个 configuration：两个独立 `REASM` assembly states
- 最小样本数：`2 × 4 × 3 × 2 × 2 = 96` 个 Sweep

96 个样本的逐行身份、session、block、role 和采集顺序由配套采集计划预注册。任何额外复测必须保留原失败文件、使用新 sample ID、注明偏差原因，且不能替代或删除原计划行。

本批身份固定为：

- `data_origin=real_experiment` 仅在真实采集和 provenance 完整时填写；
- schema dataset role：`development`；
- protocol experiment role：`formal_pilot`；
- `eligible_for_scientific_analysis=false`，直到 import、hash、metadata、QC、P2-B 和人工资格门禁全部通过；
- 绝不标为 `final_test`。

## 6. 数据完整性、停止条件与偏差

出现任一条件立即停止当前 block，不继续采集，也不在现场改变阈值或参数：

1. 数字削波或 REW 报告 `input clipping`；
2. 输入/输出设备、Windows 音量、iMM-6C 输入音量或增强设置发生变化；
3. 麦克风、扬声器、装置或房间基准位置意外移动；
4. 环境出现持续异常噪声；
5. `CMM29939.txt` 缺失、失效、hash 不符或未实际加载；
6. metadata、原始文件、导出 TXT、照片、环境记录、hash 或任一备份缺失；
7. REW 版本、sample rate、sweep length、frequency、level、timing reference、t=0 或 repetitions 与冻结值不一致。

停止后必须隔离受影响文件，记录时间、已完成 sample IDs、原因、设备状态和处置人。只有重新核对全部门禁并获得人工批准后才能以新 block/resume record 继续。不得覆盖、重命名或静默重做失败样本。

## 7. rev-001 到 rev-002 的逐项变更

| 项目 | rev-001 | rev-002 |
|---|---|---|
| 主问题/H0/H1 | 已冻结 | 不变 |
| 确认性方向 | 四正交方向；八方向探索性 | 不变，并明确八方向不能替代主结果 |
| 正式真实测量模式 | Sweep 主要、Multisine 待批准 | Sweep 唯一正式主测量；真实 Multisine/P8 暂不进入 |
| REW 参数 | 未具体冻结 | 按第 3 节完整冻结 |
| 原始频率范围 | 未具体冻结 | 200–8000 Hz 全量保存 |
| 主/次分析频带 | 待正式 pilot 前确定 | 主 200–4000 Hz；次 4000–8000 Hz |
| 公共网格/smoothing | 未具体冻结 | 48 点/octave 对数网格；1/12 octave smoothing |
| 主指标/成功阈值 | `G_demeaned` 及全部门槛 | 完全不变 |
| 工程扰动解释 | 未列明 | 0.8 dB 仅诊断；增加 <1.0/1.0–1.5/>1.5 dB 辅助分档 |
| 最小正式设计 | 未逐行冻结 | 96 Sweep，完整预注册矩阵 |
| 既有预实验 | 非正式研究证据 | 全部 diagnostic_pilot，禁止并入 |
| final-test | sealed | sealed；本批全部 development/formal_pilot |

## 8. 正式 pilot 后的变更控制

本 rev-002 是唯一允许的修订。首次正式样本开始采集后：

- 不得发布 rev-003 来改善结果；
- 不得改变主问题、主频带、主指标、阈值、方向、结构或样本量公式；
- 偏差只能作为 deviation/incident 追加记录，不能改写已冻结文本；
- 探索性八方向、高频结果、Multisine 或新分类器必须独立标记，不能回填确认性 scope；
- final-test 保持 sealed，除非未来另有独立、预先批准的解封程序。

## 9. 人工冻结签署

- 协议负责人：`<首次正式采集前填写并签名>`
- 采集负责人：`<首次正式采集前填写并签名>`
- 安全审核人：`<首次正式采集前填写并签名>`
- 数据保管人：`<首次正式采集前填写并签名>`
- 冻结确认时间：`<首次正式采集前填写>`
- 首个正式 sample 开始时间：`<采集时填写；在此之前必须为空>`

任一必签项为空时，协议文档虽已版本冻结，但不得开始正式采集。
