# DEV-UI4 最终用户验收（T-UI0～T-UI10）

状态：完成（软件验证）

日期：2026-08-10

分支：`feature/v2-dual-input`
数据资格：`simulated`/`external_reference` + `software_validation`；`scientifically_eligible=false`

## 受控场景结果

| 场景 | 结果 | 实际证据 |
|---|---|---|
| T-UI0 首次启动与环境检查 | `pass` | 源码 offscreen smoke 返回 0；dist EXE 从项目外、隔离 PATH 启动返回 0；打包配置 `pipeline_sweep --validate-only` 返回完整 resolved config。 |
| T-UI1 模拟练习 | `pass` | UI2/UI3 受控 E2E 与页面场景共 `12 passed`；全量回归覆盖 DEV-C16 模拟验收 worker。 |
| T-UI2 官方 REW | `pass` | `test_official_rew_ui_registration_to_pipeline_e2e` 通过；数据为 `external_reference/software_validation`，实验身份为空。 |
| T-UI3 实验计划与 P2-B | `pass` | 显式计划、样本登记、formal P2-B E2E 通过；不扫描目录，final-test 不进入 scope。 |
| T-UI4 正式支持的 P4/P5/P6 批量阶段 | `pass` | P4/P6 formal CLI 专项 `4 passed`；UI3 capability gate 回归通过。 |
| T-UI5 模拟 P9-A/B/C/D | `pass_with_warning` | P9-A completed，5/15 tone；P9-B completed，3 folds、每 fold 3 tones；P9-C `completed_with_warnings`；打包 EXE P9-D loader/self-check 通过。全部 scientific/deployment false、final-test 未读。 |
| T-UI6 frozen package 离线读取 | `pass_with_warning` | 打包 EXE 在隔离 PATH 下恢复已知 90°；`processing_status=completed_with_warnings`、QC warning，prediction 可用；semantic result 与源码重复运行一致。 |
| T-UI7 真实 Multisine | `blocked_as_designed` | 状态/UI/worker 六项门禁专项的一部分通过；真实 WAV 可登记，但 P8 与依赖的真实 P9-C/freeze/final-test 不启动。 |
| T-UI8 final-test sealed 与误访问 | `blocked_as_designed` | 默认 sealed；缺 authority 时内容/metadata/hash 均未读并写 incident；一次性状态机专项通过。没有读取真实 final-test 文件。 |
| T-UI9 Windows dist 启动与基本工作流 | `pass` | `SweepMultisineUI.exe` 从 `C:\Users\Firefly\AppData\Local\Temp`、`PATH=C:\Windows\System32` offscreen 启动；packaged worker 完成 config、P9-D、offline readout。 |
| T-UI10 空格/中文工作区 | `pass` | EXE 使用 `outputs/ui4_uat/中文 工作区`，GUI/worker 均成功；程序/参数分离传递。 |

## 实际命令与结果

- `python -m pytest tests/test_ui4_runtime.py ... tests/test_ui4_packaging.py -q` → `18 passed in 3.43s`。
- UI2/UI3 UAT 选择集 → `12 passed in 4.01s`。
- P4/P6 formal CLI → `4 passed in 5.59s`。
- final-test/real Multisine 门禁选择集 → `6 passed in 0.37s`。
- `python -m pytest -q` → `797 passed in 124.05s`。
- `python -m compileall -q src scripts tests` → exit 0，无输出。
- `git diff --check` → exit 0，无输出。
- `python scripts/run_gui.py --smoke-test --workspace "outputs/ui4_uat/source 中文 工作区"` → exit 0。
- dist SHA 清单复核 → `2533` entries、`0` failures；最终 EXE SHA-256 `3360a281d54caa091e2170bbf7140eb01527aadf8e3d22d737720181c479c9ce`。

## P9/离线输出

- P9-A：`outputs/ui4_uat/simulated/software_validation/ui4-p9a-20260810/tone_selection`
- P9-B：`outputs/ui4_uat/simulated/software_validation/ui4-p9b-20260810/projection_ablation`
- P9-C：`outputs/ui4_uat/simulated/software_validation/ui4-p9c-20260810`
- P9-D：`outputs/ui4_uat/simulated/software_validation/ui4-p9d-20260810/readout_package_packaged`
- packaged offline：`outputs/ui4_uat/simulated/software_validation/ui4-p9d-20260810/offline_readout_packaged`

这些目录均为忽略的可再生成软件验证产物，不进入 Git，也不得用于科研结论。
