"""Build strict repair-06 lifecycle and typed-CAD schemas."""
from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any, Sequence

from scripts.gen_enc_b1_repair_06 import cad_projection_driver as cad
from scripts.gen_enc_b1_repair_06 import formal_driver as driver
from tests.helpers.gen_enc_b1_repair_06_fixture import contract, entries, objects

REPO=Path(__file__).resolve().parents[2];OLD=REPO/"schemas/gen_enc/b1_repair_02";OUT=REPO/"schemas/gen_enc/b1_repair_06"


def infer(values:Sequence[Any])->dict[str,Any]:
    kinds={"boolean" if isinstance(x,bool) else "object" if isinstance(x,dict) else "array" if isinstance(x,list) else "number" if isinstance(x,(int,float)) else "string" if isinstance(x,str) else "null" for x in values}
    if len(kinds)!=1:return {"anyOf":[infer([x for x in values if ("boolean" if isinstance(x,bool) else "object" if isinstance(x,dict) else "array" if isinstance(x,list) else "number" if isinstance(x,(int,float)) else "string" if isinstance(x,str) else "null")==kind]) for kind in sorted(kinds)]}
    kind=next(iter(kinds))
    if kind=="object":
        keys=list(values[0]);
        if any(list(x)!=keys for x in values):
            groups={tuple(x):[] for x in values}
            for x in values:groups[tuple(x)].append(x)
            return {"oneOf":[infer(group) for group in groups.values()]}
        return {"type":"object","required":keys,"properties":{k:infer([x[k] for x in values]) for k in keys},"additionalProperties":False}
    if kind=="array":
        children=[y for x in values for y in x];lengths=[len(x) for x in values]
        return {"type":"array","items":infer(children) if children else False,"minItems":min(lengths),"maxItems":max(lengths)}
    return {"type":kind}


def add_binding(schema:dict[str,Any])->None:
    props=schema["properties"]
    additions={"projection_contract_path":{"const":driver.PROJECTION_PATH},"projection_contract_sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"},"dependency_matrix_path":{"const":driver.DEPENDENCY_PATH},"dependency_matrix_sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"},"dependency_structure_sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"}}
    props.update(additions)
    for key in additions:
        if key not in schema["required"]:schema["required"].append(key)
    props["mode"]={"const":driver.MODE}
    if "mode" not in schema["required"]:schema["required"].append("mode")


