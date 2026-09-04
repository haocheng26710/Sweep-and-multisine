# COMSOL TRANS-1 RETRY_02 — fine mesh 后 solution/dataset 有界修复

日期：2026-08-27  
终态：`TRANS1_RETRY_02_BLOCKED_BY_SOLVER_DATASET`

## 首页结论

本轮在全新 COMSOL 6.4、4 核会话中完成了规定的同会话 coarse 控制，随后只执行了一次授权的 fine study/solution/dataset 修复。coarse ISO-CODED/N 四频点真实 Pressure Acoustics 求解、全部复数/能量场、MPH 保存—移除—重载均通过。fine 模型严格在全部网格操作完成后才重新创建 `std_freq/freq`；`study.run()` 返回，并且 Java 审计确认存在非空 Solution 及绑定的 Solution dataset，但默认 MPh 场提取不完整。唯一允许的显式 dataset 重提取随后失败：MPh 将 Java dataset tag `dset1` 作为显示名称查找并报告 `Dataset "dset1" does not exist.`。

依照预先冻结的停止规则，本轮立即停止并分类 `TRANS1_RETRY_02_BLOCKED_BY_SOLVER_DATASET`。没有再改用 dataset Node、显示 label 或 Java numerical evaluation，没有建立第三种网格，也没有启动 256 点门禁、六组合、外场或后续阶段。

## 1. Provenance 与冻结边界

- TRANS-0 RETRY_02 既有 manifest 17/17 重新计算匹配；其 `TRANS0_PASS_FOR_TRANS1_RETRY` 保持不变。
- TRANS-1 RETRY_01 既有 manifest 32/32 重新计算匹配；其 `TRANS1_RETRY_01_BLOCKED_BY_SOLVER` 保持不变。
- 本轮未覆盖或重新分类任何既有 PASS/BLOCKED 记录。
- 几何、内部空气域、端口、麦克风、物理参数、频率网格、固定窗口及科学门槛均未改变。
- `final_test_read=false`；未修改打印包/STL，未打印，未运行外场、分类器、参数搜索、TRANS-2/TRANS-3 或 P05–P10。

## 2. 同会话 coarse 控制：PASS

全新会话初始模型列表为空。原样复用 TRANS-0 RETRY_02 权威建模链路，ISO-CODED/N、coarse mesh、`[1000,1850,3800,5000] Hz` 四点全部完成。

| Hz | microphone real (Pa) | microphone imag (Pa) | E all (J) | E HR03 (J) | E HR07/S (J) | E plenum (J) |
|---:|---:|---:|---:|---:|---:|---:|
| 1000 | -1.27320262417 | -0.222625478972 | 3.74733225575e-11 | 4.19373505850e-12 | 2.06592629776e-12 | 1.81470691832e-12 |
| 1850 | 0.357240053724 | 0.146468417190 | 4.76284766593e-11 | 1.64712373711e-11 | 1.22086947666e-12 | 9.78626825467e-13 |
| 3800 | 0.741711735034 | -0.254418906762 | 9.99350306907e-11 | 1.90023938290e-11 | 8.96125128511e-13 | 7.74359736621e-13 |
| 5000 | 0.421022214787 | 0.0752936967767 | 3.32802156507e-11 | 7.58564784650e-12 | 1.45143014780e-13 | 2.18796322099e-13 |

Java study=`std_freq`、feature=`freq`；Solution=`sol1` 且 `is_empty=false`；Solution dataset Java tag=`dset1`、label=`研究/解 1`、binding=`sol1`。六个数组长度均为 4、finite，麦克风结果非全零。求解耗时 13.737 s。

coarse mesh：62,356 elements、13,158 vertices、minimum/mean quality `1.251e-06 / 0.5470`；继续登记 `LOW_MESH_QUALITY_WARNING`。保存的 `SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE.mph` SHA-256 为 `084f6989aca8011d1c27e00249b4ce2ca7f56a08e90aa45763cb02eaa6a1f3f6`。移除并重载后麦克风最大复数差为 `0 Pa`，通过 `1e-12 Pa` 门槛；其他场最大差不超过 `1.29247e-26`。

这些数值仅证明本次会话、许可证和 coarse 建模链路可用，不是方向选择性结论。

## 3. fine smoke 的唯一修复与失败位置

执行顺序符合授权：几何/selections/physics → 删除权威 builder 预建的 `std_freq` 及旧 solution tags → 完成 fine mesh 操作 → 重新创建 `std_freq/freq` → 写入冻结四频点 → `study.run()` → 审计 Solution/dataset → 提取场量。

实际观察：Java 解非空门禁通过，且存在与有效解绑定的 Solution dataset；否则 runner 不会进入显式 dataset 分支。默认 MPh 提取未形成完整六字段四点结果。按授权只进行一次显式 dataset 重提取，使用 Java 审计得到的 `dset1`；MPh 的名称解析报错：

```text
ValueError: Dataset "dset1" does not exist.
```

这比 RETRY_01 的“场数组为空”进一步把问题界定为 Java tag 与 MPh dataset 名称/Node 寻址不一致。由于完整 field lengths 与 fine mesh statistics 在异常前未被持久化，报告不推测其具体数值。原始 traceback 保存在 `solver_failure.json` 和 `execution_log.txt`。

## 4. 网格数值状态

- fine 四点场量验收：FAIL/BLOCKED。
- ISO-CODED/N coarse/fine 256 点：未开始。
- 共振中心变化 `<1%`：未评估。
- 固定窗口关键对比变化 `<0.5 dB`：未评估。
- 六组合：`0/6`。

因此没有可接受的 fine 数值结果，不能把 coarse 四点控制升级为网格收敛证据。

## 5. 声学科学状态与打印建议

本轮没有生成 2×2 固定窗口矩阵、diagonal advantage、off-diagonal energy、峰漂移或 ISO-SYM/MIX-CONTROL 对照；没有新的正面或负面选择性结论。当前证据不授权打印 TRANS-I2F 包，也不能声称可靠方向分类或真实房间定量预测。

建议：`DO_NOT_AUTHORIZE_PRINT_FROM_THIS_STAGE`。如用户另行授权新的阶段，下一兼容性问题已明确为 MPh dataset display name/Node 与 Java tag 的映射；本轮不继续处理。

## 6. 未来机械选项（仅登记）

“可在 TRANS-2 将完整八边形底盘/盖板缩减为南北两个通道承载臂加中央麦克风固定区；前提是内部空气域、入口端面位置、局部入口边缘、通道高度和密封边界保持不变。”

该选项不是本轮 solver 修复方法，未生成或修改 STL，也未启动 TRANS-2。

## 7. 验证与产物

专项测试、`compileall`、JSON/CSV 结构检查、既有 manifest 复核、当前产物 SHA-256 和 `git diff --check` 均在交付前执行。主要机器产物位于 `outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_02/`，包括 coarse 控制 MPH、完整复数四点 CSV、能量 CSV、study/solution/dataset 审计、几何/selection 审计、mesh/reload 状态、原始失败日志、artifact inventory 与 `SHA256SUMS.txt`。

