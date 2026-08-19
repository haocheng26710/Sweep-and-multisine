# FORMAL-2A：正式校准文件登记

状态：文件登记完成；iMM-6C 输入加载证据不足；`ready_for_B01=false`

日期：2026-08-19

分支：`feature/v2-dual-input`

## 本轮目标和边界

本轮只登记正式采集包中的 `CMM29939.txt` 和 `REW_CMM29939_LOADED.png`，验证文件内容/hash，并审查截图能否证明该校准已加载到 iMM-6C 正式采集输入设备。

没有修改校准文件字节，没有启动 REW、设备或正式测量，没有采集、导入或分析数据，没有读取 pilot/final-test，也没有改变协议、96 样本矩阵、频率网格、科研阈值或其他门禁。

## 检查对象

正式根目录：

```text
D:\Bristol course\dissertation\formal_experiment_data\FORMAL-U4-4DIR-SWEEP-REV001\
```

检查对象：

- `01_calibration/CMM29939.txt`
- `01_calibration/REW_CMM29939_LOADED.png`

登记时间：`2026-08-19T19:38:46.392456+01:00`

## 校准文件登记结果

| 字段 | 结果 |
|---|---|
| filename | `CMM29939.txt` |
| bytes | `3205` |
| SHA-256 | `421070ec6d41c1b92cb69f0f5e4e290f9644847d92d52590994a80ea9e17a11e` |
| 数据行 | `256` |
| 频率范围 | `20–20000 Hz` |
| sensitivity header | `*1000Hz -36.2` |
| frequencies | finite、strictly increasing、unique |
| source path | `D:\Bristol course\dissertation\formal_experiment_data\FORMAL-U4-4DIR-SWEEP-REV001\01_calibration\CMM29939.txt` |
| copy path | 同上 |
| registration mode | `registered_in_place=true` |
| registration modified content | `false` |

FORMAL-2A 开始前读取的 SHA-256 与登记完成后 SHA-256 完全相同，证明登记过程未修改文件。

本轮能核实的来源只有正式目录内现存文件；原始复制前路径没有伴随证据，因此没有猜测或伪造另一个 source path。登记明确把当前正式副本同时记录为本次检查 source/copy，并标记 `registered_in_place=true`。

## 截图证据审核

截图：`REW_CMM29939_LOADED.png`

- bytes：`430556`
- SHA-256：`c329c2f3f018408fe807a939c3e857d6b38b5dbc46e9b3aee4959330dc02c673`
- 格式：PNG

可见证据：

1. REW Preferences 的 Soundcard 页面显示 sample rate 为 48 kHz。
2. Input device 显示“麦克风 (iMM-6C)”。
3. 页面可见 `CMM29939.txt`。
4. 但该文件显示在 **Soundcard calibration** 区域，紧邻文字为“扬声器 (iMM-6C) SPEAKER at 48 kHz”。
5. 截图没有显示 `Cal files` 页，也没有显示把 `CMM29939.txt` 明确绑定到 microphone/input calibration 的证据。

因此截图不能证明 `CMM29939.txt` 已为 iMM-6C 正式采集输入通道正确加载。审核状态固定为：

```text
insufficient_input_binding_evidence
```

正式登记把 intended device 记录为 `iMM-6C`、role 记录为 `formal_acquisition_input`，但 binding status 为 `pending_evidence`，没有把配置意图冒充 REW 已生效证据。

## blocker 状态变化

文件存在、格式和 hash 均有效，因此移除与事实不符的：

- `calibration_file_missing`

截图不足以证明输入绑定，因此保留：

- `calibration_load_evidence_missing`

其他 FORMAL-2 blocker 原样保留。当前准确列表：

- `B01_manual_authorization_missing`
- `backup_restore_drill_not_completed`
- `calibration_load_evidence_missing`
- `environment_record_incomplete`
- `external_backup_not_configured`
- `geometry_record_incomplete`
- `preflight_manual_checks_incomplete`
- `protocol_signatures_missing`

