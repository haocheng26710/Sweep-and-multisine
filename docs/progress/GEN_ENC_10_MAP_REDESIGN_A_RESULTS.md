# GEN-ENC-10 MAP-REDESIGN-A 静态几何映射原型

## 问题与范围

本轮只问：能否在不运行声学求解的情况下，重新编译 family 参数到实体窗口布局，使 exact80 四家族在几何层先达到可辨认，同时保持总体积、星型连通、根长范围和最小制造尺寸？

输入固定为 exact80，禁止换样。静态门禁预先设为：

- 80/80 扇区体积误差不高于 1e-12 m³；
- 根长保持在 2–30 mm；
- 活动窗口宽度和 collector 边距均不低于 1.6 mm；
- 保持正面积星型连通；
- 全局最小 family between/within 不低于 1；
- HAND–NEAR between/within 不低于 1。

没有读取声学响应，没有运行 COMSOL，也没有修改正式 M2-B 编译器。

## 四个固定候选

| 候选 | 不变量 | 全局最小 | HAND–NEAR | 结论 |
|---|---|---:|---:|---|
| BASELINE_COLLAPSED | 通过 | 0.516 | 0.516 | 不通过 |
| F07_LITERAL_SLOTS | 通过 | 0.343 | 0.343 | 不通过 |
| NEAR_STAGGERED_SINGLE | collector 边距仅 1.4 mm | 0.753 | 2.417 | 不通过 |
| NEAR_DUAL_VOLUME_COMPENSATED | 通过 | 0.722 | 2.495 | 不通过 |

F07 原样保留槽位并不能解决 HAND–NEAR，因为两者仍把单一共享参数复制到中央 WINDOW_2。

交替单窗能明显拉开 HAND–NEAR，但违反 1.6 mm 边距门禁，因此直接拒绝。

对称双窗是本轮最有信息量的候选：每个 NEAR 侧窗宽为 max(2 mm, 原宽/2)，并重新求根补偿新增窗口体积。exact80 最大体积误差为 8.47e-22 m³，根长 12.58–25.57 mm，最小窗宽 2 mm，最小边距 2.038 mm，全部合格。HAND–NEAR 提升到 2.495，但最弱对转移为 NEAR–RANDOM 0.722，RANDOM–PHYSICS 也只有 0.893，仍未达到全局门限。

## 结论

终态：MAP_REDESIGN_A_NO_STATIC_GATE_PASS。

A 轮证明了 HAND–NEAR 重叠可以通过物理窗口布局改变，而不是不可避免；但仅修改 NEAR 会把重叠转移给 RANDOM 和 PHYSICS。不能因为目标代表对改善就选择对称双窗，更不能进入声学求解或替换正式映射。

下一轮若执行 MAP-REDESIGN-B，应保留 NEAR 对称双窗的体积补偿思想，同时为 RANDOM 的边关联和 PHYSICS 的环邻接建立不同的实体路径语义。约束是不能只加一个显式 family 标签形状来人为分类；差异必须来自原有 edge/ring 参数的实际流体路径。

一次性逻辑 TUI 已按原型规则删除；可保留的答案、候选精确定义和数值均封存在 result_summary.json。

未运行声学、COMSOL、exact80 response、validation/final-test；未提交、未 push。
