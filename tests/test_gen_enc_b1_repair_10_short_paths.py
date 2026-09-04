from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import jsonschema
import pytest

from scripts.gen_enc_b1_repair_10 import formal_driver as driver
from scripts.gen_enc_b1_repair_10 import independent_verifier as verifier
from scripts.gen_enc_b1_repair_10.primitives import PrimitiveError, canonical, sha_file
from tests.helpers.gen_enc_b1_repair_10_control import setup

REPO=Path(__file__).resolve().parents[1]
SCHEMAS=REPO/"schemas/gen_enc/b1_repair_10"


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
    with pytest.raises((driver.Repair10Error,KeyError)):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"generate-staging")
    with pytest.raises((verifier.Verify10Error,KeyError)):verifier.gate(c["root"],c["release"],c["attestation"],SCHEMAS)
    assert driver.authority_read_count(d)==0


def test_schema_valid_runtime_invalid_and_runtime_shape_valid_schema_invalid_are_both_rejected(tmp_path:Path)->None:
    c=setup(tmp_path/"mutual");ss=schemas();att=json.loads(c["attestation"].read_text());runtime_bad=copy.deepcopy(att);runtime_bad["authority_allowlist_sha256"]="0"*64
    jsonschema.validate(runtime_bad,ss["technical_guardian_attestation"]);c["attestation"].write_bytes(canonical(runtime_bad))
    with pytest.raises(driver.Repair10Error,match="ATTESTATION_BINDING"):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"preflight")
    c=setup(tmp_path/"extra");att=json.loads(c["attestation"].read_text());release=json.loads(c["release"].read_text());att["unlisted"]=True
    assert all(att.get(k)==release.get(k) for k in driver._binding(release))
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(att,ss["technical_guardian_attestation"])
    c["attestation"].write_bytes(canonical(att))
    with pytest.raises(driver.Repair10Error,match="SCHEMA_technical_guardian_attestation"):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"preflight")


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
    with pytest.raises((driver.Repair10Error,PrimitiveError,ValueError,json.JSONDecodeError)):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"preflight")
    c=setup(tmp_path/("v"+attack[:3]));contexts(c);release=json.loads(c["release"].read_text());issued_path=c["root"]/release["phase_a_dispatch_path"];attack_dispatch(issued_path,attack)
    with pytest.raises((verifier.Verify10Error,PrimitiveError,ValueError,json.JSONDecodeError)):verifier.gate(c["root"],c["release"],c["attestation"],SCHEMAS)


@pytest.mark.parametrize("subject",["advisor_b_final_review","advisor_b_ledger_snapshot"])
def test_dynamic_advisor_subject_hash_mutation_fails_before_authority_read(subject:str,tmp_path:Path)->None:
    c=setup(tmp_path/subject[-8:]);d,_=contexts(c);release=json.loads(c["release"].read_text());path=c["root"]/release[subject+"_path"];path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises((driver.Repair10Error,PrimitiveError)):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"generate-staging")
    with pytest.raises((verifier.Verify10Error,PrimitiveError)):verifier.gate(c["root"],c["release"],c["attestation"],SCHEMAS)
    assert driver.authority_read_count(d)==0


@pytest.mark.parametrize("path",[driver.PATH_ADDRESSABILITY_FAIL_PATH,driver.R10_REGISTRATION_PATH,driver.ROLLOVER_SIGNING_FAIL_PATH,driver.ROLLOVER_REGISTRATION_PATH,driver.GUARDIAN_SIGNING_CHECK_PATH,driver.ADVISOR_B_FINAL_REVIEW_PATH,driver.ADVISOR_LEDGER_SNAPSHOT_PROTOCOL_PATH,driver.R07_LEDGER_SNAPSHOT_ABSENCE_PATH])
def test_each_fixed_signing_provenance_byte_mutation_fails_both_pre_read_gates(path:str,tmp_path:Path)->None:
    c=setup(tmp_path/(Path(path).stem[:8]));target=c["root"]/path;target.write_bytes(target.read_bytes()+b" ")
    with pytest.raises((driver.Repair10Error,PrimitiveError)):driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"preflight")
    with pytest.raises((verifier.Verify10Error,PrimitiveError)):verifier.gate(c["root"],c["release"],c["attestation"],SCHEMAS)


