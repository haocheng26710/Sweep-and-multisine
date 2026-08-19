# FORMAL-2A-FIX：iMM-6C 麦克风输入校准加载证据

状态：证据有效、输入绑定已验证；采集前门禁仍阻塞，`ready_for_B01=false`

日期：2026-08-19

分支：`feature/v2-dual-input`

## 目标与边界

本轮补充核验 REW 对 iMM-6C **测量输入**加载 `CMM29939.txt` 的直接界面证据，修正 FORMAL-2A 只能证明 Soundcard/output calibration、不能证明 microphone/input binding 的证据缺口。

本轮没有修改 `CMM29939.txt`，没有删除或改写 FORMAL-2A 的不足证据，没有启动 REW、外部设备或正式测量，没有采集、导入或分析数据，也没有读取 final-test。研究问题、正式协议、96 样本矩阵、采集顺序、算法、科学判定门槛和备份门禁均未改变。

## 检查对象与视觉判定

正式根目录：

```text
D:\Bristol course\dissertation\formal_experiment_data\FORMAL-U4-4DIR-SWEEP-REV001\
```

检查对象：

- `01_calibration/CMM29939.txt`
- 用户上传文件 `01_calibration/REW_CMM29939_MIC_INPUT_LOADED.png.png`
- 规范登记副本 `01_calibration/REW_CMM29939_MIC_INPUT_LOADED.png`

检查时间：`2026-08-19T19:54:31.670325+01:00`

视觉核验同时满足三项硬条件：

1. REW Measurement 窗口显示测量输入为 `MICROPHONE`，设备名称包含 `iMM-6C`；
2. REW Calibration data 窗口的独立 `Mic calibration files` 区域显示麦克风 `iMM-6C`，并列出 `CMM29939.txt`；
3. 截图同时存在单独的 `Soundcard calibration` 区域，但本次结论只依据上述 `Mic calibration files` 和测量输入信息，没有把 Soundcard/output 区域冒充麦克风校准证据。

因此正式采集输入设备绑定状态由 `pending_evidence` 更新为：

```text
verified
```

## 文件与 SHA-256

| Artifact | bytes | SHA-256 | 处理 |
|---|---:|---|---|
| `CMM29939.txt` | 3,205 | `421070ec6d41c1b92cb69f0f5e4e290f9644847d92d52590994a80ea9e17a11e` | 只读复核，未修改 |
| `REW_CMM29939_MIC_INPUT_LOADED.png.png` | 266,145 | `5811b17a882bc8000e9746b172b007616aada9f8786e1f4b9b96b6fed353b9ba` | 保留原上传文件 |
| `REW_CMM29939_MIC_INPUT_LOADED.png` | 266,145 | `5811b17a882bc8000e9746b172b007616aada9f8786e1f4b9b96b6fed353b9ba` | 新增字节相同的规范名称副本 |

上传文件实际带有双 `.png` 扩展名。为同时满足不可破坏原证据和规范路径要求，登记过程没有重命名、覆盖或删除它，而是创建字节完全相同的单扩展副本。两份截图 hash 相同。

`CMM29939.txt` 的 SHA-256 与 FORMAL-2A 登记值一致，证明本轮没有改变其内容；`calibration_file_missing` 继续保持已清除。

## 审计记录和 blocker 变化

新增或更新的外置采集包 artifact：

- `01_calibration/calibration_input_evidence_fix.json`
- `01_calibration/REW_CMM29939_MIC_INPUT_LOADED.png`
- `00_protocol_and_manifests/preflight_status.json`
- `00_protocol_and_manifests/preflight_status_history/FORMAL_2A_PREFLIGHT_STATUS.json`
- `07_hashes/history/FORMAL_2A_SHA256SUMS.json`
- `07_hashes/history/FORMAL_2A_SHA256SUMS.txt`
- `07_hashes/SHA256SUMS.json`
- `07_hashes/SHA256SUMS.txt`

FORMAL-2A 的旧截图、`calibration_registration.json`、旧状态和旧 hash 均保留。当前包级清单列出 25 个非循环 artifact，独立复核为 `25/25` 存在且 SHA-256 匹配。

本轮只移除：

- `calibration_load_evidence_missing`

当前仍未解决的 blocker：

- `B01_manual_authorization_missing`
- `backup_restore_drill_not_completed`
- `environment_record_incomplete`
- `external_backup_not_configured`
- `geometry_record_incomplete`
- `preflight_manual_checks_incomplete`
- `protocol_signatures_missing`

外置备份仍为 `not_configured`，没有虚构或自动签署任何人工检查项。状态保持：

- `ready_for_B01=false`
- `formal_measurement_started=false`
- `real_data_imported_or_analyzed=false`
- `final_test_read=false`
- `scientifically_eligible=false`

## 实现与 fail-closed 行为

新增公开登记入口 `supplement_formal_mic_input_evidence(...)` 和命令行脚本 `scripts/register_formal_mic_input_evidence.py`。入口要求三项视觉判断全部显式为 true；任一条件缺失时，在写入规范截图、证据记录或 preflight 状态前失败。

入口还会核验：

- 截图必须在正式包 `01_calibration` 中且为 PNG；
- `CMM29939.txt` 必须通过格式检查并与 FORMAL-2A 不可变登记 hash 一致；
- 已登记输入设备必须是 `iMM-6C`；
- `formal_measurement_started=false` 且 `final_test_read=false`；
- 已存在的规范截图或审计记录不得被不同内容覆盖；
- 更新前保存 FORMAL-2A 状态/hash 快照；
- 更新后刷新并逐项复核整个正式包 hash；
- 登记结束时再次确认校准文件和原上传截图 hash 未改变。

## 测试与验证

TDD RED：新增测试首先因缺少 `supplement_formal_mic_input_evidence` 公开接口而在 collection 阶段失败；没有把其他错误当作预期失败。

FORMAL-2/2A/FIX 联合专项：

```powershell
python -m pytest -q tests/test_formal_calibration_input_evidence_fix.py tests/test_formal_calibration_registration.py tests/test_formal_acquisition.py
```

结果：`13 passed in 0.64s`，退出码 0。

全量：

```powershell
python -m pytest -q
```

最终代码结果：`883 passed in 258.33s (0:04:18)`，退出码 0。

字节码检查：

```powershell
python -m compileall -q src scripts
```

结果：无输出，退出码 0。

差异检查：

```powershell
git diff --check
```

结果：无输出，退出码 0。文档最终修改后在提交前再次执行。

## 修改文件

Repository：

- `src/acoustic_encoder/formal_acquisition.py`
- `scripts/register_formal_mic_input_evidence.py`
- `tests/test_formal_calibration_input_evidence_fix.py`
- `docs/progress/FORMAL_2A_FIX_MIC_INPUT_EVIDENCE.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`

外置正式采集包不进入 Git。没有修改科研算法、冻结协议、96 样本矩阵、配置、UI、final-test 或任何测量数据。

## 下一步门槛

校准文件和 iMM-6C 麦克风输入加载证据现已满足，但这不等于 B01 获准。必须另外完成独立外置备份及恢复演练、几何和环境记录、人工 preflight、协议签名和 B01 人工授权，才能重新评估 `ready_for_B01`。

本轮结束时正式测量仍被禁止，不能从采集基础设施证据推导任何科研结论。
