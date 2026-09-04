from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
import time
from pathlib import Path

import jsonschema
import pytest

from scripts.gen_enc_b1_repair_11_pre_01 import driver_core, verifier_core
from scripts.gen_enc_b1_repair_11_pre_01.build_freeze_package import CONTRACT, CONTRACT_SHA, PACKAGE, SUPERVISION, SUPERVISION_SHA, build, sha_file
from tests.helpers.gen_enc_b1_repair_11_pre_01_fixture import argv, canonical, make_case, synthetic_objects, write

SCHEMAS=Path("schemas/gen_enc/b1_repair_11_pre_01")
REQUIRED_SELECTORS=[x["id"] for x in json.loads(Path("outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_10/cad_typed_projection_contract.json").read_text())["semantic_selectors"] if x["id"] not in {"OWNERSHIP_CELLS","OWNERSHIP_RULE"}]

def run(case,command):return subprocess.run(argv(case,command),text=True,capture_output=True)

def test_authorities_and_contract_are_frozen_without_reading_formal_objects():
    build();assert sha_file(CONTRACT)==CONTRACT_SHA;assert sha_file(SUPERVISION)==SUPERVISION_SHA
    authority=json.loads((PACKAGE/"authority_manifest.json").read_text());assert authority["entry_count"]==13;assert authority["formal_authority_read_count"]==0
    assert [x["purpose"] for x in authority["entries"]]==[f"CAD0_MULTI_SOURCE_{i:02d}" for i in range(1,14)]

def test_all_schemas_strict_and_valid():
    build()
    for path in SCHEMAS.glob("*.schema.json"):
        value=json.loads(path.read_text());jsonschema.Draft202012Validator.check_schema(value);assert value["additionalProperties"] is False

def test_driver_verifier_import_independence_and_no_dynamic_import():
    forbidden_driver={"scripts.gen_enc_b1_repair_11_pre_01.independent_verifier","scripts.gen_enc_b1_repair_11_pre_01.verifier_core","scripts.gen_enc_b1_repair_10"}
    forbidden_verifier={"scripts.gen_enc_b1_repair_11_pre_01.formal_driver","scripts.gen_enc_b1_repair_11_pre_01.driver_core","scripts.gen_enc_b1_repair_10","tests.helpers"}
    for file,forbidden in ((Path("scripts/gen_enc_b1_repair_11_pre_01/formal_driver.py"),forbidden_driver),(Path("scripts/gen_enc_b1_repair_11_pre_01/independent_verifier.py"),forbidden_verifier)):
        tree=ast.parse(file.read_text());imports=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports.extend(x.name for x in node.names)
            if isinstance(node,ast.ImportFrom):imports.append(node.module or "")
            if isinstance(node,ast.Call) and ((isinstance(node.func,ast.Name) and node.func.id=="__import__") or (isinstance(node.func,ast.Attribute) and node.func.attr=="import_module")):pytest.fail("dynamic import")
        assert not any(any(name.startswith(block) for block in forbidden) for name in imports)

def test_future_outputs_absent_are_classified_not_missing():
    build();entries=json.loads((PACKAGE/"authority_manifest.json").read_text())["entries"];selectors=json.loads((PACKAGE/"selector_contract.json").read_text())["selectors"];objects=synthetic_objects()
    d=driver_core.snapshot(entries,objects,selectors);v=verifier_core.verify_snapshot(entries,objects,selectors,d)
    row=next(x for x in d["objects"] if x["purpose"]=="CAD0_MULTI_SOURCE_03")
    assert row["candidate_selector_status_by_id"]["OWNERSHIP_CELLS"]=="ABSENT_FIXTURE_ONLY_OR_FUTURE_OUTPUT"
    assert row["candidate_selector_status_by_id"]["OWNERSHIP_RULE"]=="ABSENT_FIXTURE_ONLY_OR_FUTURE_OUTPUT";assert v==d

@pytest.mark.parametrize("lane",["driver","verifier"])
def test_injected_fixture_future_outputs_are_rejected(lane):
    build();entries=json.loads((PACKAGE/"authority_manifest.json").read_text())["entries"];selectors=json.loads((PACKAGE/"selector_contract.json").read_text())["selectors"];objects=synthetic_objects(inject_future_outputs=True)
    if lane=="driver":
        with pytest.raises(driver_core.ShapeDriverError,match="FIXTURE_ONLY_FUTURE_OUTPUT_PRESENT"):driver_core.snapshot(entries,objects,selectors)
    else:
        clean=driver_core.snapshot(entries,synthetic_objects(),selectors)
        with pytest.raises(verifier_core.ShapeVerifierError,match="FIXTURE_ONLY_FUTURE_OUTPUT_PRESENT"):verifier_core.verify_snapshot(entries,objects,selectors,clean)

