from __future__ import annotations

import pytest

from acoustic_encoder.ui.state import (
    HARD_BLOCK_REAL_MULTISINE_MESSAGE,
    InvalidStepTransition,
    StepStatus,
    UiMode,
    WizardState,
)


EXPECTED_STEPS = (
    "检查软件环境",
    "选择使用方式",
    "制定实验计划",
    "生成实验刺激",
    "完成外部播放和录音",
    "导入并检查单次数据",
    "检查完整实验数据集",
    "比较方向、配置和重复性",
    "分类、选频和校准",
    "冻结分析方案",
    "最终测试",
    "查看和导出报告",
)


def test_wizard_defaults_to_simple_mode_with_twelve_ordered_steps() -> None:
    state = WizardState()

    assert state.mode is UiMode.SIMPLE
    assert tuple(step.title for step in state.steps) == EXPECTED_STEPS
    assert state.steps[0].status is StepStatus.READY
    assert all(step.status is StepStatus.NOT_STARTED for step in state.steps[1:])


def test_step_state_machine_accepts_execution_path_and_rejects_illegal_jump() -> None:
    state = WizardState()

    state.transition("environment", StepStatus.RUNNING)
    state.transition("environment", StepStatus.PASSED)
    assert state.step("environment").status is StepStatus.PASSED

    with pytest.raises(InvalidStepTransition, match="passed -> running"):
        state.transition("environment", StepStatus.RUNNING)


@pytest.mark.parametrize(
    "value",
    [
        "not_started",
        "ready",
        "waiting_external",
        "running",
        "passed",
        "warning",
        "manual_review",
        "blocked",
        "failed",
    ],
)
def test_all_required_step_statuses_are_explicit(value: str) -> None:
    assert StepStatus(value).value == value


def test_real_experiment_multisine_is_fail_closed_without_provenance_override() -> None:
    state = WizardState()

    decision = state.select_usage(
        data_origin="real_experiment",
        measurement_mode="schroeder_multisine",
        run_purpose="research_analysis",
    )

    assert not decision.allowed
    assert decision.reason == HARD_BLOCK_REAL_MULTISINE_MESSAGE
    assert state.step("single_measurement").status is StepStatus.BLOCKED
    assert "eligible_for_scientific_analysis" not in state.editable_context_fields


def test_unknown_persisted_status_fails_closed() -> None:
    assert StepStatus.from_external("future_state") is StepStatus.BLOCKED
