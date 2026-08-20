"""FORMAL-5 synthesis of immutable FORMAL-3 and FORMAL-4 authorities."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import shutil
import statistics
from typing import Any, Mapping

from .schemas import artifact_sha256
from .formal_core_analysis import verify_formal3_authority, verify_formal4_output_hashes


FORMAL5_SCHEMA_VERSION = "formal5_final_synthesis_v1"
FORMAL3_ZIP_SHA256 = (
    "cfbaa7a3c300b8443d934462386e9a5faad74d2b2cf0a50292d8c08423f7b4cb"
)


class Formal5InputError(ValueError):
    """Raised when a frozen authority or synthesis invariant fails."""


@dataclass(frozen=True, slots=True)
class Formal5RunResult:
    output_directory: Path
    disposition: str
    artifact_count: int


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Formal5InputError(f"cannot read JSON authority: {path}") from exc
    if not isinstance(payload, dict):
        raise Formal5InputError(f"JSON authority must be an object: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise Formal5InputError(f"cannot read CSV authority: {path}") from exc


_EXPECTED_NUMBERS = {
    "repeatability median": 0.3782942415603068,
    "repeatability IQR": 0.2190678991596497,
    "repeatability p95": 0.8792543414488713,
    "U4ENC G_demeaned": 1.2805414340255579,
    "U4ENC CI lower": 0.829727543676017,
    "U4ENC CI upper": 1.766654301499613,
    "U4SYM G_demeaned": 0.6823847630714056,
    "U4SYM CI lower": 0.6105373373858028,
    "U4SYM CI upper": 1.2699369797033497,
    "delta G_demeaned": 0.5981566709541523,
    "delta CI lower": -0.11310886268350098,
    "delta CI upper": 1.0842695384282073,
    "AS01 configuration effect/floor": 1.5687667558448029,
    "U4SYM balanced accuracy": 0.375,
    "U4SYM macro F1": 0.25,
    "U4ENC balanced accuracy": 0.25,
    "U4ENC macro F1": 0.18333333333333335,
}


def _require_equal(label: str, observed: Any, expected: Any) -> None:
    if isinstance(expected, float):
        try:
            matches = math.isclose(float(observed), expected, rel_tol=0.0, abs_tol=1e-12)
        except (TypeError, ValueError):
            matches = False
    else:
        matches = observed == expected
    if not matches:
        raise Formal5InputError(
            f"frozen {label} mismatch: expected {expected!r}, found {observed!r}"
        )


def evaluate_frozen_evidence(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Validate frozen FORMAL-4 evidence and return the bounded FORMAL-5 decision."""
    _require_equal("ready_for_formal_synthesis", summary.get("ready_for_formal_synthesis"), True)
    _require_equal("final_test_read", summary.get("final_test_read"), False)
    selection = summary.get("selection", {})
    authority = summary.get("input_authority", {})
    provenance = summary.get("provenance", {})
    _require_equal("ACTIVE count", selection.get("active_count"), 72)
    _require_equal("EXCLUDED count", selection.get("excluded_count"), 19)
    _require_equal("selection changed", selection.get("active_or_excluded_decision_changed"), False)
    _require_equal("EXCLUDED entered analysis", selection.get("excluded_entered_analysis"), False)
    _require_equal("ZIP SHA-256", authority.get("zip_sha256"), FORMAL3_ZIP_SHA256)
    _require_equal("data_origin", provenance.get("data_origin"), "real_experiment")
    _require_equal("dataset_role", provenance.get("dataset_role"), "research_analysis")
    _require_equal("run_purpose", provenance.get("run_purpose"), "research_analysis")
    _require_equal("scientifically_eligible", provenance.get("scientifically_eligible"), False)

    floor = summary["repeatability_floor"]["primary_band"]
    gain = summary["direction_effect"]["G_demeaned_AS01_primary"]
    configuration = summary["configuration_effect"]
    classification = summary["classification"]
    observed_numbers = {
        "repeatability median": floor["median_db"],
        "repeatability IQR": floor["iqr_db"],
        "repeatability p95": floor["p95_db"],
        "U4ENC G_demeaned": gain["U4ENC"],
        "U4ENC CI lower": gain["U4ENC_ci95"][0],
        "U4ENC CI upper": gain["U4ENC_ci95"][1],
        "U4SYM G_demeaned": gain["U4SYM"],
        "U4SYM CI lower": gain["U4SYM_ci95"][0],
        "U4SYM CI upper": gain["U4SYM_ci95"][1],
        "delta G_demeaned": gain["U4ENC_minus_U4SYM"],
        "delta CI lower": gain["U4ENC_minus_U4SYM_ci95"][0],
        "delta CI upper": gain["U4ENC_minus_U4SYM_ci95"][1],
        "AS01 configuration effect/floor": configuration["AS01_median_demeaned_to_floor_ratio"],
        "U4SYM balanced accuracy": classification["U4SYM_AS01"]["balanced_accuracy"],
        "U4SYM macro F1": classification["U4SYM_AS01"]["macro_f1"],
        "U4ENC balanced accuracy": classification["U4ENC_AS01"]["balanced_accuracy"],
        "U4ENC macro F1": classification["U4ENC_AS01"]["macro_f1"],
    }
    for label, expected in _EXPECTED_NUMBERS.items():
        _require_equal(label, observed_numbers[label], expected)

    pairs = summary["direction_effect"][
        "reliable_primary_pairs_exceed_CONT_p95_in_both_AS01_REPOS_blocks"
    ]
    _require_equal("U4ENC reliable direction pair count", len(pairs["U4ENC"]), 6)
    _require_equal("U4SYM reliable direction pair count", len(pairs["U4SYM"]), 3)
    outliers = summary["outlier_policy"]
    _require_equal("outlier flag count", outliers.get("flagged_active_count"), 10)
    _require_equal("outlier selection mutation", outliers.get("active_manifest_modified"), False)
    _require_equal(
        "outlier threshold conclusion change",
        outliers.get("any_frozen_threshold_conclusion_changed"),
        False,
    )
    assembly = summary["assembly_set_effect"]
    _require_equal("AS02 causal conclusion", assembly.get("strong_causal_conclusion_allowed"), False)

    return {
        "disposition": "supported_with_limits",
        "hypothesis_decisions": {"H0": "not_rejected", "H1": "not_confirmed"},
        "question_decisions": {
            "RQ1": "supported",
            "RQ2": "partially_supported",
            "RQ3": "supported_with_limits",
            "RQ4": "not_supported",
            "RQ5": "exploratory_only",
            "RQ6": "bounded_results_and_exploratory_observations_separated",
            "RQ7": "continue_dissertation_without_required_redesign",
        },
        "scientifically_eligible": False,
        "final_test_read": False,
    }


