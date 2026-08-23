"""SUP-0 frequency localization from the immutable FORMAL-3 ACTIVE corpus.

The analysis deliberately avoids pointwise significance tests and post-hoc peak
selection.  It partitions each frozen parent band into deterministic 16-bin
windows on the 48-points-per-octave FORMAL-1 grid, then compares block-aware
direction and configuration effects with the same-window CONT p95 floor.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import itertools
import json
import math
from pathlib import Path
import shutil
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .formal_core_analysis import (
    FORMAL3_ZIP_SHA256,
    Formal4InputError,
    Formal4Sample,
    _AS01_BLOCKS,
    _DIRECTIONS,
    _cell_medians,
    _cell_samples,
    _load_samples,
    _read_csv,
    _write_csv,
    _write_json,
    band_masks,
    verify_formal3_authority,
    verify_formal4_output_hashes,
)
from .schemas import artifact_sha256
from .version import SCHEMA_VERSION_QUARTET


SUP0_SCHEMA_VERSION = "sup0_frequency_localization_v1"
SUP0_WINDOW_POINTS = 16
SUP0_MIN_FINAL_WINDOW_POINTS = 8
SUP0_DIRECTION_PAIR_MINIMUM = 4
SUP0_CONFIGURATION_DIRECTION_MINIMUM = 3


@dataclass(frozen=True, slots=True)
class FrequencyWindow:
    window_id: str
    parent_band: str
    ordinal: int
    indices: NDArray[np.int64]
    frequency_low_hz: float
    frequency_high_hz: float

    @property
    def point_count(self) -> int:
        return int(self.indices.size)


@dataclass(frozen=True, slots=True)
class Sup0RunResult:
    output_directory: Path
    active_count: int
    excluded_count: int
    outlier_count: int
    candidate_band_count: int
    artifact_count: int


def build_frequency_windows(
    frequency_hz: NDArray[np.float64],
    valid_mask: NDArray[np.bool_],
) -> tuple[FrequencyWindow, ...]:
    """Partition frozen primary/secondary bands into deterministic grid windows."""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    valid = np.asarray(valid_mask, dtype=np.bool_)
    masks = band_masks(frequency, valid)
    windows: list[FrequencyWindow] = []
    for parent_band, prefix in (("primary", "P"), ("secondary", "S")):
        band_indices = np.flatnonzero(masks[parent_band])
        chunks = [
            band_indices[start : start + SUP0_WINDOW_POINTS]
            for start in range(0, band_indices.size, SUP0_WINDOW_POINTS)
        ]
        if len(chunks) > 1 and chunks[-1].size < SUP0_MIN_FINAL_WINDOW_POINTS:
            chunks[-2] = np.concatenate((chunks[-2], chunks[-1]))
            chunks.pop()
        if not chunks or any(chunk.size < SUP0_MIN_FINAL_WINDOW_POINTS for chunk in chunks):
            raise Formal4InputError(f"{parent_band} cannot be partitioned into auditable windows")
        if not np.array_equal(np.concatenate(chunks), band_indices):
            raise Formal4InputError(f"{parent_band} window partition is incomplete")
        for ordinal, indices in enumerate(chunks, start=1):
            windows.append(FrequencyWindow(
                window_id=f"{prefix}{ordinal:02d}",
                parent_band=parent_band,
                ordinal=ordinal,
                indices=np.asarray(indices, dtype=np.int64),
                frequency_low_hz=float(frequency[indices[0]]),
                frequency_high_hz=float(frequency[indices[-1]]),
            ))
    return tuple(windows)


def _rms_delta(left: NDArray[np.float64], right: NDArray[np.float64]) -> float:
    return float(np.sqrt(np.mean(np.square(left - right))))


def _parent_demeaned(
    values: NDArray[np.float64], parent_mask: NDArray[np.bool_]
) -> NDArray[np.float64]:
    return values - float(np.mean(values[parent_mask]))


def _repeatability_values(
    cells: Mapping[tuple[str, int], Sequence[Formal4Sample]],
    indices: NDArray[np.int64],
) -> NDArray[np.float64]:
    values: list[float] = []
    for group in cells.values():
        for left, right in itertools.combinations(group, 2):
            values.append(_rms_delta(left.values[indices], right.values[indices]))
    result = np.asarray(values, dtype=np.float64)
    if result.size == 0 or not np.all(np.isfinite(result)):
        raise Formal4InputError("SUP-0 repeatability floor is empty or non-finite")
    return result


def _metric_rows_for_scope(
    samples: Sequence[Formal4Sample],
    *,
    include_flagged: bool,
    scopes: Sequence[FrequencyWindow],
    frequency: NDArray[np.float64],
    valid_mask: NDArray[np.bool_],
    scope_kind: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    variant = "primary_all_active" if include_flagged else "sensitivity_without_flagged_curves"
    cells = _cell_samples(samples, include_flagged=include_flagged)
    medians = _cell_medians(cells)
    parent_masks = band_masks(frequency, valid_mask)
    summary_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    configuration_rows: list[dict[str, Any]] = []

    for scope in scopes:
        indices = scope.indices
        parent_mask = parent_masks[scope.parent_band]
        repeatability = _repeatability_values(cells, indices)
        q25, q75 = np.percentile(repeatability, [25, 75])
        floor_p95 = float(np.percentile(repeatability, 95))
        row: dict[str, Any] = {
            "analysis_variant": variant,
            "scope_kind": scope_kind,
            "parent_band": scope.parent_band,
            "window_id": scope.window_id,
            "frequency_low_hz": scope.frequency_low_hz,
            "frequency_high_hz": scope.frequency_high_hz,
            "frequency_geometric_center_hz": math.sqrt(
                scope.frequency_low_hz * scope.frequency_high_hz
            ),
            "point_count": scope.point_count,
            "octave_span": math.log2(scope.frequency_high_hz / scope.frequency_low_hz),
            "cont_pair_count": int(repeatability.size),
            "cont_median_rms_db": float(np.median(repeatability)),
            "cont_iqr_rms_db": float(q75 - q25),
            "cont_p95_rms_db": floor_p95,
        }

        for configuration in ("U4SYM", "U4ENC"):
            blocks = _AS01_BLOCKS[configuration]
            block_medians: list[float] = []
            block_counts: list[int] = []
            for block in blocks:
                effects: list[float] = []
                for direction_a, direction_b in itertools.combinations(_DIRECTIONS, 2):
                    left = _parent_demeaned(medians[(block, direction_a)], parent_mask)
                    right = _parent_demeaned(medians[(block, direction_b)], parent_mask)
                    effect = _rms_delta(left[indices], right[indices])
                    effects.append(effect)
                    pair_rows.append({
                        "analysis_variant": variant,
                        "scope_kind": scope_kind,
                        "parent_band": scope.parent_band,
                        "window_id": scope.window_id,
                        "frequency_low_hz": scope.frequency_low_hz,
                        "frequency_high_hz": scope.frequency_high_hz,
                        "configuration": configuration,
                        "block_id": block,
                        "direction_a_deg": direction_a,
                        "direction_b_deg": direction_b,
                        "demeaned_rms_db": effect,
                        "cont_p95_rms_db": floor_p95,
                        "effect_to_floor_ratio": effect / floor_p95,
                        "exceeds_floor": effect > floor_p95,
                    })
                block_median = float(np.median(effects))
                block_count = sum(effect > floor_p95 for effect in effects)
                block_medians.append(block_median)
                block_counts.append(block_count)
            prefix = configuration.lower()
            row[f"{prefix}_block_1_id"] = blocks[0]
            row[f"{prefix}_block_1_median_direction_rms_db"] = block_medians[0]
            row[f"{prefix}_block_1_pairs_above_floor"] = block_counts[0]
            row[f"{prefix}_block_2_id"] = blocks[1]
            row[f"{prefix}_block_2_median_direction_rms_db"] = block_medians[1]
            row[f"{prefix}_block_2_pairs_above_floor"] = block_counts[1]
            row[f"{prefix}_minimum_block_median_to_floor_ratio"] = (
                min(block_medians) / floor_p95
            )
            row[f"{prefix}_direction_rule_pass"] = (
                min(block_counts) >= SUP0_DIRECTION_PAIR_MINIMUM
                and min(block_medians) > floor_p95
            )

        representative: dict[tuple[str, int], NDArray[np.float64]] = {}
        for configuration in ("U4SYM", "U4ENC"):
            blocks = _AS01_BLOCKS[configuration]
            for direction in _DIRECTIONS:
                curve = np.median(
                    np.vstack([medians[(block, direction)] for block in blocks]), axis=0
                )
                representative[(configuration, direction)] = _parent_demeaned(
                    curve, parent_mask
                )
        configuration_effects: list[float] = []
        for direction in _DIRECTIONS:
            effect = _rms_delta(
                representative[("U4SYM", direction)][indices],
                representative[("U4ENC", direction)][indices],
            )
            configuration_effects.append(effect)
            configuration_rows.append({
                "analysis_variant": variant,
                "scope_kind": scope_kind,
                "parent_band": scope.parent_band,
                "window_id": scope.window_id,
                "frequency_low_hz": scope.frequency_low_hz,
                "frequency_high_hz": scope.frequency_high_hz,
                "direction_deg": direction,
                "demeaned_rms_db": effect,
                "cont_p95_rms_db": floor_p95,
                "effect_to_floor_ratio": effect / floor_p95,
                "exceeds_floor": effect > floor_p95,
            })
        configuration_median = float(np.median(configuration_effects))
        configuration_count = sum(effect > floor_p95 for effect in configuration_effects)
        row.update({
            "configuration_median_demeaned_rms_db": configuration_median,
            "configuration_median_to_floor_ratio": configuration_median / floor_p95,
            "configuration_directions_above_floor": configuration_count,
            "configuration_rule_pass": (
                configuration_count >= SUP0_CONFIGURATION_DIRECTION_MINIMUM
                and configuration_median > floor_p95
            ),
        })
        summary_rows.append(row)
    return summary_rows, pair_rows, configuration_rows


def _whole_band_scopes(
    frequency: NDArray[np.float64], valid_mask: NDArray[np.bool_]
) -> tuple[FrequencyWindow, ...]:
    masks = band_masks(frequency, valid_mask)
    result: list[FrequencyWindow] = []
    for ordinal, band in enumerate(("primary", "secondary"), start=1):
        indices = np.flatnonzero(masks[band])
        result.append(FrequencyWindow(
            window_id=band,
            parent_band=band,
            ordinal=ordinal,
            indices=indices,
            frequency_low_hz=float(frequency[indices[0]]),
            frequency_high_hz=float(frequency[indices[-1]]),
        ))
    return tuple(result)


def _candidate_rows(
    primary_rows: Sequence[Mapping[str, Any]],
    sensitivity_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    sensitivity = {str(row["window_id"]): row for row in sensitivity_rows}
    candidates: list[dict[str, Any]] = []
    for row in primary_rows:
        match = sensitivity[str(row["window_id"])]
        direction = bool(row["u4enc_direction_rule_pass"]) and bool(
            match["u4enc_direction_rule_pass"]
        )
        configuration = bool(row["configuration_rule_pass"]) and bool(
            match["configuration_rule_pass"]
        )
        if not (direction or configuration):
            continue
        reasons = []
        if direction:
            reasons.append("u4enc_direction_stable_across_both_AS01_REPOS")
        if configuration:
            reasons.append("as01_configuration_stable_across_at_least_3_directions")
        candidates.append({
            "candidate_id": f"SUP0-{row['window_id']}",
            "parent_band": row["parent_band"],
            "window_id": row["window_id"],
            "frequency_low_hz": row["frequency_low_hz"],
            "frequency_high_hz": row["frequency_high_hz"],
            "point_count": row["point_count"],
            "freeze_for_SUP1_to_SUP4": True,
            "freeze_reason": reasons,
            "primary_cont_p95_rms_db": row["cont_p95_rms_db"],
            "sensitivity_cont_p95_rms_db": match["cont_p95_rms_db"],
            "primary_u4enc_min_direction_to_floor_ratio": row[
                "u4enc_minimum_block_median_to_floor_ratio"
            ],
            "sensitivity_u4enc_min_direction_to_floor_ratio": match[
                "u4enc_minimum_block_median_to_floor_ratio"
            ],
            "primary_configuration_median_to_floor_ratio": row[
                "configuration_median_to_floor_ratio"
            ],
            "sensitivity_configuration_median_to_floor_ratio": match[
                "configuration_median_to_floor_ratio"
            ],
            "selection_is_union_without_top_n_ranking": True,
        })
    return candidates


def _verify_formal4_headlines(
    formal4_directory: Path, band_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    verification = verify_formal4_output_hashes(formal4_directory)
    frozen = {
        row["band_id"]: row
        for row in _read_csv(formal4_directory / "repeatability_summary.csv")
        if row["band_id"] in {"primary", "secondary"}
    }
    primary = {
        str(row["parent_band"]): row
        for row in band_rows
        if row["analysis_variant"] == "primary_all_active"
    }
    for band in ("primary", "secondary"):
        expected = float(frozen[band]["p95_pairwise_rms_db"])
        actual = float(primary[band]["cont_p95_rms_db"])
        if not np.isclose(actual, expected, rtol=0.0, atol=1e-12):
            raise Formal4InputError(
                f"SUP-0 {band} CONT p95 does not reproduce FORMAL-4: {actual} != {expected}"
            )
    return {
        "all_hashes_match": True,
        "artifact_count": verification["artifact_count"],
        "artifact_manifest_sha256": verification["artifact_manifest_sha256"],
        "repeatability_p95_reproduced": True,
    }


def _write_plot(
    output: Path,
    primary_rows: Sequence[Mapping[str, Any]],
    candidate_ids: set[str],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = sorted(primary_rows, key=lambda row: float(row["frequency_low_hz"]))
    x = np.asarray([row["frequency_geometric_center_hz"] for row in rows], dtype=float)
    enc = np.asarray(
        [row["u4enc_minimum_block_median_to_floor_ratio"] for row in rows], dtype=float
    )
    sym = np.asarray(
        [row["u4sym_minimum_block_median_to_floor_ratio"] for row in rows], dtype=float
    )
    config = np.asarray(
        [row["configuration_median_to_floor_ratio"] for row in rows], dtype=float
    )
    floor = np.asarray([row["cont_p95_rms_db"] for row in rows], dtype=float)
    selected = np.asarray([str(row["window_id"]) in candidate_ids for row in rows])

    fig, axes = plt.subplots(2, 1, figsize=(10.5, 7.2), sharex=True)
    axes[0].plot(x, enc, marker="o", label="U4ENC direction: min AS01 block median / floor")
    axes[0].plot(x, sym, marker="s", label="U4SYM residual direction: min block median / floor")
    axes[0].plot(x, config, marker="^", label="AS01 configuration median / floor")
    axes[0].scatter(x[selected], config[selected], s=100, facecolors="none", edgecolors="black",
                    linewidths=1.4, label="Frozen candidate window")
    axes[0].axhline(1.0, color="black", linestyle="--", linewidth=1)
    axes[0].set_ylabel("Effect / same-window CONT p95")
    axes[0].set_title("SUP-0 fixed-window frequency localization")
    axes[0].grid(alpha=0.25)
    axes[0].legend(fontsize=8, ncol=2)

    axes[1].plot(x, floor, color="#7b2cbf", marker="o")
    axes[1].set_ylabel("CONT p95 RMS (dB)")
    axes[1].set_xlabel("Frequency (Hz, logarithmic scale)")
    axes[1].grid(alpha=0.25)
    for axis in axes:
        axis.set_xscale("log")
        axis.axvline(4000.0, color="#666666", linestyle=":", linewidth=1)
    fig.tight_layout()
    plot_dir = output / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_dir / "frequency_localization.png", dpi=200)
    fig.savefig(plot_dir / "frequency_localization.svg")
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
        "schema_version": "sup0_artifact_manifest_v1",
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


def verify_sup0_output_hashes(output_directory: str | Path) -> dict[str, Any]:
    root = Path(output_directory).resolve()
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise Formal4InputError("SUP-0 artifact manifest is empty")
    sums: dict[str, str] = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator:
            raise Formal4InputError("invalid SUP-0 SHA256SUMS line")
        sums[relative] = digest
    for entry in artifacts:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise Formal4InputError("SUP-0 artifact path escapes output") from exc
        if not path.is_file() or artifact_sha256(path) != entry["sha256"]:
            raise Formal4InputError(f"SUP-0 artifact hash mismatch: {relative}")
        if sums.get(relative) != entry["sha256"]:
            raise Formal4InputError(f"SUP-0 SHA256SUMS mismatch: {relative}")
    manifest_hash = artifact_sha256(root / "artifact_manifest.json")
    if sums.get("artifact_manifest.json") != manifest_hash:
        raise Formal4InputError("SUP-0 manifest hash is not bound by SHA256SUMS")
    return {
        "all_match": True,
        "artifact_count": len(artifacts),
        "artifact_manifest_sha256": manifest_hash,
    }


def run_sup0_frequency_localization(
    formal3_directory: str | Path,
    formal4_directory: str | Path,
    output_directory: str | Path,
    *,
    source_commit: str,
    created_at: str | datetime,
    source_worktree_clean: bool,
) -> Sup0RunResult:
    """Run SUP-0 without raw-data scans or changes to frozen selection."""
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise Formal4InputError("source_commit must be a full lowercase Git SHA")
    timestamp = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)
    try:
        parsed_time = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise Formal4InputError("created_at must be ISO-8601") from exc
    if parsed_time.tzinfo is None:
        raise Formal4InputError("created_at must include timezone")

    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing SUP-0 output: {output}")
    authority = verify_formal3_authority(formal3_directory)
    samples = _load_samples(authority.input_directory)
    formal4 = Path(formal4_directory).resolve()
    first = samples[0]
    windows = build_frequency_windows(first.frequency_hz, first.valid_mask)
    whole_bands = _whole_band_scopes(first.frequency_hz, first.valid_mask)

    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        raise FileExistsError(f"refusing to overwrite existing SUP-0 staging output: {staging}")
    staging.mkdir(parents=True)
    try:
        window_primary, pair_primary, config_primary = _metric_rows_for_scope(
            samples, include_flagged=True, scopes=windows, frequency=first.frequency_hz,
            valid_mask=first.valid_mask, scope_kind="fixed_16_bin_window",
        )
        window_sensitivity, pair_sensitivity, config_sensitivity = _metric_rows_for_scope(
            samples, include_flagged=False, scopes=windows, frequency=first.frequency_hz,
            valid_mask=first.valid_mask, scope_kind="fixed_16_bin_window",
        )
        band_primary, band_pair_primary, band_config_primary = _metric_rows_for_scope(
            samples, include_flagged=True, scopes=whole_bands, frequency=first.frequency_hz,
            valid_mask=first.valid_mask, scope_kind="frozen_parent_band",
        )
        band_sensitivity, band_pair_sensitivity, band_config_sensitivity = _metric_rows_for_scope(
            samples, include_flagged=False, scopes=whole_bands, frequency=first.frequency_hz,
            valid_mask=first.valid_mask, scope_kind="frozen_parent_band",
        )
        formal4_verification = _verify_formal4_headlines(
            formal4, [*band_primary, *band_sensitivity]
        )
        candidates = _candidate_rows(window_primary, window_sensitivity)

        metric_rows = [*window_primary, *window_sensitivity]
        band_rows = [*band_primary, *band_sensitivity]
        direction_rows = [
            *pair_primary, *pair_sensitivity, *band_pair_primary, *band_pair_sensitivity
        ]
        configuration_rows = [
            *config_primary, *config_sensitivity, *band_config_primary, *band_config_sensitivity
        ]
        _write_csv(staging / "frequency_window_metrics.csv", metric_rows, tuple(metric_rows[0]))
        _write_csv(staging / "parent_band_metrics.csv", band_rows, tuple(band_rows[0]))
        _write_csv(
            staging / "direction_pair_effects.csv", direction_rows, tuple(direction_rows[0])
        )
        _write_csv(
            staging / "configuration_direction_effects.csv",
            configuration_rows,
            tuple(configuration_rows[0]),
        )
        candidate_fields = (
            "candidate_id", "parent_band", "window_id", "frequency_low_hz",
            "frequency_high_hz", "point_count", "freeze_for_SUP1_to_SUP4",
            "freeze_reason", "primary_cont_p95_rms_db", "sensitivity_cont_p95_rms_db",
            "primary_u4enc_min_direction_to_floor_ratio",
            "sensitivity_u4enc_min_direction_to_floor_ratio",
            "primary_configuration_median_to_floor_ratio",
            "sensitivity_configuration_median_to_floor_ratio",
            "selection_is_union_without_top_n_ranking",
        )
        _write_csv(staging / "candidate_bands.csv", candidates, candidate_fields)

        candidate_payload = [{
            "candidate_id": row["candidate_id"],
            "parent_band": row["parent_band"],
            "frequency_hz": [row["frequency_low_hz"], row["frequency_high_hz"]],
            "reason": row["freeze_reason"],
        } for row in candidates]
        band_summary = {
            str(row["parent_band"]): {
                "cont_median_rms_db": row["cont_median_rms_db"],
                "cont_iqr_rms_db": row["cont_iqr_rms_db"],
                "cont_p95_rms_db": row["cont_p95_rms_db"],
                "u4sym_minimum_block_median_to_floor_ratio": row[
                    "u4sym_minimum_block_median_to_floor_ratio"
                ],
                "u4enc_minimum_block_median_to_floor_ratio": row[
                    "u4enc_minimum_block_median_to_floor_ratio"
                ],
                "configuration_median_to_floor_ratio": row[
                    "configuration_median_to_floor_ratio"
                ],
            }
            for row in band_primary
        }
        summary = {
            "schema_version": SUP0_SCHEMA_VERSION,
            "created_at": timestamp,
            "status": "SUP-0_frozen",
            "selection": {
                "active_count": 72,
                "excluded_count": 19,
                "flagged_active_count": authority.outlier_sample_count,
                "primary_uses_all_ACTIVE": True,
                "selection_manifest_changed": False,
                "excluded_entered_analysis": False,
            },
            "preprocessing": {
                "grid": "FORMAL-1 logarithmic 48 points per octave",
                "smoothing": "FORMAL-1 1/12-octave dB smoothing",
                "primary_band_hz": [200.0, 4000.0],
                "secondary_band_hz": [4000.0, 8000.0],
                "valid_points": 255,
                "unsupported_200_hz_endpoint_extrapolated": False,
            },
            "localization_rule": {
                "window_points": SUP0_WINDOW_POINTS,
                "minimum_final_window_points": SUP0_MIN_FINAL_WINDOW_POINTS,
                "window_selection": "all fixed windows evaluated; no top-N or peak picking",
                "normalization": "demean each robust curve over its frozen parent band before window RMS",
                "floor": "same-window pooled CONT pairwise raw RMS p95",
                "u4enc_direction_pass": (
                    "at least 4 of 6 direction pairs above floor in each AS01 REPOS block "
                    "and each block median effect above floor"
                ),
                "configuration_pass": (
                    "at least 3 of 4 AS01 direction-specific configuration effects above floor "
                    "and their median above floor"
                ),
                "sensitivity_gate": "rule must pass with all ACTIVE and with flagged ACTIVE omitted",
                "candidate_union": "U4ENC direction pass OR AS01 configuration pass",
                "pointwise_significance_tests": False,
            },
            "parent_band_results": band_summary,
            "frozen_candidate_count": len(candidates),
            "frozen_candidates": candidate_payload,
            "formal4_verification": formal4_verification,
            "provenance": {
                "data_origin": "real_experiment",
                "dataset_role": "supplemental_development_analysis",
                "run_purpose": "SUP-0_frequency_localization_and_freeze",
                "scientifically_eligible": False,
            },
            "claim_boundary": {
                "existing_FORMAL5_disposition_changed": False,
                "candidate_bands_are_confirmatory_evidence": False,
                "allowed_use": "pre-frozen descriptive windows for SUP-1 through SUP-4",
            },
            "final_test_read": False,
        }
        _write_json(staging / "analysis_summary.json", summary)
        _write_json(staging / "run_manifest.json", {
            "schema_version": SUP0_SCHEMA_VERSION,
            "created_at": timestamp,
            "source_commit": source_commit,
            "source_worktree_clean": source_worktree_clean,
            **SCHEMA_VERSION_QUARTET,
            "input": {
                "formal3_directory": str(authority.input_directory),
                "formal3_run_manifest_sha256": authority.run_manifest_sha256,
                "formal3_artifact_manifest_sha256": authority.artifact_manifest_sha256,
                "formal3_verified_artifact_count": authority.input_artifact_count,
                "formal3_zip_sha256": FORMAL3_ZIP_SHA256,
                "formal4_directory": str(formal4),
                "formal4_artifact_manifest_sha256": formal4_verification[
                    "artifact_manifest_sha256"
                ],
            },
            "analysis": summary["localization_rule"],
            "selection": summary["selection"],
            "provenance": summary["provenance"],
            "raw_directory_scanned": False,
            "raw_txt_reimported": False,
            "active_excluded_selection_changed": False,
            "final_test_read": False,
        })
        _write_plot(
            staging, window_primary, {str(row["window_id"]) for row in candidates}
        )
        artifact_count = _write_artifact_manifests(staging)
        verification = verify_sup0_output_hashes(staging)
        if verification["artifact_count"] != artifact_count:
            raise Formal4InputError("SUP-0 artifact verification count mismatch")
        staging.rename(output)
        return Sup0RunResult(
            output_directory=output,
            active_count=72,
            excluded_count=19,
            outlier_count=authority.outlier_sample_count,
            candidate_band_count=len(candidates),
            artifact_count=artifact_count,
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
