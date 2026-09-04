from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path("schemas/gen_enc/b1_repair_11")
TASK = "01a049a7-15ca-79e1-92a2-d3822ba8609d"
MODE = "FORMAL_B1_AUTHORITY_SHAPE_ONLY_EXACT_13X2"
COMMANDS = ["shape-preflight", "extract-shape", "verify-shape", "package-shape"]
HEX = "^[0-9a-f]{64}$"


def obj(properties: dict[str, Any], required: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    return {"type":"object","additionalProperties":False,"properties":properties,"required":required or list(properties),**extra}


def const(value: Any) -> dict[str, Any]: return {"const":value}
def string(**kw: Any) -> dict[str, Any]: return {"type":"string",**kw}
def integer(**kw: Any) -> dict[str, Any]: return {"type":"integer",**kw}
def array(items: dict[str, Any], **kw: Any) -> dict[str, Any]: return {"type":"array","items":items,**kw}
def write(name: str, value: Any) -> None:
    ROOT.mkdir(parents=True,exist_ok=True)
    (ROOT/f"{name}.schema.json").write_text(json.dumps(value,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")


path = string(minLength=1,pattern="^(?!/)(?![A-Za-z]:)(?!.*(?:^|/)\\.\\.(?:/|$)).+$")
sha = string(pattern=HEX)
run = string(pattern=HEX)
roots = obj({name:path for name in ("staging","receipts","side_records","package","terminal")})
technical_binding={"technical_mirror":{"type":"boolean"},"technical_bundle_path":{"anyOf":[path,{"type":"null"}]},"technical_bundle_sha256":{"anyOf":[sha,{"type":"null"}]},"technical_fail_after_driver_read":{"anyOf":[integer(minimum=1,maximum=13),{"type":"null"}]},"technical_fail_after_verifier_read":{"anyOf":[integer(minimum=1,maximum=13),{"type":"null"}]},"technical_read_delay_ms":integer(minimum=0,maximum=500)}
binding = {
    "task_id":const(TASK),"batch_id":const("B1"),"run_id":run,"dispatch_id":run,"mode":const(MODE),"commands_exact":const(COMMANDS),
    "authority_manifest_path":path,"authority_manifest_sha256":sha,"selector_contract_path":path,"selector_contract_sha256":sha,
    "source_manifest_path":path,"source_manifest_sha256":sha,"schema_manifest_path":path,"schema_manifest_sha256":sha,
    "command_manifest_path":path,"command_manifest_sha256":sha,"output_manifest_path":path,"output_manifest_sha256":sha,
    "negative_capability_manifest_path":path,"negative_capability_manifest_sha256":sha,"guardian_contract_path":path,"guardian_contract_sha256":sha,
    "roots":roots,"final_test_read":const(False),**technical_binding,
}
release_props={"schema_version":const("gen_enc_b1_r11_shape_release_v1"),"record_kind":const("SHAPE_ONLY_RELEASE"),**binding,"release_path":path,"attestation_path":path,"dispatch_path":path,"permissions":obj({"shape_preflight":const(True),"extract_shape":const(True),"verify_shape":const(True),"package_shape":const(True),"identity":const(False),"static":const(False),"publication":const(False),"phase_b":const(False)})}
write("shape_release",obj(release_props))
write("shape_attestation",obj({"schema_version":const("gen_enc_b1_r11_shape_attestation_v1"),"record_kind":const("GUARDIAN_SHAPE_ONLY_ATTESTATION"),**binding,"release_path":path,"release_sha256":sha,"one_way":const(True)}))
write("shape_dispatch",obj({"schema_version":const("gen_enc_b1_r11_shape_dispatch_v1"),"record_kind":const("TASK_BOUND_SHAPE_DISPATCH"),**binding,"release_path":path,"release_sha256":sha,"attestation_path":path,"attestation_sha256":sha,"state":const("SHAPE_ISSUED"),"one_use":const(True),"revoked":const(False)}))
write("dispatch_consumed",obj({"schema_version":const("gen_enc_b1_r11_dispatch_consumed_v1"),"record_kind":const("SHAPE_DISPATCH_CONSUMED"),"task_id":const(TASK),"batch_id":const("B1"),"run_id":run,"dispatch_id":run,"release_sha256":sha,"attestation_sha256":sha,"dispatch_sha256":sha,"state":const("SHAPE_CONSUMED"),"one_use":const(True),"final_test_read":const(False)}))

entry=obj({"purpose":string(pattern="^CAD0_MULTI_SOURCE_(0[1-9]|1[0-3])$"),"path":path,"sha256":sha,"pointer":{"type":"string"}})
write("authority_manifest",obj({"schema_version":const("gen_enc_b1_r11_authority_manifest_v1"),"record_kind":const("EXACT_13_SHAPE_AUTHORITY_MANIFEST"),"task_id":const(TASK),"entry_count":const(13),"entries":array(entry,minItems=13,maxItems=13),"formal_authority_read_count":const(0),"final_test_read":const(False)}))
selector=obj({"id":string(pattern="^[A-Z0-9_]+$"),"purpose":string(pattern="^CAD0_MULTI_SOURCE_(0[1-9]|1[0-3])$"),"pointer":{"type":"string"},"type":{"enum":["object","array","string","integer","number","boolean","null"]},"classification":{"enum":["REQUIRED_ACTUAL_AUTHORITY_INPUT","FIXTURE_ONLY_FUTURE_OUTPUT"]}})
write("selector_contract",obj({"schema_version":const("gen_enc_b1_r11_selector_contract_v1"),"record_kind":const("SHAPE_ONLY_SELECTOR_CONTRACT"),"task_id":const(TASK),"selector_count":integer(minimum=1),"selectors":array(selector,minItems=1),"mandatory_known_classifications":obj({"OWNERSHIP_CELLS":const("ABSENT_FIXTURE_ONLY_OR_FUTURE_OUTPUT"),"OWNERSHIP_RULE":const("ABSENT_FIXTURE_ONLY_OR_FUTURE_OUTPUT")}),"pointer_substitution_allowed":const(False),"formal_authority_read_count":const(0),"final_test_read":const(False)}))

command_entry=obj({"command":{"enum":COMMANDS},"module":{"enum":["scripts.gen_enc_b1_repair_11.formal_driver","scripts.gen_enc_b1_repair_11.independent_verifier"]},"argv_after_python":array(string(minLength=1),minItems=2)})
write("command_manifest",obj({"schema_version":const("gen_enc_b1_r11_command_manifest_v1"),"record_kind":const("EXACT_FOUR_COMMAND_MANIFEST"),"task_id":const(TASK),"mode":const(MODE),"commands_exact":const(COMMANDS),"entries":array(command_entry,minItems=4,maxItems=4),"formal_execution_authorized":const(False),"final_test_read":const(False)}))
file_entry=obj({"path":path,"sha256":sha})
write("file_manifest",obj({"schema_version":string(pattern="^gen_enc_b1_r11_(source|schema)_manifest_v1$"),"record_kind":{"enum":["R11_SOURCE_MANIFEST","R11_SCHEMA_MANIFEST"]},"task_id":const(TASK),"entry_count":integer(minimum=1),"entries":array(file_entry,minItems=1),"formal_authority_read_count":const(0),"final_test_read":const(False)}))
write("output_manifest",obj({"schema_version":const("gen_enc_b1_r11_output_manifest_v1"),"record_kind":const("SHAPE_ONLY_OUTPUT_ALLOWLIST"),"task_id":const(TASK),"allowed_run_relative_paths":array(string(),minItems=1,uniqueItems=True),"scientific_artifacts_allowed":const(False),"member_artifacts_allowed":const(False),"publication_allowed":const(False),"final_test_read":const(False)}))
write("negative_capability_manifest",obj({"schema_version":const("gen_enc_b1_r11_negative_capability_manifest_v1"),"record_kind":const("R11_NEGATIVE_CAPABILITY_FREEZE"),"task_id":const(TASK),"forbidden":array(string(),minItems=1,uniqueItems=True),"ownership_cells_classification":const("FIXTURE_ONLY_FUTURE_OUTPUT"),"ownership_rule_classification":const("FIXTURE_ONLY_FUTURE_OUTPUT"),"pointer_substitution_allowed":const(False),"formal_authority_read_count":const(0),"final_test_read":const(False)}))

shape_meta=obj({"length":integer(minimum=0),"element_types":array({"enum":["object","array","string","integer","number","boolean","null"]},uniqueItems=True)})
object_meta=obj({"child_count":integer(minimum=0),"key_names":array(string(),uniqueItems=True)})
row=obj({"purpose":string(),"source_path":path,"source_sha256":sha,"source_pointer":{"type":"string"},"available_json_pointer_set":array({"type":"string"},minItems=1,uniqueItems=True),"node_type_by_pointer":{"type":"object","additionalProperties":{"enum":["object","array","string","integer","number","boolean","null"]}},"array_arity_by_pointer":{"type":"object","additionalProperties":shape_meta},"object_arity_by_pointer":{"type":"object","additionalProperties":object_meta},"structural_digest":sha,"candidate_selector_status_by_id":{"type":"object","additionalProperties":{"enum":["PRESENT_ACTUAL_AUTHORITY_INPUT","ABSENT_FIXTURE_ONLY_OR_FUTURE_OUTPUT","PRESENT_BUT_NOT_AUTHORIZED_FOR_DIRECT_USE","UNRESOLVED_FAIL_CLOSED"]}}})
write("structural_snapshot",obj({"schema_version":const("gen_enc_b1_r11_structural_snapshot_v1"),"record_kind":const("DRIVER_AUTHORITY_STRUCTURAL_SNAPSHOT"),"task_id":const(TASK),"batch_id":const("B1"),"run_id":run,"claim_ceiling":const("E0_AUTHORITY_STRUCTURE_CONFORMANCE_ONLY"),"authority_read_count":const(13),"objects":array(row,minItems=13,maxItems=13),"structural_snapshot_digest":sha,"member_count":const(0),"scientific_artifact_count":const(0),"final_test_read":const(False)}))
write("authority_read_receipt",obj({"schema_version":const("gen_enc_b1_r11_authority_read_receipt_v1"),"record_kind":const("AUTHORITY_SHAPE_READ_RECEIPT"),"task_id":const(TASK),"batch_id":const("B1"),"run_id":run,"dispatch_id":run,"lane":{"enum":["DRIVER","VERIFIER"]},"ordinal":integer(minimum=1,maximum=26),"purpose":string(),"source_path":path,"source_sha256":sha,"source_pointer":{"type":"string"},"release_sha256":sha,"attestation_sha256":sha,"final_test_read":const(False)}))
write("independent_report",obj({"schema_version":const("gen_enc_b1_r11_independent_report_v1"),"record_kind":const("INDEPENDENT_AUTHORITY_SHAPE_VERIFICATION"),"task_id":const(TASK),"batch_id":const("B1"),"run_id":run,"status":const("PASS"),"driver_read_count":const(13),"verifier_read_count":const(13),"authority_read_count":const(26),"object_count":const(13),"structural_snapshot_digest":sha,"scalar_values_persisted":const(False),"scalar_value_hashes_persisted":const(False),"scalar_lengths_persisted":const(False),"member_count":const(0),"scientific_artifact_count":const(0),"publication_count":const(0),"claim_ceiling":const("E0_AUTHORITY_STRUCTURE_CONFORMANCE_ONLY"),"final_test_read":const(False)}))
write("verifier_terminal",obj({"schema_version":const("gen_enc_b1_r11_verifier_terminal_v1"),"record_kind":const("INDEPENDENT_SHAPE_VERIFIER_TERMINAL"),"task_id":const(TASK),"batch_id":const("B1"),"run_id":run,"status":const("VERIFIED_SHAPE_AWAITING_PACKAGE"),"structural_snapshot_digest":sha,"authority_read_count":const(26),"object_count":const(13),"final_test_read":const(False)}))
package_entry=obj({"path":{"enum":["driver_shape_snapshot.json","independent_shape_report.json","verifier_terminal.json"]},"sha256":sha})
write("shape_package",obj({"schema_version":const("gen_enc_b1_r11_shape_package_v1"),"record_kind":const("SEALED_AUTHORITY_SHAPE_ONLY_PACKAGE"),"task_id":const(TASK),"batch_id":const("B1"),"run_id":run,"status":const("SEALED_AWAITING_GUARDIAN_RESULT_REVIEW"),"entry_count":const(3),"entries":array(package_entry,minItems=3,maxItems=3),"structural_snapshot_digest":sha,"authority_read_count":const(26),"member_count":const(0),"scientific_artifact_count":const(0),"publication_count":const(0),"final_test_read":const(False)}))
write("terminal",obj({"schema_version":const("gen_enc_b1_r11_terminal_v1"),"record_kind":const("SHAPE_RUN_TERMINAL"),"task_id":const(TASK),"batch_id":const("B1"),"run_id":run,"status":{"enum":["FAIL_CLOSED","SUCCESS_SHAPE_ONLY_AWAITING_GUARDIAN_RESULT_SEAL"]},"reason":{"anyOf":[string(minLength=1),{"type":"null"}]},"authority_read_count":integer(minimum=0,maximum=26),"driver_read_count":integer(minimum=0,maximum=13),"verifier_read_count":integer(minimum=0,maximum=13),"shape_package_count":integer(minimum=0,maximum=1),"member_count":const(0),"scientific_artifact_count":const(0),"publication_count":const(0),"scientific_hypothesis_status":const("NOT_TESTED"),"final_test_read":const(False)}))
write("draft",obj({"schema_version":const("gen_enc_b1_r11_draft_v1"),"record_kind":const("DRAFT"),"task_id":const(TASK),"repair_id":const("PRE-RELEASE-REPAIR-11"),"attempt":const(0),"authoritative":const(False),"run_id":const(None),"permissions":obj({name:const(False) for name in ("authority_shape_read","shape_controls","shape_run","identity","static","publication","phase_b")}),"final_test_read":const(False)}))

if __name__=="__main__":
    print(f"wrote schemas to {ROOT}")