def _one_row(
    tables: Mapping[str, list[dict[str, str]]], filename: str, **criteria: str
) -> dict[str, str]:
    matches = [
        row for row in tables.get(filename, [])
        if all(row.get(field) == value for field, value in criteria.items())
    ]
    if len(matches) != 1:
        raise Formal5InputError(
            f"expected exactly one {filename} row for {criteria}, found {len(matches)}"
        )
    return matches[0]


def validate_formal4_numeric_trace(
    summary: Mapping[str, Any], tables: Mapping[str, list[dict[str, str]]]
) -> None:
    """Require every headline number to agree with its authoritative FORMAL-4 CSV."""
    evaluate_frozen_evidence(summary)
    floor = _one_row(tables, "repeatability_summary.csv", band_id="primary")
    _require_equal("repeatability median CSV", floor.get("median_pairwise_rms_db"), _EXPECTED_NUMBERS["repeatability median"])
    _require_equal("repeatability IQR CSV", floor.get("iqr_pairwise_rms_db"), _EXPECTED_NUMBERS["repeatability IQR"])
    _require_equal("repeatability p95 CSV", floor.get("p95_pairwise_rms_db"), _EXPECTED_NUMBERS["repeatability p95"])
    for configuration in ("U4SYM", "U4ENC"):
        row = _one_row(
            tables, "direction_gain_summary.csv", configuration=configuration,
            assembly_scope="AS01", band_id="primary", normalization="demeaned",
        )
        for field, label in (
            ("gain", f"{configuration} G_demeaned"),
            ("bootstrap_ci95_low", f"{configuration} CI lower"),
            ("bootstrap_ci95_high", f"{configuration} CI upper"),
        ):
            _require_equal(f"{label} CSV", row.get(field), _EXPECTED_NUMBERS[label])
    contrast = _one_row(
        tables, "direction_gain_contrasts.csv", assembly_scope="AS01",
        band_id="primary", normalization="demeaned",
    )
    _require_equal("delta G_demeaned CSV", contrast.get("u4enc_minus_u4sym_gain"), _EXPECTED_NUMBERS["delta G_demeaned"])
    _require_equal("delta CI lower CSV", contrast.get("bootstrap_ci95_low"), _EXPECTED_NUMBERS["delta CI lower"])
    _require_equal("delta CI upper CSV", contrast.get("bootstrap_ci95_high"), _EXPECTED_NUMBERS["delta CI upper"])
    config_rows = [
        row for row in tables.get("configuration_effects.csv", [])
        if row.get("assembly_id") == "AS01" and row.get("band_id") == "primary"
    ]
    if len(config_rows) != 4:
        raise Formal5InputError("expected four AS01 primary configuration-effect rows")
    median_ratio = statistics.median(
        float(row["configuration_to_repeatability_ratio"]) for row in config_rows
    )
    _require_equal("AS01 configuration effect/floor CSV", median_ratio, _EXPECTED_NUMBERS["AS01 configuration effect/floor"])
    for configuration in ("U4SYM", "U4ENC"):
        row = _one_row(tables, "grouped_validation_metrics.csv", scope_id=f"{configuration}_AS01")
        _require_equal(f"{configuration} balanced accuracy CSV", row.get("balanced_accuracy"), _EXPECTED_NUMBERS[f"{configuration} balanced accuracy"])
        _require_equal(f"{configuration} macro F1 CSV", row.get("macro_f1"), _EXPECTED_NUMBERS[f"{configuration} macro F1"])
    sensitivity = tables.get("outlier_sensitivity.csv", [])
    if not sensitivity:
        raise Formal5InputError("outlier sensitivity CSV is empty")
    for row in sensitivity:
        _require_equal("outlier flag count CSV", row.get("flagged_curve_count"), "10")
        _require_equal("outlier conclusion changed CSV", row.get("conclusion_changed_between_variants"), "false")
        _require_equal("outlier selection changed CSV", row.get("selection_manifest_changed"), "false")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _decision_rows() -> list[dict[str, str]]:
    return [
        {
            "hypothesis_id": "H0",
            "question": "方向差异是否不大于重复、重定位或重装配误差，且 U4ENC 不优于 U4SYM？",
            "frozen_rule": "若方向效应不超过误差且 U4ENC 不优于 U4SYM，则维持 H0。",
            "observed_result": "U4ENC 的 6/6 方向对超过两个 AS01 block 的 CONT p95；但 ΔG 的 95% CI 包含 0。",
            "decision": "not_rejected",
            "claim_strength": "inconclusive_confirmatory",
            "allowed_wording": "数据表明存在可测方向差异，但不足以拒绝完整 H0。",
            "prohibited_wording": "H0 已被拒绝；U4ENC 已被证明优于 U4SYM。",
        },
        {
            "hypothesis_id": "H1",
            "question": "U4ENC 方向效应是否大于误差并优于 U4SYM？",
            "frozen_rule": "U4ENC G_demeaned>1、U4ENC>U4SYM，且相应 95% CI 下限跨过 1/0 边界。",
            "observed_result": "点估计 1.2805 对 0.6824；U4ENC CI 下限 0.8297，ΔG=0.5982 的 CI 下限 -0.1131。",
            "decision": "not_confirmed",
            "claim_strength": "partial_support_only",
            "allowed_wording": "U4ENC 的方向性效应点估计更高，但确认性证据不足。",
            "prohibited_wording": "U4ENC 的方向性显著或已证实优于 U4SYM。",
        },
        {
            "hypothesis_id": "RQ1",
            "question": "方向变化是否产生超过重复测量误差底线的频谱变化？",
            "frozen_rule": "方向差异相对 CONT p95=0.8793 dB 判断。",
            "observed_result": "U4ENC 6/6、U4SYM 3/6 方向对在两个 AS01 blocks 中稳定超过底线。",
            "decision": "supported",
            "claim_strength": "bounded_measurement_evidence",
            "allowed_wording": "存在超过测量重复性底线的方向相关频谱变化。",
            "prohibited_wording": "所有方向均可可靠识别。",
        },
        {
            "hypothesis_id": "RQ2",
            "question": "U4ENC 是否比 U4SYM 表现出更强方向性？",
            "frozen_rule": "G 点估计、U4ENC CI 下限>1 且 ΔG CI 下限>0。",
            "observed_result": "点估计方向正确，但两个 CI 门槛均未完全通过。",
            "decision": "partially_supported",
            "claim_strength": "point_estimate_only",
            "allowed_wording": "U4ENC 的方向性点估计高于 U4SYM。",
            "prohibited_wording": "U4ENC 已证明具有更强方向性。",
        },
        {
            "hypothesis_id": "RQ3",
            "question": "U4ENC 与 U4SYM 是否具有可测配置差异？",
            "frozen_rule": "同方向配置效应应超过 CONT 重复性底线。",
            "observed_result": "AS01 四方向均超过底线，median effect/floor ratio=1.5688。",
            "decision": "supported_with_limits",
            "claim_strength": "block_aware_measurement_evidence",
            "allowed_wording": "AS01 中两种配置存在超过 CONT 底线的可测差异。",
            "prohibited_wording": "该配置差异必然导致可用方向分类。",
        },
        {
            "hypothesis_id": "RQ4",
            "question": "当前数据能否支持可靠方向分类？",
            "frozen_rule": "grouped balanced accuracy 至少 0.50。",
            "observed_result": "AS01 U4SYM=0.375，U4ENC=0.250，均低于目标。",
            "decision": "not_supported",
            "claim_strength": "negative_result",
            "allowed_wording": "当前 grouped validation 未支持稳定方向分类。",
            "prohibited_wording": "模型可以可靠识别方向。",
        },
        {
            "hypothesis_id": "RQ5",
            "question": "AS01 与 AS02 是否能无混杂独立比较？",
            "frozen_rule": "assembly 比较需与 block/time 独立。",
            "observed_result": "AS02 每种配置仅一个 block，assembly 与 block/time 混杂。",
            "decision": "exploratory_only",
            "claim_strength": "descriptive_observation",
            "allowed_wording": "AS02 结果仅为探索性观察。",
            "prohibited_wording": "差异由 assembly set 因果造成。",
        },
        {
            "hypothesis_id": "RQ6",
            "question": "哪些结果可进入论文 Results？",
            "frozen_rule": "confirmatory 与 exploratory 必须分离。",
            "observed_result": "重复性、AS01 效应、G 与 CI、配置差异及分类负结果可报告；AS02 仅 exploratory。",
            "decision": "bounded_results_allowed",
            "claim_strength": "supported_with_limits",
            "allowed_wording": "按测量、推断和限制分层报告。",
            "prohibited_wording": "把探索性 AS02 或连续重复当确认性独立证据。",
        },
        {
            "hypothesis_id": "RQ7",
            "question": "是否需要改变设计，或可在当前边界下继续论文？",
            "frozen_rule": "门槛未全过时不得宣称确认，但允许如实报告受限证据。",
            "observed_result": "存在可测效应，但确认性 H1 与分类目标未通过。",
            "decision": "continue_dissertation_with_limits",
            "claim_strength": "bounded_completion",
            "allowed_wording": "无需为完成当前受限论文强制重设计；可选补充实验用于未来验证。",
            "prohibited_wording": "无需任何后续验证，或装置已达到部署要求。",
        },
    ]


