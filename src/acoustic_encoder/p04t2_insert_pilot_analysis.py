"""P04T2 integrated central-chamber insert pilot analysis.

The analysis keeps all six consecutive repeats.  Four repeats per condition are
selected solely by RMS distance to that condition's all-six median over the
frozen 200--4000 Hz primary band; the all-six result is retained as a mandatory
sensitivity analysis.  Frequency bins are never treated as independent samples.
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

P04T2_SCHEMA_VERSION = "p04t2_integrated_insert_pilot_v1"
P04T2_SOURCE_ZIP_SHA256 = "179b932bae0bb73980cebb8092d2f022ecb3c1e8d333896416076d270eb0c07d"
P04T2_LOCAL_FLOOR_DB = 1.396
P04T2_LANDMARKS_HZ = (1646.88357862959, 1986.97249931757)
P04T2_CONDITIONS = ("BASE0", "BASE1", "I75A", "I50PA")
P04T2_REALIZED_AIR_PERCENT = {"BASE": 100.0, "I75A": 75.82604198172172, "I50PA": 54.05870578763019}
_NAME = re.compile(
    r"^R P04T2_(?P<condition>BASE0|BASE1|I75A|I50PA)_"
    r"(?P<assembly>A0[1-4])_(?P<repeat>0[1-6])(?P<extension>\.txt|\.mdat)$"
)


class P04T2InputError(ValueError):
    """Raised when P04T2 identity, provenance, or processing fails closed."""


@dataclass(frozen=True, slots=True)
class P04T2Member:
    path: Path
    filename: str
    condition: str
    assembly_id: str
    repeat_number: int
    extension: str
    sha256: str
    size_bytes: int

    @property
    def sample_id(self) -> str:
        return f"P04T2-{self.condition}-{self.assembly_id}-R{self.repeat_number:02d}"


@dataclass(frozen=True, slots=True)
class P04T2RunResult:
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


def parse_p04t2_filename(filename: str) -> tuple[str, str, int]:
    match = _NAME.fullmatch(filename)
    if match is None:
        raise P04T2InputError(f"cannot reliably identify P04T2 condition/repeat: {filename}")
    return match.group("condition"), match.group("assembly"), int(match.group("repeat"))


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


def contiguous_frequency_bands(
    frequency_hz: FloatArray,
    mask: BoolArray,
    *,
    minimum_bins: int = 2,
) -> list[dict[str, Any]]:
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    indices = np.flatnonzero(np.asarray(mask, dtype=bool))
    if indices.size == 0:
        return []
    groups = np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
    return [
        {
            "low_hz": float(frequency[group[0]]),
            "high_hz": float(frequency[group[-1]]),
            "bin_count": int(group.size),
        }
        for group in groups
        if group.size >= minimum_bins
    ]


def _inspect_inputs(batch_root: Path) -> tuple[list[P04T2Member], Path, str]:
    source_archives = list((batch_root / "source").glob("*.zip"))
    if len(source_archives) != 1:
        raise P04T2InputError(f"P04T2 requires exactly one source ZIP; found {len(source_archives)}")
    source_zip = source_archives[0]
    zip_sha = _sha256_file(source_zip)
    if zip_sha != P04T2_SOURCE_ZIP_SHA256:
        raise P04T2InputError(f"P04T2 source ZIP SHA mismatch: {zip_sha}")

    members: list[P04T2Member] = []
    for directory, extension in ((batch_root / "raw_txt", ".txt"), (batch_root / "raw_mdat", ".mdat")):
        files = sorted(path for path in directory.iterdir() if path.is_file())
        if len(files) != 24:
            raise P04T2InputError(f"expected 24 {extension} files in {directory}; found {len(files)}")
        for path in files:
            condition, assembly, repeat = parse_p04t2_filename(path.name)
            if path.suffix.casefold() != extension:
                raise P04T2InputError(f"extension mismatch: {path.name}")
            members.append(P04T2Member(
                path=path,
                filename=path.name,
                condition=condition,
                assembly_id=assembly,
                repeat_number=repeat,
                extension=extension,
                sha256=_sha256_file(path),
                size_bytes=path.stat().st_size,
            ))

    expected = {(condition, repeat) for condition in P04T2_CONDITIONS for repeat in range(1, 7)}
    for extension in (".txt", ".mdat"):
        actual = {(m.condition, m.repeat_number) for m in members if m.extension == extension}
        if actual != expected:
            raise P04T2InputError(f"incomplete P04T2 {extension} condition/repeat matrix")
    if Counter(m.condition for m in members if m.extension == ".txt") != Counter({c: 6 for c in P04T2_CONDITIONS}):
        raise P04T2InputError("P04T2 condition counts mismatch")

    with zipfile.ZipFile(source_zip, "r") as archive:
        zip_files = [info for info in archive.infolist() if not info.is_dir()]
        by_name: dict[str, tuple[int, str]] = {}
        for info in zip_files:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise P04T2InputError(f"unsafe ZIP member: {info.filename}")
            name = path.name
            if name in by_name:
                raise P04T2InputError(f"duplicate ZIP basename: {name}")
            payload = archive.read(info)
            by_name[name] = (len(payload), hashlib.sha256(payload).hexdigest())
    if len(by_name) != 48:
        raise P04T2InputError(f"source ZIP requires 48 files; found {len(by_name)}")
    for member in members:
        if by_name.get(member.filename) != (member.size_bytes, member.sha256):
            raise P04T2InputError(f"extracted file differs from source ZIP: {member.filename}")
    return members, source_zip, zip_sha


def _measurement_meta(member: P04T2Member, reasons: Sequence[str]) -> MeasurementMeta:
    return MeasurementMeta(
        sample_id=member.sample_id,
        pipeline_version=PIPELINE_VERSION,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        measurement_schema_version=MEASUREMENT_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        device_version="V2.5_P04T2_integrated_insert",
        configuration=member.condition,
        angle_deg=0.0,
        session_id="P04T2-PILOT-20260826",
        repeat_type="CONT",
        repeat_id=f"R{member.repeat_number:02d}",
        experiment_step="P04T2_INTEGRATED_INSERT_PILOT",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=member.path.as_posix(),
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_ANALYSIS,
        source_sha256=member.sha256,
        provenance_uri=f"sha256:{P04T2_SOURCE_ZIP_SHA256}#member={member.sha256}",
        eligible_for_scientific_analysis=False,
        assembly_id=member.assembly_id,
        acquisition_block_id=member.condition,
        valid=True,
        qc_status=QCStatus.WARNING if reasons else QCStatus.VALID,
        manual_review_reasons=tuple(reasons),
    )


def _preprocess_members(
    members: Sequence[P04T2Member],
) -> tuple[FloatArray, BoolArray, dict[str, FloatArray], list[dict[str, Any]], dict[str, datetime]]:
    txt_members = sorted(
        (member for member in members if member.extension == ".txt"),
        key=lambda member: (P04T2_CONDITIONS.index(member.condition), member.repeat_number),
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
        identity_ok = f"Measurement: R P04T2_{member.condition}_{member.assembly_id}_{member.repeat_number:02d}" in all_headers
        note = parsed.headers.get("note", "")
        note_ok = all(re.search(pattern, note, re.I) for pattern in (
            r"1 acoustic channels open", r"Windows out=50", r"mic input=100", r"distance=0\.8 m",
        ))
        source_ok = "iMM-6C" in parsed.headers.get("source", "")
        differences = np.diff(parsed.frequency_hz)
        inferred_sample_rate = float(np.median(differences) * 131072.0)
        inferred_48k = abs(inferred_sample_rate - 48000.0) <= 2.0
        # REW's 48 kHz FFT grid ends at 7999.87793 Hz rather than exactly
        # 8000 Hz; this is the accepted no-extrapolation boundary condition.
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
            quality_metrics={"p04t2_qc_reasons": reasons, "inferred_sample_rate_hz": inferred_sample_rate},
            meta=meta,
            magnitude_quantity="spl",
            magnitude_reference="REW frequency-response export",
        )
        result = preprocess_formal_sweep(spectrum, contract)
        if frequency is None:
            frequency = result.frequency_hz.copy()
            valid_mask = result.valid_mask.copy()
        elif not np.array_equal(frequency, result.frequency_hz) or not np.array_equal(valid_mask, result.valid_mask):
            raise P04T2InputError("preprocessed P04T2 grids or masks differ")
        curves[member.sample_id] = result.magnitude_db.copy()
        dated = parsed.headers.get("dated", "").removeprefix("Dated:").strip()
        try:
            date = datetime.strptime(dated, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise P04T2InputError(f"invalid Dated header: {member.filename}: {dated}") from exc
        dates[member.sample_id] = date
        qc_rows.append({
            "sample_id": member.sample_id,
            "filename": member.filename,
            "condition": member.condition,
            "assembly_id": member.assembly_id,
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
        raise P04T2InputError("P04T2 preprocessing produced no curves")
    bad = [row["sample_id"] for row in qc_rows if not row["structural_valid"]]
    if bad:
        raise P04T2InputError(f"P04T2 structural QC failed: {bad}")
    return frequency, valid_mask, curves, qc_rows, dates


def _rms(values: FloatArray, mask: BoolArray) -> float:
    return float(np.sqrt(np.mean(np.square(values[mask]))))


def _demean(values: FloatArray, mask: BoolArray) -> FloatArray:
    return values - float(np.mean(values[mask]))


def _window_mask(frequency: FloatArray, valid: BoolArray, center_hz: float) -> BoolArray:
    return valid & (frequency >= center_hz * 2.0 ** (-1.0 / 24.0)) & (frequency <= center_hz * 2.0 ** (1.0 / 24.0))


def _pairwise_rms(matrix: FloatArray, mask: BoolArray) -> list[float]:
    return [_rms(matrix[i] - matrix[j], mask) for i, j in itertools.combinations(range(matrix.shape[0]), 2)]


def _condition_matrix(
    condition: str,
    curves: Mapping[str, FloatArray],
) -> tuple[NDArray[np.int64], list[str], FloatArray]:
    sample_ids = [f"P04T2-{condition}-A{P04T2_CONDITIONS.index(condition)+1:02d}-R{repeat:02d}" for repeat in range(1, 7)]
    # The frozen identities are A01/A04/A02/A03 rather than condition order.
    assemblies = {"BASE0": "A01", "BASE1": "A04", "I75A": "A02", "I50PA": "A03"}
    sample_ids = [f"P04T2-{condition}-{assemblies[condition]}-R{repeat:02d}" for repeat in range(1, 7)]
    return np.arange(1, 7, dtype=np.int64), sample_ids, np.vstack([curves[sample] for sample in sample_ids])


def _bootstrap_effects(
    matrices: Mapping[str, FloatArray],
    selected_indices: Mapping[str, NDArray[np.int64]],
    frequency: FloatArray,
    valid: BoolArray,
    primary: BoolArray,
    *,
    iterations: int = 2000,
    seed: int = 260826,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    output: dict[str, Any] = {}
    for condition in ("I75A", "I50PA"):
        shape_rms = np.empty(iterations)
        raw_windows = {center: np.empty(iterations) for center in P04T2_LANDMARKS_HZ}
        shape_windows = {center: np.empty(iterations) for center in P04T2_LANDMARKS_HZ}
        raw_points = {center: np.empty(iterations) for center in P04T2_LANDMARKS_HZ}
        shape_points = {center: np.empty(iterations) for center in P04T2_LANDMARKS_HZ}
        for index in range(iterations):
            reps: dict[str, FloatArray] = {}
            for key in P04T2_CONDITIONS:
                subset = matrices[key][selected_indices[key]]
                draw = rng.integers(0, subset.shape[0], subset.shape[0])
                reps[key] = np.median(subset[draw], axis=0)
            baseline = np.median(np.vstack([reps["BASE0"], reps["BASE1"]]), axis=0)
            raw = reps[condition] - baseline
            shape = _demean(raw, primary)
            shape_rms[index] = _rms(shape, primary)
            for center in P04T2_LANDMARKS_HZ:
                mask = _window_mask(frequency, valid, center)
                point_index = int(np.argmin(np.abs(frequency - center)))
                raw_windows[center][index] = float(np.mean(raw[mask]))
                shape_windows[center][index] = float(np.mean(shape[mask]))
                raw_points[center][index] = float(raw[point_index])
                shape_points[center][index] = float(shape[point_index])
        output[condition] = {
            "iterations": iterations,
            "seed": seed,
            "shape_primary_rms_db_ci95": np.percentile(shape_rms, [2.5, 97.5]).tolist(),
            "landmarks": {
                str(center): {
                    "raw_db_ci95": np.percentile(raw_windows[center], [2.5, 97.5]).tolist(),
                    "shape_db_ci95": np.percentile(shape_windows[center], [2.5, 97.5]).tolist(),
                    "point_raw_db_ci95": np.percentile(raw_points[center], [2.5, 97.5]).tolist(),
                    "point_shape_db_ci95": np.percentile(shape_points[center], [2.5, 97.5]).tolist(),
                    "raw_positive_probability": float(np.mean(raw_windows[center] > 0.0)),
                    "shape_positive_probability": float(np.mean(shape_windows[center] > 0.0)),
                }
                for center in P04T2_LANDMARKS_HZ
            },
        }
    return output


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def run_p04t2_insert_pilot_analysis(
    batch_root: str | Path,
    output_directory: str | Path,
) -> P04T2RunResult:
    batch = Path(batch_root).resolve()
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"P04T2 output already exists: {output}")
    members, source_zip, zip_sha = _inspect_inputs(batch)
    frequency, valid, curves, qc_rows, dates = _preprocess_members(members)
    output.mkdir(parents=True, exist_ok=False)

    primary = valid & (frequency >= 200.0) & (frequency <= 4000.0)
    secondary = valid & (frequency > 4000.0) & (frequency <= 8000.0)
    matrices: dict[str, FloatArray] = {}
    sample_ids: dict[str, list[str]] = {}
    selected_indices: dict[str, NDArray[np.int64]] = {}
    representatives: dict[str, FloatArray] = {}
    all_representatives: dict[str, FloatArray] = {}
    selection_rows: list[dict[str, Any]] = []
    repeatability_rows: list[dict[str, Any]] = []

    for condition in P04T2_CONDITIONS:
        repeats, ids, matrix = _condition_matrix(condition, curves)
        matrices[condition] = matrix
        sample_ids[condition] = ids
        selected, flagged, distances = select_closest_repeats(
            matrix, repeat_numbers=repeats, analysis_mask=primary, keep=4,
        )
        selected_indices[condition] = selected - 1
        representatives[condition] = np.median(matrix[selected - 1], axis=0)
        all_representatives[condition] = np.median(matrix, axis=0)
        for repeat, sample, distance in zip(repeats, ids, distances, strict=True):
            selection_rows.append({
                "sample_id": sample,
                "condition": condition,
                "repeat_number": int(repeat),
                "rms_to_all6_median_primary_db": float(distance),
                "primary_selected_4of6": bool(repeat in selected),
                "flagged_not_deleted": bool(repeat in flagged),
                "selection_rule": "four lowest RMS distances to all-six condition median over 200-4000 Hz",
                "automatic_exclusion": False,
            })
        for scope, subset in (("selected4", matrix[selected - 1]), ("all6", matrix)):
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

    baseline = np.median(np.vstack([representatives["BASE0"], representatives["BASE1"]]), axis=0)
    baseline_all = np.median(np.vstack([all_representatives["BASE0"], all_representatives["BASE1"]]), axis=0)
    base_raw = representatives["BASE1"] - representatives["BASE0"]
    base_shape = _demean(base_raw, primary)
    base_shape_rms = _rms(base_shape, primary)

    condition_effect_rows: list[dict[str, Any]] = []
    fixed_window_rows: list[dict[str, Any]] = []
    effects: dict[str, dict[str, FloatArray]] = {}
    all_effects: dict[str, dict[str, FloatArray]] = {}
    exploratory_bands: dict[str, list[dict[str, Any]]] = {}
    for condition in ("I75A", "I50PA"):
        raw = representatives[condition] - baseline
        shape = _demean(raw, primary)
        raw_all = all_representatives[condition] - baseline_all
        shape_all = _demean(raw_all, primary)
        effects[condition] = {"raw": raw, "shape": shape}
        all_effects[condition] = {"raw": raw_all, "shape": shape_all}
        condition_effect_rows.append({
            "condition": condition,
            "realized_air_percent": P04T2_REALIZED_AIR_PERCENT[condition],
            "primary_raw_rms_db": _rms(raw, primary),
            "primary_shape_rms_db": _rms(shape, primary),
            "secondary_raw_rms_db": _rms(raw, secondary),
            "secondary_shape_rms_db": _rms(_demean(raw, secondary), secondary),
            "effect_to_baseline_batch_shape_ratio": _rms(shape, primary) / base_shape_rms,
            "selected_vs_all6_primary_shape_rms_db": _rms(shape - shape_all, primary),
        })
        selected_matrix = matrices[condition][selected_indices[condition]]
        repeat_shapes = selected_matrix - baseline
        repeat_shapes -= np.mean(repeat_shapes[:, primary], axis=1, keepdims=True)
        median_repeat_shape = np.median(repeat_shapes, axis=0)
        sign_fraction = np.maximum(np.mean(repeat_shapes > 0.0, axis=0), np.mean(repeat_shapes < 0.0, axis=0))
        stable_mask = primary & (np.abs(median_repeat_shape) > P04T2_LOCAL_FLOOR_DB) & (sign_fraction >= 0.75)
        exploratory_bands[condition] = contiguous_frequency_bands(frequency, stable_mask, minimum_bins=2)
        for center in P04T2_LANDMARKS_HZ:
            mask = _window_mask(frequency, valid, center)
            point_index = int(np.argmin(np.abs(frequency - center)))
            fixed_window_rows.append({
                "condition": condition,
                "center_hz": center,
                "window_low_hz": float(frequency[mask][0]),
                "window_high_hz": float(frequency[mask][-1]),
                "raw_effect_db": float(np.mean(raw[mask])),
                "shape_effect_db": float(np.mean(shape[mask])),
                "raw_all6_effect_db": float(np.mean(raw_all[mask])),
                "shape_all6_effect_db": float(np.mean(shape_all[mask])),
                "point_frequency_hz": float(frequency[point_index]),
                "point_raw_effect_db": float(raw[point_index]),
                "point_shape_effect_db": float(shape[point_index]),
                "point_raw_all6_effect_db": float(raw_all[point_index]),
                "point_shape_all6_effect_db": float(shape_all[point_index]),
                "raw_abs_exceeds_1p396": abs(float(np.mean(raw[mask]))) > P04T2_LOCAL_FLOOR_DB,
                "shape_abs_exceeds_1p396": abs(float(np.mean(shape[mask]))) > P04T2_LOCAL_FLOOR_DB,
                "point_raw_abs_exceeds_1p396": abs(float(raw[point_index])) > P04T2_LOCAL_FLOOR_DB,
            })

    bootstrap = _bootstrap_effects(matrices, selected_indices, frequency, valid, primary)
    for row in fixed_window_rows:
        info = bootstrap[row["condition"]]["landmarks"][str(row["center_hz"])]
        row["raw_bootstrap_ci95_low"] = info["raw_db_ci95"][0]
        row["raw_bootstrap_ci95_high"] = info["raw_db_ci95"][1]
        row["shape_bootstrap_ci95_low"] = info["shape_db_ci95"][0]
        row["shape_bootstrap_ci95_high"] = info["shape_db_ci95"][1]
        row["point_raw_bootstrap_ci95_low"] = info["point_raw_db_ci95"][0]
        row["point_raw_bootstrap_ci95_high"] = info["point_raw_db_ci95"][1]
        row["point_shape_bootstrap_ci95_low"] = info["point_shape_db_ci95"][0]
        row["point_shape_bootstrap_ci95_high"] = info["point_shape_db_ci95"][1]

    i75_shape = effects["I75A"]["shape"][primary]
    i50_shape = effects["I50PA"]["shape"][primary]
    similarity = float(np.corrcoef(i75_shape, i50_shape)[0, 1])
    effect_by_condition = {row["condition"]: row for row in condition_effect_rows}
    fixed_map = {(row["condition"], row["center_hz"]): row for row in fixed_window_rows}
    double_landmark_pass = all(
        fixed_map[("I75A", center)]["point_raw_abs_exceeds_1p396"]
        for center in P04T2_LANDMARKS_HZ
    )
    dose_ordered = (
        effect_by_condition["I50PA"]["primary_shape_rms_db"]
        > effect_by_condition["I75A"]["primary_shape_rms_db"]
        > base_shape_rms
    )
    classification = "USEFUL_BOUNDED_MECHANISM_EVIDENCE_WITH_LIMITS" if dose_ordered and similarity >= 0.6 else "INCONCLUSIVE"

    source_rows = [{
        "relative_path": member.path.relative_to(batch).as_posix(),
        "condition": member.condition,
        "assembly_id": member.assembly_id,
        "repeat_number": member.repeat_number,
        "extension": member.extension,
        "size_bytes": member.size_bytes,
        "sha256": member.sha256,
    } for member in members]
    source_rows.append({
        "relative_path": source_zip.relative_to(batch).as_posix(),
        "condition": "SOURCE_ARCHIVE",
        "assembly_id": "NA",
        "repeat_number": "NA",
        "extension": ".zip",
        "size_bytes": source_zip.stat().st_size,
        "sha256": zip_sha,
    })

    _write_csv(output / "source_manifest.csv", source_rows, list(source_rows[0].keys()))
    _write_csv(output / "qc_table.csv", qc_rows, list(qc_rows[0].keys()))
    _write_csv(output / "repeat_selection.csv", selection_rows, list(selection_rows[0].keys()))
    _write_csv(output / "repeatability.csv", repeatability_rows, list(repeatability_rows[0].keys()))
    _write_csv(output / "condition_effects.csv", condition_effect_rows, list(condition_effect_rows[0].keys()))
    _write_csv(output / "fixed_window_effects.csv", fixed_window_rows, list(fixed_window_rows[0].keys()))

    spectra_rows = []
    for index, value in enumerate(frequency):
        spectra_rows.append({
            "frequency_hz": float(value),
            "valid": bool(valid[index]),
            "base0_selected4_median_db": float(representatives["BASE0"][index]),
            "base1_selected4_median_db": float(representatives["BASE1"][index]),
            "baseline_combined_db": float(baseline[index]),
            "i75_selected4_median_db": float(representatives["I75A"][index]),
            "i50p_selected4_median_db": float(representatives["I50PA"][index]),
            "i75_minus_base_raw_db": float(effects["I75A"]["raw"][index]),
            "i75_minus_base_shape_db": float(effects["I75A"]["shape"][index]),
            "i50p_minus_base_raw_db": float(effects["I50PA"]["raw"][index]),
            "i50p_minus_base_shape_db": float(effects["I50PA"]["shape"][index]),
        })
    _write_csv(output / "representative_spectra.csv", spectra_rows, list(spectra_rows[0].keys()))

    chronological = sorted(dates.items(), key=lambda item: item[1])
    base0_last = max(dates[sample] for sample in sample_ids["BASE0"])
    base1_first = min(dates[sample] for sample in sample_ids["BASE1"])
    summary = {
        "schema_version": P04T2_SCHEMA_VERSION,
        "classification": classification,
        "source_zip_sha256": zip_sha,
        "data_origin": "real_experiment",
        "dataset_role": "supplemental_mechanism_pilot",
        "scientifically_eligible": False,
        "final_test_read": False,
        "counts": {"txt": 24, "mdat": 24, "conditions": 4, "repeats_per_condition": 6},
        "selection_rule": "objective 4-of-6 by lowest primary-band RMS distance to all-six condition median; all-six retained",
        "selection": {
            condition: {
                "selected_repeats": [int(index + 1) for index in selected_indices[condition]],
                "flagged_not_deleted": [int(value) for value in sorted(set(range(1, 7)) - set(index + 1 for index in selected_indices[condition]))],
            }
            for condition in P04T2_CONDITIONS
        },
        "acquisition_order": [sample for sample, _ in chronological],
        "base0_to_base1_gap_seconds": (base1_first - base0_last).total_seconds(),
        "base1_is_not_post_intervention_return_control": True,
        "baseline_batch_consistency": {
            "primary_raw_rms_db": _rms(base_raw, primary),
            "primary_shape_rms_db": base_shape_rms,
            "secondary_raw_rms_db": _rms(base_raw, secondary),
        },
        "condition_effects": {row["condition"]: row for row in condition_effect_rows},
        "fixed_window_effects": fixed_window_rows,
        "bootstrap": bootstrap,
        "effect_similarity_primary_pearson": similarity,
        "effect_similarity_primary_cosine": float(np.dot(i75_shape, i50_shape) / (np.linalg.norm(i75_shape) * np.linalg.norm(i50_shape))),
        "dose_ordered_primary_shape_rms": dose_ordered,
        "i75_double_frozen_landmark_gate_pass": double_landmark_pass,
        "exploratory_stable_bands": exploratory_bands,
        "conclusion_boundary": {
            "supported": "central shared-chamber volume intervention produces repeat-consistent, dose-ordered spectral-shape change larger than sequential baseline-batch variation",
            "not_supported": [
                "complete validation of both frozen P04 simulation landmarks",
                "independent reassembly or long-term repeatability",
                "direction classification or full U4 performance",
                "single-module causal contribution percentage",
            ],
        },
    }
    (output / "analysis_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_mask = valid & (frequency >= 200.0) & (frequency <= 4000.0)
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.semilogx(frequency[plot_mask], baseline[plot_mask], label="BASE combined", color="black", linewidth=2)
    ax.semilogx(frequency[plot_mask], representatives["I75A"][plot_mask], label="I75 75.83%", linewidth=1.6)
    ax.semilogx(frequency[plot_mask], representatives["I50PA"][plot_mask], label="I50P 54.06%", linewidth=1.6)
    ax.set(xlabel="Frequency (Hz)", ylabel="Smoothed SPL (dB)", title="P04T2 selected-4 representatives")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "representative_spectra_200_4000.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.semilogx(frequency[plot_mask], effects["I75A"]["shape"][plot_mask], label="I75 − BASE", linewidth=1.8)
    ax.semilogx(frequency[plot_mask], effects["I50PA"]["shape"][plot_mask], label="I50P − BASE", linewidth=1.8)
    ax.axhline(P04T2_LOCAL_FLOOR_DB, color="grey", linestyle="--", linewidth=1, label="±1.396 dB reference")
    ax.axhline(-P04T2_LOCAL_FLOOR_DB, color="grey", linestyle="--", linewidth=1)
    for center in P04T2_LANDMARKS_HZ:
        ax.axvline(center, color="black", alpha=0.35, linestyle=":")
    ax.set(xlabel="Frequency (Hz)", ylabel="Demeaned spectral effect (dB)", title="Central-chamber intervention effects")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "demeaned_effects_200_4000.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    labels = []
    values = []
    lower = []
    upper = []
    for row in fixed_window_rows:
        labels.append(f"{row['condition']}\n{row['center_hz']:.0f} Hz")
        values.append(row["raw_effect_db"])
        lower.append(row["raw_effect_db"] - row["raw_bootstrap_ci95_low"])
        upper.append(row["raw_bootstrap_ci95_high"] - row["raw_effect_db"])
    x = np.arange(len(values))
    ax.bar(x, values, color=["#4c78a8", "#4c78a8", "#f58518", "#f58518"])
    ax.errorbar(x, values, yerr=np.vstack([lower, upper]), fmt="none", ecolor="black", capsize=4)
    ax.axhline(P04T2_LOCAL_FLOOR_DB, color="grey", linestyle="--", linewidth=1)
    ax.axhline(-P04T2_LOCAL_FLOOR_DB, color="grey", linestyle="--", linewidth=1)
    ax.set_xticks(x, labels)
    ax.set(ylabel="Raw effect vs BASE (dB)", title="Frozen-window effects with repeat bootstrap CI")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output / "fixed_window_effects.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    for position, condition in enumerate(P04T2_CONDITIONS):
        rows = [row for row in selection_rows if row["condition"] == condition]
        colors = ["#4c78a8" if row["primary_selected_4of6"] else "#e45756" for row in rows]
        ax.scatter([position] * 6, [row["rms_to_all6_median_primary_db"] for row in rows], c=colors, s=50)
    ax.set_xticks(range(4), P04T2_CONDITIONS)
    ax.set(ylabel="RMS to all-six condition median (dB)", title="Objective 4-of-6 repeat selection")
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output / "repeat_selection_qc.png", dpi=180)
    plt.close(fig)

    manifest_targets = sorted(path for path in output.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt")
    with (output / "SHA256SUMS.txt").open("w", encoding="utf-8", newline="\n") as handle:
        for path in manifest_targets:
            handle.write(f"{_sha256_file(path)}  {path.name}\n")
    return P04T2RunResult(output, 24, 16, len(manifest_targets) + 1, classification)
