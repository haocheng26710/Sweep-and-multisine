from __future__ import annotations

import ast
import hashlib
import inspect
import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from acoustic_encoder.gen_enc.generator import api
from acoustic_encoder.gen_enc.generator.cad_audit import (
    audit_abstract_cad,
    solve_cavity_length_bisection,
)
from acoustic_encoder.gen_enc.generator.canonical import (
    canonical_json_bytes,
    sha256_lower_hex,
)
from acoustic_encoder.gen_enc.generator.families import (
    PHYSICS_PARAMETER_ORDER,
    RANDOM_PARAMETER_ORDER,
    TECHNICAL_LABEL,
    _random_inverse_cdf,
    physics_midpoint_lhs,
    random_parameters,
)
from acoustic_encoder.gen_enc.generator.prng import open_interval_uniform53, splitmix64
from acoustic_encoder.gen_enc.generator.schema_validation import validate_source_bundle
from acoustic_encoder.gen_enc.generator.table_reader import load_literal_family_table
from acoustic_encoder.gen_enc.generator.volume_mapping import map_volume_partition

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "gen_enc_2b"
REV01_ROOT = ROOT / "outputs" / "gen_enc" / "GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01"
TABLE_PATH = REV01_ROOT / "family_design_tables_rev01.json"
TABLE_SHA256 = "3b7d649fb4640b852aeddca5be0ce272d85721d8ae8b82ee2be82b8b39a6f751"
TECHNICAL = "TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY"


def _load_fixture(name: str) -> dict:
    payload = json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))
    assert payload["object_class"] == TECHNICAL
    assert payload["frozen_before_test_execution"] is True
    return payload


def _random_spec() -> dict:
    return {"object_class": TECHNICAL, "parameter_order": list(RANDOM_PARAMETER_ORDER)}


def _physics_spec() -> dict:
    bounds = [(-0.12, 0.12)] * 3 + [(0.2, 0.8)] * 8 + [(0.02, 0.08)] * 4
    return {
        "object_class": TECHNICAL,
        "parameter_order": list(PHYSICS_PARAMETER_ORDER),
        "bounds": bounds,
    }


def _cost_contract() -> dict:
    return {
        "object_class": TECHNICAL,
        "matched_target_interval_m3": [
            0.00002984750608872877,
            0.000030450486009713192,
        ],
        "envelope_caps_m": {"x": 0.227302, "y": 0.227302, "z": 0.0122},
        "counts": {"ports": 4, "states": 4, "sensors": 1},
        "interface_identity": "U4_CARDINAL_4PORT_CENTRAL_M1_v1",
        "interface_dimensions_m": {
            "outer_port_width": 0.016,
            "outer_port_height": 0.0092,
            "sensor_bore_diameter": 0.009,
            "observable_disk_diameter": 0.0088,
        },
        "interface_tolerance_m": 0.0002,
        "minimum_designed_feature_m": 0.002,
        "minimum_solid_load_path_m": 0.0016,
    }


def _passing_cad_payload() -> dict:
    return {
        "object_class": TECHNICAL,
        "connected_volume_m3": 0.00003014899604922098,
        "envelope_m": {"x": 0.227302, "y": 0.227302, "z": 0.0122},
        "connected_components": 1,
        "counts": {"ports": 4, "states": 4, "sensors": 1},
        "interface_identity": "U4_CARDINAL_4PORT_CENTRAL_M1_v1",
        "interface_dimensions_m": {
            "outer_port_width": 0.016,
            "outer_port_height": 0.0092,
            "sensor_bore_diameter": 0.009,
            "observable_disk_diameter": 0.0088,
        },
        "minimum_feature_m": 0.002,
        "minimum_solid_load_path_m": 0.0016,
    }


def test_canonical_fixture_binding_correction() -> None:
    fixture = _load_fixture("expected_canonical_bytes.json")
    encoded = canonical_json_bytes(fixture["input_object"])
    assert encoded == b'{"a":[3,2,1],"b":1}'
    assert len(encoded) == fixture["authoritative_utf8_byte_length"] == 19
    assert sha256_lower_hex(encoded) == fixture["authoritative_sha256"]
    assert fixture["phase_a_literal_typo"]["incorrect_value"] == 21


def test_canonical_unicode_order_arrays_and_no_newline() -> None:
    encoded = canonical_json_bytes({"é": 2, "a": [2, 1], "中": 3})
    assert encoded == '{"a":[2,1],"é":2,"中":3}'.encode("utf-8")
    assert not encoded.startswith(b"\xef\xbb\xbf")
    assert not encoded.endswith(b"\n")


def test_canonical_rejects_nonfinite_numbers() -> None:
    with pytest.raises(ValueError):
        canonical_json_bytes({"x": math.nan})


