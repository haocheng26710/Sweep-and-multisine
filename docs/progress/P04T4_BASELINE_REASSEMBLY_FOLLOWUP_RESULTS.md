# P04T4F — 第三批BASE重装与时间/环境跟踪结果

日期：2026-08-26  
终态：`P04T4F BASELINE_NONSTATIONARY_OR_REASSEMBLY_SENSITIVE_WITH_I50_EFFECT_ROBUST`

## 1. 简要结论

新测的第三批 `BASE-RR` 没有证明第一次 BASE 回程差异主要来自装配。相反，它显示基线在本时段存在不可忽略的非平稳性，而时间、环境/收音状态与重新装配在现有设计中不能分离。

- BASE-C、BASE-R、BASE-RR 的采集中心时间约为 20:17、20:28、20:54；BASE-RR 比 BASE-R 晚 `25.79 min`；
- BASE-C→BASE-R 与 BASE-C→BASE-RR 的200–4000 Hz去均值谱形RMS分别为 `1.0887` 和 `1.0468 dB`，两者几乎同量级；
- BASE-R→BASE-RR 仍有 `0.7308 dB`，高于原P04T4本地all-six组内上限 `0.6168 dB`；
- BASE-RR 自身all-six最大组内差异达到 `1.4311 dB`；主要来自 R02→R03 的 `1.4311 dB` 突变，R03→R04又改变 `1.2059 dB`，说明这一小段时间内确有短期状态变化；
- 客观4-of-6保留 R01/R04/R05/R06，R02/R03只flag、不删除；即便采用selected-4，BASE-RR组内最大差异仍为 `0.7582 dB`，略高于原批本地上限；
- 因此当前数据只能写为“基线受到时间/环境/重装联合影响”，不能写成“装配是主要原因”或“环境是唯一原因”。

核心机制结论仍稳定：I50P分别相对BASE-C、BASE-R、BASE-RR的去均值谱形效应为 `2.5692/2.2801/2.4131 dB`；三种基线定义所得效应谱形两两最低Pearson/cosine仍为 `0.906/0.906`。完整曲线bootstrap中，最小I50P效应超过P04本地 `1.396 dB` 参考的概率为 `1.000`，最低相关超过0.60的概率也为 `1.000`。

所以第三批BASE削弱了“装配敏感性可以单独解释”的说法，但没有削弱“中央腔体积干预产生大于基线变化、且主要谱形可复现的效应”。

## 2. 数据与provenance

- 新原始ZIP：`data/real_experiment/P04T4_BASELINE_REASSEMBLY_FOLLOWUP/source/仿真P04T4再次.zip`；
- ZIP SHA-256：`cda5a7471c9b866a0df5ac0e2fd2e15d44e676f833d415ca997ba0e7291a72b9`；
- 新增6 TXT + 6 MDAT，原名 `R P04T4_BASERR_R01–R06` 完整保留；
- 与原P04T4的18 TXT + 18 MDAT严格分开存放，联合比较共使用24条真实TXT曲线；
- REW格式、−30 dBFS、no timing reference、iMM-6C、Windows 50、mic 100、0.8 m、推断48 kHz及频率覆盖均通过；
- 原始TXT/MDAT未修改、未覆盖，文件哈希见 `metadata/source_manifest.csv`；
- `final_test_read=false`，新COMSOL求解次数为0。

## 3. 分析规则

沿用P04T4冻结规则：200–8000 Hz、48 PPo对数网格、1/12-octave dB smoothing；200–4000 Hz为主频带，4000–8000 Hz为次要频带。

每组主分析按完整曲线到本组all-six中位谱的200–4000 Hz RMS距离选取最近4次；all-six作为敏感性分析。bootstrap共2000次，以完整重复曲线为单位，不把频率点当作独立样本。

## 4. 三批BASE轨迹

| 比较 | 时间中心差 | selected-4去均值RMS | all-six去均值RMS |
|---|---:|---:|---:|
| BASE-C→BASE-R | 10.98 min | 1.0887 dB | 1.0747 dB |
| BASE-C→BASE-RR | 36.77 min | 1.0468 dB | 1.0274 dB |
| BASE-R→BASE-RR | 25.79 min | 0.7308 dB | 0.7072 dB |

BASE-RR相对BASE-C的距离与第一次回程距离之比为 `0.962`，bootstrap 95% CI `[0.908, 1.053]`；它比BASE-R更接近BASE-C的bootstrap概率只有 `0.696`。这不足以称为明确“恢复”，也不足以称为明确“持续同一偏移”。更准确的描述是：三个时点形成相互接近但超出原连续重复范围的基线状态。

高达约0.98–0.99的三批BASE原始谱相关不能证明它们相同，因为共同的整体传递函数占主导；本报告的判断使用的是去均值差异RMS和完整曲线不确定性。

## 5. I50P对基线选择的稳健性

| 基线参照 | I50P去均值谱形RMS | 相对BASE-C定义效应的Pearson |
|---|---:|---:|
| BASE-C | 2.5692 dB | 1.000 |
| BASE-R | 2.2801 dB | 0.906 |
| BASE-RR | 2.4131 dB | 0.914 |

三个值都高于P04本地 `1.396 dB` 参考，而且效应谱的主要正负结构保持一致。因而不能用某一个BASE批次的偶然位置解释全部I50P效应。

不过，I50P只在20:22–20:24测量，并未在BASE-RR之后再次测量；因此不能声称已经完成跨长时间、跨环境状态的严格交错验证。结论仍是“在三个可用基线参照下稳健”，不是“已完全消除环境影响”。

## 6. 对论文表述的修正

建议采用：

> 中央共享腔有效空气体积的干预效应，在三个不同时点/重装状态的BASE参照下仍保持约2.28–2.57 dB的主频带谱形变化和至少0.906的效应谱相关。基线本身呈现约0.71–1.09 dB的非平稳变化；由于时间、环境与重新装配同步改变，其来源不可唯一识别。

不建议采用：

- “BASE变化已被证明由装配导致”；
- “环境是唯一影响因素”；
- “BASE-RR完成回归，因此完全可逆”；
- “现有COMSOL能精确预测实体局部峰谷”；
- “装置已实现方向识别”。

## 7. 下一步

继续执行既有P04T5，且不再增加P04重测。理由是：第三批BASE没有改变I50P机制结论，只把干扰项从过窄的“装配敏感性”修正为“时间/环境/重装联合的基线非平稳性”。P04T5仍应进行轻量论文证据综合并关闭或重建P05门禁，不运行COMSOL、不继续实体测量。

既有 `P04T5_PUBLICATION_SYNTHESIS_AND_P05_GATE_DECISION.md` 无需更换提示词，因为它会读取已经加入本跟踪结论的P04T4主报告。

## 8. 产物

权威输出目录：

`outputs/real_experiment/research_analysis/P04T4_BASELINE_REASSEMBLY_FOLLOWUP/`

包括新数据QC、重复选择、三批BASE时序与两两比较、I50P三基线敏感性、bootstrap摘要、代表谱、两张PNG/SVG图和SHA-256清单。

