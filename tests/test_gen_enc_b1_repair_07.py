from __future__ import annotations

import json
import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.gen_enc_b1_repair_07 import formal_driver as driver
from scripts.gen_enc_b1_repair_07.primitives import canonical, sha_file, sha_value
from tests.helpers.gen_enc_b1_repair_07_control import authorize_phase_b, setup

REPO=Path(__file__).resolve().parents[1]
SCHEMAS=REPO/"schemas/gen_enc/b1_repair_07"


def env(extra:dict[str,str]|None=None)->dict[str,str]:
    value=dict(os.environ);value["PYTHONPATH"]=str(REPO)+(os.pathsep+value["PYTHONPATH"] if value.get("PYTHONPATH") else "");value.update(extra or {});return value


def argv(module:str,command:str,phase_b:dict|None=None)->list[str]:
    value=[sys.executable,"-m",module,command,"--repo-root",".","--release","control/RELEASE.json","--guardian-attestation","control/GUARDIAN_ATTESTATION.json","--schema-root",str(SCHEMAS),"--projection-contract",driver.PROJECTION_PATH,"--dependency-matrix",driver.DEPENDENCY_PATH]
    if phase_b:
        value += ["--guardian-phase-b-authorization",driver.PHASE_B_AUTH_PATH,"--guardian-phase-b-expected-sha256",phase_b["authorization_sha256"],"--guardian-phase-b-attestation",driver.PHASE_B_ATTESTATION_PATH,"--guardian-phase-b-attestation-expected-sha256",phase_b["phase_b_attestation_sha256"],"--phase-b-dispatch",driver.PHASE_B_DISPATCH_PATH,"--phase-b-dispatch-expected-sha256",phase_b["dispatch_sha256"]]
    return value


def run(c:dict,module:str,command:str,phase_b:dict|None=None,extra:dict[str,str]|None=None)->subprocess.CompletedProcess:
    return subprocess.run(argv(module,command,phase_b),cwd=c["root"],env=env(extra),text=True,capture_output=True,check=False)


def phase_a(root:Path)->dict:
    c=setup(root);assert run(c,"scripts.gen_enc_b1_repair_07.formal_driver","preflight").returncode==0;assert run(c,"scripts.gen_enc_b1_repair_07.formal_driver","generate-staging").returncode==0
    verified=run(c,"scripts.gen_enc_b1_repair_07.independent_verifier","verify");assert verified.returncode==0,verified.stderr
    return c


def phase_b_ready(root:Path)->tuple[dict,dict]:
    c=phase_a(root);return c,authorize_phase_b(c)


def test_phase_a_three_commands_stop_with_canonical_handoff_and_zero_publication(tmp_path:Path)->None:
    c=phase_a(tmp_path/"phase-a");handoff=c["roots"]["side_records"]/driver.PHASE_A_HANDOFF_PATH;value=json.loads(handoff.read_text())
    assert value["state"]=="PHASE_A_VERIFIED_HANDOFF_STOP" and value["phase_a_commands_exact"]==list(driver.PHASE_A_COMMANDS)
    assert value["verification_subject_count"]==27 and value["artifact_graph_count"]==31
    assert value["formal_publication_count"]==value["commit_pointer_count"]==value["success_package_count"]==0
    assert not c["roots"]["run"].exists() and not c["roots"]["pointer"].exists() and not c["roots"]["success"].exists()


def test_phase_a_cannot_publish_and_old_six_command_release_is_rejected(tmp_path:Path)->None:
    c=phase_a(tmp_path/"no-publish");result=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish")
    assert result.returncode==2 and "EXTERNAL_EXPECTED_REQUIRED" in result.stderr and not c["roots"]["run"].exists() and not c["roots"]["pointer"].exists()
    c2=setup(tmp_path/"old-release");release=json.loads(c2["release"].read_text());release["commands_exact"]=list(driver.COMMANDS);release["run_id"]=driver.derive_run_id(release);release["roots"]=driver.exact_roots(release["run_id"],True);c2["release"].write_bytes(canonical(release))
    denied=run(c2,"scripts.gen_enc_b1_repair_07.formal_driver","preflight");assert denied.returncode==2 and "PHASE_A_RELEASE_CONTRACT" in denied.stderr and '"authority_read_count": 0' in denied.stderr


