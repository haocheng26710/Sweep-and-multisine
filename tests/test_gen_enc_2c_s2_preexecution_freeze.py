from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest


REPO = Path(__file__).resolve().parents[1]
TASK_ID = "01a048bd-dc5e-7e93-87e6-72d299ebaa4d"
PKG = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/s2_preexecution_freeze"
DRIVER_PATH = REPO / "scripts/gen_enc_2c_s2/formal_driver_rev03_s2.py"
VERIFIER_PATH = REPO / "scripts/gen_enc_2c_s2/formal_independent_verifier_rev03_s2.py"
SCHEMA_PATH = REPO / "schemas/gen_enc/gen_enc_2c_s2/s2_task_bound_dispatch.schema.json"
CONTRACT_PATH = PKG / "implementation_contract.json"
DRAFT_PATH = PKG / "s2_task_bound_authorization_record.DRAFT.json"
ALLOWLIST_PATH = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/s1_implementation_freeze/path_allowlist_manifest.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver(): return load_module("s2_driver", DRIVER_PATH)


def draft(): return json.loads(DRAFT_PATH.read_text(encoding="utf-8"))


def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_record(path: Path, value: dict):
    value["record_payload_sha256"] = hashlib.sha256(canonical(value["payload"])).hexdigest()
    path.write_bytes(canonical(value))


def test_unique_schema_valid_and_draft_exact_canonical():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8")); jsonschema.Draft202012Validator.check_schema(schema)
    record = draft(); jsonschema.validate(record, schema, cls=jsonschema.Draft202012Validator)
    assert DRAFT_PATH.read_bytes() == canonical(record)
    assert record["payload"]["released"] is record["payload"]["guardian_approved"] is record["payload"]["formal_execution_authorized"] is False


def test_gap1_cli_task_compared(driver):
    with pytest.raises(driver.FailClosed, match="TASK_ID_MISMATCH"):
        driver.validate_record(REPO, DRAFT_PATH, SCHEMA_PATH, CONTRACT_PATH, "wrong-task", "preflight", "S2_PREFLIGHT", False,
                               datetime(2026, 8, 28, tzinfo=timezone.utc))


def test_gaps3_to6_exact_bindings(driver):
    record, contract = driver.validate_record(REPO, DRAFT_PATH, SCHEMA_PATH, CONTRACT_PATH, TASK_ID, "preflight", "S2_PREFLIGHT", False,
                                              datetime(2026, 8, 28, tzinfo=timezone.utc))
    assert record["payload"]["allowed_commands"] == list(driver.FORMAL_COMMANDS)
    assert record["payload"]["permissions"] == driver.PERMISSION_VECTOR
    assert set(contract["manifest_sha256"]) == {"source", "schema", "fixture", "authority", "allowlist"}


@pytest.mark.parametrize("kind", ["revoked", "permission", "mode", "hash"])
def test_dispatch_mutations_fail_closed(tmp_path, driver, kind):
    record = draft()
    if kind == "revoked": record["payload"]["revoked"] = True
    elif kind == "permission": record["payload"]["permissions"]["timing"] = True
    elif kind == "mode": record["payload"]["allowed_modes"] = ["S2_PREFLIGHT"]
    else: record["payload"]["manifest_sha256"]["source"] = "0" * 64
    path = tmp_path / "record.json"; write_record(path, record)
    with pytest.raises((driver.FailClosed, jsonschema.ValidationError)):
        driver.validate_record(REPO, path, SCHEMA_PATH, CONTRACT_PATH, TASK_ID, "preflight", "S2_PREFLIGHT", False,
                               datetime(2026, 8, 28, tzinfo=timezone.utc))


def test_expiry_and_noncanonical_tamper(tmp_path, driver):
    record = draft(); path = tmp_path / "expired.json"; write_record(path, record)
    with pytest.raises(driver.FailClosed, match="EXPIRED"):
        driver.validate_record(REPO, path, SCHEMA_PATH, CONTRACT_PATH, TASK_ID, "preflight", "S2_PREFLIGHT", False,
                               datetime(2099, 1, 1, tzinfo=timezone.utc))
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(driver.FailClosed, match="NOT_CANONICAL"):
        driver.validate_record(REPO, path, SCHEMA_PATH, CONTRACT_PATH, TASK_ID, "preflight", "S2_PREFLIGHT", False,
                               datetime(2026, 8, 28, tzinfo=timezone.utc))


def test_formal_entrypoints_reject_unreleased_draft():
    common = ["--repo-root", str(REPO), "--contract", str(CONTRACT_PATH), "--authorization-record", str(DRAFT_PATH),
              "--authorization-schema", str(SCHEMA_PATH), "--task-id", TASK_ID]
    run = subprocess.run([sys.executable, str(DRIVER_PATH), "formal-generate-static-audit", *common], capture_output=True, text=True)
    assert run.returncode == 2 and "GUARDIAN_RELEASE_REQUIRED" in run.stderr
    verify = subprocess.run([sys.executable, str(VERIFIER_PATH), "--repo-root", str(REPO), "--contract", str(CONTRACT_PATH),
                             "--authorization-record", str(DRAFT_PATH), "--authorization-schema", str(SCHEMA_PATH),
                             "--task-id", TASK_ID, "--mode", "verify-formal"], capture_output=True, text=True)
    assert verify.returncode == 2 and "RELEASE_REQUIRED" in verify.stderr


def test_validate_draft_reports_zero_formal_reads():
    common = ["--repo-root", str(REPO), "--contract", str(CONTRACT_PATH), "--authorization-record", str(DRAFT_PATH),
              "--authorization-schema", str(SCHEMA_PATH), "--task-id", TASK_ID]
    run = subprocess.run([sys.executable, str(DRIVER_PATH), "validate-draft", *common], check=True, capture_output=True, text=True)
    report = json.loads(run.stdout)
    assert report["formal_input_read_count"] == report["formal_seed_read_count"] == report["formal_row_read_count"] == 0


def test_verifier_independence_and_recomputation_surface():
    tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert not any("formal_driver" in name or "generator" in name or "cad_mapping" in name for name in imports)
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert {"splitmix64", "open_uniform", "random_once", "midpoint_lhs", "positive_area_components", "verify_formal_package"} <= names


def test_92_paths_unique_safe_and_absent(driver):
    manifest = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    targets = driver.validate_allowlist(REPO, manifest, require_absent=True)
    assert len(targets) == 92 and sum(path.exists() for path in targets) == 0


def test_atomic_terminal_mutual_exclusion(tmp_path, driver):
    staging = tmp_path / "staging"; success = tmp_path / "success"; failure = tmp_path / "failure"; staging.mkdir()
    (staging / "VERIFIED_SUCCESS.json").write_text("{}", encoding="utf-8")
    (staging / "FAIL_CLOSED.json").write_text("{}", encoding="utf-8")
    with pytest.raises(driver.FailClosed, match="MIXED"):
        driver.package_results(staging, success, failure)


def test_seven_gap_machine_matrix_and_zero_state():
    matrix = json.loads((PKG / "gap_closure_matrix.json").read_text(encoding="utf-8"))
    assert len(matrix["gaps"]) == 7 and all(item["status"] == "CLOSED_TECHNICAL_PREEXECUTION_BINDING" for item in matrix["gaps"])
    state = json.loads((PKG / "execution_state.json").read_text(encoding="utf-8"))
    assert state["formal_instance_count"] == state["static_eligibility_run_count"] == 0
    assert state["formal_hashes"] == {"member": None, "family": None, "index": None}
    assert state["final_test_read"] is False
