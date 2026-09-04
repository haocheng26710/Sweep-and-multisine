"""Science-blind CLI for the frozen GEN-ENC-2 timing preflight.

The only mode is ``timing-preflight``.  ``--contract-check-only`` validates
the exact workload without importing or calling the forward compute core.
Formal execution remains authorization-gated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import psutil
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MODEL_NAME = "PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1"
HAND_01_FILE_SHA256 = "313c55e1517b9ef62c7e98918b7544cd6ad45836a21e82cddf59b4b571100857"
HAND_01_MEMBER_SHA256 = "8180161b8f8611050a57adce28fca45fdb0e0fd70050d73c8ceb1798b6bb62a0"
EXPECTED_STATES = [0, 90, 180, 270]
EXPECTED_VALIDATION_ANGLES = list(range(0, 360, 15))
EXPECTED_CELLS = 3675
EXPECTED_REPEATS = 2
EXPECTED_PORTS = 4
EXPECTED_FREQUENCIES = 256
REPRESENTATIVE_COMPLEX_VALUE_COUNT = EXPECTED_CELLS * EXPECTED_REPEATS * len(EXPECTED_STATES) * EXPECTED_PORTS * EXPECTED_FREQUENCIES
FORMAL_COMPLEX_VALUE_COUNT = 4 * 20 * EXPECTED_CELLS * EXPECTED_REPEATS * (4 + 24) * EXPECTED_PORTS * EXPECTED_FREQUENCIES
CPU_HARD_STOP_HOURS = 20.0
WALL_HARD_STOP_HOURS = 10.0
MEMORY_HARD_STOP_GIB = 8.0
PROJECTION_MULTIPLIER = 560


class PreflightError(RuntimeError):
    """Fail-closed command or input error."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PreflightError(f"JSON_OBJECT_REQUIRED:{path.as_posix()}")
    return value


def _nuisance_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        first = handle.readline()
        if not first.startswith("# addendum_metadata:"):
            raise PreflightError("NUISANCE_METADATA_HEADER_REQUIRED")
        rows = list(csv.DictReader(handle))
    expected_ids = [f"N{index:04d}" for index in range(1, EXPECTED_CELLS + 1)]
    if len(rows) != EXPECTED_CELLS or [row.get("design_row_id") for row in rows] != expected_ids:
        raise PreflightError("EXACT_3675_NUISANCE_ROWS_REQUIRED")
    return rows


def _validate_contract_inputs(args: argparse.Namespace) -> dict[str, Any]:
    member_path = Path(args.member)
    if _sha256(member_path) != HAND_01_FILE_SHA256:
        raise PreflightError("HAND_01_FILE_HASH_MISMATCH")
    member = _json(member_path)
    if (
        member.get("member_id") != "HAND_01"
        or member.get("family_id") != "HAND_DESIGNED"
        or member.get("global_ordinal") != 1
        or member.get("member_sha256") != HAND_01_MEMBER_SHA256
    ):
        raise PreflightError("HAND_01_IDENTITY_MISMATCH")
    final92 = _json(Path(args.final92_review))
    if final92.get("verdict") != "ACCEPT" or final92.get("final_test_read") is not False:
        raise PreflightError("FINAL92_REVIEW_NOT_ACCEPTED_OR_SEALED")
    profile = _json(Path(args.profile))
    if profile.get("common_observable", {}).get("design_angles_degrees") != EXPECTED_STATES:
        raise PreflightError("FOUR_STATE_PROFILE_MISMATCH")
    if profile.get("final_test_read") is not False:
        raise PreflightError("PROFILE_FINAL_TEST_NOT_SEALED")
    matched = _json(Path(args.matched_cost))
    if matched.get("interface", {}).get("states") != 4:
        raise PreflightError("MATCHED_COST_STATE_MISMATCH")
    frequency = _json(Path(args.frequency_contract))
    if frequency.get("secondary_sensitivity", {}).get("point_count") != EXPECTED_FREQUENCIES:
        raise PreflightError("FREQUENCY_COUNT_MISMATCH")
    nuisance_contract = _json(Path(args.nuisance_contract))
    deterministic = nuisance_contract.get("deterministic_design", {})
    if deterministic.get("cell_count") != EXPECTED_CELLS or deterministic.get("repeats_per_cell_development") != EXPECTED_REPEATS:
        raise PreflightError("NUISANCE_CONTRACT_WORKLOAD_MISMATCH")
    seeds = _json(Path(args.seed_split))
    if seeds.get("nuisance_partition_seeds", {}).get("development_training") != [2026091001, 2026091002]:
        raise PreflightError("DEVELOPMENT_REPEAT_SEEDS_MISMATCH")
    if seeds.get("nuisance_partition_seeds", {}).get("single_use_validation") != [2026092001, 2026092002]:
        raise PreflightError("VALIDATION_REPEAT_SEEDS_MISMATCH")
    expected_seeds = [2026091001, 2026091002] if args.partition == "development" else [2026092001, 2026092002]
    expected_angles = EXPECTED_STATES if args.partition == "development" else EXPECTED_VALIDATION_ANGLES
    if args.repeat_seeds != expected_seeds:
        raise PreflightError("PARTITION_REPEAT_SEED_ROUTING_MISMATCH")
    if args.angles != expected_angles:
        raise PreflightError("PARTITION_FROZEN_ANGLE_ORDER_MISMATCH")
    rows = _nuisance_rows(Path(args.nuisance_csv))
    if args.frequency_block_size < 1 or EXPECTED_FREQUENCIES % args.frequency_block_size:
        raise PreflightError("FREQUENCY_BLOCK_MUST_DIVIDE_256")
    if args.checkpoint_unit_interval < 1:
        raise PreflightError("CHECKPOINT_INTERVAL_MUST_BE_POSITIVE")
    return {"member": member, "rows": rows}