def test_all_phase_b_commands_reject_missing_external_expected_values(tmp_path:Path)->None:
    c=phase_a(tmp_path/"missing-external")
    for command in driver.PHASE_B_COMMANDS:
        result=run(c,"scripts.gen_enc_b1_repair_07.formal_driver",command);assert result.returncode==2 and "EXTERNAL_EXPECTED_REQUIRED" in result.stderr
    assert not c["roots"]["run"].exists() and not c["roots"]["pointer"].exists() and not c["roots"]["success"].exists()


def test_guardian_common_contract_and_review_bytes_are_pre_read_bound(tmp_path:Path)->None:
    for index,rel in enumerate((driver.GUARDIAN_TWO_PHASE_CONTRACT_PATH,driver.GUARDIAN_TWO_PHASE_REVIEW_PATH)):
        c=setup(tmp_path/f"g{index}");path=c["root"]/rel;path.write_bytes(path.read_bytes()+b"\n")
        result=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","preflight");assert result.returncode==2 and "GUARDIAN_TWO_PHASE_AUTHORITY_BYTES" in result.stderr and '"authority_read_count": 0' in result.stderr


def test_repair07_entrypoints_are_independent_and_have_no_dynamic_imports()->None:
    for name in ("formal_driver.py","independent_verifier.py","cad_projection_driver.py","cad_projection_verifier.py"):
        tree=ast.parse((REPO/"scripts/gen_enc_b1_repair_07"/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                module=node.module or "";assert not module.startswith(("scripts.gen_enc_b1.","scripts.gen_enc_b1_repair_01","scripts.gen_enc_b1_repair_02","scripts.gen_enc_b1_repair_03","scripts.gen_enc_b1_repair_04","scripts.gen_enc_b1_repair_05","scripts.gen_enc_b1_repair_06"))
                if name=="formal_driver.py":assert "independent_verifier" not in module and "cad_projection_verifier" not in module
                if name=="independent_verifier.py":assert "formal_driver" not in module and "cad_projection_driver" not in module
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):assert node.func.id!="__import__"
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):assert node.func.attr not in ("import_module","exec_module")


def test_phase_b_full_chain_requires_external_expected_hashes(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"full");published=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b);assert published.returncode==0,published.stderr
    packaged=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","package-results",b);assert packaged.returncode==0,packaged.stderr
    assert len([p for p in c["roots"]["run"].rglob("*") if p.is_file()])==31 and (c["roots"]["pointer"]/"B1.json").is_file()


@pytest.mark.parametrize("attack",["wrong_auth_sha","wrong_att_sha","wrong_dispatch_sha","old_task","old_batch","old_run","phase_a_escalation"])
def test_phase_b_external_and_binding_attacks_fail_zero_publication(attack:str,tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/attack)
    if attack.endswith("sha"):b[{"wrong_auth_sha":"authorization_sha256","wrong_att_sha":"phase_b_attestation_sha256","wrong_dispatch_sha":"dispatch_sha256"}[attack]]="0"*64
    else:
        path=b["authorization"];value=json.loads(path.read_text());value[{"old_task":"task_id","old_batch":"batch_id","old_run":"run_id","phase_a_escalation":"phase_b_permissions"}[attack]]="OLD" if attack!="phase_a_escalation" else {**driver.PHASE_B_PERMISSIONS,"generate_staging":True};path.write_bytes(canonical(value));b["authorization_sha256"]=sha_file(path)
    result=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b)
    assert result.returncode==2 and not c["roots"]["run"].exists() and not (c["roots"]["pointer"]/"B1.json").exists()


