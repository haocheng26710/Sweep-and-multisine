# 正式 Sweep 采集计划 rev-001

计划 ID：`FORMAL-U4-4DIR-SWEEP-REV001`

协议 authority：[`RESEARCH_PROTOCOL_REV002.md`](./RESEARCH_PROTOCOL_REV002.md)

冻结日期：2026-08-19（Europe/London）

状态：预注册冻结；尚未开始真实采集

## 1. 计划目的与角色

本计划为 U4SYM/U4ENC 四方向确认性 formal pilot 预注册 96 个 REW Sweep。它不包含八方向、Multisine/P8 或 final-test。

- `measurement_mode=rew_sweep`
- `data_origin=real_experiment`：仅采集发生且 provenance 完整后使用
- `dataset_role=development`
- `experiment_role=formal_pilot`
- 初始 `eligible_for_scientific_analysis=false`
- `final_test_read=false`

现有预实验文件全部属于 `diagnostic_pilot`，不得移动、复制、重命名或重新标记到本计划目录，也不得进入本计划的 measurement index、P2-B scope 或 95% CI。

## 2. 冻结设备和 REW 参数

使用 REW `V5.31.3`，Sweep，48 kHz，256k sweep length，repetitions=1，No timing reference，t=0=IR peak，capture 200–8000 Hz，sweep level -30 dBFS，Windows 输出 50，iMM-6C 输入 100，校准文件 `CMM29939.txt`。Windows 增强、AGC、EQ、空间音效全部关闭。

扬声器—装置中心距离目标约 0.8 m，但必须在采集前实测，以毫米或至少 1 mm 分辨率记录。音箱旋钮、开放通道、麦克风深度、结构高度及房间基准位置必须冻结、标尺复核并拍照。

## 3. 物理重复结构与 session/block

每个 configuration 有两个独立 assembly states；每个 assembly 在同一 session 内完成两轮 REPOS；每个 REPOS 固定状态按预注册方向顺序采集，每个方向连续执行三次 CONT。三次 CONT 期间不得触碰装置、麦克风、扬声器或增益。

| Session | Block | Configuration | REASM | REPOS | 方向顺序 | block 样本数 |
|---|---|---|---|---|---|---:|
| `S01` | `B01` | U4SYM | AS01 | RP01 | 0, 90, 180, 270 | 12 |
| `S01` | `B02` | U4SYM | AS01 | RP02 | 180, 270, 0, 90 | 12 |
| `S02` | `B03` | U4ENC | AS01 | RP01 | 90, 180, 270, 0 | 12 |
| `S02` | `B04` | U4ENC | AS01 | RP02 | 270, 0, 90, 180 | 12 |
| `S03` | `B05` | U4ENC | AS02 | RP01 | 270, 180, 90, 0 | 12 |
| `S03` | `B06` | U4ENC | AS02 | RP02 | 90, 0, 270, 180 | 12 |
| `S04` | `B07` | U4SYM | AS02 | RP01 | 180, 90, 0, 270 | 12 |
| `S04` | `B08` | U4SYM | AS02 | RP02 | 0, 270, 180, 90 | 12 |

该顺序是预注册的平衡顺序：配置在整体前后半段对称安排；每个方向在八个 block 的第 1–4 个位置各出现两次。不得先看频谱结果再改变顺序。若客观原因必须暂停，只能在完整 block 边界暂停；中途停止须记录 deviation，剩余计划行的身份和相对顺序不得改变。

## 4. 96 样本完整预注册条件矩阵

`CONT` 列是同一固定状态下的连续技术重复编号。每一行 `expected_count=1`；总计 96。`role` 始终为 `development/formal_pilot`。

