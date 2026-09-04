# COMSOL TRANS-1P0 — 紧凑打印几何与声学域不变性门禁

日期：2026-08-27T02:18:28.417810+01:00  
终态：`TRANS1P0_COMPACT_PRINT_PACKAGE_READY_ACOUSTIC_DOMAIN_INVARIANT`

## 结论

V1C 已把 V1 的完整八边形外壳缩减为中央机械圆台/枢纽与 N/S 双长分支，删除另外六个无声道实心区域。只修改内部空气域以外的 PLA；现有 TRANS-I2F 内部空气域和当前 COMSOL 流体模型仍可沿用。

READY 仅表示可作为打印候选，不表示256点、完整声学仿真、外场或实体实验通过。

## 权威与不变性

- 原 V1 SHA-256：`17/17` 重新计算匹配；原 ZIP、源代码、STL、文档均未修改。
- V1C 直接复用 V1 `build_geometry()` 返回的同一个 `airspace` 对象。
- 二维 symmetric difference `0.0 mm²`；总面积、各子域面积/质心、端口位置/宽度、三维体积差均为0。
- 主空气域 `13860.275699 mm³`；HR03 `2488.044774 mm³`；HR07 `728.044774 mm³`；微汇合区 `543.655245 mm³`。
- N/S端面保持 y=±117 mm、宽20 mm；除微汇合区外重叠0 mm²。
- P04M接口保持 Ø9.0 mm短孔 z=1..3 mm、Ø8.8 mm膜面 z=1.0 mm。

## 外形、紧固与密封

- 新底盘/盖板共同外形：`100.0 × 234.0 mm`，含5 mm brim代理 `110.0 × 244.0 mm`。
- 10个 N/S 与左右对称的主盖 M3 紧固件；覆盖中央、两腔体和两入口附近；转盘孔不计入。
- 原 P14/P15 四坐标完整保留，P03 Ø20.4 mm座完整保留。
- 最小名义侧壁4.0 mm；连续密封台4.0 mm；空气域到主螺孔边缘最小 `4.80 mm`。
- N/S端面为有意开放端口，不适用封闭侧壁；其侧壁仍为4.0 mm。
- 螺孔和螺母槽平面均不侵入空气域；0.8 mm螺母槽下保留2.4 mm盖板皮层，不形成贯穿漏气路径。

## STL与节材代理

- 底盘：watertight `True`，winding `True`，components `1`，体积 `109521.141 mm³`。
- 盖板：watertight `True`，winding `True`，components `1`，体积 `41265.721 mm³`。
- V1→V1C 底盘体积减少 `70.97%`；盖板减少 `67.66%`；总 PLA 几何代理减少 `70.14%`。
- 材料与打印时间仅按几何体积一阶代理估计约减少 `70.14%`；未运行切片器，不是耗材克数或打印时长实测。

## 只需打印

1. `STL/TRANS_I2F_V1C_COMPACT_BASE_HR03_N_HR07_S.stl`；
2. `STL/TRANS_I2F_V1C_COMPACT_SEALING_LID.stl`。

P03与已有P14/P15/P16直接复用，不需要重复打印。

## 范围

- 新 COMSOL solve=0，`study.run=0`；256点、六组合、TRANS-2/3、外场、参数搜索和实测均未开始。
- 未读取 final-test；`final_test_read=false`。
- 未修改频率、窗口、阈值或既有科研结论；未 commit、push、tag 或 release。

## 产物

- `outputs/print_packages/TRANS_I2F_COMPACT_TWO_PORT_V1C/`
- `outputs/print_packages/TRANS_I2F_COMPACT_TWO_PORT_V1C.zip`（SHA-256 `ffc0b5eddfcc0c78d3f121ba7969839abdbca401a4da983b5c7d98612f3dada3`）
- `docs/progress/COMSOL_TRANS_1P0_COMPACT_PRINT_GEOMETRY_GATE.md`
