# P04T1 — P04E 75% 四叶可打印插入件发布

终态：`P04T1 PRINT_PACKAGE_READY`

日期：2026-08-26

## 范围与边界

本轮仅把 P04M 已保留的 P04E 75% 中央腔机制干预实现为四件式 FDM 打印包。没有调用 COMSOL、没有重新优化声学几何、没有进行实体测量，也没有开始 P04T1 以外的任何阶段。该插入件只用于中央腔机制验证，不是方向识别升级件。

`final_test_read=false`。未 commit、push、tag 或 release。

## 溯源门控

- V2.0.1 权威 ZIP SHA-256：`2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f`，匹配。
- P04T0 `SHA256SUMS`：26/26 条匹配。
- P04M `SHA256SUMS.txt`：23/23 条匹配。
- P04M 实际麦克风位置、P03 Ø9 孔、Ø20/Ø20.18 外形及 0.5 mm protrusion 均保持为冻结 authority。

## 发布尺寸

| 项目 | 冻结值 |
|---|---:|
| P01 名义中央腔 | Ø36.00 mm，R18.00 mm |
| Printable outer radius | 17.90 mm |
| Straight-edge half-width | 6.76166872071184 mm |
| Retained cross width | 13.52333744142368 mm |
| 叶片高度 | 9.20 mm |
| P03 bottom relief | Ø20.40 × 0.70 mm |
| 外圆弧分段 | 每叶 64 段 |
| 最大弦高误差 | 0.0003462 mm（门限 0.02 mm） |

四片严格对应 L1_NE、L2_SE、L3_SW、L4_NW；没有桥、底板、顶板、载体、卡扣、胶、垫片或密封材料。

## 声学保真与机械门禁

- 解析四叶总体积：`2250.6289178073816 mm³`。
- STL 重载网格总体积：`2250.5078276480026 mm³`。
- 网格/解析体积相对误差：`0.0053803%`，小于 `0.2%` 门限。
- 相对 R18 × 9.2 mm 原始中央腔的等效 retained-air fraction：`75.96626963670103%`。
- 相对理想 75% 的绝对偏差：`0.9662696367010284` 个百分点；位于预注册 `75.0%–76.1%` 门内。
- Ø8 mm 固定通道最小侧向余量：`2.76166872071184 mm`；中央正交十字和至 Ø9 mm 麦克风孔的路径开放。
- P01 R18 壁面名义径向间隙：`0.100 mm`。
- P03 Ø20.00 名义径向间隙：`0.200 mm`。
- P03 Ø20.18 ridge 名义径向间隙：`0.110 mm`。
- P03 0.50 mm protrusion 名义轴向间隙：`0.200 mm`。
- Relief 上方剩余实体高度：`8.500 mm`。
- 四叶装配互不连接；4-up 打印板组件名义间距 `10 mm`，大于 8 mm 门限。

全部机械与声学门禁通过。完整数值见 `acoustic_fidelity_audit.json` 与 `fit_and_clearance_release.csv`。

## STL 与 SHA-256

发布目录：`outputs/simulation/COMSOL_SCHEME_3A/P04T1_PRINTABLE_FOUR_LOBE_INSERT_RELEASE/`

| 文件 | SHA-256 |
|---|---|
| `P04T1_L1_NE.stl` | `a899bd38a14395eef6e9dc48f301108c9dc336953ea320df829751f1203b03ed` |
| `P04T1_L2_SE.stl` | `36ca00855a072278745cebe6c2eeb0fc091ea76de4e42eb41160fb35a9655926` |
| `P04T1_L3_SW.stl` | `99562a68220be7c063a442ac8a33b5aa3a2164397683ed9d6d39345aa9666c69` |
| `P04T1_L4_NW.stl` | `8a191fab1f82aa63ef1f3dd9f0d11daa5e6cd3ef3995feae6c70bd3385231b63` |
| `P04T1_ONE_LOBE_PRINT_X4.stl` | `a54d67c23805ad7e91b0b479c0d31dcf891ab56e642a6584e4e50f26fa0b4d44` |
| `P04T1_FOUR_LOBE_PRINT_PLATE.stl` | `9044c42ef38d9abd4d8abe2e3b098816ba10edb914b9316bb14e3cae3b6f0f93` |

六个 STL 均按 mm 解释，保存后重新读取。单叶文件各为一个 connected component；打印板恰为四个。全部 watertight、winding consistent、outward normals、正体积、零退化面，并通过基于简单多边形共形拉伸和闭合有向二流形边审计的 self-intersection 检查。详细结果见 `mesh_validation.json`。

## 打印与装配

建议使用与原装置一致的刚性 PLA、0.20 mm 层高、底面平放、supports 关闭、100% infill、至少 4 perimeters、100% 比例。Elephant-foot compensation 建议 0.15 mm，但必须记录实际设置；brim 只在防翘曲需要时使用。

- 中文装配手册：`assembly_manual.md`
- 建议打印设置：`print_settings.md`
- 空白打印后验收模板：`post_print_acceptance_template.csv`
- 装配俯视图：`figure_01_assembled_top_view.png/.svg`
- P03 relief 剖面图：`figure_02_z_section_and_p03_relief.png/.svg`
- 4-up 打印板图：`figure_03_print_plate.png`

打印后验收模板未填写任何虚构实测值。若 P02 不能无明显翘曲地贴合，或需从任一叶片总高度去除超过 0.20 mm，必须判为 FAIL，不得强压。

## 复现与验证

- 权威参数化源：`generate_p04t1_insert.py`
- 固定设计契约：`design_contract.json`
- 专项测试：`test_p04t1_insert.py`
- `pytest`：7/7 passed。
- `compileall`：通过。
- `SHA256SUMS.txt`：自洽复验通过。
- `git diff --check`：通过。

终态 `P04T1 PRINT_PACKAGE_READY` 只表示该打印包满足预注册 CAD、网格、机械和声学保真门禁，不表示打印件或物理实验已经通过。
