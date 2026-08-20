"""FORMAL-4 block-aware analysis of the immutable FORMAL-3 FeatureSet corpus."""

from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import itertools
import json
from pathlib import Path
import shutil
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score

from .direction_models import predict_direction_arrays
from .schemas import FeatureSet, artifact_sha256, load_feature_set
from .version import SCHEMA_VERSION_QUARTET


FORMAL4_SCHEMA_VERSION = "formal4_core_analysis_v1"
FORMAL3_ZIP_SHA256 = (
    "cfbaa7a3c300b8443d934462386e9a5faad74d2b2cf0a50292d8c08423f7b4cb"
)
FORMAL3_ACTIVE_COUNT = 72
FORMAL3_EXCLUDED_COUNT = 19
FORMAL3_VALID_POINT_COUNT = 255
FORMAL4_RANDOM_STATE = 20260820
FORMAL4_BOOTSTRAP_ITERATIONS = 2000
FORMAL4_PERMUTATION_ITERATIONS = 999
_DIRECTIONS = (0, 90, 180, 270)
_BLOCKS: dict[str, tuple[str, str, str, str]] = {
    "B01": ("U4SYM", "AS01", "RP01", "S01"),
    "B02": ("U4SYM", "AS01", "RP02", "S01"),
    "B03": ("U4ENC", "AS01", "RP01", "S02"),
    "B04": ("U4ENC", "AS01", "RP02", "S02"),
    "B05": ("U4ENC", "AS02", "RP01", "S03"),
    "B07": ("U4SYM", "AS02", "RP01", "S04"),
}
_AS01_BLOCKS = {"U4SYM": ("B01", "B02"), "U4ENC": ("B03", "B04")}
_AS02_BLOCKS = {"U4SYM": ("B07",), "U4ENC": ("B05",)}


class Formal4InputError(ValueError):
    """Raised when an input/output authority or frozen analysis invariant fails."""


@dataclass(frozen=True, slots=True)
class Formal3Authority:
    input_directory: Path
    active_count: int
    excluded_count: int
    feature_count: int
    common_valid_point_count: int
    outlier_sample_count: int
    run_manifest_sha256: str
    artifact_manifest_sha256: str
    input_artifact_count: int


@dataclass(frozen=True, slots=True)
class Formal4Sample:
    sample_id: str
    block_id: str
    configuration: str
    assembly_id: str
    reposition_round_id: str
    session_id: str
    direction_deg: int
    repeat_id: str
    values: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]
    frequency_hz: NDArray[np.float64]
    outlier_flag: bool
    feature_npz_sha256: str
    feature_json_sha256: str


@dataclass(frozen=True, slots=True)
class Formal4RunResult:
    output_directory: Path
    active_count: int
    excluded_count: int
    outlier_count: int
    ready_for_formal_synthesis: bool
    artifact_count: int


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Formal4InputError(f"cannot read JSON authority: {path}") from exc
    if not isinstance(payload, dict):
        raise Formal4InputError(f"JSON authority must be an object: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise Formal4InputError(f"cannot read CSV authority: {path}") from exc


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fields})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (tuple, list)):
        return ";".join(str(item) for item in value)
    return value


