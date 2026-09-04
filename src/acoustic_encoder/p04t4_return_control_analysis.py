"""P04T4 bracketed return-control analysis for the integrated I50P insert.

All six consecutive repeats are retained.  The primary estimate uses the four
curves closest to each condition's all-six median over the frozen 200--4000 Hz
band, exactly as in P04T2.  The complete six-repeat result is a mandatory
sensitivity analysis.  Bootstrap resampling operates on complete repeat curves,
never on frequency bins.
"""

from __future__ import annotations

from collections import Counter
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

P04T4_SCHEMA_VERSION = "p04t4_return_control_confirmation_v1"
P04T4_SOURCE_ZIP_SHA256 = "ca0a8c7522e7b8f1f20747ead16144e6acdaccf624f40efe0257709c2459abeb"
P04T4_CONDITIONS = ("BASEC", "I50PC", "BASER")
P04T4_LANDMARKS_HZ = (1646.88357862959, 1986.97249931757)
SUP0_HISTORICAL_CONT_P95_DB = 0.8793
P04_LOCAL_REFERENCE_DB = 1.396
MIN_EFFECT_TO_RETURN_RATIO = 2.0
MIN_PRE_POST_SIMILARITY = 0.60
MIN_BOOTSTRAP_EFFECT_GT_RETURN_PROBABILITY = 0.975
BOOTSTRAP_ITERATIONS = 2000
BOOTSTRAP_SEED = 260826

_NAME = re.compile(
    r"^R P04T4_(?P<condition>BASEC|I50PC|BASER)_R(?P<repeat>0[1-6])"
    r"(?P<extension>\.txt|\.mdat)$"
)


class P04T4InputError(ValueError):
    """Raised when P04T4 identity, provenance, or processing fails closed."""


@dataclass(frozen=True, slots=True)
class P04T4Member:
    path: Path
    filename: str
    condition: str
    repeat_number: int
    extension: str
    sha256: str
    size_bytes: int

    @property
    def sample_id(self) -> str:
        return f"P04T4-{self.condition}-R{self.repeat_number:02d}"


@dataclass(frozen=True, slots=True)
class P04T4RunResult:
    output_directory: Path
    measurement_count: int
    selected_count: int
    artifact_count: int
    classification: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_p04t4_filename(filename: str) -> tuple[str, int]:
    match = _NAME.fullmatch(filename)
    if match is None:
        raise P04T4InputError(f"cannot reliably identify P04T4 condition/repeat: {filename}")
    return match.group("condition"), int(match.group("repeat"))


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


def _pairwise_rms(matrix: FloatArray, mask: BoolArray) -> list[float]:
    return [_rms(matrix[i] - matrix[j], mask) for i, j in itertools.combinations(range(matrix.shape[0]), 2)]


def _window_mask(frequency: FloatArray, valid: BoolArray, center_hz: float) -> BoolArray:
    return valid & (frequency >= center_hz * 2.0 ** (-1.0 / 24.0)) & (
        frequency <= center_hz * 2.0 ** (1.0 / 24.0)
    )


def select_closest_repeats(
    curves: FloatArray,
    *,
    repeat_numbers: NDArray[np.integer[Any]],
    analysis_mask: BoolArray,
    keep: int = 4,
) -> tuple[NDArray[np.int64], NDArray[np.int64], FloatArray]:
    matrix = np.asarray(curves, dtype=np.float64)
    repeats = np.asarray(repeat_numbers, dtype=np.int64)
    mask = np.asarray(analysis_mask, dtype=bool)
    if matrix.ndim != 2 or repeats.shape != (matrix.shape[0],):
        raise ValueError("curves/repeat_numbers shape mismatch")
    if keep <= 0 or keep >= matrix.shape[0] or not np.any(mask):
        raise ValueError("invalid objective repeat-selection contract")
    median = np.median(matrix, axis=0)
    distances = np.sqrt(np.mean(np.square(matrix[:, mask] - median[mask]), axis=1))
    order = np.lexsort((repeats, distances))
    selected = np.sort(repeats[order[:keep]])
    flagged = np.sort(repeats[order[keep:]])
    return selected, flagged, distances.astype(np.float64)


