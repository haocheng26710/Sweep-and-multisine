from __future__ import annotations

import json
import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.gen_enc_b1_repair_06 import formal_driver as driver
from scripts.gen_enc_b1_repair_06.primitives import canonical, sha_file, sha_value
from tests.helpers.gen_enc_b1_repair_06_control import authorize_phase_b, setup

REPO=Path(__file__).resolve().parents[1]
SCHEMAS=REPO/"schemas/gen_enc/b1_repair_06"


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
    c=setup(root);assert run(c,"scripts.gen_enc_b1_repair_06.formal_driver","preflight").returncode==0;assert run(c,"scripts.gen_enc_b1_repair_06.formal_driver","generate-staging").returncode==0
    verified=run(c,"scripts.gen_enc_b1_repair_06.independent_verifier","verify");assert verified.returncode==0,verified.stderr
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
    c=phase_a(tmp_path/"no-publish");result=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","publish")
    assert result.returncode==2 and "EXTERNAL_EXPECTED_REQUIRED" in result.stderr and not c["roots"]["run"].exists() and not c["roots"]["pointer"].exists()
    c2=setup(tmp_path/"old-release");release=json.loads(c2["release"].read_text());release["commands_exact"]=list(driver.COMMANDS);release["run_id"]=driver.derive_run_id(release);release["roots"]=driver.exact_roots(release["run_id"],True);c2["release"].write_bytes(canonical(release))
    denied=run(c2,"scripts.gen_enc_b1_repair_06.formal_driver","preflight");assert denied.returncode==2 and "PHASE_A_RELEASE_CONTRACT" in denied.stderr and '"authority_read_count": 0' in denied.stderr


def test_all_phase_b_commands_reject_missing_external_expected_values(tmp_path:Path)->None:
    c=phase_a(tmp_path/"missing-external")
    for command in driver.PHASE_B_COMMANDS:
        result=run(c,"scripts.gen_enc_b1_repair_06.formal_driver",command);assert result.returncode==2 and "EXTERNAL_EXPECTED_REQUIRED" in result.stderr
    assert not c["roots"]["run"].exists() and not c["roots"]["pointer"].exists() and not c["roots"]["success"].exists()


def test_guardian_common_contract_and_review_bytes_are_pre_read_bound(tmp_path:Path)->None:
    for index,rel in enumerate((driver.GUARDIAN_TWO_PHASE_CONTRACT_PATH,driver.GUARDIAN_TWO_PHASE_REVIEW_PATH)):
        c=setup(tmp_path/f"g{index}");path=c["root"]/rel;path.write_bytes(path.read_bytes()+b"\n")
        result=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","preflight");assert result.returncode==2 and "GUARDIAN_TWO_PHASE_AUTHORITY_BYTES" in result.stderr and '"authority_read_count": 0' in result.stderr


def test_repair06_entrypoints_are_independent_and_have_no_dynamic_imports()->None:
    for name in ("formal_driver.py","independent_verifier.py","cad_projection_driver.py","cad_projection_verifier.py"):
        tree=ast.parse((REPO/"scripts/gen_enc_b1_repair_06"/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                module=node.module or "";assert not module.startswith(("scripts.gen_enc_b1.","scripts.gen_enc_b1_repair_01","scripts.gen_enc_b1_repair_02","scripts.gen_enc_b1_repair_03","scripts.gen_enc_b1_repair_04","scripts.gen_enc_b1_repair_05"))
                if name=="formal_driver.py":assert "independent_verifier" not in module and "cad_projection_verifier" not in module
                if name=="independent_verifier.py":assert "formal_driver" not in module and "cad_projection_driver" not in module
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):assert node.func.id!="__import__"
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):assert node.func.attr not in ("import_module","exec_module")


def test_phase_b_full_chain_requires_external_expected_hashes(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"full");published=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","publish",b);assert published.returncode==0,published.stderr
    packaged=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","package-results",b);assert packaged.returncode==0,packaged.stderr
    assert len([p for p in c["roots"]["run"].rglob("*") if p.is_file()])==31 and (c["roots"]["pointer"]/"B1.json").is_file()


@pytest.mark.parametrize("attack",["wrong_auth_sha","wrong_att_sha","wrong_dispatch_sha","old_task","old_batch","old_run","phase_a_escalation"])
def test_phase_b_external_and_binding_attacks_fail_zero_publication(attack:str,tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/attack)
    if attack.endswith("sha"):b[{"wrong_auth_sha":"authorization_sha256","wrong_att_sha":"phase_b_attestation_sha256","wrong_dispatch_sha":"dispatch_sha256"}[attack]]="0"*64
    else:
        path=b["authorization"];value=json.loads(path.read_text());value[{"old_task":"task_id","old_batch":"batch_id","old_run":"run_id","phase_a_escalation":"phase_b_permissions"}[attack]]="OLD" if attack!="phase_a_escalation" else {**driver.PHASE_B_PERMISSIONS,"generate_staging":True};path.write_bytes(canonical(value));b["authorization_sha256"]=sha_file(path)
    result=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","publish",b)
    assert result.returncode==2 and not c["roots"]["run"].exists() and not (c["roots"]["pointer"]/"B1.json").exists()