def _evidence_markdown() -> str:
    return """# FORMAL-5 最终证据总结

## 最终裁决

`supported_with_limits`。本轮仅综合 FORMAL-3/FORMAL-4 冻结产物；没有重新扫描原始目录、改变 72 ACTIVE/19 EXCLUDED、重新选阈值、搜索模型或读取 final-test。

## 冻结证据

- 主频带 CONT 重复性底线：median 0.3783 dB，IQR 0.2191 dB，p95 0.8793 dB。
- U4ENC `G_demeaned=1.2805`，95% CI 0.8297–1.7667。
- U4SYM `G_demeaned=0.6824`，95% CI 0.6105–1.2699。
- `ΔG_demeaned=0.5982`，95% CI -0.1131–1.0843。
- AS01 配置差异 median effect/floor ratio=1.5688。
- U4ENC 的 6/6 方向对、U4SYM 的 3/6 方向对在两个 AS01 REPOS blocks 中超过 CONT p95 底线。
- AS01 grouped validation：U4SYM balanced accuracy 0.375、macro-F1 0.250；U4ENC balanced accuracy 0.250、macro-F1 0.183，均低于冻结的 0.50 实用目标。
- 10 条 outlier flag 的敏感性分析没有改变冻结阈值结论，也没有改变 ACTIVE/EXCLUDED。

## 研究问题逐项回答

1. **方向频谱变化：支持。** 测量层面存在超过 CONT 重复性底线的方向相关频谱变化。
2. **U4ENC 方向性更强：部分支持，但未确认。** 点估计更高；U4ENC CI 下限未高于 1，且 ΔG CI 包含 0。
3. **配置差异：有边界支持。** AS01 四方向差异均超过底线，不能据此推导稳定分类能力。
4. **可靠方向分类：不支持。** 两种配置的 grouped balanced accuracy 均未达到 50%。
5. **AS01/AS02 独立比较：不可作确认性判断。** AS02 每种配置只有一个 block，assembly 与 block/time 混杂。
6. **论文材料边界：** 可报告重复性、AS01 方向和配置效应、G/CI、分类负结果；AS02 只能标为 exploratory。
7. **后续处置：** 可在上述边界下继续论文撰写；不要求为本论文强制补测或重设计，额外独立 blocks/sessions 仅为可选后续验证。

## 假设裁决

H1 **未确认**；完整 H0 **未被拒绝**。点估计方向符合 H1，但 ΔG 的 CI 包含 0，且冻结 CI 门槛未完全通过。三次 CONT 仅用于技术重复性，不作为三个独立科学样本。

## 摘要可用句

在本研究的普通房间与有限重复条件下，编码结构产生了超过测量重复性底线的方向相关频谱变化，其方向性效应点估计高于对称结构，但组间差异和方向分类性能未达到预设的确认性标准。

## 资格与限制

`scientifically_eligible=false`，因为上游冻结 artifact 尚未授予科学资格、确认性 CI/分类门槛未全部通过，且 FORMAL-2 仍保存未解决的采集治理项。这表示证据仅可作为有明确边界的论文结果与探索性观察，并非软件执行失败。`final_test_read=false`，final-test 继续 sealed。
"""


