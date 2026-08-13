# 最终软件验证用户验收归档

状态：通过并归档

日期：2026-08-13

分支：`feature/v2-dual-input`

受验代码提交：`8f2c8c2128e81153a2843adf355553e0642b97ce`

## 验收对象

本归档只记录以下工作区中已经生成的软件验证总结，不复制或提交该工作区及其模拟数据产物：

`D:\Bristol course\dissertation\UI_acceptance_workspace\outputs\ui_simulated_flow\closeout_reports\ui-summary-20260813T111624716115Z\`

验收读取 `software_validation_summary.md`、`software_validation_summary.json`、JSON SHA-256 sidecar，以及 JSON 清单显式引用的六个上游 artifact。没有扫描目录来推断输入，也没有读取 final-test。

## 最终步骤状态

| 步骤 | 状态 | 验收说明 |
|---|---|---|
| 01–07 | `passed` | 模拟软件验证的环境、使用方式、计划、刺激、采集、单次处理和数据集完整性步骤通过 |
| 08–09 | `not_applicable` | sparse Multisine 路线安全跳过，不伪造 FeatureSet-only P2-B/P4/P5/P6 authority |
| 10 | `blocked` | 没有批准的 P9-D/freeze authority |
| 11 | `sealed` | `final_test_read=false`，final-test 未读取 |
| 12 | `ready` | 软件验证总结已经生成并完成本次哈希复核 |

## 数据集与计划结果

- `expected_and_present=32/32`
- `warning=0`
- `failed=0`
- plan revision：`rev-002`
- `data_origin=simulated`
- `run_purpose=software_validation`
- `scientifically_eligible=false`
- `final_test_read=false`

## 报告 SHA-256

| 文件 | 实际 SHA-256 | 结果 |
|---|---|---|
| `software_validation_summary.md` | `a2c25287d59a8d40dee551e4cc9f2c4a36de6ebe2a3134f62fbc891de0db14e1` | 与 JSON 中记录一致 |
| `software_validation_summary.json` | `ae4dab7c6fe4f7eee0e0bad949ef4bf93ed0b0abe9ed9e3b896a39c704c5639a` | 与 `.sha256` sidecar 一致 |

## 上游 artifact 完整性复核

清单中六个显式上游 artifact 均存在，且逐文件复算 SHA-256 后全部匹配：

| Role | 清单 SHA-256 | 存在 | 匹配 |
|---|---|---|---|
| `workflow_state` | `c53941b7d3927c72eeb5e2d4eed553a86107aab6fe7dd000ec444c719de120c4` | 是 | 是 |
| `plan_manifest` | `9cb5ca246b115efed56d42d74211613f2133e63569fb916d30c49de66fda730d` | 是 | 是 |
| `stimulus_manifest` | `103d63923fe8f09df50db6c2a3175507257db731cda7c22853d56f6958a1a80f` | 是 | 是 |
| `acquisition_manifest` | `274e7f7beee188921ef62cfbf4403458af0ad0b7ab12bcd95166cf552929febb` | 是 | 是 |
| `processing_manifest` | `f299399d1a22f9054fa81f078fd924ef3e25b5b9f0caa85300da6d3b864e28f2` | 是 | 是 |
| `dataset_audit` | `6009a93f12925aff27692ded836d819fa5b3c09658c513c6adaf87d17d41628b` | 是 | 是 |

复核结论：`6/6` 存在，`6/6` SHA-256 匹配。

## 科研与权限边界

本次只完成 `simulated/software_validation` 软件验证验收。它不授予科研资格，不允许形成科研结论，也不授予 canonical analysis、P9-D/freeze、deployment 或 final-test 权限。真实 Multisine/P8 仍未开放；若未来接入真实数据，必须使用新的显式 `real_experiment` provenance、获批的真实后端和独立门禁，不得改写或复用本模拟验收来提升资格。

## 实际执行的复核

- 核对当前分支、工作树和 HEAD：分支正确、工作树 clean、HEAD 为受验提交。
- `git fetch origin feature/v2-dual-input` 后运行 `git rev-list --left-right --count origin/feature/v2-dual-input...HEAD`：归档提交前结果为 `0 1`，即远程没有新提交，本地仅领先尚未 push 的 FIX7 提交，不存在分叉。
- 对 Markdown、JSON、JSON sidecar 和六个上游 artifact 执行 SHA-256 复算：全部符合本报告记录。
- 归档文档写入后执行 `git diff --check`；准确结果记录在本次 docs-only Git 提交及最终回复中。

## Git 边界

本次归档只新增本文件并更新 `docs/progress/INDEX.md`。不修改程序代码、算法、schema 或配置；不提交 `UI_acceptance_workspace` 或任何模拟产物；不创建 tag、release，也不合并分支。