@pytest.mark.parametrize("subject",["FINAL_REVIEW","LEDGER_SNAPSHOT"])
def test_dynamic_advisor_subject_wrong_root_is_rejected_without_discovery(subject:str,tmp_path:Path)->None:
    c=setup(tmp_path/subject.lower());release=json.loads(c["release"].read_text());key="advisor_b_final_review_path" if subject=="FINAL_REVIEW" else "advisor_b_ledger_snapshot_path";release[key]="elsewhere/"+Path(release[key]).name
    with pytest.raises(driver.Repair10Error,match="ADVISOR_DYNAMIC_ROOT"):driver._validate_signing_authority_bytes(c["root"],release,True)
    with pytest.raises(verifier.Verify10Error,match="ADVISOR_DYNAMIC_ROOT"):verifier._validate_signing_authority_bytes(c["root"],release,True)


def test_attestation_schema_required_set_is_runtime_binding_superset_and_no_discovery()->None:
    ss=schemas();required=set(ss["guardian_attestation"]["required"]);binding=set(driver._binding.__code__.co_consts[1]) if False else set(driver._binding({k:None for k in ("task_id","batch_id","run_id","mode","commands_exact","guardian_two_phase_contract_path","guardian_two_phase_contract_sha256","guardian_two_phase_review_path","guardian_two_phase_review_sha256","advisor_b_final_review_path","advisor_b_final_review_sha256","advisor_b_ledger_snapshot_path","advisor_b_ledger_snapshot_sha256","phase_a_commands_exact","phase_a_permissions","phase_a_release_path","phase_a_attestation_path","phase_a_dispatch_id","phase_a_dispatch_path","guardian_phase_b_authorization_path","guardian_phase_b_attestation_path","phase_b_dispatch_path","authority_allowlist_path","authority_allowlist_sha256","verification_subject_seal_path","projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256","source_manifest_path","source_manifest_sha256","schema_manifest_path","schema_manifest_sha256","command_manifest_path","command_manifest_sha256","roots")}))
    assert binding<=required and ss["guardian_attestation"]["additionalProperties"] is False
    for path in (REPO/"scripts/gen_enc_b1_repair_10/formal_driver.py",REPO/"scripts/gen_enc_b1_repair_10/independent_verifier.py"):
        text=path.read_text();block=text[text.index("def _validate_signing_authority_bytes"):text.index("def ",text.index("def _validate_signing_authority_bytes")+5)]
        assert ".glob(" not in block and ".rglob(" not in block and "iterdir(" not in block
        control=text[text.index("def _validate_cli_control_addressability"):text.index("def ",text.index("def _validate_cli_control_addressability")+5)]
        assert all(token not in control for token in (".glob(",".rglob(","iterdir(","getenv(","environ"))


PREDECESSOR={"phase_a_release_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_08/control/PHASE_A_RELEASE.json","phase_a_attestation_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_08/control/PHASE_A_GUARDIAN_ATTESTATION.json","phase_a_dispatch_path":"control/PHASE_A_DISPATCH_AUTHORIZATION.json"}


@pytest.mark.parametrize("field",list(PREDECESSOR))
def test_all_predecessor_control_paths_rejected_by_both_entrypoints_before_read(field:str,tmp_path:Path)->None:
    c=setup(tmp_path/field[-8:]);release=json.loads(c["release"].read_text());release[field]=PREDECESSOR[field]
    with pytest.raises(driver.Repair10Error,match="ROLLOVER_"):driver._validate_rollover_paths(release,c["release"],c["attestation"],c["dispatch"],c["root"],True)
    with pytest.raises(verifier.Verify10Error,match="ROLLOVER_"):verifier._validate_rollover_paths(release,c["release"],c["attestation"],c["dispatch"],c["root"],True)
    assert not c["roots"]["side_records"].exists()


