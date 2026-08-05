from __future__ import annotations

from pathlib import Path

import pytest

from acoustic_encoder.dataset_quality_outputs import (
    load_dataset_quality_bundle,
    write_dataset_quality_outputs,
)
from acoustic_encoder.schemas import artifact_sha256
from test_dataset_quality_control import _config, _measurement, _scope


def _result_and_scope():
    pairs = (
        _measurement("output-cont-01", repeat_id="R01"),
        _measurement("output-cont-02", repeat_id="R02"),
    )
    scope = _scope(("output-cont-01", "output-cont-02"))
    from acoustic_encoder.dataset_quality_control import evaluate_dataset_quality

    result = evaluate_dataset_quality(
        tuple(item[0] for item in pairs),
        tuple(item[1] for item in pairs),
        scope,
        _config(),
    )
    return result, scope


def test_dataset_quality_bundle_is_hash_audited_and_round_trips(tmp_path: Path) -> None:
    result, scope = _result_and_scope()
    input_path = tmp_path / "explicit-input.bin"
    input_path.write_bytes(b"immutable explicit input")
    output = tmp_path / "dataset_qc"

    paths = write_dataset_quality_outputs(
        result,
        scope,
        _config(),
        output,
        input_artifacts=(
            {
                "sample_id": "output-cont-01",
                "artifact_role": "feature_npz",
                "path": input_path.as_posix(),
                "sha256": artifact_sha256(input_path),
            },
        ),
        git_commit="9ec8cfec3c6b4a8cb29fcf0317d500b13b071e85",
        random_state=20260805,
        created_at_utc="2026-08-05T12:00:00+00:00",
    )

    assert set(paths) == {
        "dataset_qc_summary.csv",
        "condition_completeness.csv",
        "same_condition_outliers.csv",
        "repeatability_qc.csv",
        "measurement_qc_rollup.csv",
        "manual_review_queue.csv",
        "dataset_qc.json",
        "dataset_qc_manifest.json",
        "dataset_qc_manifest.sha256",
    }
    restored = load_dataset_quality_bundle(output)
    assert restored.to_dict() == result.to_dict()

    with pytest.raises(FileExistsError):
        write_dataset_quality_outputs(
            result,
            scope,
            _config(),
            output,
            input_artifacts=(),
            git_commit="9ec8cfe",
            random_state=0,
        )


def test_dataset_quality_bundle_rejects_tampered_csv(tmp_path: Path) -> None:
    result, scope = _result_and_scope()
    output = tmp_path / "dataset_qc"
    write_dataset_quality_outputs(
        result,
        scope,
        _config(),
        output,
        input_artifacts=(),
        git_commit="9ec8cfe",
        random_state=0,
        created_at_utc="2026-08-05T12:00:00+00:00",
    )
    path = output / "condition_completeness.csv"
    path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        load_dataset_quality_bundle(output)
