# P04T4 — I50P 回程对照确认结果

日期：2026-08-26  
原P04T4终态：`P04T4 RETURN_CONTROL_SUPPORTS_EFFECT_WITH_ASSEMBLY_SENSITIVITY`  
第三批BASE跟踪后的限定：`P04T4F BASELINE_NONSTATIONARY_OR_REASSEMBLY_SENSITIVE_WITH_I50_EFFECT_ROBUST`

## 1. 简要结论

P04T4 支持 I50P 中央腔插入件产生真实、可重复的频谱变化，但 BASE-R 没有完全恢复到 BASE-C，因此不能称为无条件的完全可逆确认。后续第三批BASE-RR显示，不能把该回程差异过早归因于装配：时间、环境/收音状态与重新装配同步改变，基线来源不可分离。

- BASE-R−BASE-C 的 200–4000 Hz 去均值谱形 RMS 为 `1.0887 dB`；
- 本批 all-six 最大组内 pairwise RMS 为 `0.6168 dB`，说明重新装配带来的基线改变明显超过连续重复波动；
- I50P 相对于前后 BASE 点对点平均的去均值谱形 RMS 为 `2.3672 dB`，bootstrap 95% CI 为 `[2.3409, 2.4127] dB`；
- I50P 效应为回程漂移的 `2.174×`，95% CI 为 `[1.997, 2.286]`；完整曲线 bootstrap 中 I50P 效应大于回程漂移的概率为 `1.000`；
- 分别相对 BASE-C 与 BASE-R 得到的 I50P 效应谱形 Pearson/cosine 为 `0.906/0.906`，说明插入件的主要效应在两端基线下保持一致；
- selected-4 与 all-six 给出相同科学分类。

因此，当前最稳妥的论文结论是：**中央共享腔的有效空气体积能够系统性调控真实装置的频谱传递；I50P 的效应大于观测到的基线变化并可跨测量批次复现，但时间、环境/收音状态与重新装配共同形成不可忽略且尚不可分离的基线非平稳性。**

## 2. 数据与 provenance

- 原始 ZIP：`data/real_experiment/P04T4_RETURN_CONTROL_CONFIRMATION/source/仿真P04T4.zip`；
- ZIP SHA-256：`ca0a8c7522e7b8f1f20747ead16144e6acdaccf624f40efe0257709c2459abeb`；
- 18 TXT + 18 MDAT，三组各6次；
- REW 时间顺序严格为 BASE-C → I50P-C → BASE-R；
- 18/18 TXT 的文件身份、256k/1 sweep/−30 dBFS/no timing reference、iMM-6C、Windows 50、mic 100、0.8 m、推断48 kHz和200–8000 Hz覆盖均通过；
- TXT不提供校准文件名、IR peak t=0、clipping或装配照片证据，因此保持 warning，不伪装为已验证；
- 原始文件未修改、未覆盖，逐文件哈希记录在 `metadata/source_manifest.csv`；
- `final_test_read=false`。

## 3. 重复选择与QC

主分析继续使用预先固定的客观4-of-6规则：按完整曲线到本条件all-six中位数在200–4000 Hz的RMS距离排序，选择最近4条；另外2条只flag、不删除。

| 条件 | 主分析 | flag但保留 | all-six最大组内pairwise RMS |
|---|---|---|---:|
| BASEC | 02/03/04/06 | 01/05 | 0.6168 dB |
| I50PC | 02/04/05/06 | 01/03 | 0.5509 dB |
| BASER | 02/03/04/05 | 01/06 | 0.5494 dB |

没有文件被识别为明确技术事故；all-six结果与主分析一致。

## 4. 回程与插入件效应

| 口径 | selected-4 | all-six |
|---|---:|---:|
| BASE回程去均值RMS | 1.0887 dB | 1.0747 dB |
| I50P相对BASE-C去均值RMS | 2.5692 dB | 2.5802 dB |
| I50P相对BASE-R去均值RMS | 2.2801 dB | 2.2830 dB |
| I50P相对bracketed BASE去均值RMS | 2.3672 dB | 2.3761 dB |
| effect/return ratio | 2.174 | 2.211 |
| 前后BASE下效应谱形相似度 | 0.906 | 0.909 |