def compute_return_control_metrics(
    representatives: Mapping[str, FloatArray],
    primary_mask: BoolArray,
) -> dict[str, float]:
    base_c = np.asarray(representatives["BASEC"], dtype=np.float64)
    intervention = np.asarray(representatives["I50PC"], dtype=np.float64)
    base_r = np.asarray(representatives["BASER"], dtype=np.float64)
    mask = np.asarray(primary_mask, dtype=bool)
    if base_c.shape != intervention.shape or base_c.shape != base_r.shape or base_c.shape != mask.shape:
        raise ValueError("representative curve shapes differ")

    bracket = 0.5 * (base_c + base_r)
    return_raw = base_r - base_c
    return_shape = _demean(return_raw, mask)
    pre_raw = intervention - base_c
    post_raw = intervention - base_r
    bracket_raw = intervention - bracket
    pre_shape = _demean(pre_raw, mask)
    post_shape = _demean(post_raw, mask)
    bracket_shape = _demean(bracket_raw, mask)
    return_shape_rms = _rms(return_shape, mask)
    intervention_shape_rms = _rms(bracket_shape, mask)

    return {
        "base_return_raw_rms_db": _rms(return_raw, mask),
        "base_return_shape_rms_db": return_shape_rms,
        "i50p_vs_precursor_raw_rms_db": _rms(pre_raw, mask),
        "i50p_vs_precursor_shape_rms_db": _rms(pre_shape, mask),
        "i50p_vs_return_raw_rms_db": _rms(post_raw, mask),
        "i50p_vs_return_shape_rms_db": _rms(post_shape, mask),
        "i50p_bracket_raw_rms_db": _rms(bracket_raw, mask),
        "i50p_bracket_shape_rms_db": intervention_shape_rms,
        "effect_to_return_shape_ratio": (
            intervention_shape_rms / return_shape_rms if return_shape_rms > 1e-12 else float("inf")
        ),
        "pre_post_effect_pearson": _correlation(pre_shape[mask], post_shape[mask]),
        "pre_post_effect_cosine": _cosine(pre_shape[mask], post_shape[mask]),
        "base_return_below_historical_sup0_cont_p95": float(
            return_shape_rms <= SUP0_HISTORICAL_CONT_P95_DB
        ),
        "i50p_effect_above_p04_local_reference": float(
            intervention_shape_rms >= P04_LOCAL_REFERENCE_DB
        ),
    }


def classify_return_control(
    selected4: Mapping[str, float],
    all6: Mapping[str, float],
    bootstrap_effect_gt_return_probability: float,
    within_condition_repeatability_ceiling_db: float = 0.60,
) -> str:
    scopes = (selected4, all6)
    return_stable = all(
        row["base_return_shape_rms_db"] <= within_condition_repeatability_ceiling_db
        for row in scopes
    )
    effect_present = all(row["i50p_bracket_shape_rms_db"] >= P04_LOCAL_REFERENCE_DB for row in scopes)
    ratio_strong = all(row["effect_to_return_shape_ratio"] >= MIN_EFFECT_TO_RETURN_RATIO for row in scopes)
    pairing_stable = all(
        row["pre_post_effect_pearson"] >= MIN_PRE_POST_SIMILARITY
        and row["pre_post_effect_cosine"] >= MIN_PRE_POST_SIMILARITY
        for row in scopes
    )
    bootstrap_strong = (
        bootstrap_effect_gt_return_probability >= MIN_BOOTSTRAP_EFFECT_GT_RETURN_PROBABILITY
    )
    if return_stable and effect_present and ratio_strong and pairing_stable and bootstrap_strong:
        return "P04T4 REVERSIBLE_I50P_EFFECT_CONFIRMED_WITH_LIMITS"
    if effect_present and ratio_strong and pairing_stable and bootstrap_strong:
        return "P04T4 RETURN_CONTROL_SUPPORTS_EFFECT_WITH_ASSEMBLY_SENSITIVITY"
    if (
        any(row["effect_to_return_shape_ratio"] < 1.5 for row in scopes)
        or any(row["pre_post_effect_pearson"] < 0.30 for row in scopes)
        or bootstrap_effect_gt_return_probability < 0.90
    ):
        return "P04T4 ASSEMBLY_OR_TIME_DRIFT_CONFOUNDED"
    return "P04T4 I50P_EFFECT_NOT_ROBUSTLY_REPLICATED"


