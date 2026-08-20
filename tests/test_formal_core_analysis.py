from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.formal_core_analysis import (
    Formal4InputError,
    band_masks,
    run_formal4_core_analysis,
    verify_formal3_authority,
    verify_formal4_output_hashes,
)
from acoustic_encoder.schemas import (
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
    artifact_sha256,
    save_feature_set,
)
from acoustic_encoder.version import (
    CONFIG_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    MEASUREMENT_SCHEMA_VERSION,
    PIPELINE_VERSION,
)


BLOCKS = {
    "B01": ("U4SYM", "AS01", "RP01", "S01"),
    "B02": ("U4SYM", "AS01", "RP02", "S01"),
    "B03": ("U4ENC", "AS01", "RP01", "S02"),
    "B04": ("U4ENC", "AS01", "RP02", "S02"),
    "B05": ("U4ENC", "AS02", "RP01", "S03"),
    "B07": ("U4SYM", "AS02", "RP01", "S04"),
}


def _csv(path: Path, rows: list[dict[str, object]], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _meta(sample_id: str, block: str, configuration: str, assembly: str,
          repos: str, session: str, direction: int, repeat: int) -> MeasurementMeta:
    return MeasurementMeta(
        sample_id=sample_id,
        pipeline_version=PIPELINE_VERSION,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        measurement_schema_version=MEASUREMENT_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        device_version="U4",
        configuration=configuration,
        angle_deg=float(direction),
        session_id=session,
        repeat_type="CONT",
        repeat_id=f"C{repeat:02d}",
        experiment_step="FORMAL-3",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=f"frozen/{sample_id}.txt",
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_ANALYSIS,
        source_sha256=hashlib.sha256(sample_id.encode()).hexdigest(),
        provenance_uri=f"formal3://{sample_id}",
        eligible_for_scientific_analysis=False,
        reposition_round_id=repos,
        assembly_id=assembly,
        acquisition_block_id=block,
        qc_status=QCStatus.WARNING,
    )


def _formal3_fixture(root: Path) -> Path:
    root.mkdir()
    feature_dir = root / "preprocessed" / "features"
    feature_dir.mkdir(parents=True)
    frequency = 200.0 * np.power(2.0, np.arange(256, dtype=float) / 48.0)
    valid = np.ones(256, dtype=bool)
    valid[0] = False
    names = tuple(f"spl_{value:.9f}_hz" for value in frequency)
    active: list[dict[str, object]] = []
    qc: list[dict[str, object]] = []
    index: list[dict[str, object]] = []
    for block_index, (block, identity) in enumerate(BLOCKS.items()):
        configuration, assembly, repos, session = identity
        for direction_index, direction in enumerate((0, 90, 180, 270)):
            for repeat in (1, 2, 3):
                sample_id = (
                    f"FORMAL3-{block}-{configuration}-{assembly}-"
                    f"D{direction:03d}-C{repeat:02d}"
                )
                x = np.linspace(0.0, 7.0, 256)
                shape_scale = 0.45 if configuration == "U4SYM" else 1.15
                values = (
                    70.0
                    + 1.8 * np.sin(x)
                    + shape_scale * np.sin(x * (1.0 + direction_index * 0.12) + direction_index)
                    + 0.14 * block_index * np.cos(0.8 * x)
                    + 0.025 * repeat * np.sin(2.1 * x + repeat)
                )
                # One deterministic FORMAL-3 flag; it remains ACTIVE.
                flagged = sample_id.endswith("B01-U4SYM-AS01-D000-C03")
                if flagged:
                    values += 0.45 * np.sin(3.7 * x)
                feature = FeatureSet(
                    sample_id=sample_id,
                    feature_schema_version=FEATURE_SCHEMA_VERSION,
                    feature_kind=FeatureKind.DENSE_RAW_SPL,
                    feature_names=names,
                    values=values,
                    valid_mask=valid,
                    units=tuple("dB SPL" for _ in values),
                    source_measurement_mode=MeasurementMode.REW_SWEEP,
                    source_representation=Representation.DENSE_SPECTRUM,
                    preprocessing_id="sha256:" + "1" * 64,
                    meta=_meta(sample_id, block, configuration, assembly, repos,
                               session, direction, repeat),
                    normalization_method="none",
                    source_magnitude_quantity="spl",
                    source_magnitude_reference="synthetic FORMAL-4 fixture",
                    source_phase_status=PhaseStatus.UNAVAILABLE,
                    source_qc_status=QCStatus.WARNING,
                    source_qc_eligible_for_downstream=True,
                )
                base = feature_dir / sample_id
                npz_path, json_path = save_feature_set(feature, base)
                group = f"{block}_{configuration}_{assembly}"
                active.append({
                    "sample_id": sample_id, "selection_status": "ACTIVE",
                    "analysis_included": "true", "group_id": group,
                    "block_id": block, "configuration": configuration,
                    "assembly_id": assembly, "direction_id": f"{direction:03d}",
                    "repeat_id": f"{repeat:02d}",
                })
                qc.append({
                    "sample_id": sample_id,
                    "curve_outlier_flag": str(flagged).lower(),
                    "structural_valid": "true", "qc_status": "warning",
                })
                index.append({
                    "sample_id": sample_id, "group_id": group,
                    "direction_id": f"{direction:03d}",
                    "feature_kind": "dense_raw_spl", "grid_point_count": 256,
                    "valid_point_count": 255,
                    "preprocessing_id": "sha256:" + "1" * 64,
                    "feature_npz": npz_path.relative_to(root).as_posix(),
                    "feature_json": json_path.relative_to(root).as_posix(),
                    "feature_npz_sha256": artifact_sha256(npz_path),
                    "feature_json_sha256": artifact_sha256(json_path),
                })
    excluded = [
        {"sample_id": f"EXCLUDED-{i:02d}", "selection_status": "EXCLUDED",
         "analysis_included": "false"}
        for i in range(19)
    ]
    _csv(root / "active_manifest.csv", active, tuple(active[0]))
    _csv(root / "excluded_manifest.csv", excluded, tuple(excluded[0]))
    _csv(root / "file_qc.csv", qc, tuple(qc[0]))
    _csv(root / "feature_index.csv", index, tuple(index[0]))
    run_manifest = {
        "schema_version": "formal3_real_import_qc_v1",
        "ready_for_formal_analysis": True,
        "preprocessed_feature_count": 72,
        "final_test_read": False,
        "input_zip": {"sha256": "cfbaa7a3c300b8443d934462386e9a5faad74d2b2cf0a50292d8c08423f7b4cb"},
        "selection": {"active_count": 72, "excluded_count": 19,
                      "automatic_selection_change_allowed": False,
                      "excluded_entered_features_statistics_training_or_results": False},
        "provenance": {"data_origin": "real_experiment",
                       "dataset_role": "research_analysis",
                       "run_purpose": "research_analysis",
                       "scientifically_eligible": False},
        "formal_preprocessing_contract": {
            "grid_type": "logarithmic", "points_per_octave": 48,
            "frequency_min_hz": 200.0, "frequency_max_hz": 8000.0,
            "primary_band_hz": [200.0, 4000.0],
            "secondary_band_hz": [4000.0, 8000.0],
            "smoothing_fraction_octave": "1/12",
        },
    }
    (root / "run_manifest.json").write_text(
        json.dumps(run_manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    managed = [
        root / "active_manifest.csv", root / "excluded_manifest.csv",
        root / "file_qc.csv", root / "feature_index.csv", root / "run_manifest.json",
        *sorted(feature_dir.glob("*")),
    ]
    artifacts = [
        {"path": path.relative_to(root).as_posix(), "sha256": artifact_sha256(path),
         "bytes": path.stat().st_size}
        for path in managed
    ]
    (root / "artifact_manifest.json").write_text(
        json.dumps({"schema_version": "formal3_artifact_manifest_v1",
                    "algorithm": "SHA-256", "artifacts": artifacts},
                   sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sums = artifacts + [{
        "path": "artifact_manifest.json",
        "sha256": artifact_sha256(root / "artifact_manifest.json"),
    }]
    (root / "SHA256SUMS").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in sums),
        encoding="utf-8",
    )
    return root


def test_authority_locks_formal3_counts_contract_and_hashes(tmp_path: Path) -> None:
    source = _formal3_fixture(tmp_path / "formal3")
    authority = verify_formal3_authority(source)

    assert authority.active_count == 72
    assert authority.excluded_count == 19
    assert authority.feature_count == 72
    assert authority.common_valid_point_count == 255
    assert authority.outlier_sample_count == 1

    with (source / "feature_index.csv").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    with pytest.raises(Formal4InputError, match="hash mismatch"):
        verify_formal3_authority(source)


def test_band_masks_use_actual_valid_grid_without_extrapolating_200_hz() -> None:
    frequency = 200.0 * np.power(2.0, np.arange(256) / 48.0)
    valid = np.ones(256, dtype=bool)
    valid[0] = False

    masks = band_masks(frequency, valid)

    assert not masks["primary"][0]
    assert np.all(frequency[masks["primary"]] > 200.0)
    assert np.all(frequency[masks["primary"]] <= 4000.0)
    assert np.all(frequency[masks["secondary"]] >= 4000.0)
    assert np.count_nonzero(masks["full"]) == 255


def test_formal4_run_is_block_grouped_audited_and_non_overwriting(tmp_path: Path) -> None:
    source = _formal3_fixture(tmp_path / "formal3")
    output = tmp_path / "formal4"
    active_hash = artifact_sha256(source / "active_manifest.csv")

    result = run_formal4_core_analysis(
        source, output, source_commit="a" * 40, created_at="2026-08-20T18:00:00+01:00",
        bootstrap_iterations=60, permutation_iterations=24,
    )

    assert result.active_count == 72
    assert result.outlier_count == 1
    assert artifact_sha256(source / "active_manifest.csv") == active_hash
    assert verify_formal4_output_hashes(output)["all_match"] is True
    assert {
        "repeatability_by_cell.csv", "repeatability_frequency.csv",
        "repeatability_summary.csv", "direction_pairwise_effects.csv",
        "direction_effect_summary.csv", "direction_gain_summary.csv",
        "direction_gain_contrasts.csv", "configuration_effects.csv",
        "configuration_difference_curves.csv", "assembly_set_effects.csv",
        "assembly_set_difference_curves.csv", "outlier_sensitivity.csv",
        "grouped_validation_metrics.csv", "grouped_validation_predictions.csv",
        "analysis_summary.json", "run_manifest.json", "artifact_manifest.json",
        "SHA256SUMS",
    } <= {path.name for path in output.iterdir() if path.is_file()}
    assert {
        "block_direction_B01.png", "block_direction_B02.png",
        "block_direction_B03.png", "block_direction_B04.png",
        "block_direction_B05.png", "block_direction_B07.png",
        "repeatability_frequency.png", "direction_pairwise_heatmap.png",
        "configuration_difference.png", "effect_to_repeatability_ratio.png",
        "outlier_sensitivity.png", "grouped_validation_confusion_matrix.png",
    } <= {path.name for path in (output / "plots").iterdir()}
    summary = json.loads((output / "analysis_summary.json").read_text(encoding="utf-8"))
    assert summary["provenance"]["scientifically_eligible"] is False
    assert summary["final_test_read"] is False
    assert summary["selection"]["active_count"] == 72
    assert summary["selection"]["excluded_count"] == 19
    assert summary["outlier_policy"]["active_manifest_modified"] is False
    assert summary["classification"]["continuous_repeats_crossed_folds"] is False
    contrast = summary["direction_effect"]["G_demeaned_AS01_primary"]
    assert len(contrast["U4ENC_minus_U4SYM_ci95"]) == 2

    with (output / "grouped_validation_predictions.csv").open(encoding="utf-8", newline="") as handle:
        predictions = list(csv.DictReader(handle))
    assert predictions
    assert all(row["test_block_id"] not in row["train_block_ids"].split(";") for row in predictions)

    metrics = list(csv.DictReader((output / "grouped_validation_metrics.csv").open(encoding="utf-8")))
    assert any(row["scope_id"] == "U4ENC_AS02" and row["status"] == "not_estimable" for row in metrics)
    assert any(row["scope_id"] == "U4SYM_AS01" and row["status"] == "estimable_limited" for row in metrics)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_formal4_core_analysis(
            source, output, source_commit="a" * 40,
            created_at="2026-08-20T18:00:01+01:00",
            bootstrap_iterations=10, permutation_iterations=4,
        )


def test_sensitivity_never_rewrites_frozen_selection_and_reports_conclusion_change(
    tmp_path: Path,
) -> None:
    source = _formal3_fixture(tmp_path / "formal3")
    output = tmp_path / "formal4"
    before = (source / "active_manifest.csv").read_bytes()
    run_formal4_core_analysis(
        source, output, source_commit="b" * 40,
        created_at="2026-08-20T18:00:00+01:00",
        bootstrap_iterations=40, permutation_iterations=12,
    )

    rows = list(csv.DictReader((output / "outlier_sensitivity.csv").open(encoding="utf-8")))
    assert rows
    assert {row["analysis_variant"] for row in rows} == {
        "primary_all_active", "sensitivity_without_flagged_curves"
    }
    assert all(row["selection_manifest_changed"] == "false" for row in rows)
    assert (source / "active_manifest.csv").read_bytes() == before


def test_output_hash_tampering_fails_closed(tmp_path: Path) -> None:
    source = _formal3_fixture(tmp_path / "formal3")
    output = tmp_path / "formal4"
    run_formal4_core_analysis(
        source, output, source_commit="c" * 40,
        created_at="2026-08-20T18:00:00+01:00",
        bootstrap_iterations=20, permutation_iterations=8,
    )
    with (output / "repeatability_summary.csv").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    with pytest.raises(Formal4InputError, match="hash mismatch"):
        verify_formal4_output_hashes(output)
