from __future__ import annotations

import json
import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.gen_enc_b1_repair_05 import formal_driver as driver
from scripts.gen_enc_b1_repair_05.primitives import canonical, sha_file
from tests.helpers.gen_enc_b1_repair_05_control import setup

REPO=Path(__file__).resolve().parents[1];SCHEMAS=REPO/"schemas/gen_enc/b1_repair_05"


def env(extra:dict[str,str]|None=None)->dict[str,str]:
    value=dict(os.environ);value["PYTHONPATH"]=str(REPO)+(os.pathsep+value["PYTHONPATH"] if value.get("PYTHONPATH") else "");value.update(extra or {});return value


def argv(module:str,command:str)->list[str]:
    return [sys.executable,"-m",module,command,"--repo-root",".","--release","control/RELEASE.json","--guardian-attestation","control/GUARDIAN_ATTESTATION.json","--schema-root",str(SCHEMAS),"--projection-contract",driver.PROJECTION_PATH,"--dependency-matrix",driver.DEPENDENCY_PATH]


def run(c:dict,module:str,command:str,extra:dict[str,str]|None=None)->subprocess.CompletedProcess:
    return subprocess.run(argv(module,command),cwd=c["root"],env=env(extra),text=True,capture_output=True,check=False)


def staged(root:Path,**kwargs)->dict:
    c=setup(root,**kwargs);assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","preflight").returncode==0;g=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","generate-staging");assert g.returncode==0,g.stderr;v=run(c,"scripts.gen_enc_b1_repair_05.independent_verifier","verify");assert v.returncode==0,v.stderr;return c


def rewrite_sums(root:Path)->None:(root/"SHA256SUMS.txt").write_bytes(driver._hash_lines(root))


def test_full_six_cli_and_verified_stage_gate(tmp_path:Path)->None:
    c=staged(tmp_path/"full");p=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","publish");assert p.returncode==0,p.stderr
    assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","package-results").returncode==0
    assert len([x for x in c["roots"]["run"].rglob("*") if x.is_file()])==31


def test_b_falsifier_pending_resealed_false_index_false_rejected_before_publish(tmp_path:Path)->None:
    c=staged(tmp_path/"pending");stage=c["roots"]["staging"]
    report=json.loads((stage/"independent_verification.json").read_text());report.update(status="PENDING_NON_SUCCESS",verified_member_count=0,verified_manifest_count=0,artifact_count=0,checks=[],resealed=False);(stage/"independent_verification.json").write_bytes(canonical(report))
    index=json.loads((stage/"batch_index.json").read_text());index["verification_complete"]=False;(stage/"batch_index.json").write_bytes(canonical(index));rewrite_sums(stage)
    result=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","publish");assert result.returncode==2 and "VERIFIED_GATE_REPORT" in result.stderr
    assert not c["roots"]["run"].exists() and not (c["roots"]["pointer"]/"B1.json").exists()


def test_package_repeats_verified_state_assertions_even_if_hashes_resealed(tmp_path:Path)->None:
    c=staged(tmp_path/"package");assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","publish").returncode==0;root=c["roots"]["run"]
    report=json.loads((root/"independent_verification.json").read_text());report.update(status="PENDING_NON_SUCCESS",verified_member_count=0,verified_manifest_count=0,artifact_count=0,checks=[],resealed=False);(root/"independent_verification.json").write_bytes(canonical(report))
    index=json.loads((root/"batch_index.json").read_text());index["verification_complete"]=False;(root/"batch_index.json").write_bytes(canonical(index));rewrite_sums(root)
    pointer_path=c["roots"]["pointer"]/"B1.json";pointer=json.loads(pointer_path.read_text());pointer.update(batch_index_sha256=sha_file(root/"batch_index.json"),verification_sha256=sha_file(root/"independent_verification.json"),sha256sums_sha256=sha_file(root/"SHA256SUMS.txt"));pointer_path.write_bytes(canonical(pointer))
    terminal=c["roots"]["success"]/"VERIFIED_SUCCESS.json";value=json.loads(terminal.read_text());value["commit_pointer_sha256"]=sha_file(pointer_path);terminal.write_bytes(canonical(value))
    result=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","package-results");assert result.returncode==2 and "VERIFIED_GATE_REPORT" in result.stderr


