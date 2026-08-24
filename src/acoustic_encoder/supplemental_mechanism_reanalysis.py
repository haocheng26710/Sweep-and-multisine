"""SUP-1 module library and SUP-2R existing-data mechanism reanalysis."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import csv
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .formal_core_analysis import verify_formal3_authority, verify_formal4_output_hashes
from .formal_final_synthesis import verify_formal5_output_hashes
from .schemas import FeatureSet, artifact_sha256, load_feature_set
from .supplemental_frequency_localization import verify_sup0_output_hashes
from .supplemental_module_scan import (
    SUP1_PRIMARY_FLOOR_P95_DB,
    SUP1_SECONDARY_FLOOR_P95_DB,
    verify_sup1_output_hashes,
)


class SupplementalMechanismInputError(ValueError):
    """Raised when a frozen SUP-1/SUP-2R input contract is violated."""


_V2_MAPPING = {0: "ENC-A", 90: "ENC-B", 180: "ENC-D", 270: "ENC-F"}
_V2_MAPPING_AUTHORITY = "user_V2_incremental_spec_2026-08-24"
_DIRECTIONS = (0, 90, 180, 270)
_MODULES = tuple(f"ENC-{letter}" for letter in "ABCDEFGH")
_HOM_BLOCKS = ("B01", "B02")
_HET_BLOCKS = ("B03", "B04")
_BOOTSTRAP_ITERATIONS = 2000
_RANDOM_STATE = 20260824


@dataclass(frozen=True, slots=True)
class SupplementalMechanismRunResult:
    output_directory: Path
    sup1_measurement_count: int
    formal_active_count: int
    formal_as01_active_count: int
    candidate_window_count: int
    artifact_count: int


@dataclass(frozen=True, slots=True)
class _LoadedInputs:
    frequency_hz: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]
    candidates: tuple[dict[str, str], ...]
    sup1_curves: Mapping[str, NDArray[np.float64]]
    sup1_primary_ids: Mapping[str, tuple[str, ...]]
    sup1_flags: frozenset[str]
    formal_curves: Mapping[tuple[str, int], Mapping[str, NDArray[np.float64]]]
    formal_sample_ids: Mapping[tuple[str, int], Mapping[str, tuple[str, ...]]]
    formal_flags: frozenset[str]
    audit: Mapping[str, Any]


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise SupplementalMechanismInputError(f"cannot read required CSV: {path}") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SupplementalMechanismInputError(f"cannot read required JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SupplementalMechanismInputError(f"required JSON is not an object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (tuple, list)):
        return ";".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise SupplementalMechanismInputError(f"refusing to write empty analysis table: {path.name}")
    fields = tuple(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            if tuple(row) != fields:
                raise SupplementalMechanismInputError(f"inconsistent CSV columns: {path.name}")
            writer.writerow({field: _csv_value(row[field]) for field in fields})


def _frequency(feature: FeatureSet) -> NDArray[np.float64]:
    try:
        result = np.asarray(
            [float(name.removeprefix("spl_").removesuffix("_hz")) for name in feature.feature_names],
            dtype=np.float64,
        )
    except ValueError as exc:
        raise SupplementalMechanismInputError("invalid FORMAL-1 frequency feature name") from exc
    if result.size != 256 or not np.all(np.diff(result) > 0):
        raise SupplementalMechanismInputError("FORMAL-1 common frequency axis mismatch")
    return result


def _load_feature_from_index(root: Path, row: Mapping[str, str]) -> FeatureSet:
    relative = Path(row["feature_npz"])
    base = (root / relative).resolve().with_suffix("")
    try:
        base.relative_to(root.resolve())
    except ValueError as exc:
        raise SupplementalMechanismInputError("feature path escapes authority directory") from exc
    if artifact_sha256(base.with_suffix(".npz")) != row["feature_npz_sha256"]:
        raise SupplementalMechanismInputError(f"feature NPZ hash mismatch: {row['sample_id']}")
    if artifact_sha256(base.with_suffix(".json")) != row["feature_json_sha256"]:
        raise SupplementalMechanismInputError(f"feature JSON hash mismatch: {row['sample_id']}")
    return load_feature_set(base)


def _load_and_audit_inputs(
    *,
    formal3_directory: Path,
    formal4_directory: Path,
    formal5_directory: Path,
    sup0_directory: Path,
    sup1_directory: Path,
) -> _LoadedInputs:
    mapping = validate_v2_physical_mapping(_V2_MAPPING, authority=_V2_MAPPING_AUTHORITY)
    formal3 = verify_formal3_authority(formal3_directory)
    formal4 = verify_formal4_output_hashes(formal4_directory)
    formal5 = verify_formal5_output_hashes(formal5_directory)
    sup0 = verify_sup0_output_hashes(sup0_directory)
    sup1 = verify_sup1_output_hashes(sup1_directory)
    formal3_run = _read_json(formal3_directory / "run_manifest.json")
    formal4_run = _read_json(formal4_directory / "run_manifest.json")
    formal5_run = _read_json(formal5_directory / "final_analysis_manifest.json")
    sup0_run = _read_json(sup0_directory / "run_manifest.json")
    sup1_run = _read_json(sup1_directory / "run_manifest.json")
    if any(
        manifest.get("final_test_read") is not False
        for manifest in (formal3_run, formal4_run, formal5_run, sup0_run, sup1_run)
    ):
        raise SupplementalMechanismInputError("an input authority does not keep final-test sealed")
    if formal5_run.get("disposition") != "supported_with_limits":
        raise SupplementalMechanismInputError("FORMAL-5 frozen disposition mismatch")
    if formal4_run.get("active_excluded_selection_changed") is not False:
        raise SupplementalMechanismInputError("FORMAL-4 reports an ACTIVE/EXCLUDED change")

    candidates = tuple(_read_csv(sup0_directory / "candidate_bands.csv"))
    if len(candidates) != 12 or any(row.get("freeze_for_SUP1_to_SUP4") != "true" for row in candidates):
        raise SupplementalMechanismInputError("SUP-0 frozen candidate-window inventory mismatch")

    sup1_index = _read_csv(sup1_directory / "feature_index.csv")
    sup1_repeatability = _read_csv(sup1_directory / "module_repeatability.csv")
    sup1_qc = _read_csv(sup1_directory / "file_qc.csv")
    if len(sup1_index) != 29 or len(sup1_repeatability) != 8:
        raise SupplementalMechanismInputError("SUP-1 requires 29 measurements and eight modules")
    sup1_features: dict[str, FeatureSet] = {}
    for row in sup1_index:
        feature = _load_feature_from_index(sup1_directory, row)
        if feature.sample_id != row["sample_id"] or feature.meta.data_origin.value != "real_experiment":
            raise SupplementalMechanismInputError(f"SUP-1 feature identity mismatch: {row['sample_id']}")
        sup1_features[row["sample_id"]] = feature
    sup1_primary_ids = {
        row["module_id"]: tuple(row["primary_sample_ids"].split(";"))
        for row in sup1_repeatability
    }
    if set(sup1_primary_ids) != set(_MODULES) or any(len(ids) != 3 for ids in sup1_primary_ids.values()):
        raise SupplementalMechanismInputError("SUP-1 primary triplet membership mismatch")
    sup1_curves = {
        module: np.vstack([sup1_features[sample_id].values for sample_id in ids])
        for module, ids in sup1_primary_ids.items()
    }
    sup1_flags = frozenset(
        row["sample_id"] for row in sup1_qc if row.get("curve_outlier_flag") == "true"
    )

    formal_active = _read_csv(formal3_directory / "active_manifest.csv")
    formal_index = {row["sample_id"]: row for row in _read_csv(formal3_directory / "feature_index.csv")}
    formal_qc = {row["sample_id"]: row for row in _read_csv(formal3_directory / "file_qc.csv")}
    as01_rows = [row for row in formal_active if row["block_id"] in {*_HOM_BLOCKS, *_HET_BLOCKS}]
    expected_blocks = {"B01": "U4SYM", "B02": "U4SYM", "B03": "U4ENC", "B04": "U4ENC"}
    if len(as01_rows) != 48 or Counter(row["block_id"] for row in as01_rows) != Counter({key: 12 for key in expected_blocks}):
        raise SupplementalMechanismInputError("FORMAL AS01 B01-B04 ACTIVE membership mismatch")
    grouped_curves: dict[tuple[str, int], dict[str, list[NDArray[np.float64]]]] = {}
    grouped_ids: dict[tuple[str, int], dict[str, list[str]]] = {}
    formal_reference_frequency: NDArray[np.float64] | None = None
    formal_reference_mask: NDArray[np.bool_] | None = None
    for active in sorted(as01_rows, key=lambda row: row["sample_id"]):
        sample_id = active["sample_id"]
        block = active["block_id"]
        configuration = active["configuration"]
        direction = int(active["direction_id"])
        if (
            active["selection_status"] != "ACTIVE"
            or active["analysis_included"] != "true"
            or active["assembly_id"] != "AS01"
            or expected_blocks.get(block) != configuration
            or direction not in _DIRECTIONS
        ):
            raise SupplementalMechanismInputError(f"FORMAL AS01 identity mismatch: {sample_id}")
        feature = _load_feature_from_index(formal3_directory, formal_index[sample_id])
        if feature.sample_id != sample_id or feature.meta.data_origin.value != "real_experiment":
            raise SupplementalMechanismInputError(f"FORMAL feature identity mismatch: {sample_id}")
        frequency = _frequency(feature)
        if formal_reference_frequency is None:
            formal_reference_frequency = frequency
            formal_reference_mask = np.asarray(feature.valid_mask, dtype=np.bool_)
        elif not np.array_equal(frequency, formal_reference_frequency) or not np.array_equal(
            feature.valid_mask, formal_reference_mask
        ):
            raise SupplementalMechanismInputError("FORMAL AS01 FeatureSets do not share a grid/mask")
        key = (configuration, direction)
        grouped_curves.setdefault(key, {}).setdefault(block, []).append(
            np.asarray(feature.values, dtype=np.float64)
        )
        grouped_ids.setdefault(key, {}).setdefault(block, []).append(sample_id)
    formal_curves = {
        key: {block: np.vstack(curves) for block, curves in blocks.items()}
        for key, blocks in grouped_curves.items()
    }
    formal_sample_ids = {
        key: {block: tuple(ids) for block, ids in blocks.items()}
        for key, blocks in grouped_ids.items()
    }
    for direction in _DIRECTIONS:
        if set(formal_curves[("U4SYM", direction)]) != set(_HOM_BLOCKS):
            raise SupplementalMechanismInputError(f"HOM blocks missing for direction {direction}")
        if set(formal_curves[("U4ENC", direction)]) != set(_HET_BLOCKS):
            raise SupplementalMechanismInputError(f"HET blocks missing for direction {direction}")
        if any(
            curves.shape[0] != 3
            for configuration in ("U4SYM", "U4ENC")
            for curves in formal_curves[(configuration, direction)].values()
        ):
            raise SupplementalMechanismInputError("FORMAL AS01 requires three repeats per block/direction")
    sup1_reference = next(iter(sup1_features.values()))
    sup1_frequency = _frequency(sup1_reference)
    if formal_reference_frequency is None or formal_reference_mask is None:
        raise SupplementalMechanismInputError("FORMAL AS01 frequency authority is empty")
    if not np.array_equal(sup1_frequency, formal_reference_frequency) or not np.array_equal(
        sup1_reference.valid_mask, formal_reference_mask
    ):
        raise SupplementalMechanismInputError("SUP-1 and FORMAL AS01 do not share the frozen grid/mask")
    formal_flags = frozenset(
        sample_id for sample_id, row in formal_qc.items() if row.get("curve_outlier_flag") == "true"
    )
    audit = {
        "status": "all_required_existing_real_data_verified",
        "physical_mapping": {str(key): value for key, value in mapping.items()},
        "physical_mapping_authority": _V2_MAPPING_AUTHORITY,
        "physical_mapping_not_inferred_from_filenames": True,
        "HOM_A_identity": {"configuration": "U4SYM", "assembly": "AS01", "blocks": list(_HOM_BLOCKS)},
        "HET_ABDF_identity": {"configuration": "U4ENC", "assembly": "AS01", "blocks": list(_HET_BLOCKS)},
        "no_new_HOM_or_HET_acquisition": True,
        "SUP1_measurement_count": 29,
        "SUP1_primary_measurement_count": 24,
        "FORMAL3_ACTIVE_count": formal3.active_count,
        "FORMAL3_EXCLUDED_count": formal3.excluded_count,
        "FORMAL_AS01_ACTIVE_count": len(as01_rows),
        "FORMAL_AS01_block_counts": dict(Counter(row["block_id"] for row in as01_rows)),
        "SUP0_candidate_window_count": len(candidates),
        "hash_verification": {
            "FORMAL3": {"artifact_count": formal3.input_artifact_count, "artifact_manifest_sha256": formal3.artifact_manifest_sha256},
            "FORMAL4": formal4,
            "FORMAL5": formal5,
            "SUP0": sup0,
            "SUP1": sup1,
        },
        "provenance": {
            "data_origin": "real_experiment",
            "dataset_role": "supplemental_research_analysis",
            "scientifically_eligible": False,
        },
        "selection_changed": False,
        "final_test_read": False,
        "simulated_data_used": False,
    }
    return _LoadedInputs(
        frequency_hz=formal_reference_frequency,
        valid_mask=formal_reference_mask,
        candidates=candidates,
        sup1_curves=sup1_curves,
        sup1_primary_ids=sup1_primary_ids,
        sup1_flags=sup1_flags,
        formal_curves=formal_curves,
        formal_sample_ids=formal_sample_ids,
        formal_flags=formal_flags,
        audit=audit,
    )


def validate_v2_physical_mapping(
    mapping: Mapping[int, str], *, authority: str
) -> dict[int, str]:
    """Accept only the explicit V2 mapping authority, never filename inference."""
    normalized = {int(direction): str(module) for direction, module in mapping.items()}
    if authority != _V2_MAPPING_AUTHORITY or normalized != _V2_MAPPING:
        raise SupplementalMechanismInputError(
            "SUP-2R physical mapping must come from the explicit user V2 incremental spec"
        )
    return dict(_V2_MAPPING)


def _parent_demean(
    curves: NDArray[np.float64], parent_mask: NDArray[np.bool_]
) -> NDArray[np.float64]:
    return curves - np.mean(curves[:, parent_mask], axis=1, keepdims=True)


def bootstrap_signature_window_effect(
    candidate_curves: NDArray[np.float64],
    reference_curves: NDArray[np.float64],
    *,
    parent_mask: NDArray[np.bool_],
    window_mask: NDArray[np.bool_],
    bootstrap_iterations: int,
    random_state: int,
) -> dict[str, object]:
    """Estimate a module-minus-reference window effect using repeat-level resampling."""
    candidate = np.asarray(candidate_curves, dtype=np.float64)
    reference = np.asarray(reference_curves, dtype=np.float64)
    parent = np.asarray(parent_mask, dtype=np.bool_)
    window = np.asarray(window_mask, dtype=np.bool_)
    if (
        candidate.ndim != 2
        or reference.ndim != 2
        or candidate.shape[1] != reference.shape[1]
        or parent.shape != (candidate.shape[1],)
        or window.shape != parent.shape
        or not np.any(parent)
        or not np.any(window)
    ):
        raise SupplementalMechanismInputError("invalid repeat-curve window input")
    candidate = _parent_demean(candidate, parent)
    reference = _parent_demean(reference, parent)

    def effect(left: NDArray[np.float64], right: NDArray[np.float64]) -> tuple[float, float]:
        delta = np.median(left, axis=0) - np.median(right, axis=0)
        values = delta[window]
        return float(np.mean(values)), float(np.sqrt(np.mean(values**2)))

    signed, rms = effect(candidate, reference)
    rng = np.random.default_rng(random_state)
    signed_bootstrap: list[float] = []
    rms_bootstrap: list[float] = []
    for _ in range(bootstrap_iterations):
        left = candidate[rng.integers(0, candidate.shape[0], size=candidate.shape[0])]
        right = reference[rng.integers(0, reference.shape[0], size=reference.shape[0])]
        boot_signed, boot_rms = effect(left, right)
        signed_bootstrap.append(boot_signed)
        rms_bootstrap.append(boot_rms)
    signed_ci = np.percentile(signed_bootstrap, [2.5, 97.5])
    rms_ci = np.percentile(rms_bootstrap, [2.5, 97.5])
    return {
        "signed_mean_db": signed,
        "rms_db": rms,
        "signed_mean_ci95": (float(signed_ci[0]), float(signed_ci[1])),
        "rms_ci95": (float(rms_ci[0]), float(rms_ci[1])),
        "bootstrap_iterations": bootstrap_iterations,
        "resampling_unit": "whole_repeat_curve",
    }


def bootstrap_array_window_effect(
    hom_block_curves: Mapping[str, NDArray[np.float64]],
    het_block_curves: Mapping[str, NDArray[np.float64]],
    *,
    parent_mask: NDArray[np.bool_],
    window_mask: NDArray[np.bool_],
    bootstrap_iterations: int,
    random_state: int,
) -> dict[str, object]:
    """Estimate HET-minus-HOM while preserving configuration/block/repeat clusters."""
    parent = np.asarray(parent_mask, dtype=np.bool_)
    window = np.asarray(window_mask, dtype=np.bool_)
    groups = {
        "HOM": {key: np.asarray(value, dtype=np.float64) for key, value in hom_block_curves.items()},
        "HET": {key: np.asarray(value, dtype=np.float64) for key, value in het_block_curves.items()},
    }
    point_count = next(iter(groups["HOM"].values())).shape[1]
    if (
        any(len(group) < 2 for group in groups.values())
        or parent.shape != (point_count,)
        or window.shape != parent.shape
        or not np.any(parent)
        or not np.any(window)
        or any(
            curves.ndim != 2 or curves.shape[0] < 1 or curves.shape[1] != point_count
            for group in groups.values()
            for curves in group.values()
        )
    ):
        raise SupplementalMechanismInputError("invalid block/repeat array window input")

    def representative(
        group: Mapping[str, NDArray[np.float64]],
        rng: np.random.Generator | None = None,
    ) -> NDArray[np.float64]:
        keys = tuple(sorted(group))
        selected = keys if rng is None else tuple(rng.choice(keys, size=len(keys), replace=True))
        block_medians: list[NDArray[np.float64]] = []
        for key in selected:
            curves = group[str(key)]
            if rng is not None:
                curves = curves[rng.integers(0, curves.shape[0], size=curves.shape[0])]
            block_medians.append(np.median(curves, axis=0))
        result = np.median(np.vstack(block_medians), axis=0)
        return result - np.mean(result[parent])

    def effect(
        hom_curve: NDArray[np.float64], het_curve: NDArray[np.float64]
    ) -> tuple[NDArray[np.float64], float, float]:
        delta = het_curve - hom_curve
        values = delta[window]
        return delta, float(np.mean(values)), float(np.sqrt(np.mean(values**2)))

    delta, signed, rms = effect(representative(groups["HOM"]), representative(groups["HET"]))
    rng = np.random.default_rng(random_state)
    signed_bootstrap: list[float] = []
    rms_bootstrap: list[float] = []
    for _ in range(bootstrap_iterations):
        _, boot_signed, boot_rms = effect(
            representative(groups["HOM"], rng), representative(groups["HET"], rng)
        )
        signed_bootstrap.append(boot_signed)
        rms_bootstrap.append(boot_rms)
    signed_ci = np.percentile(signed_bootstrap, [2.5, 97.5])
    rms_ci = np.percentile(rms_bootstrap, [2.5, 97.5])
    return {
        "delta_curve_db": delta,
        "signed_mean_db": signed,
        "rms_db": rms,
        "signed_mean_ci95": (float(signed_ci[0]), float(signed_ci[1])),
        "rms_ci95": (float(rms_ci[0]), float(rms_ci[1])),
        "bootstrap_iterations": bootstrap_iterations,
        "resampling_unit": "configuration_block_then_whole_repeat_curve",
    }


def _average_ranks(values: NDArray[np.float64]) -> NDArray[np.float64]:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=np.float64)
    start = 0
    while start < values.size:
        end = start + 1
        while end < values.size and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + 1 + end) / 2.0
        start = end
    return ranks


def _safe_similarity(left: NDArray[np.float64], right: NDArray[np.float64]) -> tuple[float, float, float]:
    if (
        np.std(left) <= 1.0e-12
        or np.std(right) <= 1.0e-12
        or np.linalg.norm(left) <= 1.0e-12
        or np.linalg.norm(right) <= 1.0e-12
    ):
        return float("nan"), float("nan"), float("nan")
    pearson = float(np.corrcoef(left, right)[0, 1])
    spearman = float(np.corrcoef(_average_ranks(left), _average_ranks(right))[0, 1])
    cosine = float(np.dot(left, right) / (np.linalg.norm(left) * np.linalg.norm(right)))
    return tuple(1.0 if abs(value - 1.0) < 1.0e-12 else -1.0 if abs(value + 1.0) < 1.0e-12 else value
                 for value in (pearson, spearman, cosine))  # type: ignore[return-value]


def bootstrap_window_pattern_correspondence(
    candidate_curves: NDArray[np.float64],
    reference_curves: NDArray[np.float64],
    hom_block_curves: Mapping[str, NDArray[np.float64]],
    het_block_curves: Mapping[str, NDArray[np.float64]],
    *,
    windows: Sequence[tuple[str, NDArray[np.bool_], NDArray[np.bool_]]],
    bootstrap_iterations: int,
    random_state: int,
) -> dict[str, object]:
    """Compare fixed-window patterns with repeat- and block-cluster bootstrap CIs."""
    candidate = np.asarray(candidate_curves, dtype=np.float64)
    reference = np.asarray(reference_curves, dtype=np.float64)
    hom = {key: np.asarray(value, dtype=np.float64) for key, value in hom_block_curves.items()}
    het = {key: np.asarray(value, dtype=np.float64) for key, value in het_block_curves.items()}
    point_count = candidate.shape[1]
    if (
        candidate.ndim != 2
        or reference.shape[1] != point_count
        or len(windows) < 3
        or len(hom) < 2
        or len(het) < 2
    ):
        raise SupplementalMechanismInputError("invalid fixed-window correspondence input")

    def module_representatives(rng: np.random.Generator | None) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        if rng is None:
            left, right = candidate, reference
        else:
            left = candidate[rng.integers(0, candidate.shape[0], size=candidate.shape[0])]
            right = reference[rng.integers(0, reference.shape[0], size=reference.shape[0])]
        return np.median(left, axis=0), np.median(right, axis=0)

    def array_representative(
        group: Mapping[str, NDArray[np.float64]], rng: np.random.Generator | None
    ) -> NDArray[np.float64]:
        keys = tuple(sorted(group))
        selected = keys if rng is None else tuple(rng.choice(keys, size=len(keys), replace=True))
        medians: list[NDArray[np.float64]] = []
        for key in selected:
            curves = group[str(key)]
            if rng is not None:
                curves = curves[rng.integers(0, curves.shape[0], size=curves.shape[0])]
            medians.append(np.median(curves, axis=0))
        return np.median(np.vstack(medians), axis=0)

    def window_vectors(rng: np.random.Generator | None) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        module, module_reference = module_representatives(rng)
        hom_curve = array_representative(hom, rng)
        het_curve = array_representative(het, rng)
        module_values: list[float] = []
        array_values: list[float] = []
        for _, parent_mask, window_mask in windows:
            parent = np.asarray(parent_mask, dtype=np.bool_)
            window = np.asarray(window_mask, dtype=np.bool_)
            module_delta = (
                module - np.mean(module[parent])
                - module_reference + np.mean(module_reference[parent])
            )
            array_delta = (
                het_curve - np.mean(het_curve[parent])
                - hom_curve + np.mean(hom_curve[parent])
            )
            module_values.append(float(np.mean(module_delta[window])))
            array_values.append(float(np.mean(array_delta[window])))
        return np.asarray(module_values), np.asarray(array_values)

    module_point, array_point = window_vectors(None)
    pearson, spearman, cosine = _safe_similarity(module_point, array_point)
    sign_agreement = float(np.mean(np.sign(module_point) == np.sign(array_point)))
    rng = np.random.default_rng(random_state)
    bootstrap_metrics: list[tuple[float, float, float, float]] = []
    for _ in range(bootstrap_iterations):
        module_boot, array_boot = window_vectors(rng)
        metrics = _safe_similarity(module_boot, array_boot)
        if np.all(np.isfinite(metrics)):
            bootstrap_metrics.append((*metrics, float(np.mean(np.sign(module_boot) == np.sign(array_boot)))))
    if not bootstrap_metrics or not np.all(np.isfinite((pearson, spearman, cosine))):
        return {
            "pearson_r": None,
            "spearman_r": None,
            "cosine_similarity": None,
            "window_sign_agreement_fraction": sign_agreement,
            "evidence_status": "not_estimable_zero_reference_signature",
            "bootstrap_iterations": bootstrap_iterations,
            "resampling_unit": "module_repeat_and_configuration_block_repeat_clusters",
        }
    boot = np.asarray(bootstrap_metrics, dtype=np.float64)
    intervals = [tuple(float(value) for value in np.percentile(boot[:, index], [2.5, 97.5])) for index in range(4)]
    stable = all(intervals[index][0] > 0.0 for index in range(3))
    return {
        "pearson_r": pearson,
        "pearson_ci95": intervals[0],
        "spearman_r": spearman,
        "spearman_ci95": intervals[1],
        "cosine_similarity": cosine,
        "cosine_ci95": intervals[2],
        "window_sign_agreement_fraction": sign_agreement,
        "window_sign_agreement_ci95": intervals[3],
        "evidence_status": (
            "stable_positive_pattern_correspondence"
            if stable
            else "exploratory_inconclusive_correspondence"
        ),
        "bootstrap_iterations": bootstrap_iterations,
        "resampling_unit": "module_repeat_and_configuration_block_repeat_clusters",
    }


def _bootstrap_repeat_representatives(
    curves: NDArray[np.float64], *, iterations: int, random_state: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    point = np.median(curves, axis=0)
    rng = np.random.default_rng(random_state)
    boot = np.empty((iterations, curves.shape[1]), dtype=np.float64)
    for index in range(iterations):
        selected = curves[rng.integers(0, curves.shape[0], size=curves.shape[0])]
        boot[index] = np.median(selected, axis=0)
    return point, boot


def _bootstrap_configuration_representatives(
    blocks: Mapping[str, NDArray[np.float64]], *, iterations: int, random_state: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    keys = tuple(sorted(blocks))
    point = np.median(
        np.vstack([np.median(blocks[key], axis=0) for key in keys]), axis=0
    )
    rng = np.random.default_rng(random_state)
    boot = np.empty((iterations, point.size), dtype=np.float64)
    for index in range(iterations):
        selected_keys = rng.choice(keys, size=len(keys), replace=True)
        block_medians: list[NDArray[np.float64]] = []
        for key in selected_keys:
            curves = blocks[str(key)]
            selected_curves = curves[
                rng.integers(0, curves.shape[0], size=curves.shape[0])
            ]
            block_medians.append(np.median(selected_curves, axis=0))
        boot[index] = np.median(np.vstack(block_medians), axis=0)
    return point, boot


def _demean_rows(
    curves: NDArray[np.float64], parent_mask: NDArray[np.bool_]
) -> NDArray[np.float64]:
    if curves.ndim == 1:
        return curves - np.mean(curves[parent_mask])
    return curves - np.mean(curves[:, parent_mask], axis=1, keepdims=True)


def _window_statistics(
    candidate_point: NDArray[np.float64],
    reference_point: NDArray[np.float64],
    candidate_boot: NDArray[np.float64],
    reference_boot: NDArray[np.float64],
    *,
    parent_mask: NDArray[np.bool_],
    window_mask: NDArray[np.bool_],
) -> dict[str, float | tuple[float, float] | NDArray[np.float64]]:
    point_delta = _demean_rows(candidate_point, parent_mask) - _demean_rows(
        reference_point, parent_mask
    )
    boot_delta = _demean_rows(candidate_boot, parent_mask) - _demean_rows(
        reference_boot, parent_mask
    )
    point_values = point_delta[window_mask]
    boot_values = boot_delta[:, window_mask]
    signed = float(np.mean(point_values))
    rms = float(np.sqrt(np.mean(point_values**2)))
    signed_boot = np.mean(boot_values, axis=1)
    rms_boot = np.sqrt(np.mean(boot_values**2, axis=1))
    return {
        "signed_mean_db": signed,
        "rms_db": rms,
        "signed_mean_ci95": tuple(float(value) for value in np.percentile(signed_boot, [2.5, 97.5])),
        "rms_ci95": tuple(float(value) for value in np.percentile(rms_boot, [2.5, 97.5])),
        "signed_bootstrap": signed_boot,
        "rms_bootstrap": rms_boot,
        "delta_curve": point_delta,
    }


def _candidate_masks(
    inputs: _LoadedInputs,
) -> tuple[dict[str, NDArray[np.bool_]], dict[str, NDArray[np.bool_]]]:
    frequency = inputs.frequency_hz
    parent_masks = {
        "primary": inputs.valid_mask & (frequency >= 200.0) & (frequency <= 4000.0),
        "secondary": inputs.valid_mask & (frequency >= 4000.0) & (frequency <= 8000.0),
    }
    window_masks = {
        row["window_id"]: inputs.valid_mask
        & (frequency >= float(row["frequency_low_hz"]))
        & (frequency <= float(row["frequency_high_hz"]))
        for row in inputs.candidates
    }
    if any(int(np.count_nonzero(window_masks[row["window_id"]])) != int(row["point_count"]) for row in inputs.candidates):
        raise SupplementalMechanismInputError("SUP-0 candidate window point-count mismatch")
    return parent_masks, window_masks


def _filter_flagged_curves(
    curves: Mapping[str, NDArray[np.float64]],
    sample_ids: Mapping[str, tuple[str, ...]],
    flags: frozenset[str],
) -> dict[str, NDArray[np.float64]]:
    filtered: dict[str, NDArray[np.float64]] = {}
    for block, values in curves.items():
        keep = np.asarray([sample_id not in flags for sample_id in sample_ids[block]])
        if int(np.count_nonzero(keep)) < 2:
            raise SupplementalMechanismInputError(
                f"sensitivity variant leaves fewer than two repeats in {block}"
            )
        filtered[block] = values[keep]
    return filtered


def _ci_excludes_zero(interval: tuple[float, float]) -> bool:
    return interval[0] > 0.0 or interval[1] < 0.0


def _analyse_module_library(
    inputs: _LoadedInputs,
    parent_masks: Mapping[str, NDArray[np.bool_]],
    window_masks: Mapping[str, NDArray[np.bool_]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    representatives: dict[tuple[str, str], tuple[NDArray[np.float64], NDArray[np.float64]]] = {}
    for module_index, module in enumerate(_MODULES):
        curves = inputs.sup1_curves[module]
        representatives[(module, "primary")] = _bootstrap_repeat_representatives(
            curves,
            iterations=_BOOTSTRAP_ITERATIONS,
            random_state=_RANDOM_STATE + module_index * 101,
        )
        ids = inputs.sup1_primary_ids[module]
        keep = np.asarray([sample_id not in inputs.sup1_flags for sample_id in ids])
        sensitivity = curves[keep]
        if sensitivity.shape[0] < 2:
            raise SupplementalMechanismInputError(
                f"SUP-1 sensitivity leaves fewer than two repeats for {module}"
            )
        representatives[(module, "sensitivity")] = _bootstrap_repeat_representatives(
            sensitivity,
            iterations=_BOOTSTRAP_ITERATIONS,
            random_state=_RANDOM_STATE + module_index * 101 + 41,
        )
    zero_point = np.zeros_like(next(iter(representatives.values()))[0])
    zero_boot = np.zeros_like(next(iter(representatives.values()))[1])
    rows: list[dict[str, Any]] = []
    plot_data: dict[str, Any] = {"representatives": {}, "window_vectors": {}}
    for module in _MODULES:
        module_point, module_boot = representatives[(module, "primary")]
        sensitivity_point, sensitivity_boot = representatives[(module, "sensitivity")]
        a_point, a_boot = representatives[("ENC-A", "primary")]
        a_sensitivity_point, a_sensitivity_boot = representatives[("ENC-A", "sensitivity")]
        plot_data["representatives"][module] = module_point
        window_vector: list[float] = []
        for candidate in inputs.candidates:
            window_id = candidate["window_id"]
            band = candidate["parent_band"]
            parent = parent_masks[band]
            window = window_masks[window_id]
            absolute = _window_statistics(
                module_point,
                zero_point,
                module_boot,
                zero_boot,
                parent_mask=parent,
                window_mask=window,
            )
            absolute_sensitivity = _window_statistics(
                sensitivity_point,
                zero_point,
                sensitivity_boot,
                zero_boot,
                parent_mask=parent,
                window_mask=window,
            )
            if module == "ENC-A":
                versus_a = {
                    "signed_mean_db": 0.0,
                    "rms_db": 0.0,
                    "signed_mean_ci95": (0.0, 0.0),
                    "rms_ci95": (0.0, 0.0),
                }
                versus_a_sensitivity = versus_a
            else:
                versus_a = _window_statistics(
                    module_point,
                    a_point,
                    module_boot,
                    a_boot,
                    parent_mask=parent,
                    window_mask=window,
                )
                versus_a_sensitivity = _window_statistics(
                    sensitivity_point,
                    a_sensitivity_point,
                    sensitivity_boot,
                    a_sensitivity_boot,
                    parent_mask=parent,
                    window_mask=window,
                )
            signed_ci = versus_a["signed_mean_ci95"]
            rms_ci = versus_a["rms_ci95"]
            assert isinstance(signed_ci, tuple) and isinstance(rms_ci, tuple)
            floor = float(candidate["primary_cont_p95_rms_db"])
            window_vector.append(float(versus_a["signed_mean_db"]))
            rows.append({
                "module_id": module,
                "reference_module_id": "ENC-A",
                "window_id": window_id,
                "parent_band": band,
                "frequency_low_hz": float(candidate["frequency_low_hz"]),
                "frequency_high_hz": float(candidate["frequency_high_hz"]),
                "sup0_same_window_cont_p95_db": floor,
                "absolute_parent_demeaned_signed_mean_db": absolute["signed_mean_db"],
                "absolute_signed_mean_ci95_low": absolute["signed_mean_ci95"][0],
                "absolute_signed_mean_ci95_high": absolute["signed_mean_ci95"][1],
                "versus_A_signed_mean_db": versus_a["signed_mean_db"],
                "versus_A_signed_mean_ci95_low": signed_ci[0],
                "versus_A_signed_mean_ci95_high": signed_ci[1],
                "versus_A_rms_db": versus_a["rms_db"],
                "versus_A_rms_ci95_low": rms_ci[0],
                "versus_A_rms_ci95_high": rms_ci[1],
                "versus_A_rms_to_floor_ratio": float(versus_a["rms_db"]) / floor,
                "signed_effect_ci_excludes_zero": _ci_excludes_zero(signed_ci),
                "sensitivity_absolute_signed_mean_db": absolute_sensitivity["signed_mean_db"],
                "sensitivity_versus_A_signed_mean_db": versus_a_sensitivity["signed_mean_db"],
                "sensitivity_versus_A_rms_db": versus_a_sensitivity["rms_db"],
                "primary_repeat_ids": inputs.sup1_primary_ids[module],
                "primary_flagged_repeat_ids": tuple(
                    sample_id for sample_id in inputs.sup1_primary_ids[module]
                    if sample_id in inputs.sup1_flags
                ),
                "bootstrap_iterations": _BOOTSTRAP_ITERATIONS,
                "resampling_unit": "whole_SUP1_repeat_curve",
                "window_selection": "SUP0_frozen_no_reselection",
                "causal_contribution_interpretation_allowed": False,
            })
        plot_data["window_vectors"][module] = np.asarray(window_vector, dtype=np.float64)
    return rows, plot_data


def _analyse_array_differences(
    inputs: _LoadedInputs,
    parent_masks: Mapping[str, NDArray[np.bool_]],
    window_masks: Mapping[str, NDArray[np.bool_]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    plot_data: dict[str, Any] = {"delta_curves": {}, "delta_boot": {}, "window_patterns": {}}
    for direction_index, direction in enumerate(_DIRECTIONS):
        primary_hom = inputs.formal_curves[("U4SYM", direction)]
        primary_het = inputs.formal_curves[("U4ENC", direction)]
        sensitivity_hom = _filter_flagged_curves(
            primary_hom,
            inputs.formal_sample_ids[("U4SYM", direction)],
            inputs.formal_flags,
        )
        sensitivity_het = _filter_flagged_curves(
            primary_het,
            inputs.formal_sample_ids[("U4ENC", direction)],
            inputs.formal_flags,
        )
        variants = {
            "primary": (primary_hom, primary_het),
            "sensitivity": (sensitivity_hom, sensitivity_het),
        }
        variant_representatives: dict[str, tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]] = {}
        for variant_index, (variant, (hom, het)) in enumerate(variants.items()):
            hom_point, hom_boot = _bootstrap_configuration_representatives(
                hom,
                iterations=_BOOTSTRAP_ITERATIONS,
                random_state=_RANDOM_STATE + direction_index * 1009 + variant_index * 53,
            )
            het_point, het_boot = _bootstrap_configuration_representatives(
                het,
                iterations=_BOOTSTRAP_ITERATIONS,
                random_state=_RANDOM_STATE + direction_index * 1009 + variant_index * 53 + 19,
            )
            variant_representatives[variant] = (hom_point, hom_boot, het_point, het_boot)
        pattern_point: list[float] = []
        pattern_boot: list[NDArray[np.float64]] = []
        for candidate in inputs.candidates:
            window_id = candidate["window_id"]
            band = candidate["parent_band"]
            parent = parent_masks[band]
            window = window_masks[window_id]
            hom_point, hom_boot, het_point, het_boot = variant_representatives["primary"]
            primary = _window_statistics(
                het_point, hom_point, het_boot, hom_boot,
                parent_mask=parent, window_mask=window,
            )
            hom_s_point, hom_s_boot, het_s_point, het_s_boot = variant_representatives["sensitivity"]
            sensitivity = _window_statistics(
                het_s_point, hom_s_point, het_s_boot, hom_s_boot,
                parent_mask=parent, window_mask=window,
            )
            signed_ci = primary["signed_mean_ci95"]
            rms_ci = primary["rms_ci95"]
            assert isinstance(signed_ci, tuple) and isinstance(rms_ci, tuple)
            floor = float(candidate["primary_cont_p95_rms_db"])
            pattern_point.append(float(primary["signed_mean_db"]))
            pattern_boot.append(np.asarray(primary["signed_bootstrap"], dtype=np.float64))
            rows.append({
                "direction_deg": direction,
                "mapped_physical_module": _V2_MAPPING[direction],
                "HOM_identity": "HOM-A=U4SYM_AS01_B01_B02",
                "HET_identity": "HET-ABDF=U4ENC_AS01_B03_B04",
                "window_id": window_id,
                "parent_band": band,
                "frequency_low_hz": float(candidate["frequency_low_hz"]),
                "frequency_high_hz": float(candidate["frequency_high_hz"]),
                "sup0_same_window_cont_p95_db": floor,
                "het_minus_hom_signed_mean_db": primary["signed_mean_db"],
                "signed_mean_ci95_low": signed_ci[0],
                "signed_mean_ci95_high": signed_ci[1],
                "het_minus_hom_rms_db": primary["rms_db"],
                "rms_ci95_low": rms_ci[0],
                "rms_ci95_high": rms_ci[1],
                "rms_to_sup0_floor_ratio": float(primary["rms_db"]) / floor,
                "point_effect_exceeds_floor": float(primary["rms_db"]) > floor,
                "rms_ci95_low_exceeds_floor": rms_ci[0] > floor,
                "signed_effect_ci_excludes_zero": _ci_excludes_zero(signed_ci),
                "sensitivity_signed_mean_db": sensitivity["signed_mean_db"],
                "sensitivity_rms_db": sensitivity["rms_db"],
                "sensitivity_rms_to_sup0_floor_ratio": float(sensitivity["rms_db"]) / floor,
                "hom_block_ids": _HOM_BLOCKS,
                "het_block_ids": _HET_BLOCKS,
                "active_repeat_count_per_block_direction": 3,
                "bootstrap_iterations": _BOOTSTRAP_ITERATIONS,
                "resampling_unit": "configuration_block_then_whole_repeat_curve",
                "formal_active_excluded_changed": False,
                "window_selection": "SUP0_frozen_no_reselection",
            })
        pattern_matrix = np.column_stack(pattern_boot)
        plot_data["window_patterns"][direction] = np.asarray(pattern_point, dtype=np.float64)
        plot_data["window_patterns"][("bootstrap", direction)] = pattern_matrix
        for variant in ("primary", "sensitivity"):
            hom_point, hom_boot, het_point, het_boot = variant_representatives[variant]
            delta = np.zeros_like(hom_point)
            delta_boot = np.zeros_like(hom_boot)
            for band, parent in parent_masks.items():
                delta[parent] = (
                    _demean_rows(het_point, parent)[parent]
                    - _demean_rows(hom_point, parent)[parent]
                )
                delta_boot[:, parent] = (
                    _demean_rows(het_boot, parent)[:, parent]
                    - _demean_rows(hom_boot, parent)[:, parent]
                )
            plot_data["delta_curves"][(variant, direction)] = delta
            plot_data["delta_boot"][(variant, direction)] = delta_boot
        delta = plot_data["delta_curves"][("primary", direction)]
        delta_boot = plot_data["delta_boot"][("primary", direction)]
        low, high = np.percentile(delta_boot, [2.5, 97.5], axis=0)
        for index in np.flatnonzero(inputs.valid_mask):
            curve_rows.append({
                "direction_deg": direction,
                "mapped_physical_module": _V2_MAPPING[direction],
                "frequency_hz": float(inputs.frequency_hz[index]),
                "het_minus_hom_parent_demeaned_db": float(delta[index]),
                "bootstrap_ci95_low": float(low[index]),
                "bootstrap_ci95_high": float(high[index]),
                "frequency_band": "primary" if inputs.frequency_hz[index] <= 4000.0 else "secondary",
                "final_test_read": False,
            })
    return rows, curve_rows, plot_data


def _analyse_correspondence(
    inputs: _LoadedInputs,
    parent_masks: Mapping[str, NDArray[np.bool_]],
    window_masks: Mapping[str, NDArray[np.bool_]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scope_candidates = {
        "primary_fixed_windows": tuple(
            row for row in inputs.candidates if row["parent_band"] == "primary"
        ),
        "all_fixed_windows_secondary_included": inputs.candidates,
    }
    for direction_index, direction in enumerate(_DIRECTIONS):
        primary_hom = inputs.formal_curves[("U4SYM", direction)]
        primary_het = inputs.formal_curves[("U4ENC", direction)]
        sensitivity_hom = _filter_flagged_curves(
            primary_hom,
            inputs.formal_sample_ids[("U4SYM", direction)],
            inputs.formal_flags,
        )
        sensitivity_het = _filter_flagged_curves(
            primary_het,
            inputs.formal_sample_ids[("U4ENC", direction)],
            inputs.formal_flags,
        )
        for module_index, module in enumerate(("ENC-A", "ENC-B", "ENC-D", "ENC-F")):
            candidate = inputs.sup1_curves[module]
            candidate_ids = inputs.sup1_primary_ids[module]
            candidate_sensitivity = candidate[
                np.asarray([sample_id not in inputs.sup1_flags for sample_id in candidate_ids])
            ]
            reference = inputs.sup1_curves["ENC-A"]
            reference_ids = inputs.sup1_primary_ids["ENC-A"]
            reference_sensitivity = reference[
                np.asarray([sample_id not in inputs.sup1_flags for sample_id in reference_ids])
            ]
            for scope_index, (scope, candidates) in enumerate(scope_candidates.items()):
                windows = tuple(
                    (
                        row["window_id"],
                        parent_masks[row["parent_band"]],
                        window_masks[row["window_id"]],
                    )
                    for row in candidates
                )
                if module == "ENC-A":
                    primary: dict[str, Any] = {
                        "pearson_r": None,
                        "pearson_ci95": (None, None),
                        "spearman_r": None,
                        "spearman_ci95": (None, None),
                        "cosine_similarity": None,
                        "cosine_ci95": (None, None),
                        "window_sign_agreement_fraction": None,
                        "window_sign_agreement_ci95": (None, None),
                        "evidence_status": "not_estimable_zero_A_minus_A_reference_signature",
                    }
                    sensitivity = primary
                else:
                    seed = _RANDOM_STATE + direction_index * 10007 + module_index * 503 + scope_index * 61
                    primary = bootstrap_window_pattern_correspondence(
                        candidate,
                        reference,
                        primary_hom,
                        primary_het,
                        windows=windows,
                        bootstrap_iterations=_BOOTSTRAP_ITERATIONS,
                        random_state=seed,
                    )
                    sensitivity = bootstrap_window_pattern_correspondence(
                        candidate_sensitivity,
                        reference_sensitivity,
                        sensitivity_hom,
                        sensitivity_het,
                        windows=windows,
                        bootstrap_iterations=_BOOTSTRAP_ITERATIONS,
                        random_state=seed + 29,
                    )
                pearson_ci = primary.get("pearson_ci95", (None, None))
                spearman_ci = primary.get("spearman_ci95", (None, None))
                cosine_ci = primary.get("cosine_ci95", (None, None))
                sign_ci = primary.get("window_sign_agreement_ci95", (None, None))
                rows.append({
                    "direction_deg": direction,
                    "physical_position_module": _V2_MAPPING[direction],
                    "single_entry_module_compared": module,
                    "is_physical_position_mapping": module == _V2_MAPPING[direction],
                    "signature_definition": f"{module}_minus_ENC-A_parent_demeaned_fixed_window_signed_means",
                    "window_scope": scope,
                    "window_count": len(windows),
                    "pearson_r": primary.get("pearson_r"),
                    "pearson_ci95_low": pearson_ci[0],
                    "pearson_ci95_high": pearson_ci[1],
                    "spearman_r": primary.get("spearman_r"),
                    "spearman_ci95_low": spearman_ci[0],
                    "spearman_ci95_high": spearman_ci[1],
                    "cosine_similarity": primary.get("cosine_similarity"),
                    "cosine_ci95_low": cosine_ci[0],
                    "cosine_ci95_high": cosine_ci[1],
                    "window_sign_agreement_fraction": primary.get("window_sign_agreement_fraction"),
                    "window_sign_agreement_ci95_low": sign_ci[0],
                    "window_sign_agreement_ci95_high": sign_ci[1],
                    "evidence_status": primary["evidence_status"],
                    "sensitivity_pearson_r": sensitivity.get("pearson_r"),
                    "sensitivity_spearman_r": sensitivity.get("spearman_r"),
                    "sensitivity_cosine_similarity": sensitivity.get("cosine_similarity"),
                    "sensitivity_window_sign_agreement_fraction": sensitivity.get("window_sign_agreement_fraction"),
                    "sensitivity_evidence_status": sensitivity["evidence_status"],
                    "bootstrap_iterations": 0 if module == "ENC-A" else _BOOTSTRAP_ITERATIONS,
                    "resampling_unit": "module_repeat_and_configuration_block_repeat_clusters",
                    "frequency_points_resampled_as_independent_samples": False,
                    "correlation_is_causal_contribution": False,
                    "independent_module_contribution_identifiable": False,
                })
    return rows


def _direction_consistency_rows(
    inputs: _LoadedInputs, array_plot_data: Mapping[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scopes = {
        "primary_fixed_windows": np.asarray(
            [index for index, row in enumerate(inputs.candidates) if row["parent_band"] == "primary"]
        ),
        "all_fixed_windows_secondary_included": np.arange(len(inputs.candidates)),
    }
    for left_index, left in enumerate(_DIRECTIONS):
        for right in _DIRECTIONS[left_index + 1:]:
            for scope, indices in scopes.items():
                left_point = array_plot_data["window_patterns"][left][indices]
                right_point = array_plot_data["window_patterns"][right][indices]
                pearson, spearman, cosine = _safe_similarity(left_point, right_point)
                sign = float(np.mean(np.sign(left_point) == np.sign(right_point)))
                left_boot = array_plot_data["window_patterns"][("bootstrap", left)][:, indices]
                right_boot = array_plot_data["window_patterns"][("bootstrap", right)][:, indices]
                boot_metrics = np.asarray([
                    (*_safe_similarity(a, b), float(np.mean(np.sign(a) == np.sign(b))))
                    for a, b in zip(left_boot, right_boot, strict=True)
                ], dtype=np.float64)
                finite = np.all(np.isfinite(boot_metrics), axis=1)
                intervals = np.percentile(boot_metrics[finite], [2.5, 97.5], axis=0)
                rows.append({
                    "direction_a_deg": left,
                    "direction_b_deg": right,
                    "window_scope": scope,
                    "window_count": int(indices.size),
                    "pearson_r": pearson,
                    "pearson_ci95_low": float(intervals[0, 0]),
                    "pearson_ci95_high": float(intervals[1, 0]),
                    "spearman_r": spearman,
                    "spearman_ci95_low": float(intervals[0, 1]),
                    "spearman_ci95_high": float(intervals[1, 1]),
                    "cosine_similarity": cosine,
                    "cosine_ci95_low": float(intervals[0, 2]),
                    "cosine_ci95_high": float(intervals[1, 2]),
                    "window_sign_agreement_fraction": sign,
                    "window_sign_agreement_ci95_low": float(intervals[0, 3]),
                    "window_sign_agreement_ci95_high": float(intervals[1, 3]),
                    "consistent_positive_pattern_ci": bool(
                        intervals[0, 0] > 0 and intervals[0, 1] > 0 and intervals[0, 2] > 0
                    ),
                    "bootstrap_iterations": _BOOTSTRAP_ITERATIONS,
                    "frequency_points_resampled_as_independent_samples": False,
                })
    return rows


def _piecewise_demeaned_curve(
    curve: NDArray[np.float64], parent_masks: Mapping[str, NDArray[np.bool_]]
) -> NDArray[np.float64]:
    result = np.full_like(curve, np.nan)
    for parent in parent_masks.values():
        result[parent] = curve[parent] - np.mean(curve[parent])
    return result


def _write_plots(
    output: Path,
    inputs: _LoadedInputs,
    parent_masks: Mapping[str, NDArray[np.bool_]],
    module_plot_data: Mapping[str, Any],
    array_plot_data: Mapping[str, Any],
    array_rows: Sequence[Mapping[str, Any]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_dir = output / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    frequency = inputs.frequency_hz

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=False)
    for module in _MODULES:
        curve = _piecewise_demeaned_curve(module_plot_data["representatives"][module], parent_masks)
        axes[0].plot(frequency, curve, linewidth=1.2, label=module)
    axes[0].set_xscale("log")
    axes[0].set_xlim(200, 8000)
    axes[0].set_ylabel("Parent-band demeaned SPL (dB)")
    axes[0].set_title("SUP-1 A–H single-entry module signatures")
    axes[0].legend(ncol=4, fontsize=8)
    for module in _MODULES:
        axes[1].plot(
            [row["window_id"] for row in inputs.candidates],
            module_plot_data["window_vectors"][module],
            marker="o",
            linewidth=1.0,
            label=module,
        )
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_ylabel("Module minus ENC-A signed mean (dB)")
    axes[1].set_xlabel("SUP-0 frozen window")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    for suffix in ("png", "svg"):
        fig.savefig(plot_dir / f"single_entry_module_signatures.{suffix}", dpi=220)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True, sharey=True)
    for axis, direction in zip(axes.flat, _DIRECTIONS, strict=True):
        delta = array_plot_data["delta_curves"][("primary", direction)]
        boot = array_plot_data["delta_boot"][("primary", direction)]
        low, high = np.percentile(boot, [2.5, 97.5], axis=0)
        axis.plot(frequency, delta, color="tab:blue", linewidth=1.2)
        axis.fill_between(frequency, low, high, color="tab:blue", alpha=0.18)
        axis.axhline(0.0, color="black", linewidth=0.7)
        axis.axvline(4000.0, color="grey", linestyle="--", linewidth=0.8)
        axis.set_xscale("log")
        axis.set_xlim(200, 8000)
        axis.set_title(f"{direction}° / {_V2_MAPPING[direction]}")
        axis.grid(alpha=0.2)
    fig.suptitle("SUP-2R HET-ABDF minus HOM-A parent-band-demeaned differences")
    fig.supxlabel("Frequency (Hz)")
    fig.supylabel("HET − HOM (dB); 95% cluster bootstrap CI")
    fig.tight_layout()
    for suffix in ("png", "svg"):
        fig.savefig(plot_dir / f"het_minus_hom_by_direction.{suffix}", dpi=220)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for axis, (direction, module) in zip(axes, ((90, "ENC-B"), (180, "ENC-D"), (270, "ENC-F")), strict=True):
        module_curve = _piecewise_demeaned_curve(
            module_plot_data["representatives"][module], parent_masks
        ) - _piecewise_demeaned_curve(
            module_plot_data["representatives"]["ENC-A"], parent_masks
        )
        array_curve = array_plot_data["delta_curves"][("primary", direction)]
        axis.plot(frequency, module_curve, label=f"{module} − ENC-A single entry", linewidth=1.1)
        axis.plot(frequency, array_curve, label=f"{direction}° HET − HOM", linewidth=1.1)
        axis.axhline(0.0, color="black", linewidth=0.7)
        axis.axvline(4000.0, color="grey", linestyle="--", linewidth=0.8)
        axis.set_xscale("log")
        axis.set_xlim(200, 8000)
        axis.set_title(f"Mapped comparison: {direction}° ↔ {module}")
        axis.legend(fontsize=8)
        axis.grid(alpha=0.2)
    fig.suptitle("Single-entry replacement signatures versus array differences")
    fig.supxlabel("Frequency (Hz)")
    fig.supylabel("Parent-band-demeaned difference (dB)")
    fig.tight_layout()
    for suffix in ("png", "svg"):
        fig.savefig(plot_dir / f"mapped_signature_comparison.{suffix}", dpi=220)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=False)
    for axis, band in zip(axes, ("primary", "secondary"), strict=True):
        band_candidates = [row for row in inputs.candidates if row["parent_band"] == band]
        labels = [row["window_id"] for row in band_candidates]
        x = np.arange(len(labels), dtype=float)
        offsets = np.linspace(-0.27, 0.27, len(_DIRECTIONS))
        for offset, direction in zip(offsets, _DIRECTIONS, strict=True):
            selected = [
                row for row in array_rows
                if row["direction_deg"] == direction and row["parent_band"] == band
            ]
            values = np.asarray([row["het_minus_hom_signed_mean_db"] for row in selected], dtype=float)
            low = values - np.asarray([row["signed_mean_ci95_low"] for row in selected], dtype=float)
            high = np.asarray([row["signed_mean_ci95_high"] for row in selected], dtype=float) - values
            axis.errorbar(x + offset, values, yerr=np.vstack([low, high]), fmt="o", capsize=2, label=f"{direction}°")
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.set_xticks(x, labels)
        axis.set_ylabel("Signed HET − HOM (dB)")
        axis.set_title(f"{band.capitalize()} frozen windows")
        axis.grid(alpha=0.2)
    axes[0].legend(ncol=4, fontsize=8)
    axes[1].set_xlabel("SUP-0 frozen window")
    fig.suptitle("Fixed-window effects with block/repeat cluster-bootstrap uncertainty")
    fig.tight_layout()
    for suffix in ("png", "svg"):
        fig.savefig(plot_dir / f"fixed_window_effects_uncertainty.{suffix}", dpi=220)
    plt.close(fig)


def _write_artifact_manifests(output: Path) -> int:
    artifacts = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"artifact_manifest.json", "SHA256SUMS"}:
            artifacts.append({
                "path": path.relative_to(output).as_posix(),
                "sha256": artifact_sha256(path),
                "bytes": path.stat().st_size,
            })
    _write_json(output / "artifact_manifest.json", {
        "analysis_format_version": "SUP-1+SUP-2R-existing-data-v1",
        "algorithm": "SHA-256",
        "artifacts": artifacts,
    })
    entries = [*artifacts, {
        "path": "artifact_manifest.json",
        "sha256": artifact_sha256(output / "artifact_manifest.json"),
        "bytes": (output / "artifact_manifest.json").stat().st_size,
    }]
    (output / "SHA256SUMS").write_text(
        "".join(f"{entry['sha256']}  {entry['path']}\n" for entry in entries),
        encoding="utf-8",
    )
    return len(artifacts)


def verify_sup1_sup2r_output_hashes(output_directory: str | Path) -> dict[str, Any]:
    root = Path(output_directory).resolve()
    manifest = _read_json(root / "artifact_manifest.json")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise SupplementalMechanismInputError("SUP-1/SUP-2R artifact manifest is empty")
    for entry in artifacts:
        path = (root / str(entry["path"])).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise SupplementalMechanismInputError("SUP-1/SUP-2R artifact escapes output") from exc
        if not path.is_file() or artifact_sha256(path) != entry["sha256"]:
            raise SupplementalMechanismInputError(f"SUP-1/SUP-2R artifact hash mismatch: {entry['path']}")
    sums = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator:
            raise SupplementalMechanismInputError("invalid SUP-1/SUP-2R SHA256SUMS")
        sums[relative] = digest
    manifest_sha = artifact_sha256(root / "artifact_manifest.json")
    if sums.get("artifact_manifest.json") != manifest_sha:
        raise SupplementalMechanismInputError("SUP-1/SUP-2R manifest hash is not bound")
    return {
        "all_match": True,
        "artifact_count": len(artifacts),
        "artifact_manifest_sha256": manifest_sha,
    }


def run_sup1_sup2r_reanalysis(
    *,
    formal3_directory: str | Path,
    formal4_directory: str | Path,
    formal5_directory: str | Path,
    sup0_directory: str | Path,
    sup1_directory: str | Path,
    output_directory: str | Path,
) -> SupplementalMechanismRunResult:
    """Run the existing-real-data-only SUP-1 library and SUP-2R reanalysis."""
    formal3 = Path(formal3_directory).resolve()
    formal4 = Path(formal4_directory).resolve()
    formal5 = Path(formal5_directory).resolve()
    sup0 = Path(sup0_directory).resolve()
    sup1 = Path(sup1_directory).resolve()
    output = Path(output_directory).resolve()
    inputs = _load_and_audit_inputs(
        formal3_directory=formal3,
        formal4_directory=formal4,
        formal5_directory=formal5,
        sup0_directory=sup0,
        sup1_directory=sup1,
    )
    parent_masks, window_masks = _candidate_masks(inputs)
    module_rows, module_plot_data = _analyse_module_library(
        inputs, parent_masks, window_masks
    )
    repeatability_by_module = {
        row["module_id"]: row for row in _read_csv(sup1 / "module_repeatability.csv")
    }
    for row in module_rows:
        repeatability = repeatability_by_module[row["module_id"]]
        row["module_primary_pairwise_rms_median_db"] = float(
            repeatability["primary_median_pairwise_rms_db"]
        )
        row["module_primary_pairwise_rms_max_db"] = float(
            repeatability["primary_max_pairwise_rms_db"]
        )
        row["module_repeatability_status"] = repeatability["repeatability_status"]
        row["module_outlier_sample_ids"] = repeatability["outlier_sample_ids"]
    array_rows, array_curve_rows, array_plot_data = _analyse_array_differences(
        inputs, parent_masks, window_masks
    )
    correspondence_rows = _analyse_correspondence(inputs, parent_masks, window_masks)
    consistency_rows = _direction_consistency_rows(inputs, array_plot_data)

    module_pair_authority = {
        (row["module_a"], row["module_b"]): row
        for row in _read_csv(sup1 / "module_pair_parent_band_effects.csv")
        if row["parent_band"] == "primary"
    }
    absolute_vectors = {
        module: np.asarray([
            float(row["absolute_parent_demeaned_signed_mean_db"])
            for row in module_rows if row["module_id"] == module
        ])
        for module in _MODULES
    }
    similarity_rows: list[dict[str, Any]] = []
    for left_index, left in enumerate(_MODULES):
        for right in _MODULES[left_index + 1:]:
            pearson, spearman, cosine = _safe_similarity(
                absolute_vectors[left], absolute_vectors[right]
            )
            authority = module_pair_authority[(left, right)]
            similarity_rows.append({
                "module_a": left,
                "module_b": right,
                "fixed_window_pearson_r": pearson,
                "fixed_window_spearman_r": spearman,
                "fixed_window_cosine_similarity": cosine,
                "primary_representative_demeaned_rms_db": float(authority["representative_demeaned_rms_db"]),
                "primary_effect_to_FORMAL_CONT_p95_ratio": float(authority["demeaned_effect_to_floor_ratio"]),
                "cross_repeat_pairs_above_floor": int(authority["cross_repeat_pairs_above_floor"]),
                "stable_above_floor": authority["stable_above_floor"] == "true",
                "interpretation": "similarity_is_descriptive_not_classification_or_causality",
            })

    formal4_summary = _read_json(formal4 / "analysis_summary.json")
    formal5_boundary = _read_json(formal5 / "final_claim_boundary.json")
    main_windows_by_direction: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for direction in _DIRECTIONS:
        main_windows_by_direction[str(direction)] = {}
        for band, limit in (("primary", 3), ("secondary", 3)):
            selected = sorted(
                (
                    row for row in array_rows
                    if row["direction_deg"] == direction and row["parent_band"] == band
                ),
                key=lambda row: float(row["rms_to_sup0_floor_ratio"]),
                reverse=True,
            )[:limit]
            main_windows_by_direction[str(direction)][band] = [
                {
                    "window_id": row["window_id"],
                    "rms_to_floor_ratio": row["rms_to_sup0_floor_ratio"],
                    "signed_mean_db": row["het_minus_hom_signed_mean_db"],
                    "rms_ci95_low_exceeds_floor": row["rms_ci95_low_exceeds_floor"],
                }
                for row in selected
            ]
    mapped_correspondence = [
        row for row in correspondence_rows
        if row["is_physical_position_mapping"]
        and row["window_scope"] == "primary_fixed_windows"
    ]
    estimable_mapped = [row for row in mapped_correspondence if row["direction_deg"] != 0]
    stable_mapped = [
        row for row in estimable_mapped
        if row["evidence_status"] == "stable_positive_pattern_correspondence"
        and row["sensitivity_evidence_status"] == "stable_positive_pattern_correspondence"
    ]
    target_row = max(
        (
            row for row in array_rows
            if row["direction_deg"] in (90, 180, 270) and row["parent_band"] == "primary"
        ),
        key=lambda row: float(row["rms_to_sup0_floor_ratio"]),
    )
    module_top_windows: dict[str, dict[str, list[str]]] = {}
    for module in _MODULES:
        selected = [row for row in module_rows if row["module_id"] == module]
        key = (
            (lambda row: abs(float(row["absolute_parent_demeaned_signed_mean_db"])))
            if module == "ENC-A"
            else (lambda row: float(row["versus_A_rms_to_floor_ratio"]))
        )
        module_top_windows[module] = {
            band: [
                row["window_id"]
                for row in sorted(
                    (item for item in selected if item["parent_band"] == band),
                    key=key,
                    reverse=True,
                )[:3]
            ]
            for band in ("primary", "secondary")
        }
    summary = {
        "status": "SUP-1_module_library_and_SUP-2R_existing_data_reanalysis_complete",
        "created_at": datetime.now().astimezone().isoformat(),
        "data_audit": inputs.audit,
        "analysis_scope": {
            "new_acquisition_performed": False,
            "HOM_A_reacquired": False,
            "HET_ABDF_reacquired": False,
            "HOM_A_reused_as": "U4SYM_AS01_B01_B02",
            "HET_ABDF_reused_as": "U4ENC_AS01_B03_B04",
            "SUP1_single_entry_measurements": 29,
            "FORMAL_AS01_ACTIVE_measurements": 48,
            "SUP0_fixed_windows": 12,
            "simulated_data_used": False,
            "classification_run": False,
            "final_test_read": False,
        },
        "FORMAL4_5_existing_results_quoted_not_repackaged_as_new": {
            "repeatability_floor": formal4_summary["repeatability_floor"],
            "G_demeaned_AS01_primary": formal4_summary["direction_effect"]["G_demeaned_AS01_primary"],
            "AS01_effect_to_floor_ratio": formal4_summary["configuration_effect"]["AS01_median_demeaned_to_floor_ratio"],
            "grouped_classification": formal4_summary["classification"],
            "disposition": formal5_boundary["disposition"],
            "hypothesis_decisions": formal5_boundary["hypothesis_decisions"],
            "scientifically_eligible": formal5_boundary["scientifically_eligible"],
        },
        "new_results": {
            "main_HET_minus_HOM_windows_by_direction": main_windows_by_direction,
            "module_top_fixed_windows": module_top_windows,
            "array_window_effect_count": len(array_rows),
            "array_windows_point_above_floor_count": sum(bool(row["point_effect_exceeds_floor"]) for row in array_rows),
            "array_windows_ci_low_above_floor_count": sum(bool(row["rms_ci95_low_exceeds_floor"]) for row in array_rows),
            "mapped_primary_correspondence_estimable_count": len(estimable_mapped),
            "mapped_primary_correspondence_stable_in_both_variants_count": len(stable_mapped),
            "mapped_primary_correspondence": mapped_correspondence,
            "direction_pair_consistency": consistency_rows,
        },
        "identifiability": {
            "frequency_localization_supported": True,
            "single_entry_to_array_correspondence_estimable_for_B_D_F": True,
            "A_at_0deg_replacement_signature": "not_estimable_A_minus_A_is_zero",
            "independent_four_position_contribution_identifiable": False,
            "module_contribution_percentages_allowed": False,
            "reason": "HET-ABDF changes three modules relative to HOM-A simultaneously; full-array observations do not isolate individual positions",
        },
        "minimal_SUP3_recommendation": {
            "needed_for_frequency_localization": False,
            "needed_for_individual_module_causal_attribution": True,
            "execute_in_this_run": False,
            "design": "one contemporaneous leave-one-module-out contrast only",
            "target_direction_deg": target_row["direction_deg"],
            "target_position_module": target_row["mapped_physical_module"],
            "target_window_id": target_row["window_id"],
            "contrast": f"HET-ABDF versus replace {target_row['mapped_physical_module']} at {target_row['direction_deg']}deg with ENC-A; hold other positions fixed",
            "minimum_future_measurements": "3 continuous repeats per condition for HET baseline and one leave-one-out condition (6 total), one target direction only",
            "not_a_current_acquisition_plan": True,
        },
        "claim_boundary": {
            "H1": "not_confirmed",
            "H0": "not_rejected",
            "U4ENC_proved_superior": False,
            "reliable_four_direction_classification_claim": False,
            "correlation_interpreted_as_causal_contribution": False,
            "FORMAL5_disposition_changed": False,
            "thresholds_changed": False,
            "algorithms_or_existing_schemas_changed": False,
            "ACTIVE_EXCLUDED_changed": False,
            "final_test_read": False,
        },
    }
    audit_rows = [
        {
            "authority": name,
            "verified_artifact_count": details["artifact_count"],
            "artifact_manifest_sha256": details["artifact_manifest_sha256"],
            "all_match": True,
            "final_test_read": False,
        }
        for name, details in inputs.audit["hash_verification"].items()
    ]
    run_manifest = {
        "analysis_format_version": "SUP-1+SUP-2R-existing-data-v1",
        "created_at": summary["created_at"],
        "input_directories": {
            "FORMAL3": str(formal3),
            "FORMAL4": str(formal4),
            "FORMAL5": str(formal5),
            "SUP0": str(sup0),
            "SUP1": str(sup1),
        },
        "physical_mapping": inputs.audit["physical_mapping"],
        "physical_mapping_authority": _V2_MAPPING_AUTHORITY,
        "bootstrap_iterations": _BOOTSTRAP_ITERATIONS,
        "bootstrap_random_state": _RANDOM_STATE,
        "frequency_points_resampled_as_independent_samples": False,
        "new_acquisition_performed": False,
        "classification_executed": False,
        "sample_selection_changed": False,
        "thresholds_changed": False,
        "existing_schema_changed": False,
        "final_test_read": False,
        "provenance": inputs.audit["provenance"],
    }

    staging = output.parent / f".{output.name}.staging-{datetime.now().strftime('%Y%m%dT%H%M%S%f')}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        _write_csv(staging / "data_audit.csv", audit_rows)
        _write_csv(staging / "module_window_features.csv", module_rows)
        _write_csv(staging / "module_similarity.csv", similarity_rows)
        _write_csv(staging / "het_hom_direction_window_effects.csv", array_rows)
        _write_csv(staging / "het_hom_direction_frequency_curves.csv", array_curve_rows)
        _write_csv(staging / "single_entry_array_correspondence.csv", correspondence_rows)
        _write_csv(staging / "direction_pattern_consistency.csv", consistency_rows)
        _write_json(staging / "input_audit.json", inputs.audit)
        _write_json(staging / "analysis_summary.json", summary)
        _write_json(staging / "run_manifest.json", run_manifest)
        _write_plots(
            staging, inputs, parent_masks, module_plot_data, array_plot_data, array_rows
        )
        artifact_count = _write_artifact_manifests(staging)
        verify_sup1_sup2r_output_hashes(staging)
        if output.exists():
            superseded = output.parent / f"_superseded_{output.name}_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
            output.replace(superseded)
        staging.replace(output)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    verification = verify_sup1_sup2r_output_hashes(output)
    return SupplementalMechanismRunResult(
        output_directory=output,
        sup1_measurement_count=29,
        formal_active_count=72,
        formal_as01_active_count=48,
        candidate_window_count=12,
        artifact_count=int(verification["artifact_count"]),
    )