def _inspect_inputs(batch_root: Path) -> tuple[list[P04T4Member], Path, str]:
    archives = list((batch_root / "source").glob("*.zip"))
    if len(archives) != 1:
        raise P04T4InputError(f"P04T4 requires exactly one source ZIP; found {len(archives)}")
    source_zip = archives[0]
    zip_sha = _sha256_file(source_zip)
    if zip_sha != P04T4_SOURCE_ZIP_SHA256:
        raise P04T4InputError(f"P04T4 source ZIP SHA mismatch: {zip_sha}")

    members: list[P04T4Member] = []
    for directory, extension in ((batch_root / "raw_txt", ".txt"), (batch_root / "raw_mdat", ".mdat")):
        files = sorted(path for path in directory.iterdir() if path.is_file())
        if len(files) != 18:
            raise P04T4InputError(f"expected 18 {extension} files in {directory}; found {len(files)}")
        for path in files:
            condition, repeat = parse_p04t4_filename(path.name)
            if path.suffix.casefold() != extension:
                raise P04T4InputError(f"extension mismatch: {path.name}")
            members.append(P04T4Member(
                path=path,
                filename=path.name,
                condition=condition,
                repeat_number=repeat,
                extension=extension,
                sha256=_sha256_file(path),
                size_bytes=path.stat().st_size,
            ))

    expected = {(condition, repeat) for condition in P04T4_CONDITIONS for repeat in range(1, 7)}
    for extension in (".txt", ".mdat"):
        actual = {(member.condition, member.repeat_number) for member in members if member.extension == extension}
        if actual != expected:
            raise P04T4InputError(f"incomplete P04T4 {extension} condition/repeat matrix")
    if Counter(member.condition for member in members if member.extension == ".txt") != Counter(
        {condition: 6 for condition in P04T4_CONDITIONS}
    ):
        raise P04T4InputError("P04T4 condition counts mismatch")

    with zipfile.ZipFile(source_zip, "r") as archive:
        zip_members: dict[str, tuple[int, str]] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise P04T4InputError(f"unsafe ZIP member: {info.filename}")
            name = path.name
            if name in zip_members:
                raise P04T4InputError(f"duplicate ZIP basename: {name}")
            parse_p04t4_filename(name)
            payload = archive.read(info)
            zip_members[name] = (len(payload), hashlib.sha256(payload).hexdigest())
    if len(zip_members) != 36:
        raise P04T4InputError(f"source ZIP requires 36 files; found {len(zip_members)}")
    for member in members:
        if zip_members.get(member.filename) != (member.size_bytes, member.sha256):
            raise P04T4InputError(f"extracted file differs from source ZIP: {member.filename}")
    return members, source_zip, zip_sha


def _measurement_meta(member: P04T4Member, reasons: Sequence[str]) -> MeasurementMeta:
    assembly_map = {"BASEC": "C01", "I50PC": "C02", "BASER": "R01"}
    return MeasurementMeta(
        sample_id=member.sample_id,
        pipeline_version=PIPELINE_VERSION,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        measurement_schema_version=MEASUREMENT_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        device_version="V2.5_P04T4_return_control",
        configuration=member.condition,
        angle_deg=0.0,
        session_id="P04T4-RETURN-20260826",
        repeat_type="CONT",
        repeat_id=f"R{member.repeat_number:02d}",
        experiment_step="P04T4_RETURN_CONTROL_CONFIRMATION",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=member.path.as_posix(),
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_ANALYSIS,
        source_sha256=member.sha256,
        provenance_uri=f"sha256:{P04T4_SOURCE_ZIP_SHA256}#member={member.sha256}",
        eligible_for_scientific_analysis=False,
        assembly_id=assembly_map[member.condition],
        acquisition_block_id=member.condition,
        valid=True,
        qc_status=QCStatus.WARNING if reasons else QCStatus.VALID,
        manual_review_reasons=tuple(reasons),
    )


