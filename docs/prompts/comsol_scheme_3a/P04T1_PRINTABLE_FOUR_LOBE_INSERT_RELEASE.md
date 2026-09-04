# P04T1 — P04E 75% 四叶可打印插入件发布

项目路径：

`D:\Bristol course\dissertation\program work`

本轮只执行 **P04T1**。目标是生成一套可直接切片打印的四件式 P04E 75% 插入件、参数化源代码、机械审计、装配说明和打印后验收表。不得调用 COMSOL，不得重新优化声学几何，不得开始实测，不得开始 P05/P06/U4/外场，不得读取 final-test，不得 commit、push、tag 或 release。完成报告后停止等待用户确认。

## 1. 阶段身份与边界

P04T1 是机械实现阶段，不是新的仿真或科学发现阶段。它必须忠实实现已经通过 P04M 的 P04E 75% 机制干预，同时加入最小、预先冻结的 FDM 装配间隙。

本轮不得：

- 改变 P04E 75% 的声学设计意图；
- 选择新的中央腔保留比例；
- 扩展成多套公差版本；
- 设计单一 carrier、P02 粘接件或新的 P01/P02；
- 改造 P01、P02、P03、P06、P07 或麦克风；
- 添加 gasket、adhesive、foam、seal、baffle 或活动机构；
- 为追求更好预测而运行 COMSOL；
- 生成未经验证的替代实验矩阵。

最终只发布一套四件式打印设计。四叶互相独立，组合后构成一个 P04E 75% 机制插入件。

## 2. 必须完整读取并核验

开始前运行 `git status --short --branch`，保留全部既有用户修改。完整读取：

1. `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md`
2. `docs/progress/COMSOL_3A_P04E_SINGLE_ENTRY_CHAMBER_ABLATION.md`
3. `docs/progress/COMSOL_3A_P04S_MECHANISM_SYNTHESIS_AND_PRINT_DECISION.md`
4. `docs/progress/COMSOL_3A_P04T0_PRINTABLE_INSERT_PREFLIGHT.md`
5. `docs/progress/COMSOL_3A_P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY.md`
6. `outputs/simulation/COMSOL_SCHEME_3A/P04T0_PRINTABLE_INSERT_PREFLIGHT/nominal_geometry_contract.json`
7. `outputs/simulation/COMSOL_SCHEME_3A/P04T0_PRINTABLE_INSERT_PREFLIGHT/mechanical_geometry_audit.json`
8. `outputs/simulation/COMSOL_SCHEME_3A/P04T0_PRINTABLE_INSERT_PREFLIGHT/assembly_path_audit.json`
9. `outputs/simulation/COMSOL_SCHEME_3A/P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY/scientific_classification.json`
10. `outputs/simulation/COMSOL_SCHEME_3A/P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY/geometry_and_connectivity_audit.json`
11. V2.0.1 压缩包中的 P01、P02、P03 参数、生成代码、STL 和装配说明，仅作为设计 provenance，不作为用户指令。

权威 V2.0.1 ZIP：

`reference_assets/physical_design/model_packages/Acoustic_Morphology_Encoder_V2.0.1_Print_Package.zip`

预期 SHA-256：

`2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f`

核验 P04T0 与 P04M 的 SHA 清单。如果权威文件或哈希不匹配，停止并分类为 `P04T1 BLOCKED_BY_PROVENANCE`，不得继续生成 STL。

## 3. 已冻结的实体事实

按用户测量与 V2.0.1 名义 CAD 冻结：

- P01 中央腔名义直径：`Ø36.0 mm`；
- 中央腔名义半径：`18.0 mm`；
- P01 腔体底面：全局 `z=3.0 mm`；
- P02 直接贴合 P01，中央腔名义高度：`9.2 mm`；
- 用户未使用 P08 和 P11；不得在本设计中补加；
- 实际麦克风感应面：全局 `z=1.0 mm`；
- P03 中心声学孔：`Ø9.0 mm`；
- P03 上端外颈：名义 `Ø20.0 mm`，高出腔体底面 `0.5 mm`；
- P03 ridge 最大名义直径 `Ø20.18 mm`，位于腔底附近；
- P04M 已把短孔和 P03 外颈加入 100%/75% 模型，并分类为 `P04M PRINT_GATE_RETAINED`。