def _validate_source_manifest(path: Path) -> str:
    manifest = _json(path)
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise PreflightError("SOURCE_MANIFEST_ENTRIES_REQUIRED")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "bytes", "role"}:
            raise PreflightError("SOURCE_MANIFEST_ENTRY_SCHEMA")
        source = REPO / entry["path"]
        if _sha256(source) != entry["sha256"] or source.stat().st_size != entry["bytes"]:
            raise PreflightError(f"SOURCE_MANIFEST_MISMATCH:{entry['path']}")
    return _sha256(path)


def _validate_execution_authorization(args: argparse.Namespace) -> dict[str, str]:
    required_paths = (args.contract, args.command_manifest, args.source_manifest, args.result_schema, args.authorization)
    if any(value is None for value in required_paths):
        raise PreflightError("FORMAL_BINDING_ARGUMENTS_REQUIRED")
    source_manifest_sha = _validate_source_manifest(Path(args.source_manifest))
    bindings = {
        "contract_sha256": _sha256(Path(args.contract)),
        "command_manifest_sha256": _sha256(Path(args.command_manifest)),
        "source_manifest_sha256": source_manifest_sha,
        "result_schema_sha256": _sha256(Path(args.result_schema)),
    }
    authorization = _json(Path(args.authorization))
    if (
        authorization.get("record_kind") != "GEN_ENC_2_TIMING_PREFLIGHT_EXECUTION_AUTHORIZATION"
        or authorization.get("guardian_approved") is not True
        or authorization.get("execution_authorized") is not True
        or authorization.get("timing_preflight_authorized") is not True
        or authorization.get("solver_execution_authorized") is not True
        or authorization.get("gen_enc_2_e2_authorized") is not False
        or authorization.get("final_test_read") is not False
        or authorization.get("member_id") != "HAND_01"
        or authorization.get("bound_sha256") != bindings
    ):
        raise PreflightError("GUARDIAN_EXECUTION_AUTHORIZATION_INVALID")
    return bindings


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def validate_and_publish_terminal_result(result: dict[str, Any], schema_path: Path, result_path: Path) -> None:
    """Validate the exact terminal object before its only atomic publication."""

    try:
        schema = _json(schema_path)
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(result),
            key=lambda error: tuple(str(part) for part in error.path),
        )
    except (SchemaError, OSError, ValueError) as exc:
        raise PreflightError("RESULT_SCHEMA_UNAVAILABLE_OR_INVALID") from exc
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.path) or "$"
        raise PreflightError(f"RESULT_SCHEMA_VALIDATION_FAILED:{location}:{first.validator}")
    _atomic_json(result_path, result)


