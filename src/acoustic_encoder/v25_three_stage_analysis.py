"""Joint V2.5 S1/S2/S3 real-measurement analysis under the revised repeat rule.

S1 is treated as one six-repeat campaign per condition and the single curve
farthest from the group median is omitted from the primary five-repeat
summary.  S2/S3 contain four repeats per direction and use the analogous
three-of-four rule.  Every raw curve remains inventoried and the all-repeat
result is emitted as a sensitivity analysis.  No final-test data are read.
"""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any, Mapping, Sequence
import zipfile

import numpy as np
from numpy.typing import NDArray

from .formal_preprocessing import (
    FORMAL_PREPROCESSING_ALGORITHM_VERSION,
    frozen_formal_preprocessing_contract,
    preprocess_formal_sweep,
)
from .formal_real_import import _header_contract, _parse_rew_member
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
    artifact_sha256,
)
from .v25_single_module_analysis import (
    HISTORICAL_PRIMARY_FLOOR_P95_DB,
    V25S1_ZIP_SHA256,
    _CONDITIONS as S1_CONDITIONS,
    _MODULES as S1_MODULES,
    _TARGETS_HZ as S1_TARGETS_HZ,
    _PREDICTED_HZ as S1_PREDICTED_HZ,
    _qc_and_preprocess as preprocess_s1,
    _local_residual,
    inspect_v25_s1_archive,
)
from .version import (
    CONFIG_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    MEASUREMENT_SCHEMA_VERSION,
    PIPELINE_VERSION,
)


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

V25_JOINT_SCHEMA_VERSION = "v25_s1_s2_s3_joint_v1"
V25_S2_ZIP_SHA256 = "b3681a43bd25f8a3940a8a341ae396a65574048c2fc21566f9516c70d4f6729a"
V25_S3_ZIP_SHA256 = "081ae2ba1284cfaeeb24f9a738b7d2198c2bababe13a9acc6e75c6781787ccf2"
ANGLES = (0, 90, 180, 270)
ARRAY_CONFIGURATIONS = ("U4SYM", "U4HR")
S3_MODULE_BY_ANGLE = {0: "HR01", 90: "HR03", 180: "HR05", 270: "HR07"}
S3_MODULES = tuple(S3_MODULE_BY_ANGLE[angle] for angle in ANGLES)
_ARRAY_NAME = re.compile(
    r"^R V2\.5_(?P<configuration>U4SYM|U4HR)_"
    r"(?P<angle>000|090|180|270)_(?P<repeat>0[1-4])"
    r"(?P<extension>\.txt|\.mdat)$"
)


class V25JointInputError(ValueError):
    """Raised when joint V2.5 identity, provenance, or analysis rules fail."""


@dataclass(frozen=True, slots=True)
class V25ArrayMember:
    archive_path: str
    filename: str
    configuration: str
    direction_deg: int
    repeat_number: int
    extension: str
    sha256: str
    size_bytes: int

    @property
    def stage_id(self) -> str:
        return "V25-S2" if self.configuration == "U4SYM" else "V25-S3"

    @property
    def sample_id(self) -> str:
        return (
            f"{self.stage_id.replace('-', '')}-{self.configuration}-"
            f"D{self.direction_deg:03d}-R{self.repeat_number:02d}"
        )


@dataclass(frozen=True, slots=True)
class V25ArrayInventory:
    zip_path: Path
    zip_sha256: str
    configuration: str
    txt_members: tuple[V25ArrayMember, ...]
    mdat_members: tuple[V25ArrayMember, ...]
    direction_counts: Mapping[int, int]


@dataclass(frozen=True, slots=True)
class RepeatSelection:
    selected_sample_ids: tuple[str, ...]
    dropped_sample_id: str
    distances_db: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class V25JointRunResult:
    output_directory: Path
    s1_txt_count: int
    s2_txt_count: int
    s3_txt_count: int
    primary_selected_count: int
    flagged_count: int
    artifact_count: int


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_v25_array_filename(filename: str) -> tuple[str, int, int, str]:
    match = _ARRAY_NAME.fullmatch(filename)
    if match is None:
        raise V25JointInputError(
            f"cannot reliably identify V2.5 array configuration/direction/repeat: {filename}"
        )
    return (
        match.group("configuration"), int(match.group("angle")),
        int(match.group("repeat")), match.group("extension"),
    )


def inspect_v25_array_archive(
    zip_path: str | Path,
    *,
    expected_configuration: str,
    expected_zip_sha256: str,
    extracted_txt_directory: str | Path | None = None,
    extracted_mdat_directory: str | Path | None = None,
) -> V25ArrayInventory:
    if expected_configuration not in ARRAY_CONFIGURATIONS:
        raise V25JointInputError(f"unsupported V2.5 configuration: {expected_configuration}")
    source = Path(zip_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"V2.5 array ZIP does not exist: {source}")
    actual_zip_sha = _sha256_file(source)
    if actual_zip_sha != expected_zip_sha256:
        raise V25JointInputError(
            f"V2.5 {expected_configuration} ZIP SHA-256 mismatch: "
            f"expected {expected_zip_sha256}, found {actual_zip_sha}"
        )
    members: list[V25ArrayMember] = []
    with zipfile.ZipFile(source, "r") as archive:
        files = [item for item in archive.infolist() if not item.is_dir()]
        archive_paths = [item.filename for item in files]
        duplicates = sorted(
            name for name, count in Counter(archive_paths).items() if count > 1
        )
        if duplicates:
            raise V25JointInputError(f"duplicate V2.5 array archive paths: {duplicates}")
        for info in files:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise V25JointInputError(f"unsafe V2.5 array member path: {info.filename}")
            configuration, angle, repeat, extension = parse_v25_array_filename(path.name)
            if configuration != expected_configuration:
                raise V25JointInputError(
                    f"configuration mismatch in {info.filename}: {configuration}"
                )
            payload = archive.read(info)
            members.append(V25ArrayMember(
                archive_path=info.filename,
                filename=path.name,
                configuration=configuration,
                direction_deg=angle,
                repeat_number=repeat,
                extension=extension,
                sha256=_sha256_bytes(payload),
                size_bytes=len(payload),
            ))
    txt = sorted(
        (member for member in members if member.extension == ".txt"),
        key=lambda item: (item.direction_deg, item.repeat_number),
    )
    mdat = sorted(
        (member for member in members if member.extension == ".mdat"),
        key=lambda item: (item.direction_deg, item.repeat_number),
    )
    expected_ids = {(angle, repeat) for angle in ANGLES for repeat in range(1, 5)}
    if len(txt) != 16 or len(mdat) != 16 or len(members) != 32:
        raise V25JointInputError(
            f"V2.5 {expected_configuration} requires 16 TXT + 16 MDAT; "
            f"found {len(txt)} + {len(mdat)}"
        )
    if {(item.direction_deg, item.repeat_number) for item in txt} != expected_ids:
        raise V25JointInputError("V2.5 array TXT direction-repeat inventory is incomplete")
    if {(item.direction_deg, item.repeat_number) for item in mdat} != expected_ids:
        raise V25JointInputError("V2.5 array MDAT direction-repeat inventory is incomplete")
    if len({item.sha256 for item in txt}) != len(txt):
        raise V25JointInputError("duplicate V2.5 array TXT content")

    def verify_extracted(
        directory: str | Path, expected: Sequence[V25ArrayMember],
    ) -> None:
        root = Path(directory).resolve()
        expected_names = sorted(item.filename for item in expected)
        actual_names = sorted(path.name for path in root.iterdir() if path.is_file())
        if actual_names != expected_names:
            raise V25JointInputError(f"extracted inventory differs from ZIP: {root}")
        for member in expected:
            if _sha256_file(root / member.filename) != member.sha256:
                raise V25JointInputError(
                    f"extracted raw hash mismatch: {member.filename}"
                )

    if extracted_txt_directory is not None:
        verify_extracted(extracted_txt_directory, txt)
    if extracted_mdat_directory is not None:
        verify_extracted(extracted_mdat_directory, mdat)
    counts = {angle: 4 for angle in ANGLES}
    return V25ArrayInventory(
        source, actual_zip_sha, expected_configuration, tuple(txt), tuple(mdat), counts
    )


def _array_meta(
    member: V25ArrayMember, inventory: V25ArrayInventory, reasons: Sequence[str],
) -> MeasurementMeta:
    return MeasurementMeta(
        sample_id=member.sample_id,
        pipeline_version=PIPELINE_VERSION,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        measurement_schema_version=MEASUREMENT_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        device_version="V2.5_U4_array",
        configuration=member.configuration,
        angle_deg=float(member.direction_deg),
        session_id=member.stage_id,
        repeat_type="CONT",
        repeat_id=f"R{member.repeat_number:02d}",
        experiment_step=f"{member.stage_id}_ARRAY",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=f"zip://{inventory.zip_path.as_posix()}!/{member.archive_path}",
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_ANALYSIS,
        source_sha256=member.sha256,
        provenance_uri=f"sha256:{inventory.zip_sha256}#member={member.sha256}",
        eligible_for_scientific_analysis=False,
        assembly_id=f"{member.stage_id}-single_campaign",
        acquisition_block_id="single_campaign",
        valid=True,
        qc_status=QCStatus.WARNING if reasons else QCStatus.VALID,
        manual_review_reasons=tuple(reasons),
    )