| sequence | sample_id | configuration | direction_deg | CONT | REPOS | REASM | session | block | role |
|---:|---|---|---:|---|---|---|---|---|---|
| 001 | `F002-SWEEP-U4SYM-D000-AS01-RP01-C01-S01-B01` | U4SYM | 0 | C01 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 002 | `F002-SWEEP-U4SYM-D000-AS01-RP01-C02-S01-B01` | U4SYM | 0 | C02 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 003 | `F002-SWEEP-U4SYM-D000-AS01-RP01-C03-S01-B01` | U4SYM | 0 | C03 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 004 | `F002-SWEEP-U4SYM-D090-AS01-RP01-C01-S01-B01` | U4SYM | 90 | C01 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 005 | `F002-SWEEP-U4SYM-D090-AS01-RP01-C02-S01-B01` | U4SYM | 90 | C02 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 006 | `F002-SWEEP-U4SYM-D090-AS01-RP01-C03-S01-B01` | U4SYM | 90 | C03 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 007 | `F002-SWEEP-U4SYM-D180-AS01-RP01-C01-S01-B01` | U4SYM | 180 | C01 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 008 | `F002-SWEEP-U4SYM-D180-AS01-RP01-C02-S01-B01` | U4SYM | 180 | C02 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 009 | `F002-SWEEP-U4SYM-D180-AS01-RP01-C03-S01-B01` | U4SYM | 180 | C03 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 010 | `F002-SWEEP-U4SYM-D270-AS01-RP01-C01-S01-B01` | U4SYM | 270 | C01 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 011 | `F002-SWEEP-U4SYM-D270-AS01-RP01-C02-S01-B01` | U4SYM | 270 | C02 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 012 | `F002-SWEEP-U4SYM-D270-AS01-RP01-C03-S01-B01` | U4SYM | 270 | C03 | RP01 | AS01 | S01 | B01 | development/formal_pilot |
| 013 | `F002-SWEEP-U4SYM-D180-AS01-RP02-C01-S01-B02` | U4SYM | 180 | C01 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 014 | `F002-SWEEP-U4SYM-D180-AS01-RP02-C02-S01-B02` | U4SYM | 180 | C02 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 015 | `F002-SWEEP-U4SYM-D180-AS01-RP02-C03-S01-B02` | U4SYM | 180 | C03 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 016 | `F002-SWEEP-U4SYM-D270-AS01-RP02-C01-S01-B02` | U4SYM | 270 | C01 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 017 | `F002-SWEEP-U4SYM-D270-AS01-RP02-C02-S01-B02` | U4SYM | 270 | C02 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 018 | `F002-SWEEP-U4SYM-D270-AS01-RP02-C03-S01-B02` | U4SYM | 270 | C03 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 019 | `F002-SWEEP-U4SYM-D000-AS01-RP02-C01-S01-B02` | U4SYM | 0 | C01 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 020 | `F002-SWEEP-U4SYM-D000-AS01-RP02-C02-S01-B02` | U4SYM | 0 | C02 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 021 | `F002-SWEEP-U4SYM-D000-AS01-RP02-C03-S01-B02` | U4SYM | 0 | C03 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 022 | `F002-SWEEP-U4SYM-D090-AS01-RP02-C01-S01-B02` | U4SYM | 90 | C01 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 023 | `F002-SWEEP-U4SYM-D090-AS01-RP02-C02-S01-B02` | U4SYM | 90 | C02 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 024 | `F002-SWEEP-U4SYM-D090-AS01-RP02-C03-S01-B02` | U4SYM | 90 | C03 | RP02 | AS01 | S01 | B02 | development/formal_pilot |
| 025 | `F002-SWEEP-U4ENC-D090-AS01-RP01-C01-S02-B03` | U4ENC | 90 | C01 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 026 | `F002-SWEEP-U4ENC-D090-AS01-RP01-C02-S02-B03` | U4ENC | 90 | C02 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 027 | `F002-SWEEP-U4ENC-D090-AS01-RP01-C03-S02-B03` | U4ENC | 90 | C03 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 028 | `F002-SWEEP-U4ENC-D180-AS01-RP01-C01-S02-B03` | U4ENC | 180 | C01 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 029 | `F002-SWEEP-U4ENC-D180-AS01-RP01-C02-S02-B03` | U4ENC | 180 | C02 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 030 | `F002-SWEEP-U4ENC-D180-AS01-RP01-C03-S02-B03` | U4ENC | 180 | C03 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 031 | `F002-SWEEP-U4ENC-D270-AS01-RP01-C01-S02-B03` | U4ENC | 270 | C01 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 032 | `F002-SWEEP-U4ENC-D270-AS01-RP01-C02-S02-B03` | U4ENC | 270 | C02 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 033 | `F002-SWEEP-U4ENC-D270-AS01-RP01-C03-S02-B03` | U4ENC | 270 | C03 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 034 | `F002-SWEEP-U4ENC-D000-AS01-RP01-C01-S02-B03` | U4ENC | 0 | C01 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 035 | `F002-SWEEP-U4ENC-D000-AS01-RP01-C02-S02-B03` | U4ENC | 0 | C02 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 036 | `F002-SWEEP-U4ENC-D000-AS01-RP01-C03-S02-B03` | U4ENC | 0 | C03 | RP01 | AS01 | S02 | B03 | development/formal_pilot |
| 037 | `F002-SWEEP-U4ENC-D270-AS01-RP02-C01-S02-B04` | U4ENC | 270 | C01 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 038 | `F002-SWEEP-U4ENC-D270-AS01-RP02-C02-S02-B04` | U4ENC | 270 | C02 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 039 | `F002-SWEEP-U4ENC-D270-AS01-RP02-C03-S02-B04` | U4ENC | 270 | C03 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 040 | `F002-SWEEP-U4ENC-D000-AS01-RP02-C01-S02-B04` | U4ENC | 0 | C01 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 041 | `F002-SWEEP-U4ENC-D000-AS01-RP02-C02-S02-B04` | U4ENC | 0 | C02 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 042 | `F002-SWEEP-U4ENC-D000-AS01-RP02-C03-S02-B04` | U4ENC | 0 | C03 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 043 | `F002-SWEEP-U4ENC-D090-AS01-RP02-C01-S02-B04` | U4ENC | 90 | C01 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 044 | `F002-SWEEP-U4ENC-D090-AS01-RP02-C02-S02-B04` | U4ENC | 90 | C02 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 045 | `F002-SWEEP-U4ENC-D090-AS01-RP02-C03-S02-B04` | U4ENC | 90 | C03 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 046 | `F002-SWEEP-U4ENC-D180-AS01-RP02-C01-S02-B04` | U4ENC | 180 | C01 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 047 | `F002-SWEEP-U4ENC-D180-AS01-RP02-C02-S02-B04` | U4ENC | 180 | C02 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 048 | `F002-SWEEP-U4ENC-D180-AS01-RP02-C03-S02-B04` | U4ENC | 180 | C03 | RP02 | AS01 | S02 | B04 | development/formal_pilot |
| 049 | `F002-SWEEP-U4ENC-D270-AS02-RP01-C01-S03-B05` | U4ENC | 270 | C01 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 050 | `F002-SWEEP-U4ENC-D270-AS02-RP01-C02-S03-B05` | U4ENC | 270 | C02 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 051 | `F002-SWEEP-U4ENC-D270-AS02-RP01-C03-S03-B05` | U4ENC | 270 | C03 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 052 | `F002-SWEEP-U4ENC-D180-AS02-RP01-C01-S03-B05` | U4ENC | 180 | C01 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 053 | `F002-SWEEP-U4ENC-D180-AS02-RP01-C02-S03-B05` | U4ENC | 180 | C02 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 054 | `F002-SWEEP-U4ENC-D180-AS02-RP01-C03-S03-B05` | U4ENC | 180 | C03 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 055 | `F002-SWEEP-U4ENC-D090-AS02-RP01-C01-S03-B05` | U4ENC | 90 | C01 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 056 | `F002-SWEEP-U4ENC-D090-AS02-RP01-C02-S03-B05` | U4ENC | 90 | C02 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 057 | `F002-SWEEP-U4ENC-D090-AS02-RP01-C03-S03-B05` | U4ENC | 90 | C03 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 058 | `F002-SWEEP-U4ENC-D000-AS02-RP01-C01-S03-B05` | U4ENC | 0 | C01 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 059 | `F002-SWEEP-U4ENC-D000-AS02-RP01-C02-S03-B05` | U4ENC | 0 | C02 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 060 | `F002-SWEEP-U4ENC-D000-AS02-RP01-C03-S03-B05` | U4ENC | 0 | C03 | RP01 | AS02 | S03 | B05 | development/formal_pilot |
| 061 | `F002-SWEEP-U4ENC-D090-AS02-RP02-C01-S03-B06` | U4ENC | 90 | C01 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 062 | `F002-SWEEP-U4ENC-D090-AS02-RP02-C02-S03-B06` | U4ENC | 90 | C02 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 063 | `F002-SWEEP-U4ENC-D090-AS02-RP02-C03-S03-B06` | U4ENC | 90 | C03 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 064 | `F002-SWEEP-U4ENC-D000-AS02-RP02-C01-S03-B06` | U4ENC | 0 | C01 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 065 | `F002-SWEEP-U4ENC-D000-AS02-RP02-C02-S03-B06` | U4ENC | 0 | C02 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 066 | `F002-SWEEP-U4ENC-D000-AS02-RP02-C03-S03-B06` | U4ENC | 0 | C03 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 067 | `F002-SWEEP-U4ENC-D270-AS02-RP02-C01-S03-B06` | U4ENC | 270 | C01 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 068 | `F002-SWEEP-U4ENC-D270-AS02-RP02-C02-S03-B06` | U4ENC | 270 | C02 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 069 | `F002-SWEEP-U4ENC-D270-AS02-RP02-C03-S03-B06` | U4ENC | 270 | C03 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 070 | `F002-SWEEP-U4ENC-D180-AS02-RP02-C01-S03-B06` | U4ENC | 180 | C01 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 071 | `F002-SWEEP-U4ENC-D180-AS02-RP02-C02-S03-B06` | U4ENC | 180 | C02 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 072 | `F002-SWEEP-U4ENC-D180-AS02-RP02-C03-S03-B06` | U4ENC | 180 | C03 | RP02 | AS02 | S03 | B06 | development/formal_pilot |
| 073 | `F002-SWEEP-U4SYM-D180-AS02-RP01-C01-S04-B07` | U4SYM | 180 | C01 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 074 | `F002-SWEEP-U4SYM-D180-AS02-RP01-C02-S04-B07` | U4SYM | 180 | C02 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 075 | `F002-SWEEP-U4SYM-D180-AS02-RP01-C03-S04-B07` | U4SYM | 180 | C03 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 076 | `F002-SWEEP-U4SYM-D090-AS02-RP01-C01-S04-B07` | U4SYM | 90 | C01 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 077 | `F002-SWEEP-U4SYM-D090-AS02-RP01-C02-S04-B07` | U4SYM | 90 | C02 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 078 | `F002-SWEEP-U4SYM-D090-AS02-RP01-C03-S04-B07` | U4SYM | 90 | C03 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 079 | `F002-SWEEP-U4SYM-D000-AS02-RP01-C01-S04-B07` | U4SYM | 0 | C01 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 080 | `F002-SWEEP-U4SYM-D000-AS02-RP01-C02-S04-B07` | U4SYM | 0 | C02 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 081 | `F002-SWEEP-U4SYM-D000-AS02-RP01-C03-S04-B07` | U4SYM | 0 | C03 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 082 | `F002-SWEEP-U4SYM-D270-AS02-RP01-C01-S04-B07` | U4SYM | 270 | C01 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 083 | `F002-SWEEP-U4SYM-D270-AS02-RP01-C02-S04-B07` | U4SYM | 270 | C02 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 084 | `F002-SWEEP-U4SYM-D270-AS02-RP01-C03-S04-B07` | U4SYM | 270 | C03 | RP01 | AS02 | S04 | B07 | development/formal_pilot |
| 085 | `F002-SWEEP-U4SYM-D000-AS02-RP02-C01-S04-B08` | U4SYM | 0 | C01 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 086 | `F002-SWEEP-U4SYM-D000-AS02-RP02-C02-S04-B08` | U4SYM | 0 | C02 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 087 | `F002-SWEEP-U4SYM-D000-AS02-RP02-C03-S04-B08` | U4SYM | 0 | C03 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 088 | `F002-SWEEP-U4SYM-D270-AS02-RP02-C01-S04-B08` | U4SYM | 270 | C01 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 089 | `F002-SWEEP-U4SYM-D270-AS02-RP02-C02-S04-B08` | U4SYM | 270 | C02 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 090 | `F002-SWEEP-U4SYM-D270-AS02-RP02-C03-S04-B08` | U4SYM | 270 | C03 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 091 | `F002-SWEEP-U4SYM-D180-AS02-RP02-C01-S04-B08` | U4SYM | 180 | C01 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 092 | `F002-SWEEP-U4SYM-D180-AS02-RP02-C02-S04-B08` | U4SYM | 180 | C02 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 093 | `F002-SWEEP-U4SYM-D180-AS02-RP02-C03-S04-B08` | U4SYM | 180 | C03 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 094 | `F002-SWEEP-U4SYM-D090-AS02-RP02-C01-S04-B08` | U4SYM | 90 | C01 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 095 | `F002-SWEEP-U4SYM-D090-AS02-RP02-C02-S04-B08` | U4SYM | 90 | C02 | RP02 | AS02 | S04 | B08 | development/formal_pilot |
| 096 | `F002-SWEEP-U4SYM-D090-AS02-RP02-C03-S04-B08` | U4SYM | 90 | C03 | RP02 | AS02 | S04 | B08 | development/formal_pilot |

