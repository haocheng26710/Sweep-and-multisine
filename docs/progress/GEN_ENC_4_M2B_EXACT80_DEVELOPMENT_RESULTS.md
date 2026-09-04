# GEN-ENC-4 M2-B exact80 development 结果

## 终态

`M2B_DEVELOPMENT_NO_FAMILY_STRUCTURED_MECHANISM`

依据预注册合取门槛，停止 M2，不读取 validation，不进入 M3。

## 执行范围

- exact80：四家族各 20，共 80/80 身份；
- 3675 个 development nuisance cell、两个 repeat、208 点主频带；
- 每身份成对运行 `CAD_BASELINE` 与等体积 `SPINE_ONLY_ABLATION`；
- 所有身份和两条 arm 均可行，所有 case 被动、互易、有限；
- validation reads = 0，final-test read = false。

运行采用六个互不重叠的本地 worker；按身份原子封印并最终单独聚合。调度变化不改变样本、种子、响应或统计。NEAR_20 暴露 `shared_alpha=0.07` 的 binary64 归一化端点略超 1；沿用 M1 已冻结的 `[0,1]` clamp 后重跑该身份。该修正只处理浮点端点，未改变科学坐标。

## 结果

四家族平均相对 SPINE/WINDOW 消融响应效应为：HAND `2.493%`、NEAR `3.511%`、RANDOM `4.324%`、PHYSICS `4.928%`。效应稳定秩为 3，六个家族 pair 至少在 response 或 Gram endpoint 之一达到 FWER 0.05；12 个 endpoint 中 8 个显著，最小调整 p=`9.9999e-6`。

但是机制效应几何的最弱 between/within ratio 只有 `0.944437 < 1`，失败于预注册阈值。最弱两对为 RANDOM–PHYSICS `0.944437` 与 HAND–NEAR `0.948137`。其余 pair 为 `1.02252–4.01516`，均不能覆盖合取门槛失败。

更重要的是，实际流体模型本身的家族分离很弱：

| arm | minimum between/within | mean between/within |
|---|---:|---:|
| CAD baseline | 0.0475964 | 0.261781 |
| SPINE-only | 0.0467728 | 0.263950 |

即使 SPINE/WINDOW 消融效应在统计上存在家族差别，它也没有形成全 pair 稳健分离，且 baseline 并未比 SPINE-only 显示有意义的整体编码几何提升。因此不应使用 validation 尝试“救回”该机制，也没有依据升级 M3。

独立 verifier 从 80 个身份 summary、compact singular arrays 与 max-T 输出重算了全部终态门槛并通过。机器证据位于 `outputs/gen_enc/GEN_ENC_4_M2B_EXACT80_DEVELOPMENT/`。未执行 commit、push、tag 或 release。
