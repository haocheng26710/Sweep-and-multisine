"""Create the additive PRE-RELEASE-REPAIR-01 byte freeze; never creates RELEASE."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema

from scripts.gen_enc_b1_repair_01 import formal_driver as driver
from scripts.gen_enc_b1_repair_01 import independent_verifier as verifier

REPO=Path(__file__).resolve().parents[2]
OUT=REPO/"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_01"
SCHEMAS=REPO/"schemas/gen_enc/b1_repair_01"
REVIEW="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_FAST_B1_PRE_RELEASE_EXECUTABLE_FREEZE_CONFORMANCE_REVIEW.json"
REVIEW_SHA="38544ae737c07f6bde05c510592b388f6a49006a392db1aa7d69cbf394ef2bb2"


def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name:str,value)->None:(OUT/name).write_bytes(driver.canonical(value))


def main()->None:
    OUT.mkdir(parents=True,exist_ok=True)
    if sha(REPO/REVIEW)!=REVIEW_SHA:raise RuntimeError("ADVISOR_REVIEW_HASH")
    sources=["scripts/gen_enc_b1_repair_01/__init__.py","scripts/gen_enc_b1_repair_01/cad_adapter_driver.py","scripts/gen_enc_b1_repair_01/cad_adapter_verifier.py","scripts/gen_enc_b1_repair_01/formal_driver.py","scripts/gen_enc_b1_repair_01/independent_verifier.py","scripts/gen_enc_b1_repair_01/build_schemas.py","scripts/gen_enc_b1_repair_01/build_freeze_package.py","scripts/gen_enc_b1/formal_driver.py","scripts/gen_enc_b1/independent_verifier.py","tests/helpers/gen_enc_b1_repair_01_cli.py","tests/test_gen_enc_b1_repair_01.py",REVIEW]
    source={"schema_version":"gen_enc_fast_b1_repair_01_source_manifest_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"advisor_review_path":REVIEW,"advisor_review_sha256":REVIEW_SHA,"files":[{"path":p,"sha256":sha(REPO/p)} for p in sources],"formal_driver_verifier_independent":True,"technical_fixture_excluded_from_formal_cli":True,"final_test_read":False}
    write("source_manifest.json",source)
    schema_files=sorted(SCHEMAS.glob("*.schema.json"));schema={"schema_version":"gen_enc_fast_b1_repair_01_schema_manifest_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"files":[{"path":p.relative_to(REPO).as_posix(),"sha256":sha(p)} for p in schema_files],"strict_zero_unlisted":True,"final_test_read":False};write("schema_manifest.json",schema)
    commands=[]
    for command in ("preflight","generate-staging","publish","recover","package-results"):
        commands.append({"command":command,"module":"scripts.gen_enc_b1_repair_01.formal_driver","argv_after_python":driver.expected_argv(command),"mode":"FORMAL_B1_EXACT_20"})
    commands.insert(2,{"command":"verify","module":"scripts.gen_enc_b1_repair_01.independent_verifier","argv_after_python":verifier.expected_argv(),"mode":"FORMAL_B1_EXACT_20"})
    command_manifest={"schema_version":"gen_enc_fast_b1_repair_01_command_manifest_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"commands_exact":["preflight","generate-staging","verify","publish","recover","package-results"],"entries":commands,"argv_byte_exact_required":True,"hidden_aliases":False,"root_template":driver.exact_roots("{run_id}"),"run_id_domain":driver.RUN_DOMAIN.decode(),"final_test_read":False};write("command_manifest.json",command_manifest)
    permissions={k:False for k in ("authority_read","identity_generation","static_audit","publication",*driver.frozen.FORBIDDEN_PERMISSIONS)}
    draft={"schema_version":"gen_enc_fast_b1_repair_01_draft_v1","record_kind":"DRAFT","authoritative":False,"repair_id":driver.REPAIR,"non_authoritative":True,"attempt":0,"task_id":driver.TASK_ID,"batch_id":"B1","run_id":None,"permissions":permissions,"may_flip_or_promote":False,"future_release_must_be_new_canonical_bytes":True}
    jsonschema.Draft202012Validator(json.loads((SCHEMAS/"draft.schema.json").read_text())).validate(draft);write("DRAFT.json",draft)
    state={"schema_version":"gen_enc_fast_b1_repair_01_execution_state_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"formal_authority_read_count":0,"formal_identity_count":0,"formal_static_run_count":0,"formal_publication_count":0,"release_created":0,"guardian_attestation_created":0,"issued_created":0,"consumed_created":0,"revoked_created":0,"commit_pointer_created":0,"package_terminal_created":0,"run_id":None,"final_test_read":False};write("execution_state.json",state)
    history={"schema_version":"gen_enc_fast_b1_repair_01_test_history_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"runs":[{"attempt":"collection_environment","result":"1 failed, 7 passed, 15 errors","causes":["verifier helper name typo","external pytest temp permission"],"residue":"external temp retained where accessible"},{"attempt":"attempt_01","command":"python -m pytest -q tests/test_gen_enc_b1_repair_01.py --basetemp .tmp/b1_repair_01_attempt_01","result":"21 passed, 2 failed","falsifier":"mutated generation terminal and SHA256SUMS were not rejected","residue":".tmp/b1_repair_01_attempt_01 retained"},{"attempt":"attempt_02","command":"python -m pytest -q tests/test_gen_enc_b1_repair_01.py --basetemp .tmp/b1_repair_01_attempt_02","result":"49 passed","residue":".tmp/b1_repair_01_attempt_02 retained"},{"attempt":"attempt_03","command":"python -m pytest -q tests/test_gen_enc_b1_repair_01.py --basetemp .tmp/b1_repair_01_attempt_03","result":"49 passed, 1 failed","falsifier":"subprocess helper lacked repository import root","residue":".tmp/b1_repair_01_attempt_03 retained"},{"attempt":"attempt_04","command":"python -m pytest -q tests/test_gen_enc_b1_repair_01.py --basetemp .tmp/b1_repair_01_attempt_04","result":"50 passed","residue":".tmp/b1_repair_01_attempt_04 retained"},{"attempt":"attempt_05","command":"python -m pytest -q tests/test_gen_enc_b1_repair_01.py --basetemp .tmp/b1_repair_01_attempt_05","result":"51 passed","residue":".tmp/b1_repair_01_attempt_05 retained"}],"old_freeze_history":"44 passed; Advisor B independent rerun 44 passed; repair regression rerun 44 passed","cleanup_performed":False,"final_test_read":False};write("test_history.json",history)
    closure={"schema_version":"gen_enc_fast_b1_repair_01_gap_closure_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"advisor_review_sha256":REVIEW_SHA,"closed_gaps":["13_CAD_AUTHORITIES_ALL_LEAF_DATAFLOW","STRICT_COMPLETE_CAD_STATIC_SEMANTICS","SEALED_RANDOM_NEXTAFTER_AND_PHYSICS_FISHER_YATES_LHS","COMPLETE_31_ARTIFACT_GRAPH","SINGLE_SCHEMA_VALID_HONEST_TERMINAL","EXACT_ARGV_ROOT_RUN_AND_EXCLUSIVE_ONE_USE","FULL_CLI_NEGATIVE_AND_SUBPROCESS_CRASH_FALSIFIERS"],"formal_execution_blocked":True,"required_next":"INTERMEDIATE_AND_ADVISOR_B_RE_REVIEW_THEN_GUARDIAN_ONE_TIME_RELEASE_ATTESTATION","claim_ceiling":driver.CLAIM,"final_test_read":False};write("repair_closure.json",closure)
    (OUT/"RELEASE_NOT_CREATED.txt").write_text("No RELEASE exists. A future RELEASE must be new canonical bytes signed for the frozen hashes and this task_id.\n",encoding="utf-8",newline="\n")
    (OUT/"GUARDIAN_ATTESTATION_NOT_CREATED.txt").write_text("No guardian attestation exists and none was requested or synthesized.\n",encoding="utf-8",newline="\n")
    names=sorted(p for p in OUT.rglob("*") if p.is_file() and p.name!="SHA256SUMS.txt")
    (OUT/"SHA256SUMS.txt").write_text("".join(f"{sha(p)}  {p.relative_to(OUT).as_posix()}\n" for p in names),encoding="ascii",newline="\n")


if __name__=="__main__":main()
