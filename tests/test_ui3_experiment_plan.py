from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re

import pytest

from acoustic_encoder.schemas import MeasurementMode
from acoustic_encoder.ui.experiment_plan import (
    ChecklistStatus,
    ExperimentPlan,
    ExperimentPlanService,
    ExperimentRole,
    PlanConditionBlock,
    SafetyChecklist,
    SafetyChecklistItem,
)


def _plan(*, version: str = "1", question: str = "Can direction be recovered?") -> ExperimentPlan:
    return ExperimentPlan(
        schema_version="1.0.0",
        plan_id="u4 encoder plan",
        experiment_name="U4 direction study",
        research_question=question,
        operator="Test Operator",
        plan_version=version,
        created_at="2026-08-10T12:00:00+01:00",
        timezone="Europe/London",
        device_version="V2",
        device_chain="interface -> amplifier -> loudspeaker -> microphone",
        calibration_uri="records/calibration.json",
        provenance_uri="records/provenance.json",
        output_root="outputs/ui_plans",
        condition_blocks=(
            PlanConditionBlock(
                block_id="main",
                configurations=("U4ENC",),
                angles_deg=(90.0, 0.0),
                sessions=("S01",),
                acquisition_blocks=("B01",),
                measurement_modes=(MeasurementMode.REW_SWEEP,),
                experiment_role=ExperimentRole.TRAINING,
                cont_repeats=2,
                repos_rounds=2,
                repos_repeats_per_round=1,
                reasm_assemblies=1,
                reasm_repeats_per_assembly=2,
            ),
        ),
    )


def _ready_checklist() -> SafetyChecklist:
    recorded_at = "2026-08-10T12:30:00+01:00"
    return SafetyChecklist(
        schema_version="1.0.0",
        items=tuple(
            SafetyChecklistItem(
                check_id=check_id,
                status=ChecklistStatus.DECLARED_PASS,
                operator="Safety Operator",
                recorded_at=recorded_at,
                note="Checked before acquisition",
                evidence_path=f"evidence/{check_id}.txt",
                required=True,
            )
            for check_id in SafetyChecklist.required_check_ids()
        ),
    )


def test_plan_schema_round_trip_and_roles_are_not_dataset_roles() -> None:
    plan = _plan()
    restored = ExperimentPlan.from_dict(plan.to_dict())

    assert restored == plan
    assert restored.condition_blocks[0].experiment_role is ExperimentRole.TRAINING
    assert "dataset_role" not in json.dumps(plan.to_dict(), sort_keys=True)


def test_matrix_count_stable_order_and_repeat_families() -> None:
    service = ExperimentPlanService(Path("."), large_plan_threshold=10)
    preview = service.preview(_plan())

    assert preview.expected_sample_count == 12
    assert preview.requires_large_plan_confirmation is True
    assert tuple(row.angle_deg for row in preview.samples[:6]) == (0.0,) * 6
    assert tuple(row.repeat_type for row in preview.samples[:6]) == (
        "CONT", "CONT", "REPOS", "REPOS", "REASM", "REASM"
    )
    assert len({row.sample_id for row in preview.samples}) == 12
    assert all(re.fullmatch(r"[a-z0-9-]+", row.sample_id) for row in preview.samples)


def test_matrix_order_is_independent_of_form_list_order() -> None:
    plan = _plan()
    block = plan.condition_blocks[0]
    reordered = ExperimentPlan.from_dict(
        {
            **plan.to_dict(),
            "condition_blocks": [
                {
                    **block.to_dict(),
                    "angles_deg": [0.0, 90.0],
                }
            ],
        }
    )
    service = ExperimentPlanService(Path("."))

    assert service.preview(plan).samples == service.preview(reordered).samples


def test_sample_identity_ignores_non_identity_plan_revision() -> None:
    service = ExperimentPlanService(Path("."))
    original = service.preview(_plan()).samples
    revised = service.preview(_plan(version="2", question="Reworded question")).samples

    assert tuple(item.sample_id for item in original) == tuple(
        item.sample_id for item in revised
    )


def test_safety_checklist_gate_preserves_human_declaration_semantics() -> None:
    ready = _ready_checklist()
    assert ready.ready_for_acquisition is True
    assert ready.scientific_eligibility_granted is False

    first = ready.items[0]
    incomplete = SafetyChecklist(
        schema_version="1.0.0",
        items=(
            SafetyChecklistItem(
                check_id=first.check_id,
                status=ChecklistStatus.NOT_RECORDED,
                operator=None,
                recorded_at=None,
                note=None,
                evidence_path=None,
                required=True,
            ),
            *ready.items[1:],
        ),
    )
    assert incomplete.ready_for_acquisition is False
    assert incomplete.missing_required_check_ids == (first.check_id,)


def test_plan_revision_is_immutable_and_hash_audited(tmp_path: Path) -> None:
    service = ExperimentPlanService(tmp_path, large_plan_threshold=100)
    first = service.save_revision(_plan(), _ready_checklist())
    second = service.save_revision(
        _plan(version="2", question="Updated before acquisition"),
        _ready_checklist(),
        revision_reason="Clarified question",
    )

    assert first.revision == 1
    assert second.revision == 2
    assert first.directory != second.directory
    assert (first.directory / "acquisition_plan.json").is_file()
    assert (first.directory / "acquisition_plan.md").is_file()
    assert (first.directory / "expected_sample_matrix.csv").is_file()
    assert (first.directory / "safety_checklist.json").is_file()
    assert (first.directory / "plan_manifest.json").is_file()
    assert (first.directory / "hashes.json").is_file()
    assert service.load_revision(first.directory) == first
    assert json.loads((first.directory / "plan_manifest.json").read_text(encoding="utf-8"))["ready_for_acquisition"] is True

    with pytest.raises(FileExistsError):
        service.save_revision(
            _plan(),
            _ready_checklist(),
            forced_revision=1,
        )


def test_checklist_rejects_duplicate_or_unknown_required_items() -> None:
    item = _ready_checklist().items[0]
    with pytest.raises(ValueError, match="unique"):
        SafetyChecklist(schema_version="1.0.0", items=(item, item))


def test_created_at_and_checklist_times_require_timezone() -> None:
    payload = _plan().to_dict()
    payload["created_at"] = datetime(2026, 8, 10, 12, 0).isoformat()
    with pytest.raises(ValueError, match="timezone"):
        ExperimentPlan.from_dict(payload)
