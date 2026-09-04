# GEN-ENC-4 CAD-to-edge 路由审计与 M2-B 合同

## 结论

路由审计终态为 `M2_DIRECT_EDGE_PHYSICAL_MAPPING_REJECTED`。现有权威不能把 M1 的 local-to-local reduced edge 转换为实体分布通道；因此上一阶段 M2-A 只能保留为假设性长度敏感性，不能成为完整 M2 的入口。

CAD-0 U2 的批准语义明确规定：RANDOM edge 是共享 plenum／固定 spine 连通底板内的附加 throttling window；reduced graph 仅为描述量，不是 physical-fluid graph；任何因果 edge 声明必须另建 spine/window ablation contract。正式 identity 的 actual-fluid 审计只有四条 `CENTRAL_PLENUM—SECTOR_i` 正面积连接，没有 sector-to-sector 正面积连接。

三种映射均被排除：

1. 直接 sector-to-sector 管道没有 CAD 面或中心线权威；
2. 2 mm WINDOW 是 sector 内部节流孔深度，不是两个 sector 端点间的路径；
3. 把 `sector—plenum—sector` 合并成单条边会重复计算共享 plenum、径向臂和空气体积，并改变冻结五节点拓扑。

## 替代方案

已冻结 `GEN-ENC-4 M2-B spine/window ablation` 预执行合同，但尚未授权响应计算。它保持真实星形流体图，对每个固定代表只比较：

- `CAD_BASELINE`：固定 SPINE 加实际启用 WINDOW；
- `SPINE_ONLY_ABLATION`：保留固定 SPINE，关闭可变 WINDOW。

关闭 WINDOW 后必须用既有 80-step bisection 重新求解 sector root length，使每个冻结 q 体积目标不变；禁止封闭固定 SPINE、创建 sector-pair duct、从 M2-A 结果选择路径长度，或读取 validation/final-test。

执行前仍需实现并冻结：真实流体星形臂的分段编译器、两臂体积与正面积面审计、被动互易 cascade 参考测试、独立结果 verifier。完成这些条件后才适合运行四代表 development-only M2-B 预飞；当前不进入完整 M2 或 M3。

机器可读证据位于 `outputs/gen_enc/GEN_ENC_4_CAD_TO_EDGE_ROUTE_AUDIT/`。未执行 commit、push、tag 或 release。
