from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from scripts.gen_enc_b1_repair_08 import formal_driver as driver
from scripts.gen_enc_b1_repair_08 import independent_verifier as verifier
from scripts.gen_enc_b1_repair_08.primitives import PrimitiveError, canonical, sha_file
from tests.helpers.gen_enc_b1_repair_08_control import setup

REPO=Path(__file__).resolve().parents[1]
SCHEMAS=REPO/"schemas/gen_enc/b1_repair_08"


def schemas()->dict:
    return {p.name.removesuffix(".schema.json"):json.loads(p.read_text()) for p in SCHEMAS.glob("*.schema.json")}


def contexts(c:dict)->tuple[dict,dict]:
    d=driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"preflight");driver.consume_once(d)
    v=verifier.gate(c["root"],c["release"],c["attestation"],SCHEMAS)
    return d,v


def test_guardian_signing_satisfiability_fixture_passes_schema_and_both_pre_read_gates(tmp_path:Path)->None:
    c=setup(tmp_path/"sat");ss=schemas();release=json.loads(c["release"].read_text());att=json.loads(c["attestation"].read_text());issued=json.loads((c["root"]/release["phase_a_dispatch_path"]).read_text())
    jsonschema.validate(att,ss["technical_guardian_attestation"]);jsonschema.validate(issued,ss["technical_phase_dispatch"])
    d,v=contexts(c)
    assert d["authority_read_count"]==v["authority_read_count"]==0
    assert release["advisor_b_final_review_path"].startswith("technical/") and release["advisor_b_ledger_snapshot_path"].startswith("technical/")


ATT_FIELDS=("commands_exact","authority_allowlist_path","authority_allowlist_sha256","source_manifest_path","source_manifest_sha256","schema_manifest_path","schema_manifest_sha256","command_manifest_path","command_manifest_sha256","roots")


def mutate_binding(value:dict,field:str)->None:
    if field=="commands_exact":value[field]=["verify","generate-staging","preflight"]
    elif field=="roots":value[field]={**value[field],"staging":value[field]["staging"]+"-wrong"}
    elif field.endswith("sha256"):value[field]="0"*64
    else:value[field]=value[field]+".wrong"


@pytest.mark.parametrize("field",ATT_FIELDS)
def test_each_attestation_runtime_field_mutation_fails_both_pre_read_gates(field:str,tmp_path:Path)->None:
    c=setup(tmp_path/field[:5]);d,_=contexts(c);att=json.loads(c["attestation"].read_text());mutate_binding(att,field);c["attestation"].write_bytes(canonical(att))
    with pytest.raises((driver.Repair08Error,KeyError)):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"generate-staging")
    with pytest.raises((verifier.Verify08Error,KeyError)):verifier.gate(c["root"],c["release"],c["attestation"],SCHEMAS)
    assert driver.authority_read_count(d)==0


def test_schema_valid_runtime_invalid_and_runtime_shape_valid_schema_invalid_are_both_rejected(tmp_path:Path)->None:
    c=setup(tmp_path/"mutual");ss=schemas();att=json.loads(c["attestation"].read_text());runtime_bad=copy.deepcopy(att);runtime_bad["authority_allowlist_sha256"]="0"*64
    jsonschema.validate(runtime_bad,ss["technical_guardian_attestation"]);c["attestation"].write_bytes(canonical(runtime_bad))
    with pytest.raises(driver.Repair08Error,match="ATTESTATION_BINDING"):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"preflight")
    c=setup(tmp_path/"extra");att=json.loads(c["attestation"].read_text());release=json.loads(c["release"].read_text());att["unlisted"]=True
    assert all(att.get(k)==release.get(k) for k in driver._binding(release))
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(att,ss["technical_guardian_attestation"])
    c["attestation"].write_bytes(canonical(att))
    with pytest.raises(driver.Repair08Error,match="SCHEMA_technical_guardian_attestation"):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"preflight")


DISPATCH_ATTACKS=("record_kind","state","phase","one_use","revoked","final_test_read","extra","old_run","noncanonical")


def attack_dispatch(path:Path,attack:str)->None:
    if attack=="noncanonical":path.write_bytes(path.read_bytes()+b" ");return
    value=json.loads(path.read_text())
    replacements={"record_kind":"OLD_DISPATCH","state":"PHASE_B_ISSUED","phase":"B","one_use":False,"revoked":True,"final_test_read":True,"old_run":"0"*64}
    if attack=="extra":value["unlisted"]=True
    else:value["run_id" if attack=="old_run" else attack]=replacements[attack]
    path.write_bytes(canonical(value))


