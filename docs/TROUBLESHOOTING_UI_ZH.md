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

原始 WAV/TXT、sidecar、manifest 和 final-test 文件都应只读备份。不要通过改 JSON、改文件名或复制到其他 provenance 目录来绕过门禁。
