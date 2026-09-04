# INFO-TOP-1：真实单麦克风分辨基线

日期：2026-08-27  
终态：`INFO_TOP_1_PASS_CONDITIONAL_GO_TO_TOP2`  
研究合同：`INFO-TOP-CONTRACT-v1`  
`final_test_read=false`

## 1. 范围与输入

本阶段只分析两层既有真实单麦克风 REW 曲线。Level A 为 TRANS 单次闭合的 N×6、S×6、NRETURN×3，共 15 条；Level B 为 AS01 的 B01/B02 U4SYM 和 B03/B04 U4ENC，各 block 4 方向×3 CONT，共 48 条 ACTIVE。全部重复均保留，未读取 EXCLUDED，未改变 ACTIVE/EXCLUDED 或既有 flag 身份，未读取 final-test。

本轮没有运行 COMSOL 或 `study.run()`，没有创建虚拟麦克风，没有做参数搜索、新实体实验或监督分类器训练。FORMAL-4 的 grouped classification 仅作为封存背景引用：U4SYM AS01 balanced accuracy 0.375，U4ENC AS01 0.250，均低于既有 0.50 实用目标。

FORMAL-3 权威派生目录在当前 Windows ACL 下不可直接列读；因此使用 FORMAL-3 报告指定的冻结 REV003 ZIP。ZIP SHA-256 `cfbaa7a...f7b4cb` 精确匹配，只打开 B01–B04 的 48 条 ACTIVE TXT。逐条 block/configuration/assembly/direction/repeat 身份由 FORMAL-3 同一解析规则验证；逐成员 hash 被重新计算并记录。FORMAL-3 的 flag 规则也原样确定性复现：全局既有 flag 总数仍引用为 10，其中本阶段 AS01 48 条的交集为 5 条（U4SYM 3、U4ENC 2）。

TOP-0、TRANS、FORMAL-4 和 SUP-0 的全部 SHA 清单均重新验证通过；TRANS 15 条选定 TXT 又与 `source_manifest.csv` 逐条匹配。`input_hash_audit.json/csv` 记录完整证据链。

## 2. 先验冻结分析合同

`top1_analysis_contract.json` 在首次正式结果计算前生成。预处理固定为 FORMAL-1：200–8000 Hz、48 PPo 对数网格、1/12-octave dB smoothing；主频带 200–4000 Hz，次要频带 4000–8000 Hz；不外推无支撑的 200 Hz 端点。dense demeaned spectrum 只用于完整曲线距离、相关和 rank，不把频点当独立样本。

低维表示固定为 SUP-0 的 12 个候选窗口加 TRANS 已冻结的 1538、1850、3800、4170 Hz 四个窗口，共 16 维。重叠窗口按原 ID 全部保留，不根据 TOP-1 结果合并、筛选或排序；由协方差 rank、条件数和 Ledoit–Wolf shrinkage 显式处理相关性。

不确定性固定为 2000 次：Level A 在状态内按完整重复曲线 bootstrap；Level B 以 block 为外层 cluster，并在 block×direction cell 内按完整曲线 bootstrap。Level A 的 N/S 精确置换枚举全部 `C(12,6)=924` 个分配；Level B 在每个配置的两个完整 block 内分别置换四方向标签，共 `(4!)²=576` 个分配。频率点从未作为置换或 bootstrap 单位。

有效秩定义为奇异值能量熵的指数。二状态中心矩阵的理论最大对比维度为 1；四方向为 3。浮点尾差造成的原始数值 rank 另存为审计字段，解释用 rank 不得超过理论上限。

## 3. Level A：TRANS 二状态基线

### 完整曲线可读性

| 频带 | N−S 去均值中心谱距离 | 组内两两距离 median | between/within ratio |
|---|---:|---:|---:|
| 200–4000 Hz | 2.0930 dB | 0.5697 dB | 3.6741 |
| 4000–8000 Hz | 2.6952 dB | 0.7127 dB | 3.7817 |

