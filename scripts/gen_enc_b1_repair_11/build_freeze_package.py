from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d"
PACKAGE=Path("outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_11_shape_only_freeze")
SCHEMAS=Path("schemas/gen_enc/b1_repair_11")
CONTRACT=Path("outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/contracts/GEN_ENC_FAST_B1_REPAIR_11_AUTHORITY_SHAPE_ONLY_CONFORMANCE_CONTRACT.json")
CONTRACT_SHA="944ecf3d7b7307d1f2df4ff9fbd887bf64896bb8393a88e8f2dba5fd0328cb7b"
SUPERVISION=Path("outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/technical_repair_events/B1_REPAIR_11_SHAPE_ONLY_IMPLEMENTATION_FREEZE_REGISTRATION_20260829_001.json")
SUPERVISION_SHA="afe458289cd556cd1162e357145753eef240ce02b9971f7cd8f89033e04ae78d"
R10_PROJECTION=Path("outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_10/cad_typed_projection_contract.json")

def canonical(value:Any)->bytes:return (json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def sha_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha_file(path:Path)->str:return sha_bytes(path.read_bytes())
def write(path:Path,value:Any)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(value))
def validate(value:Any,name:str)->None:jsonschema.Draft202012Validator(json.loads((SCHEMAS/f"{name}.schema.json").read_text())).validate(value)

def commands()->dict[str,Any]:
    common=["--repo-root",".","--release","<RELEASE_EXACT_PATH>","--guardian-attestation","<ATTESTATION_EXACT_PATH>","--dispatch","<DISPATCH_EXACT_PATH>","--schema-root","schemas/gen_enc/b1_repair_11"]
    entries=[]
    for command in ("shape-preflight","extract-shape","verify-shape","package-shape"):
        module="scripts.gen_enc_b1_repair_11.independent_verifier" if command=="verify-shape" else "scripts.gen_enc_b1_repair_11.formal_driver"
        entries.append({"command":command,"module":module,"argv_after_python":["-m",module,command,*common]})
    return {"schema_version":"gen_enc_b1_r11_command_manifest_v1","record_kind":"EXACT_FOUR_COMMAND_MANIFEST","task_id":TASK,"mode":"FORMAL_B1_AUTHORITY_SHAPE_ONLY_EXACT_13X2","commands_exact":["shape-preflight","extract-shape","verify-shape","package-shape"],"entries":entries,"formal_execution_authorized":False,"final_test_read":False}

