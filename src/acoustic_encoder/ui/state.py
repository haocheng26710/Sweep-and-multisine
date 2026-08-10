"""Fail-closed, presentation-only state for the desktop wizard."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


HARD_BLOCK_REAL_MULTISINE_MESSAGE = (
    "当前 P8-A 后端仅允许 simulated/software_validation。\n"
    "DEV-C16 ready 表示可以进入 DEV-D 准备，不代表真实 "
    "Multisine 已获准分析。"
)


class StepStatus(str, Enum):
    NOT_STARTED = "not_started"
    READY = "ready"
    WAITING_EXTERNAL = "waiting_external"
    RUNNING = "running"
    PASSED = "passed"
    WARNING = "warning"
    MANUAL_REVIEW = "manual_review"
    BLOCKED = "blocked"
    FAILED = "failed"

    @classmethod
    def from_external(cls, value: str) -> "StepStatus":
        try:
            return cls(value)
        except ValueError:
            return cls.BLOCKED


class UiMode(str, Enum):
    SIMPLE = "simple"
    PROFESSIONAL = "professional"


class InvalidStepTransition(ValueError):
    """Raised when the UI attempts an invalid lifecycle transition."""


@dataclass(frozen=True, slots=True)
class GateDecision:
    allowed: bool
    reason: str


@dataclass(slots=True)
class WizardStep:
    step_id: str
    title: str
    status: StepStatus
    implementation_round: str
    preparation: str
    unavailable_reason: str


_STEP_SPECS = (
    ("environment", "检查软件环境", "DEV-UI1", "无需实验数据。", ""),
    ("usage", "选择使用方式", "DEV-UI1", "选择入口和数据来源。", "本轮仅验证配置，不创建实验计划。"),
    ("plan", "制定实验计划", "DEV-UI2", "准备实验条件、方向、session 和重复定义。", "计划表单将在 DEV-UI2 实现。"),
    ("stimulus", "生成实验刺激", "DEV-UI2", "准备 Multisine 配置和新的 stimulus_id。", "刺激生成入口将在 DEV-UI2 实现。"),
    ("external_acquisition", "完成外部播放和录音", "DEV-UI2", "准备 REW、播放设备、录音设备和采集清单。", "外部设备说明与文件登记将在 DEV-UI2 实现。"),
    ("single_measurement", "导入并检查单次数据", "DEV-UI2", "准备 REW TXT，或 WAV、sidecar 与 stimulus manifest。", "双入口导入将在 DEV-UI2 实现。"),
    ("dataset", "检查完整实验数据集", "DEV-UI3", "准备显式 analysis scope 和条件矩阵。", "P2-B 编排将在 DEV-UI3 实现。"),
    ("comparison", "比较方向、配置和重复性", "DEV-UI3", "准备已通过门禁的 FeatureSet 和 P2-B authority。", "P3/P4 编排将在 DEV-UI3 实现。"),
    ("modeling", "分类、选频和校准", "DEV-UI3", "准备 training/development scope；final-test 保持封存。", "P5/P6/P9 编排将在 DEV-UI3 实现。"),
    ("freeze", "冻结分析方案", "DEV-UI3", "准备已批准的 authority 与冻结清单。", "冻结包编排将在 DEV-UI3 实现。"),
    ("final_test", "最终测试", "DEV-UI3", "等待独立批准；当前 final-test 保持封存。", "本轮不提供解封或执行入口。"),
    ("reports", "查看和导出报告", "DEV-UI4", "保留各阶段 immutable artifacts。", "完整报告浏览与导出将在 DEV-UI4 实现。"),
)


_ALLOWED_TRANSITIONS: dict[StepStatus, frozenset[StepStatus]] = {
    StepStatus.NOT_STARTED: frozenset(
        {StepStatus.READY, StepStatus.WAITING_EXTERNAL, StepStatus.BLOCKED}
    ),
    StepStatus.READY: frozenset(
        {StepStatus.RUNNING, StepStatus.NOT_STARTED, StepStatus.BLOCKED}
    ),
    StepStatus.WAITING_EXTERNAL: frozenset(
        {StepStatus.READY, StepStatus.NOT_STARTED, StepStatus.BLOCKED}
    ),
    StepStatus.RUNNING: frozenset(
        {
            StepStatus.PASSED,
            StepStatus.WARNING,
            StepStatus.MANUAL_REVIEW,
            StepStatus.BLOCKED,
            StepStatus.FAILED,
        }
    ),
    StepStatus.PASSED: frozenset({StepStatus.READY, StepStatus.NOT_STARTED}),
    StepStatus.WARNING: frozenset({StepStatus.READY, StepStatus.NOT_STARTED}),
    StepStatus.MANUAL_REVIEW: frozenset({StepStatus.READY, StepStatus.NOT_STARTED}),
    StepStatus.BLOCKED: frozenset({StepStatus.READY, StepStatus.NOT_STARTED}),
    StepStatus.FAILED: frozenset({StepStatus.READY, StepStatus.NOT_STARTED}),
}


class WizardState:
    """Owns UI navigation state but no scientific or provenance authority."""

    editable_context_fields = frozenset(
        {"data_origin", "measurement_mode", "run_purpose"}
    )

    def __init__(self) -> None:
        self.mode = UiMode.SIMPLE
        self.steps = [
            WizardStep(
                step_id=step_id,
                title=title,
                status=(StepStatus.READY if index == 0 else StepStatus.NOT_STARTED),
                implementation_round=implementation_round,
                preparation=preparation,
                unavailable_reason=reason,
            )
            for index, (step_id, title, implementation_round, preparation, reason)
            in enumerate(_STEP_SPECS)
        ]
        self.data_origin = "simulated"
        self.measurement_mode = "rew_sweep"
        self.run_purpose = "software_validation"

    def step(self, step_id: str) -> WizardStep:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        raise KeyError(step_id)

    def transition(self, step_id: str, target: StepStatus) -> None:
        step = self.step(step_id)
        if target not in _ALLOWED_TRANSITIONS[step.status]:
            raise InvalidStepTransition(
                f"invalid step transition: {step.status.value} -> {target.value}"
            )
        step.status = target

    def set_mode(self, mode: UiMode) -> None:
        self.mode = mode

    def select_usage(
        self,
        *,
        data_origin: str,
        measurement_mode: str,
        run_purpose: str,
    ) -> GateDecision:
        self.data_origin = data_origin
        self.measurement_mode = measurement_mode
        self.run_purpose = run_purpose
        step = self.step("single_measurement")
        if data_origin == "real_experiment" and measurement_mode == "schroeder_multisine":
            if step.status is not StepStatus.BLOCKED:
                if StepStatus.BLOCKED in _ALLOWED_TRANSITIONS[step.status]:
                    step.status = StepStatus.BLOCKED
            return GateDecision(False, HARD_BLOCK_REAL_MULTISINE_MESSAGE)
        if step.status is StepStatus.BLOCKED:
            step.status = StepStatus.NOT_STARTED
        return GateDecision(True, "当前选择未触发真实 Multisine/P8 硬门禁。")

    def unavailable_details(self, step_id: str) -> dict[str, str]:
        step = self.step(step_id)
        return {
            "implementation_round": step.implementation_round,
            "preparation": step.preparation,
            "reason": step.unavailable_reason,
        }
