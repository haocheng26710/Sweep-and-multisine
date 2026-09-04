"""Freeze repair-05 executable/source/schema/command bytes without RELEASE."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from scripts.gen_enc_b1_repair_05 import cad_projection_driver as cad
from scripts.gen_enc_b1_repair_05 import formal_driver as driver
from scripts.gen_enc_b1_repair_05.primitives import canonical, sha_file
from tests.helpers.gen_enc_b1_repair_05_fixture import contract, entries, objects

REPO=Path(__file__).resolve().parents[2]
OUT=REPO/"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_05"
SCHEMAS=REPO/"schemas/gen_enc/b1_repair_05"
REVIEW="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_FAST_B1_PRE_RELEASE_REPAIR_04_SIGNING_CONFORMANCE_REREVIEW.json"
REVIEW_SHA="494304c177169190c8e44a67b9b4eb82021dfb22d766f08fa03f91d7cdc70a16"


def write(name:str,value)->None:(OUT/name).write_bytes(canonical(value))


def main()->None:
    OUT.mkdir(parents=True,exist_ok=True)
    if sha_file(REPO/REVIEW)!=REVIEW_SHA:raise RuntimeError("REREVIEW_HASH")
    contract_value=contract();write("cad_typed_projection_contract.json",contract_value);projection=cad.project(objects(),entries(),contract_value)
    structural=[{k:row[k] for k in ("purpose","pointer","selector_id","category","consumers")} for row in projection["dependency_matrix"]]
    matrix={"schema_version":"gen_enc_fast_b1_repair_05_leaf_dependency_matrix_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"projection_contract_path":driver.PROJECTION_PATH,"projection_contract_sha256":sha_file(OUT/"cad_typed_projection_contract.json"),"semantic_leaf_count":len(structural),"rows":structural,"dependency_structure_sha256":projection["dependency_matrix_sha256"],"unused_leaf_allowlist":contract_value["unused_leaf_allowlist"],"formal_authority_read_count":0,"final_test_read":False};write("cad_leaf_dependency_matrix.json",matrix)
    projection_sha=sha_file(OUT/"cad_typed_projection_contract.json");matrix_sha=sha_file(OUT/"cad_leaf_dependency_matrix.json")
    sources=["scripts/gen_enc_b1_repair_05/__init__.py","scripts/gen_enc_b1_repair_05/primitives.py","scripts/gen_enc_b1_repair_05/cad_projection_driver.py","scripts/gen_enc_b1_repair_05/cad_projection_verifier.py","scripts/gen_enc_b1_repair_05/formal_driver.py","scripts/gen_enc_b1_repair_05/independent_verifier.py","scripts/gen_enc_b1_repair_05/build_schemas.py","scripts/gen_enc_b1_repair_05/build_freeze_package.py","tests/helpers/gen_enc_b1_repair_05_fixture.py","tests/helpers/gen_enc_b1_repair_05_control.py","tests/test_gen_enc_b1_repair_05.py","docs/experiment/gen_enc/GEN_ENC_FAST_B1_PRE_RELEASE_REPAIR_05.md","docs/progress/GEN_ENC_FAST_B1_PRE_RELEASE_REPAIR_05_RESULTS.md",REVIEW]
    source={"schema_version":"gen_enc_fast_b1_repair_05_source_manifest_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"rereview_path":REVIEW,"rereview_sha256":REVIEW_SHA,"files":[{"path":p,"sha256":sha_file(REPO/p)} for p in sources],"dependency_classification":{"primitives.py":"NON_SEMANTIC_CANONICAL_HASH_ATOMIC_POINTER_ONLY","formal_driver.py":"NO_OLD_OR_VERIFIER_IMPORT_EXECUTABLE_FIVE_COMMAND_ENTRY","independent_verifier.py":"NO_OLD_OR_DRIVER_IMPORT_EXECUTABLE_VERIFY_ENTRY","cad_projection_driver.py":"NO_VERIFIER_OR_OLD_IMPORT","cad_projection_verifier.py":"NO_DRIVER_OR_OLD_IMPORT"},"dynamic_imports":False,"entrypoint_bytes_frozen":True,"final_test_read":False};write("source_manifest.json",source)
    schema_files=sorted(SCHEMAS.glob("*.schema.json"));write("schema_manifest.json",{"schema_version":"gen_enc_fast_b1_repair_05_schema_manifest_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"files":[{"path":p.relative_to(REPO).as_posix(),"sha256":sha_file(p)} for p in schema_files],"single_mode":driver.MODE,"projection_dependency_binding_required":True,"final_test_read":False})
    common=["--repo-root",".","--release","outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_05/control/RELEASE.json","--guardian-attestation","outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_05/control/GUARDIAN_ATTESTATION.json","--schema-root","schemas/gen_enc/b1_repair_05","--projection-contract",driver.PROJECTION_PATH,"--dependency-matrix",driver.DEPENDENCY_PATH]
    command_rows=[{"command":c,"module":"scripts.gen_enc_b1_repair_05.formal_driver","argv_after_python":["-m","scripts.gen_enc_b1_repair_05.formal_driver",c,*common],"mode":driver.MODE} for c in ("preflight","generate-staging","publish","recover","package-results")]
    command_rows.insert(2,{"command":"verify","module":"scripts.gen_enc_b1_repair_05.independent_verifier","argv_after_python":["-m","scripts.gen_enc_b1_repair_05.independent_verifier","verify",*common],"mode":driver.MODE})
    write("command_manifest.json",{"schema_version":"gen_enc_fast_b1_repair_05_command_manifest_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"mode":driver.MODE,"commands_exact":list(driver.COMMANDS),"entries":command_rows,"argv_byte_exact_required":True,"hidden_aliases":False,"projection_contract_path":driver.PROJECTION_PATH,"projection_contract_sha256":projection_sha,"dependency_matrix_path":driver.DEPENDENCY_PATH,"dependency_matrix_sha256":matrix_sha,"dependency_structure_sha256":projection["dependency_matrix_sha256"],"run_id_domain":driver.RUN_DOMAIN.decode(),"final_test_read":False})
    permission_names=("authority_read","identity_generation","static_audit","publication","timing","response","performance","comparison","ranking","selection","optimization","matched_cost","direction","no_improvement","simulation","full_wave","physical","final80","final92","final_test_read")
    draft={"schema_version":"gen_enc_fast_b1_repair_05_draft_v1","record_kind":"DRAFT","authoritative":False,"repair_id":driver.REPAIR,"non_authoritative":True,"attempt":0,"task_id":driver.TASK_ID,"batch_id":"B1","mode":driver.MODE,"run_id":None,"permissions":{x:False for x in permission_names},"may_flip_or_promote":False,"future_release_must_be_new_canonical_bytes":True};jsonschema.Draft202012Validator(json.loads((SCHEMAS/"draft.schema.json").read_text())).validate(draft);write("DRAFT.json",draft)
    write("execution_state.json",{"schema_version":"gen_enc_fast_b1_repair_05_execution_state_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"mode":driver.MODE,"formal_authority_read_count":0,"formal_member_count":0,"formal_static_run_count":0,"formal_publication_count":0,"release_created":0,"guardian_attestation_created":0,"issued_created":0,"consumed_created":0,"revoked_created":0,"commit_pointer_created":0,"package_terminal_created":0,"run_id":None,"final_test_read":False})
    write("test_history.json",{"schema_version":"gen_enc_fast_b1_repair_05_test_history_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"runs":[{"attempt":"a1","result":"59 passed in 143.95s","residue":".t/r05a1 retained"},{"attempt":"a2","result":"59 passed in 144.03s","residue":".t/r05a2 retained"}],"required_regressions":{"repair04":"28 passed in 46.99s","repair03":"48 passed in 74.31s","repair02":"31 passed in 2.94s","repair01":"51 passed in 24.44s","old_freeze":"44 passed in 15.50s"},"cleanup_performed":False,"failed_iteration_count":0,"final_test_read":False})
    write("repair_closure.json",{"schema_version":"gen_enc_fast_b1_repair_05_gap_closure_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"rereview_sha256":REVIEW_SHA,"signing_blockers_closed":["B1-R04-B-01_IMMUTABLE_VERIFICATION_SUBJECT_SEAL","B1-R04-B-02_RECOVERY_HISTORICAL_COUNTS"],"projection_contract_sha256":projection_sha,"dependency_matrix_sha256":matrix_sha,"dependency_structure_sha256":projection["dependency_matrix_sha256"],"formal_execution_blocked":True,"next":"INTERMEDIATE_AND_ADVISOR_B_RE_REVIEW","claim_ceiling":driver.CLAIM,"final_test_read":False})
    write("FINAL_READ_ONLY_AUDIT.json",{"schema_version":"gen_enc_fast_b1_repair_05_read_only_audit_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"status":"READY_FOR_INTERMEDIATE_AND_ADVISOR_B_RE_REVIEW_FORMAL_EXECUTION_BLOCKED","source_manifest_sha256":sha_file(OUT/"source_manifest.json"),"schema_manifest_sha256":sha_file(OUT/"schema_manifest.json"),"command_manifest_sha256":sha_file(OUT/"command_manifest.json"),"projection_contract_sha256":projection_sha,"dependency_matrix_sha256":matrix_sha,"dependency_structure_sha256":projection["dependency_matrix_sha256"],"formal_counts":{"authority_reads":0,"members":0,"static_runs":0,"publications":0,"releases":0,"guardian_attestations":0,"side_records":0,"commit_pointers":0,"package_terminals":0},"draft_attempt":0,"draft_run_id":None,"all_formal_permissions":False,"final_test_read":False})
    (OUT/"RELEASE_NOT_CREATED.txt").write_text("No formal RELEASE exists. Future canonical RELEASE bytes must bind repair-05 frozen hashes and exact argv.\n",encoding="utf-8",newline="\n")
    (OUT/"GUARDIAN_ATTESTATION_NOT_CREATED.txt").write_text("No guardian attestation exists or was requested.\n",encoding="utf-8",newline="\n")
    files=sorted(p for p in OUT.rglob("*") if p.is_file() and p.name!="SHA256SUMS.txt");(OUT/"SHA256SUMS.txt").write_text("".join(f"{sha_file(p)}  {p.relative_to(OUT).as_posix()}\n" for p in files),encoding="ascii",newline="\n")


if __name__=="__main__":main()