主频带 ratio 的完整重复 bootstrap 95% CI 为 3.5505–7.9283；精确置换 p=0.00324。该结果重新按 TOP-1 的统一 median-within 合同计算，因此与 TRANS 既有以组内 p95 为分母的 headline 数值不同，不是复制旧结论。

### 固定窗口与协方差

16 个冻结窗口上的 Fisher trace ratio 为 1.7432（bootstrap 95% CI 1.4865–10.7499）；Ledoit–Wolf shrinkage Mahalanobis 为 18.6297（13.3317–42.7142）。原始协方差 rank 10/16、条件数 `1.68×10^18`，不能直接稳定求逆；shrinkage=0.1600 后 rank 16/16、条件数 70.94，状态为 `well_conditioned`。因此报告的是收缩估计下的描述性分离，不是分类性能。

### 回程、漂移与维度

- N−S 主频带谱形 RMS：2.0930 dB；NRETURN−S：2.0711 dB。
- N−NRETURN 漂移：1.1255 dB；效应/漂移比 1.8596，bootstrap 95% CI 1.3014–2.0688。
- N−S 与 NRETURN−S 效应 Pearson/cosine 均为 0.8539；相关 bootstrap 95% CI 0.7600–0.8855。
- 固定窗口中心矩阵有效秩为 1.0000，解释 rank 为 1/1。这个“一条可读取对比轴”是二状态中心化的结构上限，不是发现了一个独立物理通道。

所以 Level A 支持：在这一次闭合、房间、距离和无 timing reference 条件内，单麦克风可读出一个稳定但受漂移限制的 N/S 谱形对比。它不支持跨闭合、跨房间、跨距离、四方向或独立模块因果外推。

## 4. Level B：旧 U4 四状态基线

### 主频带四方向可读性

| 配置 | 组内重复 median | 六对最小/中位距离 | worst-case/median ratio | 精确置换 p |
|---|---:|---:|---:|---:|
| U4SYM | 0.3585 dB | 0.7326 / 0.7989 dB | 2.0437 / 2.2285 | 0.0849 |
| U4ENC | 0.4837 dB | 1.2190 / 1.3654 dB | 2.5199 / 2.8227 | 0.0433 |

Level B block-cluster bootstrap 的 worst-case ratio 95% CI 为 U4SYM 2.0649–5.7282、U4ENC 1.7018–7.7530。2000 次请求中分别有 68、66 次完整曲线重采样使 within median 恰为零；这些未定义 draw 没有被伪造成有限数值，区间分别基于 1932、1934 个有限 draw，并在机器产物中显式登记。

次要频带的 worst-case ratio 为 U4SYM 0.9022、U4ENC 3.8345；U4SYM 的最差方向对未超过组内尺度，说明 4–8 kHz 并非两种配置都稳定可读。

### 固定窗口分离与 rank

| 配置 | Fisher | shrinkage Mahalanobis median / minimum | shrinkage | shrinkage 条件数 |
|---|---:|---:|---:|---:|
| U4SYM | 0.7901 | 7.8009 / 6.5920 | 0.1805 | 34.05 |
| U4ENC | 4.7124 | 16.8944 / 10.8293 | 0.1864 | 28.97 |

两者的原始与 shrinkage 协方差均为 rank 16/16；原始条件数分别为 2604.9、4090.5，收缩后明显改善。block-aware bootstrap 的 Fisher 95% CI 为 U4SYM 0.7407–8.5567、U4ENC 4.4604–57.4700；Mahalanobis 为 8.0594–31.3505 与 17.1202–70.4263。区间很宽，反映只有两个 block，不能作为可靠四方向分类的替代证明。

主频带 dense 方向中心矩阵：U4SYM 奇异值 11.6170/8.0735/5.9386/约0，有效秩 2.6089；U4ENC 为 17.0912/13.7738/10.4668/约0，有效秩 2.7884。固定窗口有效秩分别为 2.6130 和 2.2279。所有解释 rank 均为 3/3；第四个约零奇异值来自四状态中心化的结构约束。有效秩是观测结构的描述，不等于三个独立因果通道。

### block 与 flag 敏感性

