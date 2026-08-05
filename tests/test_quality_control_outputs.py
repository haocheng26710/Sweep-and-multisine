from __future__ import annotations

import csv
import json

import pytest

from acoustic_encoder.quality_control import (
    MeasurementQCResult,
    QCCheckResult,
    QCScope,
    QCSourceStage,
    UnavailablePolicy,
)
from acoustic_encoder.quality_control_outputs import (
    load_quality_control_json,
    write_quality_control_outputs,
)
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMode,
    QCCheckStatus,
    QCStatus,
)


def _result() -> MeasurementQCResult:
    return MeasurementQCResult(
        qc_schema_version="1.0.0",
        sample_id="qc-output-fixture",
        measurement_mode=MeasurementMode.REW_SWEEP,
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        checks=(
            QCCheckResult(
                check_id="p2.valid",
                scope=QCScope.SPECTRUM,
                status=QCCheckStatus.VALID,
                source_stage=QCSourceStage.P2,
                source_module="test.output",
                measured_value=8,
                threshold={"minimum": 5},
                units="points",
            ),
            QCCheckResult(
                check_id="p1.unavailable",
                scope=QCScope.MEASUREMENT,
                status=QCCheckStatus.UNAVAILABLE,
                source_stage=QCSourceStage.P1,
                source_module="test.output",
                reason="evidence_unavailable",
                details={"evidence": "not_in_source_format"},
            ),
        ),
        unavailable_required_policy=UnavailablePolicy.WARNING,
        manual_review_reasons=("confirm_fixture",),
        human_valid=True,
        human_exclusion_reason=None,
        scientifically_eligible=False,
    )


def test_qc_output_bundle_is_consistent_and_json_round_trips(tmp_path) -> None:
    result = _result()

    artifacts = write_quality_control_outputs(result, tmp_path)

    assert set(artifacts) == {
        "quality_control_csv",
        "qc_checks_csv",
        "measurement_qc_csv",
        "quality_control_json",
    }
    assert all(path.is_file() and path.stat().st_size > 0 for path in artifacts.values())
    with artifacts["qc_checks_csv"].open(encoding="utf-8", newline="") as handle:
        checks = list(csv.DictReader(handle))
    with artifacts["measurement_qc_csv"].open(
        encoding="utf-8", newline=""
    ) as handle:
        measurement = next(csv.DictReader(handle))
    payload = json.loads(artifacts["quality_control_json"].read_text(encoding="utf-8"))

    assert len(checks) == len(result.checks)
    assert measurement["aggregate_status"] == payload["aggregate_status"] == "valid"
    assert json.loads(measurement["unavailable_checks"]) == ["p1.unavailable"]
    assert payload["eligible_for_downstream"] is False
    assert load_quality_control_json(artifacts["quality_control_json"]) == result


def test_qc_output_bundle_refuses_to_overwrite_any_existing_artifact(tmp_path) -> None:
    existing = tmp_path / "qc_checks.csv"
    existing.write_text("do-not-replace", encoding="utf-8")

    with pytest.raises(FileExistsError, match="qc_checks.csv"):
        write_quality_control_outputs(_result(), tmp_path)

    assert existing.read_text(encoding="utf-8") == "do-not-replace"
    assert not (tmp_path / "quality_control.json").exists()