def _preprocess_array(
    inventory: V25ArrayInventory,
) -> tuple[dict[str, FloatArray], FloatArray, BoolArray, list[dict[str, Any]]]:
    curves: dict[str, FloatArray] = {}
    rows: list[dict[str, Any]] = []
    frequency: FloatArray | None = None
    valid_mask: BoolArray | None = None
    contract = frozen_formal_preprocessing_contract()
    with zipfile.ZipFile(inventory.zip_path, "r") as archive:
        for member in inventory.txt_members:
            payload = archive.read(member.archive_path)
            if _sha256_bytes(payload) != member.sha256:
                raise V25JointInputError(
                    f"ZIP member changed after inventory: {member.filename}"
                )
            parsed = _parse_rew_member(payload, member.archive_path)
            header, failures = _header_contract(parsed)
            all_headers = parsed.headers["all"]
            format_ok = bool(re.search(
                r"Format:\s*256k Log Swept Sine,\s*1 sweep at -30\.0 dBFS "
                r"with no timing reference", all_headers, re.I,
            ))
            identity = re.search(
                r"Measurement:\s*R V2\.5_(?P<configuration>U4SYM|U4HR)_"
                r"(?P<angle>000|090|180|270)_(?P<repeat>0[1-4])\b",
                all_headers, re.I,
            )
            identity_ok = bool(
                identity
                and identity.group("configuration").upper() == member.configuration
                and int(identity.group("angle")) == member.direction_deg
                and int(identity.group("repeat")) == member.repeat_number
            )
            note = parsed.headers.get("note", "")
            fixed_note_ok = all(re.search(pattern, note, re.I) for pattern in (
                r"Windows out=50", r"mic input=100", r"distance=0\.8 m",
            ))
            open_match = re.search(r"(\d+) acoustic channels open", note, re.I)
            declared_open_channels = int(open_match.group(1)) if open_match else None
            open_channel_note_matches = declared_open_channels == 4
            source_ok = "iMM-6C" in parsed.headers.get("source", "")
            inferred_sample_rate = float(
                np.median(np.diff(parsed.frequency_hz)) * 131072.0
            )
            inferred_48k = abs(inferred_sample_rate - 48000.0) <= 2.0
            if not format_ok:
                failures.append("rew_format_contract_mismatch")
            if not identity_ok:
                failures.append("measurement_header_identity_mismatch")
            if not fixed_note_ok:
                failures.append("fixed_note_settings_mismatch")
            if not source_ok:
                failures.append("microphone_source_not_iMM6C")
            if not inferred_48k:
                failures.append("sample_rate_not_consistent_with_48khz")
            warnings = [
                "calibration_filename_header_unavailable",
                "t0_at_ir_peak_header_unavailable",
                "clipping_unavailable_from_frequency_response_txt",
            ]
            if not open_channel_note_matches:
                warnings.append("declared_open_channel_count_not_four")
            reasons = sorted(set(failures if failures else warnings))
            meta = _array_meta(member, inventory, reasons)
            spectrum = SpectrumData(
                frequency_hz=parsed.frequency_hz,
                magnitude_db=parsed.magnitude_db,
                valid_mask=np.ones(parsed.frequency_hz.size, dtype=bool),
                representation=Representation.DENSE_SPECTRUM,
                phase_status=PhaseStatus.UNAVAILABLE,
                quality_metrics={
                    "v25_joint_qc_reasons": reasons,
                    "declared_open_channels": declared_open_channels,
                    "calibration_external_declaration": "CMM29939.txt",
                    "set_t0_external_declaration": "IR peak",
                    "inferred_sample_rate_hz": inferred_sample_rate,
                },
                meta=meta,
                magnitude_quantity="spl",
                magnitude_reference="REW frequency-response export",
            )
            result = preprocess_formal_sweep(spectrum, contract)
            if np.flatnonzero(~result.valid_mask).tolist() != [0]:
                raise V25JointInputError(
                    f"FORMAL-1 valid mask mismatch: {member.sample_id}"
                )
            if frequency is None:
                frequency = result.frequency_hz.copy()
                valid_mask = result.valid_mask.copy()
            elif not np.array_equal(frequency, result.frequency_hz):
                raise V25JointInputError("preprocessed V2.5 array grids differ")
            curves[member.sample_id] = result.magnitude_db.copy()
            rows.append({
                "sample_id": member.sample_id,
                "stage_id": member.stage_id,
                "configuration": member.configuration,
                "direction_deg": member.direction_deg,
                "repeat_number": member.repeat_number,
                "filename": member.filename,
                "file_sha256": member.sha256,
                "size_bytes": member.size_bytes,
                "dated_header": parsed.headers.get("dated", "").removeprefix("Dated:").strip(),
                "structural_valid": not failures,
                "qc_status": "fail" if failures else "warning",
                "reason_codes": reasons,
                "declared_open_channels": declared_open_channels,
                "expected_open_channels": 4,
                "open_channel_note_matches": open_channel_note_matches,
                "fixed_note_settings_match": fixed_note_ok,
                "measurement_identity_matches_filename": identity_ok,
                "rew_version": header["rew_version"] or "unavailable",
                "format_256k_1rep_minus30_no_timing": format_ok,
                "raw_smoothing": header["raw_smoothing"] or "unavailable",
                "source_mentions_iMM6C": source_ok,
                "inferred_sample_rate_hz": inferred_sample_rate,
                "inferred_sample_rate_is_48khz": inferred_48k,
                "automatic_exclusion": False,
                "final_test_read": False,
            })
    if any(not row["structural_valid"] for row in rows):
        bad = [row["sample_id"] for row in rows if not row["structural_valid"]]
        raise V25JointInputError(f"V2.5 array structural QC failed: {bad}")
    if frequency is None or valid_mask is None:
        raise V25JointInputError("V2.5 array preprocessing produced no curves")
    return curves, frequency, valid_mask, rows


def _finite_mask(curves: Mapping[str, FloatArray], frequency: FloatArray,
                 lower: float, upper: float) -> BoolArray:
    finite = np.logical_and.reduce([np.isfinite(curve) for curve in curves.values()])
    return finite & (frequency >= lower) & (frequency <= upper)