def test_splitmix64_literal_known_answers() -> None:
    fixture = _load_fixture("expected_prng_vectors.json")
    for vector in fixture["splitmix64_known_answers"]:
        value = splitmix64(int(vector["input_uint64_hex"], 16))
        assert f"{value:016x}" == vector["expected_uint64_hex"]


def test_open_interval_uniform_extremes() -> None:
    assert 0.0 < open_interval_uniform53(0) < 1.0
    assert 0.0 < open_interval_uniform53((1 << 64) - 1) < 1.0


@pytest.mark.parametrize(
    ("index", "uniform", "expected"),
    [(0, 0.5, 0.0), (3, 0.25, 0.0), (3, 0.5, 0.2), (3, 0.75, 0.5), (9, 0.5, 0.05)],
)
def test_inverse_cdf_literal_boundaries(index: int, uniform: float, expected: float) -> None:
    assert _random_inverse_cdf(index, uniform) == expected


@pytest.mark.parametrize("sentinel_seed", [3100000001, 3100000002, 3100000003])
def test_random_sentinel_literal_outputs(sentinel_seed: int) -> None:
    fixture = _load_fixture("expected_prng_vectors.json")
    output = random_parameters(sentinel_seed, _random_spec())
    assert output["object_class"] == TECHNICAL
    assert output["seed"] == sentinel_seed
    assert output["draw_count"] == 13
    assert output["redraw_count"] == 0
    expected = fixture["sentinel_random_expected"][str(sentinel_seed)]
    assert output["splitmix64_words_hex"] == [row[0] for row in expected]
    assert output["uniforms"] == [row[1] for row in expected]
    assert list(output["parameters"].values()) == [row[2] for row in expected]


def test_random_reciprocity_diagonal_and_repeatability() -> None:
    first = random_parameters(3100000001, _random_spec())
    second = random_parameters(3100000001, _random_spec())
    assert first == second
    matrix = first["edge_matrix"]
    for left in range(4):
        assert matrix[left][left] == 0.0
        for right in range(4):
            assert matrix[left][right] == matrix[right][left]


def test_random_zero_edges_are_retained_without_redraw() -> None:
    output = random_parameters(3100000001, _random_spec())
    assert sum(value == 0.0 for value in list(output["parameters"].values())[3:9]) >= 1
    assert output["redraw_count"] == 0


def test_physics_sentinel_literal_permutations_and_repeatability() -> None:
    fixture = _load_fixture("expected_prng_vectors.json")
    first = physics_midpoint_lhs(fixture["sentinel_physics_master_seed"], _physics_spec())
    second = physics_midpoint_lhs(fixture["sentinel_physics_master_seed"], _physics_spec())
    assert first == second
    assert first["object_class"] == TECHNICAL
    assert first["permutations"] == fixture["sentinel_physics_expected_permutations"]
    assert first["jitter"] is False


def test_physics_each_stratum_once_bounds_and_row_labels() -> None:
    output = physics_midpoint_lhs(3200000000, _physics_spec())
    assert len(output["rows"]) == 20
    for permutation in output["permutations"]:
        assert sorted(permutation) == list(range(20))
    spec = _physics_spec()
    for row in output["rows"]:
        assert row["object_class"] == TECHNICAL
        for index, name in enumerate(PHYSICS_PARAMETER_ORDER):
            lower, upper = spec["bounds"][index]
            assert lower < row["parameters"][name] < upper