def _contract_check(args: argparse.Namespace) -> int:
    _validate_contract_inputs(args)
    output_root = Path(args.output_root)
    if output_root.exists() and any(output_root.iterdir()):
        raise PreflightError("CONTRACT_CHECK_OUTPUT_ROOT_NOT_EMPTY")
    report = {
        "schema_version": "gen_enc_2_timing_preflight_contract_check_v2",
        "record_kind": "SCIENCE_BLIND_NO_RUN_CONTRACT_CHECK",
        "status": "PASS",
        "model_name": MODEL_NAME,
        "member_id": "HAND_01",
        "complete_units": EXPECTED_CELLS * EXPECTED_REPEATS,
        "nuisance_cells": EXPECTED_CELLS,
        "repeats_per_cell": EXPECTED_REPEATS,
        "states": len(EXPECTED_STATES),
        "ports": EXPECTED_PORTS,
        "computed_frequencies": EXPECTED_FREQUENCIES,
        "representative_complex_value_count": REPRESENTATIVE_COMPLEX_VALUE_COUNT,
        "frequency_block_size": args.frequency_block_size,
        "frequency_blocks_per_unit": EXPECTED_FREQUENCIES // args.frequency_block_size,
        "checkpoint_unit_interval": args.checkpoint_unit_interval,
        "projection_multiplier": FORMAL_COMPLEX_VALUE_COUNT // REPRESENTATIVE_COMPLEX_VALUE_COUNT,
        "forbidden_artifact_count": 0,
        "timing_executed": False,
        "solver_executed": False,
        "run_id": None,
        "final_test_read": False,
    }
    _atomic_json(output_root / "contract_check.json", report)
    return 0


def _checkpoint_path(args: argparse.Namespace) -> Path:
    relative = Path(args.checkpoint)
    if relative.is_absolute() or len(relative.parts) != 1 or relative.name != "checkpoint.json":
        raise PreflightError("CHECKPOINT_PATH_MUST_BE_LITERAL_CHECKPOINT_JSON")
    return Path(args.output_root) / relative


def _nuisance_values(row: dict[str, str]) -> dict[str, float]:
    names = (
        "snr_db",
        "common_gain_db",
        "sensor_independent_gain_db",
        "common_frequency_axis_shift_relative",
        "independent_manufacturing_percent",
        "batch_correlated_manufacturing_percent",
        "angle_offset_degrees",
    )
    try:
        return {name: float(row[name]) for name in names}
    except (KeyError, ValueError) as exc:
        raise PreflightError("NUISANCE_ROW_NUMERIC_SCHEMA") from exc


def _resource_snapshot(process: psutil.Process, wall_seconds: float, cpu_seconds: float, peak_gib: float) -> tuple[float, float, float]:
    current_peak = max(peak_gib, process.memory_info().rss / (1024.0**3))
    return wall_seconds, cpu_seconds, current_peak


def _write_checkpoint(
    path: Path,
    *,
    bindings: dict[str, str],
    next_unit_index: int,
    wall_time_seconds: float,
    cpu_time_seconds: float,
    aggregate_peak_memory_gib: float,
) -> None:
    _atomic_json(
        path,
        {
            "schema_version": "gen_enc_2_timing_preflight_checkpoint_freeze_03_v1",
            "record_kind": "SCIENCE_BLIND_CHECKPOINT",
            "member_id": "HAND_01",
            "bound_sha256": bindings,
            "next_unit_index": next_unit_index,
            "complete_units": next_unit_index,
            "expected_units": 7350,
            "states": 4,
            "ports": 4,
            "computed_frequencies": 256,
            "representative_complex_value_count": 30105600,
            "wall_time_seconds": wall_time_seconds,
            "cpu_time_seconds": cpu_time_seconds,
            "aggregate_peak_memory_gib": aggregate_peak_memory_gib,
            "numerically_valid_so_far": True,
            "solver_exit_code_so_far": 0,
            "run_id": None,
            "final_test_read": False,
        },
    )


