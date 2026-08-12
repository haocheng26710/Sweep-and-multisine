# 桌面向导快速入门

## 1. 启动

源码版：

```powershell
python scripts/run_gui.py
```

安装/解压版：运行 `SweepMultisineUI.exe`。首次启动使用 `%LOCALAPPDATA%\SweepMultisineUI\workspace`，也可在源码版或打包版使用 `--workspace "D:\含空格\中文 工作区"` 指定。界面顶部始终显示当前实际工作区；安装目录只存放只读资源。

## 1.1 更换工作区

简易模式和专业模式的窗口顶部均有“更换工作区”。选择可创建、可写的文件夹后，界面会明确标记“下次启动生效”；当前窗口及其后端仍使用顶部显示的原工作区，不会出现界面与输出路径不一致。可点击“立即重启”，也可稍后手动重启。

工作区优先级固定为：命令行 `--workspace` > 用户保存的工作区 > `%LOCALAPPDATA%\SweepMultisineUI\workspace`。取消选择不会改变设置；旧工作区数据不会被移动、复制或删除。任务运行期间切换和立即重启均被阻止，请先等待任务完成或取消任务。

## 2. 完成一次安全的软件练习

1. 点击“检查软件环境”，确认配置与核心依赖可用。
2. 在“选择使用方式”中选择“模拟练习”；数据来源和用途由路线锁定，不能手工伪造。
3. 点击“运行模拟软件验收”。任务在后台执行，可取消，结果不会覆盖旧目录。
4. 验收结束后打开结果目录和报告；`software_integration_ready` 只代表软件集成通过，不代表科研资格。
5. 在“导入并检查单次数据”中选择模拟 WAV、明确 sidecar/manifest，完成只读预检、metadata 登记和单次运行。

## 3. 导入官方 REW TXT

选择“官方 REW 参考”路线，再选择一个官方导出的频响 TXT。官方样例固定标记为 `external_reference/software_validation`，不得填写 angle、configuration、session 或 repeat 身份，也不能用于科研结论。

## 4. P9、冻结和离线读取

P9-A/B/C 只接受用户显式选择的 scope/input/authority，不扫描目录。P9-D 只用 training/development manifest 创建新的、不可覆盖的 package revision。模拟 package 始终是 `software_validation_only`、`scientifically_eligible=false`、`deployment_allowed=false`。

离线读取必须选择已通过 loader/self-check 的 frozen package、显式 input manifest 和尚不存在的输出目录。nearest-centroid score 越小越匹配；margin 是第二名与第一名的距离差，不是概率。

## 5. 真实实验下一步

请进入 [真实实验接入清单](experiment/DEV_D_REAL_EXPERIMENT_ENTRY_CHECKLIST.md)。当前真实 Multisine/P8 和依赖它的真实 P9-C/final-test 仍硬阻塞；DEV-C16 ready 不等于真实 Multisine 已获准。