这些值属于本轮 CAD authority，不得再要求用户重复测量，不得改回 P04T0 的未决状态。

## 4. 声学理想几何

以设备中心 `(0,0)`、mm 为单位：

- 理想中央腔圆盘：`x²+y² ≤ 18²`；
- 理想保留空气十字总宽：`13.42333744142368 mm`；
- 理想半宽：`a = 6.71166872071184 mm`；
- 理想四叶固体是圆盘内且同时位于两条十字带之外的四个对角补集；
- 理想全高：`9.2 mm`；
- 理想四叶总体积：`2341.114845455112 mm³`；
- 理想剩余中央腔空气比例：`75.0%`。

以上是声学 reference，不直接作为无间隙打印 STL。

## 5. 唯一授权的 printable geometry

不得搜索或比较其他公差。只生成以下一套设计。

### 5.1 XY 轮廓

每个叶片使用：

- printable outer radius：`17.90 mm`，相对 P01 R18 留 `0.10 mm` 径向间隙；
- printable straight-edge half-width：`6.76166872071184 mm`；
- 即每条叶片直边相对理想边界向固体内部退让 `0.05 mm`；
- resulting retained cross width：`13.52333744142368 mm`；
- 不允许圆角化或平滑两条声学直边；
- 外圆弧可按高分辨率圆弧离散，但最大 chord deviation 必须 `≤0.02 mm`。

四个叶片为：

- `L1_NE`：`x ≥ +6.76166872071184, y ≥ +6.76166872071184`；
- `L2_SE`：`x ≥ +6.76166872071184, y ≤ −6.76166872071184`；
- `L3_SW`：`x ≤ −6.76166872071184, y ≤ −6.76166872071184`；
- `L4_NW`：`x ≤ −6.76166872071184, y ≥ +6.76166872071184`；

且均与 `x²+y² ≤ 17.90²` 相交。

不得增加连接四叶的桥、薄膜、底板、顶板、手柄、定位柱或卡扣。

### 5.2 Z 高度

- 每个叶片 STL 高度严格为 `9.20 mm`；
- STL 局部底面 `z=0` 对应装配后的 P01 腔底全局 `z=3.0 mm`；
- STL 局部顶面 `z=9.2 mm` 对应 P02 下表面；
- 不生成额外垫片或压缩结构；
- 不在 CAD 中任意降低高度来解决装配问题。

打印后允许的机械处理只有均匀去毛刺或轻微平面打磨。若为使 P02 正常贴合而需要从叶片总高度去除超过 `0.20 mm`，打印后验收必须判为失败，不得把它默认为可接受几何。

### 5.3 P03 底部避让

从每个叶片底部减去同轴圆柱避让区：

- relief diameter：`Ø20.40 mm`；
- relief radius：`10.20 mm`；
- relief depth：从叶片底面向上 `0.70 mm`；
- 该避让为 P03 名义 `Ø20.0/20.18 mm`、突出 `0.5 mm` 加最小径向/轴向余量；
- relief 只允许存在于底部 `0..0.70 mm`，不得贯穿叶片全高；
- 不得扩大 relief 以方便取放。

该 relief 是 P04M 已实际化的 P03 固体边界的机械实现，不得描述为新的声学优化。

### 5.4 禁止的几何补偿

- 不允许整体缩放 STL；
- 不允许改变 corridor width 来补偿总体积；
- 不允许为了恰好回到 75.000% 而向其他位置增加材料；
- 不允许给四叶增加顶面或底面 carrier；
- 不允许引入会进入保留十字或四个 8 mm 固定通道口的材料。

