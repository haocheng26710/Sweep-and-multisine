# GEN-ENC-11 MAP-REDESIGN-B 静态路径语义原型

## 设计

B 轮保留 A 轮 NEAR 对称双窗，并把原 8 mm collector 改为前 6 mm 编码层和后 2 mm共同混合层；2 mm 高 spine 始终贯通。

- HAND 使用中央单通道；
- NEAR 使用对称双通道；
- RANDOM 将三个 incident edge 参数映射为并联通道；
- PHYSICS 将两个 ring 参数映射为两个串联的 3 mm 收缩级。

RANDOM 预先固定三种长度规则：全长 6 mm、参数决定 2–6 mm、相邻/对置 edge 决定 4/6 mm。编码层替代原全宽 collector，所有流体体积差均由 root 重新求解补偿。

门限与 A 轮相同，并增加通道间隙不低于 1.6 mm。只读取 exact80 身份参数和静态几何，不读取或计算声学响应。

## 结果

| 候选 | 全局最小 | 平均 | HAND–NEAR | 限制对 |
|---|---:|---:|---:|---|
| B0 edge 全长 | 0.7005 | 2.0051 | 2.9933 | NEAR–RANDOM |
| B1 edge 参数长度 | 0.9244 | 1.9254 | 3.0329 | NEAR–RANDOM |
| B2 edge 角度长度 | 0.8422 | 1.9694 | 3.0244 | NEAR–RANDOM |

三个候选均通过 80/80 体积、根长、最小通道宽度、collector 边距、通道间隙与连通门禁。B1 最接近目标：根长 14.95–28.65 mm，最小通道宽 2 mm，最小边距 2.038 mm，最小通道间隙 3.013 mm，最大体积误差 8.47e-22 m³。

B1 已使除 NEAR–RANDOM 外的所有家族对超过 1：HAND–RANDOM 1.146、RANDOM–PHYSICS 1.144；但 NEAR–RANDOM 只有 0.924，仍低于冻结门限，不能按四舍五入或事后放宽判为通过。

## 结论

终态：MAP_REDESIGN_B_NO_STATIC_GATE_PASS。

并联 edge 通道与串联 ring 收缩级成功解决了 A 轮 RANDOM–PHYSICS 的重叠，也保留了 HAND–NEAR 的明显改善。剩余设计问题已缩小为一个：如何让 NEAR 的 shared coupling 与 RANDOM 的 sector-local edge incidence 形成不同的真实流体路径。

若继续 C 轮，最合理的物理方向是把 NEAR 的 shared 参数作用于一个跨四扇区共同的环形或公共节流元件，而 RANDOM 继续保持扇区局部并联 edge 通道。该改变涉及共享拓扑，必须单独检查是否仍符合星型连接语义，不能直接吸收进正式 M2-B。

一次性原型代码已删除；B1 的定义、不变量和完整结论封存在 result_summary.json。正式编译器未修改。

未运行声学、COMSOL、validation/final-test；未提交、未 push。