def test_sentinel_seed_disjointness_against_sealed_static_contract() -> None:
    fixture = _load_fixture("expected_prng_vectors.json")
    contract = fixture["formal_seed_contract"]
    path = ROOT / contract["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == contract["sha256"]
    sealed = json.loads(path.read_text(encoding="utf-8"))
    topology = sealed["topology_identity_seeds"]
    nuisance = sealed["nuisance_partition_seeds"]
    assert topology["random_disordered_members"] == contract["formal_random_member_seeds"]
    assert topology["physics_lhs_master"] == contract["formal_physics_master_seed"]
    assert topology["physics_member_identity"] == contract["formal_physics_member_identity_seeds"]
    assert nuisance["development_training"] == contract["formal_nuisance_development_seeds"]
    assert nuisance["single_use_validation"] == contract["formal_nuisance_validation_seeds"]
    formal = set(contract["formal_random_member_seeds"])
    formal.add(contract["formal_physics_master_seed"])
    formal.update(contract["formal_physics_member_identity_seeds"])
    formal.update(contract["formal_nuisance_development_seeds"])
    formal.update(contract["formal_nuisance_validation_seeds"])
    sentinels = set(fixture["sentinel_random_seeds"])
    sentinels.add(fixture["sentinel_physics_master_seed"])
    assert len(formal) == contract["formal_seed_count"] == 45
    assert len(sentinels) == 4
    assert sentinels.isdisjoint(formal)
    assert fixture["disjointness_expected"] is True
    assert fixture["formal_seeds_may_be_passed_to_generator_execution"] is False


@pytest.mark.parametrize("family", ["HAND_DESIGNED", "NEAR_INDEPENDENT"])
def test_sealed_literal_table_identity_only(family: str) -> None:
    result = load_literal_family_table(TABLE_PATH, TABLE_SHA256, family)
    assert result["object_class"] == TECHNICAL
    assert result["validation_only"] is True
    assert result["row_count"] == 20
    assert result["tunable_dof"] == 12
    assert len(set(result["member_ids"])) == 20
    assert result["derived_cad_or_topology_payload"] is None


def test_sealed_literal_table_hash_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_literal_family_table(TABLE_PATH, "0" * 64, "HAND_DESIGNED")


def test_volume_partition_literal_and_target_sum() -> None:
    target = 0.00003014899604922098
    output = map_volume_partition(0.0, 0.0, 0.0, target)
    assert output["object_class"] == TECHNICAL
    assert output["q270"] == 0.0
    assert output["local_shares"] == [0.15] * 4
    assert output["central_share"] == 0.4
    assert math.isclose(math.fsum(output["partition_volumes_m3"]), target, rel_tol=0.0, abs_tol=1e-20)


def test_volume_partition_q270_and_nonfinite_fail() -> None:
    output = map_volume_partition(-0.12, 0.06, 0.0, 0.00003014899604922098)
    assert output["q270"] == pytest.approx(0.02, abs=1e-15)
    with pytest.raises(ValueError):
        map_volume_partition(math.nan, 0.0, 0.0, 1.0)


def test_bisection_literal_cases() -> None:
    fixture = _load_fixture("expected_bisection_cases.json")
    functions = {
        "IDENTITY": lambda x: x,
        "SQUARE": lambda x: x * x,
        "NONFINITE_UPPER": lambda x: math.inf if x == 1.0 else x,
    }
    for case in fixture["cases"]:
        result = solve_cavity_length_bisection(
            functions[case["function"]],
            case["lower"],
            case["upper"],
            case["target"],
            case["tolerance"],
            case["max_iterations"],
        )
        assert result["object_class"] == TECHNICAL
        assert result["status"] == case["expected_status"]
        if result["status"] == "PASS":
            assert result["value"] == pytest.approx(case["expected_value"], abs=case.get("value_tolerance", 0.0))
            assert result["iterations"] == case["expected_iterations"]


def test_bisection_repeatability_and_80_iteration_cap() -> None:
    first = solve_cavity_length_bisection(lambda x: x * x, 0.0, 2.0, 2.0, 1e-12, 80)
    second = solve_cavity_length_bisection(lambda x: x * x, 0.0, 2.0, 2.0, 1e-12, 80)
    assert first == second
    assert solve_cavity_length_bisection(lambda x: x, 0.0, 1.0, 0.5, 1e-12, 81)["status"] == "FAIL_INVALID_CONTROL"


def test_cad_audit_pass_and_closed_interval_boundaries() -> None:
    cost = _cost_contract()
    for volume in cost["matched_target_interval_m3"]:
        payload = _passing_cad_payload()
        payload["connected_volume_m3"] = volume
        result = audit_abstract_cad(payload, cost)
        assert result == {
            "object_class": TECHNICAL,
            "status": "PASS",
            "eligible": True,
            "retained": True,
            "reasons": [],
            "redraw_count": 0,
        }


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (("connected_components", 2), "CONNECTED_COMPONENT_COUNT"),
        (("minimum_feature_m", 0.0019), "MINIMUM_FEATURE"),
        (("minimum_solid_load_path_m", 0.0015), "SOLID_LOAD_PATH"),
        (("interface_identity", "WRONG"), "INTERFACE_IDENTITY"),
    ],
)
def test_cad_audit_fail_closed_and_retained(mutation: tuple[str, object], reason: str) -> None:
    payload = _passing_cad_payload()
    payload[mutation[0]] = mutation[1]
    result = audit_abstract_cad(payload, _cost_contract())
    assert result["status"] == "COST_INELIGIBLE"
    assert result["eligible"] is False
    assert result["retained"] is True
    assert result["redraw_count"] == 0
    assert reason in result["reasons"]