@pytest.mark.parametrize("selector_id",REQUIRED_SELECTORS)
def test_missing_nonfuture_selector_fails_closed_without_substitution(selector_id):
    build();entries=json.loads((PACKAGE/"authority_manifest.json").read_text())["entries"];selectors=json.loads((PACKAGE/"selector_contract.json").read_text())["selectors"]
    with pytest.raises(driver_core.ShapeDriverError,match="UNRESOLVED_SELECTOR"):driver_core.snapshot(entries,synthetic_objects(missing_selector=selector_id),selectors)

@pytest.mark.parametrize("selector_id",REQUIRED_SELECTORS)
def test_type_mismatch_fails_closed(selector_id):
    build();entries=json.loads((PACKAGE/"authority_manifest.json").read_text())["entries"];selectors=json.loads((PACKAGE/"selector_contract.json").read_text())["selectors"]
    with pytest.raises(driver_core.ShapeDriverError,match="TYPE_MISMATCH"):driver_core.snapshot(entries,synthetic_objects(type_mismatch_selector=selector_id),selectors)

@pytest.mark.parametrize("selector_id",REQUIRED_SELECTORS)
def test_independent_verifier_missing_selector_fails_without_substitution(selector_id):
    build();entries=json.loads((PACKAGE/"authority_manifest.json").read_text())["entries"];selectors=json.loads((PACKAGE/"selector_contract.json").read_text())["selectors"];clean=driver_core.snapshot(entries,synthetic_objects(),selectors)
    with pytest.raises(verifier_core.ShapeVerifierError,match="UNRESOLVED_SELECTOR"):verifier_core.verify_snapshot(entries,synthetic_objects(missing_selector=selector_id),selectors,clean)

@pytest.mark.parametrize("selector_id",REQUIRED_SELECTORS)
def test_independent_verifier_type_mismatch_fails(selector_id):
    build();entries=json.loads((PACKAGE/"authority_manifest.json").read_text())["entries"];selectors=json.loads((PACKAGE/"selector_contract.json").read_text())["selectors"];clean=driver_core.snapshot(entries,synthetic_objects(),selectors)
    with pytest.raises(verifier_core.ShapeVerifierError,match="WRONG_SELECTOR_TYPE"):verifier_core.verify_snapshot(entries,synthetic_objects(type_mismatch_selector=selector_id),selectors,clean)

def test_full_four_command_cli_and_exact_26_receipts():
    case=make_case()
    results=[run(case,c) for c in ("shape-preflight","extract-shape","verify-shape","package-shape")]
    assert [x.returncode for x in results]==[0,0,0,0],[x.stderr for x in results]
    receipts=sorted(case["roots"]["driver_receipts"].glob("*.json"))+sorted(case["roots"]["verifier_receipts"].glob("*.json"));assert len(receipts)==26
    values=[json.loads(p.read_text()) for p in receipts];assert [x["cumulative_ordinal"] for x in values]==list(range(1,27));assert [x["lane"] for x in values]==["DRIVER"]*13+["VERIFIER"]*13
    terminal=json.loads((case["roots"]["terminal"]/"TERMINAL.json").read_text());assert terminal["status"]=="TECHNICAL_SUCCESS_NEVER_FORMAL";assert terminal["record_kind"]=="TECHNICAL_SHAPE_RUN_TERMINAL";assert terminal["authority_read_count"]==26
    assert (case["roots"]["package"]/"SHAPE_PACKAGE.json").exists()

def test_structural_snapshot_contains_no_scalar_values_hashes_or_lengths():
    case=make_case();assert run(case,"shape-preflight").returncode==0;assert run(case,"extract-shape").returncode==0
    raw=(case["roots"]["staging"]/"driver_shape_snapshot.json").read_text()
    assert "ULTRA_SECRET_SCALAR" not in raw and "987654321" not in raw and "12345.6789" not in raw
    value=json.loads(raw);allowed=set(value)-{"objects"};assert allowed=={"schema_version","record_kind","task_id","batch_id","run_id","claim_ceiling","authority_read_count","structural_snapshot_digest","member_count","scientific_artifact_count","final_test_read"}
    for row in value["objects"]:assert set(row)=={"purpose","source_path","source_sha256","source_pointer","available_json_pointer_set","node_type_by_pointer","array_arity_by_pointer","object_arity_by_pointer","structural_digest","candidate_selector_status_by_id"}

def test_partial_driver_read_failure_is_honest_and_permanent():
    case=make_case(fail_driver=5);assert run(case,"shape-preflight").returncode==0;r=run(case,"extract-shape");assert r.returncode==2
    terminal=json.loads((case["roots"]["terminal"]/"TERMINAL.json").read_text());assert terminal["authority_read_count"]==5 and terminal["status"]=="FAIL_CLOSED"
    assert run(case,"extract-shape").returncode==2;assert len(list(case["roots"]["driver_receipts"].glob("*.json")))==5