@pytest.mark.parametrize("attack",["same_path","cross_run","casefold","traversal","absolute","revoked_run","revoked_dispatch","r09_revoked_run","r09_revoked_dispatch"])
def test_rollover_path_run_and_dispatch_attacks_fail_both_independent_validators(attack:str,tmp_path:Path)->None:
    c=setup(tmp_path/attack);release=json.loads(c["release"].read_text());rid=release["run_id"]
    if attack=="same_path":release["phase_a_attestation_path"]=release["phase_a_release_path"]
    elif attack=="cross_run":release["phase_a_dispatch_path"]=release["phase_a_dispatch_path"].replace(rid,"f"*64)
    elif attack=="casefold":release["phase_a_release_path"]=release["phase_a_release_path"].replace("/R.json","/r.json")
    elif attack=="traversal":release["phase_a_dispatch_path"]="technical/dispatch_rollover/../"+Path(release["phase_a_dispatch_path"]).name
    elif attack=="absolute":release["phase_a_release_path"]="C:/forbidden/PHASE_A_RELEASE.json"
    elif attack=="revoked_run":release["run_id"]=driver.REVOKED_RUN_ID
    elif attack=="revoked_dispatch":release["phase_a_dispatch_id"]=driver.REVOKED_DISPATCH_ID
    elif attack=="r09_revoked_run":release["run_id"]=driver.R09_REVOKED_RUN_ID
    else:release["phase_a_dispatch_id"]=driver.R09_REVOKED_DISPATCH_ID
    with pytest.raises(driver.Repair10Error,match="ROLLOVER_"):driver._validate_rollover_paths(release,c["release"],c["attestation"],c["dispatch"],c["root"],True)
    with pytest.raises(verifier.Verify10Error,match="ROLLOVER_"):verifier._validate_rollover_paths(release,c["release"],c["attestation"],c["dispatch"],c["root"],True)


def test_cross_run_control_mix_and_cli_dispatch_substitution_fail_pre_read(tmp_path:Path)->None:
    c1=setup(tmp_path/"one");c2=setup(tmp_path/"two")
    with pytest.raises(driver.Repair10Error,match="CONTROL_|ROLLOVER_"):driver.validate_control(c1["root"],c1["release"],c2["attestation"],SCHEMAS,"preflight",c1["dispatch"])
    with pytest.raises(verifier.Verify10Error,match="CONTROL_|ROLLOVER_"):verifier.gate(c1["root"],c1["release"],c2["attestation"],SCHEMAS)
    rel=lambda p:p.relative_to(c1["root"]).as_posix();wrong_dispatch=c2["dispatch"].relative_to(c2["root"]).as_posix();args=[sys.executable,"-m","scripts.gen_enc_b1_repair_10.formal_driver","preflight","--repo-root",".","--release",rel(c1["release"]),"--guardian-attestation",rel(c1["attestation"]),"--phase-a-dispatch",wrong_dispatch,"--schema-root",str(SCHEMAS),"--projection-contract",driver.PROJECTION_PATH,"--dependency-matrix",driver.DEPENDENCY_PATH];env=dict(os.environ);env["PYTHONPATH"]=str(REPO)+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "");result=subprocess.run(args,cwd=c1["root"],env=env,text=True,capture_output=True,check=False)
    assert result.returncode==2 and ("CONTROL_PATH_ROLE_OR_RUN_COLLISION" in result.stderr or "ROLLOVER_DISPATCH_CLI_BINDING" in result.stderr) and '"authority_read_count": 0' in result.stderr and not c1["roots"]["side_records"].exists()


def test_successor_paths_unique_run_bound_and_manifest_placeholder_mechanism(tmp_path:Path)->None:
    c=setup(tmp_path/"newrun");release=json.loads(c["release"].read_text());rid=release["run_id"];paths=[release[x] for x in ("phase_a_release_path","phase_a_attestation_path","phase_a_dispatch_path")]
    assert len({x.casefold() for x in paths})==3 and all(rid in x for x in paths) and not any(x in PREDECESSOR.values() for x in paths)
    manifest=json.loads((REPO/"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_10/command_manifest.json").read_text());placeholders={"<GUARDIAN_PHASE_A_RELEASE_EXACT_PATH>","<GUARDIAN_PHASE_A_ATTESTATION_EXACT_PATH>","<CONTROLLER_PHASE_A_DISPATCH_EXACT_PATH>"}
    assert set(manifest["signed_path_substitution_only"])==placeholders and all(placeholders<=set(row["argv_after_python"]) for row in manifest["entries"])
    assert paths==[f"{driver.CONTROL_ROOT}/{rid}/R.json",f"{driver.CONTROL_ROOT}/{rid}/A.json",f"{driver.CONTROL_ROOT}/{rid}/D.json"]
    assert len(paths[0])==driver.CONTROL_RELATIVE_CHARS==98


