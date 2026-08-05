"""Shared command-line orchestration for unified and mode-specific entry points."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import load_config
from .run_execution import execute_measurement_run
from .schemas import MeasurementMode


def pipeline_main(
    argv: list[str] | None = None,
    *,
    required_mode: MeasurementMode | None = None,
    project_root: Path,
) -> int:
    parser = argparse.ArgumentParser(
        description="Validate configuration or execute one auditable DEV-C measurement run."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--stimulus-manifest", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--run-id")
    arguments = parser.parse_args(argv)
    resolved = load_config(
        arguments.config,
        default_path=project_root / "config" / "default.yaml",
    )
    configured_mode = MeasurementMode(resolved["measurement_mode"])
    if required_mode is not None and configured_mode is not required_mode:
        parser.error(
            f"this entry point requires measurement_mode={required_mode.value}"
        )

    if arguments.validate_only or arguments.input is None:
        print(json.dumps(resolved, indent=2, sort_keys=True, ensure_ascii=False))
        if not arguments.validate_only:
            print(
                "DEV-C stage gate: configuration is valid; provide --input, "
                "--metadata, and --run-id to execute P1/P2-A/P8 plus dense "
                "P3-A/P3-B. P2-B requires an explicit dataset scope and input "
                "manifest; canonical P4-A additionally requires the matching "
                "P2-B result/hash. P4-B requires its explicit comparison scope; "
                "P5-A requires an explicit classification scope; P5-B/P6/P9 "
                "remain not implemented.",
                file=sys.stderr,
            )
        return 0

    if arguments.metadata is None:
        parser.error("--metadata is required when --input is provided")
    if arguments.run_id is None:
        parser.error("--run-id is required when --input is provided")
    output_root = (
        arguments.output_root
        if arguments.output_root is not None
        else Path(resolved["paths"]["outputs"])
    )
    result = execute_measurement_run(
        arguments.input,
        arguments.metadata,
        resolved,
        output_root=output_root,
        run_id=arguments.run_id,
        stimulus_manifest=arguments.stimulus_manifest,
    )
    print(
        json.dumps(
            {
                "run_id": arguments.run_id,
                "output_directory": result.output_directory.as_posix(),
                "processing_status": result.processing_status,
                "success": result.success,
                "qc_status": result.run_manifest["qc_status"],
                "stage_gate": result.run_manifest["stage_gate"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(
        "DEV-C stage gate reached: P2-A and dense P3-A/P3-B are available; "
        "P2-B requires an explicit dataset scope and canonical P4-A requires "
        "the matching P2-B result/hash. P4-B requires its explicit comparison "
        "scope; P5-A requires an explicit classification scope, while "
        "P5-B/P6/P9 remain not implemented.",
        file=sys.stderr,
    )
    if result.processing_status == "completed" and result.success:
        return 0
    if result.processing_status == "manual_review_required":
        return 2
    if result.processing_status == "blocked_research_gate":
        return 3
    if result.processing_status == "completed":
        return 4
    return 1