def _preprocess_members(
    members: Sequence[P04T4Member],
) -> tuple[FloatArray, BoolArray, dict[str, FloatArray], list[dict[str, Any]], dict[str, datetime]]:
    txt_members = sorted(
        (member for member in members if member.extension == ".txt"),
        key=lambda member: (P04T4_CONDITIONS.index(member.condition), member.repeat_number),
    )
    curves: dict[str, FloatArray] = {}
    qc_rows: list[dict[str, Any]] = []
    dates: dict[str, datetime] = {}
    frequency: FloatArray | None = None
    valid_mask: BoolArray | None = None
    contract = frozen_formal_preprocessing_contract()
    for member in txt_members:
        parsed = _parse_rew_member(member.path.read_bytes(), member.filename)
        all_headers = parsed.headers["all"]
        failures: list[str] = []
        format_ok = bool(re.search(
            r"Format:\s*256k Log Swept Sine,\s*1 sweep at -30\.0 dBFS with no timing reference",
            all_headers,
            re.I,
        ))
        identity_ok = f"Measurement: R P04T4_{member.condition}_R{member.repeat_number:02d}" in all_headers
        note = parsed.headers.get("note", "")
        note_ok = all(re.search(pattern, note, re.I) for pattern in (
            r"1 acoustic channels open",
            r"Windows out=50",
            r"mic input=100",
            r"distance=0\.8 m",
        ))
        source_ok = "iMM-6C" in parsed.headers.get("source", "")
        differences = np.diff(parsed.frequency_hz)
        inferred_sample_rate = float(np.median(differences) * 131072.0)
        inferred_48k = abs(inferred_sample_rate - 48000.0) <= 2.0
        coverage_ok = parsed.frequency_hz[0] <= 200.0 and parsed.frequency_hz[-1] >= 7999.0
        for ok, code in (
            (format_ok, "rew_format_contract_mismatch"),
            (identity_ok, "measurement_header_identity_mismatch"),
            (note_ok, "fixed_note_settings_mismatch"),
            (source_ok, "microphone_source_not_iMM6C"),
            (inferred_48k, "sample_rate_not_consistent_with_48khz"),
            (coverage_ok, "frequency_coverage_mismatch"),
        ):
            if not ok:
                failures.append(code)
        warnings = [
            "calibration_filename_header_unavailable",
            "t0_at_ir_peak_header_unavailable",
            "clipping_unavailable_from_frequency_response_txt",
            "assembly_photo_and_manual_close_record_not_in_zip",
        ]
        reasons = sorted(set(failures if failures else warnings))
        meta = _measurement_meta(member, reasons)
        spectrum = SpectrumData(
            frequency_hz=parsed.frequency_hz,
            magnitude_db=parsed.magnitude_db,
            valid_mask=np.ones(parsed.frequency_hz.size, dtype=bool),
            representation=Representation.DENSE_SPECTRUM,
            phase_status=PhaseStatus.UNAVAILABLE,
            quality_metrics={"p04t4_qc_reasons": reasons, "inferred_sample_rate_hz": inferred_sample_rate},
            meta=meta,
            magnitude_quantity="spl",
            magnitude_reference="REW frequency-response export",
        )
        result = preprocess_formal_sweep(spectrum, contract)
        if frequency is None:
            frequency = result.frequency_hz.copy()
            valid_mask = result.valid_mask.copy()
        elif not np.array_equal(frequency, result.frequency_hz) or not np.array_equal(valid_mask, result.valid_mask):
            raise P04T4InputError("preprocessed P04T4 grids or masks differ")
        curves[member.sample_id] = result.magnitude_db.copy()
        dated = parsed.headers.get("dated", "").removeprefix("Dated:").strip()
        try:
            date = datetime.strptime(dated, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise P04T4InputError(f"invalid Dated header: {member.filename}: {dated}") from exc
        dates[member.sample_id] = date
        qc_rows.append({
            "sample_id": member.sample_id,
            "filename": member.filename,
            "condition": member.condition,
            "repeat_number": member.repeat_number,
            "dated_header": dated,
            "file_sha256": member.sha256,
            "size_bytes": member.size_bytes,
            "structural_valid": not failures,
            "qc_status": "fail" if failures else "warning",
            "reason_codes": reasons,
            "raw_point_count": int(parsed.frequency_hz.size),
            "frequency_min_hz": float(parsed.frequency_hz[0]),
            "frequency_max_hz": float(parsed.frequency_hz[-1]),
            "format_contract_ok": format_ok,
            "identity_ok": identity_ok,
            "note_contract_ok": note_ok,
            "source_iMM6C_ok": source_ok,
            "inferred_sample_rate_hz": inferred_sample_rate,
            "inferred_48k_ok": inferred_48k,
            "frequency_coverage_ok": coverage_ok,
            "automatic_exclusion": False,
            "final_test_read": False,
        })
    if frequency is None or valid_mask is None:
        raise P04T4InputError("P04T4 preprocessing produced no curves")
    bad = [row["sample_id"] for row in qc_rows if not row["structural_valid"]]
    if bad:
        raise P04T4InputError(f"P04T4 structural QC failed: {bad}")
    return frequency, valid_mask, curves, qc_rows, dates


def _condition_matrix(condition: str, curves: Mapping[str, FloatArray]) -> FloatArray:
    return np.vstack([curves[f"P04T4-{condition}-R{repeat:02d}"] for repeat in range(1, 7)])


def _bootstrap_metrics(
    matrices: Mapping[str, FloatArray],
    selected_indices: Mapping[str, NDArray[np.int64]],
    primary: BoolArray,
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    keys = [
        "base_return_raw_rms_db",
        "base_return_shape_rms_db",
        "i50p_bracket_raw_rms_db",
        "i50p_bracket_shape_rms_db",
        "effect_to_return_shape_ratio",
        "pre_post_effect_pearson",
        "pre_post_effect_cosine",
    ]
    values = {key: np.empty(iterations, dtype=np.float64) for key in keys}
    for index in range(iterations):
        representatives: dict[str, FloatArray] = {}
        for condition in P04T4_CONDITIONS:
            subset = matrices[condition][selected_indices[condition]]
            draw = rng.integers(0, subset.shape[0], subset.shape[0])
            representatives[condition] = np.median(subset[draw], axis=0)
        metrics = compute_return_control_metrics(representatives, primary)
        for key in keys:
            value = metrics[key]
            values[key][index] = 1e9 if not np.isfinite(value) else value
    return {
        "iterations": iterations,
        "seed": seed,
        "unit": "complete repeat curve within frozen condition",
        "frequency_bootstrap": False,
        "ci95": {key: np.percentile(value, [2.5, 97.5]).tolist() for key, value in values.items()},
        "effect_gt_return_probability": float(
            np.mean(values["i50p_bracket_shape_rms_db"] > values["base_return_shape_rms_db"])
        ),
        "effect_gt_2x_return_probability": float(
            np.mean(values["effect_to_return_shape_ratio"] >= MIN_EFFECT_TO_RETURN_RATIO)
        ),
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            })


def _scope_representatives(
    matrices: Mapping[str, FloatArray],
    selected_indices: Mapping[str, NDArray[np.int64]],
    scope: str,
) -> dict[str, FloatArray]:
    return {
        condition: np.median(
            matrices[condition][selected_indices[condition]] if scope == "selected4" else matrices[condition],
            axis=0,
        )
        for condition in P04T4_CONDITIONS
    }


def run_p04t4_return_control_analysis(
    batch_root: str | Path,
    output_directory: str | Path,
    *,
    p04t2_representative_spectra: str | Path | None = None,
) -> P04T4RunResult:
    batch = Path(batch_root).resolve()
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"P04T4 output already exists: {output}")
    members, source_zip, zip_sha = _inspect_inputs(batch)
    frequency, valid, curves, qc_rows, dates = _preprocess_members(members)
    output.mkdir(parents=True, exist_ok=False)

    primary = valid & (frequency >= 200.0) & (frequency <= 4000.0)
    secondary = valid & (frequency > 4000.0) & (frequency <= 8000.0)
    matrices = {condition: _condition_matrix(condition, curves) for condition in P04T4_CONDITIONS}
    selected_indices: dict[str, NDArray[np.int64]] = {}
    selection_rows: list[dict[str, Any]] = []
    repeatability_rows: list[dict[str, Any]] = []
    for condition in P04T4_CONDITIONS:
        repeats = np.arange(1, 7, dtype=np.int64)
        selected, flagged, distances = select_closest_repeats(
            matrices[condition], repeat_numbers=repeats, analysis_mask=primary, keep=4,
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
                "selection_rule": "four lowest RMS distances to all-six condition median over 200-4000 Hz",
                "automatic_exclusion": False,
            })
        for scope, subset in (
            ("selected4", matrices[condition][selected - 1]),
            ("all6", matrices[condition]),
        ):
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

    representatives = {
        scope: _scope_representatives(matrices, selected_indices, scope)
        for scope in ("selected4", "all6")
    }
    scope_metrics = {
        scope: compute_return_control_metrics(representatives[scope], primary)
        for scope in ("selected4", "all6")
    }
    bootstrap = _bootstrap_metrics(matrices, selected_indices, primary)
    within_condition_repeatability_ceiling_db = max(
        row["max_pairwise_primary_rms_db"]
        for row in repeatability_rows
        if row["scope"] == "all6"
    )
    classification = classify_return_control(
        scope_metrics["selected4"],
        scope_metrics["all6"],
        bootstrap["effect_gt_return_probability"],
        within_condition_repeatability_ceiling_db,
    )

    metric_rows: list[dict[str, Any]] = []
    for scope in ("selected4", "all6"):
        row: dict[str, Any] = {
            "scope": scope,
            "primary_band_low_hz": 200.0,
            "primary_band_high_hz": 4000.0,
            "observed_within_condition_repeatability_ceiling_db": (
                within_condition_repeatability_ceiling_db
            ),
            **scope_metrics[scope],
        }
        if scope == "selected4":
            for key, ci in bootstrap["ci95"].items():
                row[f"{key}_bootstrap_ci95_low"] = ci[0]
                row[f"{key}_bootstrap_ci95_high"] = ci[1]
            row["bootstrap_effect_gt_return_probability"] = bootstrap["effect_gt_return_probability"]
            row["bootstrap_effect_gt_2x_return_probability"] = bootstrap[
                "effect_gt_2x_return_probability"
            ]
        metric_rows.append(row)

    fixed_window_rows: list[dict[str, Any]] = []
    for scope in ("selected4", "all6"):
        rep = representatives[scope]
        bracket = 0.5 * (rep["BASEC"] + rep["BASER"])
        return_raw = rep["BASER"] - rep["BASEC"]
        intervention_raw = rep["I50PC"] - bracket
        return_shape = _demean(return_raw, primary)
        intervention_shape = _demean(intervention_raw, primary)
        for center in P04T4_LANDMARKS_HZ:
            mask = _window_mask(frequency, valid, center)
            point_index = int(np.argmin(np.abs(frequency - center)))
            fixed_window_rows.append({
                "scope": scope,
                "center_hz": center,
                "window_low_hz": float(frequency[mask][0]),
                "window_high_hz": float(frequency[mask][-1]),
                "point_frequency_hz": float(frequency[point_index]),
                "base_return_raw_window_db": float(np.mean(return_raw[mask])),
                "base_return_shape_window_db": float(np.mean(return_shape[mask])),
                "i50p_bracket_raw_window_db": float(np.mean(intervention_raw[mask])),
                "i50p_bracket_shape_window_db": float(np.mean(intervention_shape[mask])),
                "base_return_raw_point_db": float(return_raw[point_index]),
                "i50p_bracket_raw_point_db": float(intervention_raw[point_index]),
                "i50p_raw_point_abs_exceeds_1p396": bool(
                    abs(float(intervention_raw[point_index])) > P04_LOCAL_REFERENCE_DB
                ),
            })

    spectra_rows: list[dict[str, Any]] = []
    selected_rep = representatives["selected4"]
    all_rep = representatives["all6"]
    selected_bracket = 0.5 * (selected_rep["BASEC"] + selected_rep["BASER"])
    selected_return = selected_rep["BASER"] - selected_rep["BASEC"]
    selected_effect = selected_rep["I50PC"] - selected_bracket
    selected_return_shape = _demean(selected_return, primary)
    selected_effect_shape = _demean(selected_effect, primary)
    all_bracket = 0.5 * (all_rep["BASEC"] + all_rep["BASER"])
    all_return = all_rep["BASER"] - all_rep["BASEC"]
    all_effect = all_rep["I50PC"] - all_bracket
    all_return_shape = _demean(all_return, primary)
    all_effect_shape = _demean(all_effect, primary)
    for index, value in enumerate(frequency):
        spectra_rows.append({
            "frequency_hz": float(value),
            "valid": bool(valid[index]),
            "basec_selected4_median_db": float(selected_rep["BASEC"][index]),
            "i50pc_selected4_median_db": float(selected_rep["I50PC"][index]),
            "baser_selected4_median_db": float(selected_rep["BASER"][index]),
            "bracketed_base_selected4_db": float(selected_bracket[index]),
            "base_return_raw_selected4_db": float(selected_return[index]),
            "base_return_shape_selected4_db": float(selected_return_shape[index]),
            "i50p_bracket_raw_selected4_db": float(selected_effect[index]),
            "i50p_bracket_shape_selected4_db": float(selected_effect_shape[index]),
            "base_return_shape_all6_db": float(all_return_shape[index]),
            "i50p_bracket_shape_all6_db": float(all_effect_shape[index]),
        })

    replication_rows: list[dict[str, Any]] = []
    if p04t2_representative_spectra is not None:
        previous_path = Path(p04t2_representative_spectra).resolve()
        with previous_path.open("r", encoding="utf-8-sig", newline="") as handle:
            previous_rows = list(csv.DictReader(handle))
        previous_frequency = np.asarray([float(row["frequency_hz"]) for row in previous_rows])
        previous_shape = np.asarray([float(row["i50p_minus_base_shape_db"]) for row in previous_rows])
        if not np.array_equal(previous_frequency, frequency):
            raise P04T4InputError("P04T2/P04T4 processed frequency grids differ")
        replication_rows.append({
            "comparison": "P04T4_I50PC_bracket_vs_P04T2_I50PA",
            "band_low_hz": 200.0,
            "band_high_hz": 4000.0,
            "pearson": _correlation(selected_effect_shape[primary], previous_shape[primary]),
            "cosine": _cosine(selected_effect_shape[primary], previous_shape[primary]),
            "rms_difference_db": _rms(selected_effect_shape - previous_shape, primary),
            "p04t4_shape_rms_db": _rms(selected_effect_shape, primary),
            "p04t2_shape_rms_db": _rms(previous_shape, primary),
            "interpretation_scope": "cross-batch spectral-shape replication; not independent-day repeatability",
        })

    chronological = sorted(dates.items(), key=lambda item: item[1])
    ordered_conditions = [sample.split("-")[1] for sample, _ in chronological]
    expected_order = ["BASEC"] * 6 + ["I50PC"] * 6 + ["BASER"] * 6
    acquisition_order_ok = ordered_conditions == expected_order
    if not acquisition_order_ok:
        raise P04T4InputError(f"P04T4 acquisition order differs from frozen design: {ordered_conditions}")

    source_rows = [{
        "relative_path": member.path.relative_to(batch).as_posix(),
        "condition": member.condition,
        "repeat_number": member.repeat_number,
        "extension": member.extension,
        "size_bytes": member.size_bytes,
        "sha256": member.sha256,
    } for member in members]
    source_rows.append({
        "relative_path": source_zip.relative_to(batch).as_posix(),
        "condition": "SOURCE_ARCHIVE",
        "repeat_number": "NA",
        "extension": ".zip",
        "size_bytes": source_zip.stat().st_size,
        "sha256": zip_sha,
    })

    _write_csv(batch / "metadata" / "source_manifest.csv", source_rows, list(source_rows[0].keys()))
    _write_csv(output / "source_manifest.csv", source_rows, list(source_rows[0].keys()))
    _write_csv(output / "qc_table.csv", qc_rows, list(qc_rows[0].keys()))
    _write_csv(output / "repeat_selection.csv", selection_rows, list(selection_rows[0].keys()))
    _write_csv(output / "repeatability.csv", repeatability_rows, list(repeatability_rows[0].keys()))
    _write_csv(output / "return_control_metrics.csv", metric_rows, list(metric_rows[0].keys()))
    _write_csv(output / "fixed_window_effects.csv", fixed_window_rows, list(fixed_window_rows[0].keys()))
    _write_csv(output / "representative_spectra.csv", spectra_rows, list(spectra_rows[0].keys()))
    if replication_rows:
        _write_csv(output / "cross_batch_replication.csv", replication_rows, list(replication_rows[0].keys()))

    selection_summary = {
        condition: {
            "selected_repeats": [int(index + 1) for index in selected_indices[condition]],
            "flagged_not_deleted": [
                repeat for repeat in range(1, 7) if repeat not in set(index + 1 for index in selected_indices[condition])
            ],
        }
        for condition in P04T4_CONDITIONS
    }
    summary = {
        "schema_version": P04T4_SCHEMA_VERSION,
        "classification": classification,
        "source_zip_sha256": zip_sha,
        "data_origin": "real_experiment",
        "dataset_role": "supplemental_return_control_confirmation",
        "scientifically_eligible": False,
        "final_test_read": False,
        "counts": {"txt": 18, "mdat": 18, "conditions": 3, "repeats_per_condition": 6},
        "acquisition_order": [sample for sample, _ in chronological],
        "acquisition_order_ok": acquisition_order_ok,
        "first_timestamp": chronological[0][1].isoformat(sep=" "),
        "last_timestamp": chronological[-1][1].isoformat(sep=" "),
        "selection_rule": "objective 4-of-6 by lowest primary-band RMS distance to all-six condition median; all-six retained",
        "selection": selection_summary,
        "preprocessing": {
            "frequency_band_hz": [200.0, 8000.0],
            "grid": "48 PPo logarithmic",
            "smoothing": "1/12-octave dB smoothing",
            "primary_band_hz": [200.0, 4000.0],
            "secondary_band_hz": [4000.0, 8000.0],
        },
        "thresholds": {
            "observed_within_condition_all6_max_pairwise_primary_rms_db": (
                within_condition_repeatability_ceiling_db
            ),
            "sup0_historical_cont_p95_db_nonuniversal": SUP0_HISTORICAL_CONT_P95_DB,
            "p04_local_reference_db": P04_LOCAL_REFERENCE_DB,
            "minimum_effect_to_return_ratio": MIN_EFFECT_TO_RETURN_RATIO,
            "minimum_pre_post_effect_similarity": MIN_PRE_POST_SIMILARITY,
            "minimum_bootstrap_effect_gt_return_probability": MIN_BOOTSTRAP_EFFECT_GT_RETURN_PROBABILITY,
        },
        "selected4_metrics": scope_metrics["selected4"],
        "all6_metrics": scope_metrics["all6"],
        "bootstrap": bootstrap,
        "cross_batch_replication": replication_rows,
        "conclusion_boundary": {
            "supported": "I50P intervention produces a repeat-consistent within-session spectral-shape effect larger than bracketed baseline return drift, with measurable assembly sensitivity",
            "not_supported": [
                "independent-day or multi-operator repeatability",
                "precise COMSOL localization or amplitude validation",
                "direction classification or full U4 performance",
                "single-component causal contribution percentage",
            ],
        },
    }
    (output / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    classification_payload = {
        "schema_version": "p04t4_scientific_classification_v1",
        "classification": classification,
        "gates": {
            "input_identity_and_hash": True,
            "acquisition_order": acquisition_order_ok,
            "selected4_base_return_within_observed_repeatability_ceiling": (
                scope_metrics["selected4"]["base_return_shape_rms_db"]
                <= within_condition_repeatability_ceiling_db
            ),
            "all6_base_return_within_observed_repeatability_ceiling": (
                scope_metrics["all6"]["base_return_shape_rms_db"]
                <= within_condition_repeatability_ceiling_db
            ),
            "selected4_i50p_effect_above_1p396": (
                scope_metrics["selected4"]["i50p_bracket_shape_rms_db"] >= P04_LOCAL_REFERENCE_DB
            ),
            "all6_i50p_effect_above_1p396": (
                scope_metrics["all6"]["i50p_bracket_shape_rms_db"] >= P04_LOCAL_REFERENCE_DB
            ),
            "selected4_effect_to_return_ratio_ge_2": (
                scope_metrics["selected4"]["effect_to_return_shape_ratio"] >= MIN_EFFECT_TO_RETURN_RATIO
            ),
            "all6_effect_to_return_ratio_ge_2": (
                scope_metrics["all6"]["effect_to_return_shape_ratio"] >= MIN_EFFECT_TO_RETURN_RATIO
            ),
            "selected4_pre_post_similarity_ge_0p60": (
                scope_metrics["selected4"]["pre_post_effect_pearson"] >= MIN_PRE_POST_SIMILARITY
                and scope_metrics["selected4"]["pre_post_effect_cosine"] >= MIN_PRE_POST_SIMILARITY
            ),
            "all6_pre_post_similarity_ge_0p60": (
                scope_metrics["all6"]["pre_post_effect_pearson"] >= MIN_PRE_POST_SIMILARITY
                and scope_metrics["all6"]["pre_post_effect_cosine"] >= MIN_PRE_POST_SIMILARITY
            ),
            "bootstrap_effect_gt_return_probability_ge_0p975": (
                bootstrap["effect_gt_return_probability"]
                >= MIN_BOOTSTRAP_EFFECT_GT_RETURN_PROBABILITY
            ),
        },
        "final_test_read": False,
        "automatic_exclusion": False,
        "new_comsol_solves": 0,
    }
    (output / "scientific_classification.json").write_text(
        json.dumps(classification_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_mask = valid & (frequency >= 200.0) & (frequency <= 4000.0)
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.semilogx(frequency[plot_mask], selected_rep["BASEC"][plot_mask], label="BASE-C", linewidth=1.6)
    ax.semilogx(frequency[plot_mask], selected_rep["I50PC"][plot_mask], label="I50P-C", linewidth=1.6)
    ax.semilogx(frequency[plot_mask], selected_rep["BASER"][plot_mask], label="BASE-R", linewidth=1.6)
    ax.set(xlabel="Frequency (Hz)", ylabel="Smoothed SPL (dB)", title="P04T4 bracketed return-control representatives")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "representative_spectra_200_4000.png", dpi=180)
    fig.savefig(output / "representative_spectra_200_4000.svg")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.semilogx(frequency[plot_mask], selected_effect_shape[plot_mask], label="I50P − bracketed BASE", linewidth=1.8)
    ax.semilogx(frequency[plot_mask], selected_return_shape[plot_mask], label="BASE-R − BASE-C", linewidth=1.5)
    ax.axhline(P04_LOCAL_REFERENCE_DB, color="grey", linestyle="--", linewidth=1, label="±1.396 dB reference")
    ax.axhline(-P04_LOCAL_REFERENCE_DB, color="grey", linestyle="--", linewidth=1)
    ax.set(xlabel="Frequency (Hz)", ylabel="Demeaned spectral effect (dB)", title="Intervention effect versus return drift")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "intervention_vs_return_effect.png", dpi=180)
    fig.savefig(output / "intervention_vs_return_effect.svg")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.8, 5.1))
    values = [
        scope_metrics["selected4"]["base_return_shape_rms_db"],
        scope_metrics["selected4"]["i50p_bracket_shape_rms_db"],
    ]
    ci_return = bootstrap["ci95"]["base_return_shape_rms_db"]
    ci_effect = bootstrap["ci95"]["i50p_bracket_shape_rms_db"]
    lower = [values[0] - ci_return[0], values[1] - ci_effect[0]]
    upper = [ci_return[1] - values[0], ci_effect[1] - values[1]]
    ax.bar([0, 1], values, color=["#4c78a8", "#f58518"])
    ax.errorbar([0, 1], values, yerr=np.vstack([lower, upper]), fmt="none", ecolor="black", capsize=4)
    ax.axhline(
        within_condition_repeatability_ceiling_db,
        color="#54a24b",
        linestyle="--",
        label="Observed all-six within-condition ceiling",
    )
    ax.axhline(P04_LOCAL_REFERENCE_DB, color="grey", linestyle=":", label="P04 1.396 dB reference")
    ax.set_xticks([0, 1], ["BASE return", "I50P intervention"])
    ax.set(ylabel="Primary-band demeaned RMS (dB)", title="Return-control decision metrics")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "return_control_decision_metrics.png", dpi=180)
    fig.savefig(output / "return_control_decision_metrics.svg")
    plt.close(fig)

    manifest_targets = sorted(path for path in output.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt")
    with (output / "SHA256SUMS.txt").open("w", encoding="utf-8", newline="\n") as handle:
        for path in manifest_targets:
            handle.write(f"{_sha256_file(path)}  {path.name}\n")
    return P04T4RunResult(output, 18, 12, len(manifest_targets) + 1, classification)
