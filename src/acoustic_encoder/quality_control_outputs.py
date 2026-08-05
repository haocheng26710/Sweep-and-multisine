"""Consistent CSV/JSON serialization for the shared P2 QC result."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .quality_control import MeasurementQCResult


def _json_cell(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_rows(
    path: Path,
    fieldnames: Iterable[str],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def write_quality_control_outputs(
    result: MeasurementQCResult,
    output_directory: str | Path,
) -> dict[str, Path]:
    """Write all P2 views from one typed result and refuse partial overwrite."""
    output = Path(output_directory)
    paths = {
        "quality_control_csv": output / "quality_control.csv",
        "qc_checks_csv": output / "qc_checks.csv",
        "measurement_qc_csv": output / "measurement_qc.csv",
        "quality_control_json": output / "quality_control.json",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(f"QC artifact already exists: {existing[0]}")
    output.mkdir(parents=True, exist_ok=True)

    _write_rows(
        paths["quality_control_csv"],
        (
            "sample_id",
            "measurement_mode",
            "qc_status",
            "valid",
            "exclusion_reason",
            "eligible_for_downstream",
        ),
        (
            {
                "sample_id": result.sample_id,
                "measurement_mode": result.measurement_mode.value,
                "qc_status": result.aggregate_status.value,
                "valid": result.human_valid,
                "exclusion_reason": result.human_exclusion_reason or "",
                "eligible_for_downstream": result.eligible_for_downstream,
            },
        ),
    )

    check_rows = []
    for check in result.checks:
        check_rows.append(
            {
                "qc_schema_version": result.qc_schema_version,
                "sample_id": result.sample_id,
                "measurement_mode": result.measurement_mode.value,
                "data_origin": result.data_origin.value,
                "dataset_role": result.dataset_role.value,
                "run_purpose": result.run_purpose.value,
                "check_id": check.check_id,
                "scope": check.scope.value,
                "status": check.status.value,
                "severity_rank": (
                    "" if check.severity_rank is None else check.severity_rank
                ),
                "available": check.available,
                "required": check.required,
                "source_stage": check.source_stage.value,
                "source_module": check.source_module,
                "frequency_hz": (
                    "" if check.frequency_hz is None else check.frequency_hz
                ),
                "measured_value": _json_cell(check.measured_value),
                "threshold": _json_cell(check.threshold),
                "units": check.units or "",
                "reason": check.reason or "",
                "details": _json_cell(check.details),
            }
        )
    _write_rows(
        paths["qc_checks_csv"],
        check_rows[0].keys(),
        check_rows,
    )

    measurement_row = {
        "qc_schema_version": result.qc_schema_version,
        "sample_id": result.sample_id,
        "measurement_mode": result.measurement_mode.value,
        "data_origin": result.data_origin.value,
        "dataset_role": result.dataset_role.value,
        "run_purpose": result.run_purpose.value,
        "aggregate_status": result.aggregate_status.value,
        "warning_reasons": _json_cell(result.warning_reasons),
        "exclude_candidate_reasons": _json_cell(
            result.exclude_candidate_reasons
        ),
        "unavailable_checks": _json_cell(result.unavailable_checks),
        "manual_review_reasons": _json_cell(result.manual_review_reasons),
        "human_valid": result.human_valid,
        "human_exclusion_reason": result.human_exclusion_reason or "",
        "scientifically_eligible": result.scientifically_eligible,
        "eligible_for_downstream": result.eligible_for_downstream,
        "check_count": len(result.checks),
    }
    _write_rows(
        paths["measurement_qc_csv"],
        measurement_row.keys(),
        (measurement_row,),
    )
    paths["quality_control_json"].write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return paths


def load_quality_control_json(path: str | Path) -> MeasurementQCResult:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Serialized quality_control.json root must be an object")
    return MeasurementQCResult.from_dict(payload)
