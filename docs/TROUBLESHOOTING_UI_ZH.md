# 桌面向导故障排除

| 现象 | 原因与处理 |
|---|---|
| PySide6 无法导入 | 源码版运行 `python -m pip install -r requirements.txt`；打包版不要另装 Python，重新解压完整 one-folder。 |
| 输出目录已存在 | 这是不可覆盖门禁。创建新的 run-id、package revision 或输出目录，不要删除/篡改旧证据。 |
| P9 显示 authority 缺失 | 显式选择正确的 P2-B/P4/P3-C/P9-A 权威文件；程序不会扫描“最近文件”。 |
| scope 含 final-test 被拒绝 | 正常安全行为。只建立 training/development scope；不得用 final-test 调参。 |
| package self-check 失败 | 不运行离线读取或 final-test。核对 manifest、sidecar 和所有 SHA-256；原 package 不修补，重新生成 revision。 |
| 离线结果 blocked/invalid/unavailable | 不会产生预测。查看 `readout_manifest.json`、`prediction.json` 和 QC 原因；warning 结果仍保留 warning。 |
| score 或 margin 看似“低置信” | score 是距离且越小越好；margin 是两个最优距离之差，都不是概率。 |
| 真实 Multisine/P8 按钮禁用 | 当前真实后端未获批准，只可登记 WAV/sidecar/manifest/hash；等待 DEV-D 硬件与真实数据 authority。 |
| final-test 始终 sealed | 缺少任一冻结计划、真实 package、自检、独立批准、保管人、一次性规则、版本/scope 或真实后端 authority 都必须阻塞。 |
| Git 状态在打包版不可用 | 打包版使用 `build_manifest.json` 记录构建 commit；不要求用户安装 Git。 |
| 中文/空格路径失败 | 将整个 one-folder 放在可写用户目录，选择新的工作区；不要把运行输出写入安装目录。保留技术日志用于复核。 |
| 顶部仍显示旧工作区 | 新选择采用重启生效策略。确认旁边显示“下次启动生效”，点击“立即重启”或关闭后重新启动；当前窗口不会热切换后端。 |
| 无法选择工作区 | 目标必须是可创建、可写目录。不要选择已有文件、只读介质或无权限的系统目录；按提示改选用户目录。 |
| 任务运行时不能更换工作区 | 这是输出一致性门禁。等待任务结束或取消任务，再点击“更换工作区”；程序不会把同一任务拆分到两个目录。 |
| `--workspace` 与界面保存值不同 | 命令行值优先且只影响该次启动，不会改写保存值。移除 `--workspace` 后，下次启动恢复使用保存值。 |

原始 WAV/TXT、sidecar、manifest 和 final-test 文件都应只读备份。不要通过改 JSON、改文件名或复制到其他 provenance 目录来绕过门禁。

## 打包版“模拟软件验收”失败

新版 one-folder 已包含受 `validation_assets/pre_experiment_acceptance/assets_manifest.json` 管理的只读验证资源。请完整解压/复制整个 `SweepMultisineUI` 文件夹，不能只复制 EXE；不要修改 `_internal/validation_assets` 中的官方 REW 文件。它们仅用于 `external_reference/software_validation`，不能用于科研结论。

若界面显示“模拟验收未完成：打包验证资源缺失或不可读取。”，先查看专业模式的异常类型、缺失路径和 traceback，再打开该次唯一 run-id 下的 `acceptance/technical_log.txt`。失败不会覆盖已有输出；重新运行会生成新的 run-id。环境检查与模拟验收是两个独立结果，因此可同时看到“环境检查：passed”和“模拟验收：failed”。T0～T3 没有完成时应显示“尚未完成”。

不要从源码 `tests/fixtures` 手工补文件，也不要修改 fixture 以迁就 hash。若 validation asset 缺失或 hash 不一致，应重新取得完整发行目录。真实 Multisine/P8 仍被阻塞，final-test 仍为 sealed；模拟验收通过不会解除这些门禁。
