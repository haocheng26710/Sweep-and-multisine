"""Build additive Freeze02 RC03 final narrow-closure package without formal execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
from typing import Any

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[1]
REL = Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_02_rc03_closure")
OUT = REPO / REL
B_REVIEW = Path("outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_2_E2_FREEZE_02_RC01_RC04_LIGHTWEIGHT_CLOSURE_REVIEW.json")
G_REVIEW = Path("outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2_E2_PREEXECUTION_CONTRACT_FREEZE_02_NARROW_CLOSURE_REVIEW.json")
FREEZE02 = Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_02")
CORR01 = Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01")
FORMAL = Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_freeze02_rc03")


def sha(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes())
    return digest.hexdigest()


def bind(relative: str | Path, role: str) -> dict[str, Any]:
    relative = Path(relative); path = REPO / relative
    return {"path": relative.as_posix(), "sha256": sha(path), "bytes": path.stat().st_size, "role": role}


def write(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def product(shape: list[int]) -> int:
    result = 1
    for item in shape: result *= item
    return result


DTYPE_BYTES = {"float64": 8, "uint64": 8, "uint8": 1}


def storage_ledger() -> dict[str, Any]:
    dev_chunks = val_chunks = 80 * 147
    reference_chunks = 147
    dev_candidate_roles = {
        "SHARED_DIFFERENTIAL_COMPONENTS": ([25, 2, 2, 4, 4], "float64"),
        "ENDPOINT_UNIT_VALUES": ([25, 2, 6], "float64"),
        "THROUGHPUT_NUMERATOR_256": ([4, 25, 2, 256], "float64"),
        "MATCHED_COST_ELIGIBILITY_INPUTS": ([25, 2, 4], "float64"),
        "BOOTSTRAP_PERMUTATION_UNCERTAINTY_UNIT_VALUES": ([25, 2, 6], "float64"),
        "RESAMPLING_UNIT_KEYS": ([25, 2, 4], "uint64"),
        "CANDIDATE_FAMILY_GLOBAL_TERMINAL_INPUTS": ([25, 2, 12], "float64"),
    }
    val_candidate_roles = {**dev_candidate_roles,
        "THROUGHPUT_NUMERATOR_256": ([24, 25, 2, 256], "float64"),
        "BRIDGE_24_UNIT_VALUES": ([25, 2, 24, 6], "float64"),
        "HELD_OUT_4_UNIT_VALUES": ([25, 2, 4, 4], "float64"),
    }
    reference_roles = {
        "development_denominator": ([4, 25, 2, 256], "float64", reference_chunks),
        "development_availability_packbits": ([6400], "uint8", reference_chunks),
        "validation_denominator": ([24, 25, 2, 256], "float64", reference_chunks),
        "validation_availability_packbits": ([38400], "uint8", reference_chunks),
    }
    dev_payload = sum(product(shape) * DTYPE_BYTES[dtype] for shape, dtype in dev_candidate_roles.values()) * dev_chunks
    val_payload = sum(product(shape) * DTYPE_BYTES[dtype] for shape, dtype in val_candidate_roles.values()) * val_chunks
    reference_payload = sum(product(shape) * DTYPE_BYTES[dtype] * count for shape, dtype, count in reference_roles.values())
    npy_files = len(dev_candidate_roles) * dev_chunks + len(val_candidate_roles) * val_chunks + len(reference_roles) * reference_chunks
    components = {
        "retained_development_candidate_role_payloads": dev_payload,
        "retained_validation_candidate_role_payloads": val_payload,
        "deduplicated_partition_reference_payloads": reference_payload,
        "npy_headers_max_256_bytes_each": npy_files * 256,
        "sealed_common_w_operator_empirical_shrunk": 3 * 1664 * 1664 * 8 + 4096,
        "raw_audit_320_chunks": 160 * (4 * 25 * 2 * 4 * 256 * 16) + 160 * (24 * 25 * 2 * 4 * 256 * 16),
        "receipts_max_16k_each": (3 * dev_chunks) * 16 * 1024,
        "full_role_manifests_max_32k_each": (3 * dev_chunks) * 32 * 1024,
        "reference_dedup_records_max_4k_each": (dev_chunks + val_chunks) * 4 * 1024,
        "candidate_family_partition_outputs": 16 * 1024**2,
        "checkpoints_and_inventory": 16 * 1024**2,
        "largest_live_raw_plus_roles_plus_w_merge_working": 128 * 1024**2,
        "single_validation_failure_quarantine": 24 * 25 * 2 * 4 * 256 * 16,
        "filesystem_safety_overhead": 4 * 1024**3,
    }
    total = sum(components.values())
    return {"schema_version": "gen_enc_2_e2_mechanical_storage_ledger_rc03_v1",
            "derivation_kind": "MECHANICAL_FROM_ROLE_SHAPES_DTYPES_COUNTS", "role_specs": {
                "development_candidate": dev_candidate_roles, "validation_candidate": val_candidate_roles, "partition_reference": reference_roles},
            "counts": {"identities": 80, "chunks_per_identity_partition": 147, "development_chunks": dev_chunks,
                       "validation_chunks": val_chunks, "common_w_chunks": dev_chunks, "audit_per_identity_partition": 2},
            "components_bytes": components, "worst_case_retained_bytes": total, "worst_case_retained_gib": total / 1024**3,
            "managed_cap_bytes": 48 * 1024**3, "bound_pass": total <= 48 * 1024**3, "audit_raw_chunks": 320,
            "startup_free_minimum_bytes": 80 * 1024**3, "reserve_floor_bytes": 32 * 1024**3,
            "no_metric_contraction": True, "formal_execution": False, "final_test_read": False}


HEX = {"type": "string", "pattern": "^[0-9a-f]{64}$"}


def entry(role: str, shape: list[int], dtype: str, retention: str) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False,
            "required": ["role", "path", "sha256", "shape", "dtype", "format", "order", "payload_bytes", "retention"],
            "properties": {"role": {"const": role}, "path": {"type": "string", "minLength": 1}, "sha256": HEX,
                           "shape": {"const": shape}, "dtype": {"const": dtype}, "format": {"const": "NPY_1_0"}, "order": {"const": "C"},
                           "payload_bytes": {"const": product(shape) * DTYPE_BYTES[dtype]}, "retention": {"const": retention}}}


def manifest_branch(phase: str, partition: str, roles: list[tuple[str, list[int], str, str]]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False,
            "required": ["schema_version", "partition", "phase", "identity_id", "chunk_id", "cell_start", "cell_end_exclusive", "expected_roles", "entries", "role_set_complete", "canonical_merge_position", "raw_complex_json"],
            "properties": {"schema_version": {"const": "gen_enc_2_e2_full_role_manifest_rc03_v1"}, "partition": {"const": partition}, "phase": {"const": phase},
                           "identity_id": {"type": "string"}, "chunk_id": {"type": "string", "pattern": "^chunk_[0-9]{3}$"},
                           "cell_start": {"type": "integer", "minimum": 0, "maximum": 3650}, "cell_end_exclusive": {"type": "integer", "minimum": 25, "maximum": 3675},
                           "expected_roles": {"const": [item[0] for item in roles]},
                           "entries": {"type": "array", "minItems": len(roles), "maxItems": len(roles), "prefixItems": [entry(*item) for item in roles], "items": False},
                           "role_set_complete": {"const": True}, "canonical_merge_position": {"type": "integer", "minimum": 0, "maximum": 11759}, "raw_complex_json": {"const": False}}}


def schemas() -> dict[str, Any]:
    w = [("WITHIN_CELL_RESIDUAL_BLOCK", [25,2,4,1664], "float64", "TRANSIENT_UNTIL_COMMON_W_MERGE"),
         ("W_WEIGHTED_OUTER_SUM", [1664,1664], "float64", "TRANSIENT_UNTIL_COMMON_W_MERGE"),
         ("W_WEIGHT_SUM", [1], "float64", "TRANSIENT_UNTIL_COMMON_W_MERGE")]
    dev = [("SHARED_DIFFERENTIAL_COMPONENTS",[25,2,2,4,4],"float64","RETAINED_FINEST_UNIT"),("ENDPOINT_UNIT_VALUES",[25,2,6],"float64","RETAINED_FINEST_UNIT"),
           ("THROUGHPUT_NUMERATOR_256",[4,25,2,256],"float64","RETAINED_FINEST_UNIT"),("THROUGHPUT_REFERENCE_DENOMINATOR_256",[4,25,2,256],"float64","RETAINED_FINEST_UNIT"),
           ("THROUGHPUT_AVAILABILITY_256",[6400],"uint8","RETAINED_FINEST_UNIT"),("MATCHED_COST_ELIGIBILITY_INPUTS",[25,2,4],"float64","RETAINED_FINEST_UNIT"),
           ("BOOTSTRAP_PERMUTATION_UNCERTAINTY_UNIT_VALUES",[25,2,6],"float64","RETAINED_FINEST_UNIT"),("RESAMPLING_UNIT_KEYS",[25,2,4],"uint64","RETAINED_FINEST_UNIT"),
           ("CANDIDATE_FAMILY_GLOBAL_TERMINAL_INPUTS",[25,2,12],"float64","RETAINED_FINEST_UNIT")]
    val = [(name, ([24,25,2,256] if name in ("THROUGHPUT_NUMERATOR_256","THROUGHPUT_REFERENCE_DENOMINATOR_256") else [38400] if name=="THROUGHPUT_AVAILABILITY_256" else shape), dtype, retention) for name,shape,dtype,retention in dev]
    val += [("BRIDGE_24_UNIT_VALUES",[25,2,24,6],"float64","RETAINED_FINEST_UNIT"),("HELD_OUT_4_UNIT_VALUES",[25,2,4,4],"float64","RETAINED_FINEST_UNIT")]
    manifest = {"$schema": "https://json-schema.org/draft/2020-12/schema", "oneOf": [manifest_branch("COMMON_W_PASS","development",w), manifest_branch("DEVELOPMENT_METRIC_PASS","development",dev), manifest_branch("VALIDATION_METRIC_PASS","single_use_validation",val)]}
    hash_names = ["contract","exact80","nuisance","seed_split","driver_code","verifier_code","stats_code","merge_code","core_code","runtime","dependencies"]
    receipt = {"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","additionalProperties":False,
               "required":["schema_version","status","partition","phase","identity_id","chunk_id","hashes","shape","dtype","value_count","driver_raw_sha256","verifier_raw_sha256","max_abs_diff","max_rel_diff","full_role_manifest_sha256","role_count","canonical_merge_position"],
               "properties":{"schema_version":{"const":"gen_enc_2_e2_full_role_receipt_rc03_v1"},"status":{"const":"PASS"},"partition":{"enum":["development","single_use_validation"]},
                             "phase":{"enum":["COMMON_W_PASS","DEVELOPMENT_METRIC_PASS","VALIDATION_METRIC_PASS"]},"identity_id":{"type":"string"},"chunk_id":{"type":"string","pattern":"^chunk_[0-9]{3}$"},
                             "hashes":{"type":"object","additionalProperties":False,"required":hash_names,"properties":{name:HEX for name in hash_names}},
                             "shape":{"oneOf":[{"const":[4,25,2,4,256]},{"const":[24,25,2,4,256]}]},"dtype":{"const":"complex128"},"value_count":{"enum":[204800,1228800]},
                             "driver_raw_sha256":HEX,"verifier_raw_sha256":HEX,"max_abs_diff":{"type":"number","minimum":0},"max_rel_diff":{"type":"number","minimum":0},
                             "full_role_manifest_sha256":HEX,"role_count":{"enum":[3,9,11]},"canonical_merge_position":{"type":"integer","minimum":0,"maximum":11759}}}
    dterm = {"type":"object","additionalProperties":False,"required":["schema_version","status","complete_identities","independent_verify_pass","common_w_sha256","candidate_decision_hashes","family_aggregate_sha256","development_decisions_sealed","validation_opened","validation_refit","final_test_read"],
             "properties":{"schema_version":{"const":"gen_enc_2_e2_development_seal_rc03_v1"},"status":{"const":"E2_D_SEALED_INDEPENDENT_PASS"},"complete_identities":{"const":80},"independent_verify_pass":{"const":True},"common_w_sha256":HEX,
                           "candidate_decision_hashes":{"type":"array","minItems":80,"maxItems":80,"items":HEX},"family_aggregate_sha256":HEX,"development_decisions_sealed":{"const":True},"validation_opened":{"const":False},"validation_refit":{"const":False},"final_test_read":{"const":False}}}
    vterm = {"type":"object","additionalProperties":False,"required":["schema_version","partition","status","complete_identities","independent_verify_pass","common_w_sha256","development_seal_sha256","candidate_terminals_sha256","family_global_terminal_sha256","validation_refit","validation_feedback_to_development","single_use_consumed","formal_run_id_created","final_test_read"],
             "properties":{"schema_version":{"const":"gen_enc_2_e2_partition_terminal_rc03_v1"},"partition":{"const":"single_use_validation"},"status":{"const":"E2_V_SINGLE_USE_TERMINAL"},"complete_identities":{"const":80},"independent_verify_pass":{"const":True},"common_w_sha256":HEX,"development_seal_sha256":HEX,"candidate_terminals_sha256":HEX,"family_global_terminal_sha256":HEX,"validation_refit":{"const":False},"validation_feedback_to_development":{"const":False},"single_use_consumed":{"const":True},"formal_run_id_created":{"const":False},"final_test_read":{"const":False}}}
    return {"full_role_manifest.schema.json":manifest,"full_role_receipt.schema.json":receipt,
            "partition_terminal.schema.json":{"$schema":"https://json-schema.org/draft/2020-12/schema","oneOf":[dterm,vterm]}}


def main() -> int:
    required = {B_REVIEW:"4d9d7cc8e9c0d822d45ffb0ae2bcf5b7739ea10913a35bcf0b9b7010db6a555a",G_REVIEW:"90d6a9af958799b6d7dc9eec995f69b163cd23dedb0ec51ebe1398ec1050d8ec"}
    for path, expected in required.items():
        if sha(REPO/path)!=expected: raise SystemExit(f"REVIEW_HASH_MISMATCH:{path}")
    OUT.mkdir(parents=True,exist_ok=True)
    for name,schema in schemas().items(): Draft202012Validator.check_schema(schema); write(name,schema)
    ledger=storage_ledger(); write("storage_bound_ledger.json",ledger)
    if not ledger["bound_pass"]: raise SystemExit("STORAGE_BOUND_EXCEEDS_48_GIB")
    sources=[("src/acoustic_encoder/gen_enc/e2_rc03_stats.py","FULL_ROLE_SCIENTIFIC_STATS"),("src/acoustic_encoder/gen_enc/e2_rc03_resource.py","PROCESS_TREE_RESOURCE_ACCOUNTING"),
             ("scripts/gen_enc_2_e2_formal_driver_rc03.py","THREE_PASS_FORMAL_DRIVER"),("scripts/gen_enc_2_e2_independent_verifier_rc03.py","FULL_ROLE_INPUT_RECOMPUTING_VERIFIER"),
             ("scripts/gen_enc_2_e2_merge_reconstruct_rc03.py","EXECUTABLE_MERGE_RECONSTRUCTION"),("scripts/build_gen_enc_2_e2_rc03_final_closure.py","NO_FORMAL_PACKAGE_BUILDER"),
             ("tests/test_gen_enc_2_e2_rc03_final_closure.py","MINIMAL_RC_A_E_TESTS"),("src/acoustic_encoder/gen_enc/forward_acoustic_network.py","ACCEPTED_FROZEN_CORE")]
    write("source_manifest.json",{"schema_version":"gen_enc_2_e2_source_manifest_rc03_v1","entries":[bind(p,r) for p,r in sources],"verifier_imports_driver":False,"science_changed":False,"formal_execution":False,"final_test_read":False})
    write("runtime_manifest.json",{"schema_version":"gen_enc_2_e2_runtime_manifest_rc03_v1","platform":platform.platform(),"authoritative_runtime":bind(FREEZE02/"runtime_manifest.json","UNCHANGED_RUNTIME"),
          "resource_method":"PSUTIL_WINDOWS_PROCESS_TREE_SAMPLE_10MS_V1","cpu_metric":"PARENT_PLUS_ALL_DESCENDANT_USER_PLUS_SYSTEM_SECONDS","memory_metric":"MAX_SAMPLED_SUM_RSS_PARENT_PLUS_ALL_LIVE_DESCENDANTS","wall_metric":"PERF_COUNTER_FROM_PRE_OUTPUT_ROOT_GATE_THROUGH_FINAL_TERMINAL",
          "limits":{"cpu_core_seconds":72000,"wall_seconds":36000,"aggregate_peak_rss_bytes":8*1024**3},"formal_execution":False,"final_test_read":False})
    base=["--contract",(REL/"contract.json").as_posix(),"--exact80",(CORR01/"exact80_manifest.json").as_posix(),"--nuisance-csv","outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv","--seed-split","outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json","--source-manifest",(REL/"source_manifest.json").as_posix(),"--runtime-manifest",(REL/"runtime_manifest.json").as_posix(),"--verifier","scripts/gen_enc_2_e2_independent_verifier_rc03.py","--stats-code","src/acoustic_encoder/gen_enc/e2_rc03_stats.py","--merge-code","scripts/gen_enc_2_e2_merge_reconstruct_rc03.py","--through-reference","outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_authority_addendum_01/THROUGH_REFERENCE_U4_IDENTITY_V1.json"]
    prefix=["D:/Anaconda3/python.exe","-B","scripts/gen_enc_2_e2_formal_driver_rc03.py"]
    droot=(FORMAL/"development").as_posix(); vroot=(FORMAL/"single_use_validation").as_posix()
    write("command_manifest.json",{"schema_version":"gen_enc_2_e2_command_manifest_rc03_v1","development_argv":prefix+["development","--authorization","outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_2_E2_RC03_DEVELOPMENT_AUTHORIZATION.json","--output-root",droot]+base,
          "single_use_validation_argv":prefix+["single-use-validation","--authorization","outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_2_E2_RC03_SINGLE_USE_VALIDATION_AUTHORIZATION.json","--output-root",vroot,"--development-seal",f"{droot}/partition_terminal.json","--sealed-w",f"{droot}/sealed/common_w.npz"]+base,
          "formal_commands_executed":0,"authorization_first":True,"final_test_read":False})
    write("output_graph.json",{"schema_version":"gen_enc_2_e2_output_graph_rc03_v1","edges":["D_RAW_TO_INDEPENDENT_VERIFY","D_COMMON_W_ROLES_TO_CANONICAL_ACCUMULATOR","ACCUMULATOR_TO_ONE_OAS_W_SEAL","SEALED_W_TO_D_METRIC_ROLES","D80_CANDIDATES_TO_FOUR_FAMILY_AGGREGATES_TO_D_SEAL","D_SEAL_AND_SAME_W_TO_SINGLE_USE_V_METRICS","V80_CANDIDATES_TO_FOUR_FAMILY_AND_GLOBAL_TERMINAL"],"validation_refits_w":False,"validation_feedback_to_development":False,"delete_gate":"COMPLETE_EXACT_ROLE_SET_RECEIPT_MANIFEST_MERGE_CONTRIBUTION_CHECKPOINT_RESOURCE_PASS_THEN_RAW_DELETE","failure":"ONE_CHUNK_QUARANTINE_PARTITION_STOP_NO_MERGE_NO_RETRY","final_test_read":False})
    write("authority_record.json",{"schema_version":"gen_enc_2_e2_rc03_final_closure_authority_v1","status":"RC_A_E_IMPLEMENTED_EXECUTION_UNAUTHORIZED","reviews":[bind(B_REVIEW,"ADVISOR_B_RC03_REVIEW"),bind(G_REVIEW,"GUARDIAN_RC_A_E_REVIEW")],"additive_to":bind(FREEZE02/"SHA256SUMS.txt","FREEZE02_IMMUTABLE_PROVENANCE"),"closed":["FREEZE02-RC-A","FREEZE02-RC-B","FREEZE02-RC-C","FREEZE02-RC-D","FREEZE02-RC-E"],"gap01_to_gap05_changed":False,"science_changed":False,"exact80_changed":False,"formal_execution":False,"formal_response_reads":0,"formal_response_writes":0,"controls_created":0,"formal_run_id_created":False,"final_test_read":False})
    write("schema_manifest.json",{"schema_version":"gen_enc_2_e2_schema_manifest_rc03_v1","entries":[bind(REL/name,"EXACT_PHASE_SCHEMA") for name in sorted(schemas())],"meta_valid":True,"final_test_read":False})
    write("path_allowlist.json",{"schema_version":"gen_enc_2_e2_path_allowlist_rc03_v1","development_root":droot,"validation_root":vroot,"validation_before_d_seal":False,"cross_partition_read":False,"formal_roots_created":False,"final_test_read":False})
    write("contract.json",{"schema_version":"gen_enc_2_e2_preexecution_contract_freeze02_rc03_closure_v1","status":"READY_FOR_B_AND_GUARDIAN_FINAL_NARROW_CONFIRMATION","authority":bind(REL/"authority_record.json","RC03_FINAL_AUTHORITY"),"accepted_science":bind(CORR01/"contract.json","UNCHANGED_SCIENCE"),"source":bind(REL/"source_manifest.json","IMPLEMENTATION_BYTES"),"runtime":bind(REL/"runtime_manifest.json","PROCESS_TREE_RUNTIME"),"commands":bind(REL/"command_manifest.json","EXACT_COMMANDS"),"schemas":bind(REL/"schema_manifest.json","EXACT_ROLE_SCHEMAS"),"storage":bind(REL/"storage_bound_ledger.json","MECHANICAL_BOUND"),"output_graph":bind(REL/"output_graph.json","EXECUTABLE_GRAPH"),"execution_authorized":False,"formal_units":0,"formal_response_reads":0,"formal_response_writes":0,"controls_created":0,"formal_run_id_created":False,"final_test_read":False})
    write("DRAFT_ZERO_STATE.json",{"schema_version":"gen_enc_2_e2_zero_state_rc03_v1","status":"NO_FORMAL_EXECUTION","development_units":0,"validation_units":0,"formal_response_reads":0,"formal_response_writes":0,"formal_roots_created":False,"controls_created":0,"formal_run_id_created":False,"scientific_results":[],"final_test_read":False})
    files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in ("artifact_inventory.json","no_run_validation_report.json","SHA256SUMS.txt"))
    write("artifact_inventory.json",{"schema_version":"gen_enc_2_e2_inventory_rc03_v1","entries":[{"path":(REL/p.name).as_posix(),"sha256":sha(p),"bytes":p.stat().st_size} for p in files],"formal_artifacts":0,"final_test_read":False})
    scan=sorted(p for p in OUT.iterdir() if p.is_file()); tokens=["T"+"BD","T"+"ODO","REQUIRES_"+"DECISION","FUTURE_"+"DECISION"]
    hits=[{"file":p.name,"token":t} for p in scan for t in tokens if t.lower() in p.read_text(encoding="utf-8").lower()]
    write("no_run_validation_report.json",{"schema_version":"gen_enc_2_e2_no_run_rc03_v1","status":"PASS" if not hits else "FAIL","review_hashes_match":True,"schemas_meta_valid":3,"exact_phase_role_counts":{"COMMON_W_PASS":3,"DEVELOPMENT_METRIC_PASS":9,"VALIDATION_METRIC_PASS":11},"storage_bound_pass":ledger["bound_pass"],"forbidden_token_hits":hits,"formal_tests":0,"formal_units":0,"formal_response_reads":0,"formal_response_writes":0,"controls_created":0,"formal_run_id_created":False,"final_test_read":False})
    if hits: raise SystemExit("TOKEN_SCAN_FAIL")
    allfiles=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!="SHA256SUMS.txt")
    (OUT/"SHA256SUMS.txt").write_text("\n".join(f"{sha(p)}  {(REL/p.name).as_posix()}" for p in allfiles)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"status":"READY_FOR_B_AND_GUARDIAN_FINAL_NARROW_CONFIRMATION","package":REL.as_posix(),"seal_sha256":sha(OUT/"SHA256SUMS.txt"),"storage_bytes":ledger["worst_case_retained_bytes"],"storage_gib":ledger["worst_case_retained_gib"]},sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
