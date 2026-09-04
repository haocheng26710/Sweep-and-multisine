"""TRANS-1 compact two-port physical pilot analysis.

The pilot uses every acquired repeat: N x6, S x6, and N-return x3.  The
frozen FORMAL-1 preprocessing contract is retained.  Frequency bins are never
resampled as independent observations; uncertainty is obtained by resampling
whole repeat curves within acquisition condition.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping, Sequence
import zipfile

import numpy as np
from numpy.typing import NDArray

from .formal_preprocessing import (
    frozen_formal_preprocessing_contract,
    preprocess_formal_sweep,
)
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

TRANS1_PILOT_SCHEMA_VERSION = "trans1_two_port_physical_pilot_v1"
TRANS1_SOURCE_ZIP_SHA256 = "af68c8cb235500d72dd96b0a5cbdc6d09c4f436fec2307038e82c19951193a02"
CONDITIONS = ("N", "S", "NRETURN")
EXPECTED_REPEATS = {"N": 6, "S": 6, "NRETURN": 3}
HISTORICAL_CONT_P95_DB = 0.8793
P04_LOCAL_FLOOR_DB = 1.396
WINDOW_PAIRS = {
    "frozen_module_targets": (1850.0, 3800.0),
    "r256_localized_modes": (1538.0, 4170.0),
}
_NAME = re.compile(
    r"^R TRANS_(?P<condition>NRETURN|N|S)_(?P<repeat>0[1-9])(?P<extension>\.txt|\.mdat)$"
)


class Trans1InputError(ValueError):
    """Raised when TRANS-1 pilot identity, provenance, or QC fails closed."""


@dataclass(frozen=True, slots=True)
class Trans1Member:
    path: Path
    filename: str
    condition: str
    repeat_number: int
    extension: str
    sha256: str
    size_bytes: int

    @property
    def sample_id(self) -> str:
        return f"TRANS1-{self.condition}-R{self.repeat_number:02d}"


@dataclass(frozen=True, slots=True)
class Trans1RunResult:
    output_directory: Path
    measurement_count: int
    artifact_count: int
    classification: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_trans1_filename(filename: str) -> tuple[str, int]:
    match = _NAME.fullmatch(filename)
    if match is None:
        raise Trans1InputError(f"cannot reliably identify TRANS-1 condition/repeat: {filename}")
    return match.group("condition"), int(match.group("repeat"))


def directional_contrast(
    north: FloatArray,
    south: FloatArray,
    low_mask: BoolArray,
    high_mask: BoolArray,
) -> float:
    """Return (N_low-N_high) - (S_low-S_high), in dB."""
    return float(
        (np.mean(north[low_mask]) - np.mean(north[high_mask]))
        - (np.mean(south[low_mask]) - np.mean(south[high_mask]))
    )


def classify_trans1_pilot(
    *,
    direction_effect_rms_db: float,
    repeatability_floor_db: float,
    return_drift_rms_db: float,
    return_effect_correlation: float,
    fixed_window_supported: bool,
) -> str:
    if direction_effect_rms_db <= repeatability_floor_db:
        return "TWO_PORT_SELECTIVITY_NOT_SUPPORTED"
    if direction_effect_rms_db <= return_drift_rms_db:
        return "TWO_PORT_EFFECT_CONFOUNDED_BY_RETURN_DRIFT"
    if return_effect_correlation >= 0.8 and fixed_window_supported:
        return "TWO_PORT_SELECTIVE_ENCODING_SUPPORTED_WITH_LIMITS"
    return "TWO_PORT_SPECTRAL_DIFFERENCE_WITHOUT_STABLE_CODE"


def _inspect_inputs(batch_root: Path) -> tuple[list[Trans1Member], Path, str]:
    archives = list((batch_root / "source").glob("*.zip"))
    if len(archives) != 1:
        raise Trans1InputError(f"requires exactly one source ZIP; found {len(archives)}")
    source_zip = archives[0]
    zip_sha = _sha256_file(source_zip)
    if zip_sha != TRANS1_SOURCE_ZIP_SHA256:
        raise Trans1InputError(f"source ZIP SHA mismatch: {zip_sha}")

    members: list[Trans1Member] = []
    for directory, extension in ((batch_root / "raw_txt", ".txt"), (batch_root / "raw_mdat", ".mdat")):
        files = sorted(path for path in directory.iterdir() if path.is_file())
        if len(files) != 15:
            raise Trans1InputError(f"expected 15 {extension} files; found {len(files)}")
        for path in files:
            condition, repeat = parse_trans1_filename(path.name)
            if path.suffix.casefold() != extension:
                raise Trans1InputError(f"extension mismatch: {path.name}")
            if repeat > EXPECTED_REPEATS[condition]:
                raise Trans1InputError(f"out-of-range repeat: {path.name}")
            members.append(Trans1Member(
                path=path,
                filename=path.name,
                condition=condition,
                repeat_number=repeat,
                extension=extension,
                sha256=_sha256_file(path),
                size_bytes=path.stat().st_size,
            ))

    for extension in (".txt", ".mdat"):
        actual = {(m.condition, m.repeat_number) for m in members if m.extension == extension}
        expected = {
            (condition, repeat)
            for condition, count in EXPECTED_REPEATS.items()
            for repeat in range(1, count + 1)
        }
        if actual != expected:
            raise Trans1InputError(f"incomplete {extension} condition/repeat matrix")

    with zipfile.ZipFile(source_zip, "r") as archive:
        by_name: dict[str, tuple[int, str]] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise Trans1InputError(f"unsafe ZIP member: {info.filename}")
            if path.name in by_name:
                raise Trans1InputError(f"duplicate ZIP basename: {path.name}")
            payload = archive.read(info)
            by_name[path.name] = (len(payload), hashlib.sha256(payload).hexdigest())
    if len(by_name) != 30:
        raise Trans1InputError(f"source ZIP requires 30 files; found {len(by_name)}")
    for member in members:
        if by_name.get(member.filename) != (member.size_bytes, member.sha256):
            raise Trans1InputError(f"archived file differs from source ZIP: {member.filename}")
    return members, source_zip, zip_sha


def _measurement_meta(member: Trans1Member, reasons: Sequence[str]) -> MeasurementMeta:
    return MeasurementMeta(
        sample_id=member.sample_id,
        pipeline_version=PIPELINE_VERSION,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        measurement_schema_version=MEASUREMENT_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        device_version="TRANS_I2F_V1C_compact_two_port",
        configuration=member.condition,
        angle_deg={"N": 0.0, "S": 180.0, "NRETURN": 0.0}[member.condition],
        session_id="TRANS1-TWO-PORT-PILOT-20260827",
        repeat_type="CONT",
        repeat_id=f"R{member.repeat_number:02d}",
        experiment_step="TRANS1_TWO_PORT_PHYSICAL_PILOT",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=member.path.as_posix(),
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_ANALYSIS,
        source_sha256=member.sha256,
        provenance_uri=f"sha256:{TRANS1_SOURCE_ZIP_SHA256}#member={member.sha256}",
        eligible_for_scientific_analysis=False,
        assembly_id="TRANS1-V1C-SINGLE-CLOSE",
        acquisition_block_id=member.condition,
        valid=True,
        qc_status=QCStatus.WARNING if reasons else QCStatus.VALID,
        manual_review_reasons=tuple(reasons),
    )


def _preprocess_members(
    members: Sequence[Trans1Member],
) -> tuple[FloatArray, BoolArray, dict[str, FloatArray], list[dict[str, Any]], dict[str, datetime]]:
    curves: dict[str, FloatArray] = {}
    qc_rows: list[dict[str, Any]] = []
    dates: dict[str, datetime] = {}
    frequency: FloatArray | None = None
    valid_mask: BoolArray | None = None
    contract = frozen_formal_preprocessing_contract()
    order = {condition: index for index, condition in enumerate(CONDITIONS)}
    txt_members = sorted(
        (member for member in members if member.extension == ".txt"),
        key=lambda member: (order[member.condition], member.repeat_number),
    )
    for member in txt_members:
        parsed = _parse_rew_member(member.path.read_bytes(), member.filename)
        headers = parsed.headers["all"]
        note = parsed.headers.get("note", "")
        failures: list[str] = []
        format_ok = bool(re.search(
            r"Format:\s*256k Log Swept Sine,\s*1 sweep at -30\.0 dBFS with no timing reference",
            headers,
            re.I,
        ))
        identity_ok = f"Measurement: R TRANS_{member.condition}_{member.repeat_number:02d}" in headers
        note_ok = all(re.search(pattern, note, re.I) for pattern in (
            r"2 acoustic channels open",
            r"Windows out=50",
            r"mic input=100",
            r"speaker=6 o'clock",
            r"distance=0\.8 m",
        ))
        source_ok = "iMM-6C" in parsed.headers.get("source", "")
        inferred_sample_rate = float(np.median(np.diff(parsed.frequency_hz)) * 131072.0)
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
            "magnitude_only_no_timing_reference",
        ]
        reasons = sorted(set(failures if failures else warnings))
        spectrum = SpectrumData(
            frequency_hz=parsed.frequency_hz,
            magnitude_db=parsed.magnitude_db,
            valid_mask=np.ones(parsed.frequency_hz.size, dtype=bool),
            representation=Representation.DENSE_SPECTRUM,
            phase_status=PhaseStatus.UNAVAILABLE,
            quality_metrics={"trans1_qc_reasons": reasons, "inferred_sample_rate_hz": inferred_sample_rate},
            meta=_measurement_meta(member, reasons),
            magnitude_quantity="spl",
            magnitude_reference="REW frequency-response export",
        )
        result = preprocess_formal_sweep(spectrum, contract)
        if frequency is None:
            frequency = result.frequency_hz.copy()
            valid_mask = result.valid_mask.copy()
        elif not np.array_equal(frequency, result.frequency_hz) or not np.array_equal(valid_mask, result.valid_mask):
            raise Trans1InputError("preprocessed grids or masks differ")
        curves[member.sample_id] = result.magnitude_db.copy()
        dated = parsed.headers.get("dated", "").removeprefix("Dated:").strip()
        try:
            dates[member.sample_id] = datetime.strptime(dated, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise Trans1InputError(f"invalid Dated header: {member.filename}: {dated}") from exc
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
        raise Trans1InputError("preprocessing produced no curves")
    bad = [row["sample_id"] for row in qc_rows if not row["structural_valid"]]
    if bad:
        raise Trans1InputError(f"structural QC failed: {bad}")
    return frequency, valid_mask, curves, qc_rows, dates


def _condition_matrix(condition: str, curves: Mapping[str, FloatArray]) -> tuple[list[str], FloatArray]:
    ids = [f"TRANS1-{condition}-R{repeat:02d}" for repeat in range(1, EXPECTED_REPEATS[condition] + 1)]
    return ids, np.vstack([curves[sample] for sample in ids])


def _demean(values: FloatArray, mask: BoolArray) -> FloatArray:
    return values - float(np.mean(values[mask]))


def _rms(values: FloatArray, mask: BoolArray) -> float:
    return float(np.sqrt(np.mean(np.square(values[mask]))))


def _pairwise_rms(matrix: FloatArray, mask: BoolArray, *, demean: bool) -> list[float]:
    source = matrix.copy()
    if demean:
        source -= np.mean(source[:, mask], axis=1, keepdims=True)
    return [_rms(source[i] - source[j], mask) for i, j in itertools.combinations(range(source.shape[0]), 2)]


def _window_mask(frequency: FloatArray, valid: BoolArray, center_hz: float) -> BoolArray:
    return valid & (frequency >= center_hz * 2 ** (-1 / 6)) & (frequency <= center_hz * 2 ** (1 / 6))


def _correlation(a: FloatArray, b: FloatArray) -> float:
    if np.std(a) == 0.0 or np.std(b) == 0.0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _cosine(a: FloatArray, b: FloatArray) -> float:
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator else float("nan")


def _bootstrap(
    matrices: Mapping[str, FloatArray],
    frequency: FloatArray,
    valid: BoolArray,
    primary: BoolArray,
    *,
    iterations: int = 2000,
    seed: int = 270827,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    direction_rms = np.empty(iterations)
    return_direction_rms = np.empty(iterations)
    drift_rms = np.empty(iterations)
    effect_corr = np.empty(iterations)
    window_values: dict[str, dict[str, NDArray[np.float64]]] = {}
    for pair_name, (low, high) in WINDOW_PAIRS.items():
        window_values[pair_name] = {
            "contrast": np.empty(iterations),
            "return_contrast": np.empty(iterations),
            "low_n_minus_s": np.empty(iterations),
            "high_n_minus_s": np.empty(iterations),
        }
    for index in range(iterations):
        reps: dict[str, FloatArray] = {}
        for condition in CONDITIONS:
            matrix = matrices[condition]
            draw = rng.integers(0, matrix.shape[0], matrix.shape[0])
            reps[condition] = np.median(matrix[draw], axis=0)
        direction = _demean(reps["N"] - reps["S"], primary)
        return_direction = _demean(reps["NRETURN"] - reps["S"], primary)
        drift = _demean(reps["NRETURN"] - reps["N"], primary)
        direction_rms[index] = _rms(direction, primary)
        return_direction_rms[index] = _rms(return_direction, primary)
        drift_rms[index] = _rms(drift, primary)
        effect_corr[index] = _correlation(direction[primary], return_direction[primary])
        for pair_name, (low, high) in WINDOW_PAIRS.items():
            low_mask = _window_mask(frequency, valid, low)
            high_mask = _window_mask(frequency, valid, high)
            values = window_values[pair_name]
            values["contrast"][index] = directional_contrast(reps["N"], reps["S"], low_mask, high_mask)
            values["return_contrast"][index] = directional_contrast(reps["NRETURN"], reps["S"], low_mask, high_mask)
            values["low_n_minus_s"][index] = float(np.mean((reps["N"] - reps["S"])[low_mask]))
            values["high_n_minus_s"][index] = float(np.mean((reps["N"] - reps["S"])[high_mask]))
    return {
        "iterations": iterations,
        "seed": seed,
        "direction_effect_rms_db_ci95": np.percentile(direction_rms, [2.5, 97.5]).tolist(),
        "return_direction_effect_rms_db_ci95": np.percentile(return_direction_rms, [2.5, 97.5]).tolist(),
        "return_drift_rms_db_ci95": np.percentile(drift_rms, [2.5, 97.5]).tolist(),
        "return_effect_correlation_ci95": np.nanpercentile(effect_corr, [2.5, 97.5]).tolist(),
        "window_pairs": {
            pair_name: {
                key + "_ci95": np.percentile(array, [2.5, 97.5]).tolist()
                for key, array in values.items()
            }
            for pair_name, values in window_values.items()
        },
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


def run_trans1_two_port_physical_analysis(
    batch_root: str | Path,
    output_directory: str | Path,
) -> Trans1RunResult:
    batch = Path(batch_root).resolve()
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"TRANS-1 pilot output already exists: {output}")
    members, source_zip, zip_sha = _inspect_inputs(batch)
    frequency, valid, curves, qc_rows, dates = _preprocess_members(members)
    output.mkdir(parents=True, exist_ok=False)

    primary = valid & (frequency >= 200.0) & (frequency <= 4000.0)
    secondary = valid & (frequency > 4000.0) & (frequency <= 8000.0)
    matrices: dict[str, FloatArray] = {}
    representatives: dict[str, FloatArray] = {}
    repeatability_rows: list[dict[str, Any]] = []
    all_pairwise_shape: list[float] = []
    for condition in CONDITIONS:
        _, matrix = _condition_matrix(condition, curves)
        matrices[condition] = matrix
        representatives[condition] = np.median(matrix, axis=0)
        raw_primary = _pairwise_rms(matrix, primary, demean=False)
        shape_primary = _pairwise_rms(matrix, primary, demean=True)
        shape_secondary = _pairwise_rms(matrix, secondary, demean=True)
        all_pairwise_shape.extend(shape_primary)
        repeatability_rows.append({
            "condition": condition,
            "repeat_count": matrix.shape[0],
            "median_pairwise_primary_raw_rms_db": float(np.median(raw_primary)),
            "max_pairwise_primary_raw_rms_db": float(np.max(raw_primary)),
            "median_pairwise_primary_shape_rms_db": float(np.median(shape_primary)),
            "max_pairwise_primary_shape_rms_db": float(np.max(shape_primary)),
            "median_pairwise_secondary_shape_rms_db": float(np.median(shape_secondary)),
            "max_pairwise_secondary_shape_rms_db": float(np.max(shape_secondary)),
            "automatic_exclusion": False,
        })
    repeatability_floor = float(np.percentile(all_pairwise_shape, 95.0))

    n_minus_s_raw = representatives["N"] - representatives["S"]
    nr_minus_s_raw = representatives["NRETURN"] - representatives["S"]
    nr_minus_n_raw = representatives["NRETURN"] - representatives["N"]
    n_minus_s = _demean(n_minus_s_raw, primary)
    nr_minus_s = _demean(nr_minus_s_raw, primary)
    return_drift = _demean(nr_minus_n_raw, primary)
    direction_effect_rms = _rms(n_minus_s, primary)
    return_direction_effect_rms = _rms(nr_minus_s, primary)
    return_drift_rms = _rms(return_drift, primary)
    effect_corr = _correlation(n_minus_s[primary], nr_minus_s[primary])
    effect_cosine = _cosine(n_minus_s[primary], nr_minus_s[primary])
    bootstrap = _bootstrap(matrices, frequency, valid, primary)

    window_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    fixed_window_supported = False
    for pair_name, (low_center, high_center) in WINDOW_PAIRS.items():
        masks = {
            "low": _window_mask(frequency, valid, low_center),
            "high": _window_mask(frequency, valid, high_center),
        }
        for role, center in (("low", low_center), ("high", high_center)):
            mask = masks[role]
            boot_key = f"{role}_n_minus_s_ci95"
            ci = bootstrap["window_pairs"][pair_name][boot_key]
            window_rows.append({
                "window_pair": pair_name,
                "window_role": role,
                "center_hz": center,
                "window_low_hz": float(frequency[mask][0]),
                "window_high_hz": float(frequency[mask][-1]),
                "n_median_db": float(np.mean(representatives["N"][mask])),
                "s_median_db": float(np.mean(representatives["S"][mask])),
                "nreturn_median_db": float(np.mean(representatives["NRETURN"][mask])),
                "n_minus_s_db": float(np.mean(n_minus_s_raw[mask])),
                "nreturn_minus_s_db": float(np.mean(nr_minus_s_raw[mask])),
                "n_minus_s_bootstrap_ci95_low": ci[0],
                "n_minus_s_bootstrap_ci95_high": ci[1],
            })
        contrast = directional_contrast(representatives["N"], representatives["S"], masks["low"], masks["high"])
        return_contrast = directional_contrast(representatives["NRETURN"], representatives["S"], masks["low"], masks["high"])
        contrast_ci = bootstrap["window_pairs"][pair_name]["contrast_ci95"]
        return_ci = bootstrap["window_pairs"][pair_name]["return_contrast_ci95"]
        ci_excludes_zero = bool(contrast_ci[0] > 0.0 or contrast_ci[1] < 0.0)
        return_same_sign = bool(np.sign(contrast) == np.sign(return_contrast) and contrast != 0.0)
        supported = bool(
            ci_excludes_zero
            and abs(contrast) > repeatability_floor
            and return_same_sign
            and abs(return_contrast) > repeatability_floor
        )
        fixed_window_supported = fixed_window_supported or supported
        pair_rows.append({
            "window_pair": pair_name,
            "low_center_hz": low_center,
            "high_center_hz": high_center,
            "directional_contrast_db": contrast,
            "bootstrap_ci95_low": contrast_ci[0],
            "bootstrap_ci95_high": contrast_ci[1],
            "return_directional_contrast_db": return_contrast,
            "return_bootstrap_ci95_low": return_ci[0],
            "return_bootstrap_ci95_high": return_ci[1],
            "ci_excludes_zero": ci_excludes_zero,
            "return_same_sign": return_same_sign,
            "abs_contrast_exceeds_current_repeatability_p95": abs(contrast) > repeatability_floor,
            "supported_with_return_control": supported,
        })

    classification = classify_trans1_pilot(
        direction_effect_rms_db=direction_effect_rms,
        repeatability_floor_db=repeatability_floor,
        return_drift_rms_db=return_drift_rms,
        return_effect_correlation=effect_corr,
        fixed_window_supported=fixed_window_supported,
    )

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
    _write_csv(output / "source_manifest.csv", source_rows, list(source_rows[0].keys()))
    _write_csv(output / "qc_table.csv", qc_rows, list(qc_rows[0].keys()))
    _write_csv(output / "repeatability.csv", repeatability_rows, list(repeatability_rows[0].keys()))
    _write_csv(output / "fixed_window_effects.csv", window_rows, list(window_rows[0].keys()))
    _write_csv(output / "window_pair_selectivity.csv", pair_rows, list(pair_rows[0].keys()))

    metrics_rows = [{
        "direction_effect_primary_shape_rms_db": direction_effect_rms,
        "return_direction_effect_primary_shape_rms_db": return_direction_effect_rms,
        "return_drift_primary_shape_rms_db": return_drift_rms,
        "current_within_condition_pairwise_shape_p95_db": repeatability_floor,
        "effect_to_repeatability_ratio": direction_effect_rms / repeatability_floor,
        "effect_to_return_drift_ratio": direction_effect_rms / return_drift_rms,
        "return_effect_pearson": effect_corr,
        "return_effect_cosine": effect_cosine,
        "secondary_direction_effect_shape_rms_db": _rms(_demean(n_minus_s_raw, secondary), secondary),
        "historical_cont_p95_db": HISTORICAL_CONT_P95_DB,
        "p04_local_floor_db": P04_LOCAL_FLOOR_DB,
        "fixed_window_supported": fixed_window_supported,
        "classification": classification,
    }]
    _write_csv(output / "direction_effect_metrics.csv", metrics_rows, list(metrics_rows[0].keys()))

    spectra_rows = []
    for index, value in enumerate(frequency):
        spectra_rows.append({
            "frequency_hz": float(value),
            "valid": bool(valid[index]),
            "n_all6_median_db": float(representatives["N"][index]),
            "s_all6_median_db": float(representatives["S"][index]),
            "nreturn_all3_median_db": float(representatives["NRETURN"][index]),
            "n_minus_s_raw_db": float(n_minus_s_raw[index]),
            "n_minus_s_shape_db": float(n_minus_s[index]),
            "nreturn_minus_s_raw_db": float(nr_minus_s_raw[index]),
            "nreturn_minus_s_shape_db": float(nr_minus_s[index]),
            "nreturn_minus_n_shape_drift_db": float(return_drift[index]),
        })
    _write_csv(output / "representative_spectra.csv", spectra_rows, list(spectra_rows[0].keys()))

    chronological = [sample for sample, _ in sorted(dates.items(), key=lambda item: item[1])]
    summary = {
        "schema_version": TRANS1_PILOT_SCHEMA_VERSION,
        "classification": classification,
        "source_zip_sha256": zip_sha,
        "data_origin": "real_experiment",
        "dataset_role": "trans1_two_port_physical_pilot",
        "scientifically_eligible": False,
        "final_test_read": False,
        "counts": {"txt": 15, "mdat": 15, "N": 6, "S": 6, "NRETURN": 3},
        "all_repeats_retained": True,
        "automatic_exclusion": False,
        "preprocessing": frozen_formal_preprocessing_contract(),
        "window_pairs_frozen_before_analysis": WINDOW_PAIRS,
        "acquisition_order": chronological,
        "repeatability_floor": {
            "definition": "p95 of within-condition pairwise demeaned RMS over 200-4000 Hz",
            "value_db": repeatability_floor,
            "historical_cont_p95_db": HISTORICAL_CONT_P95_DB,
            "p04_local_floor_db": P04_LOCAL_FLOOR_DB,
        },
        "direction_effects": metrics_rows[0],
        "window_effects": window_rows,
        "window_pair_selectivity": pair_rows,
        "bootstrap": bootstrap,
        "conclusion_boundary": {
            "supported": (
                "single-close N/S state produces a repeatable magnitude-spectrum code beyond current repeatability and return drift"
                if classification == "TWO_PORT_SELECTIVE_ENCODING_SUPPORTED_WITH_LIMITS"
                else "see classification and component gates"
            ),
            "not_supported": [
                "generalization across independent assembly closures or rooms",
                "four-direction localization",
                "precise COMSOL prediction of measured peak locations",
                "phase, impulse-response, or multi-microphone information",
                "individual module causal contribution percentage",
            ],
        },
    }
    (output / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    (output / "preprocessing_contract.json").write_text(
        json.dumps(frozen_formal_preprocessing_contract(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def save_figure(fig: Any, stem: str) -> None:
        fig.tight_layout()
        fig.savefig(output / f"{stem}.png", dpi=180)
        fig.savefig(output / f"{stem}.svg")
        plt.close(fig)

    plot_mask = valid & (frequency >= 200.0) & (frequency <= 4000.0)
    fig, ax = plt.subplots(figsize=(10, 5.6))
    for condition, label, color in (
        ("N", "N initial (n=6)", "#4c78a8"),
        ("S", "S (n=6)", "#f58518"),
        ("NRETURN", "N return (n=3)", "#54a24b"),
    ):
        ax.semilogx(frequency[plot_mask], representatives[condition][plot_mask], label=label, color=color, linewidth=1.7)
    ax.set(xlabel="Frequency (Hz)", ylabel="Smoothed SPL (dB)", title="TRANS-1 two-port physical pilot representatives")
    ax.grid(True, which="both", alpha=0.25); ax.legend()
    save_figure(fig, "representative_spectra_200_4000")

    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.semilogx(frequency[plot_mask], n_minus_s[plot_mask], label="N − S", linewidth=1.8)
    ax.semilogx(frequency[plot_mask], nr_minus_s[plot_mask], label="N-return − S", linewidth=1.5)
    ax.axhline(repeatability_floor, color="grey", linestyle="--", linewidth=1, label="current repeatability p95")
    ax.axhline(-repeatability_floor, color="grey", linestyle="--", linewidth=1)
    for centers in WINDOW_PAIRS.values():
        for center in centers:
            ax.axvline(center, color="black", alpha=0.23, linestyle=":")
    ax.set(xlabel="Frequency (Hz)", ylabel="Demeaned spectral difference (dB)", title="Direction code and N-return sensitivity")
    ax.grid(True, which="both", alpha=0.25); ax.legend()
    save_figure(fig, "direction_effects_200_4000")

    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    labels = [row["window_pair"] for row in pair_rows]
    values = [row["directional_contrast_db"] for row in pair_rows]
    lower = [value - row["bootstrap_ci95_low"] for value, row in zip(values, pair_rows, strict=True)]
    upper = [row["bootstrap_ci95_high"] - value for value, row in zip(values, pair_rows, strict=True)]
    x = np.arange(len(values))
    ax.bar(x, values, color=["#4c78a8", "#f58518"])
    ax.errorbar(x, values, yerr=np.vstack([lower, upper]), fmt="none", ecolor="black", capsize=4)
    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_xticks(x, labels); ax.set(ylabel="Directional low–high contrast (dB)", title="Predeclared two-window code with repeat bootstrap CI")
    ax.grid(True, axis="y", alpha=0.25)
    save_figure(fig, "window_pair_selectivity")

    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    labels = ["Within-condition\np95", "N-return\ndrift", "N–S\neffect"]
    values = [repeatability_floor, return_drift_rms, direction_effect_rms]
    ax.bar(range(3), values, color=["#9d9da1", "#54a24b", "#e45756"])
    ax.set_xticks(range(3), labels); ax.set(ylabel="Primary-band demeaned RMS (dB)", title="Direction effect versus repeatability and return drift")
    ax.grid(True, axis="y", alpha=0.25)
    save_figure(fig, "effect_floor_return_comparison")

    targets = sorted(path for path in output.iterdir() if path.is_file() and path.name not in {"SHA256SUMS.txt", "artifact_inventory.json"})
    inventory = [{"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256_file(path)} for path in targets]
    (output / "artifact_inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    targets.append(output / "artifact_inventory.json")
    with (output / "SHA256SUMS.txt").open("w", encoding="utf-8", newline="\n") as handle:
        for path in sorted(targets):
            handle.write(f"{_sha256_file(path)}  {path.name}\n")
    return Trans1RunResult(output, 15, len(targets) + 1, classification)
