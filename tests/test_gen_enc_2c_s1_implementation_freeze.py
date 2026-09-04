from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]
ADDENDUM_METADATA = {
    "new_content": "S1 ordinary technical tests only",
    "related_legacy_files": ["docs/experiment/gen_enc/GEN_ENC_2C_PREEXECUTION_CONTRACT_ADDENDUM_REV03.md"],
    "unchanged_content": "No formal input, identity, static eligibility or scientific conclusion is changed",
    "evidence_level": "E1_TECHNICAL_IMPLEMENTATION_CONFORMANCE_ONLY",
    "overrides": False,
}


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


orch = load_module("gen_enc_2c_s1_orch", "scripts/gen_enc_2c_s1/orchestrator_rev03_s1.py")
ver = load_module("gen_enc_2c_s1_ver", "scripts/gen_enc_2c_s1/independent_verifier_rev03_s1.py")
FIXTURE_PATH = ROOT / "tests/fixtures/gen_enc_2c_s1/technical_80_slot_fixture.json"
FIXTURE_SCHEMA_PATH = ROOT / "tests/fixtures/gen_enc_2c_s1/technical_80_slot_fixture.schema.json"
SCHEMA_ROOT = ROOT / "schemas/gen_enc/gen_enc_2c_rev03"


def fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_nine_formal_schemas_parse_and_validate_as_draft_2020_12():
    schemas = sorted(SCHEMA_ROOT.glob("*.schema.json"))
    assert len(schemas) == 9
    for path in schemas:
        jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_technical_fixture_schema_and_exact_identity_label():
    document = fixture()
    jsonschema.validate(document, json.loads(FIXTURE_SCHEMA_PATH.read_text(encoding="utf-8")), cls=jsonschema.Draft202012Validator)
    assert document["identity_class"] == "TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY"


def test_verifier_reconstructs_synthetic_80_slots():
    report = ver.verify_fixture(fixture())
    assert report["status"] == "PASS_TECHNICAL_FIXTURE_RECOMPUTATION"
    assert report["observed_member_count"] == 80
    assert report["failure_count"] == 0
    assert set(report["family_counts"].values()) == {20}
    assert report["formal_input_read_count"] == 0


def test_verifier_detects_parameter_hash_mismatch():
    document = fixture()
    document["families"][2]["expected_parameter_matrix_sha256"] = "0" * 64
    assert ver.verify_fixture(document)["status"].startswith("FAIL_CLOSED")


@pytest.mark.parametrize("field,value", [("dof", 17), ("volume_m3", 1.0), ("minimum_feature_m", 0.001), ("solid_load_path_m", 0.001)])
def test_verifier_detects_static_failures(field, value):
    document = fixture()
    document["families"][0]["static_template"][field] = value
    assert ver.verify_fixture(document)["failure_count"] >= 1


def test_random_zero_edge_is_exact_and_descriptive_only():
    document = fixture()
    report = ver.verify_fixture(document)
    assert report["failure_count"] == 0
    document["families"][2]["reduced_edges"][0][3] = True
    assert "RANDOM_EXACT_ZERO:TECHNICAL_FIXTURE_RANDOM" in ver.verify_fixture(document)["failures"]


def test_actual_positive_area_bfs_is_independent_of_reduced_edges():
    assert ver.connected_components(["A", "B", "C"], [["A", "B", 1.0], ["B", "C", 0.0]]) == 2
    assert ver.connected_components(["A", "B", "C"], [["A", "B", 1.0], ["B", "C", 1e-300]]) == 1


def test_canonical_json_rejects_nonfinite_and_has_no_newline():
    assert orch.canonical_json_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    with pytest.raises(orch.PreflightError):
        orch.canonical_json_bytes({"x": float("nan")})