def test_coordinated_stage_seal_report_replacement_cannot_match_guardian_hash(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"coordinated");stage=c["roots"]["staging"];member=stage/"members/HAND_01.json";value=json.loads(member.read_text());value["parameters"][value["parameter_order"][0]]+=1e-9;member.write_bytes(canonical(value))
    manifest=stage/"partial_manifests/HAND.json";value=json.loads(manifest.read_text());value["member_entries"][0]["sha256"]=sha_file(member);manifest.write_bytes(canonical(value))
    seal_path=c["roots"]["side_records"]/driver.SUBJECT_SEAL_PATH;seal=json.loads(seal_path.read_text());seal["subject_entries"]=[{"path":rel,"sha256":sha_file(stage/rel)} for rel in driver.verification_subject_paths()];seal["subject_digest"]=sha_value({"domain":"GEN-ENC-FAST-B1-REPAIR-07-VERIFICATION-SUBJECT-v1","entries":seal["subject_entries"]});seal_path.write_bytes(canonical(seal));seal_sha=sha_file(seal_path)
    for name in ("independent_verification.json","verifier_terminal.json"):
        path=stage/name;record=json.loads(path.read_text());record.update(verification_subject_seal_sha256=seal_sha,verification_subject_digest=seal["subject_digest"]);path.write_bytes(canonical(record))
    (stage/"SHA256SUMS.txt").write_bytes(driver._hash_lines(stage));handoff_path=c["roots"]["side_records"]/driver.PHASE_A_HANDOFF_PATH;handoff=json.loads(handoff_path.read_text());graph=[{"path":rel,"sha256":sha_file(stage/rel)} for rel in driver.exact_artifacts()];handoff.update(verification_subject_seal_sha256=seal_sha,verification_subject_digest=seal["subject_digest"],independent_report_sha256=sha_file(stage/"independent_verification.json"),verifier_terminal_sha256=sha_file(stage/"verifier_terminal.json"),artifact_graph_entries=graph,artifact_graph_digest=sha_value({"domain":"GEN-ENC-FAST-PHASE-A-31-GRAPH-v1","entries":graph}),sha256sums_sha256=sha_file(stage/"SHA256SUMS.txt"));handoff["handoff_digest"]=sha_value({"domain":"GEN-ENC-FAST-TWO-PHASE-HANDOFF-v1","payload":{k:v for k,v in handoff.items() if k!="handoff_digest"}});handoff_path.write_bytes(canonical(handoff))
    result=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b);assert result.returncode==2 and not c["roots"]["run"].exists() and not (c["roots"]["pointer"]/"B1.json").exists()


def test_wrong_phase_b_path_and_reused_dispatch_are_rejected(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"path");args=argv("scripts.gen_enc_b1_repair_07.formal_driver","publish",b);args[args.index(driver.PHASE_B_AUTH_PATH)]="control/not-guardian.json";wrong=subprocess.run(args,cwd=c["root"],env=env(),text=True,capture_output=True,check=False);assert wrong.returncode==2 and "EXTERNAL_EXPECTED_REQUIRED" in wrong.stderr
    assert run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b).returncode==0
    reused=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b);assert reused.returncode==2 and "PHASE_B_ALREADY_CONSUMED" in reused.stderr


def _rewrite_phase_b_chain(c:dict,b:dict,mutate)->None:
    auth=json.loads(b["authorization"].read_text());mutate(auth,"authorization");b["authorization"].write_bytes(canonical(auth));b["authorization_sha256"]=sha_file(b["authorization"])
    att=json.loads(b["phase_b_attestation"].read_text());mutate(att,"attestation");att["authorization_sha256"]=b["authorization_sha256"];b["phase_b_attestation"].write_bytes(canonical(att));b["phase_b_attestation_sha256"]=sha_file(b["phase_b_attestation"])
    dispatch=json.loads(b["dispatch"].read_text());mutate(dispatch,"dispatch");dispatch["authorization_sha256"]=b["authorization_sha256"];dispatch["phase_b_attestation_sha256"]=b["phase_b_attestation_sha256"];b["dispatch"].write_bytes(canonical(dispatch));b["dispatch_sha256"]=sha_file(b["dispatch"])