def test_partial_verifier_read_failure_is_honest_and_permanent():
    case=make_case(fail_verifier=4);assert run(case,"shape-preflight").returncode==0;assert run(case,"extract-shape").returncode==0;r=run(case,"verify-shape");assert r.returncode==2
    terminal=json.loads((case["roots"]["terminal"]/"TERMINAL.json").read_text());assert terminal["authority_read_count"]==17 and terminal["verifier_read_count"]==4
    assert not (case["roots"]["staging"]/"independent_shape_report.json").exists()

def test_real_subprocess_kill_preserves_partial_receipts_and_next_observation_seals_failure():
    case=make_case(read_delay_ms=100);assert run(case,"shape-preflight").returncode==0
    process=subprocess.Popen(argv(case,"extract-shape"),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    deadline=time.time()+5
    while time.time()<deadline and len(list(case["roots"]["driver_receipts"].glob("*.json")))<3:time.sleep(.01)
    process.kill();process.communicate(timeout=5)
    count=len(list(case["roots"]["driver_receipts"].glob("*.json")));assert 1<=count<13;assert not (case["roots"]["staging"]/"driver_shape_snapshot.json").exists()
    observed=run(case,"extract-shape");assert observed.returncode==2
    terminal=json.loads((case["roots"]["terminal"]/"TERMINAL.json").read_text());assert terminal["status"]=="FAIL_CLOSED" and terminal["authority_read_count"]==count

def test_eight_process_one_use_dispatch():
    case=make_case();procs=[subprocess.Popen(argv(case,"shape-preflight"),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)];results=[p.communicate()+(p.returncode,) for p in procs]
    assert sum(code==0 for _,_,code in results)==1;assert (case["roots"]["side_records"]/"SHAPE_DISPATCH_CONSUMED.json").exists()

def test_control_extra_field_rejected_pre_read():
    case=make_case();value=json.loads(case["dispatch"].read_text());value["unexpected"]=1;write(case["dispatch"],value);r=run(case,"shape-preflight");assert r.returncode==2;assert not case["roots"]["driver_receipts"].exists()

@pytest.mark.parametrize("field",["run_id","dispatch_id","authority_manifest_sha256","selector_contract_sha256","guardian_contract_sha256","technical_bundle_sha256"])
def test_cross_run_or_hash_binding_mutation_rejected_pre_read(field):
    case=make_case();value=json.loads(case["dispatch"].read_text());value[field]="0"*64;write(case["dispatch"],value);r=run(case,"shape-preflight");assert r.returncode==2;assert not case["roots"]["driver_receipts"].exists()

def test_coordinated_arbitrary_root_rejected_by_both_runtime_templates():
    case=make_case()
    for path in (case["release"],case["attestation"],case["dispatch"]):
        value=json.loads(path.read_text());value["roots"]={name:f".r11t/arbitrary/{name}" for name in value["roots"]};write(path,value)
    assert run(case,"shape-preflight").returncode==2;assert not case["roots"]["driver_receipts"].exists()

def test_package_recomputes_report_terminal_and_snapshot_digest_binding():
    case=make_case();assert all(run(case,c).returncode==0 for c in ("shape-preflight","extract-shape","verify-shape"));report=case["roots"]["staging"]/"independent_shape_report.json";value=json.loads(report.read_text());value["structural_snapshot_digest"]="0"*64;write(report,value)
    assert run(case,"package-shape").returncode==2;assert not (case["roots"]["package"]/"SHAPE_PACKAGE.json").exists()

def test_wrong_exact_argv_rejected_pre_read():
    case=make_case();bad=argv(case,"shape-preflight")+["--extra"];r=subprocess.run(bad,text=True,capture_output=True);assert r.returncode!=0;assert not case["roots"]["driver_receipts"].exists()

def test_package_zero_unlisted_and_no_scientific_graph():
    case=make_case();assert all(run(case,c).returncode==0 for c in ("shape-preflight","extract-shape","verify-shape"));(case["roots"]["staging"]/"UNLISTED.json").write_text("{}")
    before={p.relative_to(case["roots"]["staging"].parent).as_posix():p.read_bytes() for p in case["roots"]["staging"].parent.rglob("*") if p.is_file()};assert run(case,"package-shape").returncode==2;after={p.relative_to(case["roots"]["staging"].parent).as_posix():p.read_bytes() for p in case["roots"]["staging"].parent.rglob("*") if p.is_file()};assert after==before;assert not (case["roots"]["terminal"]/"TERMINAL.json").exists()

def test_draft_and_negative_capabilities_are_frozen_zero_state():
    build();draft=json.loads((PACKAGE/"DRAFT.json").read_text());assert draft["attempt"]==0 and draft["run_id"] is None and not any(draft["permissions"].values()) and draft["final_test_read"] is False
    negative=json.loads((PACKAGE/"negative_capability_manifest.json").read_text());assert "SCALAR_VALUES" in negative["forbidden"] and negative["pointer_substitution_allowed"] is False