def test_fail_closed_record_schema_and_honest_zero_counts():
    record = orch.fail_closed_record("TECHNICAL_FIXTURE_FAILURE", {"files_observed": 3}, "TECHNICAL_FIXTURE_TASK")
    schema = json.loads((SCHEMA_ROOT / "fail_closed_record.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(record, schema, cls=jsonschema.Draft202012Validator)
    assert record["formal_instance_count"] == 0
    assert record["formal_hashes"] == {"member": None, "family": None, "index": None}


def test_fail_closed_record_is_schema_valid_and_atomic(tmp_path):
    target = tmp_path / "fail" / "FAIL_CLOSED.json"
    orch.write_fail_closed_atomic(target, SCHEMA_ROOT / "fail_closed_record.schema.json", "TECHNICAL_FIXTURE_FAILURE", {"files_observed":2}, "TECHNICAL_FIXTURE_TASK")
    assert target.is_file() and not target.with_name(target.name + ".tmp").exists()
    jsonschema.validate(json.loads(target.read_text(encoding="utf-8")), json.loads((SCHEMA_ROOT / "fail_closed_record.schema.json").read_text(encoding="utf-8")), cls=jsonschema.Draft202012Validator)


def test_materialized_allowlist_is_exact_92_casefold_unique_and_absent():
    document = json.loads((ROOT / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/s1_implementation_freeze/path_allowlist_manifest.json").read_text(encoding="utf-8"))
    assert len(orch.validate_allowlist(document["paths"])) == 92
    assert all(not (ROOT / path).exists() for path in document["paths"])


@pytest.mark.parametrize("bad", ["CON.json", "safe/name. ", "../escape.json"])
def test_allowlist_rejects_reserved_trailing_and_escape(bad):
    base = [f"safe/{index}.json" for index in range(92)]
    base[1] = bad
    with pytest.raises(orch.PreflightError):
        orch.validate_allowlist(base)


def test_allowlist_rejects_casefold_duplicate_and_collision():
    base = [f"safe/{index}.json" for index in range(92)]
    base[1] = "SAFE/0.JSON"
    with pytest.raises(orch.PreflightError):
        orch.validate_allowlist(base)
    base = [f"safe/{index}.json" for index in range(92)]
    base[1] = "safe/0.json/child"
    with pytest.raises(orch.PreflightError):
        orch.validate_allowlist(base)


def test_unlisted_file_is_rejected(tmp_path):
    root = tmp_path / "out"
    root.mkdir()
    (root / "unlisted.json").write_text("{}", encoding="utf-8")
    with pytest.raises(orch.PreflightError):
        orch.zero_unlisted_files(root, set())


def test_reparse_or_symlink_ancestor_is_rejected_fail_closed(tmp_path, monkeypatch):
    link = tmp_path / "link"
    link.mkdir()
    monkeypatch.setattr(orch, "_is_reparse", lambda path: path == link)
    with pytest.raises(orch.PreflightError):
        orch.validate_containment_and_ancestors(tmp_path, link / "target.json")


def test_dispatch_authority_expiry_revocation_and_final_seal():
    valid = {"stage":"S1_TECHNICAL_FIXTURE","authorized":True,"revoked":False,"expires_at":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),"source_manifest_sha256":"a"*64,"final_test_state":"SEALED","final_test_read":False,"formal_execution_authorized":False}
    orch.verify_dispatch(valid, "a" * 64, datetime.now(timezone.utc))
    for mutation in ({"authorized":False}, {"revoked":True}, {"expires_at":"2000-01-01T00:00:00Z"}, {"source_manifest_sha256":"b"*64}, {"final_test_read":True}, {"formal_execution_authorized":True}):
        candidate = {**valid, **mutation}
        with pytest.raises(orch.PreflightError):
            orch.verify_dispatch(candidate, "a" * 64, datetime.now(timezone.utc))


def test_s1_cannot_bind_sealed_generator_api():
    with pytest.raises(orch.PreflightError):
        orch.bind_sealed_generator_api({"status":"PASS_TECHNICAL_PREFLIGHT_ONLY"}, {"stage":"S1_TECHNICAL_FIXTURE","formal_execution_authorized":False})


def test_hash_manifest_mismatch_fails_closed(tmp_path):
    path = tmp_path / "x.txt"
    path.write_text("x", encoding="utf-8")
    manifest = {"entries":[{"path":"x.txt","sha256":"0"*64}]}
    with pytest.raises(orch.PreflightError):
        orch.verify_hash_manifest(tmp_path, manifest)


def test_negative_capability_ast_detects_executable_symbol_not_comment(tmp_path):
    clean = tmp_path / "clean.py"
    clean.write_text("# response endpoint\nx = 1\n", encoding="utf-8")
    assert orch.audit_negative_capability([clean])["violation_count"] == 0
    bad = tmp_path / "bad.py"
    bad.write_text("def timing_probe():\n    return 1\n", encoding="utf-8")
    assert orch.audit_negative_capability([bad])["violation_count"] == 1


def test_verifier_ast_has_no_generator_or_orchestrator_import():
    path = ROOT / "scripts/gen_enc_2c_s1/independent_verifier_rev03_s1.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = [ast.unparse(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert not any("generator" in item or "orchestrator" in item for item in imports)


def test_success_and_fail_closed_packaging_are_atomic_and_mutually_exclusive(tmp_path):
    staging = tmp_path / "stage-success"
    staging.mkdir()
    (staging / "SUCCESS.json").write_text("{}", encoding="utf-8")
    success, failure = tmp_path / "success", tmp_path / "failure"
    orch.package_results(staging, success, failure, SCHEMA_ROOT / "fail_closed_record.schema.json")
    assert success.is_dir() and not failure.exists() and not staging.exists()
    mixed = tmp_path / "stage-mixed"
    mixed.mkdir()
    (mixed / "SUCCESS.json").write_text("{}", encoding="utf-8")
    (mixed / "FAIL_CLOSED.json").write_text("{}", encoding="utf-8")
    with pytest.raises(orch.PreflightError):
        orch.package_results(mixed, tmp_path / "s2", tmp_path / "f2", SCHEMA_ROOT / "fail_closed_record.schema.json")


def test_schema_valid_fail_closed_packaging(tmp_path):
    staging = tmp_path / "stage-fail"
    staging.mkdir()
    record = orch.fail_closed_record("TECHNICAL_FIXTURE_FAILURE", {"files_observed":1}, "TECHNICAL_FIXTURE_TASK")
    (staging / "FAIL_CLOSED.json").write_bytes(orch.canonical_json_bytes(record))
    success, failure = tmp_path / "success-f", tmp_path / "failure-f"
    orch.package_results(staging, success, failure, SCHEMA_ROOT / "fail_closed_record.schema.json")
    assert failure.is_dir() and not success.exists()


def test_fixture_paths_are_isolated_from_formal_roots():
    assert "phase_b/scientific" not in FIXTURE_PATH.as_posix()
    assert "TECHNICAL_FIXTURE" in FIXTURE_PATH.read_text(encoding="utf-8")
