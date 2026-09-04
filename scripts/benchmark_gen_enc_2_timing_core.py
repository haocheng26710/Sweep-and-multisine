"""Development-only scalar/batched equivalence and timing aggregate fixture."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

import numpy as np


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acoustic_encoder.gen_enc.forward_acoustic_network import (  # noqa: E402
    frozen_frequency_grid,
    solve_forward_block,
    solve_forward_block_reference,
)


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if any(os.environ.get(name) != "1" for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")):
        raise SystemExit("THREAD_ENV_MUST_EQUAL_ONE")
    fixture = json.loads((REPO / args.fixture).read_text(encoding="utf-8"))
    if fixture.get("formal_preflight") is not False or fixture.get("persist_response") is not False or fixture.get("final_test_read") is not False:
        raise SystemExit("FIXTURE_SCOPE_INVALID")
    start = int(fixture["frequency_start_index"])
    count = int(fixture["frequency_count"])
    frequencies = frozen_frequency_grid()[start : start + count]
    members = [
        json.loads(
            (REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances" / relative).read_text(encoding="utf-8")
        )
        for relative in fixture["families"]
    ]
    kwargs = {
        "nuisance": fixture["nuisance"],
        "cell_index": int(fixture["cell_index"]),
        "repeat_index": int(fixture["repeat_index"]),
        "frequencies_hz": frequencies,
        "frequency_start_index": start,
        "state_angles_degrees": (0.0, 90.0, 180.0, 270.0),
        "partition": "development",
        "repeat_seed_tuple": (2026091001, 2026091002),
    }
    maximum_absolute_error = 0.0
    maximum_relative_error = 0.0
    statuses_equal = True
    for member in members:
        reference = solve_forward_block_reference(member=member, **kwargs)
        optimized = solve_forward_block(member=member, **kwargs)
        delta = np.abs(optimized.central_pressure - reference.central_pressure)
        maximum_absolute_error = max(maximum_absolute_error, float(delta.max(initial=0.0)))
        denominator = np.maximum(np.abs(reference.central_pressure), float(fixture["atol"]))
        maximum_relative_error = max(maximum_relative_error, float((delta / denominator).max(initial=0.0)))
        statuses_equal = statuses_equal and (
            optimized.passive,
            optimized.reciprocal,
            optimized.solvable,
            optimized.numerically_valid,
        ) == (
            reference.passive,
            reference.reciprocal,
            reference.solvable,
            reference.numerically_valid,
        )
        np.testing.assert_allclose(
            optimized.central_pressure,
            reference.central_pressure,
            rtol=float(fixture["rtol"]),
            atol=float(fixture["atol"]),
        )
        del reference, optimized, delta, denominator

    iterations = int(fixture["iterations"])
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    for _ in range(iterations):
        for member in members:
            block = solve_forward_block_reference(member=member, **kwargs)
            if not block.numerically_valid:
                raise SystemExit("SCALAR_NUMERIC_STATUS_FAIL")
            del block
    scalar_wall = time.perf_counter() - wall_start
    scalar_cpu = time.process_time() - cpu_start
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    for _ in range(iterations):
        for member in members:
            block = solve_forward_block(member=member, **kwargs)
            if not block.numerically_valid:
                raise SystemExit("BATCHED_NUMERIC_STATUS_FAIL")
            del block
    optimized_wall = time.perf_counter() - wall_start
    optimized_cpu = time.process_time() - cpu_start
    report = {
        "schema_version": "gen_enc_2_timing_optimization_development_benchmark_v1",
        "equivalence": {
            "status": "PASS" if statuses_equal else "FAIL",
            "families": 4,
            "shape": [4, 4, count],
            "rtol": float(fixture["rtol"]),
            "atol": float(fixture["atol"]),
            "maximum_absolute_error": maximum_absolute_error,
            "maximum_relative_error": maximum_relative_error,
            "finite_and_status_equal": statuses_equal,
        },
        "benchmark": {
            "formal_preflight": False,
            "iterations": iterations,
            "family_blocks_per_implementation": iterations * len(members),
            "scalar_wall_seconds": scalar_wall,
            "optimized_wall_seconds": optimized_wall,
            "wall_speedup": scalar_wall / optimized_wall,
            "scalar_cpu_seconds": scalar_cpu,
            "optimized_cpu_seconds": optimized_cpu,
            "cpu_speedup": scalar_cpu / optimized_cpu,
            "minimum_wall_speedup": float(fixture["minimum_wall_speedup"]),
            "minimum_cpu_speedup": float(fixture["minimum_cpu_speedup"]),
            "wall_target_met": scalar_wall / optimized_wall >= float(fixture["minimum_wall_speedup"]),
            "cpu_target_met": scalar_cpu / optimized_cpu >= float(fixture["minimum_cpu_speedup"]),
            "thread_environment": {name: os.environ[name] for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
            "response_artifacts": 0,
        },
        "scientific_hypothesis_status": "NOT_TESTED",
        "formal_timing_runs": 0,
        "gen_enc_2_e2_authorized": False,
        "final_test_read": False,
    }
    _atomic_json(Path(args.output), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