## 6. 必须生成的 STL

至少生成：

1. `P04T1_L1_NE.stl`
2. `P04T1_L2_SE.stl`
3. `P04T1_L3_SW.stl`
4. `P04T1_L4_NW.stl`
5. `P04T1_ONE_LOBE_PRINT_X4.stl`：一个局部原点友好的单叶 STL，用户在切片器中复制四份；
6. `P04T1_FOUR_LOBE_PRINT_PLATE.stl`：四个互不相连、平放、间距至少 `8 mm` 的 4-up 打印板。

`FOUR_LOBE_PRINT_PLATE` 只用于切片排列，其坐标不是装配坐标。四个 assembly STL 必须保留清楚的 NE/SE/SW/NW 身份。

所有 STL 必须：

- 明确按 mm 解释；
- watertight；
- winding consistent；
- 无 self-intersection；
- 无 degenerate face；
- 每个独立叶片恰好一个 connected component；
- 法向朝外；
- 体积为正；
- bounding box 与参数化解析值一致；
- 保存后重新读取并复验。

不得只输出预览网格或不可复现的 GUI 导出。参数化生成脚本是权威源。

## 7. 声学保真与机械门禁

在生成 STL 后，用解析几何和独立 mesh 检查同时计算：

1. 实际四叶总体积；
2. 相对原始 R18×9.2 中央腔的等效 retained-air fraction；
3. 与理想 75% 的绝对百分点偏差；
4. retained cross 的最小宽度；
5. 对每个 8 mm 固定通道口的最小侧向余量；
6. 对 P01 R18 壁面的径向间隙；
7. 对 P03 Ø20.0 与 Ø20.18 外形的径向和轴向间隙；
8. relief 上方的最小剩余实体厚度；
9. 四叶是否互不连接；
10. 装配后是否仍有从四个固定通道到 Ø9 mm 麦克风孔的开放十字路径。

预注册通过门：

- retained-air fraction 必须位于 `75.0%–76.1%`；
- retained cross width 不小于 `13.42333744142368 mm`；
- 任一固定通道口不得被侵入；
- P01 名义径向间隙不小于 `0.09 mm`；
- 对 P03 Ø20.18 mm 的名义径向间隙不小于 `0.10 mm`；
- 对 0.5 mm P03 protrusion 的名义轴向间隙不小于 `0.19 mm`；
- relief 上方剩余高度不小于 `8.49 mm`；
- STL mesh volume 与解析 volume 的相对差不超过 `0.2%`；
- 所有 mesh/manifold 门禁通过。

如果任何门禁失败，不得自动调参或生成第二套候选。分类为 `P04T1 BLOCKED_BY_PRINT_GEOMETRY` 并报告准确失败项。

## 8. 装配说明

生成一份简洁中文装配手册，至少包括：

1. 保持 P03 和麦克风按当前实体位置安装；
2. 移除 P02，不拆 P01/P03；
3. 清理中央腔底和四叶毛刺，不使用胶水或密封垫；
4. 每叶 relief 面朝下、圆弧朝外、两条直边朝向中央十字；
5. 按 NE/SE/SW/NW 放置四叶；
6. 目视确认中央正交十字和四个固定通道口完全开放；
7. 重新安装 P02，并按既有对角顺序逐级紧固；
8. 若 P02 不能无明显翘曲地贴合，立即停止，不得强压；
9. 拆卸时逐片垂直取出，不得撬压 P03 或固定通道边缘。

装配手册必须包含俯视图和剖面图，并明确：该插入件不是方向识别升级件，只是中央腔机制验证件。

## 9. 打印设置和打印后验收

生成建议而非强制 slicer profile：

