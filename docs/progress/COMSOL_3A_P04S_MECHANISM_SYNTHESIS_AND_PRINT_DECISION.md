# P04S — Scheme 3A 机制综合与最小打印决策

## 终态分类

`P04S COMPLETE — PRINT_ONE_P04E_75PCT_MECHANISM_INSERT`

P04S 仅综合既有实验、报告和机器结果；未调用 COMSOL、未读取或修改 MPH、未生成新几何或 STL，也未读取 final-test。

## 1. Provenance 与阶段边界

P03、P04A、P04B、P04C、P04D、P04D RETRY_01、P04E、P04F 的 `SHA256SUMS` 已分别复核 37、124、94、26、24、14、28、27 项，全部匹配。

- P04D 与 RETRY_01 只登记为 `BLOCKED_BY_SOLVER` 技术失败；没有正式频段结果，不能充当声学否定证据。
- 此前 P04F 连接失败保持为 `P04F PRESTART BLOCKED_BY_MCP`，不是科学分类，也不消耗正式尝试。
- P04F 正式结果保持为 `P04F NO_USEFUL_IMPROVEMENT`。
- P04A 没有可冻结的全局校准参数；P04B-N 不授权完整 U4。

## 2. 当前最强论文结论

单入口 HR 模块的局部频率中心可以通过形态参数控制，但接入共同接收拓扑后，局部模态会与中央腔和固定通道形成混合模态。在 nominal simulation 内，中央腔容积干预能够系统移动该混合分支，而 5–10 mm、在约 1650 Hz 下小于 0.05 波长的短通道延伸不能恢复模块独立性。

因此，本研究能够形成“实验诊断 + nominal simulation 机制解释 + 有边界设计准则”的论文贡献，但不能升级为完整 U4 验证、方向解码成功或单模块因果贡献率识别。

## 3. 实验结果

- HR01–HR08 实测中心保持设计顺序，最大绝对误差约 3.08%。
- 只有 HR03、HR04、HR07 满足当前稳定签名门槛；八个正交频谱条形码不成立。
- U4SYM 与 U4HR 的本 campaign 方向效应分别约 1.049 和 1.697 dB；U4HR 增加约 0.648 dB。
- 预定 U4HR 对角码失败：score −0.239 dB、expected top-1 0/4、top-2 1/4。
- 1623、2198、3974、6493 Hz 仍是探索性频率，不是确认性窗口。

## 4. 实验—仿真连续性

| 频率身份 | Hz | 资格边界 |
|---|---:|---|
| HR03 CAD target | 1850.000 | 设计名义值 |
| HR03 measured S1 centre | 1848.564 | 单 campaign 实测中心 |
| isolated reduced fine | 1890.617 | 局部 reduced/BLI 模型 |
| isolated full-TV fine | 1904.194 | 局部 full-TV 参考；较实测 +3.009% |
| integrated cavity branch | 1650.401 | nominal internal-energy branch |
| P04E 75% | 1684.694 | nominal virtual intervention |
| P04E 50% | 1749.399 | 极端间隙/网格敏感状态 |
| P04F 10 mm | 1652.658 | 有效但无有用改善的干预 |
| existing experimental clue | 1623.273 | post-hoc exploratory microphone feature |
| transfer feature | 1986.972 | microphone/chamber transfer feature，不是 cavity-energy peak |

1623.273 与 1650.401 Hz 相差 27.129 Hz、1.671%、0.02391 octave。二者接近只构成探索性的机制对应，不是独立验证，也不能把 1623 Hz 重命名为 HR03 的因果贡献。simulation internal-energy branch 与 microphone spectral feature 不是同一种 observable。

## 5. P04E 与 P04F 因果对照