def build(test_history:dict[str,Any]|None=None)->None:
    if sha_file(CONTRACT)!=CONTRACT_SHA:raise RuntimeError("GUARDIAN_CONTRACT_HASH")
    if sha_file(SUPERVISION)!=SUPERVISION_SHA:raise RuntimeError("ADVISOR_SUPERVISION_HASH")
    contract=json.loads(CONTRACT.read_text(encoding="utf-8"));projection=json.loads(R10_PROJECTION.read_text(encoding="utf-8"))
    authority={"schema_version":"gen_enc_b1_r11_authority_manifest_v1","record_kind":"EXACT_13_SHAPE_AUTHORITY_MANIFEST","task_id":TASK,"entry_count":13,"entries":contract["authorized_shape_authority_scope"]["entries"],"formal_authority_read_count":0,"final_test_read":False};validate(authority,"authority_manifest");write(PACKAGE/"authority_manifest.json",authority)
    selectors=[]
    for item in projection["semantic_selectors"]:
        selectors.append({"id":item["id"],"purpose":item["purpose"],"pointer":item["pointer"],"type":item["type"],"classification":"FIXTURE_ONLY_FUTURE_OUTPUT" if item["id"] in {"OWNERSHIP_CELLS","OWNERSHIP_RULE"} else "REQUIRED_ACTUAL_AUTHORITY_INPUT"})
    selector={"schema_version":"gen_enc_b1_r11_selector_contract_v1","record_kind":"SHAPE_ONLY_SELECTOR_CONTRACT","task_id":TASK,"selector_count":len(selectors),"selectors":selectors,"mandatory_known_classifications":{"OWNERSHIP_CELLS":"ABSENT_FIXTURE_ONLY_OR_FUTURE_OUTPUT","OWNERSHIP_RULE":"ABSENT_FIXTURE_ONLY_OR_FUTURE_OUTPUT"},"pointer_substitution_allowed":False,"formal_authority_read_count":0,"final_test_read":False};validate(selector,"selector_contract");write(PACKAGE/"selector_contract.json",selector)
    command=commands();validate(command,"command_manifest");write(PACKAGE/"command_manifest.json",command)
    allowed=["side_records/SHAPE_DISPATCH_CONSUMED.json",*[f"receipts/{i:04d}.json" for i in range(1,27)],"staging/driver_shape_snapshot.json","staging/independent_shape_report.json","staging/verifier_terminal.json","package/SHAPE_PACKAGE.json","terminal/TERMINAL.json"]
    output={"schema_version":"gen_enc_b1_r11_output_manifest_v1","record_kind":"SHAPE_ONLY_OUTPUT_ALLOWLIST","task_id":TASK,"allowed_run_relative_paths":allowed,"scientific_artifacts_allowed":False,"member_artifacts_allowed":False,"publication_allowed":False,"final_test_read":False};validate(output,"output_manifest");write(PACKAGE/"output_manifest.json",output)
    negative={"schema_version":"gen_enc_b1_r11_negative_capability_manifest_v1","record_kind":"R11_NEGATIVE_CAPABILITY_FREEZE","task_id":TASK,"forbidden":["FORMAL_AUTHORITY_READ_DURING_IMPLEMENTATION_FREEZE","SCALAR_VALUES","SCALAR_VALUE_HASHES","SCALAR_LENGTHS","MEMBER_IDENTITIES","STATIC_ELIGIBILITY","SCIENTIFIC_ARTIFACTS","PUBLICATION","PHASE_B","FINAL_TEST_READ","POINTER_SUBSTITUTION","DIRECT_OWNERSHIP_CELLS_SELECTOR","DIRECT_OWNERSHIP_RULE_SELECTOR","R10_RUN_OR_CONTROL_REUSE","SHARED_DRIVER_VERIFIER_PARSED_OBJECT_CACHE"],"ownership_cells_classification":"FIXTURE_ONLY_FUTURE_OUTPUT","ownership_rule_classification":"FIXTURE_ONLY_FUTURE_OUTPUT","pointer_substitution_allowed":False,"formal_authority_read_count":0,"final_test_read":False};validate(negative,"negative_capability_manifest");write(PACKAGE/"negative_capability_manifest.json",negative)
    source_paths=[Path("scripts/gen_enc_b1_repair_11")/name for name in ("__init__.py","driver_core.py","verifier_core.py","formal_driver.py","independent_verifier.py","build_schemas.py","build_freeze_package.py")]+[Path("tests/helpers/gen_enc_b1_repair_11_fixture.py"),Path("tests/test_gen_enc_b1_repair_11.py")]
    source={"schema_version":"gen_enc_b1_r11_source_manifest_v1","record_kind":"R11_SOURCE_MANIFEST","task_id":TASK,"entry_count":len(source_paths),"entries":[{"path":p.as_posix(),"sha256":sha_file(p)} for p in source_paths],"formal_authority_read_count":0,"final_test_read":False};validate(source,"file_manifest");write(PACKAGE/"source_manifest.json",source)
    schema_paths=sorted(SCHEMAS.glob("*.schema.json"));schema={"schema_version":"gen_enc_b1_r11_schema_manifest_v1","record_kind":"R11_SCHEMA_MANIFEST","task_id":TASK,"entry_count":len(schema_paths),"entries":[{"path":p.as_posix(),"sha256":sha_file(p)} for p in schema_paths],"formal_authority_read_count":0,"final_test_read":False};validate(schema,"file_manifest");write(PACKAGE/"schema_manifest.json",schema)
    draft={"schema_version":"gen_enc_b1_r11_draft_v1","record_kind":"DRAFT","task_id":TASK,"repair_id":"PRE-RELEASE-REPAIR-11","attempt":0,"authoritative":False,"run_id":None,"permissions":{name:False for name in ("authority_shape_read","shape_controls","shape_run","identity","static","publication","phase_b")},"final_test_read":False};validate(draft,"draft");write(PACKAGE/"DRAFT.json",draft)
    provenance={"schema_version":"gen_enc_b1_r11_authority_provenance_v1","record_kind":"IMPLEMENTATION_FREEZE_AUTHORITY_PROVENANCE","task_id":TASK,"guardian_contract":{"path":CONTRACT.as_posix(),"sha256":CONTRACT_SHA},"advisor_b_supervision":{"path":SUPERVISION.as_posix(),"sha256":SUPERVISION_SHA},"r10_projection_metadata":{"path":R10_PROJECTION.as_posix(),"sha256":sha_file(R10_PROJECTION)},"formal_authority_files_opened":0,"formal_controls_created":0,"formal_run_id":None,"final_test_read":False};write(PACKAGE/"authority_provenance.json",provenance)
    if test_history is not None:write(PACKAGE/"TEST_HISTORY.json",test_history)
    freeze_names=["authority_manifest.json","selector_contract.json","command_manifest.json","output_manifest.json","negative_capability_manifest.json","source_manifest.json","schema_manifest.json","DRAFT.json","authority_provenance.json"]
    freeze={"schema_version":"gen_enc_b1_r11_freeze_manifest_v1","record_kind":"R11_IMPLEMENTATION_HASH_FREEZE","task_id":TASK,"package_path":PACKAGE.as_posix(),"entries":[{"path":name,"sha256":sha_file(PACKAGE/name)} for name in freeze_names],"guardian_contract_sha256":CONTRACT_SHA,"advisor_b_supervision_sha256":SUPERVISION_SHA,"formal_authority_read_count":0,"formal_shape_run_count":0,"formal_control_count":0,"identity_count":0,"static_count":0,"publication_count":0,"phase_b_count":0,"final_test_read":False};write(PACKAGE/"FREEZE_MANIFEST.json",freeze)
    sums="".join(f"{sha_file(p)}  {p.relative_to(PACKAGE).as_posix()}\n" for p in sorted(PACKAGE.glob("*.json")) if p.name!="SHA256SUMS.txt")
    (PACKAGE/"SHA256SUMS.txt").write_text(sums,encoding="ascii",newline="\n")

def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--test-history",type=Path);ns=parser.parse_args();history=json.loads(ns.test_history.read_text()) if ns.test_history else None;build(history);print(PACKAGE)

if __name__=="__main__":main()