def test_predecessor_sealed_bytes_preserved_and_old_paths_schema_invalid(tmp_path:Path)->None:
    expected={"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_08/control/PHASE_A_RELEASE.json":"2d5e85b338e83c53998a279b806301c58b516f767ab020581c3220b9cc379a03","outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_08/control/PHASE_A_GUARDIAN_ATTESTATION.json":"0219fa01cfd0408c83c4790b05da2da434a4fb7d568ad19aa20431e818cf0ad3","control/PHASE_A_DISPATCH_AUTHORIZATION.json":"4643569d7acd2bff3165f2cfb8f7ae5964d707a3b4a8af7ebea414ebaedd54a6"}
    assert all(sha_file(REPO/p)==h for p,h in expected.items());c=setup(tmp_path/"schemaold");att=json.loads(c["attestation"].read_text());att["phase_a_dispatch_path"]=PREDECESSOR["phase_a_dispatch_path"]
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(att,schemas()["technical_guardian_attestation"])
    assert all(sha_file(REPO/p)==h for p,h in expected.items())


R09_LONG_PATHS=(
    "outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_09/control_rollover/0135cb06febe7bf5aa7beca053d3b45c42dbeddb1c1ef9bffe2b882cdd8f606d/PHASE_A_RELEASE.0135cb06febe7bf5aa7beca053d3b45c42dbeddb1c1ef9bffe2b882cdd8f606d.json",
    "outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_09/control_rollover/0135cb06febe7bf5aa7beca053d3b45c42dbeddb1c1ef9bffe2b882cdd8f606d/PHASE_A_GUARDIAN_ATTESTATION.0135cb06febe7bf5aa7beca053d3b45c42dbeddb1c1ef9bffe2b882cdd8f606d.json",
    "control/gen_enc_fast_b1_repair_09/0135cb06febe7bf5aa7beca053d3b45c42dbeddb1c1ef9bffe2b882cdd8f606d/PHASE_A_DISPATCH_AUTHORIZATION.0135cb06febe7bf5aa7beca053d3b45c42dbeddb1c1ef9bffe2b882cdd8f606d.json",
)


def test_revoked_r09_long_paths_and_ids_are_pre_read_rejected(tmp_path:Path)->None:
    c=setup(tmp_path/"r09-long");release=json.loads(c["release"].read_text())
    for field,value in zip(("phase_a_release_path","phase_a_attestation_path","phase_a_dispatch_path"),R09_LONG_PATHS):
        changed={**release,field:value}
        with pytest.raises(driver.Repair10Error,match="ROLLOVER_PATH"):driver._validate_rollover_paths(changed,c["release"],c["attestation"],c["dispatch"],c["root"],True)
        with pytest.raises(verifier.Verify10Error,match="ROLLOVER_PATH"):verifier._validate_rollover_paths(changed,c["release"],c["attestation"],c["dispatch"],c["root"],True)
    for key,value in (("run_id",driver.R09_REVOKED_RUN_ID),("phase_a_dispatch_id",driver.R09_REVOKED_DISPATCH_ID)):
        changed={**release,key:value}
        with pytest.raises(driver.Repair10Error,match="ROLLOVER_"):driver._validate_rollover_paths(changed,c["release"],c["attestation"],c["dispatch"],c["root"],True)
        with pytest.raises(verifier.Verify10Error,match="ROLLOVER_"):verifier._validate_rollover_paths(changed,c["release"],c["attestation"],c["dispatch"],c["root"],True)