def test_coordinated_stage_seal_report_replacement_cannot_match_guardian_hash(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"coordinated");stage=c["roots"]["staging"];member=stage/"members/HAND_01.json";value=json.loads(member.read_text());value["parameters"][value["parameter_order"][0]]+=1e-9;member.write_bytes(canonical(value))
    manifest=stage/"partial_manifests/HAND.json";value=json.loads(manifest.read_text());value["member_entries"][0]["sha256"]=sha_file(member);manifest.write_bytes(canonical(value))
    seal_path=c["roots"]["side_records"]/driver.SUBJECT_SEAL_PATH;seal=json.loads(seal_path.read_text());seal["subject_entries"]=[{"path":rel,"sha256":sha_file(stage/rel)} for rel in driver.verification_subject_paths()];seal["subject_digest"]=sha_value({"domain":"GEN-ENC-FAST-B1-REPAIR-06-VERIFICATION-SUBJECT-v1","entries":seal["subject_entries"]});seal_path.write_bytes(canonical(seal));seal_sha=sha_file(seal_path)
    for name in ("independent_verification.json","verifier_terminal.json"):
        path=stage/name;record=json.loads(path.read_text());record.update(verification_subject_seal_sha256=seal_sha,verification_subject_digest=seal["subject_digest"]);path.write_bytes(canonical(record))
    (stage/"SHA256SUMS.txt").write_bytes(driver._hash_lines(stage));handoff_path=c["roots"]["side_records"]/driver.PHASE_A_HANDOFF_PATH;handoff=json.loads(handoff_path.read_text());graph=[{"path":rel,"sha256":sha_file(stage/rel)} for rel in driver.exact_artifacts()];handoff.update(verification_subject_seal_sha256=seal_sha,verification_subject_digest=seal["subject_digest"],independent_report_sha256=sha_file(stage/"independent_verification.json"),verifier_terminal_sha256=sha_file(stage/"verifier_terminal.json"),artifact_graph_entries=graph,artifact_graph_digest=sha_value({"domain":"GEN-ENC-FAST-PHASE-A-31-GRAPH-v1","entries":graph}),sha256sums_sha256=sha_file(stage/"SHA256SUMS.txt"));handoff["handoff_digest"]=sha_value({"domain":"GEN-ENC-FAST-TWO-PHASE-HANDOFF-v1","payload":{k:v for k,v in handoff.items() if k!="handoff_digest"}});handoff_path.write_bytes(canonical(handoff))
    result=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","publish",b);assert result.returncode==2 and not c["roots"]["run"].exists() and not (c["roots"]["pointer"]/"B1.json").exists()


def test_wrong_phase_b_path_and_reused_dispatch_are_rejected(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"path");args=argv("scripts.gen_enc_b1_repair_06.formal_driver","publish",b);args[args.index(driver.PHASE_B_AUTH_PATH)]="control/not-guardian.json";wrong=subprocess.run(args,cwd=c["root"],env=env(),text=True,capture_output=True,check=False);assert wrong.returncode==2 and "EXTERNAL_EXPECTED_REQUIRED" in wrong.stderr
    assert run(c,"scripts.gen_enc_b1_repair_06.formal_driver","publish",b).returncode==0
    reused=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","publish",b);assert reused.returncode==2 and "PHASE_B_ALREADY_CONSUMED" in reused.stderr


def test_phase_a_dispatch_eight_process_one_use(tmp_path:Path)->None:
    c=setup(tmp_path/"race-a");processes=[subprocess.Popen(argv("scripts.gen_enc_b1_repair_06.formal_driver","preflight"),cwd=c["root"],env=env(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)];results=[p.communicate()+(p.returncode,) for p in processes]
    assert sum(code==0 for _,_,code in results)==1


def test_phase_b_dispatch_eight_process_one_use(tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/"race-b");processes=[subprocess.Popen(argv("scripts.gen_enc_b1_repair_06.formal_driver","publish",b),cwd=c["root"],env=env(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)];results=[p.communicate()+(p.returncode,) for p in processes]
    assert sum(code==0 for _,_,code in results)==1


@pytest.mark.parametrize("index",range(20))
def test_phase_b_real_kill_each_target_then_recover(index:int,tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/f"kill-{index}");crash=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","publish",b,{"GEN_ENC_B1_REPAIR06_FAULT":f"kill:{index}"});assert crash.returncode==86
    recovered=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","recover",b);assert recovered.returncode==0,recovered.stderr
    assert len(list(c["roots"]["failure"].glob("*.json")))==1 and not (c["roots"]["pointer"]/"B1.json").exists()


@pytest.mark.parametrize("boundary,code,success",[("after-targets",87,False),("after-commit",88,True),("after-pointer",89,True),("after-success",90,True)])
def test_phase_b_commit_boundaries(boundary:str,code:int,success:bool,tmp_path:Path)->None:
    c,b=phase_b_ready(tmp_path/boundary);crash=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","publish",b,{"GEN_ENC_B1_REPAIR06_FAULT":boundary});assert crash.returncode==code
    recovered=run(c,"scripts.gen_enc_b1_repair_06.formal_driver","recover",b);assert recovered.returncode==0,recovered.stderr
    terminals=list(c["roots"]["success"].glob("*.json"))+list(c["roots"]["failure"].glob("*.json"));assert len(terminals)==1
    assert (c["roots"]["pointer"]/"B1.json").exists() is success