def test_b1_r06_b01_coherent_three_phase_a_path_reanchor_fails_before_subject_or_target(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"three-path")
    original=driver.verified_stage_gate;driver.verified_stage_gate=lambda *_: (_ for _ in ()).throw(AssertionError("SUBJECT_ACCESSED"))
    try:
        _rewrite_phase_b_chain(c,b,lambda record,_:record.update(phase_a_release_path="control/OTHER_RELEASE.json",phase_a_attestation_path="control/OTHER_ATTESTATION.json",phase_a_handoff_path="control/OTHER_HANDOFF.json"))
        result=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b)
    finally:driver.verified_stage_gate=original
    assert result.returncode==2 and "PHASE_B_AUTH_BINDING:phase_a_release_path" in result.stderr
    assert not c["roots"]["run"].exists() and not c["roots"]["pointer"].exists()


@pytest.mark.parametrize("field,value",[("claim_ceiling","GLOBAL_PERFORMANCE"),("verification_subject_count",26)])
@pytest.mark.parametrize("record_name",["authorization","attestation","dispatch"])
def test_phase_b_claim_and_subject_count_are_strictly_bound(record_name:str,field:str,value, tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/f"{record_name}-{field}")
    keys={"authorization":"authorization","attestation":"phase_b_attestation","dispatch":"dispatch"};target=keys[record_name]
    def mutate(record,name):
        if name==record_name:record[field]=value
    _rewrite_phase_b_chain(c,b,mutate)
    result=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b)
    assert result.returncode==2 and not c["roots"]["run"].exists() and not c["roots"]["pointer"].exists()


@pytest.mark.parametrize("record_name",["authorization","attestation","dispatch"])
@pytest.mark.parametrize("attack",["missing","extra"])
def test_phase_b_required_and_zero_unlisted_fields(record_name:str,attack:str,tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/f"{record_name[0]}-{attack[0]}")
    def mutate(record,name):
        if name!=record_name:return
        if attack=="missing":record.pop("claim_ceiling")
        else:record["unlisted_attack"]=True
    _rewrite_phase_b_chain(c,b,mutate);result=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b)
    assert result.returncode==2 and "SCHEMA_" in result.stderr and not c["roots"]["run"].exists() and not c["roots"]["pointer"].exists()


def test_b1_r06_b02_phase_a_failure_is_permanent_for_same_run(tmp_path:Path)->None:
    c=setup(tmp_path/"phase-a-permanent");assert run(c,"scripts.gen_enc_b1_repair_07.formal_driver","preflight").returncode==0;assert run(c,"scripts.gen_enc_b1_repair_07.formal_driver","generate-staging").returncode==0
    member=c["roots"]["staging"]/"members/HAND_01.json";sums=c["roots"]["staging"]/"SHA256SUMS.txt";member_bytes=member.read_bytes();sum_bytes=sums.read_bytes();member.write_bytes(member_bytes+b" ")
    failed=run(c,"scripts.gen_enc_b1_repair_07.independent_verifier","verify");assert failed.returncode==2
    terminal=json.loads((c["roots"]["failure"]/"FAIL_CLOSED.json").read_text());assert terminal["terminal_phase"]=="PHASE_A"
    member.write_bytes(member_bytes);sums.write_bytes(sum_bytes)
    retried=run(c,"scripts.gen_enc_b1_repair_07.independent_verifier","verify")
    assert retried.returncode==2 and "PHASE_A_FAILURE_PERMANENT_NEW_RUN_REQUIRED" in retried.stderr
    assert not (c["roots"]["side_records"]/driver.PHASE_A_HANDOFF_PATH).exists() and not (c["roots"]["side_records"]/driver.SUBJECT_SEAL_PATH).exists()