| Intervention | Frequency restoration | Chamber participation | Microphone | Engineering sensitivity | Interpretation |
|---|---:|---:|---|---|---|
| P04E 75% chamber | +0.028784 octave | 0.064232→0.094929 | fixed 1646.884 Hz −2.931 dB；1986.972 Hz +3.027 dB | 31,457 elements；5.423 mm clearance | 系统性但部分的 branch motion |
| P04E 50% chamber | +0.083157 octave | 0.064232→0.105034 | 强频率重分布 | 731,519 elements；0.0317 mm clearance | 接近恢复门槛，但工程敏感 |
| P04F 5 mm | −0.000169 octave | 0.064232→0.071767 | tracked peak +0.206 dB | 41,092 elements | 无有用恢复 |
| P04F 10 mm | +0.001085 octave | 0.064232→0.080409 | tracked peak +0.304 dB | 41,621 elements | 短分隔不足以形成阻抗隔离 |

P04E 100→50% 的 octave shift 是 P04F 0→10 mm 的约 76.62 倍。P04F 10 mm 的 chamber participation 增加约 25.18%，Q 从 38.204 降至 35.069（约 −8.21%）。在 1650 Hz、`c=343 m/s` 下，5/10 mm 分别约为 0.0241/0.0481 wavelength。

该对照支持：共同腔容积/声学顺应性是 nominal model 内的重要控制变量；5–10 mm 的短混合距离变化不足以恢复独立性。它不证明所有更强隔离方案无效，也尚未获得插入件物理验证。

## 6. 论文结论资格

13 项候选结论的逐项资格见 `claim_eligibility_matrix.csv`。核心边界为：

- `supported`：单入口局部中心的形态可控性。
- `supported_with_limits`：单 campaign 方向谱变化、HR 阵列在本 campaign 增加总体差异、shared-topology hybridization、中央腔容积控制作用，以及整体论文贡献。
- `exploratory`：1623 Hz 实验线索与约 1650 Hz 模拟分支的机制一致性。
- `not_supported`：八个正交条形码、预定四方向解码、短通道充分隔离、P04E 恢复方向编码、完整 U4 预测和单模块方向因果贡献率。

## 7. 75% 插入件打印门

八项门槛在“后续最小验证概念”层面全部通过：

1. 75% 状态没有 50% 的极端狭缝或网格爆炸。
2. 可在不重打主体、HR03 和麦克风支架的前提下形成 carrier-backed 单一可移除件；具体 CAD 仍需另行授权。
3. 冻结 cross 保留四个 8×9.2 mm 通道和 Ø9 mm microphone well。
4. 已有固定麦克风 observable：1646.8836 与 1986.9725 Hz。
5. 预测幅值变化约 2.93/3.03 dB，高于 HR03 同 campaign local p95 ≈1.396 dB；33.28 Hz branch motion 也超过 1.65 kHz 附近一个 48-PPo bin。
6. 可以在采集前冻结 1646.8836 Hz 为 primary、1986.9725 Hz 为 secondary，不需事后挑峰。
7. 最大范围仅为原 baseline、一个 75% insert、HR03 单入口和一轮配对/交错重复。
8. 该实验只检验中央腔修改能否产生预测频谱变化，不检验方向识别。

因此打印终态是 `PRINT_ONE_P04E_75PCT_MECHANISM_INSERT`。P04S 没有生成 STL、正式采集矩阵或 CAD；这些都必须等待用户另行授权。

## 8. 最终设计准则

未来设计必须控制共同腔的声学顺应性，或提供明显强于 5–10 mm 短几何分隔的阻抗隔离。不能只依赖独立模块调谐或短距离分隔。

## 9. 尚不可识别的内容

- H1 未确认；可靠四方向分类未实现。
- U4HR 不能被表述为普遍优于 U4SYM。
- P04A 不是可信校准；P04B 未验证完整阵列。
- P04E/P04F 没有实测验证。
- 相关性、participation 和方向谱差异都不能识别单模块因果贡献率。

## 10. Scheme 3A 终止边界

当前 Scheme 3A 设计搜索正式结束并等待用户验收。打印决策不需要新 COMSOL 仿真。本轮未开始 P05、P06、U4、外场、STL 或数据采集；未 commit、push、tag 或 release；`final_test_read=false`。

机器结果、论文提纲和全部图形位于：

`outputs/simulation/COMSOL_SCHEME_3A/P04S_MECHANISM_SYNTHESIS/`