def _dissertation_draft() -> str:
    return """# Dissertation Results Draft — FORMAL-5

## Methods 摘要

本研究比较 U4ENC 与 U4SYM 在 0°、90°、180°和 270°四个方向的 REW Sweep 频率响应。冻结的 72 条 ACTIVE 测量由六个 12 样本 blocks 构成，每个 block×direction 包含三次 CONT 技术重复；19 条 EXCLUDED 记录仅保留于排除审计。所有曲线按 FORMAL-1 契约投影至 200–8000 Hz、48 points/octave 的公共对数网格，并在连续有效区间内执行 1/12-octave dB smoothing。主分析使用 200–4000 Hz 的实际有效公共点，不外推缺失的 200 Hz 边界。

方向效应以冻结的 `G_demeaned` 为主指标，并同时保留 raw、demeaned 和 z-score 视图。CONT 只定义技术重复误差，不被视为独立科学样本。分类采用 leave-one-block-out grouped validation，未使用普通随机拆分。FORMAL-3 的 10 条 outlier flags 全部留在 primary analysis，仅在独立 sensitivity analysis 中暂时省略，且未写回样本选择。

## Results

主频带 CONT 两两 RMS dB 差的稳健分布为 median 0.3783 dB、IQR 0.2191 dB、p95 0.8793 dB。以该 p95 作为技术重复性底线，U4ENC 的六个方向对均在两个 AS01 REPOS blocks 中超过底线；U4SYM 有三个方向对满足同一条件。这支持“存在可测的方向相关频谱变化”，但不等同于每个方向都能被可靠分类。

U4ENC 的 `G_demeaned` 点估计为 1.2805（95% CI 0.8297–1.7667），U4SYM 为 0.6824（95% CI 0.6105–1.2699）。两者差值为 0.5982（95% CI -0.1131–1.0843）。因此，U4ENC 的点估计高于 U4SYM 且高于 1，但 U4ENC CI 下限未超过 1，差值 CI 亦包含 0；冻结的确认性门槛没有全部满足，H1 不能判定为 confirmed。

AS01 中 U4ENC−U4SYM 的同方向差异在四个方向均超过 CONT p95 底线，median effect/floor ratio 为 1.5688。这说明两种配置在当前 AS01 blocks 中具有可测差异，但不能单独证明编码结构具有更强或可部署的方向识别能力。

AS01 grouped validation 的 U4SYM balanced accuracy 为 0.375、macro-F1 为 0.250；U4ENC 分别为 0.250 和 0.183。两者均低于预注册的 0.50 实用目标，因此当前数据不支持稳定方向分类。省略 10 条 outlier flags 的敏感性分析未改变任何冻结阈值结论，ACTIVE/EXCLUDED 始终保持 72/19。

## Discussion

结果显示，物理频谱层面能够观察到超过技术重复性底线的方向效应，且 U4ENC 的方向性点估计高于 U4SYM。然而，置信区间反映的 block-level 不确定性仍较大，配置间 `ΔG_demeaned` 尚不能排除 0。分类负结果进一步表明，当前可测差异没有转化为满足预设实用目标的稳健方向识别。

因此，恰当结论是“编码结构呈现更高的方向性点估计并产生可测频谱差异”，而不是“编码结构已被证明优于对称结构”或“方向可以可靠分类”。这组受限证据可用于完成当前论文的 Results 与 Discussion，但 H1 仍未确认。

## Limitations

- 72 条 ACTIVE 由连续技术重复嵌套在有限 blocks 中；CONT 不能扩充独立样本数。
- U4ENC 与 U4SYM 的 `G_demeaned` 和差值 CI 均未完全越过冻结确认性边界。
- AS02 每种配置只有一个 block，assembly-set 与 acquisition block/time 混杂，只能作为探索性观察。
- FORMAL-2 审计仍保存外置备份、几何/环境记录、人工授权与签署等未解决治理项。
- 原始 REW TXT header 未列出校准文件，FORMAL-3 因而保留 72 个 calibration-provenance warnings；独立截图证据验证了 iMM-6C 输入校准加载，但不能回写 TXT header。
- final-test 未读取，不能用本轮结果声称 final-test 泛化或部署能力。

## Future work

可选后续研究可增加独立 sessions、补齐 AS02 的第二个 REPOS/block，并预注册同一 grouped validation。该补充不是完成当前受限论文的必要条件，也不得用于追溯性改变本研究的样本选择、主指标或阈值。真实 Multisine/P8 与 final-test 仍不在本轮范围。
"""


