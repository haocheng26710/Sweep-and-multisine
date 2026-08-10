# Sweep / Multisine 声学分析桌面向导用户手册

## 安装与启动

源码版安装 `requirements.txt` 后运行 `python scripts/run_gui.py`。构建者另装 `requirements-ui-build.txt`，执行 `powershell -ExecutionPolicy Bypass -File scripts/build_windows_gui.ps1`，产物为 `dist/SweepMultisineUI/SweepMultisineUI.exe`。one-folder 目录必须整体保留。

资源目录包含配置和说明，只读；工作区保存 sessions、staging metadata、计划、日志和 outputs。程序不扫描工作区自动组 cohort，所有输入均需显式选择/manifest。简易模式显示当前任务、结果和下一步；专业模式增加路径、commit、参数、stdout/stderr 和技术错误。

## 十二步流程

1. 环境检查：Python/打包运行时、资源、依赖、配置和工作区可写性。
2. 使用方式：严格区分 `simulated`、`external_reference`、`real_experiment`。
3. 实验计划：创建不可覆盖 revision、预期条件矩阵和安全清单。
4. 生成刺激：仅调用现有 P7；真实播放仍由外部设备完成。
5. 外部播放录音：按清单操作，程序不控制硬件。
6. 单次导入：TXT 或 WAV + sidecar + stimulus manifest；只读预检和 hash 配对后运行 P1/P2/P8。
7. 数据集 QC：显式登记样本，运行 P2-B；不把 CONT/REPOS/REASM 混合。
8. 比较：在 P2-B gate 后运行正式支持的 P4/P5/P6 阶段。
9. P9：P9-A 选 tone、P9-B 最小 tone 消融、P9-C 跨模式桥接；全部使用显式 scope/authority。
10. 冻结：P9-D 生成新 package revision，loader/self-check 后写 approval、报告和 hash 清单。
11. final-test：默认 sealed，一次性、不可逆；当前真实 authority 不完整，按钮保持禁用。
12. 报告/离线读取：冻结 package + 显式 input manifest + 新输出目录。

## Metadata 与重复类型

真实数据应按计划填写设备/配置、方向、session、repeat、reposition round、assembly、acquisition block、时间及时区、来源记录。`CONT` 是连续重复，`REPOS` 是重新定位，`REASM` 是重新装配；缺失一种不得以另一种替代。官方 REW 参考不得伪造这些实验身份。

## QC 与状态

`valid < warning < exclude_candidate` 是自动 QC 聚合优先级；`unavailable` 不等于 pass。manual review 和人工 `valid` 独立保存。UI 不自动删除数据、不翻转人工标志，也不替代 SpectrumData/MeasurementMeta/FeatureSet 和正式 manifest 的权威状态。

## P9 与 package

P9-A 只用 training/development，拒绝 final-test、hash 不匹配和缺失 P2-B/P4 authority。P9-B 必须引用 P9-A fold authority。P9-C 必须引用正式 P3-C 配对 authority，并保持 tone identity/order。模拟结果不可称为真实 tone set、真实性能或真实 calibration。

冻结后不能更改 tone、归一化、阈值、校准、模型或方向标签；变更必须创建新 revision。package manifest、semantic hash、文件 hash 和 loader self-check 必须同时通过。模拟 package 不具备科研或部署资格。

## 离线读取解释

只加载持久化 P8/P3-C/QC 输入，不重新训练、不读取原始 WAV/TXT、不扫描目录。valid/warning 可保留相应状态；blocked/invalid/unavailable 不生成预测。nearest-centroid score 越小越匹配；margin 是第二名减第一名的距离差，不是概率或置信概率。

## final-test 安全

解封前需冻结计划/package、hash/self-check、预登记 scope、已结束 training/development、保管人、独立批准人、含时区批准时间、一次性规则、空且唯一输出、版本一致、真实科研 authority、无未处理 incident 和已批准真实 Multisine 后端。任一失败都不打开文件、不读标签、不提供绕过；误访问写入 incident。DEV-UI4 测试只用模拟密封 fixture，从未读取真实 final-test。

## 数据备份与科研资格

对原始输入、sidecar/manifest、计划 revision、输出和 hash 清单做只读备份。模拟和官方参考只能做软件验证。只有完成 DEV-D、真实 provenance、P2-B/canonical gate、训练/开发冻结与独立 final-test 批准的 `real_experiment/research_analysis` 才可能形成科研结论；当前项目尚未达到该状态。

快速操作见 [快速入门](QUICKSTART_UI_ZH.md)，问题排查见 [故障排除](TROUBLESHOOTING_UI_ZH.md)。