@pytest.mark.parametrize("boundary,exit_code,success",[("after-targets",87,False),("after-commit",88,True),("after-pointer",89,True),("after-success",90,True)])
def test_real_crash_boundaries_recover_state_machine(boundary:str,exit_code:int,success:bool,tmp_path:Path)->None:
    c=staged(tmp_path/boundary);crash=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","publish",{"GEN_ENC_B1_REPAIR05_FAULT":boundary});assert crash.returncode==exit_code
    recovered=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","recover");assert recovered.returncode==0,recovered.stderr
    terminals=list(c["roots"]["success"].glob("*.json"))+list(c["roots"]["failure"].glob("*.json"));assert len(terminals)==1
    if success:
        pointer_path=c["roots"]["pointer"]/"B1.json";assert json.loads(terminals[0].read_text())["record_kind"]=="VERIFIED_SUCCESS" and len([x for x in c["roots"]["run"].rglob("*") if x.is_file()])==31 and pointer_path.is_file() and pointer_path.stat().st_mtime_ns<=terminals[0].stat().st_mtime_ns
        before={x:sha_file(x) for x in [*c["roots"]["run"].rglob("*"),c["roots"]["pointer"]/"B1.json",terminals[0]] if x.is_file()};again=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","recover");after={x:sha_file(x) for x in before};assert again.returncode==0 and before==after and "IDEMPOTENT" in again.stdout
        assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","package-results").returncode==0
    else:
        assert json.loads(terminals[0].read_text())["record_kind"]=="FAIL_CLOSED" and not any(x.is_file() for x in c["roots"]["run"].rglob("*")) and not (c["roots"]["pointer"]/"B1.json").exists()


@pytest.mark.parametrize("fail_after",[1,10,20])
def test_cumulative_read_receipts_survive_driver_mid_failure(fail_after:int,tmp_path:Path)->None:
    c=setup(tmp_path/f"read-{fail_after}",simulate_formal_reads=True,fail_after_reads=fail_after);assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","preflight").returncode==0
    result=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","generate-staging");assert result.returncode==2 and f'"authority_read_count": {fail_after}' in result.stderr
    terminal=json.loads((c["roots"]["failure"]/"FAIL_CLOSED.json").read_text());assert terminal["honest_counts"]["authority_reads"]==fail_after and len(list((c["roots"]["side_records"]/"AUTHORITY_READS").glob("*.json")))==fail_after


def test_cumulative_reads_propagate_generation_verifier_publish_package(tmp_path:Path)->None:
    c=staged(tmp_path/"cumulative",simulate_formal_reads=True);stage=c["roots"]["staging"]
    assert json.loads((stage/"generation_terminal.json").read_text())["authority_read_count"]==20 and json.loads((stage/"independent_verification.json").read_text())["authority_read_count"]==40
    assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","publish").returncode==0
    terminal=json.loads((c["roots"]["success"]/"VERIFIED_SUCCESS.json").read_text());assert terminal["honest_counts"]["authority_reads"]==40 and run(c,"scripts.gen_enc_b1_repair_05.formal_driver","package-results").returncode==0


def test_verifier_mid_read_failure_reports_cumulative_count(tmp_path:Path)->None:
    c=setup(tmp_path/"verify-read",simulate_formal_reads=True,fail_after_verifier_reads=30);assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","preflight").returncode==0;assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","generate-staging").returncode==0
    result=run(c,"scripts.gen_enc_b1_repair_05.independent_verifier","verify");assert result.returncode==2 and '"authority_read_count": 30' in result.stderr
    assert json.loads((c["roots"]["failure"]/"FAIL_CLOSED.json").read_text())["honest_counts"]["authority_reads"]==30


@pytest.mark.parametrize("field",["task_id","batch_id","run_id","mode","commands_exact","roots","release_sha256","attestation_sha256","projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256"])
def test_forged_revoked_binding_is_rejected_not_accepted_as_valid_revocation(field:str,tmp_path:Path)->None:
    c=setup(tmp_path/field);issued=json.loads((c["roots"]["side_records"]/"ISSUED.json").read_text());revoked={**issued,"state":"REVOKED","revoked":True}
    revoked[field]=["wrong"] if field=="commands_exact" else {"wrong":"root"} if field=="roots" else "0"*64 if field.endswith("sha256") or field=="run_id" else "WRONG"
    (c["roots"]["side_records"]/"REVOKED.json").write_bytes(canonical(revoked));result=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","preflight")
    assert result.returncode==2 and "REVOKED_VALID_BOUND" not in result.stderr and '"authority_read_count": 0' in result.stderr


