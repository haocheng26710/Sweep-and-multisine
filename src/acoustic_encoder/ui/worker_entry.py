"""Frozen-safe command dispatcher for UI background jobs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Callable, Sequence, TextIO


def _package(argv: Sequence[str]) -> dict[str, object]:
    from acoustic_encoder.offline_readout_cli import build_readout_package_from_manifest

    parser = argparse.ArgumentParser(description="Build one immutable P9-D readout package")
    parser.add_argument("--config", required=True)
    parser.add_argument("--training-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    return build_readout_package_from_manifest(args.config, args.training_manifest, args.output)


def _offline(argv: Sequence[str]) -> dict[str, object]:
    from acoustic_encoder.offline_readout_cli import execute_offline_readout_from_manifest

    parser = argparse.ArgumentParser(description="Run one frozen-package offline direction readout")
    parser.add_argument("--package", required=True)
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    return execute_offline_readout_from_manifest(args.package, args.input_manifest, args.output)


def dispatch_worker(
    task: str,
    argv: Sequence[str],
    *,
    resource_root: str | Path,
    workspace_root: str | Path,
) -> int:
    """Run one authoritative backend entry point and print structured output."""
    arguments = list(argv)
    project_root = str(Path(resource_root).resolve())
    if task in {"p9a", "p9b", "p9c"} and "--project-root" not in arguments:
        arguments.extend(["--project-root", project_root])
    if task == "acceptance":
        from acoustic_encoder.pre_experiment_acceptance_runner import run_pre_experiment_acceptance

        parser = argparse.ArgumentParser(description="Run DEV-C16 T0-T3 pre-experiment acceptance")
        parser.add_argument("--project-root", default=project_root)
        parser.add_argument("--config", required=True)
        parser.add_argument("--output-root", required=True)
        parser.add_argument("--run-id", required=True)
        args = parser.parse_args(arguments)
        result = run_pre_experiment_acceptance(
            project_root=Path(args.project_root), config_path=Path(args.config),
            output_root=Path(args.output_root), run_id=args.run_id,
            packaged_runtime=bool(getattr(sys, "frozen", False)),
        )
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0 if result["overall_status"] == "pass" else 2
    if task in {"pipeline_sweep", "pipeline_multisine"}:
        from acoustic_encoder.pipeline_cli import pipeline_main
        from acoustic_encoder.schemas import MeasurementMode

        required = None if task == "pipeline_sweep" else MeasurementMode.SCHROEDER_MULTISINE
        return pipeline_main(arguments, required_mode=required, project_root=Path(project_root))
    if task == "simulated_batch":
        from acoustic_encoder.ui.simulated_flow import SimulatedFlowService

        parser = argparse.ArgumentParser(description="Process explicit FIX6 simulated batch")
        parser.add_argument("--acquisition-manifest", required=True)
        parser.add_argument("--processing-id")
        parser.add_argument("--cancel-file")
        args = parser.parse_args(arguments)
        service = SimulatedFlowService(project_root, workspace_root)

        def report(event: object) -> None:
            print(json.dumps(event, sort_keys=True, ensure_ascii=False), flush=True)

        result = service.process_simulated_batch(
            args.acquisition_manifest,
            processing_id=args.processing_id,
            cancel_requested=(
                None
                if args.cancel_file is None
                else lambda: Path(args.cancel_file).is_file()
            ),
            progress=report,
        )
        print(
            json.dumps(
                {
                    "event": "batch_finished",
                    "status": result.status,
                    "processed_count": result.processed_count,
                    "manifest_path": result.manifest_path.as_posix(),
                },
                sort_keys=True,
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0 if result.status == "passed" else 2
    if task == "p2b":
        from acoustic_encoder.dataset_quality_cli import run_dataset_quality_cli

        return run_dataset_quality_cli(arguments, project_root=Path(project_root))
    if task == "p4":
        from acoustic_encoder.comparison_metrics_cli import run_comparison_metrics_cli

        return run_comparison_metrics_cli(arguments, project_root=Path(project_root))
    if task == "p5a":
        from acoustic_encoder.classification_cli import run_classification_cli

        return run_classification_cli(arguments, project_root=Path(project_root))
    if task == "p5b":
        from acoustic_encoder.cross_mode_classification_cli import run_cross_mode_classification_cli

        return run_cross_mode_classification_cli(arguments, project_root=Path(project_root))
    if task == "p6a":
        from acoustic_encoder.hr_cli import main

        return main(arguments)
    if task == "p6b":
        from acoustic_encoder.hr_readout_cli import main

        return main(arguments)
    if task == "p9a":
        from acoustic_encoder.tone_selection_cli import main

        return main(arguments)
    if task == "p9b":
        from acoustic_encoder.projection_ablation_cli import run_projection_ablation_command

        result = run_projection_ablation_command(arguments)
    elif task == "p9c":
        from acoustic_encoder.cross_mode_bridge_cli import run_cross_mode_bridge_command

        result = run_cross_mode_bridge_command(arguments)
    elif task == "p9d":
        result = _package(arguments)
    elif task == "offline":
        result = _offline(arguments)
    else:
        raise ValueError(f"unknown UI worker task: {task}")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


def _acceptance_failure_log(argv: Sequence[str], workspace_root: Path) -> Path:
    arguments = list(argv)

    def value(name: str) -> str | None:
        try:
            return arguments[arguments.index(name) + 1]
        except (ValueError, IndexError):
            return None

    output = Path(value("--output-root") or workspace_root / "outputs").resolve()
    run_id = value("--run-id") or "worker-failure"
    safe_run_id = run_id if Path(run_id).name == run_id else "worker-failure"
    return (
        output
        / "simulated"
        / "software_validation"
        / safe_run_id
        / "acceptance"
        / "technical_log.txt"
    )


def _emit_stderr(payload: dict[str, object], stream: TextIO | None) -> None:
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    if stream is not None:
        stream.write(line)
        stream.flush()
        return
    try:
        if sys.stderr is not None:
            sys.stderr.write(line)
            sys.stderr.flush()
        else:
            os.write(2, line.encode("utf-8", errors="replace"))
    except OSError:
        pass


def run_worker_safely(
    task: str,
    argv: Sequence[str],
    *,
    resource_root: str | Path,
    workspace_root: str | Path,
    dispatcher: Callable[..., int] = dispatch_worker,
    error_stream: TextIO | None = None,
) -> int:
    """Prevent a frozen worker exception from reaching the bootloader dialog."""
    try:
        return dispatcher(
            task,
            argv,
            resource_root=resource_root,
            workspace_root=workspace_root,
        )
    except Exception as exc:  # top-level application boundary
        technical = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        log_path = _acceptance_failure_log(list(argv), Path(workspace_root).resolve())
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(technical, encoding="utf-8")
            log_value: str | None = str(log_path)
        except OSError:
            log_value = None
        payload: dict[str, object] = {
            "schema_version": "1.0.0",
            "status": "failed",
            "error_code": "worker_unexpected_exception",
            "task": task,
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "traceback": technical,
            "technical_log": log_value,
            "scientifically_eligible": False,
            "final_test_read": False,
        }
        _emit_stderr(payload, error_stream)
        return 70