BASE-R没有回到本批连续重复范围内，说明基线状态变化是真实存在的；但单次前后设计不能把它唯一归因于装配。I50P对前后两个BASE均保持约2.3–2.6 dB效应，并且两条效应曲线高度一致。因此回程差异不能解释全部I50P变化。

SUP-0的`0.8793 dB`来自旧P06/正式实验活动，仅作为历史参照，不作为V2.5/P04通用硬门槛。REV01的回程判定使用本批all-six组内最大pairwise RMS `0.6168 dB`。

## 5. 与P04T2和仿真的连续性

P04T4 I50P谱形与P04T2 I50P谱形在200–4000 Hz的Pearson/cosine均为`0.786`；P04T4/P04T2效应强度为`2.367/2.141 dB`。这支持跨采集批次的同类谱形重现，但仍不是跨日期、多操作者或多台装置的普适重复性。

冻结精确频点仍没有成为可靠条形码：P04T4 selected-4 在1646.88/1986.97 Hz的bracketed raw点效应仅为`+0.245/+0.416 dB`，均未超过`1.396 dB`。1/12-octave窗口则为`−0.966/+0.466 dB`。这延续P04T3的结论：简化COMSOL模型能指示体积控制趋势，却不能精确预测实体的局部频率和幅值。

## 6. 可以与不可以声称的内容

可以支持：

- 中央共享腔不是无关空腔，而是可操作的频谱控制参数；
- 更强的体积干预产生更大的宽频谱形变化；
- I50P效应在前后BASE以及P04T2/P04T4两个批次中保持主要谱形；
- 时间、环境/收音状态与重新装配共同形成的基线非平稳性会改变频谱，工程设计和后续协议都需要定位、密封及交错时间控制。

不能支持：

- 当前COMSOL模型能够精确预测实体峰谷位置和幅值；
- 装置已经实现可靠方向分类；
- 单个模块的独立因果贡献百分比；
- 跨日期、多操作者或量产装置重复性；
- H1已确认或U4HR已被证明优于U4SYM。

## 7. 第三批BASE跟踪限定

新BASE-RR于20:52–20:55重新装配后测量。BASE-C→BASE-RR去均值谱形RMS为`1.0468 dB`，BASE-R→BASE-RR为`0.7308 dB`；BASE-RR没有明确返回任何一个早期BASE。其all-six最大组内差异为`1.4311 dB`，明显高于原批`0.6168 dB`，主要来自R03附近的短时变化。

尽管如此，I50P相对BASE-C/BASE-R/BASE-RR的效应仍为`2.569/2.280/2.413 dB`，三种基线定义的效应谱最低相关仍为`0.906`。因此第三批数据修正了干扰项解释，但不改变中央腔体积效应结论。完整报告见 [P04T4_BASELINE_REASSEMBLY_FOLLOWUP_RESULTS.md](./P04T4_BASELINE_REASSEMBLY_FOLLOWUP_RESULTS.md)。

## 8. 下一步决策

不建议继续增加P04重测、打印件或COMSOL局部调参。P04已经获得足够用于论文的有界机制结果。

原始`P05_U4SYM_NUMERICAL_CONTROL.md`要求P04B先证明模型可用于U4；但P04B为`MODEL_NOT_CREDIBLE_FOR_U4`，P04T3又确认局部频率定位失配。P04T4没有恢复这一模型资格。因此不能直接按旧提示词进入P05。

建议下一步仅执行一次轻量的 **P04T5论文证据综合与P05门禁决策**：整合P04T2–P04T4，冻结论文图表、主张边界和Scheme 3A停止/重建决策；不运行COMSOL、不再实测。完成后结束P04分支，避免无限精细化。

## 9. 产物

权威修订输出：

`outputs/real_experiment/research_analysis/P04T4_RETURN_CONTROL_CONFIRMATION_REV01/`

其中包括QC、重复选择、回程指标、固定窗口、代表谱、跨批次对应、JSON摘要、科学分类、PNG/SVG图和汇总工作簿。

无COMSOL新求解；未读取final-test；未commit、push、tag或release。