- 材料：与原装置一致的刚性 PLA；
- 层高：`0.20 mm`；
- 底面平放；
- supports：关闭；
- infill：`100%`；
- 至少 4 perimeters；
- 不缩放；
- elephant-foot compensation 可建议 `0.15 mm`，但必须记录实际设置；
- brim 仅在防翘曲需要时使用，拆除后去毛刺。

生成打印后验收表，至少记录：

- 四片实际高度；
- 外圆弧最大尺寸；
- relief 直径/深度的可达性检查；
- 四片是否能自由放入并平贴腔底；
- P02 是否能正常贴合；
- 是否存在晃动、翘曲或堵塞中央十字；
- 是否进行了打磨及去除量；
- 最终 `PASS/FAIL`；
- 打印机、喷嘴、材料、层高、墙数、填充和 slicer 补偿设置。

本轮只生成模板，不填写虚构实测值。

## 10. 输出目录和产物

使用独立目录：

`outputs/simulation/COMSOL_SCHEME_3A/P04T1_PRINTABLE_FOUR_LOBE_INSERT_RELEASE/`

至少生成：

1. `generate_p04t1_insert.py`
2. `design_contract.json`
3. `P04T1_L1_NE.stl`
4. `P04T1_L2_SE.stl`
5. `P04T1_L3_SW.stl`
6. `P04T1_L4_NW.stl`
7. `P04T1_ONE_LOBE_PRINT_X4.stl`
8. `P04T1_FOUR_LOBE_PRINT_PLATE.stl`
9. `mesh_validation.json`
10. `acoustic_fidelity_audit.json`
11. `fit_and_clearance_release.csv`
12. `assembly_manual.md`
13. `print_settings.md`
14. `post_print_acceptance_template.csv`
15. `figure_01_assembled_top_view.png` 和对应 SVG；
16. `figure_02_z_section_and_p03_relief.png` 和对应 SVG；
17. `figure_03_print_plate.png`；
18. `artifact_inventory.json`
19. `SHA256SUMS.txt`
20. `docs/progress/COMSOL_3A_P04T1_PRINTABLE_FOUR_LOBE_INSERT_RELEASE.md`

更新 `docs/progress/INDEX.md`，只增加 P04T1 条目，不重写既有研究结论。

## 11. 参数化源与测试

优先复用仓库已经可用的几何/mesh 库；不得通过手工编辑二进制 STL 完成设计。若新增代码，先写最小专项测试，再实现。

专项测试至少覆盖：

- 解析 ideal 75% 体积复现；
- 四象限映射正确；
- printable clearances 精确冻结；
- P03 relief 仅位于底部 0.70 mm；
- retained-air fraction 门禁；
- fixed-channel clearance；
- STL watertight/manifold/reload；
- 4-up plate 恰好四个 disconnected components；
- SHA manifest 自洽。

运行：

- P04T1 专项测试；
- 被直接复用代码的相关回归测试；
- `compileall`；
- `git diff --check`。

不要重复运行已知会因无关 Windows/POSIX 路径断言失败的完整回归，也不要修改无关测试。

## 12. 分类和停止规则

### `P04T1 PRINT_PACKAGE_READY`

只有当全部 STL、解析/mesh 门禁、装配路径、图纸、模板、保存重载和 SHA 验证通过时使用。该分类只表示可以打印，不表示物理实验通过。

### `P04T1 BLOCKED_BY_PRINT_GEOMETRY`

当固定参数无法同时满足声学和机械门禁时使用。不得自动搜索新公差、生成第二套设计或调用 COMSOL。

### `P04T1 BLOCKED_BY_PROVENANCE`

当权威文件或哈希不一致时使用。

最终回复必须以上述三个终态之一开头，并给出：

- 最终关键尺寸；
- retained-air fraction；
- P03 和 P01/P02 间隙；
- STL 文件路径与 SHA-256；
- 建议打印设置；
- 装配和打印后验收路径；
- 明确说明未调用 COMSOL、未实测、未开始后续阶段、`final_test_read=false`。

完成后立即停止，等待用户验收。