矩阵行是唯一计划身份来源。不得从文件存在情况反推预期条件，不得从文件名猜 metadata。采集顺序只按 `sequence`；失败或停止的行仍保留，复测使用新 suffix 和 deviation record，不能替换原行。

## 5. 正式文件命名规则

基础 sample ID 与矩阵完全一致：

`F002-SWEEP-{CONFIG}-D{DEG3}-{REASM}-{REPOS}-C{CONT2}-{SESSION}-{BLOCK}`

示例：`F002-SWEEP-U4ENC-D090-AS01-RP02-C03-S02-B04`。

文件名仅是已登记 metadata 的可读副本，不是身份 authority：

- REW 原始项目：`<sample_id>.mdat`
- REW Frequency Response TXT：`<sample_id>_FR.txt`
- 采集 sidecar：`<sample_id>.metadata.json`
- 现场 QC 截图（若有）：`<sample_id>_QC.png`

禁止覆盖或事后重命名。若复测，使用 `<sample_id>-RETAKE01`，sidecar 必须引用原 sample ID、停止/偏差记录和批准人；原文件保持不变。

## 6. 保存目录与硬隔离

正式主数据根目录固定为项目代码目录之外：

`D:\Bristol course\dissertation\formal_experiment_data\FORMAL-U4-4DIR-SWEEP-REV001\`

目录结构：

```text
FORMAL-U4-4DIR-SWEEP-REV001/
  00_protocol_and_manifests/
  01_calibration/CMM29939.txt
  02_photos_and_geometry/
  03_environment_logs/
  04_raw_rew_mdat/S01...S04/
  05_exported_rew_txt/S01...S04/
  06_metadata_sidecars/S01...S04/
  07_hashes/
  08_deviations_and_manual_review/
