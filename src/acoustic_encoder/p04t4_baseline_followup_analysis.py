"""P04T4 third-baseline follow-up analysis.

The added BASERR batch is treated as a third, independently reassembled BASE
observation.  Time, room/environment and assembly all changed together, so the
analysis describes baseline trajectories without assigning a unique cause.
Complete repeat curves are the resampling unit; frequency bins are never
treated as independent observations.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import itertools
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping, Sequence
import zipfile

import numpy as np
from numpy.typing import NDArray

from .formal_preprocessing import frozen_formal_preprocessing_contract, preprocess_formal_sweep
from .formal_real_import import _parse_rew_member
from .p04t4_return_control_analysis import (
    P04_LOCAL_REFERENCE_DB,
    P04T4InputError,
    _condition_matrix,
    _inspect_inputs,
    _pairwise_rms,
    _preprocess_members,
    _sha256_file,
    _write_csv,
    select_closest_repeats,
)
from .schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    QCStatus,
    Representation,
    SourceFormat,
    SpectrumData,
)
from .version import (
    CONFIG_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    MEASUREMENT_SCHEMA_VERSION,
    PIPELINE_VERSION,
)


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

P04T4_FOLLOWUP_SCHEMA_VERSION = "p04t4_baseline_reassembly_followup_v1"
P04T4_FOLLOWUP_SOURCE_ZIP_SHA256 = (
    "cda5a7471c9b866a0df5ac0e2fd2e15d44e676f833d415ca997ba0e7291a72b9"
)
CONDITIONS = ("BASEC", "I50PC", "BASER", "BASERR")
BASELINE_CONDITIONS = ("BASEC", "BASER", "BASERR")
BOOTSTRAP_ITERATIONS = 2000
BOOTSTRAP_SEED = 260827
MIN_EFFECT_SIMILARITY = 0.60

_NAME = re.compile(r"^R P04T4_BASERR_R(?P<repeat>0[1-6])(?P<extension>\.txt|\.mdat)$")


class P04T4BaselineFollowupInputError(ValueError):
    """Raised when follow-up identity, provenance or processing fails closed."""


@dataclass(frozen=True, slots=True)
class FollowupMember:
    path: Path
    filename: str
    repeat_number: int
    extension: str
    sha256: str
    size_bytes: int

    @property
    def sample_id(self) -> str:
        return f"P04T4-BASERR-R{self.repeat_number:02d}"


@dataclass(frozen=True, slots=True)
class FollowupRunResult:
    output_directory: Path
    classification: str
    measurement_count: int
    artifact_count: int


def parse_p04t4_baseline_followup_filename(filename: str) -> int:
    match = _NAME.fullmatch(filename)
    if match is None:
        raise P04T4BaselineFollowupInputError(
            f"cannot reliably identify P04T4 BASERR repeat: {filename}"
        )
    return int(match.group("repeat"))


def _rms(values: FloatArray, mask: BoolArray) -> float:
    return float(np.sqrt(np.mean(np.square(values[mask]))))


def _demean(values: FloatArray, mask: BoolArray) -> FloatArray:
    return values - float(np.mean(values[mask]))


def _correlation(left: FloatArray, right: FloatArray) -> float:
    if np.std(left) <= 1e-12 or np.std(right) <= 1e-12:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def _cosine(left: FloatArray, right: FloatArray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return 0.0 if denominator <= 1e-12 else float(np.dot(left, right) / denominator)


def compute_baseline_followup_metrics(
    representatives: Mapping[str, FloatArray], primary_mask: BoolArray
) -> dict[str, float]:
    mask = np.asarray(primary_mask, dtype=bool)
    arrays = {key: np.asarray(representatives[key], dtype=np.float64) for key in CONDITIONS}
    if len({array.shape for array in arrays.values()} | {mask.shape}) != 1:
        raise ValueError("representative curve shapes differ")

    baseline_differences: dict[tuple[str, str], FloatArray] = {}
    for left, right in itertools.combinations(BASELINE_CONDITIONS, 2):
        baseline_differences[(left, right)] = arrays[right] - arrays[left]

    effects = {
        baseline: _demean(arrays["I50PC"] - arrays[baseline], mask)
        for baseline in BASELINE_CONDITIONS
    }
    effect_rms = {baseline: _rms(effect, mask) for baseline, effect in effects.items()}
    effect_correlations = [
        _correlation(effects[left][mask], effects[right][mask])
        for left, right in itertools.combinations(BASELINE_CONDITIONS, 2)
    ]
    effect_cosines = [
        _cosine(effects[left][mask], effects[right][mask])
        for left, right in itertools.combinations(BASELINE_CONDITIONS, 2)
    ]

    result: dict[str, float] = {}
    labels = {
        ("BASEC", "BASER"): "basec_to_baser",
        ("BASEC", "BASERR"): "basec_to_baserr",
        ("BASER", "BASERR"): "baser_to_baserr",
    }
    for pair, difference in baseline_differences.items():
        label = labels[pair]
        result[f"{label}_raw_rms_db"] = _rms(difference, mask)
        result[f"{label}_shape_rms_db"] = _rms(_demean(difference, mask), mask)
    for baseline, value in effect_rms.items():
        result[f"i50_vs_{baseline.casefold()}_shape_rms_db"] = value
    result["i50_min_shape_rms_db"] = min(effect_rms.values())
    result["i50_max_shape_rms_db"] = max(effect_rms.values())
    result["i50_effect_min_pairwise_pearson"] = min(effect_correlations)
    result["i50_effect_min_pairwise_cosine"] = min(effect_cosines)
    initial_return = result["basec_to_baser_shape_rms_db"]
    result["baserr_recovery_ratio_vs_initial_return"] = (
        result["basec_to_baserr_shape_rms_db"] / initial_return
        if initial_return > 1e-12
        else float("inf")
    )
    return result


def classify_baseline_pattern(
    metrics: Mapping[str, float], *, within_condition_ceiling_db: float
) -> str:
    i50_robust = (
        metrics["i50_min_shape_rms_db"] >= P04_LOCAL_REFERENCE_DB
        and metrics["i50_effect_min_pairwise_pearson"] >= MIN_EFFECT_SIMILARITY
    )
    c_to_r = metrics["basec_to_baser_shape_rms_db"]
    c_to_rr = metrics["basec_to_baserr_shape_rms_db"]
    r_to_rr = metrics["baser_to_baserr_shape_rms_db"]
    if c_to_rr <= within_condition_ceiling_db and c_to_r > within_condition_ceiling_db:
        baseline_state = "BASELINE_RECOVERED"
    elif r_to_rr <= within_condition_ceiling_db and c_to_r > within_condition_ceiling_db:
        baseline_state = "BASELINE_SHIFT_PERSISTED"
    elif max(c_to_r, c_to_rr, r_to_rr) <= within_condition_ceiling_db:
        baseline_state = "BASELINE_STABLE_WITHIN_LOCAL_REPEATABILITY"
    else:
        baseline_state = "BASELINE_NONSTATIONARY_OR_REASSEMBLY_SENSITIVE"
    suffix = "I50_EFFECT_ROBUST" if i50_robust else "I50_EFFECT_NOT_ROBUST"
    return f"P04T4F {baseline_state}_WITH_{suffix}"


def _inspect_followup_inputs(batch: Path) -> tuple[list[FollowupMember], Path, str]:
    archives = list((batch / "source").glob("*.zip"))
    if len(archives) != 1:
        raise P04T4BaselineFollowupInputError(
            f"follow-up requires exactly one source ZIP; found {len(archives)}"
        )
    source_zip = archives[0]
    zip_sha = _sha256_file(source_zip)
    if zip_sha != P04T4_FOLLOWUP_SOURCE_ZIP_SHA256:
        raise P04T4BaselineFollowupInputError(f"follow-up source ZIP SHA mismatch: {zip_sha}")

    members: list[FollowupMember] = []
    for directory, extension in ((batch / "raw_txt", ".txt"), (batch / "raw_mdat", ".mdat")):
        files = sorted(path for path in directory.iterdir() if path.is_file())
        if len(files) != 6:
            raise P04T4BaselineFollowupInputError(
                f"expected six {extension} files in {directory}; found {len(files)}"
            )
        for path in files:
            repeat = parse_p04t4_baseline_followup_filename(path.name)
            if path.suffix.casefold() != extension:
                raise P04T4BaselineFollowupInputError(f"extension mismatch: {path.name}")
            members.append(
                FollowupMember(
                    path=path,
                    filename=path.name,
                    repeat_number=repeat,
                    extension=extension,
                    sha256=_sha256_file(path),
                    size_bytes=path.stat().st_size,
                )
            )
    expected = set(range(1, 7))
    for extension in (".txt", ".mdat"):
        actual = {member.repeat_number for member in members if member.extension == extension}
        if actual != expected:
            raise P04T4BaselineFollowupInputError(f"incomplete BASERR {extension} repeat matrix")

    with zipfile.ZipFile(source_zip, "r") as archive:
        zip_members: dict[str, tuple[int, str]] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            posix = PurePosixPath(info.filename)
            if posix.is_absolute() or ".." in posix.parts:
                raise P04T4BaselineFollowupInputError(f"unsafe ZIP member: {info.filename}")
            name = posix.name
            if name in zip_members:
                raise P04T4BaselineFollowupInputError(f"duplicate ZIP basename: {name}")
            parse_p04t4_baseline_followup_filename(name)
            payload = archive.read(info)
            zip_members[name] = (len(payload), hashlib.sha256(payload).hexdigest())
    if len(zip_members) != 12:
        raise P04T4BaselineFollowupInputError(
            f"follow-up ZIP requires 12 files; found {len(zip_members)}"
        )
    for member in members:
        if zip_members.get(member.filename) != (member.size_bytes, member.sha256):
            raise P04T4BaselineFollowupInputError(
                f"extracted file differs from source ZIP: {member.filename}"
            )
    return members, source_zip, zip_sha


def _followup_meta(member: FollowupMember, reasons: Sequence[str]) -> MeasurementMeta:
    return MeasurementMeta(
        sample_id=member.sample_id,
        pipeline_version=PIPELINE_VERSION,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        measurement_schema_version=MEASUREMENT_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        device_version="V2.5_P04T4_return_control",
        configuration="BASERR",
        angle_deg=0.0,
        session_id="P04T4-BASELINE-FOLLOWUP-20260826",
        repeat_type="CONT",
        repeat_id=f"R{member.repeat_number:02d}",
        experiment_step="P04T4_BASELINE_REASSEMBLY_FOLLOWUP",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=member.path.as_posix(),
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_ANALYSIS,
        source_sha256=member.sha256,
        provenance_uri=f"sha256:{P04T4_FOLLOWUP_SOURCE_ZIP_SHA256}#member={member.sha256}",
        eligible_for_scientific_analysis=False,
        assembly_id="R02",
        acquisition_block_id="BASERR",
        valid=True,
        qc_status=QCStatus.WARNING if reasons else QCStatus.VALID,
        manual_review_reasons=tuple(reasons),
    )


def _preprocess_followup(
    members: Sequence[FollowupMember],
) -> tuple[FloatArray, BoolArray, dict[str, FloatArray], list[dict[str, Any]], dict[str, datetime]]:
    frequency: FloatArray | None = None
    valid: BoolArray | None = None
    curves: dict[str, FloatArray] = {}
    qc_rows: list[dict[str, Any]] = []
    dates: dict[str, datetime] = {}
    contract = frozen_formal_preprocessing_contract()
    for member in sorted((item for item in members if item.extension == ".txt"), key=lambda item: item.repeat_number):
        parsed = _parse_rew_member(member.path.read_bytes(), member.filename)
        headers = parsed.headers["all"]
        note = parsed.headers.get("note", "")
        checks = {
            "format_contract_ok": bool(re.search(
                r"Format:\s*256k Log Swept Sine,\s*1 sweep at -30\.0 dBFS with no timing reference",
                headers,
                re.I,
            )),
            "identity_ok": (
                f"Measurement: R P04T4_BASERR_R{member.repeat_number:02d}" in headers
            ),
            "note_contract_ok": all(re.search(pattern, note, re.I) for pattern in (
                r"1 acoustic channels open",
                r"Windows out=50",
                r"mic input=100",
                r"distance=0\.8 m",
            )),
            "source_iMM6C_ok": "iMM-6C" in parsed.headers.get("source", ""),
            "frequency_coverage_ok": (
                parsed.frequency_hz[0] <= 200.0 and parsed.frequency_hz[-1] >= 7999.0
            ),
        }
        inferred_sample_rate = float(np.median(np.diff(parsed.frequency_hz)) * 131072.0)
        checks["inferred_48k_ok"] = abs(inferred_sample_rate - 48000.0) <= 2.0
        failures = [name for name, ok in checks.items() if not ok]
        if failures:
            raise P04T4BaselineFollowupInputError(
                f"structural QC failed for {member.filename}: {failures}"
            )
        warnings = (
            "calibration_filename_header_unavailable",
            "t0_at_ir_peak_header_unavailable",
            "clipping_unavailable_from_frequency_response_txt",
            "time_environment_and_reassembly_are_jointly_changed",
        )
        spectrum = SpectrumData(
            frequency_hz=parsed.frequency_hz,
            magnitude_db=parsed.magnitude_db,
            valid_mask=np.ones(parsed.frequency_hz.size, dtype=bool),
            representation=Representation.DENSE_SPECTRUM,
            phase_status=PhaseStatus.UNAVAILABLE,
            quality_metrics={"p04t4_followup_qc_reasons": warnings},
            meta=_followup_meta(member, warnings),
            magnitude_quantity="spl",
            magnitude_reference="REW frequency-response export",
        )
        processed = preprocess_formal_sweep(spectrum, contract)
        if frequency is None:
            frequency = processed.frequency_hz.copy()
            valid = processed.valid_mask.copy()
        elif not np.array_equal(frequency, processed.frequency_hz) or not np.array_equal(valid, processed.valid_mask):
            raise P04T4BaselineFollowupInputError("BASERR processed grids or masks differ")
        curves[member.sample_id] = processed.magnitude_db.copy()
        dated = parsed.headers.get("dated", "").removeprefix("Dated:").strip()
        try:
            date = datetime.strptime(dated, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise P04T4BaselineFollowupInputError(
                f"invalid Dated header: {member.filename}: {dated}"
            ) from exc
        dates[member.sample_id] = date
        qc_rows.append({
            "sample_id": member.sample_id,
            "filename": member.filename,
            "repeat_number": member.repeat_number,
            "dated_header": dated,
            "file_sha256": member.sha256,
            "size_bytes": member.size_bytes,
            "structural_valid": True,
            "qc_status": "warning",
            "reason_codes": warnings,
            "raw_point_count": int(parsed.frequency_hz.size),
            "frequency_min_hz": float(parsed.frequency_hz[0]),
            "frequency_max_hz": float(parsed.frequency_hz[-1]),
            "inferred_sample_rate_hz": inferred_sample_rate,
            **checks,
            "automatic_exclusion": False,
            "final_test_read": False,
        })
    if frequency is None or valid is None:
        raise P04T4BaselineFollowupInputError("follow-up preprocessing produced no curves")
    return frequency, valid, curves, qc_rows, dates


def _condition_matrix_followup(curves: Mapping[str, FloatArray]) -> FloatArray:
    return np.vstack([curves[f"P04T4-BASERR-R{repeat:02d}"] for repeat in range(1, 7)])


def _bootstrap(
    matrices: Mapping[str, FloatArray],
    selected_indices: Mapping[str, NDArray[np.int64]],
    primary: BoolArray,
) -> dict[str, Any]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    keys = (
        "basec_to_baser_shape_rms_db",
        "basec_to_baserr_shape_rms_db",
        "baser_to_baserr_shape_rms_db",
        "i50_min_shape_rms_db",
        "i50_effect_min_pairwise_pearson",
        "baserr_recovery_ratio_vs_initial_return",
    )
    values = {key: np.empty(BOOTSTRAP_ITERATIONS, dtype=np.float64) for key in keys}
    for index in range(BOOTSTRAP_ITERATIONS):
        reps: dict[str, FloatArray] = {}
        for condition in CONDITIONS:
            subset = matrices[condition][selected_indices[condition]]
            draw = rng.integers(0, subset.shape[0], subset.shape[0])
            reps[condition] = np.median(subset[draw], axis=0)
        metrics = compute_baseline_followup_metrics(reps, primary)
        for key in keys:
            values[key][index] = metrics[key]
    return {
        "iterations": BOOTSTRAP_ITERATIONS,
        "seed": BOOTSTRAP_SEED,
        "unit": "complete repeat curve within condition",
        "frequency_bootstrap": False,
        "ci95": {key: np.percentile(value, [2.5, 97.5]).tolist() for key, value in values.items()},
        "probability_baserr_closer_to_basec_than_baser_is": float(
            np.mean(values["basec_to_baserr_shape_rms_db"] < values["basec_to_baser_shape_rms_db"])
        ),
        "probability_i50_min_effect_above_1p396": float(
            np.mean(values["i50_min_shape_rms_db"] >= P04_LOCAL_REFERENCE_DB)
        ),
        "probability_i50_min_similarity_ge_0p60": float(
            np.mean(values["i50_effect_min_pairwise_pearson"] >= MIN_EFFECT_SIMILARITY)
        ),
    }


def run_p04t4_baseline_followup_analysis(
    original_batch_root: str | Path,
    followup_batch_root: str | Path,
    output_directory: str | Path,
) -> FollowupRunResult:
    original_batch = Path(original_batch_root).resolve()
    followup_batch = Path(followup_batch_root).resolve()
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"follow-up output already exists: {output}")

    try:
        original_members, _, original_zip_sha = _inspect_inputs(original_batch)
        frequency, valid, original_curves, original_qc, original_dates = _preprocess_members(original_members)
    except P04T4InputError as exc:
        raise P04T4BaselineFollowupInputError(str(exc)) from exc
    followup_members, source_zip, followup_zip_sha = _inspect_followup_inputs(followup_batch)
    followup_frequency, followup_valid, followup_curves, followup_qc, followup_dates = _preprocess_followup(
        followup_members
    )
    if not np.array_equal(frequency, followup_frequency) or not np.array_equal(valid, followup_valid):
        raise P04T4BaselineFollowupInputError("original and follow-up processed grids differ")

    output.mkdir(parents=True, exist_ok=False)
    primary = valid & (frequency >= 200.0) & (frequency <= 4000.0)
    secondary = valid & (frequency > 4000.0) & (frequency <= 8000.0)
    matrices = {
        "BASEC": _condition_matrix("BASEC", original_curves),
        "I50PC": _condition_matrix("I50PC", original_curves),
        "BASER": _condition_matrix("BASER", original_curves),
        "BASERR": _condition_matrix_followup(followup_curves),
    }

    selected_indices: dict[str, NDArray[np.int64]] = {}
    selection_rows: list[dict[str, Any]] = []
    repeatability_rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        repeats = np.arange(1, 7, dtype=np.int64)
        selected, flagged, distances = select_closest_repeats(
            matrices[condition], repeat_numbers=repeats, analysis_mask=primary, keep=4
        )
        selected_indices[condition] = selected - 1
        for repeat, distance in zip(repeats, distances, strict=True):
            selection_rows.append({
                "sample_id": f"P04T4-{condition}-R{repeat:02d}",
                "condition": condition,
                "repeat_number": int(repeat),
                "rms_to_all6_median_primary_db": float(distance),
                "primary_selected_4of6": bool(repeat in selected),
                "flagged_not_deleted": bool(repeat in flagged),
                "automatic_exclusion": False,
            })
        for scope, subset in (("selected4", matrices[condition][selected - 1]), ("all6", matrices[condition])):
            primary_pairs = _pairwise_rms(subset, primary)
            secondary_pairs = _pairwise_rms(subset, secondary)
            repeatability_rows.append({
                "condition": condition,
                "scope": scope,
                "repeat_count": int(subset.shape[0]),
                "median_pairwise_primary_rms_db": float(np.median(primary_pairs)),
                "max_pairwise_primary_rms_db": float(np.max(primary_pairs)),
                "median_pairwise_secondary_rms_db": float(np.median(secondary_pairs)),
                "max_pairwise_secondary_rms_db": float(np.max(secondary_pairs)),
            })

    original_local_ceiling = max(
        row["max_pairwise_primary_rms_db"]
        for row in repeatability_rows
        if row["scope"] == "all6" and row["condition"] != "BASERR"
    )
    representatives = {
        scope: {
            condition: np.median(
                matrices[condition][selected_indices[condition]] if scope == "selected4" else matrices[condition],
                axis=0,
            )
            for condition in CONDITIONS
        }
        for scope in ("selected4", "all6")
    }
    metrics = {
        scope: compute_baseline_followup_metrics(representatives[scope], primary)
        for scope in ("selected4", "all6")
    }
    classification = classify_baseline_pattern(
        metrics["selected4"], within_condition_ceiling_db=original_local_ceiling
    )
    bootstrap = _bootstrap(matrices, selected_indices, primary)

    all_dates = {**original_dates, **followup_dates}
    midpoints = {
        condition: min(date for sample, date in all_dates.items() if f"-{condition}-" in sample)
        + (
            max(date for sample, date in all_dates.items() if f"-{condition}-" in sample)
            - min(date for sample, date in all_dates.items() if f"-{condition}-" in sample)
        ) / 2
        for condition in CONDITIONS
    }
    first_last = {
        condition: (
            min(date for sample, date in all_dates.items() if f"-{condition}-" in sample),
            max(date for sample, date in all_dates.items() if f"-{condition}-" in sample),
        )
        for condition in CONDITIONS
    }
    chronology_rows = []
    for condition in CONDITIONS:
        first, last = first_last[condition]
        chronology_rows.append({
            "condition": condition,
            "first_timestamp": first.isoformat(sep=" "),
            "last_timestamp": last.isoformat(sep=" "),
            "midpoint_timestamp": midpoints[condition].isoformat(sep=" "),
            "minutes_from_basec_midpoint": (
                midpoints[condition] - midpoints["BASEC"]
            ).total_seconds() / 60.0,
        })

    metric_rows = []
    for scope in ("selected4", "all6"):
        row = {
            "scope": scope,
            "original_p04t4_all6_within_condition_ceiling_db": original_local_ceiling,
            **metrics[scope],
        }
        if scope == "selected4":
            for key, ci in bootstrap["ci95"].items():
                row[f"{key}_bootstrap_ci95_low"] = ci[0]
                row[f"{key}_bootstrap_ci95_high"] = ci[1]
            row.update({key: value for key, value in bootstrap.items() if key.startswith("probability_")})
        metric_rows.append(row)

    pair_rows = []
    for scope in ("selected4", "all6"):
        rep = representatives[scope]
        for left, right in itertools.combinations(BASELINE_CONDITIONS, 2):
            difference = rep[right] - rep[left]
            shape = _demean(difference, primary)
            pair_rows.append({
                "scope": scope,
                "left": left,
                "right": right,
                "midpoint_time_difference_minutes": (
                    midpoints[right] - midpoints[left]
                ).total_seconds() / 60.0,
                "primary_raw_rms_db": _rms(difference, primary),
                "primary_shape_rms_db": _rms(shape, primary),
                "primary_spectral_pearson": _correlation(rep[left][primary], rep[right][primary]),
                "primary_spectral_cosine": _cosine(rep[left][primary], rep[right][primary]),
                "causal_attribution": "not identifiable: time, environment, and reassembly changed jointly",
            })

    effect_rows = []
    spectra_rows = []
    for scope in ("selected4", "all6"):
        rep = representatives[scope]
        effects = {
            baseline: _demean(rep["I50PC"] - rep[baseline], primary)
            for baseline in BASELINE_CONDITIONS
        }
        for baseline, effect in effects.items():
            effect_rows.append({
                "scope": scope,
                "baseline": baseline,
                "primary_shape_rms_db": _rms(effect, primary),
                "pearson_vs_effect_using_basec": _correlation(
                    effect[primary], effects["BASEC"][primary]
                ),
                "cosine_vs_effect_using_basec": _cosine(
                    effect[primary], effects["BASEC"][primary]
                ),
            })
    selected = representatives["selected4"]
    selected_effects = {
        baseline: _demean(selected["I50PC"] - selected[baseline], primary)
        for baseline in BASELINE_CONDITIONS
    }
    for index, hz in enumerate(frequency):
        spectra_rows.append({
            "frequency_hz": float(hz),
            "valid": bool(valid[index]),
            "basec_selected4_db": float(selected["BASEC"][index]),
            "baser_selected4_db": float(selected["BASER"][index]),
            "baserr_selected4_db": float(selected["BASERR"][index]),
            "i50pc_selected4_db": float(selected["I50PC"][index]),
            "baser_minus_basec_shape_db": float(_demean(selected["BASER"] - selected["BASEC"], primary)[index]),
            "baserr_minus_basec_shape_db": float(_demean(selected["BASERR"] - selected["BASEC"], primary)[index]),
            "baserr_minus_baser_shape_db": float(_demean(selected["BASERR"] - selected["BASER"], primary)[index]),
            "i50_vs_basec_shape_db": float(selected_effects["BASEC"][index]),
            "i50_vs_baser_shape_db": float(selected_effects["BASER"][index]),
            "i50_vs_baserr_shape_db": float(selected_effects["BASERR"][index]),
        })

    source_rows = [{
        "relative_path": member.path.relative_to(followup_batch).as_posix(),
        "condition": "BASERR",
        "repeat_number": member.repeat_number,
        "extension": member.extension,
        "size_bytes": member.size_bytes,
        "sha256": member.sha256,
    } for member in followup_members]
    source_rows.append({
        "relative_path": source_zip.relative_to(followup_batch).as_posix(),
        "condition": "SOURCE_ARCHIVE",
        "repeat_number": "NA",
        "extension": ".zip",
        "size_bytes": source_zip.stat().st_size,
        "sha256": followup_zip_sha,
    })
    _write_csv(followup_batch / "metadata" / "source_manifest.csv", source_rows, list(source_rows[0]))
    _write_csv(output / "source_manifest.csv", source_rows, list(source_rows[0]))
    _write_csv(output / "qc_table.csv", followup_qc, list(followup_qc[0]))
    _write_csv(output / "repeat_selection.csv", selection_rows, list(selection_rows[0]))
    _write_csv(output / "repeatability.csv", repeatability_rows, list(repeatability_rows[0]))
    _write_csv(output / "chronology.csv", chronology_rows, list(chronology_rows[0]))
    _write_csv(output / "baseline_pairwise_comparison.csv", pair_rows, list(pair_rows[0]))
    _write_csv(output / "i50_effect_by_baseline.csv", effect_rows, list(effect_rows[0]))
    _write_csv(output / "followup_metrics.csv", metric_rows, list(metric_rows[0]))
    _write_csv(output / "representative_spectra.csv", spectra_rows, list(spectra_rows[0]))

    summary = {
        "schema_version": P04T4_FOLLOWUP_SCHEMA_VERSION,
        "classification": classification,
        "data_origin": "real_experiment",
        "dataset_role": "supplemental_baseline_reassembly_followup",
        "original_p04t4_source_zip_sha256": original_zip_sha,
        "followup_source_zip_sha256": followup_zip_sha,
        "counts": {"new_txt": 6, "new_mdat": 6, "combined_txt": 24},
        "selection": {
            condition: {
                "selected_repeats": [int(index + 1) for index in selected_indices[condition]],
                "flagged_not_deleted": [
                    repeat for repeat in range(1, 7)
                    if repeat not in {int(index + 1) for index in selected_indices[condition]}
                ],
            }
            for condition in CONDITIONS
        },
        "preprocessing": {
            "frequency_band_hz": [200.0, 8000.0],
            "grid": "48 PPo logarithmic",
            "smoothing": "1/12-octave dB smoothing",
            "primary_band_hz": [200.0, 4000.0],
            "secondary_band_hz": [4000.0, 8000.0],
        },
        "original_local_repeatability_ceiling_db": original_local_ceiling,
        "selected4_metrics": metrics["selected4"],
        "all6_metrics": metrics["all6"],
        "bootstrap": bootstrap,
        "identifiability": {
            "baseline_trajectory_observable": True,
            "assembly_time_environment_separable": False,
            "reason": "BASERR was acquired later and after reassembly under a potentially changed room/environment state",
        },
        "final_test_read": False,
        "automatic_exclusion": False,
        "new_comsol_solves": 0,
    }
    (output / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    (output / "scientific_classification.json").write_text(
        json.dumps({
            "classification": classification,
            "baseline_causal_attribution": "not_identifiable",
            "i50_effect_robust_across_three_baseline_references": (
                metrics["selected4"]["i50_min_shape_rms_db"] >= P04_LOCAL_REFERENCE_DB
                and metrics["selected4"]["i50_effect_min_pairwise_pearson"] >= MIN_EFFECT_SIMILARITY
            ),
            "final_test_read": False,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_mask = primary
    fig, ax = plt.subplots(figsize=(10, 5.6))
    for condition, label in (("BASEC", "BASE-C 20:16"), ("BASER", "BASE-R 20:28"), ("BASERR", "BASE-RR 20:54")):
        ax.semilogx(frequency[plot_mask], selected[condition][plot_mask], linewidth=1.6, label=label)
    ax.set(xlabel="Frequency (Hz)", ylabel="Smoothed SPL (dB)", title="Three sequential BASE representatives")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "baseline_trajectory_200_4000.png", dpi=180)
    fig.savefig(output / "baseline_trajectory_200_4000.svg")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.6))
    for baseline, label in (("BASEC", "I50P − BASE-C"), ("BASER", "I50P − BASE-R"), ("BASERR", "I50P − BASE-RR")):
        ax.semilogx(frequency[plot_mask], selected_effects[baseline][plot_mask], linewidth=1.6, label=label)
    ax.axhline(P04_LOCAL_REFERENCE_DB, color="grey", linestyle="--", linewidth=1)
    ax.axhline(-P04_LOCAL_REFERENCE_DB, color="grey", linestyle="--", linewidth=1)
    ax.set(xlabel="Frequency (Hz)", ylabel="Demeaned effect (dB)", title="I50P effect under three BASE references")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "i50_effect_three_baselines.png", dpi=180)
    fig.savefig(output / "i50_effect_three_baselines.svg")
    plt.close(fig)

    targets = sorted(path for path in output.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt")
    with (output / "SHA256SUMS.txt").open("w", encoding="utf-8", newline="\n") as handle:
        for path in targets:
            handle.write(f"{_sha256_file(path)}  {path.name}\n")
    return FollowupRunResult(output, classification, 24, len(targets) + 1)