def test_revoked_r09_long_release_path_full_cli_fails_before_read(tmp_path:Path)->None:
    c=setup(tmp_path/"old-cli");rel=lambda p:p.relative_to(c["root"]).as_posix()
    args=[sys.executable,"-m","scripts.gen_enc_b1_repair_10.formal_driver","preflight","--repo-root",".","--release",R09_LONG_PATHS[0],"--guardian-attestation",rel(c["attestation"]),"--phase-a-dispatch",rel(c["dispatch"]),"--schema-root",str(SCHEMAS),"--projection-contract",driver.PROJECTION_PATH,"--dependency-matrix",driver.DEPENDENCY_PATH]
    env=dict(os.environ);env["PYTHONPATH"]=str(REPO)+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    result=subprocess.run(args,cwd=c["root"],env=env,text=True,capture_output=True,check=False)
    assert result.returncode==2 and "CONTROL_" in result.stderr and '"authority_read_count": 0' in result.stderr
    assert not c["roots"]["side_records"].exists()


def _synthetic_root_of_length(length:int)->Path:
    value=Path("D:/"+("x"*(length-3)))
    assert len(str(value.resolve()))==length
    return value


def test_frozen_workspace_and_absolute_length_boundaries()->None:
    rid="e"*64;relative={role:f"{driver.CONTROL_ROOT}/{rid}/{name}" for role,name in (("release","R.json"),("attestation","A.json"),("dispatch","D.json"))}
    at_limit=_synthetic_root_of_length(driver.MAX_WORKSPACE_PREFIX_CHARS)
    args=(at_limit,*(at_limit/relative[x] for x in ("release","attestation","dispatch")))
    driver._validate_cli_control_addressability(*args);verifier._validate_cli_control_addressability(*args)
    assert max(len(str(x.resolve())) for x in args[1:])==driver.MAX_CONTROL_ABSOLUTE_CHARS==219
    over=_synthetic_root_of_length(driver.MAX_WORKSPACE_PREFIX_CHARS+1)
    over_args=(over,*(over/relative[x] for x in ("release","attestation","dispatch")))
    with pytest.raises(driver.Repair10Error,match="WORKSPACE_PREFIX_BUDGET"):driver._validate_cli_control_addressability(*over_args)
    with pytest.raises(verifier.Verify10Error,match="WORKSPACE_PREFIX_BUDGET"):verifier._validate_cli_control_addressability(*over_args)


def test_overlength_and_max_path_inputs_fail_before_any_read(tmp_path:Path)->None:
    c=setup(tmp_path/"overlength");rid=c["run_id"];too_long=c["root"]/("z"*130)/driver.CONTROL_ROOT/rid/"R.json"
    with pytest.raises(driver.Repair10Error,match="CONTROL_MAX_PATH"):driver._validate_cli_control_addressability(c["root"],too_long,c["attestation"],c["dispatch"])
    with pytest.raises(verifier.Verify10Error,match="CONTROL_MAX_PATH"):verifier._validate_cli_control_addressability(c["root"],too_long,c["attestation"],c["dispatch"])
    assert not too_long.exists() and not c["roots"]["side_records"].exists()


def test_current_workspace_task_owned_mirror_ordinary_pathlib_and_full_cli()->None:
    mirror=REPO/".r10_technical_mirrors"/uuid.uuid4().hex[:8]
    c=setup(mirror);release=json.loads(c["release"].read_text());paths=(c["release"],c["attestation"],c["dispatch"])
    assert len(str(REPO.resolve()))==43
    assert len(f"{driver.CONTROL_ROOT}/{'0'*64}/R.json")==98
    assert len(str((REPO/f"{driver.CONTROL_ROOT}/{'0'*64}/R.json").resolve()))==142
    for path in paths:
        raw=path.read_bytes();assert sha_file(path) and canonical(json.loads(raw))==raw
    rel=lambda p:p.relative_to(mirror).as_posix();args=[sys.executable,"-m","scripts.gen_enc_b1_repair_10.formal_driver","preflight","--repo-root",".","--release",rel(c["release"]),"--guardian-attestation",rel(c["attestation"]),"--phase-a-dispatch",rel(c["dispatch"]),"--schema-root",str(SCHEMAS),"--projection-contract",driver.PROJECTION_PATH,"--dependency-matrix",driver.DEPENDENCY_PATH]
    env=dict(os.environ);env["PYTHONPATH"]=str(REPO)+(os.pathsep+env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    result=subprocess.run(args,cwd=mirror,env=env,text=True,capture_output=True,check=False)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)["status"]=="PREFLIGHT_CONSUMED_NO_AUTHORITY_READ" and driver.authority_read_count({"roots_resolved":c["roots"]})==0