def _rms(values: FloatArray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def _demean(values: FloatArray) -> FloatArray:
    return values - float(np.mean(values))


def select_farthest_repeat(
    curves: Mapping[str, FloatArray], frequency: FloatArray, *, keep_count: int,
) -> RepeatSelection:
    if len(curves) != keep_count + 1:
        raise V25JointInputError(
            f"selection requires exactly keep_count+1 curves; got {len(curves)}"
        )
    mask = _finite_mask(curves, frequency, 200.0, 4000.0)
    center = np.median(np.vstack(list(curves.values())), axis=0)
    distances = {
        sample_id: _rms((curve - center)[mask])
        for sample_id, curve in curves.items()
    }
    dropped = max(sorted(distances), key=lambda sample_id: distances[sample_id])
    selected = tuple(sorted(sample_id for sample_id in curves if sample_id != dropped))
    return RepeatSelection(selected, dropped, distances)


def direction_code_score(matrix: FloatArray) -> dict[str, Any]:
    values = np.asarray(matrix, dtype=np.float64)
    if values.shape != (4, 4):
        raise V25JointInputError("direction code matrix must be 4x4")
    diagonal = np.diag(values)
    off = values[~np.eye(4, dtype=bool)]
    score = float(np.mean(diagonal) - np.mean(off))
    top1 = sum(int(np.argmax(values[:, column])) == column for column in range(4))
    top2 = sum(
        column in np.argsort(values[:, column])[-2:] for column in range(4)
    )
    permutation_scores: list[float] = []
    for permutation in itertools.permutations(range(4)):
        selected = np.asarray([values[permutation[column], column] for column in range(4)])
        remainder = np.asarray([
            values[row, column]
            for column in range(4)
            for row in range(4)
            if row != permutation[column]
        ])
        permutation_scores.append(float(np.mean(selected) - np.mean(remainder)))
    p_value = sum(value >= score - 1.0e-12 for value in permutation_scores) / 24.0
    return {
        "score_db": score,
        "diagonal_mean_db": float(np.mean(diagonal)),
        "off_diagonal_mean_db": float(np.mean(off)),
        "correct_direction_top1_count": int(top1),
        "correct_direction_top2_count": int(top2),
        "exact_mapping_permutation_p": float(p_value),
    }


def _selection_rows(
    stage_id: str,
    group_id: str,
    curves: Mapping[str, FloatArray],
    selection: RepeatSelection,
) -> list[dict[str, Any]]:
    ordered = sorted(selection.distances_db, key=selection.distances_db.get)
    ranks = {sample_id: index + 1 for index, sample_id in enumerate(ordered)}
    return [{
        "stage_id": stage_id,
        "group_id": group_id,
        "sample_id": sample_id,
        "distance_to_group_median_primary_raw_rms_db": selection.distances_db[sample_id],
        "distance_rank_ascending": ranks[sample_id],
        "primary_selected": sample_id in selection.selected_sample_ids,
        "primary_drop_flag": sample_id == selection.dropped_sample_id,
        "selection_rule": (
            "drop_unique_maximum_curve_to_all_repeat_group_median_"
            "primary_200_4000hz_raw_rms"
        ),
        "raw_curve_deleted": False,
    } for sample_id in sorted(curves)]


def _extract_local_feature(
    frequency: FloatArray, delta: FloatArray, *, target_hz: float,
) -> dict[str, Any]:
    mask = (
        np.isfinite(delta)
        & (frequency >= target_hz * 2.0 ** (-1.0 / 6.0))
        & (frequency <= target_hz * 2.0 ** (1.0 / 6.0))
    )
    local_frequency = frequency[mask]
    residual = _local_residual(local_frequency, delta[mask])
    peak_index = int(np.argmax(np.abs(residual)))
    signed = float(residual[peak_index])
    threshold = abs(signed) / math.sqrt(2.0)
    above = np.flatnonzero(np.abs(residual) >= threshold)
    bandwidth = (
        float(local_frequency[above[-1]] - local_frequency[above[0]])
        if above.size > 1 else 0.0
    )
    return {
        "measured_feature_hz": float(local_frequency[peak_index]),
        "signed_contrast_db": signed,
        "absolute_contrast_db": abs(signed),
        "polarity": "peak" if signed >= 0.0 else "notch",
        "target_window_rms_db": _rms(residual),
        "contrast_bandwidth_hz": bandwidth,
        "effective_q": (
            float(local_frequency[peak_index] / bandwidth) if bandwidth > 0.0 else None
        ),
        "at_search_boundary": peak_index in (0, residual.size - 1),
    }


def _local_pair_floor(
    curves: Mapping[str, FloatArray], sample_ids: Sequence[str],
    frequency: FloatArray, target_hz: float,
) -> float:
    mask = (
        (frequency >= target_hz * 2.0 ** (-1.0 / 6.0))
        & (frequency <= target_hz * 2.0 ** (1.0 / 6.0))
    )
    values = [
        _rms(_local_residual(
            frequency[mask], (curves[left] - curves[right])[mask],
        ))
        for left, right in itertools.combinations(sample_ids, 2)
    ]
    return float(np.quantile(values, 0.95))


def _s1_analysis(
    curves: Mapping[str, FloatArray],
    frequency: FloatArray,
    member_ids: Mapping[str, Sequence[str]],
    selections: Mapping[str, RepeatSelection],
    *,
    random_state: int,
    bootstrap_iterations: int,
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]],
    dict[str, FloatArray], dict[str, float], dict[str, int],
]:
    selected_representatives = {
        condition: np.median(np.vstack([
            curves[sample_id] for sample_id in selections[condition].selected_sample_ids
        ]), axis=0)
        for condition in S1_CONDITIONS
    }
    all_representatives = {
        condition: np.median(np.vstack([
            curves[sample_id] for sample_id in member_ids[condition]
        ]), axis=0)
        for condition in S1_CONDITIONS
    }
    signatures = {
        module: selected_representatives[module] - selected_representatives["base"]
        for module in S1_MODULES
    }
    feature_rows: list[dict[str, Any]] = []
    centers: dict[str, float] = {}
    polarity_signs: dict[str, int] = {}
    for module_index, module in enumerate(S1_MODULES):
        target = float(S1_TARGETS_HZ[module])
        selected_ids = selections[module].selected_sample_ids
        base_ids = selections["base"].selected_sample_ids
        delta = signatures[module]
        point = _extract_local_feature(frequency, delta, target_hz=target)
        all_delta = all_representatives[module] - all_representatives["base"]
        all_point = _extract_local_feature(frequency, all_delta, target_hz=target)
        local_floor = _local_pair_floor(curves, base_ids, frequency, target)
        all_local_floor = _local_pair_floor(
            curves, member_ids["base"], frequency, target,
        )
        rng = np.random.default_rng(random_state + module_index * 100)
        boot_frequency: list[float] = []
        boot_contrast: list[float] = []
        boot_rms: list[float] = []
        for _ in range(bootstrap_iterations):
            module_sample = rng.choice(selected_ids, size=len(selected_ids), replace=True)
            base_sample = rng.choice(base_ids, size=len(base_ids), replace=True)
            bootstrap_delta = (
                np.median(np.vstack([curves[str(item)] for item in module_sample]), axis=0)
                - np.median(np.vstack([curves[str(item)] for item in base_sample]), axis=0)
            )
            value = _extract_local_feature(
                frequency, bootstrap_delta, target_hz=target,
            )
            boot_frequency.append(float(value["measured_feature_hz"]))
            boot_contrast.append(float(value["signed_contrast_db"]))
            boot_rms.append(float(value["target_window_rms_db"]))
        frequency_ci = np.percentile(boot_frequency, [2.5, 97.5])
        contrast_ci = np.percentile(boot_contrast, [2.5, 97.5])
        rms_ci = np.percentile(boot_rms, [2.5, 97.5])
        point_sign = 1 if float(point["signed_contrast_db"]) >= 0.0 else -1
        polarity_consistency = float(np.mean(
            np.sign(np.asarray(boot_contrast)) == point_sign
        ))
        contrast_ci_excludes_zero = bool(
            float(contrast_ci[0]) > 0.0 or float(contrast_ci[1]) < 0.0
        )
        stable = bool(
            float(point["target_window_rms_db"]) > local_floor
            and contrast_ci_excludes_zero
            and polarity_consistency >= 0.8
            and not bool(point["at_search_boundary"])
        )
        centers[module] = float(point["measured_feature_hz"])
        polarity_signs[module] = point_sign
        feature_rows.append({
            "module_id": module,
            "target_hz": target,
            "package_predicted_hz": float(S1_PREDICTED_HZ[module]),
            **point,
            "frequency_error_percent": (
                (float(point["measured_feature_hz"]) / target - 1.0) * 100.0
            ),
            "selected_base_local_p95_db": local_floor,
            "effect_to_selected_local_floor_ratio": (
                float(point["target_window_rms_db"]) / local_floor
            ),
            "bootstrap_feature_hz_ci95_low": float(frequency_ci[0]),
            "bootstrap_feature_hz_ci95_high": float(frequency_ci[1]),
            "bootstrap_signed_contrast_ci95_low_db": float(contrast_ci[0]),
            "bootstrap_signed_contrast_ci95_high_db": float(contrast_ci[1]),
            "bootstrap_target_window_rms_ci95_low_db": float(rms_ci[0]),
            "bootstrap_target_window_rms_ci95_high_db": float(rms_ci[1]),
            "bootstrap_polarity_consistency": polarity_consistency,
            "bootstrap_iterations": bootstrap_iterations,
            "stable_single_campaign_signature": stable,
            "all6_measured_feature_hz": all_point["measured_feature_hz"],
            "all6_signed_contrast_db": all_point["signed_contrast_db"],
            "all6_target_window_rms_db": all_point["target_window_rms_db"],
            "all6_base_local_p95_db": all_local_floor,
            "selection_sensitivity_feature_shift_hz": (
                float(point["measured_feature_hz"])
                - float(all_point["measured_feature_hz"])
            ),
            "selection_sensitivity_contrast_shift_db": (
                float(point["signed_contrast_db"])
                - float(all_point["signed_contrast_db"])
            ),
            "claim_scope": "single_campaign_repeat_bootstrap_no_independent_block",
        })

    channel_rows: list[dict[str, Any]] = []
    for module in S1_MODULES:
        effects: list[tuple[str, float]] = []
        pending: list[dict[str, Any]] = []
        for channel in S1_MODULES:
            target = float(S1_TARGETS_HZ[channel])
            mask = (
                (frequency >= target * 2.0 ** (-1.0 / 6.0))
                & (frequency <= target * 2.0 ** (1.0 / 6.0))
            )
            effect = _rms(_local_residual(frequency[mask], signatures[module][mask]))
            floor = _local_pair_floor(
                curves, selections["base"].selected_sample_ids, frequency, target,
            )
            effects.append((channel, effect))
            pending.append({
                "module_id": module,
                "target_channel": channel,
                "target_hz": target,
                "window_rms_contrast_db": effect,
                "selected_base_local_p95_db": floor,
                "effect_to_local_floor_ratio": effect / floor,
                "own_target_channel": module == channel,
            })
        ranks = {
            channel: index + 1
            for index, (channel, _) in enumerate(
                sorted(effects, key=lambda item: item[1], reverse=True)
            )
        }
        for row in pending:
            row["within_module_effect_rank"] = ranks[str(row["target_channel"])]
            channel_rows.append(row)

    similarity_rows: list[dict[str, Any]] = []
    mask = _finite_mask(signatures, frequency, 800.0, 5000.0)
    for left, right in itertools.combinations(S1_MODULES, 2):
        a, b = _demean(signatures[left][mask]), _demean(signatures[right][mask])
        similarity_rows.append({
            "module_a": left,
            "module_b": right,
            "pearson_800_5000hz": float(np.corrcoef(a, b)[0, 1]),
            "cosine_800_5000hz": float(
                np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
            ),
        })
    return (
        feature_rows, channel_rows, similarity_rows,
        signatures, centers, polarity_signs,
    )


def _representatives(
    curves: Mapping[str, FloatArray],
    groups: Mapping[int, Sequence[str]],
) -> dict[int, FloatArray]:
    return {
        angle: np.median(np.vstack([curves[sample_id] for sample_id in sample_ids]), axis=0)
        for angle, sample_ids in groups.items()
    }


def direction_discriminability_spectrum(
    curves: Mapping[str, FloatArray],
    groups: Mapping[int, Sequence[str]],
) -> dict[str, FloatArray]:
    """Return exploratory between/within direction contrast at each frequency.

    The measurement repeat is the sampling unit.  Frequency bins are only a
    visualization axis and are not treated as independent observations.
    """
    if len(groups) < 2 or any(len(sample_ids) < 2 for sample_ids in groups.values()):
        raise V25JointInputError(
            "direction discriminability requires at least two directions and repeats"
        )
    representatives = _representatives(curves, groups)
    direction_stack = np.vstack([representatives[angle] for angle in sorted(groups)])
    grand_mean = np.mean(direction_stack, axis=0)
    between = np.sqrt(np.mean((direction_stack - grand_mean) ** 2, axis=0))
    residuals = np.vstack([
        curves[sample_id] - representatives[angle]
        for angle in sorted(groups)
        for sample_id in groups[angle]
    ])
    within = np.sqrt(np.mean(residuals ** 2, axis=0))
    ratio = np.divide(
        between, within,
        out=np.full_like(between, np.nan),
        where=within > np.finfo(np.float64).eps,
    )
    return {
        "between_direction_rms_db": between,
        "within_direction_rms_db": within,
        "between_to_within_ratio": ratio,
    }


