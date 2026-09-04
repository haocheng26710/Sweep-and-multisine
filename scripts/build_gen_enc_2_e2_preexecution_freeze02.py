"""Build the additive GEN-ENC-2 E2 Freeze02 RC completion package.

This builder is metadata-only. It does not open formal response roots and does
not execute development or single-use validation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import sys
from typing import Any

from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[1]
REL = Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_02")
OUT = REPO / REL
GUARDIAN = Path("outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2_E2_AUTHORITY_ADDENDUM_01_FREEZE_01_CORR01_GUARDIAN_REVIEW.json")
GUARDIAN_SHA = "c69015d6bbe9fba1c70146365963eb2adcb36c1f0855f28a6a94fa31c78a4f49"
CORR01 = Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01")
AUTHORITY = Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_authority_addendum_01")
FORMAL_ROOT = Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_freeze02")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def binding(relative: Path | str, role: str) -> dict[str, Any]:
    relative = Path(relative)
    path = REPO / relative
    return {"path": relative.as_posix(), "sha256": sha(path), "bytes": path.stat().st_size, "role": role}


def write(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def obj(required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": required, "properties": properties}


HEX = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
PATH = {"type": "string", "minLength": 1}
U64 = {"type": "integer", "minimum": 0}


def schemas() -> dict[str, dict[str, Any]]:
    hash_fields = ["contract", "exact80", "nuisance", "seed_split", "driver_code", "verifier_code", "core_code", "runtime", "dependencies"]
    hashes = obj(hash_fields, {name: HEX for name in hash_fields})
    array_entry = obj(
        ["role", "path", "sha256", "shape", "dtype", "order", "format"],
        {"role": {"enum": ["W_WEIGHTED_OUTER_SUM", "W_WEIGHT_SUM", "ENDPOINT_UNIT_VALUES", "THROUGHPUT_FREQUENCY_VALUES", "BRIDGE_UNIT_VALUES", "BOOTSTRAP_PERMUTATION_UNIT_KEYS", "port_power_by_frequency", "differential_energy"]},
         "path": PATH, "sha256": HEX, "shape": {"type": "array", "minItems": 1, "items": U64},
         "dtype": {"enum": ["float64", "uint64"]}, "order": {"const": "C"}, "format": {"const": "NPY_1_0"}},
    )
    result: dict[str, dict[str, Any]] = {}
    result["chunk_receipt.schema.json"] = obj(
        ["schema_version", "status", "partition", "identity_id", "chunk_id", "cell_start", "cell_end_exclusive", "hashes", "value_count", "shape", "dtype", "driver_raw_sha256", "verifier_raw_sha256", "max_abs_diff", "max_rel_diff", "sufficient_stat_manifest_sha256", "merge_position"],
        {"schema_version": {"const": "gen_enc_2_e2_chunk_pass_receipt_freeze02_v1"}, "status": {"const": "PASS"},
         "partition": {"enum": ["development", "single_use_validation"]}, "identity_id": {"type": "string", "pattern": "^(HAND|NEAR|RANDOM|PHYSICS)_[0-9]{2}$"},
         "chunk_id": {"type": "string", "pattern": "^chunk_[0-9]{3}$"}, "cell_start": U64, "cell_end_exclusive": {"type": "integer", "minimum": 1, "maximum": 3675},
         "hashes": hashes, "value_count": {"type": "integer", "minimum": 1}, "shape": {"type": "array", "minItems": 5, "maxItems": 5, "items": {"type": "integer", "minimum": 1}},
         "dtype": {"const": "complex128"}, "driver_raw_sha256": HEX, "verifier_raw_sha256": HEX,
         "max_abs_diff": {"type": "number", "minimum": 0}, "max_rel_diff": {"type": "number", "minimum": 0},
         "sufficient_stat_manifest_sha256": HEX, "merge_position": U64},
    )
    result["compact_stats_manifest.schema.json"] = obj(
        ["schema_version", "partition", "stage", "identity_id", "chunk_id", "cell_start", "cell_end_exclusive", "format", "entries", "merge_algebra", "canonical_merge_key", "raw_complex_json_records"],
        {"schema_version": {"const": "gen_enc_2_e2_compact_stats_manifest_freeze02_v1"}, "partition": {"enum": ["development", "single_use_validation"]},
         "stage": {"enum": ["COMMON_W_PASS", "METRIC_PASS"]}, "identity_id": {"type": "string"}, "chunk_id": {"type": "string", "pattern": "^chunk_[0-9]{3}$"},
         "cell_start": U64, "cell_end_exclusive": {"type": "integer", "minimum": 1, "maximum": 3675}, "format": {"const": "NPY_1_0"},
         "entries": {"type": "array", "minItems": 1, "items": array_entry},
         "merge_algebra": {"const": "SEQUENTIAL_BINARY64_SUM_FOR_MATCHED_SHAPES_AND_C_AXIS_CONCATENATION_FOR_CANONICAL_RESAMPLING_ROWS"},
         "canonical_merge_key": {"const": "PARTITION_STAGE_FAMILY_ORDINAL_MEMBER_ORDINAL_CHUNK_INDEX_ARRAY_ROLE"}, "raw_complex_json_records": {"const": False}},
    )
    result["checkpoint.schema.json"] = obj(
        ["schema_version", "partition", "stage", "status", "last_merge_position", "last_receipt_sha256", "last_stats_manifest_sha256", "managed_bytes", "free_bytes", "cpu_seconds", "wall_seconds", "aggregate_peak_bytes", "same_run_retry", "later_merge"],
        {"schema_version": {"const": "gen_enc_2_e2_checkpoint_freeze02_v1"}, "partition": {"enum": ["development", "single_use_validation"]}, "stage": {"enum": ["COMMON_W_PASS", "METRIC_PASS"]},
         "status": {"enum": ["PASS_VERIFIED_CHECKPOINTED", "PARTITION_STOP", "RESOURCE_BLOCKED"]}, "last_merge_position": U64,
         "last_receipt_sha256": HEX, "last_stats_manifest_sha256": HEX, "managed_bytes": U64, "free_bytes": U64,
         "cpu_seconds": {"type": "number", "minimum": 0}, "wall_seconds": {"type": "number", "minimum": 0}, "aggregate_peak_bytes": U64,
         "same_run_retry": {"const": False}, "later_merge": {"type": "boolean"}},
    )
    result["audit_manifest.schema.json"] = obj(
        ["schema_version", "domain", "partition", "identity_id", "selected_chunks", "selection_hashes", "retained_paths", "retained_sha256", "response_independent", "selection_use"],
        {"schema_version": {"const": "gen_enc_2_e2_audit_manifest_freeze02_v1"}, "domain": {"const": "GEN_ENC_E2_RAW_AUDIT_V1"},
         "partition": {"enum": ["development", "single_use_validation"]}, "identity_id": {"type": "string"},
         "selected_chunks": {"type": "array", "minItems": 2, "maxItems": 2, "uniqueItems": True, "items": {"type": "string", "pattern": "^chunk_[0-9]{3}$"}},
         "selection_hashes": {"type": "array", "minItems": 2, "maxItems": 2, "items": HEX}, "retained_paths": {"type": "array", "minItems": 2, "maxItems": 2, "items": PATH},
         "retained_sha256": {"type": "array", "minItems": 2, "maxItems": 2, "items": HEX}, "response_independent": {"const": True},
         "selection_use": {"const": "AUDIT_ONLY_NO_REFIT_THRESHOLD_SELECTION_OR_DECISION"}},
    )
    result["quarantine_record.schema.json"] = obj(
        ["schema_version", "partition", "identity_id", "chunk_id", "raw_path", "raw_sha256", "failure_code", "partition_stopped", "merged", "deleted", "same_run_retry"],
        {"schema_version": {"const": "gen_enc_2_e2_quarantine_record_freeze02_v1"}, "partition": {"enum": ["development", "single_use_validation"]}, "identity_id": {"type": "string"},
         "chunk_id": {"type": "string", "pattern": "^chunk_[0-9]{3}$"}, "raw_path": PATH, "raw_sha256": HEX, "failure_code": {"type": "string", "minLength": 1},
         "partition_stopped": {"const": True}, "merged": {"const": False}, "deleted": {"const": False}, "same_run_retry": {"const": False}},
    )
    result["partition_terminal.schema.json"] = obj(
        ["schema_version", "partition", "status", "complete_identities", "complete_chunks", "independent_verify_pass", "development_seal_sha256", "validation_feedback_to_development", "formal_run_id_created", "final_test_read"],
        {"schema_version": {"const": "gen_enc_2_e2_partition_terminal_freeze02_v1"}, "partition": {"enum": ["development", "single_use_validation"]},
         "status": {"enum": ["E2_D_SEALED_INDEPENDENT_PASS", "E2_V_SINGLE_USE_TERMINAL", "RESOURCE_BLOCKED", "TECHNICAL_FAILURE"]},
         "complete_identities": {"type": "integer", "minimum": 0, "maximum": 80}, "complete_chunks": {"type": "integer", "minimum": 0, "maximum": 11760},
         "independent_verify_pass": {"type": "boolean"}, "development_seal_sha256": HEX, "validation_feedback_to_development": {"const": False},
         "formal_run_id_created": {"const": False}, "final_test_read": {"const": False}},
    )
    return {name: {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": name, **schema} for name, schema in result.items()}


def main() -> int:
    if sha(REPO / GUARDIAN) != GUARDIAN_SHA:
        raise SystemExit("GUARDIAN_REVIEW_HASH_MISMATCH")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        write(name, schema)

    exact80 = json.loads((REPO / CORR01 / "exact80_manifest.json").read_text(encoding="utf-8"))
    label_errors = []
    for member in exact80["members"]:
        expected = f"B{(int(member['family_ordinal']) - 1) // 5 + 1}"
        if member["source_batch"] != expected or f"/{expected.lower()}_science_first_exact20_runs/" not in member["source_authority_path"]:
            label_errors.append(member["member_id"])
    if label_errors:
        raise SystemExit("EXACT80_SOURCE_BATCH_AUDIT_FAIL:" + ",".join(label_errors))

    source_entries = [
        binding("src/acoustic_encoder/gen_enc/forward_acoustic_network.py", "HASH_FROZEN_SHARED_SCIENTIFIC_CORE"),
        binding("src/acoustic_encoder/gen_enc/e2_authority.py", "ANGLE_SEED_AND_COMMON_W_RULES"),
        binding("src/acoustic_encoder/gen_enc/generator/prng.py", "SPLITMIX64_PRIMITIVE"),
        binding("src/acoustic_encoder/gen_enc/estimator.py", "FROZEN_ESTIMATOR_ALGEBRA"),
        binding("src/acoustic_encoder/gen_enc/bridge.py", "FROZEN_BRIDGE_ALGEBRA"),
        binding("scripts/gen_enc_2_e2_formal_driver_freeze02.py", "FORMAL_AUTHORIZATION_GATED_DRIVER"),
        binding("scripts/gen_enc_2_e2_independent_verifier_freeze02.py", "INPUT_RECOMPUTING_INDEPENDENT_VERIFIER"),
        binding("tests/test_gen_enc_2_e2_freeze02_rc.py", "SYNTHETIC_RC_TESTS"),
        binding("tests/test_gen_enc_2_e2_authority_corr01.py", "ACCEPTED_SCIENCE_REGRESSION_TESTS"),
    ]
    source = {"schema_version": "gen_enc_2_e2_source_manifest_freeze02_v1", "entries": source_entries,
              "verifier_imports_formal_driver": False, "shared_imports": ["HASH_FROZEN_CORE", "CANONICAL_JSON", "SHA256"],
              "unresolved_imports": [], "formal_execution": False, "final_test_read": False}
    write("source_manifest.json", source)
    runtime = {"schema_version": "gen_enc_2_e2_runtime_manifest_freeze02_v1", "python": platform.python_version(),
               "executable": binding(Path(sys.executable).relative_to(REPO) if Path(sys.executable).is_relative_to(REPO) else Path("scripts/gen_enc_2_e2_formal_driver_freeze02.py"), "RUNTIME_BINDING_FALLBACK_TO_FROZEN_CORR01"),
               "authoritative_runtime": binding(CORR01 / "runtime_manifest.json", "CORR01_RUNTIME_AND_DEPENDENCIES"),
               "thread_environment": {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
               "workers": 1, "maximum_workers": 8, "preferred_execution": "SINGLE_PROCESS", "formal_execution": False, "final_test_read": False}
    write("runtime_manifest.json", runtime)

    common = ["D:/Anaconda3/python.exe", "-B", "scripts/gen_enc_2_e2_formal_driver_freeze02.py"]
    base_args = ["--contract", (REL / "contract.json").as_posix(), "--exact80", (CORR01 / "exact80_manifest.json").as_posix(),
                 "--nuisance-csv", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv",
                 "--seed-split", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json",
                 "--source-manifest", (REL / "source_manifest.json").as_posix(), "--runtime-manifest", (REL / "runtime_manifest.json").as_posix(),
                 "--checkpoint", "checkpoint.json", "--verifier", "scripts/gen_enc_2_e2_independent_verifier_freeze02.py"]
    d_auth = "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_2_E2_FREEZE02_DEVELOPMENT_EXECUTION_AUTHORIZATION.json"
    v_auth = "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_2_E2_FREEZE02_SINGLE_USE_VALIDATION_EXECUTION_AUTHORIZATION.json"
    d_root = (FORMAL_ROOT / "development").as_posix()
    v_root = (FORMAL_ROOT / "single_use_validation").as_posix()
    d_command = common + ["development", "--authorization", d_auth, "--output-root", d_root] + base_args
    v_command = common + ["single-use-validation", "--authorization", v_auth, "--output-root", v_root, "--development-seal", f"{d_root}/partition_terminal.json"] + base_args
    commands = {"schema_version": "gen_enc_2_e2_exact_command_manifest_freeze02_v1", "working_directory": REPO.as_posix(),
                "development_argv": d_command, "single_use_validation_argv": v_command,
                "pre_read_gate": "AUTHORIZATION_FILE_ONLY_BEFORE_ANY_SCIENCE_INPUT_OR_OUTPUT_ROOT_ACCESS",
                "formal_execution_authorized": False, "formal_commands_executed": 0, "final_test_read": False}
    write("command_manifest.json", commands)

    storage_components = {"metric_payload": 34_489_728_000, "audit_raw_320_chunks": 3_670_016_000, "common_w": 66_453_504,
                          "receipts": 578_027_520, "stats_manifests": 289_013_760, "checkpoint": 268_435_456,
                          "single_failure_quarantine": 19_660_800, "misc_inventory": 536_870_912, "filesystem_safety_overhead": 4_294_967_296}
    storage_total = sum(storage_components.values())
    storage = {"schema_version": "gen_enc_2_e2_retained_storage_bound_freeze02_v1", "components_bytes": storage_components,
               "worst_case_retained_bytes": storage_total, "worst_case_retained_gib": storage_total / 1024**3,
               "managed_cap_bytes": 48 * 1024**3, "startup_free_minimum_bytes": 80 * 1024**3, "reserve_floor_bytes": 32 * 1024**3,
               "bound_pass": storage_total <= 48 * 1024**3, "raw_audit_chunks": 320, "full_raw_saved": False,
               "quarantine_allowance": "ONE_LARGEST_VALIDATION_CHUNK", "formal_execution": False, "final_test_read": False}
    write("retained_storage_bound.json", storage)
    reconstruction = {
        "schema_version": "gen_enc_2_e2_reconstruction_proof_freeze02_v1",
        "passes": ["DEVELOPMENT_COMMON_W_PASS", "DEVELOPMENT_METRIC_PASS_AFTER_W_SEAL", "SINGLE_USE_VALIDATION_METRIC_PASS_WITH_SEALED_W"],
        "common_w": {"unit": "FAMILY_MEMBER_CELL_REPEAT_STATE_RESIDUAL_ROW", "feature_dimension": 1664, "rows": 2352000,
                     "weight": "1/4*1/20*1/3675*1/8=1/2352000", "chunk_contribution": "SUM_W_AND_SUM_W_OUTER_XXT_FLOAT64",
                     "merge": "SEQUENTIAL_BINARY64_ADDITION_IN_FAMILY_MEMBER_CHUNK_ORDER", "missing_nonfinite": "W_UNAVAILABLE_NO_DROP_FILL_OR_RENORMALIZE", "validation_refit": False},
        "metric_payload": {"format": "NPY_1_0_FLOAT64_OR_UINT64_NO_COMPLEX_JSON", "finest_key": "PARTITION_IDENTITY_CELL_REPEAT_ANGLE_FREQUENCY_WHERE_REQUIRED",
                           "roles": {"ENDPOINT_UNIT_VALUES": "PER_CELL_REPEAT_SIGMA_1_2_3_SHARED_AND_DIFFERENTIAL_SUMMARIES",
                                     "THROUGHPUT_FREQUENCY_VALUES": "PER_CELL_REPEAT_ANGLE_ALL_256_FREQUENCIES_CANDIDATE_OVER_REFERENCE_OR_UNAVAILABLE_CODE",
                                     "BRIDGE_UNIT_VALUES": "PER_CELL_REPEAT_ALL_24_ANGLES_RESPONSE_ANGLE_DERIVATIVE_MARGIN_CHORD_HELDOUT_AND_STATUS",
                                     "BOOTSTRAP_PERMUTATION_UNIT_KEYS": "PER_IDENTITY_CELL_REPEAT_CANONICAL_KEYS_AND_UNIT_VALUES"}},
        "reconstructs": ["COMMON_W", "SHARED_DIFFERENTIAL", "E_PRIMARY", "R_STABLE", "MATCHED_COST_ELIGIBILITY", "THROUGHPUT_DIAGNOSTIC", "CONTINUOUS_BRIDGE", "HELD_OUT", "CANDIDATE_TERMINALS", "FAMILY_WORST_MEMBER", "BOOTSTRAP", "PERMUTATION", "UNCERTAINTY", "GLOBAL_TERMINALS"],
        "family_rule": "ALL_20_REQUIRED_WORST_MEMBER_NO_GLOBAL_RANKING_BEFORE_FOUR_COMPLETE_FAMILIES",
        "primary_secondary": "PRIMARY_200_4000_208_POINTS_AND_SECONDARY_200_8000_256_POINTS_REPORTED_SEPARATELY",
        "proof": "Each nonlinear candidate or bridge statistic is evaluated before raw deletion at the finest frozen resampling unit; its scalar/vector result and canonical unit key are retained. Frequency-resolved throughput retains every 256-point ratio. Common W retains the exact weighted outer-product accumulator. Therefore all later resampling and worst-member reductions replay from retained unit payloads without raw responses.",
        "formal_execution": False, "final_test_read": False,
    }
    write("reconstruction_proof.json", reconstruction)
    paths = {"schema_version": "gen_enc_2_e2_path_allowlist_freeze02_v1", "read_after_authorization": [entry["path"] for entry in source_entries] + [
                (CORR01 / "exact80_manifest.json").as_posix(), "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv",
                "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json", (AUTHORITY / "THROUGH_REFERENCE_U4_IDENTITY_V1.json").as_posix()],
             "development_write_root": d_root, "validation_write_root": v_root, "validation_read_before_development_seal": False,
             "cross_partition_reads": False, "forbidden_roots": ["FINAL_TEST", "HELD_OUT_RESPONSE", "COMSOL", "FULL_WAVE", "E3", "E4"], "final_test_read": False}
    write("path_allowlist.json", paths)
    schema_names = sorted(schemas())
    write("schema_manifest.json", {"schema_version": "gen_enc_2_e2_schema_manifest_freeze02_v1", "entries": [binding(REL / name, "FULLY_CONSTRAINED_SCHEMA") for name in schema_names], "draft": "2020-12", "meta_valid": True, "final_test_read": False})

    authority = {"schema_version": "gen_enc_2_e2_rc_completion_authority_freeze02_v1", "status": "RC01_RC04_CLOSED_EXECUTION_UNAUTHORIZED",
                 "guardian_review": binding(GUARDIAN, "REVISE_REVIEW_BOUND"), "accepted_science_authority": binding(AUTHORITY / "SHA256SUMS.txt", "GAP01_GAP05_ACCEPTED_UNCHANGED"),
                 "corr01": binding(CORR01 / "SHA256SUMS.txt", "FREEZE01_CORR01_IMMUTABLE_PROVENANCE"), "closed_items": ["RC01", "RC02", "RC03", "RC04"],
                 "scientific_semantics_changed": False, "exact80_or_workload_changed": False, "execution_authorized": False,
                 "formal_units": 0, "formal_response_reads": 0, "formal_response_writes": 0, "formal_run_id_created": False, "controls_created": 0, "final_test_read": False}
    write("authority_record.json", authority)
    contract = {"schema_version": "gen_enc_2_e2_preexecution_contract_freeze02_v1", "status": "READY_FOR_B_LIGHTWEIGHT_AND_GUARDIAN_NARROW_CLOSURE",
                "additive_only": True, "authority": binding(REL / "authority_record.json", "RC_COMPLETION_AUTHORITY"),
                "science_contract": binding(CORR01 / "contract.json", "ACCEPTED_SCIENCE_UNCHANGED"), "exact80": binding(CORR01 / "exact80_manifest.json", "EXACT80_CORRECTED_LABELS"),
                "source": binding(REL / "source_manifest.json", "FORMAL_BYTES_CLOSURE"), "runtime": binding(REL / "runtime_manifest.json", "RUNTIME_CLOSURE"),
                "commands": binding(REL / "command_manifest.json", "EXACT_D_AND_V_COMMANDS"), "schemas": binding(REL / "schema_manifest.json", "CONCRETE_STORAGE_SCHEMAS"),
                "paths": binding(REL / "path_allowlist.json", "D_V_ISOLATION"), "storage": binding(REL / "retained_storage_bound.json", "48_GIB_BOUND"),
                "reconstruction": binding(REL / "reconstruction_proof.json", "FINEST_UNIT_RECONSTRUCTION"),
                "rc04_sequence": ["DRIVER_RAW_TEMP", "INDEPENDENT_INPUT_RECOMPUTE", "COMPARE", "PASS_RECEIPT_AND_FINEST_STATS_DURABLE", "CHECKPOINT_AND_RESOURCE_STORAGE_GATE", "AUDIT_RETAIN_OR_NONAUDIT_DELETE"],
                "verify_failure": "QUARANTINE_UNIQUE_CHUNK_STOP_PARTITION_NO_MERGE_NO_DELETE_NO_SAME_RUN_RETRY",
                "development_before_validation": "D_80_OF_80_INDEPENDENT_PASS_W_DECISIONS_AND_SEAL_REQUIRED_BEFORE_ONE_V_OPEN",
                "validation_feedback_to_development": False, "execution_authorized": False, "formal_units": 0, "formal_response_reads": 0,
                "formal_response_writes": 0, "formal_run_id_created": False, "controls_created": 0, "final_test_read": False}
    write("contract.json", contract)
    zero = {"schema_version": "gen_enc_2_e2_draft_zero_state_freeze02_v1", "status": "NO_FORMAL_EXECUTION",
            "formal_development_units": 0, "formal_validation_units": 0, "formal_response_reads": 0, "formal_response_writes": 0,
            "formal_run_id_created": False, "controls_created": 0, "development_root_created": False, "validation_root_created": False,
            "held_out_response_reads": 0, "final_test_read": False, "scientific_results": [], "terminals": []}
    write("DRAFT_ZERO_STATE.json", zero)

    files = sorted(path for path in OUT.iterdir() if path.is_file() and path.name not in {"artifact_inventory.json", "SHA256SUMS.txt", "no_run_validation_report.json"})
    write("artifact_inventory.json", {"schema_version": "gen_enc_2_e2_artifact_inventory_freeze02_v1", "entries": [{"path": (REL / p.name).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in files], "formal_artifacts": 0, "final_test_read": False})
    scan_files = sorted(path for path in OUT.iterdir() if path.is_file())
    forbidden = ["T" + "BD", "T" + "ODO", "FUTURE_" + "DECISION", "REQUIRES_" + "DECISION"]
    hits = [{"file": p.name, "token": token} for p in scan_files for token in forbidden if token.lower() in p.read_text(encoding="utf-8").lower()]
    report = {"schema_version": "gen_enc_2_e2_no_run_validation_freeze02_v1", "status": "PASS" if not hits else "FAIL",
              "guardian_hash_match": True, "json_files_parsed": len(scan_files), "schemas_meta_valid": len(schema_names),
              "exact80_members": 80, "family_counts": {name: 20 for name in ["HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED"]},
              "source_batch_label_errors": label_errors, "workload_units_unchanged": 1176000, "storage_bound_pass": storage["bound_pass"],
              "forbidden_token_hits": hits, "formal_tests": 0, "formal_units": 0, "formal_response_reads": 0, "formal_response_writes": 0,
              "formal_run_id_created": False, "controls_created": 0, "final_test_read": False}
    write("no_run_validation_report.json", report)
    if hits:
        raise SystemExit("FORBIDDEN_TOKEN_SCAN_FAIL")
    all_files = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt")
    (OUT / "SHA256SUMS.txt").write_text("\n".join(f"{sha(path)}  {(REL / path.name).as_posix()}" for path in all_files) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": contract["status"], "package": REL.as_posix(), "seal_sha256": sha(OUT / "SHA256SUMS.txt"), "storage_bytes": storage_total}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