def test_valid_bound_revoked_and_consumed_revoked_conflict(tmp_path:Path)->None:
    c=setup(tmp_path/"valid");issued=json.loads((c["roots"]["side_records"]/"ISSUED.json").read_text());revoked={**issued,"state":"REVOKED","revoked":True};(c["roots"]["side_records"]/"REVOKED.json").write_bytes(canonical(revoked));result=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","preflight");assert result.returncode==2 and "REVOKED_VALID_BOUND" in result.stderr
    c2=setup(tmp_path/"conflict");assert run(c2,"scripts.gen_enc_b1_repair_05.formal_driver","preflight").returncode==0;issued=json.loads((c2["roots"]["side_records"]/"ISSUED.json").read_text());(c2["roots"]["side_records"]/"REVOKED.json").write_bytes(canonical({**issued,"state":"REVOKED","revoked":True}));result=run(c2,"scripts.gen_enc_b1_repair_05.formal_driver","generate-staging");assert result.returncode==2 and "REVOKED_INVALID_STATE" in result.stderr


def test_verifier_independently_validates_revoked_and_noncanonical_record(tmp_path:Path)->None:
    c=setup(tmp_path/"verifier-valid");issued=json.loads((c["roots"]["side_records"]/"ISSUED.json").read_text());(c["roots"]["side_records"]/"REVOKED.json").write_bytes(canonical({**issued,"state":"REVOKED","revoked":True}))
    result=run(c,"scripts.gen_enc_b1_repair_05.independent_verifier","verify");assert result.returncode==2 and "REVOKED_VALID_BOUND" in result.stderr
    c2=setup(tmp_path/"noncanonical");(c2["roots"]["side_records"]/"REVOKED.json").write_text('{"state":"REVOKED"}',encoding="utf-8")
    for module,command in (("scripts.gen_enc_b1_repair_05.formal_driver","preflight"),("scripts.gen_enc_b1_repair_05.independent_verifier","verify")):
        result=run(c2,module,command);assert result.returncode==2 and ("NON_CANONICAL" in result.stderr or "SCHEMA_side_record" in result.stderr or "JSON_READ" in result.stderr)


def test_repair05_ast_independence_and_no_dynamic_imports()->None:
    for name in ("formal_driver.py","independent_verifier.py","cad_projection_driver.py","cad_projection_verifier.py"):
        tree=ast.parse((REPO/"scripts/gen_enc_b1_repair_05"/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                module=node.module or "";assert not module.startswith(("scripts.gen_enc_b1.","scripts.gen_enc_b1_repair_01","scripts.gen_enc_b1_repair_02","scripts.gen_enc_b1_repair_03","scripts.gen_enc_b1_repair_04"))
                if name=="formal_driver.py":assert "independent_verifier" not in module and "cad_projection_verifier" not in module
                if name=="independent_verifier.py":assert "formal_driver" not in module and "cad_projection_driver" not in module
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):assert node.func.id!="__import__"
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):assert node.func.attr not in ("import_module","exec_module")


def mutate_hand_subject(root:Path)->None:
    member_path=root/"members/HAND_01.json";member=json.loads(member_path.read_text());key=member["parameter_order"][0];member["parameters"][key]=float(member["parameters"][key])+1e-9;member_path.write_bytes(canonical(member))
    manifest_path=root/"partial_manifests/HAND.json";manifest=json.loads(manifest_path.read_text());manifest["member_entries"][0]["sha256"]=sha_file(member_path);manifest_path.write_bytes(canonical(manifest));rewrite_sums(root)


def test_b_exact_post_verify_member_manifest_reseal_falsifier_publish_and_package_fail_closed(tmp_path:Path)->None:
    c=staged(tmp_path/"b01");mutate_hand_subject(c["roots"]["staging"]);result=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","publish")
    assert result.returncode==2 and "SUBJECT_SEAL_SUBJECT_MISMATCH" in result.stderr and not (c["roots"]["pointer"]/"B1.json").exists() and not c["roots"]["success"].exists()
    packaged=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","package-results");assert packaged.returncode==0 and "TECHNICAL_FAIL_CLOSED" in packaged.stdout


def test_package_rejects_resealed_published_subject_mutation_against_control_seal(tmp_path:Path)->None:
    c=staged(tmp_path/"pkg-subject");assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","publish").returncode==0;root=c["roots"]["run"];mutate_hand_subject(root)
    pointer_path=c["roots"]["pointer"]/"B1.json";pointer=json.loads(pointer_path.read_text());pointer.update(batch_index_sha256=sha_file(root/"batch_index.json"),verification_sha256=sha_file(root/"independent_verification.json"),sha256sums_sha256=sha_file(root/"SHA256SUMS.txt"));pointer_path.write_bytes(canonical(pointer));terminal=c["roots"]["success"]/"VERIFIED_SUCCESS.json";value=json.loads(terminal.read_text());value["commit_pointer_sha256"]=sha_file(pointer_path);terminal.write_bytes(canonical(value))
    result=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","package-results");assert result.returncode==2 and "SUBJECT_SEAL_SUBJECT_MISMATCH" in result.stderr