def _direction_frequency_rows(
    curves_by_configuration: Mapping[str, Mapping[str, FloatArray]],
    frequency: FloatArray,
    selected_groups: Mapping[str, Mapping[int, Sequence[str]]],
    all_groups: Mapping[str, Mapping[int, Sequence[str]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for configuration in ARRAY_CONFIGURATIONS:
        for analysis_set, groups in (
            ("selected", selected_groups[configuration]),
            ("all", all_groups[configuration]),
        ):
            spectrum = direction_discriminability_spectrum(
                curves_by_configuration[configuration], groups,
            )
            for index, frequency_hz in enumerate(frequency):
                if not 200.0 <= frequency_hz <= 8000.0:
                    continue
                rows.append({
                    "configuration": configuration,
                    "analysis_set": analysis_set,
                    "frequency_hz": float(frequency_hz),
                    "between_direction_rms_db": float(
                        spectrum["between_direction_rms_db"][index]
                    ),
                    "within_direction_rms_db": float(
                        spectrum["within_direction_rms_db"][index]
                    ),
                    "between_to_within_ratio": float(
                        spectrum["between_to_within_ratio"][index]
                    ),
                    "scope": (
                        "post_hoc_exploratory_localisation_frequency_bins_not_independent"
                    ),
                })
    return rows


def _top_direction_frequency_peaks(
    rows: Sequence[Mapping[str, Any]], *, count: int = 5,
) -> dict[str, list[dict[str, float]]]:
    result: dict[str, list[dict[str, float]]] = {}
    for configuration in ARRAY_CONFIGURATIONS:
        candidates = sorted(
            (
                row for row in rows
                if row["configuration"] == configuration
                and row["analysis_set"] == "selected"
                and math.isfinite(float(row["between_to_within_ratio"]))
            ),
            key=lambda row: float(row["between_to_within_ratio"]),
            reverse=True,
        )
        selected: list[dict[str, float]] = []
        for row in candidates:
            center = float(row["frequency_hz"])
            if any(
                2.0 ** (-1.0 / 6.0) <= center / item["frequency_hz"]
                <= 2.0 ** (1.0 / 6.0)
                for item in selected
            ):
                continue
            selected.append({
                "frequency_hz": center,
                "between_direction_rms_db": float(row["between_direction_rms_db"]),
                "within_direction_rms_db": float(row["within_direction_rms_db"]),
                "between_to_within_ratio": float(row["between_to_within_ratio"]),
            })
            if len(selected) == count:
                break
        result[configuration] = selected
    return result


def _technical_repeatability(
    curves: Mapping[str, FloatArray],
    frequency: FloatArray,
    groups: Mapping[int, Sequence[str]],
    *,
    configuration: str,
    analysis_set: str,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    primary = _finite_mask(curves, frequency, 200.0, 4000.0)
    secondary = _finite_mask(curves, frequency, 4000.0, 8000.0)
    rows: list[dict[str, Any]] = []
    pooled_raw: list[float] = []
    pooled_shape: list[float] = []
    pooled_secondary_shape: list[float] = []
    for angle in ANGLES:
        raw_values: list[float] = []
        shape_values: list[float] = []
        secondary_values: list[float] = []
        for left, right in itertools.combinations(groups[angle], 2):
            difference = curves[left] - curves[right]
            raw_values.append(_rms(difference[primary]))
            shape_values.append(_rms(_demean(difference[primary])))
            secondary_values.append(_rms(_demean(difference[secondary])))
        pooled_raw.extend(raw_values)
        pooled_shape.extend(shape_values)
        pooled_secondary_shape.extend(secondary_values)
        rows.append({
            "configuration": configuration,
            "analysis_set": analysis_set,
            "direction_deg": angle,
            "pair_count": len(raw_values),
            "primary_raw_pair_rms_median_db": float(np.median(raw_values)),
            "primary_raw_pair_rms_p95_db": float(np.quantile(raw_values, 0.95)),
            "primary_raw_pair_rms_max_db": float(np.max(raw_values)),
            "primary_shape_pair_rms_median_db": float(np.median(shape_values)),
            "primary_shape_pair_rms_p95_db": float(np.quantile(shape_values, 0.95)),
            "primary_shape_pair_rms_max_db": float(np.max(shape_values)),
            "secondary_shape_pair_rms_median_db": float(np.median(secondary_values)),
            "secondary_shape_pair_rms_p95_db": float(np.quantile(secondary_values, 0.95)),
            "secondary_shape_pair_rms_max_db": float(np.max(secondary_values)),
        })
    summary = {
        "primary_raw_p95_db": float(np.quantile(pooled_raw, 0.95)),
        "primary_shape_p95_db": float(np.quantile(pooled_shape, 0.95)),
        "primary_shape_median_db": float(np.median(pooled_shape)),
        "secondary_shape_p95_db": float(np.quantile(pooled_secondary_shape, 0.95)),
        "pair_count": len(pooled_shape),
    }
    return rows, summary


def _direction_statistic(
    curves: Mapping[str, FloatArray],
    frequency: FloatArray,
    groups: Mapping[int, Sequence[str]],
) -> float:
    mask = _finite_mask(curves, frequency, 200.0, 4000.0)
    representatives = _representatives(curves, groups)
    values = [
        _rms(_demean((representatives[left] - representatives[right])[mask]))
        for left, right in itertools.combinations(ANGLES, 2)
    ]
    return float(np.median(values))


def _direction_permutation_p(
    curves: Mapping[str, FloatArray],
    frequency: FloatArray,
    groups: Mapping[int, Sequence[str]],
    *,
    random_state: int,
    iterations: int,
) -> float:
    observed = _direction_statistic(curves, frequency, groups)
    sample_ids = [sample_id for angle in ANGLES for sample_id in groups[angle]]
    group_size = len(groups[ANGLES[0]])
    rng = np.random.default_rng(random_state)
    exceeding = 0
    for _ in range(iterations):
        shuffled = list(rng.permutation(sample_ids))
        permuted = {
            angle: shuffled[index * group_size:(index + 1) * group_size]
            for index, angle in enumerate(ANGLES)
        }
        if _direction_statistic(curves, frequency, permuted) >= observed - 1.0e-12:
            exceeding += 1
    return float((exceeding + 1) / (iterations + 1))


def _direction_pairwise_rows(
    curves: Mapping[str, FloatArray],
    frequency: FloatArray,
    selected_groups: Mapping[int, Sequence[str]],
    all_groups: Mapping[int, Sequence[str]],
    *,
    configuration: str,
    selected_floor: Mapping[str, float],
) -> list[dict[str, Any]]:
    masks = {
        "primary": _finite_mask(curves, frequency, 200.0, 4000.0),
        "secondary": _finite_mask(curves, frequency, 4000.0, 8000.0),
    }
    selected_reps = _representatives(curves, selected_groups)
    all_reps = _representatives(curves, all_groups)
    rows: list[dict[str, Any]] = []
    for left, right in itertools.combinations(ANGLES, 2):
        for band, mask in masks.items():
            selected_delta = selected_reps[left] - selected_reps[right]
            all_delta = all_reps[left] - all_reps[right]
            selected_raw = _rms(selected_delta[mask])
            selected_shape = _rms(_demean(selected_delta[mask]))
            all_shape = _rms(_demean(all_delta[mask]))
            floor_key = (
                "primary_shape_p95_db" if band == "primary"
                else "secondary_shape_p95_db"
            )
            floor = float(selected_floor[floor_key])
            rows.append({
                "configuration": configuration,
                "direction_a_deg": left,
                "direction_b_deg": right,
                "band_id": band,
                "selected_raw_rms_db": selected_raw,
                "selected_demeaned_rms_db": selected_shape,
                "selected_technical_p95_db": floor,
                "selected_effect_to_floor_ratio": selected_shape / floor,
                "selected_clearly_exceeds_floor": selected_shape > floor,
                "all4_demeaned_rms_db": all_shape,
                "selection_sensitivity_shift_db": selected_shape - all_shape,
            })
    return rows


def _bootstrap_direction_statistics(
    curves_by_configuration: Mapping[str, Mapping[str, FloatArray]],
    frequency: FloatArray,
    groups_by_configuration: Mapping[str, Mapping[int, Sequence[str]]],
    *,
    random_state: int,
    iterations: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(random_state)
    bootstrap = {configuration: [] for configuration in ARRAY_CONFIGURATIONS}
    deltas: list[float] = []
    for _ in range(iterations):
        values: dict[str, float] = {}
        for configuration in ARRAY_CONFIGURATIONS:
            groups = groups_by_configuration[configuration]
            sampled = {
                angle: list(rng.choice(
                    groups[angle], size=len(groups[angle]), replace=True,
                ))
                for angle in ANGLES
            }
            value = _direction_statistic(
                curves_by_configuration[configuration], frequency, sampled,
            )
            bootstrap[configuration].append(value)
            values[configuration] = value
        deltas.append(values["U4HR"] - values["U4SYM"])
    return {
        "U4SYM_ci": tuple(float(item) for item in np.percentile(
            bootstrap["U4SYM"], [2.5, 97.5],
        )),
        "U4HR_ci": tuple(float(item) for item in np.percentile(
            bootstrap["U4HR"], [2.5, 97.5],
        )),
        "delta_ci": tuple(float(item) for item in np.percentile(deltas, [2.5, 97.5])),
    }


def _band_vector(
    curve: FloatArray, frequency: FloatArray, centers: Mapping[str, float],
) -> FloatArray:
    values: list[float] = []
    for module in S3_MODULES:
        center = centers[module]
        mask = (
            (frequency >= center * 2.0 ** (-1.0 / 12.0))
            & (frequency <= center * 2.0 ** (1.0 / 12.0))
            & np.isfinite(curve)
        )
        values.append(float(np.mean(curve[mask])))
    return _demean(np.asarray(values, dtype=np.float64))


def _direction_channel_matrix(
    curves: Mapping[str, FloatArray],
    frequency: FloatArray,
    groups: Mapping[int, Sequence[str]],
    centers: Mapping[str, float],
    polarity_signs: Mapping[str, int],
) -> FloatArray:
    representatives = _representatives(curves, groups)
    grand = np.mean(np.vstack([representatives[angle] for angle in ANGLES]), axis=0)
    matrix = np.zeros((4, 4), dtype=np.float64)
    for angle_index, angle in enumerate(ANGLES):
        direction_delta = representatives[angle] - grand
        for module_index, module in enumerate(S3_MODULES):
            center = centers[module]
            mask = (
                (frequency >= center * 2.0 ** (-1.0 / 12.0))
                & (frequency <= center * 2.0 ** (1.0 / 12.0))
            )
            signed_shift = float(np.mean(direction_delta[mask]))
            matrix[angle_index, module_index] = polarity_signs[module] * signed_shift
    return matrix


def _bootstrap_code_scores(
    curves_by_configuration: Mapping[str, Mapping[str, FloatArray]],
    frequency: FloatArray,
    groups_by_configuration: Mapping[str, Mapping[int, Sequence[str]]],
    centers: Mapping[str, float],
    polarity_signs: Mapping[str, int],
    *,
    random_state: int,
    iterations: int,
) -> dict[str, tuple[float, float]]:
    rng = np.random.default_rng(random_state)
    scores = {configuration: [] for configuration in ARRAY_CONFIGURATIONS}
    deltas: list[float] = []
    for _ in range(iterations):
        values: dict[str, float] = {}
        for configuration in ARRAY_CONFIGURATIONS:
            groups = groups_by_configuration[configuration]
            sampled = {
                angle: list(rng.choice(
                    groups[angle], size=len(groups[angle]), replace=True,
                ))
                for angle in ANGLES
            }
            matrix = _direction_channel_matrix(
                curves_by_configuration[configuration], frequency, sampled,
                centers, polarity_signs,
            )
            value = float(direction_code_score(matrix)["score_db"])
            scores[configuration].append(value)
            values[configuration] = value
        deltas.append(values["U4HR"] - values["U4SYM"])
    return {
        "U4SYM": tuple(float(item) for item in np.percentile(
            scores["U4SYM"], [2.5, 97.5],
        )),
        "U4HR": tuple(float(item) for item in np.percentile(
            scores["U4HR"], [2.5, 97.5],
        )),
        "delta": tuple(float(item) for item in np.percentile(deltas, [2.5, 97.5])),
    }


def _code_rows(
    matrices: Mapping[tuple[str, str], FloatArray],
    bootstrap_ci: Mapping[str, tuple[float, float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    matrix_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for configuration in ARRAY_CONFIGURATIONS:
        for analysis_set in ("selected", "all"):
            matrix = matrices[(configuration, analysis_set)]
            for angle_index, angle in enumerate(ANGLES):
                for module_index, module in enumerate(S3_MODULES):
                    value = float(matrix[angle_index, module_index])
                    expected = S3_MODULE_BY_ANGLE[angle] == module
                    column = matrix[:, module_index]
                    rank = int(
                        np.where(np.argsort(column)[::-1] == angle_index)[0][0] + 1
                    )
                    matrix_rows.append({
                        "configuration": configuration,
                        "analysis_set": analysis_set,
                        "direction_deg": angle,
                        "channel_module": module,
                        "calibrated_center_hz": "",
                        "polarity_aligned_direction_shift_db": value,
                        "expected_direction_channel": expected,
                        "direction_rank_within_channel": rank,
                    })
            score = direction_code_score(matrix)
            ci = bootstrap_ci.get(configuration) if analysis_set == "selected" else None
            summary_rows.append({
                "configuration": configuration,
                "analysis_set": analysis_set,
                **score,
                "repeat_bootstrap_ci95_low_db": ci[0] if ci else "",
                "repeat_bootstrap_ci95_high_db": ci[1] if ci else "",
                "bootstrap_scope": (
                    "within_direction_repeat_resampling_single_campaign"
                    if ci else "not_run_all_repeat_sensitivity"
                ),
            })
    selected_sym = direction_code_score(matrices[("U4SYM", "selected")])
    selected_hr = direction_code_score(matrices[("U4HR", "selected")])
    all_sym = direction_code_score(matrices[("U4SYM", "all")])
    all_hr = direction_code_score(matrices[("U4HR", "all")])
    summary_rows.append({
        "configuration": "U4HR_minus_U4SYM",
        "analysis_set": "selected",
        "score_db": float(selected_hr["score_db"]) - float(selected_sym["score_db"]),
        "diagonal_mean_db": "",
        "off_diagonal_mean_db": "",
        "correct_direction_top1_count": "",
        "correct_direction_top2_count": "",
        "exact_mapping_permutation_p": "",
        "repeat_bootstrap_ci95_low_db": bootstrap_ci["delta"][0],
        "repeat_bootstrap_ci95_high_db": bootstrap_ci["delta"][1],
        "bootstrap_scope": "independent_configuration_repeat_resampling_single_campaign",
    })
    summary_rows.append({
        "configuration": "U4HR_minus_U4SYM",
        "analysis_set": "all",
        "score_db": float(all_hr["score_db"]) - float(all_sym["score_db"]),
        "diagonal_mean_db": "",
        "off_diagonal_mean_db": "",
        "correct_direction_top1_count": "",
        "correct_direction_top2_count": "",
        "exact_mapping_permutation_p": "",
        "repeat_bootstrap_ci95_low_db": "",
        "repeat_bootstrap_ci95_high_db": "",
        "bootstrap_scope": "not_run_all_repeat_sensitivity",
    })
    return matrix_rows, summary_rows


def _configuration_target_rows(
    curves_by_configuration: Mapping[str, Mapping[str, FloatArray]],
    frequency: FloatArray,
    groups_by_configuration: Mapping[str, Mapping[int, Sequence[str]]],
    centers: Mapping[str, float],
) -> list[dict[str, Any]]:
    reps = {
        configuration: _representatives(
            curves_by_configuration[configuration], groups_by_configuration[configuration],
        )
        for configuration in ARRAY_CONFIGURATIONS
    }
    rows: list[dict[str, Any]] = []
    for angle in ANGLES:
        delta = reps["U4HR"][angle] - reps["U4SYM"][angle]
        for module in S3_MODULES:
            center = centers[module]
            mask = (
                (frequency >= center * 2.0 ** (-1.0 / 6.0))
                & (frequency <= center * 2.0 ** (1.0 / 6.0))
            )
            residual = _local_residual(frequency[mask], delta[mask])
            index = int(np.argmax(np.abs(residual)))
            rows.append({
                "direction_deg": angle,
                "channel_module": module,
                "expected_direction_channel": S3_MODULE_BY_ANGLE[angle] == module,
                "calibrated_center_hz": center,
                "u4hr_minus_u4sym_window_rms_db": _rms(residual),
                "u4hr_minus_u4sym_signed_extreme_db": float(residual[index]),
                "u4hr_minus_u4sym_extreme_hz": float(frequency[mask][index]),
            })
    return rows


def _mechanism_rows(
    curves_by_configuration: Mapping[str, Mapping[str, FloatArray]],
    frequency: FloatArray,
    selected_groups: Mapping[str, Mapping[int, Sequence[str]]],
    all_groups: Mapping[str, Mapping[int, Sequence[str]]],
    s1_signatures: Mapping[str, FloatArray],
) -> list[dict[str, Any]]:
    mask = _finite_mask(s1_signatures, frequency, 800.0, 5000.0)
    rows: list[dict[str, Any]] = []
    for analysis_set, groups_by_config in (
        ("selected", selected_groups), ("all", all_groups),
    ):
        reps = {
            configuration: _representatives(
                curves_by_configuration[configuration], groups_by_config[configuration],
            )
            for configuration in ARRAY_CONFIGURATIONS
        }
        for angle in ANGLES:
            delta = _demean((reps["U4HR"][angle] - reps["U4SYM"][angle])[mask])
            values: list[tuple[str, float]] = []
            pending: list[dict[str, Any]] = []
            for module in S3_MODULES:
                signature = _demean(s1_signatures[module][mask])
                pearson = float(np.corrcoef(delta, signature)[0, 1])
                cosine = float(
                    np.dot(delta, signature)
                    / (np.linalg.norm(delta) * np.linalg.norm(signature))
                )
                values.append((module, pearson))
                pending.append({
                    "analysis_set": analysis_set,
                    "direction_deg": angle,
                    "single_entry_module": module,
                    "expected_module": S3_MODULE_BY_ANGLE[angle] == module,
                    "pearson_800_5000hz": pearson,
                    "cosine_800_5000hz": cosine,
                })
            ranks = {
                module: index + 1
                for index, (module, _) in enumerate(
                    sorted(values, key=lambda item: item[1], reverse=True)
                )
            }
            for row in pending:
                row["pearson_rank_within_direction"] = ranks[
                    str(row["single_entry_module"])
                ]
                rows.append(row)
    return rows


def _loocv_score(
    features: FloatArray, labels: NDArray[np.int64],
) -> float:
    predictions: list[int] = []
    for index in range(features.shape[0]):
        train_mask = np.arange(features.shape[0]) != index
        centroids = {
            label: np.mean(features[train_mask & (labels == label)], axis=0)
            for label in range(4)
        }
        prediction = min(
            centroids,
            key=lambda label: float(np.linalg.norm(features[index] - centroids[label])),
        )
        predictions.append(prediction)
    return float(np.mean(np.asarray(predictions) == labels))


def _loocv_rows(
    curves_by_configuration: Mapping[str, Mapping[str, FloatArray]],
    frequency: FloatArray,
    selected_groups: Mapping[str, Mapping[int, Sequence[str]]],
    all_groups: Mapping[str, Mapping[int, Sequence[str]]],
    centers: Mapping[str, float],
    *,
    random_state: int,
    permutation_iterations: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config_index, configuration in enumerate(ARRAY_CONFIGURATIONS):
        for set_index, (analysis_set, groups) in enumerate((
            ("selected", selected_groups[configuration]),
            ("all", all_groups[configuration]),
        )):
            sample_ids = [sample_id for angle in ANGLES for sample_id in groups[angle]]
            labels = np.asarray([
                angle_index
                for angle_index, angle in enumerate(ANGLES)
                for _ in groups[angle]
            ], dtype=np.int64)
            features = np.vstack([
                _band_vector(
                    curves_by_configuration[configuration][sample_id], frequency, centers,
                )
                for sample_id in sample_ids
            ])
            observed = _loocv_score(features, labels)
            rng = np.random.default_rng(
                random_state + config_index * 1000 + set_index * 100,
            )
            exceeding = 0
            for _ in range(permutation_iterations):
                permuted = rng.permutation(labels)
                if _loocv_score(features, permuted) >= observed - 1.0e-12:
                    exceeding += 1
            rows.append({
                "configuration": configuration,
                "analysis_set": analysis_set,
                "sample_count": len(sample_ids),
                "feature_count": 4,
                "feature_definition": (
                    "demeaned_four_S1_calibrated_target_band_means_plus_minus_1_12_octave"
                ),
                "validation": "leave_one_technical_repeat_out_same_campaign",
                "balanced_accuracy": observed,
                "permutation_p": (exceeding + 1) / (permutation_iterations + 1),
                "permutation_iterations": permutation_iterations,
                "status": "exploratory_no_independent_block_generalisation",
            })
    return rows


def _csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple)):
        return ";".join(str(item) for item in value)
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return ""
    return value


def _write_csv(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None,
) -> None:
    if not rows:
        raise V25JointInputError(f"refusing empty CSV: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = tuple(fields) if fields is not None else tuple(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fieldnames})


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _json_safe(payload), ensure_ascii=False, indent=2,
            sort_keys=True, allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )


def _write_plots(
    output: Path,
    frequency: FloatArray,
    s1_feature_rows: Sequence[Mapping[str, Any]],
    selected_representatives: Mapping[str, Mapping[int, FloatArray]],
    direction_pairwise_rows: Sequence[Mapping[str, Any]],
    code_matrices: Mapping[tuple[str, str], FloatArray],
    configuration_target_rows: Sequence[Mapping[str, Any]],
    mechanism_rows: Sequence[Mapping[str, Any]],
    direction_frequency_rows: Sequence[Mapping[str, Any]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    plot_dir = output / "plots"
    plot_dir.mkdir(parents=True)

    targets = np.asarray([float(row["target_hz"]) for row in s1_feature_rows])
    measured = np.asarray([float(row["measured_feature_hz"]) for row in s1_feature_rows])
    stable = np.asarray([
        bool(row["stable_single_campaign_signature"]) for row in s1_feature_rows
    ])
    fig, axis = plt.subplots(figsize=(7.5, 6.0))
    axis.plot([1000, 5000], [1000, 5000], "k--", label="1:1")
    axis.scatter(targets[~stable], measured[~stable], s=80, color="#e9c46a", label="limited")
    axis.scatter(targets[stable], measured[stable], s=80, color="#2a9d8f", label="stable")
    for row in s1_feature_rows:
        axis.annotate(str(row["module_id"]), (
            float(row["target_hz"]), float(row["measured_feature_hz"]),
        ))
    axis.set_xlabel("CAD target (Hz)")
    axis.set_ylabel("Selected-5 measured feature (Hz)")
    axis.set_title("V2.5 S1 recalibration under the single-campaign 5-of-6 rule")
    axis.grid(alpha=0.2)
    axis.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "s1_recalibrated_target_tracking.png", dpi=200)
    fig.savefig(plot_dir / "s1_recalibrated_target_tracking.svg")
    plt.close(fig)

    fig, axes = plt.subplots(2, 4, figsize=(16, 8), sharex=True, sharey=True)
    mask = (frequency >= 200.0) & (frequency <= 8000.0)
    for row_index, configuration in enumerate(ARRAY_CONFIGURATIONS):
        for column_index, angle in enumerate(ANGLES):
            axis = axes[row_index, column_index]
            axis.semilogx(
                frequency[mask], selected_representatives[configuration][angle][mask],
                color="#2a9d8f" if configuration == "U4HR" else "#457b9d",
            )
            axis.set_title(f"{configuration} D{angle:03d}")
            axis.grid(alpha=0.15)
            if row_index == 1:
                axis.set_xlabel("Frequency (Hz)")
            if column_index == 0:
                axis.set_ylabel("Smoothed level (dB SPL)")
    fig.suptitle("V2.5 S2/S3 selected-repeat direction representatives")
    fig.tight_layout()
    fig.savefig(plot_dir / "array_direction_representative_spectra.png", dpi=200)
    fig.savefig(plot_dir / "array_direction_representative_spectra.svg")
    plt.close(fig)

    primary_rows = [row for row in direction_pairwise_rows if row["band_id"] == "primary"]
    labels = [
        f"{row['configuration']} {int(row['direction_a_deg']):03d}-{int(row['direction_b_deg']):03d}"
        for row in primary_rows
    ]
    effects = [float(row["selected_demeaned_rms_db"]) for row in primary_rows]
    floors = [float(row["selected_technical_p95_db"]) for row in primary_rows]
    fig, axis = plt.subplots(figsize=(12, 5.5))
    x = np.arange(len(labels))
    axis.bar(x, effects, color=[
        "#457b9d" if str(row["configuration"]) == "U4SYM" else "#2a9d8f"
        for row in primary_rows
    ], label="between-direction effect")
    axis.scatter(x, floors, marker="_", s=500, color="black", label="within-direction p95")
    axis.set_xticks(x, labels, rotation=55, ha="right")
    axis.set_ylabel("Primary demeaned RMS (dB)")
    axis.set_title("Direction-pair effects versus contemporaneous technical floors")
    axis.grid(axis="y", alpha=0.2)
    axis.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "direction_pair_effects_vs_floor.png", dpi=200)
    fig.savefig(plot_dir / "direction_pair_effects_vs_floor.svg")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), constrained_layout=True)
    bound = max(
        float(np.max(np.abs(code_matrices[(configuration, "selected")])))
        for configuration in ARRAY_CONFIGURATIONS
    )
    for axis, configuration in zip(axes, ARRAY_CONFIGURATIONS, strict=True):
        matrix = code_matrices[(configuration, "selected")]
        image = axis.imshow(matrix, cmap="RdBu_r", vmin=-bound, vmax=bound, aspect="auto")
        axis.set_xticks(range(4), S3_MODULES)
        axis.set_yticks(range(4), [f"D{angle:03d}" for angle in ANGLES])
        axis.set_title(configuration)
        for row in range(4):
            for column in range(4):
                axis.text(column, row, f"{matrix[row, column]:.2f}", ha="center", va="center")
    fig.colorbar(
        image, ax=axes.ravel().tolist(),
        label="S1-polarity-aligned direction shift (dB)",
        shrink=0.86, pad=0.04,
    )
    fig.suptitle("Fixed four-channel direction matrices")
    fig.savefig(plot_dir / "direction_channel_matrices.png", dpi=200)
    fig.savefig(plot_dir / "direction_channel_matrices.svg")
    plt.close(fig)

    selected_target_rows = list(configuration_target_rows)
    target_matrix = np.zeros((4, 4), dtype=np.float64)
    for row in selected_target_rows:
        i = ANGLES.index(int(row["direction_deg"]))
        j = S3_MODULES.index(str(row["channel_module"]))
        target_matrix[i, j] = float(row["u4hr_minus_u4sym_window_rms_db"])
    fig, axis = plt.subplots(figsize=(7.0, 5.5))
    image = axis.imshow(target_matrix, cmap="magma", aspect="auto")
    axis.set_xticks(range(4), S3_MODULES)
    axis.set_yticks(range(4), [f"D{angle:03d}" for angle in ANGLES])
    axis.set_xlabel("S1 calibrated channel")
    axis.set_ylabel("Incident direction")
    axis.set_title("U4HR − U4SYM local target-window effect")
    for i in range(4):
        for j in range(4):
            axis.text(j, i, f"{target_matrix[i,j]:.2f}", ha="center", va="center",
                      color="white" if target_matrix[i,j] > np.max(target_matrix)*0.55 else "black")
    fig.colorbar(image, ax=axis, label="Local residual RMS (dB)")
    fig.tight_layout()
    fig.savefig(plot_dir / "u4hr_minus_u4sym_target_effect_matrix.png", dpi=200)
    fig.savefig(plot_dir / "u4hr_minus_u4sym_target_effect_matrix.svg")
    plt.close(fig)

    selected_mechanism = [
        row for row in mechanism_rows if row["analysis_set"] == "selected"
    ]
    correlation = np.zeros((4, 4), dtype=np.float64)
    for row in selected_mechanism:
        i = ANGLES.index(int(row["direction_deg"]))
        j = S3_MODULES.index(str(row["single_entry_module"]))
        correlation[i, j] = float(row["pearson_800_5000hz"])
    fig, axis = plt.subplots(figsize=(7.0, 5.5))
    image = axis.imshow(correlation, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto")
    axis.set_xticks(range(4), S3_MODULES)
    axis.set_yticks(range(4), [f"D{angle:03d}" for angle in ANGLES])
    axis.set_title("S3−S2 array difference versus S1 single-entry signatures")
    for i in range(4):
        for j in range(4):
            axis.text(j, i, f"{correlation[i,j]:.2f}", ha="center", va="center")
    fig.colorbar(image, ax=axis, label="Pearson correlation, 800–5000 Hz")
    fig.tight_layout()
    fig.savefig(plot_dir / "single_entry_array_mechanism_correspondence.png", dpi=200)
    fig.savefig(plot_dir / "single_entry_array_mechanism_correspondence.svg")
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(10.5, 7.5), sharex=True, sharey=True)
    colors = {"selected": "#2a9d8f", "all": "#6c757d"}
    styles = {"selected": "-", "all": "--"}
    for axis, configuration in zip(axes, ARRAY_CONFIGURATIONS, strict=True):
        for analysis_set in ("selected", "all"):
            subset = [
                row for row in direction_frequency_rows
                if row["configuration"] == configuration
                and row["analysis_set"] == analysis_set
            ]
            axis.semilogx(
                [float(row["frequency_hz"]) for row in subset],
                [float(row["between_to_within_ratio"]) for row in subset],
                styles[analysis_set], color=colors[analysis_set],
                label=("primary keep-rule" if analysis_set == "selected" else "all repeats"),
                linewidth=1.5,
            )
        axis.axhline(1.0, color="black", linewidth=1.0, alpha=0.6)
        axis.set_ylabel("Between / within RMS")
        axis.set_title(configuration)
        axis.grid(alpha=0.18)
        axis.legend()
    axes[-1].set_xlabel("Frequency (Hz)")
    fig.suptitle(
        "Exploratory direction discriminability spectrum\n"
        "(frequency bins are not independent inferential units)"
    )
    fig.tight_layout()
    fig.savefig(plot_dir / "exploratory_direction_frequency_map.png", dpi=200)
    fig.savefig(plot_dir / "exploratory_direction_frequency_map.svg")
    plt.close(fig)


def _write_artifact_manifests(output: Path) -> int:
    files = sorted(
        path for path in output.rglob("*")
        if path.is_file() and path.name not in {"artifact_manifest.json", "SHA256SUMS"}
    )
    artifacts = [{
        "path": path.relative_to(output).as_posix(),
        "sha256": artifact_sha256(path),
        "bytes": path.stat().st_size,
    } for path in files]
    _write_json(output / "artifact_manifest.json", {
        "schema_version": "v25_joint_artifact_manifest_v1",
        "algorithm": "SHA-256",
        "artifacts": artifacts,
    })
    sums = [*artifacts, {
        "path": "artifact_manifest.json",
        "sha256": artifact_sha256(output / "artifact_manifest.json"),
        "bytes": (output / "artifact_manifest.json").stat().st_size,
    }]
    (output / "SHA256SUMS").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in sums),
        encoding="utf-8",
    )
    return len(artifacts)


def verify_v25_joint_output_hashes(output_directory: str | Path) -> dict[str, Any]:
    root = Path(output_directory).resolve()
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise V25JointInputError("V2.5 joint artifact manifest is empty")
    sums: dict[str, str] = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator:
            raise V25JointInputError("invalid V2.5 joint SHA256SUMS line")
        sums[relative] = digest
    for entry in artifacts:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise V25JointInputError("V2.5 joint artifact path escapes output") from exc
        digest = artifact_sha256(path)
        if not path.is_file() or digest != entry["sha256"] or sums.get(relative) != digest:
            raise V25JointInputError(f"V2.5 joint artifact hash mismatch: {relative}")
    manifest_digest = artifact_sha256(root / "artifact_manifest.json")
    if sums.get("artifact_manifest.json") != manifest_digest:
        raise V25JointInputError("V2.5 joint manifest is not bound by SHA256SUMS")
    return {
        "all_match": True,
        "artifact_count": len(artifacts),
        "artifact_manifest_sha256": manifest_digest,
    }


def run_v25_joint_analysis(
    s1_zip_path: str | Path,
    s1_raw_txt_directory: str | Path,
    s1_raw_mdat_directory: str | Path,
    s2_zip_path: str | Path,
    s2_raw_txt_directory: str | Path,
    s2_raw_mdat_directory: str | Path,
    s3_zip_path: str | Path,
    s3_raw_txt_directory: str | Path,
    s3_raw_mdat_directory: str | Path,
    output_directory: str | Path,
    *,
    source_commit: str,
    source_worktree_clean: bool,
    created_at: str | datetime,
    random_state: int = 250824,
    bootstrap_iterations: int = 2000,
    permutation_iterations: int = 2000,
) -> V25JointRunResult:
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise V25JointInputError("source_commit must be a full lowercase Git SHA")
    timestamp = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)
    parsed_time = datetime.fromisoformat(timestamp)
    if parsed_time.tzinfo is None:
        raise V25JointInputError("created_at must include timezone")
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite V2.5 joint output: {output}")

    s1_inventory = inspect_v25_s1_archive(
        s1_zip_path, expected_zip_sha256=V25S1_ZIP_SHA256,
        extracted_txt_directory=s1_raw_txt_directory,
        extracted_mdat_directory=s1_raw_mdat_directory,
    )
    s2_inventory = inspect_v25_array_archive(
        s2_zip_path, expected_configuration="U4SYM",
        expected_zip_sha256=V25_S2_ZIP_SHA256,
        extracted_txt_directory=s2_raw_txt_directory,
        extracted_mdat_directory=s2_raw_mdat_directory,
    )
    s3_inventory = inspect_v25_array_archive(
        s3_zip_path, expected_configuration="U4HR",
        expected_zip_sha256=V25_S3_ZIP_SHA256,
        extracted_txt_directory=s3_raw_txt_directory,
        extracted_mdat_directory=s3_raw_mdat_directory,
    )
    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        raise FileExistsError(f"refusing to overwrite V2.5 joint staging: {staging}")
    staging.mkdir(parents=True)
    try:
        s1_curves, frequency, valid_mask, s1_qc, _, _ = preprocess_s1(s1_inventory)
        s2_curves, s2_frequency, s2_valid, s2_qc = _preprocess_array(s2_inventory)
        s3_curves, s3_frequency, s3_valid, s3_qc = _preprocess_array(s3_inventory)
        if not np.array_equal(frequency, s2_frequency) or not np.array_equal(
            frequency, s3_frequency,
        ):
            raise V25JointInputError("V2.5 S1/S2/S3 preprocessed grids differ")
        if not np.array_equal(valid_mask, s2_valid) or not np.array_equal(valid_mask, s3_valid):
            raise V25JointInputError("V2.5 S1/S2/S3 valid masks differ")

        s1_member_ids = {
            condition: tuple(
                member.sample_id for member in s1_inventory.txt_members
                if member.condition_id == condition
            )
            for condition in S1_CONDITIONS
        }
        s1_selections: dict[str, RepeatSelection] = {}
        selection_rows: list[dict[str, Any]] = []
        for condition in S1_CONDITIONS:
            group_curves = {
                sample_id: s1_curves[sample_id]
                for sample_id in s1_member_ids[condition]
            }
            selection = select_farthest_repeat(group_curves, frequency, keep_count=5)
            s1_selections[condition] = selection
            selection_rows.extend(_selection_rows(
                "V25-S1", condition.upper(), group_curves, selection,
            ))

        array_curves = {"U4SYM": s2_curves, "U4HR": s3_curves}
        inventories = {"U4SYM": s2_inventory, "U4HR": s3_inventory}
        selected_groups: dict[str, dict[int, Sequence[str]]] = {}
        all_groups: dict[str, dict[int, Sequence[str]]] = {}
        array_selections: dict[tuple[str, int], RepeatSelection] = {}
        for configuration in ARRAY_CONFIGURATIONS:
            inventory = inventories[configuration]
            selected_groups[configuration] = {}
            all_groups[configuration] = {}
            for angle in ANGLES:
                ids = tuple(
                    member.sample_id for member in inventory.txt_members
                    if member.direction_deg == angle
                )
                all_groups[configuration][angle] = ids
                group_curves = {
                    sample_id: array_curves[configuration][sample_id]
                    for sample_id in ids
                }
                selection = select_farthest_repeat(group_curves, frequency, keep_count=3)
                array_selections[(configuration, angle)] = selection
                selected_groups[configuration][angle] = selection.selected_sample_ids
                selection_rows.extend(_selection_rows(
                    "V25-S2" if configuration == "U4SYM" else "V25-S3",
                    f"{configuration}-D{angle:03d}", group_curves, selection,
                ))

        (
            s1_feature_rows, s1_channel_rows, s1_similarity_rows,
            s1_signatures, calibrated_centers, polarity_signs,
        ) = _s1_analysis(
            s1_curves, frequency, s1_member_ids, s1_selections,
            random_state=random_state,
            bootstrap_iterations=bootstrap_iterations,
        )

        repeatability_rows: list[dict[str, Any]] = []
        technical_summary: dict[tuple[str, str], dict[str, float]] = {}
        for configuration in ARRAY_CONFIGURATIONS:
            for analysis_set, groups in (
                ("selected", selected_groups[configuration]),
                ("all", all_groups[configuration]),
            ):
                rows, summary = _technical_repeatability(
                    array_curves[configuration], frequency, groups,
                    configuration=configuration, analysis_set=analysis_set,
                )
                repeatability_rows.extend(rows)
                technical_summary[(configuration, analysis_set)] = summary

        direction_pairwise_rows: list[dict[str, Any]] = []
        direction_summary_rows: list[dict[str, Any]] = []
        for configuration_index, configuration in enumerate(ARRAY_CONFIGURATIONS):
            direction_pairwise_rows.extend(_direction_pairwise_rows(
                array_curves[configuration], frequency,
                selected_groups[configuration], all_groups[configuration],
                configuration=configuration,
                selected_floor=technical_summary[(configuration, "selected")],
            ))
            selected_stat = _direction_statistic(
                array_curves[configuration], frequency, selected_groups[configuration],
            )
            all_stat = _direction_statistic(
                array_curves[configuration], frequency, all_groups[configuration],
            )
            selected_p = _direction_permutation_p(
                array_curves[configuration], frequency, selected_groups[configuration],
                random_state=random_state + configuration_index * 1000,
                iterations=permutation_iterations,
            )
            all_p = _direction_permutation_p(
                array_curves[configuration], frequency, all_groups[configuration],
                random_state=random_state + 5000 + configuration_index * 1000,
                iterations=permutation_iterations,
            )
            for analysis_set, statistic, p_value in (
                ("selected", selected_stat, selected_p),
                ("all", all_stat, all_p),
            ):
                floor = technical_summary[(configuration, analysis_set)][
                    "primary_shape_p95_db"
                ]
                direction_summary_rows.append({
                    "configuration": configuration,
                    "analysis_set": analysis_set,
                    "between_direction_median_primary_demeaned_rms_db": statistic,
                    "within_direction_primary_shape_p95_db": floor,
                    "direction_effect_to_technical_floor_ratio": statistic / floor,
                    "direction_label_permutation_p": p_value,
                    "permutation_iterations": permutation_iterations,
                    "inference_scope": "single_campaign_repeat_units_no_independent_block",
                })
        direction_bootstrap = _bootstrap_direction_statistics(
            array_curves, frequency, selected_groups,
            random_state=random_state + 10000,
            iterations=bootstrap_iterations,
        )
        for row in direction_summary_rows:
            if row["analysis_set"] == "selected":
                ci = direction_bootstrap[f"{row['configuration']}_ci"]
                row["repeat_bootstrap_ci95_low_db"] = ci[0]
                row["repeat_bootstrap_ci95_high_db"] = ci[1]
            else:
                row["repeat_bootstrap_ci95_low_db"] = ""
                row["repeat_bootstrap_ci95_high_db"] = ""
        selected_stats = {
            row["configuration"]: float(
                row["between_direction_median_primary_demeaned_rms_db"]
            )
            for row in direction_summary_rows if row["analysis_set"] == "selected"
        }
        all_stats = {
            row["configuration"]: float(
                row["between_direction_median_primary_demeaned_rms_db"]
            )
            for row in direction_summary_rows if row["analysis_set"] == "all"
        }
        direction_summary_rows.extend([{
            "configuration": "U4HR_minus_U4SYM",
            "analysis_set": "selected",
            "between_direction_median_primary_demeaned_rms_db": (
                selected_stats["U4HR"] - selected_stats["U4SYM"]
            ),
            "within_direction_primary_shape_p95_db": "",
            "direction_effect_to_technical_floor_ratio": "",
            "direction_label_permutation_p": "",
            "permutation_iterations": bootstrap_iterations,
            "inference_scope": "independent_configuration_repeat_bootstrap_single_campaign",
            "repeat_bootstrap_ci95_low_db": direction_bootstrap["delta_ci"][0],
            "repeat_bootstrap_ci95_high_db": direction_bootstrap["delta_ci"][1],
        }, {
            "configuration": "U4HR_minus_U4SYM",
            "analysis_set": "all",
            "between_direction_median_primary_demeaned_rms_db": (
                all_stats["U4HR"] - all_stats["U4SYM"]
            ),
            "within_direction_primary_shape_p95_db": "",
            "direction_effect_to_technical_floor_ratio": "",
            "direction_label_permutation_p": "",
            "permutation_iterations": 0,
            "inference_scope": "all_repeat_sensitivity",
            "repeat_bootstrap_ci95_low_db": "",
            "repeat_bootstrap_ci95_high_db": "",
        }])

        code_matrices: dict[tuple[str, str], FloatArray] = {}
        for configuration in ARRAY_CONFIGURATIONS:
            code_matrices[(configuration, "selected")] = _direction_channel_matrix(
                array_curves[configuration], frequency, selected_groups[configuration],
                calibrated_centers, polarity_signs,
            )
            code_matrices[(configuration, "all")] = _direction_channel_matrix(
                array_curves[configuration], frequency, all_groups[configuration],
                calibrated_centers, polarity_signs,
            )
        code_ci = _bootstrap_code_scores(
            array_curves, frequency, selected_groups,
            calibrated_centers, polarity_signs,
            random_state=random_state + 20000,
            iterations=bootstrap_iterations,
        )
        code_matrix_rows, code_summary_rows = _code_rows(code_matrices, code_ci)
        for row in code_matrix_rows:
            row["calibrated_center_hz"] = calibrated_centers[str(row["channel_module"])]

        configuration_target_rows = _configuration_target_rows(
            array_curves, frequency, selected_groups, calibrated_centers,
        )
        mechanism_rows = _mechanism_rows(
            array_curves, frequency, selected_groups, all_groups, s1_signatures,
        )
        loocv_rows = _loocv_rows(
            array_curves, frequency, selected_groups, all_groups, calibrated_centers,
            random_state=random_state + 30000,
            permutation_iterations=permutation_iterations,
        )
        direction_frequency_rows = _direction_frequency_rows(
            array_curves, frequency, selected_groups, all_groups,
        )
        top_direction_frequency_peaks = _top_direction_frequency_peaks(
            direction_frequency_rows,
        )

        s1_inventory_rows: list[dict[str, Any]] = []
        s1_mdat = {
            (member.condition_id, member.repeat_number): member
            for member in s1_inventory.mdat_members
        }
        for member in s1_inventory.txt_members:
            paired = s1_mdat[(member.condition_id, member.repeat_number)]
            s1_inventory_rows.append({
                "sample_id": member.sample_id,
                "stage_id": "V25-S1",
                "condition_or_configuration": member.condition_id.upper(),
                "direction_deg": 0,
                "repeat_number": member.repeat_number,
                "txt_filename": member.filename,
                "txt_sha256": member.sha256,
                "mdat_filename": paired.filename,
                "mdat_sha256": paired.sha256,
                "source_zip_sha256": s1_inventory.zip_sha256,
                "data_origin": "real_experiment",
                "final_test_read": False,
            })
        array_inventory_rows: list[dict[str, Any]] = []
        for inventory in (s2_inventory, s3_inventory):
            mdat = {
                (member.direction_deg, member.repeat_number): member
                for member in inventory.mdat_members
            }
            for member in inventory.txt_members:
                paired = mdat[(member.direction_deg, member.repeat_number)]
                array_inventory_rows.append({
                    "sample_id": member.sample_id,
                    "stage_id": member.stage_id,
                    "condition_or_configuration": member.configuration,
                    "direction_deg": member.direction_deg,
                    "repeat_number": member.repeat_number,
                    "txt_filename": member.filename,
                    "txt_sha256": member.sha256,
                    "mdat_filename": paired.filename,
                    "mdat_sha256": paired.sha256,
                    "source_zip_sha256": inventory.zip_sha256,
                    "data_origin": "real_experiment",
                    "final_test_read": False,
                })

        _write_csv(staging / "s1_data_inventory.csv", s1_inventory_rows)
        _write_csv(staging / "array_data_inventory.csv", array_inventory_rows)
        _write_csv(staging / "s1_file_qc.csv", s1_qc)
        _write_csv(staging / "array_file_qc.csv", [*s2_qc, *s3_qc])
        _write_csv(staging / "repeat_selection.csv", selection_rows)
        _write_csv(staging / "s1_recalibrated_target_features.csv", s1_feature_rows)
        _write_csv(staging / "s1_target_channel_matrix.csv", s1_channel_rows)
        _write_csv(staging / "s1_signature_similarity.csv", s1_similarity_rows)
        _write_csv(staging / "array_technical_repeatability.csv", repeatability_rows)
        _write_csv(staging / "direction_pairwise_effects.csv", direction_pairwise_rows)
        _write_csv(staging / "direction_effect_summary.csv", direction_summary_rows)
        _write_csv(staging / "direction_channel_matrix.csv", code_matrix_rows)
        _write_csv(staging / "direction_code_summary.csv", code_summary_rows)
        _write_csv(
            staging / "u4hr_minus_u4sym_target_effects.csv", configuration_target_rows,
        )
        _write_csv(staging / "mechanism_correspondence.csv", mechanism_rows)
        _write_csv(staging / "within_session_loocv.csv", loocv_rows)
        _write_csv(
            staging / "exploratory_direction_frequency_map.csv",
            direction_frequency_rows,
        )

        all_sample_ids = [
            *[member.sample_id for member in s1_inventory.txt_members],
            *[member.sample_id for member in s2_inventory.txt_members],
            *[member.sample_id for member in s3_inventory.txt_members],
        ]
        all_curves = {**s1_curves, **s2_curves, **s3_curves}
        np.savez_compressed(
            staging / "preprocessed_spectra.npz",
            frequency_hz=frequency,
            valid_mask=valid_mask,
            sample_ids=np.asarray(all_sample_ids),
            magnitude_db=np.vstack([all_curves[sample_id] for sample_id in all_sample_ids]),
        )

        selected_representatives = {
            configuration: _representatives(
                array_curves[configuration], selected_groups[configuration],
            )
            for configuration in ARRAY_CONFIGURATIONS
        }
        _write_plots(
            staging, frequency, s1_feature_rows, selected_representatives,
            direction_pairwise_rows, code_matrices,
            configuration_target_rows, mechanism_rows, direction_frequency_rows,
        )

        selected_direction = {
            row["configuration"]: row
            for row in direction_summary_rows
            if row["analysis_set"] == "selected"
            and row["configuration"] in ARRAY_CONFIGURATIONS
        }
        selected_code = {
            row["configuration"]: row
            for row in code_summary_rows
            if row["analysis_set"] == "selected"
            and row["configuration"] in ARRAY_CONFIGURATIONS
        }
        selected_loocv = {
            row["configuration"]: row
            for row in loocv_rows if row["analysis_set"] == "selected"
        }
        expected_mechanism = [
            row for row in mechanism_rows
            if row["analysis_set"] == "selected" and row["expected_module"]
        ]
        stable_modules = [
            row["module_id"] for row in s1_feature_rows
            if row["stable_single_campaign_signature"]
        ]
        code_supported = bool(
            float(selected_code["U4HR"]["exact_mapping_permutation_p"]) <= 0.05
            and int(selected_code["U4HR"]["correct_direction_top1_count"]) >= 3
            and float(code_ci["delta"][0]) > 0.0
        )
        direction_effect_detected = bool(
            float(selected_direction["U4HR"]["direction_label_permutation_p"]) <= 0.05
            and float(selected_direction["U4HR"][
                "direction_effect_to_technical_floor_ratio"
            ]) > 1.0
        )
        if code_supported:
            disposition = "within_campaign_expected_frequency_direction_code_supported"
        elif direction_effect_detected:
            disposition = "direction_spectral_effect_without_confirmed_expected_code"
        else:
            disposition = "expected_direction_code_not_supported_single_campaign"
        summary = {
            "schema_version": V25_JOINT_SCHEMA_VERSION,
            "created_at": timestamp,
            "status": "V25_S1_S2_S3_joint_analysis_complete",
            "inventory": {
                "s1_txt_count": 54, "s1_mdat_count": 54,
                "s2_txt_count": 16, "s2_mdat_count": 16,
                "s3_txt_count": 16, "s3_mdat_count": 16,
                "total_txt_count": 86, "total_mdat_count": 86,
                "zip_sha256": {
                    "S1": s1_inventory.zip_sha256,
                    "S2": s2_inventory.zip_sha256,
                    "S3": s3_inventory.zip_sha256,
                },
                "raw_copies_hash_verified": True,
                "mdat_preserved_not_parsed": True,
            },
            "revised_repeat_rule": {
                "S1": "single_campaign_six_repeats_drop_unique_farthest_keep_five",
                "S2_S3": "per_direction_four_repeats_drop_unique_farthest_keep_three",
                "distance": "curve_to_all_repeat_group_median_primary_200_4000hz_raw_rms",
                "selection_independent_of_outcome": True,
                "all_repeat_sensitivity_emitted": True,
                "raw_curve_deleted": False,
                "primary_selected_txt_count": 69,
                "primary_drop_flag_count": 17,
            },
            "preprocessing": {
                **frozen_formal_preprocessing_contract(),
                "preprocessing_algorithm_version": FORMAL_PREPROCESSING_ALGORITHM_VERSION,
            },
            "qc": {
                "structural_fail_count": 0,
                "array_open_channel_note_mismatch_count": sum(
                    not bool(row["open_channel_note_matches"]) for row in [*s2_qc, *s3_qc]
                ),
                "S2_all_notes_declare_one_open_channel": True,
                "S3_one_open_channel_note_sample_id": "V25S3-U4HR-D000-R02",
                "physical_four_open_assembly_requires_user_confirmation": True,
                "automatic_exclusion": False,
            },
            "s1": {
                "stable_single_campaign_modules": stable_modules,
                "stable_single_campaign_count": len(stable_modules),
                "independent_block_repeatability_claim_available": False,
            },
            "direction_effect": {
                "selected": selected_direction,
                "u4hr_minus_u4sym_bootstrap_ci95_db": direction_bootstrap["delta_ci"],
            },
            "expected_direction_code": {
                "selected": selected_code,
                "u4hr_minus_u4sym_score_bootstrap_ci95_db": code_ci["delta"],
                "supported_single_campaign": code_supported,
            },
            "mechanism_correspondence": {
                "expected_module_rank1_count_of_4": sum(
                    int(row["pearson_rank_within_direction"]) == 1
                    for row in expected_mechanism
                ),
                "expected_module_pearson": {
                    str(int(row["direction_deg"])): float(row["pearson_800_5000hz"])
                    for row in expected_mechanism
                },
            },
            "within_session_loocv": selected_loocv,
            "exploratory_direction_frequency_peaks": {
                "method": (
                    "top_nonoverlapping_selected_repeat_between_to_within_ratio_"
                    "peaks_minimum_one_sixth_octave_center_separation"
                ),
                "inference_status": "post_hoc_exploratory_not_confirmatory",
                "frequency_bins_treated_as_independent": False,
                "peaks": top_direction_frequency_peaks,
            },
            "disposition": disposition,
            "claim_boundary": {
                "single_campaign_only": True,
                "independent_block_generalisation_tested": False,
                "classification_generalisation_supported": False,
                "distance_causality_tested": False,
                "H1_confirmed": False,
                "final_test_read": False,
                "scientifically_eligible_metadata_changed": False,
            },
        }
        _write_json(staging / "analysis_summary.json", summary)
        _write_json(staging / "run_manifest.json", {
            "schema_version": V25_JOINT_SCHEMA_VERSION,
            "created_at": timestamp,
            "source_commit": source_commit,
            "source_worktree_clean": source_worktree_clean,
            "source_zips": {
                "S1": str(s1_inventory.zip_path),
                "S2": str(s2_inventory.zip_path),
                "S3": str(s3_inventory.zip_path),
            },
            "random_state": random_state,
            "bootstrap_iterations": bootstrap_iterations,
            "permutation_iterations": permutation_iterations,
            "data_origin": "real_experiment",
            "analysis_scope": "V25 S1/S2/S3 only",
            "classification_scope": "exploratory_same_campaign_fixed_four_band_LOOCV",
            "final_test_read": False,
        })
        artifact_count = _write_artifact_manifests(staging)
        staging.rename(output)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    verified = verify_v25_joint_output_hashes(output)
    if not verified["all_match"]:
        raise V25JointInputError("V2.5 joint output verification failed")
    return V25JointRunResult(
        output_directory=output,
        s1_txt_count=54,
        s2_txt_count=16,
        s3_txt_count=16,
        primary_selected_count=69,
        flagged_count=17,
        artifact_count=artifact_count,
    )