def _sha256_text(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_member(root: Path, relative: str) -> Path:
    candidate = (root / Path(relative)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise Formal4InputError(f"artifact path escapes authority directory: {relative}") from exc
    return candidate


def _verify_artifact_manifest(root: Path, manifest_name: str) -> tuple[int, str]:
    path = root / manifest_name
    payload = _read_json(path)
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise Formal4InputError(f"artifact manifest is empty: {path}")
    seen: set[str] = set()
    for entry in artifacts:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise Formal4InputError(f"invalid artifact manifest entry: {path}")
        relative = entry["path"]
        if relative in seen:
            raise Formal4InputError(f"duplicate artifact manifest path: {relative}")
        seen.add(relative)
        artifact = _safe_member(root, relative)
        if not artifact.is_file():
            raise Formal4InputError(f"artifact missing: {relative}")
        actual = artifact_sha256(artifact)
        if actual != entry.get("sha256"):
            raise Formal4InputError(
                f"artifact hash mismatch for {relative}: expected {entry.get('sha256')}, found {actual}"
            )
        if "bytes" in entry and int(entry["bytes"]) != artifact.stat().st_size:
            raise Formal4InputError(f"artifact size mismatch for {relative}")
    return len(artifacts), artifact_sha256(path)


def _verify_sha256s(root: Path, required_manifest: str) -> None:
    path = root / "SHA256SUMS"
    if not path.is_file():
        raise Formal4InputError(f"SHA256SUMS missing: {root}")
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, separator, relative = line.partition("  ")
        if not separator or len(digest) != 64 or not relative:
            raise Formal4InputError("invalid SHA256SUMS line")
        entries[relative] = digest
    if required_manifest not in entries:
        raise Formal4InputError(f"SHA256SUMS does not bind {required_manifest}")
    for relative, expected in entries.items():
        artifact = _safe_member(root, relative)
        if not artifact.is_file() or artifact_sha256(artifact) != expected:
            raise Formal4InputError(f"SHA256SUMS hash mismatch for {relative}")


def _frequency_from_names(feature: FeatureSet) -> NDArray[np.float64]:
    values: list[float] = []
    for name in feature.feature_names:
        if not name.startswith("spl_") or not name.endswith("_hz"):
            raise Formal4InputError("FORMAL-4 requires FORMAL-1 spl_<frequency>_hz features")
        try:
            values.append(float(name[4:-3]))
        except ValueError as exc:
            raise Formal4InputError(f"invalid frequency feature name: {name}") from exc
    result = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(result)) or not np.all(np.diff(result) > 0):
        raise Formal4InputError("FORMAL-1 frequency axis must be finite and strictly increasing")
    return result


def _load_samples(root: Path) -> tuple[Formal4Sample, ...]:
    active_rows = _read_csv(root / "active_manifest.csv")
    feature_rows = _read_csv(root / "feature_index.csv")
    qc_rows = _read_csv(root / "file_qc.csv")
    active_by_id = {row["sample_id"]: row for row in active_rows}
    qc_by_id = {row["sample_id"]: row for row in qc_rows}
    if len(active_by_id) != FORMAL3_ACTIVE_COUNT or len(feature_rows) != FORMAL3_ACTIVE_COUNT:
        raise Formal4InputError("FORMAL-4 requires exactly 72 unique ACTIVE FeatureSets")
    feature_ids = {row["sample_id"] for row in feature_rows}
    if feature_ids != set(active_by_id):
        raise Formal4InputError("FeatureSet membership differs from frozen ACTIVE manifest")
    samples: list[Formal4Sample] = []
    reference_frequency: NDArray[np.float64] | None = None
    reference_mask: NDArray[np.bool_] | None = None
    reference_preprocessing: str | None = None
    for row in sorted(feature_rows, key=lambda item: item["sample_id"]):
        sample_id = row["sample_id"]
        active = active_by_id[sample_id]
        if active.get("selection_status") != "ACTIVE" or active.get("analysis_included") != "true":
            raise Formal4InputError(f"frozen ACTIVE membership is not analysis-included: {sample_id}")
        block = active["block_id"]
        if block not in _BLOCKS:
            raise Formal4InputError(f"unexpected FORMAL-4 block: {block}")
        configuration, assembly, repos, session = _BLOCKS[block]
        if active["configuration"] != configuration or active["assembly_id"] != assembly:
            raise Formal4InputError(f"block identity mismatch for {sample_id}")
        direction = int(active["direction_id"])
        if direction not in _DIRECTIONS:
            raise Formal4InputError(f"unexpected direction for {sample_id}")
        base = _safe_member(root, row["feature_npz"]).with_suffix("")
        npz_path = base.with_suffix(".npz")
        json_path = base.with_suffix(".json")
        if artifact_sha256(npz_path) != row["feature_npz_sha256"]:
            raise Formal4InputError(f"feature NPZ hash mismatch: {sample_id}")
        if artifact_sha256(json_path) != row["feature_json_sha256"]:
            raise Formal4InputError(f"feature JSON hash mismatch: {sample_id}")
        feature = load_feature_set(base)
        if feature.sample_id != sample_id or feature.feature_kind.value != "dense_raw_spl":
            raise Formal4InputError(f"FORMAL-4 FeatureSet contract mismatch: {sample_id}")
        if feature.meta.data_origin.value != "real_experiment":
            raise Formal4InputError(f"non-real FeatureSet in FORMAL-4 input: {sample_id}")
        if feature.meta.dataset_role.value != "research_analysis":
            raise Formal4InputError(f"wrong dataset role in FORMAL-4 input: {sample_id}")
        if feature.meta.eligible_for_scientific_analysis:
            raise Formal4InputError("FORMAL-4 input must remain scientifically ineligible pending FORMAL-5")
        if feature.meta.acquisition_block_id != block:
            raise Formal4InputError(f"FeatureSet block identity mismatch: {sample_id}")
        frequency = _frequency_from_names(feature)
        if feature.values.size != 256 or int(np.count_nonzero(feature.valid_mask)) != 255:
            raise Formal4InputError(f"FORMAL-1 FeatureSet must contain 255/256 valid points: {sample_id}")
        if np.flatnonzero(~feature.valid_mask).tolist() != [0]:
            raise Formal4InputError(f"FORMAL-1 invalid boundary contract mismatch: {sample_id}")
        if reference_frequency is None:
            reference_frequency = frequency
            reference_mask = feature.valid_mask
            reference_preprocessing = feature.preprocessing_id
        elif (
            not np.array_equal(frequency, reference_frequency)
            or not np.array_equal(feature.valid_mask, reference_mask)
            or feature.preprocessing_id != reference_preprocessing
        ):
            raise Formal4InputError("FORMAL-1 FeatureSets do not share one grid/mask/preprocessing_id")
        qc = qc_by_id.get(sample_id)
        if qc is None or qc.get("structural_valid") != "true":
            raise Formal4InputError(f"ACTIVE structural QC is not valid: {sample_id}")
        samples.append(Formal4Sample(
            sample_id=sample_id,
            block_id=block,
            configuration=configuration,
            assembly_id=assembly,
            reposition_round_id=repos,
            session_id=session,
            direction_deg=direction,
            repeat_id=active["repeat_id"],
            values=np.asarray(feature.values, dtype=np.float64),
            valid_mask=np.asarray(feature.valid_mask, dtype=np.bool_),
            frequency_hz=frequency,
            outlier_flag=qc.get("curve_outlier_flag") == "true",
            feature_npz_sha256=row["feature_npz_sha256"],
            feature_json_sha256=row["feature_json_sha256"],
        ))
    cell_counts: dict[tuple[str, int], int] = defaultdict(int)
    for sample in samples:
        cell_counts[(sample.block_id, sample.direction_deg)] += 1
    expected_cells = {(block, direction): 3 for block in _BLOCKS for direction in _DIRECTIONS}
    if cell_counts != expected_cells:
        raise Formal4InputError("FORMAL-4 requires three ACTIVE CONT curves per block/direction")
    return tuple(samples)


def verify_formal3_authority(input_directory: str | Path) -> Formal3Authority:
    """Validate the complete FORMAL-3 authority without scanning raw data."""
    root = Path(input_directory).resolve()
    if not root.is_dir():
        raise Formal4InputError(f"FORMAL-3 authority directory does not exist: {root}")
    artifact_count, manifest_sha = _verify_artifact_manifest(root, "artifact_manifest.json")
    _verify_sha256s(root, "artifact_manifest.json")
    manifest = _read_json(root / "run_manifest.json")
    selection = manifest.get("selection", {})
    provenance = manifest.get("provenance", {})
    contract = manifest.get("formal_preprocessing_contract", {})
    if manifest.get("ready_for_formal_analysis") is not True:
        raise Formal4InputError("FORMAL-3 ready_for_formal_analysis is not true")
    if selection.get("active_count") != 72 or selection.get("excluded_count") != 19:
        raise Formal4InputError("FORMAL-3 selection counts are not ACTIVE=72/EXCLUDED=19")
    if selection.get("automatic_selection_change_allowed") is not False:
        raise Formal4InputError("FORMAL-3 selection authority permits automatic change")
    if selection.get("excluded_entered_features_statistics_training_or_results") is not False:
        raise Formal4InputError("FORMAL-3 reports EXCLUDED leakage")
    if manifest.get("input_zip", {}).get("sha256") != FORMAL3_ZIP_SHA256:
        raise Formal4InputError("FORMAL-3 input ZIP SHA-256 differs from frozen REV003")
    if manifest.get("preprocessed_feature_count") != 72:
        raise Formal4InputError("FORMAL-3 preprocessed FeatureSet count is not 72")
    if manifest.get("final_test_read") is not False:
        raise Formal4InputError("FORMAL-3 final-test authority is not sealed")
    if provenance != {
        "data_origin": "real_experiment",
        "dataset_role": "research_analysis",
        "run_purpose": "research_analysis",
        "scientifically_eligible": False,
    }:
        raise Formal4InputError("FORMAL-3 provenance contract mismatch")
    expected_contract = {
        "grid_type": "logarithmic", "points_per_octave": 48,
        "frequency_min_hz": 200.0, "frequency_max_hz": 8000.0,
        "primary_band_hz": [200.0, 4000.0],
        "secondary_band_hz": [4000.0, 8000.0],
        "smoothing_fraction_octave": "1/12",
    }
    if any(contract.get(key) != value for key, value in expected_contract.items()):
        raise Formal4InputError("FORMAL-3 preprocessing contract differs from frozen FORMAL-1")
    active_rows = _read_csv(root / "active_manifest.csv")
    excluded_rows = _read_csv(root / "excluded_manifest.csv")
    if len(active_rows) != 72 or len({row["sample_id"] for row in active_rows}) != 72:
        raise Formal4InputError("active_manifest must contain 72 unique rows")
    if len(excluded_rows) != 19 or len({row["sample_id"] for row in excluded_rows}) != 19:
        raise Formal4InputError("excluded_manifest must contain 19 unique rows")
    if {row["sample_id"] for row in active_rows} & {row["sample_id"] for row in excluded_rows}:
        raise Formal4InputError("ACTIVE and EXCLUDED identities overlap")
    samples = _load_samples(root)
    common = np.logical_and.reduce([sample.valid_mask for sample in samples])
    outlier_count = sum(sample.outlier_flag for sample in samples)
    return Formal3Authority(
        root, 72, 19, len(samples), int(np.count_nonzero(common)), outlier_count,
        artifact_sha256(root / "run_manifest.json"), manifest_sha, artifact_count,
    )


def band_masks(
    frequency_hz: NDArray[np.float64], valid_mask: NDArray[np.bool_]
) -> dict[str, NDArray[np.bool_]]:
    """Return frozen bands on actual valid bins; never extrapolate the 200-Hz edge."""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    valid = np.asarray(valid_mask, dtype=np.bool_)
    if frequency.ndim != 1 or valid.shape != frequency.shape:
        raise Formal4InputError("frequency and valid mask must be aligned 1-D arrays")
    return {
        "primary": valid & (frequency >= 200.0) & (frequency <= 4000.0),
        "secondary": valid & (frequency >= 4000.0) & (frequency <= 8000.0),
        "full": valid & (frequency >= 200.0) & (frequency <= 8000.0),
    }


def _normalize(vector: NDArray[np.float64], method: str) -> NDArray[np.float64]:
    values = np.asarray(vector, dtype=np.float64)
    if method == "raw":
        return values
    centered = values - np.mean(values)
    if method == "demeaned":
        return centered
    if method == "zscore":
        scale = float(np.std(centered))
        return centered / scale if scale > 0 else np.zeros_like(centered)
    raise Formal4InputError(f"unsupported normalization: {method}")


def _rms(left: NDArray[np.float64], right: NDArray[np.float64], method: str) -> float:
    delta = _normalize(left, method) - _normalize(right, method)
    return float(np.sqrt(np.mean(np.square(delta))))


def _cell_samples(
    samples: Sequence[Formal4Sample], *, include_flagged: bool
) -> dict[tuple[str, int], tuple[Formal4Sample, ...]]:
    grouped: dict[tuple[str, int], list[Formal4Sample]] = defaultdict(list)
    for sample in samples:
        if include_flagged or not sample.outlier_flag:
            grouped[(sample.block_id, sample.direction_deg)].append(sample)
    result: dict[tuple[str, int], tuple[Formal4Sample, ...]] = {}
    for key in sorted(grouped):
        ordered = tuple(sorted(grouped[key], key=lambda item: item.sample_id))
        if len(ordered) < 2:
            raise Formal4InputError(f"outlier sensitivity leaves fewer than two curves in cell {key}")
        result[key] = ordered
    if set(result) != {(block, direction) for block in _BLOCKS for direction in _DIRECTIONS}:
        raise Formal4InputError("analysis variant does not retain all frozen block/direction cells")
    return result


def _cell_medians(
    cells: Mapping[tuple[str, int], Sequence[Formal4Sample]]
) -> dict[tuple[str, int], NDArray[np.float64]]:
    return {
        key: np.median(np.vstack([sample.values for sample in group]), axis=0)
        for key, group in cells.items()
    }


def _repeatability(
    cells: Mapping[tuple[str, int], Sequence[Formal4Sample]],
    frequency: NDArray[np.float64],
    masks: Mapping[str, NDArray[np.bool_]],
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, float]],
    list[dict[str, Any]],
]:
    rows: list[dict[str, Any]] = []
    frequency_rows: list[dict[str, Any]] = []
    pair_values: dict[str, list[float]] = defaultdict(list)
    for (block, direction), group in sorted(cells.items()):
        for band, mask in masks.items():
            matrix = np.vstack([sample.values[mask] for sample in group])
            pairs = list(itertools.combinations(range(len(group)), 2))
            pair_rms = [
                float(np.sqrt(np.mean(np.square(matrix[left] - matrix[right]))))
                for left, right in pairs
            ]
            pair_values[band].extend(pair_rms)
            absolute = np.concatenate([
                np.abs(matrix[left] - matrix[right]) for left, right in pairs
            ])
            point_median = np.median(matrix, axis=0)
            point_mad = np.median(np.abs(matrix - point_median), axis=0)
            point_sd = np.std(matrix, axis=0, ddof=1)
            rows.append({
                "block_id": block,
                "configuration": _BLOCKS[block][0],
                "assembly_id": _BLOCKS[block][1],
                "reposition_round_id": _BLOCKS[block][2],
                "direction_deg": direction,
                "band_id": band,
                "frequency_point_count": int(np.count_nonzero(mask)),
                "sample_count": len(group),
                "sample_ids": [sample.sample_id for sample in group],
                "pair_count": len(pairs),
                "pair_ids": [f"{group[left].sample_id}|{group[right].sample_id}" for left, right in pairs],
                "pairwise_rms_db": pair_rms,
                "pairwise_rms_median_db": float(np.median(pair_rms)),
                "median_absolute_difference_db": float(np.median(absolute)),
                "p95_absolute_difference_db": float(np.percentile(absolute, 95)),
                "pointwise_mad_median_db": float(np.median(point_mad)),
                "pointwise_mad_p95_db": float(np.percentile(point_mad, 95)),
                "pointwise_sd_median_db": float(np.median(point_sd)),
                "pointwise_sd_p95_db": float(np.percentile(point_sd, 95)),
            })
        full_matrix = np.vstack([sample.values[masks["full"]] for sample in group])
        full_center = np.median(full_matrix, axis=0)
        full_mad = np.median(np.abs(full_matrix - full_center), axis=0)
        full_sd = np.std(full_matrix, axis=0, ddof=1)
        for frequency_value, mad, sd in zip(
            frequency[masks["full"]], full_mad, full_sd, strict=True
        ):
            frequency_rows.append({
                "block_id": block, "configuration": _BLOCKS[block][0],
                "assembly_id": _BLOCKS[block][1], "direction_deg": direction,
                "frequency_hz": float(frequency_value),
                "frequency_band": "primary" if frequency_value <= 4000.0 else "secondary",
                "sample_count": len(group), "pointwise_mad_db": float(mad),
                "pointwise_sd_db": float(sd),
            })
    summaries: list[dict[str, Any]] = []
    floor: dict[str, dict[str, float]] = {}
    for band in ("primary", "secondary", "full"):
        values = np.asarray(pair_values[band], dtype=np.float64)
        q25, q75 = np.percentile(values, [25, 75])
        summary = {
            "band_id": band,
            "cell_count": len(cells),
            "pair_count": int(values.size),
            "median_pairwise_rms_db": float(np.median(values)),
            "iqr_pairwise_rms_db": float(q75 - q25),
            "p95_pairwise_rms_db": float(np.percentile(values, 95)),
            "minimum_pairwise_rms_db": float(np.min(values)),
            "maximum_pairwise_rms_db": float(np.max(values)),
            "interpretation": "CONT technical-repeat measurement-error floor",
        }
        summaries.append(summary)
        floor[band] = {
            "median_db": summary["median_pairwise_rms_db"],
            "iqr_db": summary["iqr_pairwise_rms_db"],
            "p95_db": summary["p95_pairwise_rms_db"],
        }
    return rows, summaries, floor, frequency_rows