5 条 AS01 既有 flag 全部保留在主分析。临时略去 flag 后，主频带 worst-case ratio：U4SYM 2.0437→2.3744，U4ENC 2.5199→2.5199，定性状态未改变。单 block 视图为：U4SYM B01/B02 2.0157/2.5262；U4ENC B03/B04 1.4544/3.0126。各 block 均仍高于 1，但 U4ENC 幅度明显受 block 影响。

这些描述说明四方向中心谱存在超出本批组内重复尺度的结构，U4ENC 点估计通常高于 U4SYM；但只有两个 block，精确置换结果和宽 bootstrap 区间仍限制强结论。尤其 FORMAL-4 的真实 grouped readout 仍只有 0.375/0.250，因此 TOP-1 不确认可靠四方向分类。

U4SYM/U4ENC 的差异不能直接归因为共享腔耦合强弱：装置、模块、状态数和实验上下文仍混杂。本轮最多说结果与 H-COUPLING/H-MATCH 的后续检验方向相容，尚不能裁决因果机制。

## 5. 统一描述性比较

Level A N/S 的 binary/worst-case ratio 为 3.6741、有效对比维度 1；Level B U4SYM/U4ENC 的 worst-case ratio 为 2.0437/2.5199、dense 有效秩为 2.6089/2.7884。这里没有合并数据层级，也没有直接比较未经标准化的绝对 dB。

当前单麦克风观测与二状态任务更匹配：只需读出一个对比维度，且 NRETURN 给出同向回程支持。四状态任务要求在最多三条对比轴上保持跨 block 的几何结构；虽然中心谱与固定窗口显示多维分离，既有 grouped classification 没有达到门槛。二状态天然比四状态容易，因此 TRANS ratio 更高不能证明拓扑隔离是唯一原因。

## 6. TOP-2 门禁建议

终态为 `INFO_TOP_1_PASS_CONDITIONAL_GO_TO_TOP2`。GO 的理由是：输入身份与 hash 可靠；Level A 至少建立了一个有限可解释真实基线，Level B 也建立了受 block/flag 限制的四状态描述基线；完整重复/block-aware 不确定性成立；final-test 仍 sealed。

进入 TOP-2 前最小待冻结问题为：

1. 在禁止 `study.run()` 的代表 MPH 只读预检后，选择路径 A（保存解有限点后处理）或路径 B（真实数据锚定降阶模型）。
2. 预先冻结有限麦克风候选集合，不根据 TOP-2 结果选择坐标。
3. 预先冻结有限噪声/漂移水平和 M=1–4 成本轴。
4. 冻结用于检验边际传感收益的具体状态对比，并保持 Level C 与真实证据分开。

TOP-1 不授权或确定坐标、噪声数值、COMSOL 预算，也没有启动 TOP-2。

## 7. 产物与验证

权威目录：`outputs/info_top/INFO_TOP_1_SINGLE_MIC_BASELINE/`。

主要产物包括冻结合同、输入 hash 审计、Level A/B JSON/CSV、两两距离矩阵、rank/奇异值、uncertainty/sensitivity、统一可读性比较、TOP-2 门禁、summary、PNG/SVG、artifact inventory 和 `SHA256SUMS.txt`。

专项 TDD 首个红灯为新模块不存在；随后按完整曲线距离、有效秩、收缩协方差三个行为逐项实现。专项及相关 FORMAL-1/FORMAL-3/TRANS 回归最终为 `39 passed in 3.68s`。第一次相关回归的 10 个 setup error 来自系统默认 pytest 临时目录 ACL，改用工作区内全新专用 `--basetemp` 后同一测试集全部通过。`python -m compileall -q src scripts`、JSON/CSV 全量解析、数值有限性、最终 SHA 复核和 `git diff --check` 均通过；未运行完整回归。

本报告与 TRANS/FORMAL-4/5 的区别是：它不沿用旧 headline 作为全部结果，而是在统一 INFO-TOP 指标合同下重新计算两层单麦基线、低维分离、有效秩和 group-aware 不确定性，并只把既有分类作为背景负结果。