def _formal_timing_preflight(args: argparse.Namespace) -> int:
    if args.partition != "development":
        raise PreflightError("TIMING_PREFLIGHT_DEVELOPMENT_PARTITION_ONLY")
    validated = _validate_contract_inputs(args)
    bindings = _validate_execution_authorization(args)
    output_root = Path(args.output_root)
    checkpoint_path = _checkpoint_path(args)
    result_path = output_root / "preflight_result.json"
    if result_path.exists():
        raise PreflightError("TERMINAL_RESULT_ALREADY_EXISTS")

    start_unit = 0
    prior_wall = 0.0
    prior_cpu = 0.0
    peak_gib = 0.0
    if args.resume and checkpoint_path.exists():
        checkpoint = _json(checkpoint_path)
        if (
            checkpoint.get("record_kind") != "SCIENCE_BLIND_CHECKPOINT"
            or checkpoint.get("member_id") != "HAND_01"
            or checkpoint.get("bound_sha256") != bindings
            or checkpoint.get("run_id") is not None
            or checkpoint.get("final_test_read") is not False
        ):
            raise PreflightError("CHECKPOINT_BINDING_MISMATCH")
        start_unit = int(checkpoint.get("next_unit_index", -1))
        prior_wall = float(checkpoint.get("wall_time_seconds", -1.0))
        prior_cpu = float(checkpoint.get("cpu_time_seconds", -1.0))
        peak_gib = float(checkpoint.get("aggregate_peak_memory_gib", -1.0))
        if not 0 <= start_unit <= 7350 or min(prior_wall, prior_cpu, peak_gib) < 0.0:
            raise PreflightError("CHECKPOINT_COUNTS_INVALID")
    else:
        if output_root.exists() and any(output_root.iterdir()):
            raise PreflightError("OUTPUT_ROOT_NOT_EMPTY_WITHOUT_RESUME")
        output_root.mkdir(parents=True, exist_ok=True)

    from acoustic_encoder.gen_enc.forward_acoustic_network import (
        ForwardCoreError,
        frozen_frequency_grid,
        solve_forward_block,
    )

    process = psutil.Process()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    completed_units = start_unit
    verdict = "FEASIBLE"
    numerical_valid = True
    exit_code = 0
    nuisance_rows = [_nuisance_values(row) for row in validated["rows"]]
    member = validated["member"]
    frequencies = frozen_frequency_grid()
    try:
        for unit_index in range(start_unit, 7350):
            cell_index, repeat_index = divmod(unit_index, 2)
            nuisance = nuisance_rows[cell_index]
            for frequency_start in range(0, 256, args.frequency_block_size):
                block = solve_forward_block(
                    member,
                    nuisance,
                    cell_index=cell_index,
                    repeat_index=repeat_index,
                    frequencies_hz=frequencies[frequency_start : frequency_start + args.frequency_block_size],
                    frequency_start_index=frequency_start,
                    state_angles_degrees=tuple(float(value) for value in args.angles),
                    partition=args.partition,
                    repeat_seed_tuple=tuple(args.repeat_seeds),
                )
                numerical_valid = numerical_valid and block.numerically_valid and block.solvable
                del block
            completed_units = unit_index + 1
            elapsed_wall = prior_wall + time.perf_counter() - wall_start
            elapsed_cpu = prior_cpu + time.process_time() - cpu_start
            _, _, peak_gib = _resource_snapshot(process, elapsed_wall, elapsed_cpu, peak_gib)
            if (
                elapsed_wall / 3600.0 >= WALL_HARD_STOP_HOURS
                or elapsed_cpu / 3600.0 >= CPU_HARD_STOP_HOURS
                or peak_gib >= MEMORY_HARD_STOP_GIB
            ):
                verdict = "RESOURCE_BLOCKED"
                break
            if completed_units % args.checkpoint_unit_interval == 0:
                _write_checkpoint(
                    checkpoint_path,
                    bindings=bindings,
                    next_unit_index=completed_units,
                    wall_time_seconds=elapsed_wall,
                    cpu_time_seconds=elapsed_cpu,
                    aggregate_peak_memory_gib=peak_gib,
                )
    except ForwardCoreError:
        verdict = "NUMERICALLY_BLOCKED"
        numerical_valid = False
        exit_code = 2

    wall_seconds = prior_wall + time.perf_counter() - wall_start
    cpu_seconds = prior_cpu + time.process_time() - cpu_start
    _, _, peak_gib = _resource_snapshot(process, wall_seconds, cpu_seconds, peak_gib)
    projected_cpu = cpu_seconds / 3600.0 * PROJECTION_MULTIPLIER
    projected_wall = wall_seconds / 3600.0 * PROJECTION_MULTIPLIER
    within_projection = (
        projected_cpu < CPU_HARD_STOP_HOURS
        and projected_wall < WALL_HARD_STOP_HOURS
        and peak_gib < MEMORY_HARD_STOP_GIB
    )
    if verdict == "FEASIBLE" and (completed_units != 7350 or not within_projection):
        verdict = "RESOURCE_BLOCKED"
    result = {
        "schema_version": "gen_enc_2_timing_preflight_result_freeze_03_v1",
        "record_kind": "DEVELOPMENT_ONLY_TIMING_PREFLIGHT_RESULT",
        "model_name": MODEL_NAME,
        "member_id": "HAND_01",
        "contract_sha256": bindings["contract_sha256"],
        "source_manifest_sha256": bindings["source_manifest_sha256"],
        "command_manifest_sha256": bindings["command_manifest_sha256"],
        "completion": {"complete_units": completed_units, "expected_units": 7350, "states": 4, "ports": 4, "computed_frequencies": 256, "representative_complex_value_count": 30105600},
        "resources": {
            "wall_time_seconds": wall_seconds,
            "cpu_time_seconds": cpu_seconds,
            "cpu_utilization_percent": 100.0 * cpu_seconds / wall_seconds if wall_seconds > 0.0 else 0.0,
            "aggregate_peak_memory_gib": peak_gib,
        },
        "projection": {
            "multiplier": 560,
            "formal_complex_value_count": 16859136000,
            "derivation": "(4_FAMILIES*20_MEMBERS*(4_DEVELOPMENT+24_VALIDATION_ANGLES)*4_PORTS)/(1_MEMBER*4_DEVELOPMENT_STATES*4_PORTS)=560",
            "cpu_core_hours": projected_cpu,
            "serial_wall_hours": projected_wall,
            "aggregate_peak_memory_gib": peak_gib,
            "within_all_hard_stops": within_projection,
        },
        "numerical": {
            "valid": numerical_valid,
            "converged": numerical_valid,
            "nan_inf_absent": numerical_valid,
            "solver_exit_code": exit_code,
        },
        "license": {"available": True, "status": "STDLIB_NUMPY_NO_EXTERNAL_LICENSE"},
        "verdict": verdict,
        "claim_limit": "HAND_01_ONLY_DEVELOPMENT_SIDE_TIMING_AND_NUMERICAL_FEASIBILITY_ON_FROZEN_RUNTIME_AND_HARD_STOPS_NOT_OTHER_FAMILIES_NOT_ALL80_NOT_WORST_CASE_NOT_FULL_E2",
        "gen_enc_2_e2_authorized": False,
        "run_id": None,
        "final_test_read": False,
    }
    validate_and_publish_terminal_result(result, Path(args.result_schema), result_path)
    return 0 if verdict == "FEASIBLE" else 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GEN-ENC-2 science-blind timing preflight")
    parser.add_argument("mode", choices=("timing-preflight",))
    parser.add_argument("--contract-check-only", action="store_true")
    parser.add_argument("--member", required=True)
    parser.add_argument("--final92-review", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--matched-cost", required=True)
    parser.add_argument("--frequency-contract", required=True)
    parser.add_argument("--nuisance-contract", required=True)
    parser.add_argument("--nuisance-csv", required=True)
    parser.add_argument("--seed-split", required=True)
    parser.add_argument("--partition", required=True, choices=("development", "single_use_validation"))
    parser.add_argument("--repeat-seeds", required=True, nargs=2, type=int)
    parser.add_argument("--angles", required=True, nargs="+", type=int)
    parser.add_argument("--source-manifest")
    parser.add_argument("--contract")
    parser.add_argument("--command-manifest")
    parser.add_argument("--result-schema")
    parser.add_argument("--authorization")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--frequency-block-size", required=True, type=int)
    parser.add_argument("--checkpoint-unit-interval", required=True, type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.contract_check_only:
            return _contract_check(args)
        return _formal_timing_preflight(args)
    except (OSError, ValueError, PreflightError) as exc:
        print(f"FAIL_CLOSED:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