def main()->None:
    OUT.mkdir(parents=True,exist_ok=True);projected=cad.project(objects(),entries(),contract());binding={"projection_contract_sha256":projected["projection_contract_sha256"],"dependency_matrix_sha256":"d"*64,"dependency_structure_sha256":projected["dependency_matrix_sha256"]};members=driver.members_from_authority(objects(),entries(),contract(),binding)
    member={"$schema":"https://json-schema.org/draft/2020-12/schema",**infer(members)};member["$id"]="gen_enc_fast_b1_repair_06_member_identity_v1";member["properties"]["schema_version"]={"const":"gen_enc_fast_b1_repair_06_member_identity_v1"};member["properties"]["record_kind"]={"const":"BATCH_LOCAL_MEMBER_IDENTITY_TYPED_CAD_DERIVED"};member["properties"]["task_id"]={"const":driver.TASK_ID};member["properties"]["repair_id"]={"const":driver.REPAIR};member["properties"]["batch_id"]={"const":"B1"};member["properties"]["final_test_read"]={"const":False}
    schemas={"member_identity":member,"typed_projection":{"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"gen_enc_fast_b1_repair_06_typed_projection_v1",**infer([projected])}}
    for path in OLD.glob("*.schema.json"):
        if path.stem=="member_identity.schema":continue
        name=path.name.removesuffix(".schema.json");value=json.loads(path.read_text());value=json.loads(json.dumps(value).replace("repair_02","repair_06").replace("PRE-RELEASE-REPAIR-02","PRE-RELEASE-REPAIR-06"))
        if name in ("release","guardian_attestation","side_record","batch_index","independent_verification","commit_pointer","package_terminal"):add_binding(value)
        if name=="draft":
            value["properties"]["mode"]={"const":driver.MODE};value["required"].append("mode");value["properties"]["final_test_read"]={"const":False};value["required"].append("final_test_read")
        schemas[name]=value
    for name in ("generation_terminal","verifier_terminal","independent_verification"):
        schemas[name]["properties"]["authority_read_count"]["maximum"]=100
    schemas["package_terminal"]["properties"]["honest_counts"]["properties"]["authority_reads"]["maximum"]=100
    schemas["static_audit"]["properties"]["authority_read_count_at_generation"]={"type":"integer","minimum":0,"maximum":100};schemas["static_audit"]["required"].append("authority_read_count_at_generation")
    side=schemas["side_record"]
    for name in ("release","guardian_attestation","side_record"):
        schemas[name]["properties"]["verification_subject_seal_path"]={"const":driver.SUBJECT_SEAL_PATH};schemas[name]["required"].append("verification_subject_seal_path")
    phase_fields={"authority_allowlist_path":{"const":driver.AUTHORITY_ALLOWLIST_PATH},"guardian_two_phase_contract_path":{"const":driver.GUARDIAN_TWO_PHASE_CONTRACT_PATH},"guardian_two_phase_contract_sha256":{"const":driver.GUARDIAN_TWO_PHASE_CONTRACT_SHA256},"guardian_two_phase_review_path":{"const":driver.GUARDIAN_TWO_PHASE_REVIEW_PATH},"guardian_two_phase_review_sha256":{"const":driver.GUARDIAN_TWO_PHASE_REVIEW_SHA256},"phase_a_commands_exact":{"const":list(driver.PHASE_A_COMMANDS)},"phase_a_permissions":{"const":driver.PHASE_A_PERMISSIONS},"phase_a_dispatch_id":{"type":"string","pattern":"^[0-9a-f]{64}$"},"phase_a_dispatch_path":{"const":"control/PHASE_A_DISPATCH_AUTHORIZATION.json"},"guardian_phase_b_authorization_path":{"const":driver.PHASE_B_AUTH_PATH},"guardian_phase_b_attestation_path":{"const":driver.PHASE_B_ATTESTATION_PATH},"phase_b_dispatch_path":{"const":driver.PHASE_B_DISPATCH_PATH}}
    for name in ("release","guardian_attestation","side_record"):
        schemas[name]["properties"].update(copy.deepcopy(phase_fields));schemas[name]["required"] += [key for key in phase_fields if key not in schemas[name]["required"]]
        if "commands_exact" in schemas[name]["properties"]:schemas[name]["properties"]["commands_exact"]={"const":list(driver.PHASE_A_COMMANDS)}
    release=schemas["release"];release["properties"]["record_kind"]={"const":"PHASE_A_RELEASE"};release["properties"]["commands_exact"]={"const":list(driver.PHASE_A_COMMANDS)};release["properties"]["permissions"]["properties"]["publication"]={"const":False};release["properties"]["consumption_record_name"]={"const":"PHASE_A_CONSUMED.json"}
    for key,path in (("source_manifest_path","outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/source_manifest.json"),("schema_manifest_path","outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/schema_manifest.json"),("command_manifest_path","outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/command_manifest.json")):
        side["properties"][key]={"const":path};side["required"].append(key)
    receipt=copy.deepcopy(schemas["side_record"]);receipt["$id"]="gen_enc_fast_b1_repair_06_authority_read_receipt_v1"
    for key in ("state","one_use","revoked"):receipt["properties"].pop(key);receipt["required"].remove(key)
    receipt["properties"].update({"schema_version":{"const":"gen_enc_fast_b1_repair_06_authority_read_receipt_v1"},"record_kind":{"const":"CUMULATIVE_AUTHORITY_READ_RECEIPT"},"ordinal":{"type":"integer","minimum":1,"maximum":100},"phase":{"enum":["DRIVER_GENERATION","INDEPENDENT_VERIFICATION"]},"purpose":{"type":"string","minLength":1},"path_label":{"type":"string","minLength":1},"expected_sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"}})
    receipt["required"] += ["record_kind","ordinal","phase","purpose","path_label","expected_sha256"]
    schemas["authority_read_receipt"]=receipt
    seal=copy.deepcopy(receipt);seal["$id"]="gen_enc_fast_b1_repair_06_verification_subject_seal_v1"
    for key in ("ordinal","phase","purpose","path_label","expected_sha256"):seal["properties"].pop(key);seal["required"].remove(key)
    seal["properties"].update({"schema_version":{"const":"gen_enc_fast_b1_repair_06_verification_subject_seal_v1"},"record_kind":{"const":"IMMUTABLE_INDEPENDENT_VERIFICATION_SUBJECT_SEAL"},"subject_count":{"const":27},"subject_entries":{"type":"array","minItems":27,"maxItems":27,"items":{"type":"object","additionalProperties":False,"required":["path","sha256"],"properties":{"path":{"type":"string","minLength":1},"sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"}}}},"subject_digest":{"type":"string","pattern":"^[0-9a-f]{64}$"},"verification_nonce":{"type":"string","pattern":"^[0-9a-f]{64}$"}})
    seal["required"] += ["subject_count","subject_entries","subject_digest","verification_nonce"]
    schemas["verification_subject_seal"]=seal
    subject_fields={"verification_subject_seal_path":{"const":driver.SUBJECT_SEAL_PATH},"verification_subject_seal_sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"},"verification_subject_digest":{"type":"string","pattern":"^[0-9a-f]{64}$"},"verification_subject_count":{"const":27}}
    for name in ("independent_verification","verifier_terminal"):
        schemas[name]["properties"].update(copy.deepcopy(subject_fields));schemas[name]["required"] += list(subject_fields)
    schemas["independent_verification"]["properties"]["verification_subject_seal_sha256"]={"anyOf":[{"type":"null"},{"type":"string","pattern":"^[0-9a-f]{64}$"}]};schemas["independent_verification"]["properties"]["verification_subject_digest"]={"anyOf":[{"type":"null"},{"type":"string","pattern":"^[0-9a-f]{64}$"}]};schemas["independent_verification"]["properties"]["verification_subject_count"]={"enum":[0,27]}
    hex64="a"*64;roots=driver.exact_roots(hex64,True)
    binding={"task_id":driver.TASK_ID,"batch_id":"B1","run_id":hex64,"mode":driver.MODE,"commands_exact":list(driver.PHASE_A_COMMANDS),"phase_a_commands_exact":list(driver.PHASE_A_COMMANDS),"phase_a_permissions":driver.PHASE_A_PERMISSIONS,"phase_a_dispatch_id":hex64,"phase_a_dispatch_path":"control/PHASE_A_DISPATCH_AUTHORIZATION.json","guardian_phase_b_authorization_path":driver.PHASE_B_AUTH_PATH,"guardian_phase_b_attestation_path":driver.PHASE_B_ATTESTATION_PATH,"phase_b_dispatch_path":driver.PHASE_B_DISPATCH_PATH,"authority_allowlist_sha256":hex64,"verification_subject_seal_path":driver.SUBJECT_SEAL_PATH,"projection_contract_path":driver.PROJECTION_PATH,"projection_contract_sha256":hex64,"dependency_matrix_path":driver.DEPENDENCY_PATH,"dependency_matrix_sha256":hex64,"dependency_structure_sha256":hex64,"source_manifest_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/source_manifest.json","source_manifest_sha256":hex64,"schema_manifest_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/schema_manifest.json","schema_manifest_sha256":hex64,"command_manifest_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/command_manifest.json","command_manifest_sha256":hex64,"roots":roots}
    phase_a_dispatch={"schema_version":"gen_enc_fast_b1_repair_06_phase_dispatch_v1","record_kind":"TECHNICAL_PHASE_DISPATCH","state":"PHASE_A_ISSUED","phase":"A","dispatch_id":hex64,"repair_id":driver.REPAIR,**binding,"release_sha256":hex64,"attestation_sha256":hex64,"one_use":True,"revoked":False,"final_test_read":False}
    phase_a_dispatch.update(authority_allowlist_path=driver.AUTHORITY_ALLOWLIST_PATH,guardian_two_phase_contract_path=driver.GUARDIAN_TWO_PHASE_CONTRACT_PATH,guardian_two_phase_contract_sha256=driver.GUARDIAN_TWO_PHASE_CONTRACT_SHA256,guardian_two_phase_review_path=driver.GUARDIAN_TWO_PHASE_REVIEW_PATH,guardian_two_phase_review_sha256=driver.GUARDIAN_TWO_PHASE_REVIEW_SHA256)
    schemas["phase_dispatch"]={"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"gen_enc_fast_b1_repair_06_phase_dispatch_v1",**infer([phase_a_dispatch,{**phase_a_dispatch,"state":"PHASE_A_CONSUMED"}])}
    phase_common={"repair_id":driver.REPAIR,"task_id":driver.TASK_ID,"batch_id":"B1","run_id":hex64,"mode":driver.MODE,"phase_a_release_path":"control/RELEASE.json","phase_a_release_sha256":hex64,"phase_a_attestation_path":"control/GUARDIAN_ATTESTATION.json","phase_a_attestation_sha256":hex64,"phase_a_handoff_path":roots["side_records"]+"/"+driver.PHASE_A_HANDOFF_PATH,"phase_a_handoff_sha256":hex64,"phase_a_handoff_digest":hex64,"verification_subject_seal_path":roots["side_records"]+"/"+driver.SUBJECT_SEAL_PATH,"verification_subject_seal_sha256":hex64,"verification_subject_digest":hex64,"independent_report_sha256":hex64,"verifier_terminal_sha256":hex64,"artifact_graph_digest":hex64,"source_manifest_sha256":hex64,"schema_manifest_sha256":hex64,"command_manifest_sha256":hex64,"projection_contract_sha256":hex64,"dependency_matrix_sha256":hex64,"dependency_structure_sha256":hex64,"roots":roots,"phase_b_commands_exact":list(driver.PHASE_B_COMMANDS),"phase_b_permissions":driver.PHASE_B_PERMISSIONS,"final_test_read":False}
    auth={"schema_version":"gen_enc_fast_two_phase_guardian_phase_b_authorization_v1","record_kind":"TECHNICAL_MIRROR_GUARDIAN_PHASE_B_AUTHORIZATION","identity_class":"TECHNICAL_ONLY_NEVER_FORMAL","authoritative":False,"authorization_id":hex64,**phase_common};att={"schema_version":"gen_enc_fast_two_phase_guardian_phase_b_attestation_v1","record_kind":"TECHNICAL_MIRROR_GUARDIAN_PHASE_B_ONE_WAY_ATTESTATION","identity_class":"TECHNICAL_ONLY_NEVER_FORMAL","authoritative":False,"authorization_id":hex64,"authorization_sha256":hex64,"one_way":True,**phase_common};dispatch={"schema_version":"gen_enc_fast_b1_repair_06_phase_b_dispatch_v1","record_kind":"TECHNICAL_PHASE_DISPATCH","state":"PHASE_B_ISSUED","phase":"B","dispatch_id":hex64,"phase_a_dispatch_id":hex64,"authorization_id":hex64,"authorization_sha256":hex64,"phase_b_attestation_sha256":hex64,**phase_common,"one_use":True,"revoked":False};consumed={**dispatch,"state":"PHASE_B_CONSUMED","dispatch_expected_sha256":hex64}
    phase_time={"authority_allowlist_path":driver.AUTHORITY_ALLOWLIST_PATH,"authority_allowlist_sha256":hex64,"source_manifest_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/source_manifest.json","schema_manifest_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/schema_manifest.json","command_manifest_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/command_manifest.json","projection_contract_path":driver.PROJECTION_PATH,"dependency_matrix_path":driver.DEPENDENCY_PATH,"phase_a_task_id":driver.TASK_ID,"phase_b_task_id":driver.TASK_ID,"guardian_two_phase_contract_path":driver.GUARDIAN_TWO_PHASE_CONTRACT_PATH,"guardian_two_phase_contract_sha256":driver.GUARDIAN_TWO_PHASE_CONTRACT_SHA256,"guardian_two_phase_review_path":driver.GUARDIAN_TWO_PHASE_REVIEW_PATH,"guardian_two_phase_review_sha256":driver.GUARDIAN_TWO_PHASE_REVIEW_SHA256,"phase_b_authorization_path":driver.PHASE_B_AUTH_PATH,"phase_b_attestation_path":driver.PHASE_B_ATTESTATION_PATH,"phase_b_dispatch_path":driver.PHASE_B_DISPATCH_PATH,"issued_at":"2026-01-01T00:00:00+00:00","expires_at":"2099-01-01T00:00:00+00:00","one_use":True,"revoked":False}
    for record in (auth,att,dispatch,consumed):record.update(phase_time)
    schemas["guardian_phase_b_authorization"]={"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"gen_enc_fast_two_phase_guardian_phase_b_authorization_v1",**infer([auth])};schemas["guardian_phase_b_attestation"]={"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"gen_enc_fast_two_phase_guardian_phase_b_attestation_v1",**infer([att])};schemas["phase_b_dispatch"]={"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"gen_enc_fast_b1_repair_06_phase_b_dispatch_v1",**infer([dispatch])};schemas["phase_b_dispatch_consumed"]={"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"gen_enc_fast_b1_repair_06_phase_b_dispatch_consumed_v1",**infer([consumed])}
    handoff={"schema_version":"gen_enc_fast_two_phase_guardian_phase_a_handoff_v1","record_kind":"CANONICAL_PHASE_A_VERIFIED_HANDOFF","state":"PHASE_A_VERIFIED_HANDOFF_STOP","repair_id":driver.REPAIR,"task_id":driver.TASK_ID,"phase_a_task_id":driver.TASK_ID,"batch_id":"B1","run_id":hex64,"mode":driver.MODE,"phase_a_release_path":"control/RELEASE.json","phase_a_release_sha256":hex64,"phase_a_attestation_path":"control/GUARDIAN_ATTESTATION.json","phase_a_attestation_sha256":hex64,"phase_a_dispatch_id":hex64,"phase_a_commands_exact":list(driver.PHASE_A_COMMANDS),"phase_a_exact_argv":[["-m","module",x] for x in driver.PHASE_A_COMMANDS],"roots":roots,"verification_subject_seal_path":roots["side_records"]+"/"+driver.SUBJECT_SEAL_PATH,"verification_subject_seal_sha256":hex64,"verification_subject_digest":hex64,"verification_subject_count":27,"independent_report_path":roots["staging"]+"/independent_verification.json","independent_report_sha256":hex64,"verifier_terminal_path":roots["staging"]+"/verifier_terminal.json","verifier_terminal_sha256":hex64,"artifact_graph_count":31,"artifact_graph_entries":[{"path":x,"sha256":hex64} for x in driver.exact_artifacts()],"artifact_graph_digest":hex64,"sha256sums_sha256":hex64,"authority_read_count":0,"source_manifest_sha256":hex64,"schema_manifest_sha256":hex64,"command_manifest_sha256":hex64,"projection_contract_path":driver.PROJECTION_PATH,"projection_contract_sha256":hex64,"dependency_matrix_path":driver.DEPENDENCY_PATH,"dependency_matrix_sha256":hex64,"dependency_structure_sha256":hex64,"formal_publication_count":0,"commit_pointer_count":0,"success_package_count":0,"final_test_read":False,"handoff_digest":hex64}
    handoff.update(authority_allowlist_path=driver.AUTHORITY_ALLOWLIST_PATH,authority_allowlist_sha256=hex64,source_manifest_path="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/source_manifest.json",schema_manifest_path="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/schema_manifest.json",command_manifest_path="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_06/command_manifest.json",guardian_two_phase_contract_path=driver.GUARDIAN_TWO_PHASE_CONTRACT_PATH,guardian_two_phase_contract_sha256=driver.GUARDIAN_TWO_PHASE_CONTRACT_SHA256,guardian_two_phase_review_path=driver.GUARDIAN_TWO_PHASE_REVIEW_PATH,guardian_two_phase_review_sha256=driver.GUARDIAN_TWO_PHASE_REVIEW_SHA256)
    schemas["phase_a_handoff"]={"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"gen_enc_fast_two_phase_guardian_phase_a_handoff_v1",**infer([handoff])};schemas["phase_a_handoff"]["properties"]["phase_a_exact_argv"]={"type":"array","minItems":3,"maxItems":3,"items":{"type":"array","minItems":3,"items":{"type":"string"}}}
    for name,value in schemas.items():(OUT/f"{name}.schema.json").write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")


if __name__=="__main__":main()