@pytest.mark.parametrize("attack",DISPATCH_ATTACKS)
def test_phase_a_dispatch_constants_and_structure_reject_in_both_entries(attack:str,tmp_path:Path)->None:
    c=setup(tmp_path/("d"+attack[:3]));release=json.loads(c["release"].read_text());issued_path=c["root"]/release["phase_a_dispatch_path"];attack_dispatch(issued_path,attack)
    with pytest.raises((driver.Repair08Error,PrimitiveError,ValueError,json.JSONDecodeError)):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"preflight")
    c=setup(tmp_path/("v"+attack[:3]));contexts(c);release=json.loads(c["release"].read_text());issued_path=c["root"]/release["phase_a_dispatch_path"];attack_dispatch(issued_path,attack)
    with pytest.raises((verifier.Verify08Error,PrimitiveError,ValueError,json.JSONDecodeError)):verifier.gate(c["root"],c["release"],c["attestation"],SCHEMAS)


@pytest.mark.parametrize("subject",["advisor_b_final_review","advisor_b_ledger_snapshot"])
def test_dynamic_advisor_subject_hash_mutation_fails_before_authority_read(subject:str,tmp_path:Path)->None:
    c=setup(tmp_path/subject[-8:]);d,_=contexts(c);release=json.loads(c["release"].read_text());path=c["root"]/release[subject+"_path"];path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises((driver.Repair08Error,PrimitiveError)):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"generate-staging")
    with pytest.raises((verifier.Verify08Error,PrimitiveError)):verifier.gate(c["root"],c["release"],c["attestation"],SCHEMAS)
    assert driver.authority_read_count(d)==0


@pytest.mark.parametrize("path",[driver.GUARDIAN_SIGNING_CHECK_PATH,driver.ADVISOR_B_FINAL_REVIEW_PATH,driver.ADVISOR_LEDGER_SNAPSHOT_PROTOCOL_PATH,driver.R07_LEDGER_SNAPSHOT_ABSENCE_PATH])
def test_each_fixed_signing_provenance_byte_mutation_fails_both_pre_read_gates(path:str,tmp_path:Path)->None:
    c=setup(tmp_path/(Path(path).stem[:8]));target=c["root"]/path;target.write_bytes(target.read_bytes()+b" ")
    with pytest.raises((driver.Repair08Error,PrimitiveError)):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"preflight")
    with pytest.raises((verifier.Verify08Error,PrimitiveError)):verifier.gate(c["root"],c["release"],c["attestation"],SCHEMAS)


@pytest.mark.parametrize("subject",["FINAL_REVIEW","LEDGER_SNAPSHOT"])
def test_dynamic_advisor_subject_wrong_root_is_rejected_without_discovery(subject:str,tmp_path:Path)->None:
    c=setup(tmp_path/subject.lower());release=json.loads(c["release"].read_text());key="advisor_b_final_review_path" if subject=="FINAL_REVIEW" else "advisor_b_ledger_snapshot_path";release[key]="elsewhere/"+Path(release[key]).name
    with pytest.raises(driver.Repair08Error,match="ADVISOR_DYNAMIC_ROOT"):driver._validate_signing_authority_bytes(c["root"],release,True)
    with pytest.raises(verifier.Verify08Error,match="ADVISOR_DYNAMIC_ROOT"):verifier._validate_signing_authority_bytes(c["root"],release,True)


def test_attestation_schema_required_set_is_runtime_binding_superset_and_no_discovery()->None:
    ss=schemas();required=set(ss["guardian_attestation"]["required"]);binding=set(driver._binding.__code__.co_consts[1]) if False else set(driver._binding({k:None for k in ("task_id","batch_id","run_id","mode","commands_exact","guardian_two_phase_contract_path","guardian_two_phase_contract_sha256","guardian_two_phase_review_path","guardian_two_phase_review_sha256","advisor_b_final_review_path","advisor_b_final_review_sha256","advisor_b_ledger_snapshot_path","advisor_b_ledger_snapshot_sha256","phase_a_commands_exact","phase_a_permissions","phase_a_dispatch_id","phase_a_dispatch_path","guardian_phase_b_authorization_path","guardian_phase_b_attestation_path","phase_b_dispatch_path","authority_allowlist_path","authority_allowlist_sha256","verification_subject_seal_path","projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256","source_manifest_path","source_manifest_sha256","schema_manifest_path","schema_manifest_sha256","command_manifest_path","command_manifest_sha256","roots")}))
    assert binding<=required and ss["guardian_attestation"]["additionalProperties"] is False
    for path in (REPO/"scripts/gen_enc_b1_repair_08/formal_driver.py",REPO/"scripts/gen_enc_b1_repair_08/independent_verifier.py"):
        text=path.read_text();block=text[text.index("def _validate_signing_authority_bytes"):text.index("def ",text.index("def _validate_signing_authority_bytes")+5)]
        assert ".glob(" not in block and ".rglob(" not in block and "iterdir(" not in block
