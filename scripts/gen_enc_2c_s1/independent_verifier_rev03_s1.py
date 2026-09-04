"""Read-only independent GEN-ENC-2C verifier for S1 technical fixtures.

This module deliberately imports neither the orchestrator nor the sealed generator.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
from collections import deque
from pathlib import Path
from typing import Any

import jsonschema


MASK64 = (1 << 64) - 1
ADDENDUM_METADATA = {
    "new_content": "S1 read-only independent technical verifier",
    "related_legacy_files": ["docs/experiment/gen_enc/GEN_ENC_2C_PREEXECUTION_CONTRACT_ADDENDUM_REV03.md"],
    "unchanged_content": "Generator, orchestrator, formal inputs and scientific artifacts remain unchanged",
    "evidence_level": "E1_TECHNICAL_IMPLEMENTATION_CONFORMANCE_ONLY",
    "overrides": False,
}
FAMILIES = ("TECHNICAL_FIXTURE_HAND", "TECHNICAL_FIXTURE_NEAR", "TECHNICAL_FIXTURE_RANDOM", "TECHNICAL_FIXTURE_PHYSICS")


def splitmix64(value: int) -> int:
    z = (value + 0x9E3779B97F4A7C15) & MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


def open_uniform(z: int) -> float:
    value = ((z >> 11) + 0.5) / float(1 << 53)
    return math.nextafter(1.0, 0.0) if value == 1.0 else value


def random_parameters(seed: int, count: int) -> list[float]:
    values: list[float] = []
    state = seed & MASK64
    for _ in range(count):
        state = splitmix64(state)
        values.append(open_uniform(state))
    return values


def physics_midpoint_lhs(seed: int, parameter_count: int, rows: int) -> list[list[float]]:
    columns: list[list[float]] = []
    for parameter in range(parameter_count):
        permutation = list(range(rows))
        state = (seed + parameter) & MASK64
        for index in range(rows - 1, 0, -1):
            state = splitmix64(state)
            swap = state % (index + 1)
            permutation[index], permutation[swap] = permutation[swap], permutation[index]
        columns.append([(stratum + 0.5) / rows for stratum in permutation])
    return [[columns[column][row] for column in range(parameter_count)] for row in range(rows)]


def connected_components(nodes: list[str], positive_area_faces: list[list[Any]]) -> int:
    adjacency = {node: set() for node in nodes}
    for left, right, area in positive_area_faces:
        if float(area) > 0.0:
            adjacency[left].add(right)
            adjacency[right].add(left)
    remaining = set(nodes)
    count = 0
    while remaining:
        count += 1
        start = remaining.pop()
        queue = deque([start])
        while queue:
            for other in adjacency[queue.popleft()]:
                if other in remaining:
                    remaining.remove(other)
                    queue.append(other)
    return count


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _technical_matrix(spec: dict[str, Any]) -> list[list[float]]:
    if spec["algorithm"] == "LITERAL_FORMULA":
        return [[(row + 1) / 100.0 + column / 1000.0 for column in range(spec["parameter_count"])] for row in range(20)]
    if spec["algorithm"] == "SPLITMIX64":
        return [random_parameters(spec["technical_seed_base"] + row, spec["parameter_count"]) for row in range(20)]
    if spec["algorithm"] == "MIDPOINT_LHS":
        return physics_midpoint_lhs(spec["technical_master_seed"], spec["parameter_count"], 20)
    raise ValueError("UNKNOWN_FIXTURE_ALGORITHM")


def verify_fixture(document: dict[str, Any]) -> dict[str, Any]:
    if document["identity_class"] != "TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY":
        raise ValueError("NOT_A_TECHNICAL_FIXTURE")
    family_counts = {family: 0 for family in FAMILIES}
    failures: list[str] = []
    observed_member_count = 0
    for spec in document["families"]:
        matrix = _technical_matrix(spec)
        matrix_hash = hashlib.sha256(canonical_bytes(matrix)).hexdigest()
        if matrix_hash != spec["expected_parameter_matrix_sha256"]:
            failures.append(f"PARAMETER_MATRIX:{spec['family_id']}")
        for family_ordinal in range(1, 21):
            observed_member_count += 1
            family_counts[spec["family_id"]] += 1
        static = spec["static_template"]
        if not (static["volume_interval"][0] <= static["volume_m3"] <= static["volume_interval"][1]):
            failures.append(f"VOLUME:{spec['family_id']}")
        if static["dof"] > static["dof_max"]:
            failures.append(f"DOF:{spec['family_id']}")
        if any(actual > cap for actual, cap in zip(static["envelope_m"], static["envelope_caps_m"])):
            failures.append(f"ENVELOPE:{spec['family_id']}")
        if static["interface"] != "TECHNICAL_FIXTURE_U4_INTERFACE":
            failures.append(f"INTERFACE:{spec['family_id']}")
        if static["minimum_feature_m"] < 0.002 or static["solid_load_path_m"] < 0.0016:
            failures.append(f"FEATURE_OR_LOAD_PATH:{spec['family_id']}")
        actual_components = connected_components(static["fluid_nodes"], static["positive_area_faces"])
        if actual_components != 1:
            failures.append(f"ACTUAL_FLUID_CONNECTIVITY:{spec['family_id']}")
        reduced_edges = spec.get("reduced_edges", [])
        if any(edge[2] == 0.0 and edge[3] is not False for edge in reduced_edges):
            failures.append(f"RANDOM_EXACT_ZERO:{spec['family_id']}")
    if set(family_counts.values()) != {20}:
        failures.append("FAMILY_COUNTS")
    return {
        "status": "PASS_TECHNICAL_FIXTURE_RECOMPUTATION" if not failures else "FAIL_CLOSED_TECHNICAL_FIXTURE_RECOMPUTATION",
        "observed_member_count": observed_member_count,
        "family_counts": family_counts,
        "failure_count": len(failures),
        "failures": failures,
        "fixture_sha256": hashlib.sha256(canonical_bytes(document)).hexdigest(),
        "runtime": {"python": platform.python_version(), "jsonschema": importlib.metadata.version("jsonschema")},
        "formal_input_read_count": 0,
        "formal_instance_count": 0,
        "static_eligibility_run_count": 0,
        "scientific_hypothesis_status": "NOT_TESTED",
        "final_test_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--fixture-schema", required=True, type=Path)
    args = parser.parse_args()
    document = json.loads(args.fixture.read_text(encoding="utf-8"))
    schema = json.loads(args.fixture_schema.read_text(encoding="utf-8"))
    jsonschema.validate(document, schema, cls=jsonschema.Draft202012Validator)
    print(canonical_bytes(verify_fixture(document)).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
