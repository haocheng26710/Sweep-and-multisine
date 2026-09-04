# GEN-ENC-4 M2-B exact80 development contract

状态：`CONTRACT_FROZEN_EXECUTION_NOT_STARTED`。本合同只授权未来单独运行 development partition；validation、final-test 和 M3 均不授权。

## 冻结对象

使用 exact80 原顺序、3675 个 development nuisance cell、两个冻结 repeat 和 208 点主频带。每个身份成对生成 `CAD_BASELINE` 与 `SPINE_ONLY_ABLATION`：后者关闭所有可变 WINDOW、保留固定 SPINE，并用既有 80-step bisection 恢复各 sector 的冻结 q 体积目标。禁止改变身份、补零宽 edge、创建 sector-pair duct、选择性丢弃失败身份或根据响应调节几何/损耗。

求解器固定为真实流体星形图的九段无源传输线 cascade。每个 sector 的外至内顺序为 collar、outer step 3/2/1、outer connector、cavity、inner connector、collector、SPINE/WINDOW entry；中央只保留冻结 40% plenum compliance。突变截面由压力与体积速度连续的二端口级联处理。每 sector 的冻结 loss 参数作为全臂统一损耗类别；batch 扰动只作用于入口 union area，independent manufacturing 扰动只作用于 outer connector，固定 collector/steps/collar 不扰动。该 nuisance 映射不得事后更改。

NEAR 的 `shared_alpha` 归一化沿用 M1 已冻结的结果盲 binary64 边界修正：计算后夹紧到 `[0,1]`。这只处理 `0.07` 端点的浮点超界，不改变任何科学坐标。

## 输出与判定

必须保存每身份、cell、repeat、arm 的响应、可行性、被动性、互易性、体积残差与哈希。主分析只用 development：

1. 对 baseline 与 spine-only 分别计算与 GEN-ENC-3A 相同的响应/state Gram、between/within、弱对和稳定秩指标；
2. 计算 paired ablation signature `baseline-spine_only`，在 identity 层进行四家族 omnibus 和六个预定 pair 的 max-T/Westfall–Young 调整；
3. 报告每家族效应量和 nuisance/repeat 稳定性，不把单成员预飞结果当家族结论。

`M2B_DEVELOPMENT_MECHANISM_FAMILY_STRUCTURED` 仅在全部 80 身份可行、所有 case 被动互易有限、paired-effect between/within ratio ≥1、稳定秩 `r_stable≥3`，且至少一个预定家族 pair 在 identity-level FWER 0.05 下分离时成立。否则终态为 `M2B_DEVELOPMENT_NO_FAMILY_STRUCTURED_MECHANISM`。无论哪种终态，本次都不得读取 validation；若通过，只能申请另一个 validation 合同。M3 始终保持未授权。

本合同的入口证据为 M2-B 四代表预飞及其独立核验；预飞门槛通过只授权本 development 合同，不预断 exact80 结果。
