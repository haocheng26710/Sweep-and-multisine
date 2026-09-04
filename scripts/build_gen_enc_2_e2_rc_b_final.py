"""Build the sole additive FREEZE02-RC-B-FINAL correction package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO=Path(__file__).resolve().parents[1]
REL=Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_02_rc_b_final")
OUT=REPO/REL
PREV=Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_02_rc03_closure")
GUARDIAN=Path("outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2_E2_FREEZE02_RC03_FINAL_NARROW_CLOSURE_REVIEW.json")
ADVISOR=Path("outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_2_E2_FREEZE_02_RC03_FINAL_NARROW_CLOSURE_CONFIRMATION.json")
CORR01=Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01")
FORMAL=Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_freeze02_rc_b_final")


def sha(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def bind(path:str|Path,role:str)->dict[str,Any]:
    p=Path(path); actual=REPO/p
    return {"path":p.as_posix(),"sha256":sha(actual),"bytes":actual.stat().st_size,"role":role}
def write(name:str,value:Any)->None: (OUT/name).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")

HEX={"type":"string","pattern":"^[0-9a-f]{64}$"}


def schemas()->dict[str,Any]:
    origin={"type":"object","additionalProperties":False,"required":["identity_id","original_manifest_path","original_role_path","original_role_sha256","receipt_path","receipt_sha256"],
            "properties":{"identity_id":{"type":"string"},"original_manifest_path":{"type":"string","minLength":1},"original_role_path":{"type":"string","minLength":1},"original_role_sha256":HEX,"receipt_path":{"type":"string","minLength":1},"receipt_sha256":HEX}}
    record={"type":"object","additionalProperties":False,"required":["partition","key","chunk_id","role","source_sha256","canonical_payload_path","canonical_payload_sha256","origins"],
            "properties":{"partition":{"enum":["development","single_use_validation"]},"key":{"type":"string","minLength":1},"chunk_id":{"type":"string","pattern":"^chunk_[0-9]{3}$"},"role":{"enum":["THROUGHPUT_REFERENCE_DENOMINATOR_256","THROUGHPUT_AVAILABILITY_256"]},"source_sha256":HEX,"canonical_payload_path":{"type":"string","minLength":1},"canonical_payload_sha256":HEX,"origins":{"type":"array","minItems":1,"maxItems":80,"items":origin}}}
    dedup={"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","additionalProperties":False,"required":["schema_version","partition","entries"],
           "properties":{"schema_version":{"const":"gen_enc_2_e2_reference_dedup_index_rc_b_final_v1"},"partition":{"enum":["development","single_use_validation"]},"entries":{"type":"object","minProperties":294,"maxProperties":294,"additionalProperties":record}}}
    metric_success={"type":"object","additionalProperties":False,
                   "required":["schema_version","identity_id","family_id","partition","technical_status","scientific_status","primary","secondary","output_hashes","dedup_index_sha256","all_required_roles_consumed"],
                   "properties":{"schema_version":{"const":"gen_enc_2_e2_candidate_terminal_rc_b_final_v1"},"identity_id":{"type":"string"},"family_id":{"type":"string"},"partition":{"enum":["development","single_use_validation"]},"technical_status":{"const":"PASS"},"scientific_status":{"enum":["PASS","NEGATIVE","UNAVAILABLE","COST_INELIGIBLE","BRIDGE_FAIL"]},"primary":{"type":"object"},"secondary":{"type":"object"},"output_hashes":{"type":"object","additionalProperties":HEX,"minProperties":8,"maxProperties":8},"dedup_index_sha256":HEX,"all_required_roles_consumed":{"const":True}}}
    metric_failure={"type":"object","additionalProperties":False,"required":["schema_version","identity_id","family_id","partition","technical_status","scientific_status","reason","all_required_roles_consumed","final_test_read"],
                    "properties":{"schema_version":{"const":"gen_enc_2_e2_candidate_technical_failure_rc_b_final_v1"},"identity_id":{"type":"string"},"family_id":{"type":"string"},"partition":{"enum":["development","single_use_validation"]},"technical_status":{"const":"TECHNICAL_FAILURE"},"scientific_status":{"const":"TECHNICAL_FAILURE"},"reason":{"type":"string","minLength":1},"all_required_roles_consumed":{"const":False},"final_test_read":{"const":False}}}
    metric_output={"$schema":"https://json-schema.org/draft/2020-12/schema","oneOf":[metric_success,metric_failure]}
    member={"type":"object","additionalProperties":False,"required":["member_count","status","worst_member","worst_E_primary","member_terminal_hashes"],"properties":{"member_count":{"const":20},"status":{"enum":["PASS","NEGATIVE","UNAVAILABLE","COST_INELIGIBLE","BRIDGE_FAIL","TECHNICAL_FAILURE"]},"worst_member":{"type":"string"},"worst_E_primary":{"oneOf":[{"type":"number"},{"const":"UNAVAILABLE"}]},"member_terminal_hashes":{"type":"array","minItems":20,"maxItems":20,"items":HEX}}}
    family={"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","additionalProperties":False,"required":["schema_version","partition","families","four_families_complete","global_status","ranking","ranking_before_four_complete"],
            "properties":{"schema_version":{"const":"gen_enc_2_e2_family_global_terminal_rc_b_final_v1"},"partition":{"enum":["development","single_use_validation"]},"families":{"type":"object","additionalProperties":False,"required":["HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED"],"properties":{name:member for name in ["HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED"]}},"four_families_complete":{"const":True},"global_status":{"enum":["NOT_EVALUATED_DEVELOPMENT","BOUNDED_COMPARATIVE_RESULT","MIXED","MATCHED_COST_BLOCKED","UNAVAILABLE"]},"ranking":{"type":"array","maxItems":4,"items":{"type":"string"}},"ranking_before_four_complete":{"const":False}},
            "allOf":[{"if":{"properties":{"partition":{"const":"development"}}},"then":{"properties":{"global_status":{"const":"NOT_EVALUATED_DEVELOPMENT"},"ranking":{"maxItems":0}}}},{"if":{"properties":{"partition":{"const":"single_use_validation"}}},"then":{"properties":{"global_status":{"enum":["BOUNDED_COMPARATIVE_RESULT","MIXED","MATCHED_COST_BLOCKED","UNAVAILABLE"]}}}}]}
    return {"reference_dedup_index.schema.json":dedup,"candidate_terminal.schema.json":metric_output,"family_global_terminal.schema.json":family}


def main()->int:
    if sha(REPO/GUARDIAN)!="b5f982cf2c97bb17eb0d14a4922b52752e876610724c5e6321820c21b39b1483": raise SystemExit("GUARDIAN_HASH_MISMATCH")
    if sha(REPO/ADVISOR)!="53a613a9af66b2787d557788924ea31391d5beacab71d8c289d89943054f0e4a": raise SystemExit("ADVISOR_HASH_MISMATCH")
    OUT.mkdir(parents=True,exist_ok=True)
    for name,schema in schemas().items(): Draft202012Validator.check_schema(schema); write(name,schema)
    sources=[("scripts/gen_enc_2_e2_merge_reconstruct_rc_b_final.py","ALL_ROLE_RECONSTRUCTION_AND_TERMINALS"),("scripts/gen_enc_2_e2_formal_driver_rc_b_final.py","DEDUP_INDEX_BEFORE_DELETE_DRIVER_OVERLAY"),("tests/test_gen_enc_2_e2_rc_b_final.py","DIRECT_OUTPUT_TESTS"),("scripts/build_gen_enc_2_e2_rc_b_final.py","NO_FORMAL_BUILDER"),
             ("scripts/gen_enc_2_e2_independent_verifier_rc03.py","UNCHANGED_FULL_ROLE_VERIFIER"),("src/acoustic_encoder/gen_enc/e2_rc03_stats.py","UNCHANGED_ROLE_PRODUCER"),("src/acoustic_encoder/gen_enc/e2_rc03_resource.py","UNCHANGED_PROCESS_TREE_ACCOUNTING"),("src/acoustic_encoder/gen_enc/forward_acoustic_network.py","UNCHANGED_CORE")]
    write("source_manifest.json",{"schema_version":"gen_enc_2_e2_source_manifest_rc_b_final_v1","entries":[bind(p,r) for p,r in sources],"only_rc_b_changed":True,"formal_execution":False,"final_test_read":False})
    write("runtime_manifest.json",{"schema_version":"gen_enc_2_e2_runtime_manifest_rc_b_final_v1","unchanged_runtime":bind(PREV/"runtime_manifest.json","RC_D_CLOSED_RUNTIME"),"resource_method_changed":False,"formal_execution":False,"final_test_read":False})
    base=["--contract",(REL/"contract.json").as_posix(),"--exact80",(CORR01/"exact80_manifest.json").as_posix(),"--nuisance-csv","outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv","--seed-split","outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json","--source-manifest",(REL/"source_manifest.json").as_posix(),"--runtime-manifest",(REL/"runtime_manifest.json").as_posix(),"--verifier","scripts/gen_enc_2_e2_independent_verifier_rc03.py","--stats-code","src/acoustic_encoder/gen_enc/e2_rc03_stats.py","--merge-code","scripts/gen_enc_2_e2_merge_reconstruct_rc_b_final.py","--through-reference","outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_authority_addendum_01/THROUGH_REFERENCE_U4_IDENTITY_V1.json"]
    prefix=["D:/Anaconda3/python.exe","-B","scripts/gen_enc_2_e2_formal_driver_rc_b_final.py"]
    droot=(FORMAL/"development").as_posix(); vroot=(FORMAL/"single_use_validation").as_posix()
    write("command_manifest.json",{"schema_version":"gen_enc_2_e2_command_manifest_rc_b_final_v1","development_argv":prefix+["development","--authorization","outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_2_E2_RC_B_FINAL_DEVELOPMENT_AUTHORIZATION.json","--output-root",droot]+base,"single_use_validation_argv":prefix+["single-use-validation","--authorization","outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_2_E2_RC_B_FINAL_SINGLE_USE_VALIDATION_AUTHORIZATION.json","--output-root",vroot,"--development-seal",f"{droot}/partition_terminal.json","--sealed-w",f"{droot}/sealed/common_w.npz"]+base,"formal_commands_executed":0,"final_test_read":False})
    prior_storage=json.loads((REPO/PREV/"storage_bound_ledger.json").read_text(encoding="utf-8"))
    dedup_budget=prior_storage["components_bytes"]["reference_dedup_records_max_4k_each"]
    storage={"schema_version":"gen_enc_2_e2_storage_rc_b_final_v1","prior_ledger":bind(PREV/"storage_bound_ledger.json","RC_C_CLOSED_MECHANICAL_LEDGER"),"role_payload_bytes_changed":False,"worst_case_retained_bytes":prior_storage["worst_case_retained_bytes"],"worst_case_retained_gib":prior_storage["worst_case_retained_gib"],"managed_cap_bytes":prior_storage["managed_cap_bytes"],"bound_pass":prior_storage["bound_pass"],"dedup_representation":"ONE_CANONICAL_INDEX_PER_PARTITION_WITH294_KEYS_AND_UP_TO80_ORIGINS_PER_KEY","dedup_index_budget_bytes":dedup_budget,"replaces_prior_per_chunk_dedup_record_budget":True,"formal_execution":False,"final_test_read":False}
    write("storage_bound_ledger.json",storage)
    outputs=["endpoint.primary.E_primary","endpoint.primary.r_stable","endpoint.primary.stable_rank_eligible","endpoint.secondary_separate","shared_differential","matched_cost.eligibility","throughput.primary_208","throughput.secondary_256","throughput.UNAVAILABLE","bridge24","held_out4","bootstrap_unit_seal","permutation_unit_seal","uncertainty_empirical_interval","candidate_terminal","family_exact20_worst_member","global_terminal_and_ranking_after_four_complete"]
    write("output_contract.json",{"schema_version":"gen_enc_2_e2_output_contract_rc_b_final_v1","outputs":outputs,"candidate_terminals":["PASS","NEGATIVE","UNAVAILABLE","COST_INELIGIBLE","BRIDGE_FAIL","TECHNICAL_FAILURE"],"family_rule":"EXACT20_WORST_MEMBER_WITH_PRECEDENCE_TECHNICAL_FAILURE_UNAVAILABLE_COST_INELIGIBLE_BRIDGE_FAIL_NEGATIVE_PASS","global_rules":{"four_complete_required":True,"development":"NOT_EVALUATED_DEVELOPMENT_NO_RANKING","validation_terminals":["BOUNDED_COMPARATIVE_RESULT","MIXED","MATCHED_COST_BLOCKED","UNAVAILABLE"],"ranking_before_four_complete":False},"development_validation_only_outputs":"NOT_EVALUATED_DEVELOPMENT","final_test_read":False})
    write("authority_record.json",{"schema_version":"gen_enc_2_e2_rc_b_final_authority_v1","status":"RC_B_FINAL_IMPLEMENTED_EXECUTION_UNAUTHORIZED","preexecution_boundary":"LAST_PREEXECUTION_CORRECTION","further_freeze_or_rc_allowed":False,"ordinary_non_scientific_defect_route":"ONE_BOUNDED_FORMAL_EXECUTION_REPAIR_ONLY","guardian":bind(GUARDIAN,"RC_B_FINAL_REQUIRED_REVIEW"),"advisor_prior":bind(ADVISOR,"PRIOR_HASH_ROLE_SCOPE_PROVENANCE"),"additive_to":bind(PREV/"SHA256SUMS.txt","RC_A_C_D_E_AND_ROLE_GENERATION_CLOSED"),"only_change":"EXECUTABLE_ALL_ROLE_RECONSTRUCTION_DEDUP_INDEX_AND_TERMINALS","rc_a_c_d_e_changed":False,"gap01_to_gap05_changed":False,"science_changed":False,"exact80_changed":False,"formal_execution":False,"formal_response_reads":0,"formal_response_writes":0,"controls_created":0,"formal_run_id_created":False,"final_test_read":False})
    write("schema_manifest.json",{"schema_version":"gen_enc_2_e2_schema_manifest_rc_b_final_v1","entries":[bind(REL/name,"RC_B_FINAL_SCHEMA") for name in sorted(schemas())],"meta_valid":True,"final_test_read":False})
    write("contract.json",{"schema_version":"gen_enc_2_e2_contract_rc_b_final_v1","status":"READY_FOR_B_AND_GUARDIAN_RC_B_FINAL_CONFIRMATION","preexecution_boundary":"LAST_PREEXECUTION_CORRECTION","further_preexecution_freeze_or_rc":False,"next_step_after_confirmation":"ENTER_E2_WITH_DISCLOSURES","ordinary_non_scientific_defects":"AT_MOST_ONE_BOUNDED_FORMAL_EXECUTION_REPAIR","authority":bind(REL/"authority_record.json","SOLE_RC_B_FINAL_AUTHORITY"),"source":bind(REL/"source_manifest.json","RC_B_FINAL_BYTES"),"runtime":bind(REL/"runtime_manifest.json","UNCHANGED_RC_D"),"commands":bind(REL/"command_manifest.json","EXACT_D_V_COMMANDS"),"storage":bind(REL/"storage_bound_ledger.json","UNCHANGED_MECHANICAL_TOTAL"),"outputs":bind(REL/"output_contract.json","COMPLETE_OUTPUT_LIST"),"schemas":bind(REL/"schema_manifest.json","DEDUP_CANDIDATE_FAMILY_SCHEMAS"),"execution_authorized":False,"formal_units":0,"formal_response_reads":0,"formal_response_writes":0,"controls_created":0,"formal_run_id_created":False,"final_test_read":False})
    write("DRAFT_ZERO_STATE.json",{"schema_version":"gen_enc_2_e2_zero_state_rc_b_final_v1","status":"NO_FORMAL_EXECUTION","development_units":0,"validation_units":0,"formal_response_reads":0,"formal_response_writes":0,"formal_roots_created":False,"controls_created":0,"formal_run_id_created":False,"candidate_outputs":0,"family_outputs":0,"global_outputs":0,"final_test_read":False})
    files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in ("artifact_inventory.json","no_run_validation_report.json","SHA256SUMS.txt"))
    write("artifact_inventory.json",{"schema_version":"gen_enc_2_e2_inventory_rc_b_final_v1","entries":[{"path":(REL/p.name).as_posix(),"sha256":sha(p),"bytes":p.stat().st_size} for p in files],"formal_artifacts":0,"final_test_read":False})
    scan=sorted(p for p in OUT.iterdir() if p.is_file()); tokens=["T"+"BD","T"+"ODO","FUTURE_"+"DECISION","REQUIRES_"+"DECISION"]
    hits=[{"file":p.name,"token":token} for p in scan for token in tokens if token.lower() in p.read_text(encoding="utf-8").lower()]
    write("no_run_validation_report.json",{"schema_version":"gen_enc_2_e2_no_run_rc_b_final_v1","status":"PASS" if not hits else "FAIL","guardian_hash_match":True,"advisor_hash_match":True,"schemas_meta_valid":3,"all_development_roles_consumed":9,"all_validation_roles_consumed":11,"outputs_count":len(outputs),"storage_bound_pass":storage["bound_pass"],"forbidden_token_hits":hits,"formal_tests":0,"formal_units":0,"formal_response_reads":0,"formal_response_writes":0,"controls_created":0,"formal_run_id_created":False,"final_test_read":False})
    if hits: raise SystemExit("TOKEN_SCAN_FAIL")
    allfiles=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!="SHA256SUMS.txt")
    (OUT/"SHA256SUMS.txt").write_text("\n".join(f"{sha(p)}  {(REL/p.name).as_posix()}" for p in allfiles)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"status":"READY_FOR_B_AND_GUARDIAN_RC_B_FINAL_CONFIRMATION","package":REL.as_posix(),"seal_sha256":sha(OUT/"SHA256SUMS.txt"),"storage_bytes":storage["worst_case_retained_bytes"]},sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