def _figure_rows() -> list[dict[str, str]]:
    return [
        {"suggested_figure": "Figure 1", "title": "主频带重复性误差随频率变化", "source_artifact": "plots/repeatability_frequency.png", "purpose": "建立 CONT 测量误差底线", "limitation": "CONT 是技术重复，不是独立科学样本"},
        {"suggested_figure": "Figure 2", "title": "各 block 四方向中位数曲线与重复范围", "source_artifact": "plots/block_direction_B01.png;plots/block_direction_B02.png;plots/block_direction_B03.png;plots/block_direction_B04.png", "purpose": "以 AS01 多面板展示方向效应和重复范围", "limitation": "应合并为一幅多面板图，避免把四个 panels 当独立实验"},
        {"suggested_figure": "Figure 3", "title": "方向两两距离热图", "source_artifact": "plots/direction_pairwise_heatmap.png", "purpose": "显示哪些方向对超过 CONT p95", "limitation": "距离超过底线不等于分类成功"},
        {"suggested_figure": "Figure 4", "title": "方向效应与重复性底线之比", "source_artifact": "plots/effect_to_repeatability_ratio.png", "purpose": "展示物理方向效应相对技术噪声", "limitation": "ratio 是描述性工程指标"},
        {"suggested_figure": "Figure 5", "title": "U4ENC−U4SYM 配置差值曲线", "source_artifact": "plots/configuration_difference.png", "purpose": "展示 AS01/AS02 配置差异及主次频带", "limitation": "AS02 与 block/time 混杂"},
        {"suggested_figure": "Figure 6", "title": "Outlier flag 敏感性", "source_artifact": "plots/outlier_sensitivity.png", "purpose": "证明 10 个 flags 未改变冻结阈值结论", "limitation": "敏感性省略不改变 ACTIVE/EXCLUDED"},
        {"suggested_figure": "Figure 7", "title": "AS01 grouped-validation confusion matrices", "source_artifact": "plots/grouped_validation_confusion_matrix.png", "purpose": "报告分类负结果与错误结构", "limitation": "有限 blocks；不得改用随机拆分"},
    ]