def test_cad_audit_envelope_counts_and_interface_dimensions() -> None:
    cases = [
        ("envelope_m", {"x": 0.227303, "y": 0.227302, "z": 0.0122}, "ENVELOPE_X_CAP"),
        ("counts", {"ports": 3, "states": 4, "sensors": 1}, "PORT_STATE_SENSOR_COUNTS"),
        (
            "interface_dimensions_m",
            {"outer_port_width": 0.0163, "outer_port_height": 0.0092, "sensor_bore_diameter": 0.009, "observable_disk_diameter": 0.0088},
            "INTERFACE_DIMENSIONS",
        ),
    ]
    for field, value, reason in cases:
        payload = _passing_cad_payload()
        payload[field] = value
        result = audit_abstract_cad(payload, _cost_contract())
        assert reason in result["reasons"]


def test_all_json_schemas_are_valid_and_fixtures_are_labelled() -> None:
    schema_root = ROOT / "schemas" / "gen_enc"
    technical_schema = json.loads((schema_root / "technical_fixture.schema.json").read_text(encoding="utf-8"))
    for path in sorted(schema_root.glob("*.json")):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))
    validator = Draft202012Validator(technical_schema)
    for path in sorted(FIXTURE_ROOT.glob("*.json")):
        validator.validate(json.loads(path.read_text(encoding="utf-8")))


def test_source_bundle_validation_pass_and_null_pending_fail_closed() -> None:
    entries = [
        {"path": "a.py", "sha256": "1" * 64, "byte_length": 1, "role": "SOURCE"},
        {"path": "b.json", "sha256": "2" * 64, "byte_length": 2, "role": "SCHEMA"},
    ]
    manifest = {"entries": entries}
    expected = {"a.py": "1" * 64, "b.json": "2" * 64}
    assert validate_source_bundle(manifest, expected)["status"] == "PASS"
    failed = validate_source_bundle(manifest, {"a.py": None, "b.json": "2" * 64})
    assert failed["status"] == "FAIL_CLOSED"
    assert "NULL_OR_PENDING_EXPECTED_HASH" in failed["reasons"]


def test_source_bundle_path_hash_and_schema_fail_closed() -> None:
    entry = {"path": "a.py", "sha256": "1" * 64, "byte_length": 1, "role": "SOURCE"}
    assert validate_source_bundle({"entries": [entry]}, {"b.py": "1" * 64})["status"] == "FAIL_CLOSED"
    extra = dict(entry)
    extra["unexpected"] = True
    assert validate_source_bundle({"entries": [extra]}, {"a.py": "1" * 64})["status"] == "FAIL_CLOSED"


def test_public_api_is_exactly_frozen() -> None:
    expected = {
        "audit_abstract_cad",
        "canonical_json_bytes",
        "load_literal_family_table",
        "map_volume_partition",
        "open_interval_uniform53",
        "physics_midpoint_lhs",
        "random_parameters",
        "sha256_lower_hex",
        "solve_cavity_length_bisection",
        "splitmix64",
        "validate_source_bundle",
    }
    assert set(api.__all__) == expected
    assert {name for name, value in inspect.getmembers(api, inspect.isfunction)} == expected


def test_negative_capability_static_audit() -> None:
    source_root = ROOT / "src" / "acoustic_encoder" / "gen_enc" / "generator"
    prohibited_function_names = {
        "load_response",
        "write_response",
        "load_project_data",
        "load_legacy_data",
        "load_development",
        "load_validation",
        "load_final_test",
        "evaluate_endpoint",
        "run_timing",
        "search",
        "optimize",
        "classify",
        "train",
        "solve",
        "write_scientific_manifest",
    }
    prohibited_import_roots = {"comsol", "sklearn", "cadquery", "gmsh", "dolfin", "fenics"}
    prohibited_branch_identifiers = {"performance", "endpoint", "score", "response"}
    prohibited_write_attributes = {"write_bytes", "write_text", "dump", "dumps_to_file"}
    for path in sorted(source_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        function_names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert function_names.isdisjoint(prohibited_function_names), path
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        assert imports.isdisjoint(prohibited_import_roots), path
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.IfExp, ast.While)):
                identifiers = {
                    child.id.lower()
                    for child in ast.walk(node.test)
                    if isinstance(child, ast.Name)
                }
                identifiers.update(
                    child.attr.lower()
                    for child in ast.walk(node.test)
                    if isinstance(child, ast.Attribute)
                )
                assert identifiers.isdisjoint(prohibited_branch_identifiers), path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in prohibited_write_attributes, path


def test_no_formal_seed_literal_is_passed_in_test_calls() -> None:
    fixture = _load_fixture("expected_prng_vectors.json")
    formal = set(fixture["formal_seed_contract"]["formal_random_member_seeds"])
    formal.add(fixture["formal_seed_contract"]["formal_physics_master_seed"])
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    executed_seed_literals: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"random_parameters", "physics_midpoint_lhs"}:
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, int):
                executed_seed_literals.add(node.args[0].value)
    assert executed_seed_literals == {3100000001, 3200000000}
    assert executed_seed_literals.isdisjoint(formal)
