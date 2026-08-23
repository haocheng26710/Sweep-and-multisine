"""SUP-1 single-position ENC-A..H module scan.

This module keeps the supplemental corpus separate from FORMAL-3/4, applies
the frozen FORMAL-1 preprocessing contract, and uses the SUP-0 windows without
reselecting frequencies.  Four-repeat modules contribute the most coherent
three-repeat triplet to the primary view; the fourth repeat is retained as an
audited sensitivity record and is never silently deleted.
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
    FeatureKind,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    QCStatus,
    Representation,
    SourceFormat,
    SpectrumData,
    artifact_sha256,
    save_feature_set,
)
from .supplemental_frequency_localization import verify_sup0_output_hashes
from .version import (
    CONFIG_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    MEASUREMENT_SCHEMA_VERSION,
    PIPELINE_VERSION,
)


SUP1_SCHEMA_VERSION = "sup1_enc_module_scan_v1"
SUP1_ZIP_SHA256 = "ed3eccbfa574c6b83d74fedce2bab80d3895eb77293ddc340f92c8fa00879875"
SUP1_PRIMARY_FLOOR_P95_DB = 0.8792543414488713
SUP1_SECONDARY_FLOOR_P95_DB = 1.345171254352607
SUP1_CROSS_REPEAT_STABLE_MINIMUM = 7
_MODULES = tuple("ABCDEFGH")
_NAME = re.compile(r"^R C03_U4ENC_(?P<module>[A-H])(?P<repeat>0[1-4])\.txt$")


class Sup1InputError(ValueError):
    """Raised when SUP-1 input, frozen rules, or output integrity fails."""


@dataclass(frozen=True, slots=True)
class Sup1Member:
    archive_path: str
    filename: str
    module_id: str
    repeat_id: str
    sha256: str
    size_bytes: int

    @property
    def sample_id(self) -> str:
        return f"SUP1-ENC-{self.module_id}-R{self.repeat_id}"


@dataclass(frozen=True, slots=True)
class Sup1Inventory:
    zip_path: Path
    zip_sha256: str
    members: tuple[Sup1Member, ...]
    module_counts: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class Sup1RunResult:
    output_directory: Path
    measurement_count: int
    primary_measurement_count: int
    extra_repeat_count: int
    flagged_count: int
    candidate_window_count: int
    artifact_count: int


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_sup1_archive(
    zip_path: str | Path,
    *,
    expected_zip_sha256: str = SUP1_ZIP_SHA256,
    extracted_raw_directory: str | Path | None = None,
) -> Sup1Inventory:
    """Read-only inventory and hash verification for the 29-file SUP-1 ZIP."""
    source = Path(zip_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SUP-1 ZIP does not exist: {source}")
    actual_zip_sha = _sha256_file(source)
    if actual_zip_sha != expected_zip_sha256:
        raise Sup1InputError(
            f"SUP-1 ZIP SHA-256 mismatch: expected {expected_zip_sha256}, found {actual_zip_sha}"
        )
    members: list[Sup1Member] = []
    with zipfile.ZipFile(source, "r") as archive:
        files = [item for item in archive.infolist() if not item.is_dir()]
        names = [item.filename for item in files]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicates:
            raise Sup1InputError(f"duplicate SUP-1 ZIP paths: {duplicates}")
        for info in files:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
                raise Sup1InputError(f"unsafe or nested SUP-1 member path: {info.filename}")
            match = _NAME.fullmatch(path.name)
            if match is None:
                raise Sup1InputError(f"cannot reliably identify module/repeat: {info.filename}")
            payload = archive.read(info)
            members.append(Sup1Member(
                archive_path=info.filename,
                filename=path.name,
                module_id=match.group("module"),
                repeat_id=match.group("repeat"),
                sha256=_sha256_bytes(payload),
                size_bytes=len(payload),
            ))
    if len(members) != 29:
        raise Sup1InputError(f"SUP-1 requires 29 TXT files; found {len(members)}")
    if len({(member.module_id, member.repeat_id) for member in members}) != 29:
        raise Sup1InputError("duplicate SUP-1 module/repeat identity")
    if len({member.sha256 for member in members}) != 29:
        raise Sup1InputError("duplicate SUP-1 file content")
    counts = Counter(member.module_id for member in members)
    expected_counts = {module: (3 if module in "ABC" else 4) for module in _MODULES}
    if dict(counts) != expected_counts:
        raise Sup1InputError(f"SUP-1 module counts mismatch: {dict(counts)}")
    for module, expected_count in expected_counts.items():
        actual_repeats = sorted(
            member.repeat_id for member in members if member.module_id == module
        )
        expected_repeats = [f"{index:02d}" for index in range(1, expected_count + 1)]
        if actual_repeats != expected_repeats:
            raise Sup1InputError(
                f"SUP-1 repeat sequence mismatch for ENC-{module}: {actual_repeats}"
            )
    members.sort(key=lambda member: (member.module_id, member.repeat_id))
    if extracted_raw_directory is not None:
        raw = Path(extracted_raw_directory).resolve()
        for member in members:
            path = raw / member.filename
            if not path.is_file() or _sha256_file(path) != member.sha256:
                raise Sup1InputError(f"extracted raw copy mismatch: {member.filename}")
        raw_names = sorted(path.name for path in raw.iterdir() if path.is_file())
        if raw_names != sorted(member.filename for member in members):
            raise Sup1InputError("extracted raw directory inventory differs from ZIP")
    return Sup1Inventory(source, actual_zip_sha, tuple(members), expected_counts)


def _preprocessing_id() -> str:
    payload = {
        **frozen_formal_preprocessing_contract(),
        "preprocessing_algorithm_version": FORMAL_PREPROCESSING_ALGORITHM_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _meta(member: Sup1Member, inventory: Sup1Inventory, reasons: Sequence[str]) -> MeasurementMeta:
    return MeasurementMeta(
        sample_id=member.sample_id,
        pipeline_version=PIPELINE_VERSION,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        measurement_schema_version=MEASUREMENT_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        device_version="V2_single_module_fixture",
        configuration=f"ENC-{member.module_id}",
        angle_deg=0.0,
        session_id="SUP1-S01",
        repeat_type="CONT",
        repeat_id=member.repeat_id,
        experiment_step="SUP-1_ENC_MODULE_SCAN",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=f"zip://{inventory.zip_path.as_posix()}!/{member.archive_path}",
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_ANALYSIS,
        source_sha256=member.sha256,
        provenance_uri=f"sha256:{inventory.zip_sha256}#member={member.sha256}",
        eligible_for_scientific_analysis=False,
        assembly_id="SUP1-SINGLE-POSITION",
        acquisition_block_id=f"SUP1-ENC-{member.module_id}",
        valid=True,
        qc_status=QCStatus.WARNING if reasons else QCStatus.VALID,
        manual_review_reasons=tuple(reasons),
    )


def _qc_and_preprocess(
    inventory: Sup1Inventory,
) -> tuple[dict[str, FeatureSet], list[dict[str, Any]], dict[str, Mapping[str, Any]]]:
    features: dict[str, FeatureSet] = {}
    qc_rows: list[dict[str, Any]] = []
    preprocessing_manifests: dict[str, Mapping[str, Any]] = {}
    contract = frozen_formal_preprocessing_contract()
    with zipfile.ZipFile(inventory.zip_path, "r") as archive:
        for member in inventory.members:
            payload = archive.read(member.archive_path)
            if _sha256_bytes(payload) != member.sha256:
                raise Sup1InputError(f"ZIP member changed after inventory: {member.filename}")
            parsed = _parse_rew_member(payload, member.archive_path)
            header, failures = _header_contract(parsed)
            all_headers = parsed.headers["all"]
            format_ok = bool(re.search(
                r"Format:\s*256k Log Swept Sine,\s*1 sweep at -30\.0 dBFS with no timing reference",
                all_headers, re.I,
            ))
            measurement_match = re.search(
                r"Measurement:\s*R C03_U4ENC_(?P<module>[A-H])_?(?P<repeat>0[1-4])\b",
                all_headers, re.I,
            )
            measurement_identity_ok = bool(
                measurement_match
                and measurement_match.group("module").upper() == member.module_id
                and measurement_match.group("repeat") == member.repeat_id
            )
            note = parsed.headers.get("note", "")
            note_ok = all(re.search(pattern, note, re.I) for pattern in (
                r"1 acoustic channels open", r"Windows out=50", r"mic input=100",
                r"distance=0\.8 m",
            ))
            source_ok = "iMM-6C" in parsed.headers.get("source", "")
            differences = np.diff(parsed.frequency_hz)
            inferred_sample_rate = float(np.median(differences) * 131072.0)
            inferred_48k = abs(inferred_sample_rate - 48000.0) <= 2.0
            if not format_ok:
                failures.append("rew_format_contract_mismatch")
            if not measurement_identity_ok:
                failures.append("measurement_header_identity_mismatch")
            if not note_ok:
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
            reasons = sorted(set(failures if failures else warnings))
            meta = _meta(member, inventory, reasons)
            spectrum = SpectrumData(
                frequency_hz=parsed.frequency_hz,
                magnitude_db=parsed.magnitude_db,
                valid_mask=np.ones(parsed.frequency_hz.size, dtype=bool),
                representation=Representation.DENSE_SPECTRUM,
                phase_status=PhaseStatus.UNAVAILABLE,
                quality_metrics={
                    "sup1_qc_reasons": reasons,
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
                raise Sup1InputError(
                    f"FORMAL-1 valid-mask contract mismatch: {member.sample_id}"
                )
            feature = FeatureSet(
                sample_id=member.sample_id,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                feature_kind=FeatureKind.DENSE_RAW_SPL,
                feature_names=tuple(f"spl_{value:.9f}_hz" for value in result.frequency_hz),
                values=result.magnitude_db,
                valid_mask=result.valid_mask,
                units=tuple("dB SPL" for _ in result.frequency_hz),
                source_measurement_mode=MeasurementMode.REW_SWEEP,
                source_representation=Representation.DENSE_SPECTRUM,
                preprocessing_id=_preprocessing_id(),
                meta=meta,
                normalization_method="none",
                source_magnitude_quantity="spl",
                source_magnitude_reference="REW frequency-response export",
                source_phase_status=PhaseStatus.UNAVAILABLE,
                source_qc_status=meta.qc_status,
                source_qc_warning_reasons=tuple(warnings if not failures else ()),
                source_qc_exclude_candidate_reasons=tuple(failures),
                source_qc_unavailable_checks=(
                    "calibration_file_header", "t0_at_ir_peak_header", "digital_clipping"
                ),
                source_qc_eligible_for_downstream=not failures,
            )
            features[member.sample_id] = feature
            preprocessing_manifests[member.sample_id] = result.manifest
            qc_rows.append({
                "sample_id": member.sample_id,
                "filename": member.filename,
                "module_id": f"ENC-{member.module_id}",
                "repeat_id": member.repeat_id,
                "file_sha256": member.sha256,
                "size_bytes": member.size_bytes,
                "qc_status": "fail" if failures else "warning",
                "structural_valid": not failures,
                "reason_codes": reasons,
                "raw_point_count": int(parsed.frequency_hz.size),
                "frequency_min_hz": float(parsed.frequency_hz[0]),
                "frequency_max_hz": float(parsed.frequency_hz[-1]),
                "rew_version": header["rew_version"] or "unavailable",
                "format_256k_1rep_minus30_no_timing": format_ok,
                "raw_smoothing": header["raw_smoothing"] or "unavailable",
                "measurement_identity_matches_filename": measurement_identity_ok,
                "fixed_note_settings_match": note_ok,
                "source_mentions_iMM6C": source_ok,
                "inferred_sample_rate_hz": inferred_sample_rate,
                "inferred_sample_rate_is_48khz": inferred_48k,
                "calibration_file_in_header": header["calibration_file"] or "unavailable",
                "calibration_external_declaration": "CMM29939.txt",
                "t0_setting_in_header": "unavailable",
                "t0_external_declaration": "IR peak",
                "clipping_check": "unavailable_from_frequency_response_txt",
                "final_test_read": False,
            })
    if any(not row["structural_valid"] for row in qc_rows):
        failures = [row["sample_id"] for row in qc_rows if not row["structural_valid"]]
        raise Sup1InputError(f"SUP-1 structural QC failed: {failures}")
    return features, qc_rows, preprocessing_manifests


def _frequency(feature: FeatureSet) -> NDArray[np.float64]:
    return np.asarray(
        [float(name.removeprefix("spl_").removesuffix("_hz")) for name in feature.feature_names],
        dtype=np.float64,
    )


def _rms(left: NDArray[np.float64], right: NDArray[np.float64]) -> float:
    return float(np.sqrt(np.mean(np.square(left - right))))


def choose_primary_triplet(
    sample_ids: Sequence[str],
    curves: Mapping[str, NDArray[np.float64]],
) -> tuple[tuple[str, ...], str | None, float]:
    """Choose a deterministic three-repeat primary set without deleting the fourth."""
    ordered = tuple(sorted(sample_ids))
    if any(not np.all(np.isfinite(curves[sample_id])) for sample_id in ordered):
        raise Sup1InputError("triplet selection curves must contain only valid finite bins")
    if len(ordered) == 3:
        pairs = [_rms(curves[a], curves[b]) for a, b in itertools.combinations(ordered, 2)]
        return ordered, None, float(np.median(pairs))
    if len(ordered) != 4:
        raise Sup1InputError("triplet selection requires three or four repeats")
    candidates: list[tuple[float, float, tuple[str, ...], str]] = []
    for selected in itertools.combinations(ordered, 3):
        pairs = [_rms(curves[a], curves[b]) for a, b in itertools.combinations(selected, 2)]
        omitted = next(sample for sample in ordered if sample not in selected)
        candidates.append((float(np.max(pairs)), float(np.median(pairs)), selected, omitted))
    _, median_score, selected, omitted = min(
        candidates, key=lambda item: (item[0], item[1], item[3])
    )
    return tuple(selected), omitted, median_score


def classify_candidate_window(
    representative_effect_db: float,
    cross_repeat_effects_db: Sequence[float],
    floor_db: float,
) -> str:
    """Frozen descriptive rule for stable versus repeat-sensitive module separation."""
    count = sum(float(value) > floor_db for value in cross_repeat_effects_db)
    if representative_effect_db > floor_db and count >= SUP1_CROSS_REPEAT_STABLE_MINIMUM:
        return "stable"
    if representative_effect_db > floor_db or count > 0:
        return "isolated_or_repeat_sensitive"
    return "below_floor"


def _select_and_flag(
    inventory: Sup1Inventory,
    features: Mapping[str, FeatureSet],
) -> tuple[dict[str, tuple[str, ...]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    frequency = _frequency(next(iter(features.values())))
    primary = (frequency >= 200.0) & (frequency <= 4000.0)
    selected_by_module: dict[str, tuple[str, ...]] = {}
    module_rows: list[dict[str, Any]] = []
    sample_state: dict[str, dict[str, Any]] = {}
    reference_feature = next(iter(features.values()))
    for module in _MODULES:
        members = [member for member in inventory.members if member.module_id == module]
        ids = [member.sample_id for member in members]
        valid_primary = primary & reference_feature.valid_mask
        curves = {sample_id: features[sample_id].values[valid_primary] for sample_id in ids}
        selected, extra, selected_score = choose_primary_triplet(ids, curves)
        selected_by_module[module] = selected
        matrix = np.vstack([curves[sample_id] for sample_id in ids])
        group_median = np.median(matrix, axis=0)
        distances = np.sqrt(np.mean(np.square(matrix - group_median), axis=1))
        center = float(np.median(distances))
        mad = float(np.median(np.abs(distances - center)))
        threshold = center + 3.0 * 1.4826 * mad
        flags = distances > threshold + 1.0e-12
        all_pair_values = [
            _rms(curves[a], curves[b]) for a, b in itertools.combinations(ids, 2)
        ]
        selected_pair_values = [
            _rms(curves[a], curves[b]) for a, b in itertools.combinations(selected, 2)
        ]
        for sample_id, distance, flag in zip(ids, distances, flags, strict=True):
            sample_state[sample_id] = {
                "primary_analysis_included": sample_id in selected,
                "analysis_role": (
                    "PRIMARY_SELECTED_REPEAT" if sample_id in selected
                    else "EXTRA_REPEAT_SENSITIVITY"
                ),
                "selection_reason": (
                    "all_three_planned_repeats" if len(ids) == 3
                    else "minimum_maximum_pairwise_primary_RMS_triplet_then_median"
                ),
                "curve_outlier_flag": bool(flag),
                "curve_distance_to_module_median_db": float(distance),
                "curve_outlier_threshold_db": threshold,
                "automatic_exclusion": False,
                "excluded": False,
            }
        module_rows.append({
            "module_id": f"ENC-{module}",
            "available_repeat_count": len(ids),
            "available_sample_ids": ids,
            "primary_repeat_count": 3,
            "primary_sample_ids": selected,
            "extra_repeat_sample_id": extra or "",
            "triplet_selection_method": (
                "all_three_planned_repeats" if len(ids) == 3
                else "minimum_maximum_pairwise_primary_RMS_triplet_then_median"
            ),
            "selected_triplet_median_pairwise_primary_rms_db": selected_score,
            "selected_triplet_max_pairwise_primary_rms_db": float(np.max(selected_pair_values)),
            "all_available_median_pairwise_primary_rms_db": float(np.median(all_pair_values)),
            "all_available_max_pairwise_primary_rms_db": float(np.max(all_pair_values)),
            "selected_median_to_FORMAL_CONT_p95_ratio": selected_score / SUP1_PRIMARY_FLOOR_P95_DB,
            "outlier_sample_ids": [
                sample_id for sample_id, flag in zip(ids, flags, strict=True) if flag
            ],
            "extra_repeat_is_outlier_flag": bool(
                extra and sample_state[extra]["curve_outlier_flag"]
            ),
            "extra_repeat_deleted_or_excluded": False,
        })
    return selected_by_module, module_rows, sample_state


def _load_sup0_windows(sup0_directory: Path) -> tuple[list[dict[str, Any]], dict[str, float]]:
    verification = verify_sup0_output_hashes(sup0_directory)
    with (sup0_directory / "candidate_bands.csv").open(encoding="utf-8", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    if len(candidates) != 12 or any(row["freeze_for_SUP1_to_SUP4"] != "true" for row in candidates):
        raise Sup1InputError("SUP-0 frozen candidate inventory mismatch")
    floors = {
        row["window_id"]: float(row["primary_cont_p95_rms_db"])
        for row in candidates
    }
    for row in candidates:
        row["sup0_artifact_manifest_sha256"] = verification["artifact_manifest_sha256"]
    return candidates, floors


def _analyse(
    inventory: Sup1Inventory,
    features: Mapping[str, FeatureSet],
    selected_by_module: Mapping[str, Sequence[str]],
    module_rows: list[dict[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    window_floors: Mapping[str, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    frequency = _frequency(next(iter(features.values())))
    parent_masks = {
        "primary": features[next(iter(features))].valid_mask & (frequency >= 200.0) & (frequency <= 4000.0),
        "secondary": features[next(iter(features))].valid_mask & (frequency >= 4000.0) & (frequency <= 8000.0),
    }
    selected_curves: dict[str, list[NDArray[np.float64]]] = {
        module: [features[sample_id].values for sample_id in selected_by_module[module]]
        for module in _MODULES
    }
    representatives = {
        module: np.median(np.vstack(selected_curves[module]), axis=0) for module in _MODULES
    }
    repeat_by_module: dict[str, dict[str, float]] = {}
    for module in _MODULES:
        values: dict[str, float] = {}
        for band, mask in parent_masks.items():
            pairwise = [
                _rms(left[mask], right[mask])
                for left, right in itertools.combinations(selected_curves[module], 2)
            ]
            values[f"{band}_median"] = float(np.median(pairwise))
            values[f"{band}_max"] = float(np.max(pairwise))
        repeat_by_module[module] = values
    for row in module_rows:
        module = str(row["module_id"])[-1]
        values = repeat_by_module[module]
        row.update({
            "primary_median_pairwise_rms_db": values["primary_median"],
            "primary_max_pairwise_rms_db": values["primary_max"],
            "primary_median_to_floor_ratio": values["primary_median"] / SUP1_PRIMARY_FLOOR_P95_DB,
            "secondary_median_pairwise_rms_db": values["secondary_median"],
            "secondary_max_pairwise_rms_db": values["secondary_max"],
            "secondary_median_to_floor_ratio": values["secondary_median"] / SUP1_SECONDARY_FLOOR_P95_DB,
            "repeatability_status": (
                "within_FORMAL_CONT_p95"
                if values["primary_max"] <= SUP1_PRIMARY_FLOOR_P95_DB
                else "some_pair_above_FORMAL_CONT_p95"
            ),
        })

    parent_pair_rows: list[dict[str, Any]] = []
    window_pair_rows: list[dict[str, Any]] = []
    for module_a, module_b in itertools.combinations(_MODULES, 2):
        for band, mask in parent_masks.items():
            floor = SUP1_PRIMARY_FLOOR_P95_DB if band == "primary" else SUP1_SECONDARY_FLOOR_P95_DB
            rep_a = representatives[module_a][mask]
            rep_b = representatives[module_b][mask]
            raw = _rms(rep_a, rep_b)
            demeaned = _rms(rep_a - np.mean(rep_a), rep_b - np.mean(rep_b))
            cross = [
                _rms(left[mask] - np.mean(left[mask]), right[mask] - np.mean(right[mask]))
                for left in selected_curves[module_a] for right in selected_curves[module_b]
            ]
            parent_pair_rows.append({
                "module_a": f"ENC-{module_a}",
                "module_b": f"ENC-{module_b}",
                "parent_band": band,
                "representative_raw_rms_db": raw,
                "representative_demeaned_rms_db": demeaned,
                "cont_p95_floor_db": floor,
                "demeaned_effect_to_floor_ratio": demeaned / floor,
                "cross_repeat_pair_count": 9,
                "cross_repeat_pairs_above_floor": sum(value > floor for value in cross),
                "stable_above_floor": demeaned > floor and sum(value > floor for value in cross) >= 7,
            })

        for candidate in candidates:
            band = str(candidate["parent_band"])
            parent_mask = parent_masks[band]
            indices = np.flatnonzero(
                features[next(iter(features))].valid_mask
                & (frequency >= float(candidate["frequency_low_hz"]))
                & (frequency <= float(candidate["frequency_high_hz"]))
            )
            floor = float(window_floors[str(candidate["window_id"])])
            rep_a_parent = representatives[module_a] - np.mean(representatives[module_a][parent_mask])
            rep_b_parent = representatives[module_b] - np.mean(representatives[module_b][parent_mask])
            representative_effect = _rms(rep_a_parent[indices], rep_b_parent[indices])
            cross: list[float] = []
            for left in selected_curves[module_a]:
                left_parent = left - np.mean(left[parent_mask])
                for right in selected_curves[module_b]:
                    right_parent = right - np.mean(right[parent_mask])
                    cross.append(_rms(left_parent[indices], right_parent[indices]))
            global_floor = (
                SUP1_PRIMARY_FLOOR_P95_DB if band == "primary" else SUP1_SECONDARY_FLOOR_P95_DB
            )
            status = classify_candidate_window(representative_effect, cross, floor)
            window_pair_rows.append({
                "candidate_id": candidate["candidate_id"],
                "window_id": candidate["window_id"],
                "parent_band": band,
                "frequency_low_hz": candidate["frequency_low_hz"],
                "frequency_high_hz": candidate["frequency_high_hz"],
                "module_a": f"ENC-{module_a}",
                "module_b": f"ENC-{module_b}",
                "representative_demeaned_rms_db": representative_effect,
                "sup0_same_window_cont_p95_db": floor,
                "same_window_effect_to_floor_ratio": representative_effect / floor,
                "parent_band_cont_p95_db": global_floor,
                "parent_band_effect_to_floor_ratio": representative_effect / global_floor,
                "cross_repeat_pair_count": 9,
                "cross_repeat_pairs_above_same_window_floor": sum(value > floor for value in cross),
                "cross_repeat_median_rms_db": float(np.median(cross)),
                "cross_repeat_minimum_rms_db": float(np.min(cross)),
                "cross_repeat_maximum_rms_db": float(np.max(cross)),
                "window_separation_status": status,
                "stable_rule": "representative_gt_floor_and_at_least_7_of_9_cross_repeat_pairs_gt_floor",
            })

    window_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        rows = [row for row in window_pair_rows if row["window_id"] == candidate["window_id"]]
        statuses = Counter(str(row["window_separation_status"]) for row in rows)
        ratios = np.asarray([float(row["same_window_effect_to_floor_ratio"]) for row in rows])
        window_rows.append({
            "candidate_id": candidate["candidate_id"],
            "window_id": candidate["window_id"],
            "parent_band": candidate["parent_band"],
            "frequency_low_hz": candidate["frequency_low_hz"],
            "frequency_high_hz": candidate["frequency_high_hz"],
            "module_pair_count": len(rows),
            "stable_pair_count": statuses["stable"],
            "isolated_or_repeat_sensitive_pair_count": statuses["isolated_or_repeat_sensitive"],
            "below_floor_pair_count": statuses["below_floor"],
            "median_same_window_effect_to_floor_ratio": float(np.median(ratios)),
            "minimum_same_window_effect_to_floor_ratio": float(np.min(ratios)),
            "maximum_same_window_effect_to_floor_ratio": float(np.max(ratios)),
            "window_level_interpretation": (
                "broad_module_separation" if statuses["stable"] >= 21
                else "partial_module_separation" if statuses["stable"] > 0
                else "no_stable_module_separation"
            ),
        })
    return parent_pair_rows, window_pair_rows, window_rows


def _csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple)):
        return ";".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fields})


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_plots(
    output: Path,
    features: Mapping[str, FeatureSet],
    selected_by_module: Mapping[str, Sequence[str]],
    module_rows: Sequence[Mapping[str, Any]],
    parent_pair_rows: Sequence[Mapping[str, Any]],
    window_rows: Sequence[Mapping[str, Any]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    plot_dir = output / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    frequency = _frequency(next(iter(features.values())))
    valid = next(iter(features.values())).valid_mask
    representatives = {
        module: np.median(
            np.vstack([features[sample_id].values for sample_id in selected_by_module[module]]),
            axis=0,
        )
        for module in _MODULES
    }
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    for module in _MODULES:
        axes[0].plot(frequency[valid], representatives[module][valid], label=f"ENC-{module}")
        primary = valid & (frequency >= 200) & (frequency <= 4000)
        demeaned = representatives[module] - np.mean(representatives[module][primary])
        axes[1].plot(frequency[valid], demeaned[valid], label=f"ENC-{module}")
    axes[0].set_ylabel("Smoothed level (dB)")
    axes[0].set_title("SUP-1 single-position module representative spectra")
    axes[1].set_ylabel("Parent-primary-demeaned level (dB)")
    axes[1].set_xlabel("Frequency (Hz)")
    for axis in axes:
        axis.set_xscale("log")
        axis.axvline(4000, color="black", linestyle=":", linewidth=1)
        axis.grid(alpha=0.2)
    axes[0].legend(ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / "module_spectra.png", dpi=200)
    plt.close(fig)

    matrix = np.zeros((8, 8), dtype=float)
    for row in parent_pair_rows:
        if row["parent_band"] != "primary":
            continue
        a = _MODULES.index(str(row["module_a"])[-1])
        b = _MODULES.index(str(row["module_b"])[-1])
        matrix[a, b] = matrix[b, a] = float(row["demeaned_effect_to_floor_ratio"])
    fig, axis = plt.subplots(figsize=(7.5, 6.5))
    image = axis.imshow(matrix, cmap="viridis", vmin=0)
    axis.set_xticks(range(8), [f"ENC-{m}" for m in _MODULES], rotation=45, ha="right")
    axis.set_yticks(range(8), [f"ENC-{m}" for m in _MODULES])
    axis.set_title("Primary-band module difference / FORMAL CONT p95")
    for i in range(8):
        for j in range(8):
            if i != j:
                axis.text(j, i, f"{matrix[i,j]:.2f}", ha="center", va="center",
                          color="white" if matrix[i,j] > np.max(matrix) * 0.55 else "black",
                          fontsize=7)
    fig.colorbar(image, ax=axis, label="Effect / 0.8793 dB")
    fig.tight_layout()
    fig.savefig(plot_dir / "module_pair_effect_heatmap.png", dpi=200)
    plt.close(fig)

    labels = [str(row["window_id"]) for row in window_rows]
    stable = [int(row["stable_pair_count"]) for row in window_rows]
    sensitive = [int(row["isolated_or_repeat_sensitive_pair_count"]) for row in window_rows]
    fig, axis = plt.subplots(figsize=(11, 5.5))
    x = np.arange(len(labels))
    axis.bar(x, stable, label="stable", color="#2a9d8f")
    axis.bar(x, sensitive, bottom=stable, label="isolated/repeat-sensitive", color="#e9c46a")
    axis.axhline(28, color="black", linestyle=":", linewidth=1)
    axis.set_xticks(x, labels)
    axis.set_ylabel("Module pairs (of 28)")
    axis.set_title("SUP-0 candidate-window module separation")
    axis.legend()
    axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(plot_dir / "candidate_window_separation.png", dpi=200)
    plt.close(fig)

    labels = [str(row["module_id"]) for row in module_rows]
    medians = [float(row["primary_median_pairwise_rms_db"]) for row in module_rows]
    maxima = [float(row["primary_max_pairwise_rms_db"]) for row in module_rows]
    fig, axis = plt.subplots(figsize=(9, 5.2))
    x = np.arange(len(labels))
    axis.bar(x - 0.18, medians, width=0.36, label="median pair RMS")
    axis.bar(x + 0.18, maxima, width=0.36, label="maximum pair RMS")
    axis.axhline(SUP1_PRIMARY_FLOOR_P95_DB, color="black", linestyle="--", label="0.8793 dB")
    axis.set_xticks(x, labels)
    axis.set_ylabel("Primary-band within-module RMS (dB)")
    axis.set_title("Selected three-repeat module repeatability")
    axis.legend()
    axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(plot_dir / "module_repeatability.png", dpi=200)
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
        "schema_version": "sup1_artifact_manifest_v1",
        "algorithm": "SHA-256",
        "artifacts": artifacts,
    })
    sums = [*artifacts, {
        "path": "artifact_manifest.json",
        "sha256": artifact_sha256(output / "artifact_manifest.json"),
        "bytes": (output / "artifact_manifest.json").stat().st_size,
    }]
    (output / "SHA256SUMS").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in sums), encoding="utf-8"
    )
    return len(artifacts)


def verify_sup1_output_hashes(output_directory: str | Path) -> dict[str, Any]:
    root = Path(output_directory).resolve()
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise Sup1InputError("SUP-1 artifact manifest is empty")
    sums: dict[str, str] = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator:
            raise Sup1InputError("invalid SUP-1 SHA256SUMS line")
        sums[relative] = digest
    for entry in artifacts:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise Sup1InputError("SUP-1 artifact path escapes output") from exc
        if not path.is_file() or artifact_sha256(path) != entry["sha256"]:
            raise Sup1InputError(f"SUP-1 artifact hash mismatch: {relative}")
        if sums.get(relative) != entry["sha256"]:
            raise Sup1InputError(f"SUP-1 SHA256SUMS mismatch: {relative}")
    manifest_sha = artifact_sha256(root / "artifact_manifest.json")
    if sums.get("artifact_manifest.json") != manifest_sha:
        raise Sup1InputError("SUP-1 manifest is not bound by SHA256SUMS")
    return {"all_match": True, "artifact_count": len(artifacts),
            "artifact_manifest_sha256": manifest_sha}


def run_sup1_module_scan(
    zip_path: str | Path,
    raw_directory: str | Path,
    sup0_directory: str | Path,
    output_directory: str | Path,
    *,
    source_commit: str,
    source_worktree_clean: bool,
    created_at: str | datetime,
    expected_zip_sha256: str = SUP1_ZIP_SHA256,
) -> Sup1RunResult:
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise Sup1InputError("source_commit must be a full lowercase Git SHA")
    timestamp = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)
    try:
        parsed_time = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise Sup1InputError("created_at must be ISO-8601") from exc
    if parsed_time.tzinfo is None:
        raise Sup1InputError("created_at must include timezone")
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing SUP-1 output: {output}")
    inventory = inspect_sup1_archive(
        zip_path, expected_zip_sha256=expected_zip_sha256,
        extracted_raw_directory=raw_directory,
    )
    candidates, window_floors = _load_sup0_windows(Path(sup0_directory).resolve())
    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        raise FileExistsError(f"refusing to overwrite SUP-1 staging output: {staging}")
    staging.mkdir(parents=True)
    try:
        features, qc_rows, preprocessing_manifests = _qc_and_preprocess(inventory)
        selected_by_module, module_rows, sample_state = _select_and_flag(inventory, features)
        for row in qc_rows:
            row.update(sample_state[row["sample_id"]])
        parent_pair_rows, window_pair_rows, window_rows = _analyse(
            inventory, features, selected_by_module, module_rows, candidates, window_floors
        )
        inventory_rows = [{
            "sample_id": member.sample_id,
            "filename": member.filename,
            "module_id": f"ENC-{member.module_id}",
            "repeat_id": member.repeat_id,
            "file_sha256": member.sha256,
            "size_bytes": member.size_bytes,
            "data_origin": "real_experiment",
            "dataset_role": "supplemental_research_analysis",
            "experiment_step": "SUP-1",
            "source_zip_sha256": inventory.zip_sha256,
        } for member in inventory.members]
        _write_csv(staging / "data_inventory.csv", inventory_rows, tuple(inventory_rows[0]))
        _write_csv(staging / "file_qc.csv", qc_rows, tuple(qc_rows[0]))
        _write_csv(staging / "module_repeatability.csv", module_rows, tuple(module_rows[0]))
        _write_csv(staging / "module_pair_parent_band_effects.csv", parent_pair_rows,
                   tuple(parent_pair_rows[0]))
        _write_csv(staging / "module_pair_candidate_window_effects.csv", window_pair_rows,
                   tuple(window_pair_rows[0]))
        _write_csv(staging / "candidate_window_summary.csv", window_rows, tuple(window_rows[0]))

        feature_rows: list[dict[str, Any]] = []
        for member in inventory.members:
            feature = features[member.sample_id]
            base = staging / "preprocessed" / "features" / member.sample_id
            npz_path, json_path = save_feature_set(feature, base)
            manifest_path = staging / "preprocessed" / "manifests" / f"{member.sample_id}.json"
            _write_json(manifest_path, dict(preprocessing_manifests[member.sample_id]))
            feature_rows.append({
                "sample_id": member.sample_id,
                "module_id": f"ENC-{member.module_id}",
                "repeat_id": member.repeat_id,
                "grid_point_count": len(feature.values),
                "valid_point_count": int(np.count_nonzero(feature.valid_mask)),
                "preprocessing_id": feature.preprocessing_id,
                "feature_npz": npz_path.relative_to(staging).as_posix(),
                "feature_json": json_path.relative_to(staging).as_posix(),
                "preprocessing_manifest": manifest_path.relative_to(staging).as_posix(),
                "feature_npz_sha256": artifact_sha256(npz_path),
                "feature_json_sha256": artifact_sha256(json_path),
                "preprocessing_manifest_sha256": artifact_sha256(manifest_path),
            })
        _write_csv(staging / "feature_index.csv", feature_rows, tuple(feature_rows[0]))
        flagged = [row for row in qc_rows if row["curve_outlier_flag"]]
        extra = [row for row in qc_rows if row["analysis_role"] == "EXTRA_REPEAT_SENSITIVITY"]
        primary_pairs = [row for row in parent_pair_rows if row["parent_band"] == "primary"]
        secondary_pairs = [row for row in parent_pair_rows if row["parent_band"] == "secondary"]
        broad_windows = [row for row in window_rows if row["window_level_interpretation"] == "broad_module_separation"]
        summary = {
            "schema_version": SUP1_SCHEMA_VERSION,
            "created_at": timestamp,
            "status": "SUP-1_complete",
            "inventory": {
                "measurement_count": 29,
                "module_counts": inventory.module_counts,
                "source_zip_sha256": inventory.zip_sha256,
                "raw_copies_hash_verified": True,
            },
            "qc": {
                "structural_fail_count": 0,
                "warning_count": len(qc_rows),
                "warning_reason": (
                    "calibration filename, t0-at-IR-peak and clipping are unavailable from TXT; "
                    "fixed settings are externally declared"
                ),
                "curve_outlier_flag_count": len(flagged),
                "curve_outlier_sample_ids": [row["sample_id"] for row in flagged],
                "automatic_exclusion": False,
                "remeasurement_recommended_sample_ids": [],
            },
            "repeat_selection": {
                "primary_measurement_count": 24,
                "extra_repeat_count": 5,
                "extra_repeats": [row["sample_id"] for row in extra],
                "method": "minimum maximum pairwise primary-band RMS triplet, then median",
                "extra_repeats_deleted_or_excluded": False,
            },
            "preprocessing": {
                **frozen_formal_preprocessing_contract(),
                "preprocessing_algorithm_version": FORMAL_PREPROCESSING_ALGORITHM_VERSION,
                "preprocessing_id": _preprocessing_id(),
                "candidate_window_count": len(candidates),
                "candidate_windows_from_SUP0_unchanged": True,
            },
            "parent_band_results": {
                "primary": {
                    "module_pair_count": 28,
                    "stable_pair_count": sum(bool(row["stable_above_floor"]) for row in primary_pairs),
                    "median_effect_to_floor_ratio": float(np.median([
                        float(row["demeaned_effect_to_floor_ratio"]) for row in primary_pairs
                    ])),
                    "minimum_effect_to_floor_ratio": float(np.min([
                        float(row["demeaned_effect_to_floor_ratio"]) for row in primary_pairs
                    ])),
                    "maximum_effect_to_floor_ratio": float(np.max([
                        float(row["demeaned_effect_to_floor_ratio"]) for row in primary_pairs
                    ])),
                    "floor_p95_db": SUP1_PRIMARY_FLOOR_P95_DB,
                },
                "secondary": {
                    "module_pair_count": 28,
                    "stable_pair_count": sum(bool(row["stable_above_floor"]) for row in secondary_pairs),
                    "median_effect_to_floor_ratio": float(np.median([
                        float(row["demeaned_effect_to_floor_ratio"]) for row in secondary_pairs
                    ])),
                    "floor_p95_db": SUP1_SECONDARY_FLOOR_P95_DB,
                    "evidence_role": "secondary",
                },
            },
            "candidate_window_results": {
                "window_count": len(window_rows),
                "broad_module_separation_window_ids": [row["window_id"] for row in broad_windows],
                "per_window": [{
                    "window_id": row["window_id"],
                    "frequency_hz": [float(row["frequency_low_hz"]), float(row["frequency_high_hz"])],
                    "stable_pair_count": int(row["stable_pair_count"]),
                    "isolated_or_repeat_sensitive_pair_count": int(
                        row["isolated_or_repeat_sensitive_pair_count"]
                    ),
                    "interpretation": row["window_level_interpretation"],
                } for row in window_rows],
            },
            "sup2_decision": {
                "worthwhile": bool(
                    sum(bool(row["stable_above_floor"]) for row in primary_pairs) >= 14
                    and len(broad_windows) >= 1
                ),
                "rule": "at least 14/28 stable primary-band module pairs and at least one broad candidate window",
                "scope": "supports HOM/HET acquisition only; does not establish direction labels or classification",
            },
            "claim_boundary": {
                "module_letters_interpreted_as_directions": False,
                "classification_performed": False,
                "SUP2_or_SUP3_performed": False,
                "FORMAL5_disposition_changed": False,
            },
            "provenance": {
                "data_origin": "real_experiment",
                "dataset_role": "supplemental_research_analysis",
                "run_purpose": "SUP-1_single_position_module_scan",
                "scientifically_eligible": False,
            },
            "final_test_read": False,
        }
        _write_json(staging / "analysis_summary.json", summary)
        _write_json(staging / "run_manifest.json", {
            "schema_version": SUP1_SCHEMA_VERSION,
            "created_at": timestamp,
            "source_commit": source_commit,
            "source_worktree_clean": source_worktree_clean,
            "input": {
                "zip_path": str(inventory.zip_path),
                "zip_sha256": inventory.zip_sha256,
                "raw_directory": str(Path(raw_directory).resolve()),
                "raw_copy_hashes_verified": True,
                "sup0_directory": str(Path(sup0_directory).resolve()),
                "sup0_artifact_manifest_sha256": candidates[0]["sup0_artifact_manifest_sha256"],
            },
            "analysis": {
                "primary_repeats_per_module": 3,
                "fourth_repeat_role": "retained_extra_repeat_sensitivity_not_EXCLUDED",
                "primary_floor_p95_db": SUP1_PRIMARY_FLOOR_P95_DB,
                "secondary_floor_p95_db": SUP1_SECONDARY_FLOOR_P95_DB,
                "candidate_window_stable_minimum_cross_pairs": SUP1_CROSS_REPEAT_STABLE_MINIMUM,
                "classification_performed": False,
            },
            "provenance": summary["provenance"],
            "raw_txt_modified": False,
            "final_test_read": False,
        })
        _write_plots(staging, features, selected_by_module, module_rows, parent_pair_rows, window_rows)
        artifact_count = _write_artifact_manifests(staging)
        verification = verify_sup1_output_hashes(staging)
        if verification["artifact_count"] != artifact_count:
            raise Sup1InputError("SUP-1 artifact verification count mismatch")
        staging.rename(output)
        return Sup1RunResult(
            output, 29, 24, 5, len(flagged), len(candidates), artifact_count
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