@pytest.mark.parametrize("attack",["missing","extra","old_run","report_digest","terminal_hash"])
def test_subject_seal_missing_extra_oldrun_and_cross_record_mutations(attack:str,tmp_path:Path)->None:
    c=staged(tmp_path/attack);seal=c["roots"]["side_records"]/driver.SUBJECT_SEAL_PATH;stage=c["roots"]["staging"]
    if attack=="missing":seal.rename(seal.with_suffix(".missing"))
    elif attack in ("extra","old_run"):
        value=json.loads(seal.read_text());value["unexpected"]=1 if attack=="extra" else value.get("unexpected")
        if attack=="old_run":value.pop("unexpected",None);value["run_id"]="0"*64
        seal.write_bytes(canonical(value))
    elif attack=="report_digest":
        path=stage/"independent_verification.json";value=json.loads(path.read_text());value["verification_subject_digest"]="0"*64;path.write_bytes(canonical(value));rewrite_sums(stage)
    else:
        path=stage/"verifier_terminal.json";value=json.loads(path.read_text());value["verification_subject_seal_sha256"]="0"*64;path.write_bytes(canonical(value));rewrite_sums(stage)
    result=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","publish");assert result.returncode==2 and not (c["roots"]["pointer"]/"B1.json").exists()


def test_subject_seal_exclusive_preexisting_replacement_blocks_verifier(tmp_path:Path)->None:
    c=setup(tmp_path/"exclusive");assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","preflight").returncode==0;assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","generate-staging").returncode==0
    seal=c["roots"]["side_records"]/driver.SUBJECT_SEAL_PATH;seal.write_bytes(canonical({"forged":True}));before=sha_file(seal);result=run(c,"scripts.gen_enc_b1_repair_05.independent_verifier","verify")
    assert result.returncode==2 and "SUBJECT_SEAL_ALREADY_EXISTS" in result.stderr and sha_file(seal)==before and (c["roots"]["failure"]/"FAIL_CLOSED.json").is_file()


def test_recover_publishing_preserves_verified_historical_counts_and_package_checks(tmp_path:Path)->None:
    c=staged(tmp_path/"b02");crash=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","publish",{"GEN_ENC_B1_REPAIR05_FAULT":"kill:0"});assert crash.returncode==86;recovered=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","recover");assert recovered.returncode==0
    terminal=json.loads((c["roots"]["failure"]/"FAIL_CLOSED.json").read_text());assert terminal["honest_counts"]=={"authority_reads":0,"members":20,"artifacts":31,"published":0};assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","package-results").returncode==0
    terminal["honest_counts"]["members"]=0;(c["roots"]["failure"]/"FAIL_CLOSED.json").write_bytes(canonical(terminal));assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","package-results").returncode==2


def test_recover_no_journal_partial_stage_observes_before_fail_closed(tmp_path:Path)->None:
    c=setup(tmp_path/"partial");assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","preflight").returncode==0;stage=c["roots"]["staging"];(stage/"members").mkdir(parents=True);(stage/"members/A.json").write_text("x");(stage/"members/B.json").write_text("y");(stage/"partial.txt").write_text("z")
    assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","recover").returncode==0;terminal=json.loads((c["roots"]["failure"]/"FAIL_CLOSED.json").read_text());assert terminal["honest_counts"]=={"authority_reads":0,"members":2,"artifacts":3,"published":0};assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","package-results").returncode==0


def test_eight_process_one_use_retained(tmp_path:Path)->None:
    c=setup(tmp_path/"race");processes=[subprocess.Popen(argv("scripts.gen_enc_b1_repair_05.formal_driver","preflight"),cwd=c["root"],env=env(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)];results=[p.communicate()+(p.returncode,) for p in processes];assert sum(code==0 for _,_,code in results)==1 and sum(code==2 for _,_,code in results)==7


@pytest.mark.parametrize("index",range(20))
def test_twenty_real_target_kills_retained_with_honest_counts(index:int,tmp_path:Path)->None:
    c=staged(tmp_path/f"k{index}");crash=run(c,"scripts.gen_enc_b1_repair_05.formal_driver","publish",{"GEN_ENC_B1_REPAIR05_FAULT":f"kill:{index}"});assert crash.returncode==86;assert run(c,"scripts.gen_enc_b1_repair_05.formal_driver","recover").returncode==0
    value=json.loads((c["roots"]["failure"]/"FAIL_CLOSED.json").read_text());assert value["honest_counts"]=={"authority_reads":0,"members":20,"artifacts":31,"published":0} and not (c["roots"]["pointer"]/"B1.json").exists()