def _validate_audit_inputs(input_artifacts: Mapping[str, Mapping[str, str]]) -> None:
    if not input_artifacts:
        raise Formal5InputError("input_artifacts must explicitly identify frozen authorities")
    for name, entry in input_artifacts.items():
        digest = entry.get("sha256")
        if not isinstance(entry.get("path"), str) or not entry["path"]:
            raise Formal5InputError(f"input artifact path missing: {name}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise Formal5InputError(f"input artifact SHA-256 invalid: {name}")


def write_formal5_bundle(
    summary: Mapping[str, Any],
    output_directory: str | Path,
    *,
    source_commit: str,
    created_at: str | datetime,
    input_artifacts: Mapping[str, Mapping[str, str]],
    acquisition_evidence: Mapping[str, Any],
) -> Formal5RunResult:
    """Write one immutable synthesis bundle from an already verified authority snapshot."""
    if len(source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in source_commit):
        raise Formal5InputError("source_commit must be a full lowercase Git SHA")
    timestamp = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise Formal5InputError("created_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise Formal5InputError("created_at must include timezone")
    output = Path(output_directory).resolve()
    staging = output.with_name(output.name + ".staging")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing FORMAL-5 output: {output}")
    if staging.exists():
        raise FileExistsError(f"refusing to overwrite existing FORMAL-5 staging output: {staging}")
    decision = evaluate_frozen_evidence(summary)
    _validate_audit_inputs(input_artifacts)
    staging.mkdir(parents=True)
    try:
        (staging / "final_evidence_summary.md").write_text(_evidence_markdown(), encoding="utf-8")
        _write_csv(
            staging / "hypothesis_decision_table.csv",
            _decision_rows(),
            ("hypothesis_id", "question", "frozen_rule", "observed_result", "decision", "claim_strength", "allowed_wording", "prohibited_wording"),
        )
        (staging / "dissertation_results_draft.md").write_text(_dissertation_draft(), encoding="utf-8")
        _write_csv(
            staging / "dissertation_figure_index.csv",
            _figure_rows(),
            ("suggested_figure", "title", "source_artifact", "purpose", "limitation"),
        )
        _write_json(staging / "final_claim_boundary.json", {
            "schema_version": FORMAL5_SCHEMA_VERSION,
            "disposition": decision["disposition"],
            "allowed_claims": [
                "存在超过测量重复性底线的方向相关频谱变化",
                "U4ENC 的方向性效应点估计高于 U4SYM",
                "AS01 中两配置存在超过 CONT 底线的可测差异",
                "当前 grouped validation 未支持稳定方向分类",
            ],
            "prohibited_claims": [
                "H1 已得到确认或 U4ENC 已被证明优于 U4SYM",
                "当前系统能够稳定识别四方向",
                "AS01 与 AS02 差异具有无混杂因果解释",
                "模拟、final-test、部署或真实 Multisine 资格已经获得",
            ],
            "scientifically_eligible": False,
            "scientifically_eligible_reason": "upstream artifacts remain ineligible; frozen confirmatory CI/classification gates were not all met; acquisition-governance limitations remain",
            "eligibility_interpretation": "bounded_and_exploratory_dissertation_evidence_not_a_software_failure",
            "supplementary_experiment": {
                "recommendation": "optional",
                "reason": "independent AS02 blocks/sessions could reduce uncertainty but are not required to complete the current bounded dissertation",
            },
            "final_test_read": False,
            "final_test_status": "sealed",
            "hypothesis_decisions": decision["hypothesis_decisions"],
            "question_decisions": decision["question_decisions"],
        })
        business_before_manifest = sorted(path for path in staging.iterdir() if path.is_file())
        output_hashes = {
            path.name: {"sha256": artifact_sha256(path), "bytes": path.stat().st_size}
            for path in business_before_manifest
        }
        _write_json(staging / "final_analysis_manifest.json", {
            "schema_version": FORMAL5_SCHEMA_VERSION,
            "created_at": timestamp,
            "source_commit": source_commit,
            "authority": "FORMAL-3_and_FORMAL-4_explicit_manifests_only",
            "input_artifacts": dict(sorted(input_artifacts.items())),
            "output_artifacts": output_hashes,
            "output_manifest_self_hash_excluded": True,
            "selection": {
                "active_count": 72,
                "excluded_count": 19,
                "outlier_flag_count": 10,
                "selection_changed": False,
                "excluded_entered_analysis": False,
            },
            "input_zip_sha256": FORMAL3_ZIP_SHA256,
            "provenance": {
                "data_origin": "real_experiment",
                "dataset_role": "research_analysis",
                "run_purpose": "research_analysis",
                "scientifically_eligible": False,
            },
            "acquisition_evidence": dict(acquisition_evidence),
            "raw_directory_scanned": False,
            "raw_txt_reimported": False,
            "sample_selection_changed": False,
            "thresholds_changed": False,
            "model_search_performed": False,
            "new_statistical_tests_performed": False,
            "final_test_read": False,
            "final_test_status": "sealed",
            "disposition": decision["disposition"],
        })
        business = sorted(path for path in staging.iterdir() if path.is_file())
        artifacts = [
            {"path": path.name, "sha256": artifact_sha256(path), "bytes": path.stat().st_size}
            for path in business
        ]
        _write_json(staging / "artifact_manifest.json", {
            "schema_version": "formal5_artifact_manifest_v1",
            "algorithm": "SHA-256",
            "artifacts": artifacts,
        })
        all_sums = [*artifacts, {
            "path": "artifact_manifest.json",
            "sha256": artifact_sha256(staging / "artifact_manifest.json"),
            "bytes": (staging / "artifact_manifest.json").stat().st_size,
        }]
        (staging / "SHA256SUMS").write_text(
            "".join(f"{entry['sha256']}  {entry['path']}\n" for entry in all_sums),
            encoding="utf-8",
        )
        verification = verify_formal5_output_hashes(staging)
        if verification["artifact_count"] != 6:
            raise Formal5InputError("FORMAL-5 business artifact count mismatch")
        staging.rename(output)
        return Formal5RunResult(output, decision["disposition"], 6)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_formal5_output_hashes(output_directory: str | Path) -> dict[str, Any]:
    root = Path(output_directory).resolve()
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise Formal5InputError("FORMAL-5 artifact manifest is empty")
    seen: set[str] = set()
    for entry in artifacts:
        relative = entry.get("path")
        if not isinstance(relative, str) or relative in seen or Path(relative).name != relative:
            raise Formal5InputError(f"invalid FORMAL-5 artifact path: {relative!r}")
        seen.add(relative)
        path = root / relative
        if not path.is_file():
            raise Formal5InputError(f"FORMAL-5 artifact missing: {relative}")
        if artifact_sha256(path) != entry.get("sha256"):
            raise Formal5InputError(f"FORMAL-5 artifact hash mismatch: {relative}")
        if int(entry.get("bytes", -1)) != path.stat().st_size:
            raise Formal5InputError(f"FORMAL-5 artifact size mismatch: {relative}")
    sums: dict[str, str] = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", maxsplit=1)
        sums[relative] = digest
    for relative in [*seen, "artifact_manifest.json"]:
        if sums.get(relative) != artifact_sha256(root / relative):
            raise Formal5InputError(f"FORMAL-5 SHA256SUMS mismatch: {relative}")
    return {
        "all_match": True,
        "artifact_count": len(artifacts),
        "artifact_manifest_sha256": artifact_sha256(root / "artifact_manifest.json"),
    }


def run_formal5_final_synthesis(
    project_root: str | Path,
    formal3_directory: str | Path,
    formal4_directory: str | Path,
    acquisition_root: str | Path,
    output_directory: str | Path,
    *,
    source_commit: str,
    created_at: str | datetime,
) -> Formal5RunResult:
    """Verify explicit frozen authorities and write the final synthesis bundle.

    This entry point accesses only the named manifests, evidence files, and FORMAL-4
    artifact closure. It never discovers raw measurements or revises sample identity.
    """
    root = Path(project_root).resolve()
    formal3 = Path(formal3_directory).resolve()
    formal4 = Path(formal4_directory).resolve()
    acquisition = Path(acquisition_root).resolve()
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing FORMAL-5 output: {output}")

    authority3 = verify_formal3_authority(formal3)
    authority4 = verify_formal4_output_hashes(formal4)
    if authority4.get("artifact_count") != 28:
        raise Formal5InputError("FORMAL-4 must provide exactly 28 verified artifacts")
    summary = _read_json(formal4 / "analysis_summary.json")
    run4 = _read_json(formal4 / "run_manifest.json")
    run3 = _read_json(formal3 / "run_manifest.json")
    evaluate_frozen_evidence(summary)
    trace_tables = {
        name: _read_csv(formal4 / name)
        for name in (
            "repeatability_summary.csv",
            "direction_gain_summary.csv",
            "direction_gain_contrasts.csv",
            "configuration_effects.csv",
            "grouped_validation_metrics.csv",
            "outlier_sensitivity.csv",
        )
    }
    validate_formal4_numeric_trace(summary, trace_tables)

    _require_equal("FORMAL-3 ready", run3.get("ready_for_formal_analysis"), True)
    _require_equal("FORMAL-3 final_test_read", run3.get("final_test_read"), False)
    _require_equal("FORMAL-3 ACTIVE", run3.get("selection", {}).get("active_count"), 72)
    _require_equal("FORMAL-3 EXCLUDED", run3.get("selection", {}).get("excluded_count"), 19)
    _require_equal("FORMAL-4 final_test_read", run4.get("final_test_read"), False)
    _require_equal("FORMAL-4 raw scan", run4.get("raw_directory_scanned"), False)
    _require_equal("FORMAL-4 selection changed", run4.get("active_excluded_selection_changed"), False)
    f4_input = run4.get("input", {})
    _require_equal("FORMAL-4 FeatureSet count", f4_input.get("feature_count"), 72)
    _require_equal("FORMAL-4 valid point count", f4_input.get("common_valid_point_count"), 255)
    _require_equal("FORMAL-4 FORMAL-3 run hash", f4_input.get("run_manifest_sha256"), authority3.run_manifest_sha256)
    _require_equal("FORMAL-4 FORMAL-3 artifact hash", f4_input.get("artifact_manifest_sha256"), authority3.artifact_manifest_sha256)
    _require_equal("FORMAL-4 ZIP hash", f4_input.get("zip_sha256"), FORMAL3_ZIP_SHA256)

    explicit_project_inputs = {
        "research_protocol_rev002": root / "docs" / "experiment" / "RESEARCH_PROTOCOL_REV002.md",
        "formal_acquisition_plan_rev001": root / "docs" / "experiment" / "FORMAL_ACQUISITION_PLAN_REV001.md",
        "formal2_preflight_report": root / "docs" / "progress" / "FORMAL_2_PREFLIGHT_PACKAGE.md",
        "formal2a_calibration_report": root / "docs" / "progress" / "FORMAL_2A_CALIBRATION_REGISTRATION.md",
        "formal2a_fix_report": root / "docs" / "progress" / "FORMAL_2A_FIX_MIC_INPUT_EVIDENCE.md",
        "formal3_active_manifest": formal3 / "active_manifest.csv",
        "formal3_excluded_manifest": formal3 / "excluded_manifest.csv",
        "formal3_run_manifest": formal3 / "run_manifest.json",
        "formal3_artifact_manifest": formal3 / "artifact_manifest.json",
        "formal4_analysis_summary": formal4 / "analysis_summary.json",
        "formal4_run_manifest": formal4 / "run_manifest.json",
        "formal4_artifact_manifest": formal4 / "artifact_manifest.json",
        "formal4_repeatability_summary": formal4 / "repeatability_summary.csv",
        "formal4_direction_gain_summary": formal4 / "direction_gain_summary.csv",
        "formal4_direction_gain_contrasts": formal4 / "direction_gain_contrasts.csv",
        "formal4_configuration_effects": formal4 / "configuration_effects.csv",
        "formal4_grouped_validation_metrics": formal4 / "grouped_validation_metrics.csv",
        "formal4_outlier_sensitivity": formal4 / "outlier_sensitivity.csv",
    }
    explicit_acquisition_inputs = {
        "preflight_status": acquisition / "00_protocol_and_manifests" / "preflight_status.json",
        "calibration_file": acquisition / "01_calibration" / "CMM29939.txt",
        "calibration_registration": acquisition / "01_calibration" / "calibration_registration.json",
        "calibration_input_evidence_fix": acquisition / "01_calibration" / "calibration_input_evidence_fix.json",
        "mic_input_evidence_screenshot": acquisition / "01_calibration" / "REW_CMM29939_MIC_INPUT_LOADED.png",
    }
    inputs = {**explicit_project_inputs, **explicit_acquisition_inputs}
    missing = [name for name, path in inputs.items() if not path.is_file()]
    if missing:
        raise Formal5InputError(f"explicit FORMAL-5 authority files missing: {', '.join(missing)}")

    preflight = _read_json(explicit_acquisition_inputs["preflight_status"])
    calibration = _read_json(explicit_acquisition_inputs["calibration_input_evidence_fix"])
    _require_equal("preflight final_test_read", preflight.get("final_test_read"), False)
    _require_equal("calibration final_test_read", calibration.get("final_test_read"), False)
    _require_equal(
        "iMM-6C input calibration binding",
        calibration.get("input_device_binding", {}).get("status"),
        "verified",
    )
    _require_equal(
        "calibration file SHA-256",
        artifact_sha256(explicit_acquisition_inputs["calibration_file"]),
        "421070ec6d41c1b92cb69f0f5e4e290f9644847d92d52590994a80ea9e17a11e",
    )
    _require_equal(
        "mic evidence SHA-256",
        artifact_sha256(explicit_acquisition_inputs["mic_input_evidence_screenshot"]),
        "5811b17a882bc8000e9746b172b007616aada9f8786e1f4b9b96b6fed353b9ba",
    )
    input_artifacts = {
        name: {"path": str(path), "sha256": artifact_sha256(path), "bytes": path.stat().st_size}
        for name, path in sorted(inputs.items())
    }
    acquisition_evidence = {
        "calibration_input_binding": "verified",
        "calibration_sha256": preflight.get("calibration_sha256"),
        "mic_input_evidence_sha256": preflight.get("calibration_input_evidence_sha256"),
        "ready_for_B01": preflight.get("ready_for_B01"),
        "manual_checks_complete": preflight.get("manual_checks_complete"),
        "unresolved_blockers": preflight.get("unresolved_blockers", []),
        "interpretation": "historical acquisition-governance evidence retained; not retroactively rewritten by FORMAL-5",
    }
    return write_formal5_bundle(
        summary,
        output,
        source_commit=source_commit,
        created_at=created_at,
        input_artifacts=input_artifacts,
        acquisition_evidence=acquisition_evidence,
    )