`external_backup_not_configured` 没有被校准登记改变。`ready_for_B01=false`。

## 新增外置登记证据与 hash

新增：

- `01_calibration/calibration_registration.json`
- `00_protocol_and_manifests/preflight_status_history/FORMAL_2_PREFLIGHT_STATUS.json`
- `07_hashes/history/FORMAL_2_BASELINE_SHA256SUMS.json`
- `07_hashes/history/FORMAL_2_BASELINE_SHA256SUMS.txt`

FORMAL-2 原始 preflight/hash 基线被归档，没有删除或改写旧失败证据。当前 `SHA256SUMS.json` 列出 19 个非循环 artifacts，实际复核为 19/19 匹配。

关键 hash：

| Artifact | SHA-256 |
|---|---|
| `CMM29939.txt` | `421070ec6d41c1b92cb69f0f5e4e290f9644847d92d52590994a80ea9e17a11e` |
| `REW_CMM29939_LOADED.png` | `c329c2f3f018408fe807a939c3e857d6b38b5dbc46e9b3aee4959330dc02c673` |
| `calibration_registration.json` | `c0d8caec5d09ddaae2b15e8b544549aeae6a651b83cff585ffeb329e64e6460d` |
| current `SHA256SUMS.json` | `2e8b06da78c22f723bde4e06f999bff41e0386c90b331a2ac316c40a7e209b15` |
| current `SHA256SUMS.txt` | `629a461a904b21f48f596e101d9e0b228a9691ecc2dcd89e86d40b5c63b65ae8` |

## 实现与测试

新增公开登记入口验证：

- copy path 和 screenshot path 必须位于正式 calibration 目录；
- input device 必须为 `iMM-6C`；
- calibration source/copy SHA-256 必须一致；
- 文件必须包含 `*1000Hz` header、至少 5 行有限且严格递增的数据；
- screenshot 必须为 PNG；
- evidence assessment、assessor 和 observations 必须显式提供；
- 只有 `verified_input_binding` 才移除 load-evidence blocker；
- 任何格式/路径/hash/final-test/measurement-state 不一致均 fail closed；
- 更新前归档 FORMAL-2 基线，更新后复核整个包 hash；
- registration 完成后再次验证 calibration hash 未改变。

命令入口：

```powershell
python scripts/register_formal_calibration.py --root <formal-root> --checked-at <ISO8601> --assessed-by <name> --evidence-status <status> --observation <text>
```

实际相关测试：

```powershell
python -m pytest -q tests/test_formal_calibration_registration.py tests/test_formal_acquisition.py
```

结果：`11 passed in 0.43s`，退出码 0。

全量：

```powershell
python -m pytest -q
```

结果：`881 passed in 233.81s (0:03:53)`，退出码 0。

提交前另执行 `python -m compileall -q src scripts` 和 `git diff --check`，准确结果记录在最终回复。

## 修改文件

- `src/acoustic_encoder/formal_acquisition.py`
- `scripts/register_formal_calibration.py`
- `tests/test_formal_calibration_registration.py`
- `docs/progress/FORMAL_2A_CALIBRATION_REGISTRATION.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`

外置正式数据目录和其中证据不纳入 Git。未修改 `CMM29939.txt`、科研算法、schema、config、UI、冻结协议/计划或任何测量数据。

## 下一步门槛

需要一张能够明确显示 microphone/input calibration binding 的新证据，例如 REW `Cal files` 页或其他明确列出 iMM-6C input 与 `CMM29939.txt` 关联的界面。新证据必须另存、hash 并追加审核，不得删除本次不足证据。

即使未来该项通过，外置备份、restore drill、几何/环境记录、人工 preflight、协议签名和 B01 人工批准仍未完成。正式测量不得开始；`formal_measurement_started=false`、`final_test_read=false`、`scientifically_eligible=false`。
