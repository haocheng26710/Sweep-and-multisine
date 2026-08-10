"""Application services that adapt existing validated backend APIs for the UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Callable, Iterable, Mapping

from acoustic_encoder.config import ConfigError, load_config
from acoustic_encoder.pre_experiment_acceptance_outputs import load_acceptance_bundle


class EnvironmentCheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EnvironmentCheckItem:
    check_id: str
    label: str
    status: EnvironmentCheckStatus
    value: str
    user_message: str
    technical_detail: str = ""


@dataclass(frozen=True, slots=True)
class EnvironmentReport:
    project_root: Path
    python_version: str
    git_commit: str
    git_worktree_clean: bool | None
    checks: tuple[EnvironmentCheckItem, ...]

    @property
    def passed(self) -> bool:
        return all(item.status is EnvironmentCheckStatus.PASSED for item in self.checks)

    def item(self, check_id: str) -> EnvironmentCheckItem:
        for item in self.checks:
            if item.check_id == check_id:
                return item
        raise KeyError(check_id)


@dataclass(frozen=True, slots=True)
class ConfigValidationResult:
    success: bool
    config_path: Path
    measurement_mode: str | None
    pipeline_version: str | None
    schema_versions: Mapping[str, str]
    run_purpose: str | None
    provisional: bool | None
    migration_warnings: tuple[str, ...]
    user_message: str
    technical_detail: str


@dataclass(frozen=True, slots=True)
class AcceptanceSummary:
    output_directory: Path
    report_path: Path
    stage_statuses: Mapping[str, str]
    v2_requirement_pass_count: int
    v2_requirement_total: int
    overall_status: str
    test_status: str
    test_passed_count: int | None
    test_summary: str
    software_integration_ready: bool
    ready_for_dev_d_diagnostic_experiment: bool
    scientifically_eligible: bool


def humanize_exception(exc: BaseException) -> tuple[str, str]:
    technical = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    message = str(exc).casefold()
    if "p8-a" in message and "simulated/software_validation" in message:
        return (
            "当前 P8-A 真实 Multisine 分析门禁仍关闭；录音只能登记，不能运行 P8。",
            technical,
        )
    if "final_test" in message or "final-test" in message:
        return (
            "检测到 final-test 封存边界；当前操作已停止、内容未读，并需要人工审核 incident。",
            technical,
        )
    if "canonical-ready p2-b" in message or "canonical-ready" in message:
        return "P2-B 尚未通过 canonical-ready 门禁；后续正式分析保持锁定。", technical
    if "large plan" in message or "异常大的计划" in str(exc):
        return "预计样本数量较大；请复核矩阵并进行第二次确认。", technical
    if isinstance(exc, FileNotFoundError):
        return "找不到所需文件。请确认路径后重试。", technical
    if isinstance(exc, ConfigError):
        return "配置未通过现有 schema 验证。请检查详细错误。", technical
    if isinstance(exc, PermissionError):
        return "没有读取输入或写入新输出目录的权限。", technical
    if isinstance(exc, FileExistsError):
        return "输出 run-id 已存在。请生成新的 run-id；界面不会覆盖旧结果。", technical
    if "hash" in message or "sha-256" in message:
        return "输入 SHA-256 与登记值不一致；请恢复原文件或重新登记。", technical
    exception_name = type(exc).__name__.casefold()
    if (
        "manual review" in message
        or "manual_review" in message
        or "manualreview" in exception_name
    ):
        return "该输入需要人工确认；请查看原因并保留审核记录。", technical
    readable_patterns = (
        (("impedance", "ohm"), "所选 REW 文件是阻抗数据，不能进入声学 SPL 路径。"),
        (("empty",), "所选文件为空；请选择包含测量数据的文件。"),
        (("extension", ".txt", ".wav"), "文件扩展名不受当前入口支持；请重新选择正确类型。"),
        (("strictly increasing", "at least 5"), "频率点不足或未严格递增；请检查导出格式。"),
        (("channel",), "所选 WAV 通道不存在；请检查通道编号。"),
        (("sample rate",), "WAV 与 stimulus manifest 的采样率不一致。"),
        (("stimulus_id", "stimulus hash", "tone_set"), "刺激 ID、tone set 或刺激 hash 不一致。"),
        (("timezone",), "date_time 必须包含明确时区。"),
        (("angle_deg",), "角度字段无效；请输入 schema 允许的角度。"),
    )
    for needles, user_message in readable_patterns:
        if any(needle in message for needle in needles):
            return user_message, technical
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return "输入字段或 schema 验证失败；请按技术详情修正后重试。", technical
    return "发生未知错误，操作已安全停止，未写入成功标记。", technical


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


class ApplicationServices:
    """Read-only preflight/config services plus acceptance result loading."""

    DEFAULT_REQUIRED_MODULES = (
        "numpy",
        "pandas",
        "scipy",
        "matplotlib",
        "sklearn",
        "yaml",
        "joblib",
        "PySide6",
    )

    def __init__(
        self,
        project_root: str | Path,
        *,
        required_modules: Iterable[str] | None = None,
        module_importer: Callable[[str], Any] = importlib.import_module,
        git_runner: Callable[[list[str], Path], Any] = _run_git,
        acceptance_loader: Callable[[str | Path], Any] = load_acceptance_bundle,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.required_modules = tuple(
            self.DEFAULT_REQUIRED_MODULES if required_modules is None else required_modules
        )
        self._module_importer = module_importer
        self._git_runner = git_runner
        self._acceptance_loader = acceptance_loader

    def check_environment(self) -> EnvironmentReport:
        checks: list[EnvironmentCheckItem] = []

        def add(
            check_id: str,
            label: str,
            passed: bool,
            value: object,
            user_message: str,
            technical_detail: str = "",
        ) -> None:
            checks.append(
                EnvironmentCheckItem(
                    check_id=check_id,
                    label=label,
                    status=(
                        EnvironmentCheckStatus.PASSED
                        if passed
                        else EnvironmentCheckStatus.FAILED
                    ),
                    value=str(value),
                    user_message=user_message,
                    technical_detail=technical_detail,
                )
            )

        python_version = ".".join(str(value) for value in sys.version_info[:3])
        add("python_version", "Python 版本", sys.version_info >= (3, 11), python_version,
            "Python 3.11 或更高版本可用。" if sys.version_info >= (3, 11) else "需要 Python 3.11 或更高版本。")
        add("project_root", "项目根目录", self.project_root.is_dir(), self.project_root,
            "项目根目录可访问。" if self.project_root.is_dir() else "项目根目录不存在。")

        commit = "unavailable"
        clean: bool | None = None
        try:
            commit_result = self._git_runner(
                ["git", "rev-parse", "HEAD"], self.project_root
            )
            status_result = self._git_runner(
                ["git", "status", "--porcelain"], self.project_root
            )
            commit_ok = commit_result.returncode == 0
            status_ok = status_result.returncode == 0
            if commit_ok:
                commit = commit_result.stdout.strip()
            if status_ok:
                clean = not bool(status_result.stdout.strip())
            add("git_commit", "Git commit", commit_ok, commit,
                "已读取当前 Git commit。" if commit_ok else "无法读取 Git commit。",
                commit_result.stderr.strip())
            add("git_worktree", "Git 工作树", status_ok, "clean" if clean else "dirty",
                ("工作树干净。" if clean else "工作树有未提交变更。") if status_ok else "无法读取工作树状态。",
                status_result.stderr.strip())
        except OSError as exc:
            _, technical = humanize_exception(exc)
            add("git_commit", "Git commit", False, commit, "无法运行 Git 只读检查。", technical)
            add("git_worktree", "Git 工作树", False, "unavailable", "无法运行 Git 只读检查。", technical)

        for module_name in self.required_modules:
            try:
                self._module_importer(module_name)
            except (ImportError, OSError) as exc:
                _, technical = humanize_exception(exc)
                add(
                    f"dependency:{module_name}",
                    f"依赖 {module_name}",
                    False,
                    "missing",
                    f"缺少依赖 {module_name}。请安装 UI 依赖后重试。",
                    technical,
                )
            else:
                add(
                    f"dependency:{module_name}",
                    f"依赖 {module_name}",
                    True,
                    "available",
                    f"依赖 {module_name} 可导入。",
                )

        config_paths = {
            "config_default": self.project_root / "config/default.yaml",
            "config_sweep": self.project_root / "config/experiment_v2_u4.yaml",
            "config_multisine": self.project_root / "config/experiment_v2_u4_multisine.yaml",
        }
        labels = {
            "config_default": "默认配置",
            "config_sweep": "Sweep 配置",
            "config_multisine": "Multisine 配置",
        }
        for check_id, path in config_paths.items():
            exists = path.is_file()
            add(check_id, labels[check_id], exists, path,
                "配置文件存在。" if exists else "配置文件缺失。")

        outputs = self.project_root / "outputs"
        target = outputs if outputs.exists() else outputs.parent
        writable = target.is_dir() and os.access(target, os.W_OK)
        add(
            "outputs_writable",
            "输出目录可写",
            writable,
            outputs,
            "outputs 可写；运行仍会创建唯一目录且拒绝覆盖。"
            if writable
            else "outputs 或其父目录不可写。",
        )
        return EnvironmentReport(
            project_root=self.project_root,
            python_version=python_version,
            git_commit=commit,
            git_worktree_clean=clean,
            checks=tuple(checks),
        )

    def validate_config(
        self,
        config_path: str | Path,
        *,
        expected_mode: str,
    ) -> ConfigValidationResult:
        path = Path(config_path).resolve()
        try:
            resolved = load_config(
                path,
                default_path=self.project_root / "config/default.yaml",
            )
            actual_mode = str(resolved["measurement_mode"])
            if actual_mode != expected_mode:
                raise ConfigError(
                    "配置入口不匹配："
                    f"期望 {expected_mode!r}，实际 {actual_mode!r}"
                )
            provisional_blocks = tuple(
                sorted(
                    key
                    for key, value in resolved.items()
                    if isinstance(value, Mapping) and value.get("provisional") is True
                )
            )
            warnings = tuple(
                str(item)
                for item in resolved.get("_runtime", {}).get("migration_warnings", ())
            )
            return ConfigValidationResult(
                success=True,
                config_path=path,
                measurement_mode=actual_mode,
                pipeline_version=str(resolved["pipeline_version"]),
                schema_versions=dict(resolved["schema_versions"]),
                run_purpose=str(resolved["run_purpose"]),
                provisional=bool(provisional_blocks),
                migration_warnings=warnings,
                user_message="配置已通过现有加载与 schema 验证。",
                technical_detail=(
                    "provisional_blocks=" + ",".join(provisional_blocks)
                ),
            )
        except Exception as exc:  # application boundary: preserve safe UI result
            user_message, technical = humanize_exception(exc)
            if isinstance(exc, ConfigError) and "配置入口不匹配" in str(exc):
                user_message = str(exc)
            return ConfigValidationResult(
                success=False,
                config_path=path,
                measurement_mode=None,
                pipeline_version=None,
                schema_versions={},
                run_purpose=None,
                provisional=None,
                migration_warnings=(),
                user_message=user_message,
                technical_detail=technical,
            )

    def load_acceptance_summary(
        self, output_directory: str | Path
    ) -> AcceptanceSummary:
        output = Path(output_directory).resolve()
        result, manifest = self._acceptance_loader(output)
        if bool(manifest.get("software_integration_ready")) != bool(
            result.software_integration_ready
        ):
            raise ValueError("acceptance readiness differs from verified manifest")
        audit_path = output / "leakage_and_provenance_audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        full_pytest = (
            audit.get("supporting_validation", {})
            .get("verification_commands", {})
            .get("full_pytest", {})
        )
        pass_count = sum(
            getattr(item.status, "value", str(item.status)) == "pass"
            for item in result.requirement_checks
        )
        return AcceptanceSummary(
            output_directory=output,
            report_path=output / "pre_experiment_acceptance_report.md",
            stage_statuses={
                item.check_id: getattr(item.status, "value", str(item.status))
                for item in result.stage_checks
            },
            v2_requirement_pass_count=pass_count,
            v2_requirement_total=len(result.requirement_checks),
            overall_status=getattr(
                result.overall_status, "value", str(result.overall_status)
            ),
            test_status=str(full_pytest.get("status", "unavailable")),
            test_passed_count=(
                int(full_pytest["passed_count"])
                if full_pytest.get("passed_count") is not None
                else None
            ),
            test_summary=str(full_pytest.get("summary_tail", "unavailable")),
            software_integration_ready=bool(result.software_integration_ready),
            ready_for_dev_d_diagnostic_experiment=bool(
                result.ready_for_dev_d_diagnostic_experiment
            ),
            scientifically_eligible=bool(result.scientifically_eligible),
        )