def _direction_effects(
    medians: Mapping[tuple[str, int], NDArray[np.float64]],
    masks: Mapping[str, NDArray[np.bool_]],
    floor: Mapping[str, Mapping[str, float]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in _BLOCKS:
        for left, right in itertools.combinations(_DIRECTIONS, 2):
            for band, mask in masks.items():
                values = {
                    method: _rms(medians[(block, left)][mask], medians[(block, right)][mask], method)
                    for method in ("raw", "demeaned", "zscore")
                }
                threshold = float(floor[band]["p95_db"])
                rows.append({
                    "block_id": block, "configuration": _BLOCKS[block][0],
                    "assembly_id": _BLOCKS[block][1],
                    "reposition_round_id": _BLOCKS[block][2],
                    "direction_a_deg": left, "direction_b_deg": right,
                    "band_id": band,
                    "raw_rms_db": values["raw"],
                    "demeaned_rms_db": values["demeaned"],
                    "zscore_rms": values["zscore"],
                    "cont_repeatability_p95_db": threshold,
                    "effect_to_repeatability_ratio": (
                        values["demeaned"] / threshold if threshold > 0 else None
                    ),
                    "clearly_exceeds_measurement_floor": values["demeaned"] > threshold,
                    "decision_rule": "demeaned_rms_gt_global_CONT_pairwise_rms_p95_same_band",
                })
    return rows


def _direction_effect_summaries(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for block in _BLOCKS:
        for band in ("primary", "secondary", "full"):
            selected = [row for row in rows if row["block_id"] == block and row["band_id"] == band]
            values = {
                "raw": np.asarray([row["raw_rms_db"] for row in selected], dtype=np.float64),
                "demeaned": np.asarray([row["demeaned_rms_db"] for row in selected], dtype=np.float64),
                "zscore": np.asarray([row["zscore_rms"] for row in selected], dtype=np.float64),
            }
            output.append({
                "block_id": block, "configuration": _BLOCKS[block][0],
                "assembly_id": _BLOCKS[block][1], "band_id": band,
                "direction_pair_count": len(selected),
                "raw_minimum_rms_db": float(np.min(values["raw"])),
                "raw_median_rms_db": float(np.median(values["raw"])),
                "raw_maximum_rms_db": float(np.max(values["raw"])),
                "demeaned_minimum_rms_db": float(np.min(values["demeaned"])),
                "demeaned_median_rms_db": float(np.median(values["demeaned"])),
                "demeaned_maximum_rms_db": float(np.max(values["demeaned"])),
                "zscore_minimum_rms": float(np.min(values["zscore"])),
                "zscore_median_rms": float(np.median(values["zscore"])),
                "zscore_maximum_rms": float(np.max(values["zscore"])),
                "clearly_exceeding_floor_pair_count": sum(
                    bool(row["clearly_exceeds_measurement_floor"]) for row in selected
                ),
            })
    return output


def _gain_components(
    medians: Mapping[tuple[str, int], NDArray[np.float64]],
    masks: Mapping[str, NDArray[np.bool_]],
    *,
    configuration: str,
    method: str,
    band: str,
) -> tuple[dict[str, list[float]], list[float]]:
    blocks = _AS01_BLOCKS[configuration]
    mask = masks[band]
    between: dict[str, list[float]] = {}
    for block in blocks:
        between[block] = [
            _rms(medians[(block, left)][mask], medians[(block, right)][mask], method)
            for left, right in itertools.combinations(_DIRECTIONS, 2)
        ]
    repos = [
        _rms(medians[(blocks[0], direction)][mask], medians[(blocks[1], direction)][mask], method)
        for direction in _DIRECTIONS
    ]
    return between, repos


def _gain_bootstrap(
    between: Mapping[str, Sequence[float]], repos: Sequence[float],
    *, rng: np.random.Generator, iterations: int,
) -> tuple[float, float]:
    blocks = tuple(sorted(between))
    values: list[float] = []
    repos_array = np.asarray(repos, dtype=np.float64)
    for _ in range(iterations):
        selected_blocks = rng.choice(blocks, size=len(blocks), replace=True)
        numerator_values = np.concatenate([
            np.asarray(between[str(block)], dtype=np.float64) for block in selected_blocks
        ])
        denominator_values = rng.choice(repos_array, size=repos_array.size, replace=True)
        denominator = float(np.median(denominator_values))
        if denominator > 0:
            values.append(float(np.median(numerator_values)) / denominator)
    if not values:
        return float("nan"), float("nan")
    return tuple(float(value) for value in np.percentile(values, [2.5, 97.5]))


def _gain_rows(
    medians: Mapping[tuple[str, int], NDArray[np.float64]],
    masks: Mapping[str, NDArray[np.bool_]],
    *, random_state: int, bootstrap_iterations: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config_index, configuration in enumerate(("U4SYM", "U4ENC")):
        for band_index, band in enumerate(("primary", "secondary", "full")):
            for method_index, method in enumerate(("raw", "demeaned", "zscore")):
                between, repos = _gain_components(
                    medians, masks, configuration=configuration, method=method, band=band
                )
                numerator = float(np.median(np.concatenate([between[key] for key in sorted(between)])))
                denominator = float(np.median(repos))
                gain = numerator / denominator if denominator > 0 else None
                rng = np.random.default_rng(
                    random_state + config_index * 100 + band_index * 10 + method_index
                )
                ci_low, ci_high = _gain_bootstrap(
                    between, repos, rng=rng, iterations=bootstrap_iterations
                )
                rows.append({
                    "configuration": configuration, "assembly_scope": "AS01",
                    "band_id": band, "normalization": method,
                    "between_direction_pair_count": sum(len(value) for value in between.values()),
                    "reposition_pair_count": len(repos),
                    "between_direction_median_rms": numerator,
                    "within_direction_REPOS_median_rms": denominator,
                    "gain": gain,
                    "bootstrap_ci95_low": ci_low,
                    "bootstrap_ci95_high": ci_high,
                    "bootstrap_iterations": bootstrap_iterations,
                    "bootstrap_method": "block_cluster_and_direction_REPOS_resampling",
                    "status": "estimable_limited_two_REPOS_blocks",
                    "threshold": 1.0 if method == "demeaned" else "",
                })
        for band in ("primary", "secondary", "full"):
            for method in ("raw", "demeaned", "zscore"):
                rows.append({
                    "configuration": configuration, "assembly_scope": "AS02",
                    "band_id": band, "normalization": method,
                    "between_direction_pair_count": 6, "reposition_pair_count": 0,
                    "between_direction_median_rms": "",
                    "within_direction_REPOS_median_rms": "", "gain": "",
                    "bootstrap_ci95_low": "", "bootstrap_ci95_high": "",
                    "bootstrap_iterations": 0,
                    "bootstrap_method": "not_applicable",
                    "status": "not_estimable_single_block_no_REPOS_denominator",
                    "threshold": 1.0 if method == "demeaned" else "",
                })
    return rows


def _gain_contrast_rows(
    medians: Mapping[tuple[str, int], NDArray[np.float64]],
    masks: Mapping[str, NDArray[np.bool_]],
    *, random_state: int, bootstrap_iterations: int,
) -> list[dict[str, Any]]:
    """Bootstrap the preregistered U4ENC minus U4SYM gain contrast."""
    rows: list[dict[str, Any]] = []
    for band_index, band in enumerate(("primary", "secondary", "full")):
        for method_index, method in enumerate(("raw", "demeaned", "zscore")):
            components = {
                configuration: _gain_components(
                    medians, masks, configuration=configuration,
                    method=method, band=band,
                )
                for configuration in ("U4SYM", "U4ENC")
            }
            point: dict[str, float] = {}
            for configuration, (between, repos) in components.items():
                point[configuration] = float(
                    np.median(np.concatenate([between[key] for key in sorted(between)]))
                    / np.median(repos)
                )
            rng = np.random.default_rng(random_state + 5000 + band_index * 10 + method_index)
            bootstrap_delta: list[float] = []
            for _ in range(bootstrap_iterations):
                gains: dict[str, float] = {}
                for configuration, (between, repos) in components.items():
                    blocks = tuple(sorted(between))
                    selected_blocks = rng.choice(blocks, size=len(blocks), replace=True)
                    numerator = float(np.median(np.concatenate([
                        np.asarray(between[str(block)], dtype=np.float64)
                        for block in selected_blocks
                    ])))
                    denominator = float(np.median(rng.choice(
                        np.asarray(repos, dtype=np.float64), size=len(repos), replace=True
                    )))
                    gains[configuration] = numerator / denominator
                bootstrap_delta.append(gains["U4ENC"] - gains["U4SYM"])
            ci_low, ci_high = np.percentile(bootstrap_delta, [2.5, 97.5])
            delta = point["U4ENC"] - point["U4SYM"]
            rows.append({
                "assembly_scope": "AS01", "band_id": band, "normalization": method,
                "u4sym_gain": point["U4SYM"], "u4enc_gain": point["U4ENC"],
                "u4enc_minus_u4sym_gain": delta,
                "bootstrap_ci95_low": float(ci_low),
                "bootstrap_ci95_high": float(ci_high),
                "bootstrap_iterations": bootstrap_iterations,
                "bootstrap_method": "independent_configuration_block_cluster_and_direction_REPOS_resampling",
                "frozen_threshold": 0.0 if method == "demeaned" else "",
                "point_threshold_pass": delta > 0 if method == "demeaned" else "",
                "ci_lower_threshold_pass": float(ci_low) > 0 if method == "demeaned" else "",
                "status": "estimable_limited_two_REPOS_blocks_per_configuration",
            })
    return rows


def _configuration_effects(
    medians: Mapping[tuple[str, int], NDArray[np.float64]],
    frequency: NDArray[np.float64], masks: Mapping[str, NDArray[np.bool_]],
    floor: Mapping[str, Mapping[str, float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    assemblies = {
        "AS01": (_AS01_BLOCKS["U4SYM"], _AS01_BLOCKS["U4ENC"], "confirmatory_limited"),
        "AS02": (_AS02_BLOCKS["U4SYM"], _AS02_BLOCKS["U4ENC"], "exploratory_single_block"),
    }
    for assembly, (sym_blocks, enc_blocks, status) in assemblies.items():
        for direction in _DIRECTIONS:
            sym = np.median(np.vstack([medians[(block, direction)] for block in sym_blocks]), axis=0)
            enc = np.median(np.vstack([medians[(block, direction)] for block in enc_blocks]), axis=0)
            delta = enc - sym
            for index in np.flatnonzero(masks["full"]):
                curve_rows.append({
                    "assembly_id": assembly, "direction_deg": direction,
                    "frequency_hz": float(frequency[index]),
                    "u4sym_median_db": float(sym[index]),
                    "u4enc_median_db": float(enc[index]),
                    "u4enc_minus_u4sym_db": float(delta[index]),
                    "frequency_band": (
                        "primary" if frequency[index] <= 4000.0 else "secondary"
                    ),
                    "status": status,
                })
            for band, mask in masks.items():
                raw = _rms(sym[mask], enc[mask], "raw")
                demeaned = _rms(sym[mask], enc[mask], "demeaned")
                zscore = _rms(sym[mask], enc[mask], "zscore")
                block_pair_raw = [
                    _rms(medians[(sym_block, direction)][mask], medians[(enc_block, direction)][mask], "raw")
                    for sym_block in sym_blocks for enc_block in enc_blocks
                ]
                threshold = float(floor[band]["p95_db"])
                rows.append({
                    "assembly_id": assembly, "direction_deg": direction, "band_id": band,
                    "u4sym_block_ids": sym_blocks, "u4enc_block_ids": enc_blocks,
                    "independent_u4sym_block_count": len(sym_blocks),
                    "independent_u4enc_block_count": len(enc_blocks),
                    "block_pair_count": len(block_pair_raw),
                    "block_pair_raw_rms_median_db": float(np.median(block_pair_raw)),
                    "representative_raw_rms_db": raw,
                    "representative_demeaned_rms_db": demeaned,
                    "representative_zscore_rms": zscore,
                    "median_u4enc_minus_u4sym_db": float(np.median(delta[mask])),
                    "p95_absolute_difference_db": float(np.percentile(np.abs(delta[mask]), 95)),
                    "cont_repeatability_p95_db": threshold,
                    "configuration_to_repeatability_ratio": demeaned / threshold if threshold > 0 else None,
                    "configuration_difference_exceeds_floor": demeaned > threshold,
                    "status": status,
                })
    return rows, curve_rows


def _assembly_effects(
    medians: Mapping[tuple[str, int], NDArray[np.float64]],
    frequency: NDArray[np.float64], masks: Mapping[str, NDArray[np.bool_]],
    floor: Mapping[str, Mapping[str, float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    for configuration in ("U4SYM", "U4ENC"):
        as01_blocks = _AS01_BLOCKS[configuration]
        as02_block = _AS02_BLOCKS[configuration][0]
        for direction in _DIRECTIONS:
            as01 = np.median(np.vstack([medians[(block, direction)] for block in as01_blocks]), axis=0)
            as02 = medians[(as02_block, direction)]
            delta = as02 - as01
            for index in np.flatnonzero(masks["full"]):
                curve_rows.append({
                    "configuration": configuration, "direction_deg": direction,
                    "frequency_hz": float(frequency[index]),
                    "as01_median_db": float(as01[index]), "as02_median_db": float(as02[index]),
                    "as02_minus_as01_db": float(delta[index]),
                    "frequency_band": "primary" if frequency[index] <= 4000 else "secondary",
                    "status": "exploratory_block_time_assembly_confounded",
                })
            for band, mask in masks.items():
                threshold = float(floor[band]["p95_db"])
                demeaned = _rms(as01[mask], as02[mask], "demeaned")
                rows.append({
                    "configuration": configuration, "direction_deg": direction,
                    "band_id": band, "as01_block_ids": as01_blocks,
                    "as02_block_ids": (as02_block,),
                    "raw_rms_db": _rms(as01[mask], as02[mask], "raw"),
                    "demeaned_rms_db": demeaned,
                    "zscore_rms": _rms(as01[mask], as02[mask], "zscore"),
                    "median_as02_minus_as01_db": float(np.median(delta[mask])),
                    "cont_repeatability_p95_db": threshold,
                    "assembly_to_repeatability_ratio": demeaned / threshold if threshold > 0 else None,
                    "difference_exceeds_floor": demeaned > threshold,
                    "status": "exploratory_block_time_assembly_confounded",
                    "causal_interpretation_allowed": False,
                })
    return rows, curve_rows


def _classification_scopes() -> tuple[tuple[str, str, tuple[str, ...], str], ...]:
    return (
        ("U4SYM_AS01", "U4SYM", _AS01_BLOCKS["U4SYM"], "estimable_limited"),
        ("U4ENC_AS01", "U4ENC", _AS01_BLOCKS["U4ENC"], "estimable_limited"),
        ("U4SYM_AS02", "U4SYM", _AS02_BLOCKS["U4SYM"], "not_estimable"),
        ("U4ENC_AS02", "U4ENC", _AS02_BLOCKS["U4ENC"], "not_estimable"),
        ("U4SYM_ALL_ASSEMBLIES", "U4SYM", (*_AS01_BLOCKS["U4SYM"], *_AS02_BLOCKS["U4SYM"]), "exploratory"),
        ("U4ENC_ALL_ASSEMBLIES", "U4ENC", (*_AS01_BLOCKS["U4ENC"], *_AS02_BLOCKS["U4ENC"]), "exploratory"),
    )


def _classification_once(
    medians: Mapping[tuple[str, int], NDArray[np.float64]], mask: NDArray[np.bool_],
    blocks: Sequence[str], *, random_state: int,
    labels_by_block: Mapping[str, Sequence[int]] | None = None,
) -> tuple[list[dict[str, Any]], NDArray[np.int64], NDArray[np.int64]]:
    predictions: list[dict[str, Any]] = []
    all_true: list[int] = []
    all_predicted: list[int] = []
    for fold_index, test_block in enumerate(blocks, start=1):
        train_blocks = tuple(block for block in blocks if block != test_block)
        x_train: list[NDArray[np.float64]] = []
        y_train: list[int] = []
        x_test: list[NDArray[np.float64]] = []
        y_test: list[int] = []
        for block in train_blocks:
            labels = labels_by_block[block] if labels_by_block is not None else _DIRECTIONS
            for direction, label in zip(_DIRECTIONS, labels, strict=True):
                x_train.append(_normalize(medians[(block, direction)][mask], "demeaned"))
                y_train.append(int(label))
        test_labels = labels_by_block[test_block] if labels_by_block is not None else _DIRECTIONS
        for direction, label in zip(_DIRECTIONS, test_labels, strict=True):
            x_test.append(_normalize(medians[(test_block, direction)][mask], "demeaned"))
            y_test.append(int(label))
        outcomes = predict_direction_arrays(
            "nearest_centroid", np.vstack(x_train), np.asarray(y_train, dtype=float),
            np.vstack(x_test), tuple(float(item) for item in _DIRECTIONS), random_state + fold_index,
        )
        for direction, truth, outcome in zip(_DIRECTIONS, y_test, outcomes, strict=True):
            predicted = int(outcome[0])
            all_true.append(truth)
            all_predicted.append(predicted)
            predictions.append({
                "fold_id": f"fold-{fold_index:02d}",
                "test_block_id": test_block, "train_block_ids": train_blocks,
                "physical_direction_deg": direction,
                "true_direction_deg": truth, "predicted_direction_deg": predicted,
                "correct": truth == predicted,
                "continuous_repeat_aggregation": "block_direction_median_curve",
            })
    return predictions, np.asarray(all_true), np.asarray(all_predicted)


def _classification(
    medians: Mapping[tuple[str, int], NDArray[np.float64]],
    primary_mask: NDArray[np.bool_], *, random_state: int, permutation_iterations: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, NDArray[np.int64]]]:
    metrics: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    matrices: dict[str, NDArray[np.int64]] = {}
    for scope_index, (scope, configuration, blocks, status) in enumerate(_classification_scopes()):
        if len(blocks) < 2:
            metrics.append({
                "scope_id": scope, "configuration": configuration,
                "assembly_scope": "AS02", "protocol": "leave_one_block_out",
                "model_id": "nearest_centroid", "status": "not_estimable",
                "reason": "single_block_cannot_support_grouped_validation",
                "group_count": len(blocks), "fold_count": 0, "prediction_count": 0,
                "fold_coverage": 0.0, "balanced_accuracy": "", "macro_f1": "",
                "chance_level": 0.25, "permutation_iterations": 0,
                "permutation_balanced_accuracy_mean": "",
                "permutation_balanced_accuracy_p95": "", "permutation_p_value": "",
                "exploratory": True,
            })
            continue
        observed, truth, predicted = _classification_once(
            medians, primary_mask, blocks, random_state=random_state
        )
        balanced = float(balanced_accuracy_score(truth, predicted))
        macro = float(f1_score(truth, predicted, labels=list(_DIRECTIONS), average="macro", zero_division=0))
        matrix = confusion_matrix(truth, predicted, labels=list(_DIRECTIONS)).astype(np.int64)
        matrices[scope] = matrix
        for row in observed:
            predictions.append({**row, "scope_id": scope, "configuration": configuration})
        rng = np.random.default_rng(random_state + scope_index * 1000)
        permutation_scores: list[float] = []
        for iteration in range(permutation_iterations):
            labels_by_block = {
                block: tuple(int(value) for value in rng.permutation(_DIRECTIONS))
                for block in blocks
            }
            _, perm_truth, perm_predicted = _classification_once(
                medians, primary_mask, blocks, random_state=random_state + iteration + 1,
                labels_by_block=labels_by_block,
            )
            permutation_scores.append(float(balanced_accuracy_score(perm_truth, perm_predicted)))
        perm = np.asarray(permutation_scores, dtype=np.float64)
        p_value = float((1 + np.count_nonzero(perm >= balanced)) / (1 + perm.size))
        metrics.append({
            "scope_id": scope, "configuration": configuration,
            "assembly_scope": "AS01" if scope.endswith("AS01") else "all_assemblies",
            "protocol": "leave_one_block_out", "model_id": "nearest_centroid",
            "status": status, "reason": "limited_independent_blocks" if status == "estimable_limited" else "assembly_time_generalization_exploratory",
            "group_count": len(blocks), "fold_count": len(blocks),
            "prediction_count": int(truth.size), "fold_coverage": 1.0,
            "balanced_accuracy": balanced, "macro_f1": macro,
            "chance_level": 0.25, "permutation_iterations": permutation_iterations,
            "permutation_balanced_accuracy_mean": float(np.mean(perm)),
            "permutation_balanced_accuracy_p95": float(np.percentile(perm, 95)),
            "permutation_p_value": p_value,
            "exploratory": status != "estimable_limited",
        })
    return metrics, predictions, matrices


def _variant_analysis(
    samples: Sequence[Formal4Sample], *, include_flagged: bool,
    random_state: int, bootstrap_iterations: int, permutation_iterations: int,
) -> dict[str, Any]:
    cells = _cell_samples(samples, include_flagged=include_flagged)
    medians = _cell_medians(cells)
    common = np.logical_and.reduce([sample.valid_mask for sample in samples])
    masks = band_masks(samples[0].frequency_hz, common)
    repeat_rows, repeat_summary, floor, repeat_frequency_rows = _repeatability(
        cells, samples[0].frequency_hz, masks
    )
    direction_rows = _direction_effects(medians, masks, floor)
    direction_summary_rows = _direction_effect_summaries(direction_rows)
    gain_rows = _gain_rows(
        medians, masks, random_state=random_state,
        bootstrap_iterations=bootstrap_iterations,
    )
    gain_contrast_rows = _gain_contrast_rows(
        medians, masks, random_state=random_state,
        bootstrap_iterations=bootstrap_iterations,
    )
    configuration_rows, configuration_curves = _configuration_effects(
        medians, samples[0].frequency_hz, masks, floor
    )
    assembly_rows, assembly_curves = _assembly_effects(
        medians, samples[0].frequency_hz, masks, floor
    )
    classification_metrics, classification_predictions, matrices = _classification(
        medians, masks["primary"], random_state=random_state,
        permutation_iterations=permutation_iterations,
    )
    return {
        "cells": cells, "medians": medians, "masks": masks,
        "repeatability_by_cell": repeat_rows, "repeatability_summary": repeat_summary,
        "repeatability_frequency": repeat_frequency_rows,
        "repeatability_floor": floor, "direction": direction_rows,
        "direction_summary": direction_summary_rows, "gains": gain_rows,
        "gain_contrasts": gain_contrast_rows,
        "configuration": configuration_rows, "configuration_curves": configuration_curves,
        "assembly": assembly_rows, "assembly_curves": assembly_curves,
        "classification_metrics": classification_metrics,
        "classification_predictions": classification_predictions,
        "classification_matrices": matrices,
    }


def _metric_map(variant: Mapping[str, Any]) -> dict[tuple[str, str, str], tuple[float, float | None, bool | None]]:
    output: dict[tuple[str, str, str], tuple[float, float | None, bool | None]] = {}
    for row in variant["repeatability_summary"]:
        output[("CONT_floor_median", "all", row["band_id"])] = (
            float(row["median_pairwise_rms_db"]), None, None
        )
    for row in variant["gains"]:
        if row["assembly_scope"] == "AS01" and row["normalization"] in {"raw", "demeaned", "zscore"}:
            value = float(row["gain"])
            threshold = 1.0 if row["normalization"] == "demeaned" else None
            output[(f"G_{row['normalization']}", row["configuration"], row["band_id"])] = (
                value, threshold, value > threshold if threshold is not None else None
            )
    for row in variant["gain_contrasts"]:
        if row["normalization"] == "demeaned":
            value = float(row["u4enc_minus_u4sym_gain"])
            output[("delta_G_demeaned", "U4ENC_minus_U4SYM", row["band_id"])] = (
                value, 0.0, value > 0.0
            )
    for row in variant["classification_metrics"]:
        if row["status"] == "estimable_limited":
            value = float(row["balanced_accuracy"])
            output[("grouped_balanced_accuracy", row["scope_id"], "primary")] = (
                value, 0.5, value >= 0.5
            )
    for configuration in ("U4SYM", "U4ENC"):
        reliable = float(len(_reliable_pairs(variant["direction"], configuration)))
        output[("reliable_direction_pair_count", configuration, "primary")] = (
            reliable, 1.0, reliable >= 1.0
        )
    for assembly in ("AS01", "AS02"):
        selected = [
            row for row in variant["configuration"]
            if row["assembly_id"] == assembly and row["band_id"] == "primary"
        ]
        ratio = float(np.median([
            row["configuration_to_repeatability_ratio"] for row in selected
        ]))
        output[("configuration_effect_to_CONT_floor", assembly, "primary")] = (
            ratio, 1.0, ratio > 1.0
        )
    for configuration in ("U4SYM", "U4ENC"):
        selected = [
            row for row in variant["assembly"]
            if row["configuration"] == configuration and row["band_id"] == "primary"
        ]
        ratio = float(np.median([
            row["assembly_to_repeatability_ratio"] for row in selected
        ]))
        output[("assembly_effect_to_CONT_floor_exploratory", configuration, "primary")] = (
            ratio, 1.0, ratio > 1.0
        )
    return output


def _sensitivity_rows(primary: Mapping[str, Any], sensitivity: Mapping[str, Any], outlier_count: int) -> list[dict[str, Any]]:
    maps = {
        "primary_all_active": _metric_map(primary),
        "sensitivity_without_flagged_curves": _metric_map(sensitivity),
    }
    keys = sorted(set(maps["primary_all_active"]) | set(maps["sensitivity_without_flagged_curves"]))
    rows: list[dict[str, Any]] = []
    for key in keys:
        primary_value = maps["primary_all_active"].get(key)
        sensitivity_value = maps["sensitivity_without_flagged_curves"].get(key)
        changed = (
            primary_value is not None and sensitivity_value is not None
            and primary_value[2] is not None and sensitivity_value[2] is not None
            and primary_value[2] != sensitivity_value[2]
        )
        for variant_name, values in maps.items():
            item = values.get(key)
            rows.append({
                "analysis_variant": variant_name, "metric_id": key[0],
                "scope_id": key[1], "band_id": key[2],
                "value": "" if item is None else item[0],
                "threshold": "" if item is None or item[1] is None else item[1],
                "threshold_conclusion": "" if item is None or item[2] is None else item[2],
                "conclusion_changed_between_variants": changed,
                "flagged_curve_count": outlier_count,
                "flagged_curves_excluded_only_in_sensitivity": variant_name.endswith("without_flagged_curves"),
                "selection_manifest_changed": False,
            })
    return rows


def _reliable_pairs(direction_rows: Sequence[Mapping[str, Any]], configuration: str) -> list[str]:
    required_blocks = set(_AS01_BLOCKS[configuration])
    by_pair: dict[tuple[int, int], set[str]] = defaultdict(set)
    for row in direction_rows:
        if (
            row["configuration"] == configuration and row["band_id"] == "primary"
            and row["clearly_exceeds_measurement_floor"]
            and row["block_id"] in required_blocks
        ):
            by_pair[(int(row["direction_a_deg"]), int(row["direction_b_deg"]))].add(str(row["block_id"]))
    return [f"{left}-{right}" for (left, right), blocks in sorted(by_pair.items()) if blocks == required_blocks]


def _lookup(rows: Sequence[Mapping[str, Any]], **criteria: Any) -> Mapping[str, Any]:
    matches = [row for row in rows if all(row.get(key) == value for key, value in criteria.items())]
    if len(matches) != 1:
        raise Formal4InputError(f"expected one result for {criteria}, found {len(matches)}")
    return matches[0]


def _analysis_summary(
    authority: Formal3Authority, primary: Mapping[str, Any], sensitivity: Mapping[str, Any],
    sensitivity_rows: Sequence[Mapping[str, Any]], *, source_commit: str,
    created_at: str, random_state: int,
) -> dict[str, Any]:
    primary_floor = primary["repeatability_floor"]["primary"]
    enc_gain = _lookup(primary["gains"], configuration="U4ENC", assembly_scope="AS01", band_id="primary", normalization="demeaned")
    sym_gain = _lookup(primary["gains"], configuration="U4SYM", assembly_scope="AS01", band_id="primary", normalization="demeaned")
    enc_class = _lookup(primary["classification_metrics"], scope_id="U4ENC_AS01")
    sym_class = _lookup(primary["classification_metrics"], scope_id="U4SYM_AS01")
    delta_gain_row = _lookup(
        primary["gain_contrasts"], assembly_scope="AS01",
        band_id="primary", normalization="demeaned",
    )
    config_as01 = [row for row in primary["configuration"] if row["assembly_id"] == "AS01" and row["band_id"] == "primary"]
    config_as02 = [row for row in primary["configuration"] if row["assembly_id"] == "AS02" and row["band_id"] == "primary"]
    changed = any(bool(row["conclusion_changed_between_variants"]) for row in sensitivity_rows)
    delta_gain = float(enc_gain["gain"]) - float(sym_gain["gain"])
    return {
        "schema_version": FORMAL4_SCHEMA_VERSION,
        "created_at": created_at,
        "source_commit": source_commit,
        "input_authority": {
            "formal3_directory": str(authority.input_directory),
            "formal3_run_manifest_sha256": authority.run_manifest_sha256,
            "formal3_artifact_manifest_sha256": authority.artifact_manifest_sha256,
            "input_artifacts_verified": authority.input_artifact_count,
            "zip_sha256": FORMAL3_ZIP_SHA256,
        },
        "selection": {
            "active_count": 72, "excluded_count": 19,
            "active_or_excluded_decision_changed": False,
            "excluded_entered_analysis": False,
        },
        "outlier_policy": {
            "flagged_active_count": authority.outlier_sample_count,
            "primary_analysis": "all_72_ACTIVE_with_block_direction_median_of_three_CONT",
            "sensitivity_analysis": "omit_FORMAL3_flags_without_modifying_selection",
            "active_manifest_modified": False,
            "any_frozen_threshold_conclusion_changed": changed,
        },
        "frequency_contract": {
            "common_grid_points": 256, "common_valid_points": 255,
            "primary_band_hz": [200.0, 4000.0],
            "primary_uses_actual_valid_bins_without_200Hz_extrapolation": True,
            "secondary_band_hz": [4000.0, 8000.0], "full_band_hz": [200.0, 8000.0],
        },
        "repeatability_floor": {
            "definition": "all CONT pairwise RMS dB distances; robust distribution, not best repeat",
            "primary_band": primary_floor,
            "all_bands": primary["repeatability_floor"],
        },
        "direction_effect": {
            "reliable_primary_pairs_exceed_CONT_p95_in_both_AS01_REPOS_blocks": {
                configuration: _reliable_pairs(primary["direction"], configuration)
                for configuration in ("U4SYM", "U4ENC")
            },
            "G_demeaned_AS01_primary": {
                "U4SYM": float(sym_gain["gain"]), "U4ENC": float(enc_gain["gain"]),
                "U4SYM_ci95": [sym_gain["bootstrap_ci95_low"], sym_gain["bootstrap_ci95_high"]],
                "U4ENC_ci95": [enc_gain["bootstrap_ci95_low"], enc_gain["bootstrap_ci95_high"]],
                "U4ENC_minus_U4SYM": delta_gain,
                "U4ENC_minus_U4SYM_ci95": [
                    delta_gain_row["bootstrap_ci95_low"],
                    delta_gain_row["bootstrap_ci95_high"],
                ],
                "point_threshold_U4ENC_gt_1": float(enc_gain["gain"]) > 1.0,
                "point_threshold_U4ENC_gt_U4SYM": delta_gain > 0,
                "ci_lower_U4ENC_gt_1": float(enc_gain["bootstrap_ci95_low"]) > 1.0,
                "delta_ci_lower_gt_0": float(delta_gain_row["bootstrap_ci95_low"]) > 0.0,
            },
        },
        "configuration_effect": {
            "AS01_status": "confirmatory_limited_two_blocks_per_configuration",
            "AS01_directions_exceeding_CONT_p95": [int(row["direction_deg"]) for row in config_as01 if row["configuration_difference_exceeds_floor"]],
            "AS01_median_demeaned_to_floor_ratio": float(np.median([row["configuration_to_repeatability_ratio"] for row in config_as01])),
            "AS02_status": "exploratory_single_block_per_configuration",
            "AS02_directions_exceeding_CONT_p95": [int(row["direction_deg"]) for row in config_as02 if row["configuration_difference_exceeds_floor"]],
        },
        "assembly_set_effect": {
            "status": "exploratory_block_time_assembly_confounded",
            "strong_causal_conclusion_allowed": False,
            "reason": "AS02 has one block per configuration and differs in acquisition time/block from AS01",
        },
        "classification": {
            "method": "nearest_centroid_on_block_direction_median_demeaned_primary_band",
            "protocol": "leave_one_block_out",
            "continuous_repeats_crossed_folds": False,
            "U4SYM_AS01": {"balanced_accuracy": sym_class["balanced_accuracy"], "macro_f1": sym_class["macro_f1"], "permutation_p_value": sym_class["permutation_p_value"], "status": sym_class["status"]},
            "U4ENC_AS01": {"balanced_accuracy": enc_class["balanced_accuracy"], "macro_f1": enc_class["macro_f1"], "permutation_p_value": enc_class["permutation_p_value"], "status": enc_class["status"]},
            "chance_level": 0.25, "practical_target": 0.50,
        },
        "statistical_boundaries": {
            "pointwise_unadjusted_mass_tests_performed": False,
            "CONT_counted_as_independent_scientific_samples": False,
            "bootstrap_random_state": random_state,
            "classification_is_auxiliary_to_physical_metrics": True,
        },
        "ready_for_formal_synthesis": True,
        "ready_reason": "all_frozen_FORMAL4_outputs_completed_and_hash_audited_for_FORMAL5_review",
        "provenance": {
            "data_origin": "real_experiment", "dataset_role": "research_analysis",
            "run_purpose": "research_analysis", "scientifically_eligible": False,
        },
        "scientific_eligibility_pending": "FORMAL-5 synthesis review",
        "final_test_read": False,
        "strong_scientific_conclusion_generated": False,
    }


def _write_plots(
    output: Path, samples: Sequence[Formal4Sample], primary: Mapping[str, Any],
    sensitivity: Mapping[str, Any],
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    (output / "plots").mkdir(parents=True, exist_ok=True)
    frequency = samples[0].frequency_hz
    masks = primary["masks"]
    for block in _BLOCKS:
        fig, axis = plt.subplots(figsize=(9.5, 5.2))
        for direction in _DIRECTIONS:
            group = primary["cells"][(block, direction)]
            matrix = np.vstack([sample.values for sample in group])
            median = np.median(matrix, axis=0)
            minimum = np.min(matrix, axis=0)
            maximum = np.max(matrix, axis=0)
            mask = masks["full"]
            axis.plot(frequency[mask], median[mask], label=f"{direction}°")
            axis.fill_between(frequency[mask], minimum[mask], maximum[mask], alpha=0.12)
        axis.axvspan(200, 4000, color="#4c78a8", alpha=0.05, label="primary 200–4000 Hz")
        axis.axvspan(4000, 8000, color="#f58518", alpha=0.06, label="secondary 4000–8000 Hz")
        axis.set_xscale("log"); axis.set_xlim(200, 8000)
        axis.set_xlabel("Frequency (Hz)"); axis.set_ylabel("Smoothed SPL (dB)")
        axis.set_title(f"{block}: direction medians and CONT range")
        axis.legend(ncol=3, fontsize=8); fig.tight_layout()
        fig.savefig(output / "plots" / f"block_direction_{block}.png", dpi=150)
        plt.close(fig)

    # Frequency-wise robust CONT error across all cells.
    point_mads: list[NDArray[np.float64]] = []
    for group in primary["cells"].values():
        matrix = np.vstack([sample.values for sample in group])
        center = np.median(matrix, axis=0)
        point_mads.append(np.median(np.abs(matrix - center), axis=0))
    fig, axis = plt.subplots(figsize=(9.5, 4.8))
    full = masks["full"]
    axis.plot(frequency[full], np.median(np.vstack(point_mads), axis=0)[full])
    axis.axvline(4000, color="black", linestyle="--", linewidth=1)
    axis.set_xscale("log"); axis.set_xlim(200, 8000)
    axis.set_xlabel("Frequency (Hz)"); axis.set_ylabel("Median pointwise MAD (dB)")
    axis.set_title("CONT repeatability error versus frequency")
    fig.tight_layout(); fig.savefig(output / "plots" / "repeatability_frequency.png", dpi=150); plt.close(fig)

    heatmaps: dict[str, NDArray[np.float64]] = {}
    for block in _BLOCKS:
        matrix = np.zeros((4, 4))
        rows = [row for row in primary["direction"] if row["block_id"] == block and row["band_id"] == "primary"]
        for row in rows:
            left = _DIRECTIONS.index(int(row["direction_a_deg"])); right = _DIRECTIONS.index(int(row["direction_b_deg"]))
            matrix[left, right] = matrix[right, left] = float(row["demeaned_rms_db"])
        heatmaps[block] = matrix
    shared_maximum = max(float(np.max(matrix)) for matrix in heatmaps.values())
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    for axis, block in zip(axes.flat, _BLOCKS, strict=True):
        matrix = heatmaps[block]
        image = axis.imshow(matrix, cmap="viridis", vmin=0.0, vmax=shared_maximum)
        axis.set_xticks(range(4), _DIRECTIONS); axis.set_yticks(range(4), _DIRECTIONS)
        axis.set_title(block); fig.colorbar(image, ax=axis, fraction=0.046)
    fig.suptitle("Primary-band demeaned direction-pair RMS distance (dB)")
    fig.tight_layout(); fig.savefig(output / "plots" / "direction_pairwise_heatmap.png", dpi=150); plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    for axis, direction in zip(axes.flat, _DIRECTIONS, strict=True):
        for assembly, style in (("AS01", "-"), ("AS02", "--")):
            rows = [row for row in primary["configuration_curves"] if row["assembly_id"] == assembly and row["direction_deg"] == direction]
            axis.plot([row["frequency_hz"] for row in rows], [row["u4enc_minus_u4sym_db"] for row in rows], style, label=assembly)
        axis.axvline(4000, color="black", linestyle=":"); axis.axhline(0, color="grey", linewidth=0.8)
        axis.set_xscale("log"); axis.set_title(f"{direction}°"); axis.legend()
    fig.suptitle("U4ENC − U4SYM difference curves (primary/secondary split at 4 kHz)")
    fig.tight_layout(); fig.savefig(output / "plots" / "configuration_difference.png", dpi=150); plt.close(fig)

    primary_rows = [row for row in primary["direction"] if row["band_id"] == "primary"]
    fig, axis = plt.subplots(figsize=(10, 4.8))
    labels = [f"{row['block_id']}:{row['direction_a_deg']}-{row['direction_b_deg']}" for row in primary_rows]
    axis.bar(np.arange(len(labels)), [row["effect_to_repeatability_ratio"] for row in primary_rows])
    axis.axhline(1, color="red", linestyle="--"); axis.set_ylabel("Demeaned effect / CONT p95 floor")
    axis.set_xticks(np.arange(len(labels)), labels, rotation=90, fontsize=6)
    axis.set_title("Direction effect-to-repeatability ratios")
    fig.tight_layout(); fig.savefig(output / "plots" / "effect_to_repeatability_ratio.png", dpi=150); plt.close(fig)

    primary_map = _metric_map(primary); sensitivity_map = _metric_map(sensitivity)
    keys = [key for key in sorted(primary_map) if key[0] == "G_demeaned" and key[2] == "primary"]
    fig, axis = plt.subplots(figsize=(7.5, 4.8))
    x = np.arange(len(keys)); width = 0.36
    axis.bar(x - width / 2, [primary_map[key][0] for key in keys], width, label="all ACTIVE")
    axis.bar(x + width / 2, [sensitivity_map[key][0] for key in keys], width, label="without flags")
    axis.axhline(1, color="red", linestyle="--"); axis.set_xticks(x, [key[1] for key in keys])
    axis.set_ylabel("G_demeaned"); axis.set_title("Outlier-flag sensitivity (primary band)"); axis.legend()
    fig.tight_layout(); fig.savefig(output / "plots" / "outlier_sensitivity.png", dpi=150); plt.close(fig)

    scopes = ("U4SYM_AS01", "U4ENC_AS01")
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for axis, scope in zip(axes, scopes, strict=True):
        matrix = primary["classification_matrices"][scope]
        image = axis.imshow(matrix, cmap="Blues")
        axis.set_xticks(range(4), _DIRECTIONS); axis.set_yticks(range(4), _DIRECTIONS)
        axis.set_xlabel("Predicted"); axis.set_ylabel("True"); axis.set_title(scope)
        for i in range(4):
            for j in range(4): axis.text(j, i, str(matrix[i, j]), ha="center", va="center")
        fig.colorbar(image, ax=axis, fraction=0.046)
    fig.suptitle("Leave-one-block-out grouped validation")
    fig.tight_layout(); fig.savefig(output / "plots" / "grouped_validation_confusion_matrix.png", dpi=150); plt.close(fig)


def _write_artifact_manifests(output: Path) -> int:
    files = sorted(
        path for path in output.rglob("*")
        if path.is_file() and path.name not in {"artifact_manifest.json", "SHA256SUMS"}
    )
    artifacts = [{
        "path": path.relative_to(output).as_posix(), "sha256": artifact_sha256(path),
        "bytes": path.stat().st_size,
    } for path in files]
    _write_json(output / "artifact_manifest.json", {
        "schema_version": "formal4_artifact_manifest_v1", "algorithm": "SHA-256",
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


def verify_formal4_output_hashes(output_directory: str | Path) -> dict[str, Any]:
    root = Path(output_directory).resolve()
    count, manifest_sha = _verify_artifact_manifest(root, "artifact_manifest.json")
    _verify_sha256s(root, "artifact_manifest.json")
    return {"all_match": True, "artifact_count": count, "artifact_manifest_sha256": manifest_sha}


def run_formal4_core_analysis(
    input_directory: str | Path,
    output_directory: str | Path,
    *,
    source_commit: str,
    created_at: str | datetime,
    random_state: int = FORMAL4_RANDOM_STATE,
    bootstrap_iterations: int = FORMAL4_BOOTSTRAP_ITERATIONS,
    permutation_iterations: int = FORMAL4_PERMUTATION_ITERATIONS,
) -> Formal4RunResult:
    """Run the frozen primary and outlier-sensitivity analyses from FORMAL-3 only."""
    if len(source_commit) != 40 or any(character not in "0123456789abcdef" for character in source_commit):
        raise Formal4InputError("source_commit must be a full lowercase Git SHA")
    if bootstrap_iterations < 10 or permutation_iterations < 1:
        raise Formal4InputError("bootstrap/permutation iterations are below auditable minimum")
    timestamp = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)
    try:
        parsed_time = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise Formal4InputError("created_at must be ISO-8601") from exc
    if parsed_time.tzinfo is None:
        raise Formal4InputError("created_at must include timezone")
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing FORMAL-4 output: {output}")
    authority = verify_formal3_authority(input_directory)
    samples = _load_samples(authority.input_directory)
    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        raise FileExistsError(f"refusing to overwrite existing FORMAL-4 staging output: {staging}")
    staging.mkdir(parents=True)
    try:
        primary = _variant_analysis(
            samples, include_flagged=True, random_state=random_state,
            bootstrap_iterations=bootstrap_iterations, permutation_iterations=permutation_iterations,
        )
        sensitivity = _variant_analysis(
            samples, include_flagged=False, random_state=random_state,
            bootstrap_iterations=bootstrap_iterations, permutation_iterations=permutation_iterations,
        )
        sensitivity_rows = _sensitivity_rows(primary, sensitivity, authority.outlier_sample_count)
        summary = _analysis_summary(
            authority, primary, sensitivity, sensitivity_rows,
            source_commit=source_commit, created_at=timestamp, random_state=random_state,
        )
        repeat_fields = (
            "block_id", "configuration", "assembly_id", "reposition_round_id", "direction_deg",
            "band_id", "frequency_point_count", "sample_count", "sample_ids", "pair_count",
            "pair_ids", "pairwise_rms_db", "pairwise_rms_median_db",
            "median_absolute_difference_db", "p95_absolute_difference_db",
            "pointwise_mad_median_db", "pointwise_mad_p95_db",
            "pointwise_sd_median_db", "pointwise_sd_p95_db",
        )
        _write_csv(staging / "repeatability_by_cell.csv", primary["repeatability_by_cell"], repeat_fields)
        _write_csv(staging / "repeatability_summary.csv", primary["repeatability_summary"], tuple(primary["repeatability_summary"][0]))
        _write_csv(staging / "repeatability_frequency.csv", primary["repeatability_frequency"], tuple(primary["repeatability_frequency"][0]))
        _write_csv(staging / "direction_pairwise_effects.csv", primary["direction"], tuple(primary["direction"][0]))
        _write_csv(staging / "direction_effect_summary.csv", primary["direction_summary"], tuple(primary["direction_summary"][0]))
        _write_csv(staging / "direction_gain_summary.csv", primary["gains"], tuple(primary["gains"][0]))
        _write_csv(staging / "direction_gain_contrasts.csv", primary["gain_contrasts"], tuple(primary["gain_contrasts"][0]))
        _write_csv(staging / "configuration_effects.csv", primary["configuration"], tuple(primary["configuration"][0]))
        _write_csv(staging / "configuration_difference_curves.csv", primary["configuration_curves"], tuple(primary["configuration_curves"][0]))
        _write_csv(staging / "assembly_set_effects.csv", primary["assembly"], tuple(primary["assembly"][0]))
        _write_csv(staging / "assembly_set_difference_curves.csv", primary["assembly_curves"], tuple(primary["assembly_curves"][0]))
        _write_csv(staging / "outlier_sensitivity.csv", sensitivity_rows, tuple(sensitivity_rows[0]))
        _write_csv(staging / "grouped_validation_metrics.csv", primary["classification_metrics"], tuple(primary["classification_metrics"][0]))
        _write_csv(staging / "grouped_validation_predictions.csv", primary["classification_predictions"], tuple(primary["classification_predictions"][0]))
        _write_json(staging / "analysis_summary.json", summary)
        _write_json(staging / "run_manifest.json", {
            "schema_version": FORMAL4_SCHEMA_VERSION,
            "created_at": timestamp, "source_commit": source_commit,
            **SCHEMA_VERSION_QUARTET,
            "input": {
                "authority": "FORMAL-3_REAL_IMPORT_QC_only_no_raw_scan",
                "directory": str(authority.input_directory),
                "run_manifest_sha256": authority.run_manifest_sha256,
                "artifact_manifest_sha256": authority.artifact_manifest_sha256,
                "verified_artifact_count": authority.input_artifact_count,
                "zip_sha256": FORMAL3_ZIP_SHA256,
                "active_count": 72, "excluded_count": 19,
                "feature_count": 72, "common_valid_point_count": 255,
            },
            "frozen_grouping": {block: {
                "configuration": identity[0], "assembly_id": identity[1],
                "reposition_round_id": identity[2], "session_id": identity[3],
                "directions_deg": _DIRECTIONS, "CONT_per_direction": 3,
            } for block, identity in _BLOCKS.items()},
            "analysis": {
                "primary_variant": "all_72_ACTIVE_robust_cell_medians",
                "sensitivity_variant": "FORMAL3_outlier_flags_omitted_without_selection_mutation",
                "outlier_count": authority.outlier_sample_count,
                "normalizations": ["raw", "demeaned", "zscore"],
                "bootstrap_iterations": bootstrap_iterations,
                "permutation_iterations": permutation_iterations,
                "random_state": random_state,
                "grouped_validation": "leave_one_block_out_nearest_centroid",
                "mass_unadjusted_pointwise_tests": False,
            },
            "provenance": summary["provenance"],
            "ready_for_formal_synthesis": True,
            "scientifically_eligible": False,
            "final_test_read": False,
            "raw_directory_scanned": False,
            "active_excluded_selection_changed": False,
        })
        _write_plots(staging, samples, primary, sensitivity)
        artifact_count = _write_artifact_manifests(staging)
        verification = verify_formal4_output_hashes(staging)
        if verification["artifact_count"] != artifact_count:
            raise Formal4InputError("FORMAL-4 artifact verification count mismatch")
        staging.rename(output)
        return Formal4RunResult(
            output, 72, 19, authority.outlier_sample_count, True, artifact_count
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
