"""Frozen-safe command dispatcher for UI background jobs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


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
    del workspace_root  # Outputs remain explicit arguments; no directory scanning.
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
        )
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0 if result["software_integration_ready"] else 2
    if task in {"pipeline_sweep", "pipeline_multisine"}:
        from acoustic_encoder.pipeline_cli import pipeline_main
        from acoustic_encoder.schemas import MeasurementMode

        required = None if task == "pipeline_sweep" else MeasurementMode.SCHROEDER_MULTISINE
        return pipeline_main(arguments, required_mode=required, project_root=Path(project_root))
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
