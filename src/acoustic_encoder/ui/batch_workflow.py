"""UI application services for explicit P2-B through P6 orchestration.

This module writes scopes and manifests understood by existing formal CLIs.  It
does not implement scientific calculations and does not invoke validation
fixture runners.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
from html import escape
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import yaml

from acoustic_encoder.dataset_quality_cli import (
    DATASET_QC_INPUT_MANIFEST_SCHEMA_VERSION,
    DatasetQCInputEntry,
    DatasetQCInputManifest,
)
from acoustic_encoder.dataset_quality_control import (
    DATASET_QC_SCOPE_SCHEMA_VERSION,
    CohortRole,
    DatasetQCScope,
    DatasetScopeMember,
    ExpectedCondition,
)
from acoustic_encoder.dataset_quality_outputs import load_dataset_quality_bundle
from acoustic_encoder.quality_control import measurement_qc_sha256
from acoustic_encoder.quality_control_outputs import load_quality_control_json
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    artifact_sha256,
    load_feature_set,
)
from acoustic_encoder.ui.experiment_plan import ExpectedSample, ExperimentRole
from acoustic_encoder.ui.sample_registry import FinalTestSealedError, RegisteredSample


class BatchStage(str, Enum):
    P2_B = "P2_B"
    P3_C = "P3_C"
    P4 = "P4"
    P5_A = "P5_A"
    P5_B = "P5_B"
    P6_A = "P6_A"
    P6_B = "P6_B"


@dataclass(frozen=True, slots=True)
class BatchStageCapability:
    stage: BatchStage
    title: str
    formally_available: bool
    entry_point: str | None
    script: str | None
    required_inputs: tuple[str, ...]
    required_scope: str
    prerequisite_qc: str
    supported_modes: tuple[str, ...]
    output_bundle: str
    requires_p3c: bool = False
    real_multisine_blocked: bool = False
    unavailable_reason: str | None = None


class BatchWorkflowStatus(str, Enum):
    NOT_STARTED = "not_started"
    PLAN_DRAFT = "plan_draft"
    PLAN_READY = "plan_ready"
    ACQUISITION_WAITING = "acquisition_waiting"
    SAMPLES_PARTIAL = "samples_partial"
    SAMPLES_COMPLETE = "samples_complete"
    DATASET_QC_RUNNING = "dataset_qc_running"
    DATASET_QC_WARNING = "dataset_qc_warning"
    DATASET_QC_PASSED = "dataset_qc_passed"
    ANALYSIS_READY = "analysis_ready"
    ANALYSIS_RUNNING = "analysis_running"
    ANALYSIS_WARNING = "analysis_warning"
    ANALYSIS_COMPLETED = "analysis_completed"
    FINAL_TEST_SEALED = "final_test_sealed"
    BLOCKED = "blocked"


class InvalidBatchTransition(ValueError):
    pass


_TRANSITIONS: dict[BatchWorkflowStatus, frozenset[BatchWorkflowStatus]] = {
    BatchWorkflowStatus.NOT_STARTED: frozenset({BatchWorkflowStatus.PLAN_DRAFT}),
    BatchWorkflowStatus.PLAN_DRAFT: frozenset(
        {
            BatchWorkflowStatus.PLAN_READY,
            BatchWorkflowStatus.SAMPLES_PARTIAL,
            BatchWorkflowStatus.SAMPLES_COMPLETE,
            BatchWorkflowStatus.BLOCKED,
        }
    ),
    BatchWorkflowStatus.PLAN_READY: frozenset(
        {BatchWorkflowStatus.ACQUISITION_WAITING, BatchWorkflowStatus.BLOCKED}
    ),
    BatchWorkflowStatus.ACQUISITION_WAITING: frozenset(
        {
            BatchWorkflowStatus.SAMPLES_PARTIAL,
            BatchWorkflowStatus.SAMPLES_COMPLETE,
            BatchWorkflowStatus.BLOCKED,
        }
    ),
    BatchWorkflowStatus.SAMPLES_PARTIAL: frozenset(
        {
            BatchWorkflowStatus.SAMPLES_COMPLETE,
            BatchWorkflowStatus.DATASET_QC_RUNNING,
            BatchWorkflowStatus.BLOCKED,
        }
    ),
    BatchWorkflowStatus.SAMPLES_COMPLETE: frozenset(
        {BatchWorkflowStatus.DATASET_QC_RUNNING, BatchWorkflowStatus.BLOCKED}
    ),
    BatchWorkflowStatus.DATASET_QC_RUNNING: frozenset(
        {
            BatchWorkflowStatus.DATASET_QC_WARNING,
            BatchWorkflowStatus.DATASET_QC_PASSED,
            BatchWorkflowStatus.BLOCKED,
        }
    ),
    BatchWorkflowStatus.DATASET_QC_WARNING: frozenset(
        {BatchWorkflowStatus.DATASET_QC_RUNNING, BatchWorkflowStatus.BLOCKED}
    ),
    BatchWorkflowStatus.DATASET_QC_PASSED: frozenset(
        {BatchWorkflowStatus.ANALYSIS_READY, BatchWorkflowStatus.DATASET_QC_RUNNING}
    ),
    BatchWorkflowStatus.ANALYSIS_READY: frozenset(
        {BatchWorkflowStatus.ANALYSIS_RUNNING, BatchWorkflowStatus.BLOCKED}
    ),
    BatchWorkflowStatus.ANALYSIS_RUNNING: frozenset(
        {
            BatchWorkflowStatus.ANALYSIS_WARNING,
            BatchWorkflowStatus.ANALYSIS_COMPLETED,
            BatchWorkflowStatus.BLOCKED,
        }
    ),
    BatchWorkflowStatus.ANALYSIS_WARNING: frozenset(
        {BatchWorkflowStatus.ANALYSIS_RUNNING, BatchWorkflowStatus.BLOCKED}
    ),
    BatchWorkflowStatus.ANALYSIS_COMPLETED: frozenset(
        {BatchWorkflowStatus.ANALYSIS_READY}
    ),
    BatchWorkflowStatus.FINAL_TEST_SEALED: frozenset(),
    BatchWorkflowStatus.BLOCKED: frozenset(
        {BatchWorkflowStatus.PLAN_DRAFT, BatchWorkflowStatus.ACQUISITION_WAITING}
    ),
}


class BatchWorkflowState:
    def __init__(self) -> None:
        self.status = BatchWorkflowStatus.NOT_STARTED

    def transition(self, target: BatchWorkflowStatus | str) -> None:
        selected = BatchWorkflowStatus(target)
        if selected not in _TRANSITIONS[self.status]:
            raise InvalidBatchTransition(
                f"invalid batch transition: {self.status.value} -> {selected.value}"
            )
        self.status = selected


@dataclass(frozen=True, slots=True)
class PreparedBatchInvocation:
    stage: BatchStage
    run_id: str
    program: str
    arguments: tuple[str, ...]
    preview_directory: Path
    output_directory: Path
    scope_path: Path
    input_manifest_path: Path


@dataclass(frozen=True, slots=True)
class DatasetQCSummary:
    processing_status: str
    aggregate_status: str
    canonical_ready: bool
    canonical_ready_reasons: tuple[str, ...]
    scientifically_eligible: bool
    missing_condition_count: int
    duplicate_condition_count: int
    unavailable_count: int


def _json_write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _canonical_id(value: Mapping[str, Any], prefix: str) -> str:
    digest = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"{prefix}-{digest[:16]}"


class BatchWorkflowService:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()

    @staticmethod
    def capabilities() -> tuple[BatchStageCapability, ...]:
        return (
            BatchStageCapability(
                BatchStage.P2_B,
                "数据集 QC",
                True,
                "acoustic_encoder.dataset_quality_cli.run_dataset_quality_cli",
                "scripts/run_dataset_qc.py",
                ("FeatureSet", "MeasurementQCResult"),
                "DatasetQCScope + DatasetQCInputManifest",
                "P2-A completed",
                ("rew_sweep", "schroeder_multisine"),
                "dataset_qc",
            ),
            BatchStageCapability(
                BatchStage.P3_C,
                "匹配 tone FeatureSet",
                False,
                None,
                None,
                ("dense sweep", "P8 sparse tones", "tone authority"),
                "paired matched-tone scope",
                "P2-A/P8",
                ("rew_sweep", "schroeder_multisine"),
                "matched-tone FeatureSets",
                requires_p3c=True,
                unavailable_reason=(
                    "仓库当前只有模拟 validation runner 和核心 API，没有通用正式生产入口；"
                    "UI3 不包装 validation fixture。"
                ),
            ),
            BatchStageCapability(
                BatchStage.P4,
                "方向和配置比较",
                True,
                "acoustic_encoder.comparison_metrics_cli.run_comparison_metrics_cli",
                "scripts/run_comparison_metrics.py",
                ("persisted FeatureSets", "P2-B bundle"),
                "ComparisonAnalysisScope + ComparisonInputManifest",
                "canonical-ready P2-B",
                ("rew_sweep", "schroeder_multisine"),
                "comparison_metrics",
            ),
            BatchStageCapability(
                BatchStage.P5_A,
                "分组分类",
                True,
                "acoustic_encoder.classification_cli.run_classification_cli",
                "scripts/run_classification.py",
                ("single-mode FeatureSets", "P2-B bundle"),
                "ClassificationScope + ClassificationInputManifest",
                "canonical-ready P2-B",
                ("rew_sweep", "schroeder_multisine"),
                "classification",
            ),
            BatchStageCapability(
                BatchStage.P5_B,
                "跨模式分类",
                True,
                "acoustic_encoder.cross_mode_classification_cli.run_cross_mode_classification_cli",
                "scripts/run_cross_mode_classification.py",
                ("P3-C matched FeatureSets", "P2-B", "P4-B"),
                "CrossModeClassificationScope + input manifest",
                "canonical-ready P2-B and verified P4-B",
                ("rew_sweep", "schroeder_multisine"),
                "cross_mode_classification",
                requires_p3c=True,
                real_multisine_blocked=True,
            ),
            BatchStageCapability(
                BatchStage.P6_A,
                "Sweep HR 校准",
                True,
                "acoustic_encoder.hr_cli.main",
                "scripts/run_hr_calibration.py",
                ("dense_raw_spl FeatureSets", "P2-B bundle"),
                "HRCalibrationScope + HRCalibrationInputManifest",
                "canonical-ready P2-B",
                ("rew_sweep",),
                "hr_calibration",
            ),
            BatchStageCapability(
                BatchStage.P6_B,
                "Multisine HR 读取",
                True,
                "acoustic_encoder.hr_readout_cli.main",
                "scripts/run_hr_readout.py",
                ("P3-C multisine FeatureSets", "P6-A authority", "P2-B"),
                "HRReadoutScope + HRReadoutInputManifest",
                "canonical-ready P2-B and exact P6-A authority",
                ("schroeder_multisine",),
                "hr_readout",
                requires_p3c=True,
                real_multisine_blocked=True,
            ),
        )

    def prepare_p2b(
        self,
        *,
        expected_samples: Sequence[ExpectedSample],
        registrations: Sequence[RegisteredSample],
        preview_directory: str | Path,
        config_path: str | Path,
        output_root: str | Path,
        run_id: str,
        feature_kind: FeatureKind | str,
        selection_reason: str,
    ) -> PreparedBatchInvocation:
        if not run_id.strip() or any(
            not (character.isalnum() or character in "-_") for character in run_id
        ):
            raise ValueError("batch run-id must be non-empty and filesystem safe")
        if not selection_reason.strip():
            raise ValueError("P2-B selection reason is required")
        output_preview = Path(preview_directory).resolve()
        if output_preview.exists():
            raise FileExistsError(f"P2-B preview directory already exists: {output_preview}")
        expected = tuple(expected_samples)
        registered = tuple(registrations)
        if not expected or not registered:
            raise ValueError("P2-B requires explicit expected samples and registrations")
        expected_by_id = {item.sample_id: item for item in expected}
        if len(expected_by_id) != len(expected):
            raise ValueError("P2-B expected sample IDs must be unique")
        for item in expected:
            if item.experiment_role not in {
                ExperimentRole.TRAINING,
                ExperimentRole.DEVELOPMENT,
            }:
                raise ValueError(
                    f"P2-B UI scope does not support experiment role {item.experiment_role.value}"
                )
        source_ids = tuple(item.source_sample_id for item in registered)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("P2-B registered source sample IDs must be unique")
        if any(item.expected_sample_id not in expected_by_id for item in registered):
            raise ValueError("P2-B registration is not bound to the explicit expected matrix")
        origins = {item.metadata.data_origin for item in registered}
        dataset_roles = {item.metadata.dataset_role for item in registered}
        purposes = {item.run_purpose for item in registered}
        if len(origins) != 1 or len(dataset_roles) != 1 or purposes != {"software_validation"}:
            raise ValueError("P2-B UI preview requires one provenance/purpose partition")
        if origins == {DataOrigin.EXTERNAL_REFERENCE}:
            raise ValueError(
                "external_reference cannot enter an experimental P2-B condition matrix"
            )
        selected_kind = FeatureKind(feature_kind)
        feature_records: list[tuple[RegisteredSample, Path, Path, Path]] = []
        for item in registered:
            if not item.feature_set_available:
                raise ValueError(f"P2-B registration has no FeatureSet: {item.source_sample_id}")
            matching = [
                Path(artifact.path)
                for artifact in item.artifacts
                if artifact.artifact_type == "feature_set"
                and f"/{selected_kind.value}/" in Path(artifact.path).as_posix()
            ]
            npz = next((path for path in matching if path.suffix.lower() == ".npz"), None)
            metadata_json = next((path for path in matching if path.suffix.lower() == ".json"), None)
            qc_path = next(
                (
                    Path(artifact.path)
                    for artifact in item.artifacts
                    if artifact.artifact_type == "quality_control"
                    and Path(artifact.path).name == "quality_control.json"
                ),
                None,
            )
            if npz is None or metadata_json is None or qc_path is None:
                raise ValueError(
                    f"P2-B FeatureSet/P2-A artifacts are incomplete: {item.source_sample_id}"
                )
            for path in (npz, metadata_json, qc_path):
                if not path.is_file():
                    raise FileNotFoundError(path)
            feature_records.append((item, npz, metadata_json, qc_path))
        members: list[DatasetScopeMember] = []
        input_entries: list[DatasetQCInputEntry] = []
        condition_members: dict[str, list[ExpectedSample]] = {}
        for target in expected:
            condition_members.setdefault(target.condition_id, []).append(target)
        for item, npz, metadata_json, qc_path in feature_records:
            target = expected_by_id[str(item.expected_sample_id)]
            role = CohortRole(target.experiment_role.value)
            feature = load_feature_set(npz.with_suffix(""))
            qc = load_quality_control_json(qc_path)
            if feature.sample_id != item.source_sample_id or qc.sample_id != item.source_sample_id:
                raise ValueError("P2-B serialized sample identity mismatch")
            if feature.meta != item.metadata:
                raise ValueError("P2-B registered metadata differs from FeatureSet metadata")
            members.append(
                DatasetScopeMember(
                    sample_id=item.source_sample_id,
                    cohort_role=role,
                    expected_condition_id=target.condition_id,
                    selection_reason=selection_reason,
                )
            )
            input_entries.append(
                DatasetQCInputEntry(
                    sample_id=item.source_sample_id,
                    feature_base_path=npz.with_suffix("").as_posix(),
                    feature_npz_sha256=artifact_sha256(npz),
                    feature_json_sha256=artifact_sha256(metadata_json),
                    measurement_qc_path=qc_path.as_posix(),
                    measurement_qc_file_sha256=artifact_sha256(qc_path),
                    measurement_qc_result_sha256=measurement_qc_sha256(qc),
                )
            )
        conditions: list[ExpectedCondition] = []
        for condition_id, rows in sorted(condition_members.items()):
            first = rows[0]
            identity = (
                first.experiment_role,
                first.measurement_mode,
                first.configuration_id,
                first.direction_id,
                first.angle_deg,
                first.session_id,
                first.repeat_type,
                first.reposition_round_id,
                first.assembly_id,
                first.acquisition_block_id,
            )
            if any(
                (
                    row.experiment_role,
                    row.measurement_mode,
                    row.configuration_id,
                    row.direction_id,
                    row.angle_deg,
                    row.session_id,
                    row.repeat_type,
                    row.reposition_round_id,
                    row.assembly_id,
                    row.acquisition_block_id,
                )
                != identity
                for row in rows[1:]
            ):
                raise ValueError("condition_id groups incompatible expected identities")
            conditions.append(
                ExpectedCondition(
                    condition_id=condition_id,
                    cohort_role=CohortRole(first.experiment_role.value),
                    measurement_mode=first.measurement_mode,
                    configuration_id=first.configuration_id,
                    direction_id=first.direction_id,
                    direction_angle_deg=first.angle_deg,
                    session_id=first.session_id,
                    repeat_type=first.repeat_type,
                    reposition_round_id=first.reposition_round_id,
                    assembly_id=first.assembly_id,
                    acquisition_block_id=first.acquisition_block_id,
                    expected_count=len(rows),
                )
            )
        scope_identity = {
            "members": [item.to_dict() for item in members],
            "conditions": [item.to_dict() for item in conditions],
            "feature_kind": selected_kind.value,
        }
        analysis_scope_id = _canonical_id(scope_identity, "ui3-p2b")
        scope = DatasetQCScope(
            schema_version=DATASET_QC_SCOPE_SCHEMA_VERSION,
            analysis_scope_id=analysis_scope_id,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            members=tuple(members),
            expected_conditions=tuple(conditions),
        )
        origin = next(iter(origins))
        dataset_role = next(iter(dataset_roles))
        inputs = DatasetQCInputManifest(
            schema_version=DATASET_QC_INPUT_MANIFEST_SCHEMA_VERSION,
            analysis_scope_id=analysis_scope_id,
            data_origin=DataOrigin(origin),
            dataset_role=DatasetRole(dataset_role),
            measurements=tuple(input_entries),
        )
        output_preview.mkdir(parents=True, exist_ok=False)
        scope_path = output_preview / "dataset_scope.json"
        inputs_path = output_preview / "dataset_inputs.json"
        _json_write(scope_path, scope.to_dict())
        _json_write(inputs_path, {
            "schema_version": inputs.schema_version,
            "analysis_scope_id": inputs.analysis_scope_id,
            "data_origin": inputs.data_origin.value,
            "dataset_role": inputs.dataset_role.value,
            "measurements": [
                {
                    name: getattr(item, name)
                    for name in item.__dataclass_fields__
                }
                for item in inputs.measurements
            ],
        })
        matrix_path = output_preview / "expected_condition_matrix.csv"
        condition_rows = [item.to_dict() for item in conditions]
        with matrix_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(condition_rows[0]))
            writer.writeheader()
            writer.writerows(condition_rows)
        audit_path = output_preview / "selected_sample_audit.csv"
        audit_rows = [
            {
                "expected_sample_id": item.expected_sample_id,
                "source_sample_id": item.source_sample_id,
                "registration_id": item.registration_id,
                "selection_reason": selection_reason,
                "included": "true",
                "scientifically_eligible": "false",
            }
            for item in registered
        ]
        with audit_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]))
            writer.writeheader()
            writer.writerows(audit_rows)
        snapshot = {
            "schema_version": "1.0.0",
            "stage": BatchStage.P2_B.value,
            "analysis_scope_id": analysis_scope_id,
            "run_id": run_id,
            "feature_kind": selected_kind.value,
            "sample_count": len(registered),
            "data_origin": origin.value,
            "dataset_role": dataset_role.value,
            "run_purpose": "software_validation",
            "scientifically_eligible": False,
            "final_test_read": False,
            "selection_reason": selection_reason,
        }
        _json_write(output_preview / "ui_scope_snapshot.json", snapshot)
        hash_targets = (scope_path, inputs_path, matrix_path, audit_path, output_preview / "ui_scope_snapshot.json")
        _json_write(
            output_preview / "artifact_hashes.json",
            {path.name: artifact_sha256(path) for path in hash_targets},
        )
        output_root_path = Path(output_root).resolve()
        output_directory = (
            output_root_path
            / origin.value
            / RunPurpose.SOFTWARE_VALIDATION.value
            / run_id
            / "dataset_qc"
        )
        if output_directory.exists():
            raise FileExistsError(f"P2-B output directory already exists: {output_directory}")
        script = self.project_root / "scripts/run_dataset_qc.py"
        arguments = (
            str(script),
            "--config",
            str(Path(config_path).resolve()),
            "--scope",
            str(scope_path),
            "--inputs",
            str(inputs_path),
            "--output-root",
            str(output_root_path),
            "--run-id",
            run_id,
        )
        return PreparedBatchInvocation(
            BatchStage.P2_B,
            run_id,
            sys.executable,
            arguments,
            output_preview,
            output_directory,
            scope_path,
            inputs_path,
        )

    def prepare_formal_stage(
        self,
        *,
        stage: BatchStage | str,
        scope_path: str | Path,
        input_manifest_path: str | Path,
        preview_directory: str | Path,
        config_path: str | Path,
        output_root: str | Path,
        run_id: str,
        dataset_qc_directory: str | Path | None = None,
        comparison_directory: str | Path | None = None,
    ) -> PreparedBatchInvocation:
        """Prepare an existing formal CLI without inventing a new scope schema."""
        selected = BatchStage(stage)
        capability = next(item for item in self.capabilities() if item.stage is selected)
        if selected in {BatchStage.P2_B, BatchStage.P3_C}:
            raise ValueError(f"{selected.value} uses a dedicated preparation path")
        if not capability.formally_available or capability.script is None:
            raise ValueError(capability.unavailable_reason or "stage is unavailable")
        if not run_id.strip() or any(
            not (character.isalnum() or character in "-_") for character in run_id
        ):
            raise ValueError("batch run-id must be non-empty and filesystem safe")
        scope_file = Path(scope_path).resolve()
        inputs_file = Path(input_manifest_path).resolve()
        config_file = Path(config_path).resolve()
        for path in (scope_file, inputs_file, config_file):
            if not path.is_file():
                raise FileNotFoundError(path)
        scope_payload = self._read_mapping(scope_file)
        if self._contains_final_test(scope_payload):
            raise FinalTestSealedError(
                "formal stage scope contains final_test; content artifacts were not read"
            )
        inputs_payload = self._read_mapping(inputs_file)
        origin = str(
            inputs_payload.get("data_origin")
            or scope_payload.get("data_origin")
            or ""
        )
        purpose = str(
            inputs_payload.get("run_purpose")
            or scope_payload.get("run_purpose")
            or (
                scope_payload.get("analysis_scope", {}).get("run_purpose")
                if isinstance(scope_payload.get("analysis_scope"), Mapping)
                else ""
            )
        )
        if origin not in {item.value for item in DataOrigin}:
            raise ValueError("formal stage scope/input data_origin is missing or invalid")
        if purpose not in {item.value for item in RunPurpose}:
            raise ValueError("formal stage scope/input run_purpose is missing or invalid")
        if capability.real_multisine_blocked and origin == DataOrigin.REAL_EXPERIMENT.value:
            raise PermissionError(
                "真实 Multisine/P8 及其依赖阶段在 DEV-UI3 中保持硬阻塞。"
            )
        if dataset_qc_directory is None:
            raise ValueError(f"{selected.value} requires an explicit P2-B bundle")
        p2b = Path(dataset_qc_directory).resolve()
        p2b_summary = self.load_p2b_summary(p2b)
        if p2b_summary.processing_status != "completed" or not p2b_summary.canonical_ready:
            reasons = ", ".join(p2b_summary.canonical_ready_reasons) or "not_canonical_ready"
            raise PermissionError(
                f"{selected.value} requires canonical-ready P2-B: {reasons}"
            )
        p2b_manifest_path = p2b / "dataset_qc_manifest.json"
        p2b_result_path = p2b / "dataset_qc.json"
        if selected is BatchStage.P5_B:
            if comparison_directory is None:
                raise ValueError("P5_B requires an explicit P4-B bundle")
            comparison = Path(comparison_directory).resolve()
            if not (comparison / "comparison_metrics.json").is_file():
                raise FileNotFoundError(comparison / "comparison_metrics.json")
        else:
            comparison = None
        preview = Path(preview_directory).resolve()
        if preview.exists():
            raise FileExistsError(f"stage preview directory already exists: {preview}")
        output_root_path = Path(output_root).resolve()
        stage_directories = {
            BatchStage.P4: "comparison_metrics",
            BatchStage.P5_A: "classification",
            BatchStage.P5_B: "cross_mode_classification",
            BatchStage.P6_A: "hr_calibration",
            BatchStage.P6_B: "hr_readout",
        }
        output = output_root_path / origin / purpose / run_id / stage_directories[selected]
        if output.exists():
            raise FileExistsError(f"formal stage output already exists: {output}")
        preview.mkdir(parents=True, exist_ok=False)
        scope_snapshot = preview / f"scope_snapshot{scope_file.suffix.lower()}"
        inputs_snapshot = preview / f"input_manifest_snapshot{inputs_file.suffix.lower()}"
        scope_snapshot.write_bytes(scope_file.read_bytes())
        inputs_snapshot.write_bytes(inputs_file.read_bytes())
        snapshot = {
            "schema_version": "1.0.0",
            "stage": selected.value,
            "run_id": run_id,
            "formal_entry_point": capability.entry_point,
            "script": capability.script,
            "data_origin": origin,
            "run_purpose": purpose,
            "scientifically_eligible": False,
            "final_test_read": False,
            "scope_path": scope_file.as_posix(),
            "scope_sha256": artifact_sha256(scope_file),
            "input_manifest_path": inputs_file.as_posix(),
            "input_manifest_sha256": artifact_sha256(inputs_file),
            "dataset_qc_directory": p2b.as_posix(),
            "dataset_qc_manifest_sha256": artifact_sha256(p2b_manifest_path),
            "dataset_qc_result_sha256": artifact_sha256(p2b_result_path),
            "comparison_directory": None if comparison is None else comparison.as_posix(),
        }
        _json_write(preview / "ui_scope_snapshot.json", snapshot)
        _json_write(
            preview / "artifact_hashes.json",
            {
                scope_snapshot.name: artifact_sha256(scope_snapshot),
                inputs_snapshot.name: artifact_sha256(inputs_snapshot),
                "ui_scope_snapshot.json": artifact_sha256(preview / "ui_scope_snapshot.json"),
            },
        )
        arguments = [
            str(self.project_root / capability.script),
            "--config",
            str(config_file),
            "--scope",
            str(scope_file),
            "--inputs",
            str(inputs_file),
            "--dataset-qc-dir",
            str(p2b),
        ]
        if selected is BatchStage.P5_B and comparison is not None:
            arguments.extend(("--comparison-dir", str(comparison)))
        arguments.extend(("--output-root", str(output_root_path), "--run-id", run_id))
        if selected in {BatchStage.P6_A, BatchStage.P6_B}:
            arguments.extend(("--project-root", str(self.project_root)))
        return PreparedBatchInvocation(
            selected,
            run_id,
            sys.executable,
            tuple(arguments),
            preview,
            output,
            scope_file,
            inputs_file,
        )

    @staticmethod
    def _read_mapping(path: Path) -> dict[str, Any]:
        value = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.suffix.lower() == ".json"
            else yaml.safe_load(path.read_text(encoding="utf-8"))
        )
        if not isinstance(value, dict):
            raise ValueError(f"expected mapping in {path}")
        return value

    @classmethod
    def _contains_final_test(cls, value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(cls._contains_final_test(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(cls._contains_final_test(item) for item in value)
        return str(value) in {"final_test", "final_test_sealed"}

    @staticmethod
    def record_stage_result(
        invocation: PreparedBatchInvocation,
        *,
        outcome: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        result_summary: Mapping[str, Any] | None = None,
    ) -> tuple[Path, Path, Path]:
        """Append UI evidence beside immutable preview snapshots."""
        log_path = invocation.preview_directory / "technical_log.txt"
        report_path = invocation.preview_directory / "step_report.md"
        html_path = invocation.preview_directory / "step_report.html"
        for path in (log_path, report_path, html_path):
            if path.exists():
                raise FileExistsError(f"stage UI evidence already exists: {path}")
        log_path.write_text(
            f"program={invocation.program}\n"
            f"arguments={json.dumps(list(invocation.arguments), ensure_ascii=False)}\n"
            f"outcome={outcome}\nexit_code={exit_code}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}\n",
            encoding="utf-8",
        )
        summary = dict(result_summary or {})
        report = (
            f"# UI batch step: {invocation.stage.value}\n\n"
            f"- Run ID: `{invocation.run_id}`\n"
            f"- Outcome: `{outcome}`\n"
            f"- Exit code: `{exit_code}`\n"
            f"- Output: `{invocation.output_directory.as_posix()}`\n"
            "- Final-test read: `false`\n"
            f"- Scientifically eligible: `{str(bool(summary.get('scientifically_eligible', False))).lower()}`\n"
            f"- Result summary: `{json.dumps(summary, sort_keys=True, ensure_ascii=False)}`\n\n"
            "The scientific result remains authoritative in the backend bundle; "
            "this report is a UI orchestration record.\n"
        )
        report_path.write_text(report, encoding="utf-8")
        html_path.write_text(
            "<!doctype html><meta charset=\"utf-8\"><title>UI batch report</title>"
            f"<pre>{escape(report)}</pre>\n",
            encoding="utf-8",
        )
        return log_path, report_path, html_path

    @staticmethod
    def load_p2b_summary(output_directory: str | Path) -> DatasetQCSummary:
        output = Path(output_directory).resolve()
        result = load_dataset_quality_bundle(output)
        manifest = json.loads(
            (output / "dataset_qc_manifest.json").read_text(encoding="utf-8")
        )
        return DatasetQCSummary(
            processing_status=str(manifest["processing_status"]),
            aggregate_status=result.aggregate_status.value,
            canonical_ready=result.canonical_ready,
            canonical_ready_reasons=tuple(result.canonical_ready_reasons),
            scientifically_eligible=result.scientifically_eligible,
            missing_condition_count=sum(item.missing_count for item in result.condition_results),
            duplicate_condition_count=sum(item.duplicate_count for item in result.condition_results),
            unavailable_count=sum(
                item.status.value == "unavailable"
                for item in (*result.outlier_results, *result.repeatability_results)
            ),
        )