```

现有 pilot 数据保留在其原 diagnostic 位置，禁止放入上述根目录。分析输出使用独立的新 run-id，禁止写入 `04_raw_rew_mdat`、`05_exported_rew_txt` 或 sidecar 目录。

## 7. SHA-256、校准、照片和环境记录

每个 sample 完成后、进入下一 block 前：

1. 计算 `.mdat`、`_FR.txt` 和 sidecar 的 SHA-256；写入 append-only block manifest。
2. 验证 TXT 与 sidecar sample ID、configuration、direction、CONT/REPOS/REASM、session、block 一致。
3. `CMM29939.txt` 在首次采集前复制到只读 calibration 目录并记录原始来源、复制时间、SHA-256 和 REW 实际加载证据；全批次 hash 必须不变。
4. 每个 session 开始和结束拍摄几何总览、距离标尺、扬声器旋钮、开放通道、麦克风深度、结构高度和 Windows/REW 设置；每张照片记录 SHA-256。
5. 每个 block 记录开始/结束时间、操作者、温度、相对湿度、背景噪声观察、异常声源、实测距离和设备/音量/DSP 核对结果。
6. 主存储写入后立即复制到两个独立备份位置 A/B；至少一个备份必须在不同物理介质。逐文件 hash 必须与主存储一致。

备份 A/B 的绝对路径、介质序列号、负责人和首次 restore drill 结果必须在批准表中填写；任一项为空或 hash 不符时不得继续下一 block。

## 8. 现场执行顺序

1. 完成 rev-002、计划、人员和安全签署；确认 final-test sealed。
2. 建立空白正式目录，保存协议/config/software/environment snapshots 和 hashes。
3. 复制并验证 `CMM29939.txt`，拍摄初始设备链和几何照片。
4. 低电平链路检查；确认无 clipping、异常噪声或 DSP。
5. 严格按 B01→B08 和矩阵 `sequence` 执行；每个方向三次 CONT 连续完成。
6. 每个 block 结束后完成 hash、metadata、环境记录和双备份核对，未通过不得进入下一 block。
7. B08 后对 96 行做 expected/present、duplicate/unexpected 和 hash 审计；不读取频谱结论来决定补测。
8. 只有完整性、P1/P2 QC 和人工 review 门禁通过后，才可建立显式 formal-pilot analysis scope；final-test 仍 sealed。

## 9. 停止与恢复

以下任一情况立即停止：削波/REW input clipping；设备、音量或 DSP 改变；几何位置意外移动；持续异常环境噪声；校准文件失效；metadata、文件、照片、环境记录、hash 或备份缺失；任一冻结 REW 参数不一致。

恢复必须：

- 保留全部失败/部分文件和 traceback/现场记录；
- 新建 deviation ID，说明原因、受影响样本和处置；
- 重新执行设备、几何、校准、存储和安全门禁；
- 由采集负责人和数据保管人签字；
- 从完整 block 边界恢复，或把不完整 block 全部标为 deviation 后按新 block ID 重采；不得覆盖原 block。

## 10. 采集前人工批准

| Gate | 决定 | 审批人 | 日期/时间 | 证据/备注 |
|---|---|---|---|---|
| rev-002 唯一修订已理解 | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |
| 96 行 identity/order 已冻结 | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |
| 设备/几何/REW 参数已实测复核 | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |
| calibration hash/加载证据有效 | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |
| 双备份路径和 restore drill 通过 | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |
| diagnostic pilot 隔离通过 | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |
| final-test sealed | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `final_test_read=false` |
| 允许开始 B01 | `<批准/拒绝>` | `<待填写>` | `<待填写>` | `<待填写>` |

全部 gate 必须明确批准；软件验证、SIM-1 或本文档提交不能替代人工签署。