def test_phase_b_rejects_mixed_handoff_and_phase_a_failure_before_copy(tmp_path:Path)->None:
    c=phase_a(tmp_path/"mixed");context=driver.validate_control(c["root"],c["release"],c["attestation"],SCHEMAS,"generate-staging")
    driver.write_terminal(context,False,{"authority_reads":0,"members":20,"artifacts":31,"published":0},"FORGED_MIXED_PHASE_A_FAILURE",phase="PHASE_A")
    b=authorize_phase_b(c);result=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b)
    assert result.returncode==2 and "PHASE_A_FAILURE_PERMANENT_NEW_RUN_REQUIRED" in result.stderr
    assert not c["roots"]["run"].exists() and not c["roots"]["pointer"].exists()


def test_phase_b_postcopy_exception_rolls_back_pointer_and_run_to_unique_failure(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"postcopy");result=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b,{"GEN_ENC_B1_REPAIR07_FAULT":"post-copy-exception"})
    assert result.returncode==2 and not (c["roots"]["pointer"]/"B1.json").exists()
    assert len([p for p in c["roots"]["run"].rglob("*") if p.is_file()])==0
    terminals=list(c["roots"]["failure"].glob("*.json"))+list(c["roots"]["success"].glob("*.json"));assert len(terminals)==1
    terminal=json.loads(terminals[0].read_text());assert terminal["terminal_phase"]=="PHASE_B" and terminal["honest_counts"]["members"]==20 and terminal["honest_counts"]["artifacts"]==31 and terminal["honest_counts"]["published"]==0


def test_phase_b_consumed_runtime_revalidates_complete_common_binding(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"consumed");published=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b);assert published.returncode==0,published.stderr
    path=c["roots"]["side_records"]/"PHASE_B_CONSUMED.json";value=json.loads(path.read_text());value["claim_ceiling"]="GLOBAL_PERFORMANCE";path.write_bytes(canonical(value))
    packaged=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","package-results",b)
    assert packaged.returncode==2 and ("SCHEMA_phase_b_dispatch_consumed" in packaged.stderr or "PHASE_B_CONSUMED_BINDING:claim_ceiling" in packaged.stderr)


def test_phase_a_dispatch_eight_process_one_use(tmp_path:Path)->None:
    c=setup(tmp_path/"race-a");processes=[subprocess.Popen(argv("scripts.gen_enc_b1_repair_07.formal_driver","preflight"),cwd=c["root"],env=env(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)];results=[p.communicate()+(p.returncode,) for p in processes]
    assert sum(code==0 for _,_,code in results)==1


def test_phase_b_dispatch_eight_process_one_use(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"race-b");processes=[subprocess.Popen(argv("scripts.gen_enc_b1_repair_07.formal_driver","publish",b),cwd=c["root"],env=env(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)];results=[p.communicate()+(p.returncode,) for p in processes]
    assert sum(code==0 for _,_,code in results)==1


@pytest.mark.parametrize("index",range(20))
def test_phase_b_real_kill_each_target_then_recover(index:int,tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/f"kill-{index}");crash=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b,{"GEN_ENC_B1_REPAIR07_FAULT":f"kill:{index}"});assert crash.returncode==86
    recovered=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","recover",b);assert recovered.returncode==0,recovered.stderr
    assert len(list(c["roots"]["failure"].glob("*.json")))==1 and not (c["roots"]["pointer"]/"B1.json").exists()


@pytest.mark.parametrize("boundary,code,success",[("after-targets",87,False),("after-commit",88,True),("after-pointer",89,True),("after-success",90,True)])
def test_phase_b_commit_boundaries(boundary:str,code:int,success:bool,tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/boundary);crash=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","publish",b,{"GEN_ENC_B1_REPAIR07_FAULT":boundary});assert crash.returncode==code
    recovered=run(c,"scripts.gen_enc_b1_repair_07.formal_driver","recover",b);assert recovered.returncode==0,recovered.stderr
    terminals=list(c["roots"]["success"].glob("*.json"))+list(c["roots"]["failure"].glob("*.json"));assert len(terminals)==1
    assert (c["roots"]["pointer"]/"B1.json").exists() is success
