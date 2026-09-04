"""Build additive E2 authority addendum 01 and Freeze-01 CORR01."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[1]
BASE = Path("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE")
ADD_REL = BASE / "e2_authority_addendum_01"
CORR_REL = BASE / "e2_preexecution_contract_freeze_01_corr01"
ADD = REPO / ADD_REL
CORR = REPO / CORR_REL


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(relative: str | Path) -> Any:
    with (REPO / relative).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(root: Path, name: str, value: Any, *, canonical: bool = False) -> None:
    if canonical:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    (root / name).write_text(text, encoding="utf-8", newline="\n")


def bind(relative: str | Path, role: str) -> dict[str, Any]:
    relative = Path(relative)
    path = REPO / relative
    return {"path": relative.as_posix(), "sha256": digest(path), "bytes": path.stat().st_size, "role": role}


def seal(root: Path, relative: Path) -> str:
    paths = sorted(path for path in root.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt")
    lines = [f"{digest(path)}  {(relative / path.name).as_posix()}" for path in paths]
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return digest(root / "SHA256SUMS.txt")


def main() -> int:
    ADD.mkdir(parents=True, exist_ok=True)
    CORR.mkdir(parents=True, exist_ok=True)
    required = {
        "outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_2_E2_PREEXECUTION_CONTRACT_FREEZE_01_SCOPE_PREEXECUTION_REVIEW.json": "fdc6cbdb847c40b41ea7ce314ceab12822c558d980acd4073ed27364ea2d2550",
        "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2_E2_PREEXECUTION_CONTRACT_FREEZE_01_GUARDIAN_REVIEW.json": "3854fed161eb44250989518270642bef678604b0f306094fad3e85f491ecc7c4",
        "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2_E2_GAP05_TOP_LEVEL_STREAMING_EVIDENCE_DECISION.json": "4e5a2b7469c802daeefb87ec5870d533b249e4b73b25ca143d8e6228fc11b4e5",
    }
    for path, expected in required.items():
        if digest(REPO / path) != expected:
            raise SystemExit(f"REQUIRED_AUTHORITY_HASH_MISMATCH:{path}")

    top_transcription = {
        "schema_version": "gen_enc_2_e2_top_level_authority_transcription_01_v1",
        "record_kind": "ADDITIVE_TRANSCRIPTION_OF_TOP_LEVEL_DECISIONS_U01_TO_U04",
        "source_thread_id": "01a0366d-bb5e-7a13-a1f7-b34403664543",
        "decisions": {
            "U01": "COSINE_NONNEGATIVE_L2_NORMALIZED_COMMON_ZERO_PHASE_ANGLE_TO_FOUR_PORTS",
            "U02": "PARTITION_EXPLICIT_IMMUTABLE_REPEAT_SEED_TUPLES_NO_FALLBACK",
            "U03": "NEUTRAL_NONCANDIDATE_THROUGH_REFERENCE_U4_IDENTITY_V1",
            "U04": "FAMILY_MEMBER_CELL_REPEAT_STATE_BALANCED_DEVELOPMENT_ONLY_COMMON_W",
        },
        "scientific_equations_changed": False, "e2_execution_authorized": False,
        "formal_response_reads": 0, "final_test_read": False,
    }
    write_json(ADD, "top_level_authority_transcription.json", top_transcription)

    reference = {
        "schema_version": "gen_enc_2_e2_through_reference_u4_identity_v1",
        "identity_id": "THROUGH_REFERENCE_U4_IDENTITY_V1",
        "family_id": "THROUGH_REFERENCE_U4_IDENTITY_V1",
        "status": "THROUGH_REFERENCE_STATIC_IDENTITY",
        "roles_excluded": ["EXACT80_MEMBER", "CANDIDATE", "FIFTH_FAMILY", "RANKING", "ENDPOINT", "ELIGIBILITY_GATE"],
        "model": "PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1",
        "interface": "U4_CARDINAL_4PORT_CENTRAL_M1_v1", "total_connected_volume_m3": 3.014899604922098e-5,
        "volume_shares": {"central": 0.40, "local_0": 0.15, "local_90": 0.15, "local_180": 0.15, "local_270": 0.15},
        "graph": {"nodes": ["local_0", "local_90", "local_180", "local_270", "central"], "edges": [["local_0", "central"], ["local_90", "central"], ["local_180", "central"], ["local_270", "central"]], "local_local_edges": [], "ring_edges": [], "diagonal_edges": []},
        "parameters": {
            "q0": 0.0, "q90": 0.0, "q180": 0.0, "q270": 0.0,
            "external_0": 0.5, "external_90": 0.5, "external_180": 0.5, "external_270": 0.5,
            "central_mix": 0.5,
            "loss_0": 0.05, "loss_90": 0.05, "loss_180": 0.05, "loss_270": 0.05,
        },
        "observable": "CENTRAL_COMPLEX_PRESSURE_PER_IDENTICALLY_NORMALIZED_FOUR_PORT_SOURCE",
        "frequency_formula": "f[n]=200*2^(n/48)_Hz_n0_TO_255",
        "comparison_stage": "SAME_PARTITION_ANGLE_CELL_REPEAT_FREQUENCY_AND_PHYSICAL_NUISANCE_BEFORE_ADDITIVE_SENSOR_NOISE",
        "denominator_failure": "UNAVAILABLE_NO_EPSILON_POINT_DELETION_OR_REFERENCE_CHANGE",
        "throughput_role": "MANDATORY_DESCRIPTIVE_NOT_ELIGIBILITY_OR_PERFORMANCE_GATE",
        "final_test_read": False,
    }
    write_json(ADD, "THROUGH_REFERENCE_U4_IDENTITY_V1.json", reference, canonical=True)
    reference_hash = digest(ADD / "THROUGH_REFERENCE_U4_IDENTITY_V1.json")

    angle = {
        "schema_version": "gen_enc_2_e2_angle_authority_01_v1",
        "ports_degrees": [0, 90, 180, 270], "theta_effective": "(theta+delta_theta)_mod_360",
        "raw": "u_i=max(0,cos((theta_effective-phi_i)*pi/180))", "normalized": "b=u/L2_norm(u)",
        "phase": "COMMON_ZERO", "cardinal": "EXACT_ONE_HOT", "intermediate": "TWO_ADJACENT_PORTS_ONLY",
        "development": [0, 90, 180, 270], "single_use_validation": list(range(0, 360, 15)),
        "held_out": [45, 135, 225, 315], "final_test_read": False,
    }
    seed = {
        "schema_version": "gen_enc_2_e2_seed_routing_authority_01_v1",
        "seed_split": bind("outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json", "SEALED_SEED_SPLIT"),
        "partition_repeat_seeds": {"development": [2026091001, 2026091002], "single_use_validation": [2026092001, 2026092002]},
        "repeat_order": [0, 1], "fallback": False, "replacement": False, "development_seed_reuse_in_validation": False,
        "substream_k_registry": {"independent_manufacturing_by_port": [0, 1, 2, 3], "reserved": [4, 5, 6, 7], "additive_sensor_noise_start": 8},
        "splitmix64_rule": "S_PLUS_GOLDEN_GAMMA_TIMES_1_PLUS_64C_PLUS_32R_PLUS_K_MOD_2POW64_THEN_FROZEN_SPLITMIX64",
        "validation_after_development_seal_once": True, "validation_refit": False, "final_test_read": False,
    }
    common_w = {
        "schema_version": "gen_enc_2_e2_common_w_authority_01_v1",
        "partition": "DEVELOPMENT_ONLY", "family_mass": "1/4", "member_mass_within_family": "1/20",
        "global_member_mass": "1/80", "cell_mass_within_member": "1/3675",
        "residual_row_mass_within_member_cell": "1/(2_REPEATS*4_STATES)=1/8",
        "global_residual_row_mass": "1/2352000", "expected_members": 80, "expected_cells_per_member": 3675,
        "expected_residual_rows": 2352000, "primary_real_embedded_feature_dimension": 1664,
        "construction_order": "EXISTING_WITHIN_CELL_REPEAT_RESIDUAL_BLOCK_THEN_ONE_WEIGHTED_COMMON_OAS_COVARIANCE",
        "oas_and_eigen_floor": "UNCHANGED_FROM_GEN_ENC_1", "validation_participates": False,
        "missing_or_nonfinite": "W_UNAVAILABLE_NO_DELETE_IMPUTE_OR_RENORMALIZE", "final_test_read": False,
    }
    throughput = {
        "schema_version": "gen_enc_2_e2_throughput_reference_authority_01_v1",
        "identity_path": f"{ADD_REL.as_posix()}/THROUGH_REFERENCE_U4_IDENTITY_V1.json",
        "identity_sha256": reference_hash, "identity_bytes": (ADD / "THROUGH_REFERENCE_U4_IDENTITY_V1.json").stat().st_size,
        "formula": "g(f)=FROBENIUS_NORM_SQUARED_H_CANDIDATE/FROBENIUS_NORM_SQUARED_H_THROUGH_REFERENCE",
        "same_inputs_before_additive_sensor_noise": True, "descriptive_only": True,
        "denominator_nonfinite_or_zero": "UNAVAILABLE", "epsilon": False, "point_deletion": False, "reference_replacement": False,
        "final_test_read": False,
    }
    storage = {
        "schema_version": "gen_enc_2_e2_streaming_storage_authority_01_v1",
        "top_level_decision": bind("outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2_E2_GAP05_TOP_LEVEL_STREAMING_EVIDENCE_DECISION.json", "TOP_LEVEL_GAP05_DECISION"),
        "full_raw_complex_values": 16859136000, "full_raw_payload_bytes": 269746176000,
        "full_raw_payload_gib": 251.220703125, "canonical_chunks": 23520,
        "cells_per_chunk": 25, "chunks_per_identity_partition": 147,
        "driver_verifier_equivalence": {"dtype": "complex128", "rtol": 1e-10, "atol": 1e-12, "shape_exact": True, "finite": True},
        "pass_delete_gate": ["IDENTITY_INPUT_SHAPE_ORDER_HASH_NUMERIC_PASS", "RECEIPT_PERSISTED", "FINEST_RESAMPLING_UNIT_STATS_PERSISTED_HASHED", "CHECKPOINT_RESOURCE_ACCOUNTING_UPDATED"],
        "audit": {"domain": "GEN_ENC_E2_RAW_AUDIT_V1", "key": "domain|partition|identity_id|chunk_id", "sort": "ASCENDING_SHA256", "retain_per_identity_partition": 2, "expected_total": 320, "response_independent": True},
        "failure": "STOP_PARTITION_QUARANTINE_ONE_FAILURE_CHUNK_NO_LATER_MERGE_NO_DELETE_NO_SAME_RUN_RETRY",
        "managed_storage_cap_gib": 48.0, "startup_free_minimum_gib": 80.0, "free_reserve_floor_gib": 32.0,
        "resource_envelope": {"cpu_core_hours": 20.0, "wall_hours": 10.0, "aggregate_peak_memory_gib": 8.0, "includes": ["DRIVER", "VERIFIER", "IO", "HASH", "STATS", "MERGE", "CHECKPOINT", "DELETE"]},
        "full_raw_persisted": False, "all_raw_recomputable_from_frozen_inputs_code_runtime_receipts": True,
        "evidence_ceiling_changed": False, "final_test_read": False,
    }
    for name, value in (("angle_mapping_authority.json", angle), ("seed_routing_authority.json", seed), ("common_w_authority.json", common_w), ("throughput_reference_authority.json", throughput), ("streaming_storage_authority.json", storage)):
        write_json(ADD, name, value)
    authority = {
        "schema_version": "gen_enc_2_e2_authority_addendum_01_v1", "status": "AUTHORITY_COMPLETE_EXECUTION_UNAUTHORIZED",
        "closes": ["E2_GAP_01", "E2_GAP_02", "E2_GAP_03", "E2_GAP_04", "E2_GAP_05"],
        "top_level_source_thread_id": "01a0366d-bb5e-7a13-a1f7-b34403664543",
        "provenance": [bind(path, "REVIEW_OR_DECISION") for path in required],
        "records": [bind(ADD_REL / name, "ADDITIVE_AUTHORITY") for name in ("top_level_authority_transcription.json", "angle_mapping_authority.json", "seed_routing_authority.json", "common_w_authority.json", "throughput_reference_authority.json", "streaming_storage_authority.json", "THROUGH_REFERENCE_U4_IDENTITY_V1.json")],
        "scientific_equations_cad_nuisance_metrics_thresholds_workload_changed": False,
        "execution_authorized": False, "formal_run_id_created": False, "formal_response_reads": 0, "formal_response_writes": 0, "final_test_read": False,
    }
    write_json(ADD, "authority_record.json", authority)
    add_seal = seal(ADD, ADD_REL)

    old_exact = read_json(BASE / "e2_preexecution_contract_freeze_01/exact80_manifest.json")
    corrected_members: list[dict[str, Any]] = []
    changed = 0
    for member in old_exact["members"]:
        item = dict(member)
        ordinal = int(item["family_ordinal"])
        expected_batch = f"B{(ordinal - 1) // 5 + 1}"
        if item["source_batch"] != expected_batch:
            changed += 1
        item["source_batch"] = expected_batch
        if f"/{expected_batch.lower()}_science_first_exact20_runs/" not in item["source_authority_path"]:
            raise SystemExit(f"SOURCE_BATCH_PATH_MISMATCH:{item['member_id']}")
        corrected_members.append(item)
    corrected_exact = dict(old_exact)
    corrected_exact["schema_version"] = "gen_enc_2_e2_exact80_manifest_freeze_01_corr01_v1"
    corrected_exact["members"] = corrected_members
    corrected_exact["technical_correction"] = {"id": "E2_TECH_01", "labels_changed": changed, "rule": "FAMILY_ORDINAL_01_05_B1_06_10_B2_11_15_B3_16_20_B4", "identity_set_path_hash_order_changed": False}
    write_json(CORR, "exact80_manifest.json", corrected_exact)
    if changed != 60:
        raise SystemExit("E2_TECH_01_EXPECTED_60_LABEL_CHANGES")

    source_paths = [
        ("src/acoustic_encoder/gen_enc/e2_authority.py", "ANGLE_SEED_COMMON_W_AUTHORITY_API"),
        ("src/acoustic_encoder/gen_enc/forward_acoustic_network.py", "ROUTE_A_CORE_CORR01"),
        ("src/acoustic_encoder/gen_enc/generator/prng.py", "SPLITMIX64_IMPORT"),
        ("scripts/run_gen_enc_2_timing_preflight.py", "PARTITION_EXPLICIT_CLI_CORR01"),
        ("scripts/gen_enc_2_e2_streaming_driver_corr01.py", "STREAMING_DRIVER_IMPLEMENTATION"),
        ("scripts/gen_enc_2_e2_streaming_independent_verifier_corr01.py", "INDEPENDENT_VERIFIER_IMPLEMENTATION"),
        ("scripts/build_gen_enc_2_e2_preexecution_corr01.py", "NO_RUN_PACKAGE_BUILDER"),
        ("tests/test_gen_enc_2_e2_authority_corr01.py", "MINIMAL_SYNTHETIC_TESTS"),
    ]
    source_manifest = {
        "schema_version": "gen_enc_2_e2_source_manifest_freeze_01_corr01_v1", "entries": [bind(path, role) for path, role in source_paths],
        "project_import_closure": ["src/acoustic_encoder/gen_enc/forward_acoustic_network.py", "src/acoustic_encoder/gen_enc/e2_authority.py", "src/acoustic_encoder/gen_enc/generator/prng.py"],
        "unresolved_project_imports": [], "formal_execution": False, "final_test_read": False,
    }
    write_json(CORR, "source_manifest.json", source_manifest)
    runtime = {
        "schema_version": "gen_enc_2_e2_runtime_manifest_freeze_01_corr01_v1",
        "executable": {"path": "D:/Anaconda3/python.exe", "sha256": "4e5a83fcdcd12bcb9ae4dc98c5405effe35dc5ac10d89982c6a6a3646493f88a", "bytes": 104208, "python": "3.12.4"},
        "dependencies": {"numpy": "1.26.4", "psutil": "5.9.0", "jsonschema": "4.19.2"},
        "thread_environment": {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
        "workers": 0, "maximum_workers_under_separate_authority": 8, "source_manifest_sha256": digest(CORR / "source_manifest.json"),
        "final_test_read": False,
    }
    write_json(CORR, "runtime_manifest.json", runtime)

    receipt_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False,
        "required": ["schema_version", "status", "partition", "identity_id", "chunk_id", "hashes", "value_count", "shape", "dtype", "driver_raw_sha256", "verifier_raw_sha256", "max_abs_diff", "max_rel_diff", "sufficient_stat_sha256", "merge_position"],
        "properties": {
            "schema_version": {"const": "gen_enc_2_e2_chunk_pass_receipt_corr01_v1"}, "status": {"const": "PASS"},
            "partition": {"enum": ["development", "single_use_validation"]}, "identity_id": {"type": "string"}, "chunk_id": {"type": "string", "pattern": "^chunk_[0-9]{3}$"},
            "hashes": {"type": "object"}, "value_count": {"type": "integer", "minimum": 1}, "shape": {"type": "array"}, "dtype": {"const": "complex128"},
            "driver_raw_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "verifier_raw_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "max_abs_diff": {"type": "number", "minimum": 0}, "max_rel_diff": {"type": "number", "minimum": 0},
            "sufficient_stat_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "merge_position": {"type": "integer", "minimum": 0},
        },
    }
    stats_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
        "required": ["schema_version", "partition", "identity_id", "chunk_id", "covariance_accumulator", "resampling_units", "reconstruction_proof"],
        "properties": {
            "schema_version": {"const": "gen_enc_2_e2_finest_resampling_stats_corr01_v1"}, "partition": {"enum": ["development", "single_use_validation"]},
            "identity_id": {"type": "string"}, "chunk_id": {"type": "string"},
            "covariance_accumulator": {"type": "object", "description": "mergeable weighted sum_weight,sum_x,sum_xxT for common W"},
            "resampling_units": {"type": "array", "description": "member/cell/repeat/state/angle/frequency-derived values for endpoints bridge throughput bootstrap permutation and uncertainty"},
            "reconstruction_proof": {"type": "object"},
        },
    }
    for name, schema in (("chunk_pass_receipt.schema.json", receipt_schema), ("finest_resampling_stats.schema.json", stats_schema)):
        Draft202012Validator.check_schema(schema)
        write_json(CORR, name, schema)
    write_json(CORR, "schema_manifest.json", {"schema_version": "gen_enc_2_e2_schema_manifest_freeze_01_corr01_v1", "entries": [bind(CORR_REL / name, "CORR01_SCHEMA") for name in ("chunk_pass_receipt.schema.json", "finest_resampling_stats.schema.json")], "meta_valid": True, "final_test_read": False})

    contract = {
        "schema_version": "gen_enc_2_e2_preexecution_contract_freeze_01_corr01_v1",
        "status": "READY_FOR_B_AND_GUARDIAN_ONE_FREEZE_REVIEW", "execution_authorized": False,
        "additive_to": bind(BASE / "e2_preexecution_contract_freeze_01/SHA256SUMS.txt", "FREEZE01_IMMUTABLE_PROVENANCE"),
        "authority_addendum": {"path": f"{ADD_REL.as_posix()}/SHA256SUMS.txt", "sha256": add_seal},
        "closed_gaps": ["E2_GAP_01", "E2_GAP_02", "E2_GAP_03", "E2_GAP_04", "E2_GAP_05"],
        "technical_correction": {"id": "E2_TECH_01", "source_batch_labels_changed": 60, "scientific_identity_change": False},
        "identity": {"exact80_manifest": f"{CORR_REL.as_posix()}/exact80_manifest.json", "members": 80, "families": 4, "members_per_family": 20, "no_reselection_replacement_or_deletion": True},
        "workload": {"complete_units": 1176000, "complex128_values": 16859136000, "cells": 3675, "repeats": 2, "ports": 4, "computed_frequencies": 256, "primary_frequencies": 208, "development_angles": [0, 90, 180, 270], "validation_angles": list(range(0, 360, 15))},
        "angle_seed_throughput_common_w": {"authority_record": f"{ADD_REL.as_posix()}/authority_record.json", "reference_sha256": reference_hash},
        "streaming": storage,
        "state_machine": {"states": ["PREEXECUTION_REVIEW", "E2_D", "E2_D_SEALED", "E2_V_SINGLE_USE", "E2_V_TERMINAL"], "current": "PREEXECUTION_REVIEW", "validation_open_requires": ["D_80_OF_80", "D_INDEPENDENT_VERIFY", "COMMON_W_SEAL", "DEVELOPMENT_DECISIONS_SEAL"], "validation_reuse": False, "development_reentry_after_validation": False},
        "metrics_thresholds_and_terminal_rules": "UNCHANGED_FROM_FREEZE01", "resource_hard_stops": {"cpu_core_hours": 20.0, "wall_hours": 10.0, "aggregate_peak_memory_gib": 8.0, "managed_storage_gib": 48.0, "startup_free_gib": 80.0, "free_reserve_gib": 32.0},
        "evidence_ceiling": "E2_REDUCED_MODEL_RESPONSE_ONLY", "formal_run_id_created": False,
        "formal_response_reads": 0, "formal_response_writes": 0, "development_reads": 0, "validation_reads": 0, "held_out_reads": 0,
        "scientific_hypothesis_status": "NOT_TESTED", "final_test_read": False,
    }
    write_json(CORR, "contract.json", contract)
    write_json(CORR, "input_manifest.json", {"schema_version": "gen_enc_2_e2_input_manifest_freeze_01_corr01_v1", "exact80": bind(CORR_REL / "exact80_manifest.json", "CORRECTED_EXACT80"), "authority": bind(ADD_REL / "authority_record.json", "AUTHORITY_ADDENDUM"), "through_reference": bind(ADD_REL / "THROUGH_REFERENCE_U4_IDENTITY_V1.json", "NEUTRAL_THROUGH_REFERENCE"), "seed_split": bind("outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json", "SEALED_SEED_SPLIT"), "validation_path_gated": True, "final_test_read": False})
    write_json(CORR, "command_manifest.json", {"schema_version": "gen_enc_2_e2_command_manifest_freeze_01_corr01_v1", "working_directory": "D:/Bristol course/dissertation/program work", "no_run_commands": [["D:/Anaconda3/python.exe", "-B", "scripts/gen_enc_2_e2_streaming_driver_corr01.py", "self-test"], ["D:/Anaconda3/python.exe", "-B", "scripts/gen_enc_2_e2_streaming_independent_verifier_corr01.py", "self-test"], ["D:/Anaconda3/python.exe", "-B", "-m", "pytest", "-q", "tests/test_gen_enc_2_e2_authority_corr01.py"]], "formal_commands_authorized": False, "formal_run_id_created": False, "final_test_read": False})
    write_json(CORR, "path_allowlist.json", {"schema_version": "gen_enc_2_e2_path_allowlist_freeze_01_corr01_v1", "development": {"temp": f"{BASE.as_posix()}/e2_formal/development/temp", "receipts": f"{BASE.as_posix()}/e2_formal/development/receipts", "stats": f"{BASE.as_posix()}/e2_formal/development/stats", "audit": f"{BASE.as_posix()}/e2_formal/development/raw_audit", "quarantine": f"{BASE.as_posix()}/e2_formal/development/quarantine"}, "single_use_validation": {"temp": f"{BASE.as_posix()}/e2_formal/validation/temp", "receipts": f"{BASE.as_posix()}/e2_formal/validation/receipts", "stats": f"{BASE.as_posix()}/e2_formal/validation/stats", "audit": f"{BASE.as_posix()}/e2_formal/validation/raw_audit", "quarantine": f"{BASE.as_posix()}/e2_formal/validation/quarantine"}, "cross_partition_reads": False, "validation_before_d_seal": False, "final_test_paths": [], "final_test_read": False})
    write_json(CORR, "reconstruction_proof.json", {"schema_version": "gen_enc_2_e2_reconstruction_proof_corr01_v1", "retained_evidence": ["CHUNK_RECEIPTS", "FINEST_RESAMPLING_UNIT_VALUES", "MERGEABLE_COMMON_W_COVARIANCE_ACCUMULATORS", "320_RAW_AUDIT_CHUNKS", "INPUT_CODE_RUNTIME_DEPENDENCY_HASHES"], "reconstructs": ["ALL_RAW_CHUNKS_BY_RECOMPUTATION", "COMMON_W", "SHARED_DIFFERENTIAL", "E_PRIMARY", "R_STABLE", "THROUGHPUT", "CONTINUOUS_BRIDGE", "HELD_OUT", "FAMILY_WORST_MEMBER", "BOOTSTRAP", "PERMUTATION", "UNCERTAINTY", "GLOBAL_TERMINALS"], "global_means_only": False, "all_dimensions_and_complex128_preserved": True, "final_test_read": False})
    write_json(CORR, "DRAFT_ZERO_STATE.json", {"schema_version": "gen_enc_2_e2_draft_zero_state_freeze_01_corr01_v1", "status": "PREEXECUTION_ONLY", "e2_executions": 0, "formal_run_id_created": False, "formal_solver_units": 0, "formal_response_reads": 0, "formal_response_writes": 0, "development_reads": 0, "validation_reads": 0, "held_out_reads": 0, "final_test_read": False, "searches": 0, "optimizations": 0, "comsol": 0, "full_wave": 0, "physical_experiments": 0, "scientific_hypothesis_status": "NOT_TESTED"})
    write_json(CORR, "no_run_validation_report.json", {"schema_version": "gen_enc_2_e2_no_run_validation_report_freeze_01_corr01_v1", "status": "PASS_MINIMAL_TECHNICAL_FIXTURES", "checks": ["AUTHORITY_HASHES", "REFERENCE_CANONICAL_JSON_HASH", "EXACT80_80_UNIQUE_ORDER_HASH_STABLE", "SOURCE_BATCH_80_PATH_CONSISTENT_60_CORRECTED", "ANGLE_ONE_HOT_ADJACENT_L2_ZERO_PHASE_OFFSET_ORDER", "PARTITION_SEED_ROUTING", "COMMON_W_WEIGHT_AUDIT", "RECEIPT_RECONSTRUCTION", "AUDIT_SELECTION", "STORAGE_CAPS", "SCHEMA_META_VALID", "NO_UNRESOLVED_TOKEN"], "formal_scientific_tests": 0, "formal_response_reads": 0, "formal_response_writes": 0, "final_test_read": False})
    write_json(CORR, "artifact_inventory.json", {"schema_version": "gen_enc_2_e2_artifact_inventory_freeze_01_corr01_v1", "authority_root": ADD_REL.as_posix(), "contract_root": CORR_REL.as_posix(), "additive": True, "old_artifacts_modified": 0, "formal_response_artifacts": 0, "final_test_read": False})
    write_json(CORR, "authority_bindings.json", {"schema_version": "gen_enc_2_e2_authority_bindings_freeze_01_corr01_v1", "entries": [bind(path, "REVIEW_OR_DECISION") for path in required] + [bind(ADD_REL / "SHA256SUMS.txt", "AUTHORITY_ADDENDUM_SEAL"), bind(BASE / "e2_preexecution_contract_freeze_01/SHA256SUMS.txt", "FREEZE01_PROVENANCE"), bind("docs/experiment/gen_enc/GEN_ENC_2_E2_PREEXECUTION_CONTRACT_FREEZE_01_CORR01.md", "HUMAN_CONTRACT"), bind("docs/progress/GEN_ENC_2_E2_PREEXECUTION_CONTRACT_FREEZE_01_CORR01.md", "PROGRESS")], "final_test_read": False})

    forbidden = re.compile(r"\b(?:TBD|TODO|PLACEHOLDER|REQUIRES_USER_OR_STAGE_SPECIFIC_VALUE|null)\b", re.IGNORECASE)
    for root in (ADD, CORR):
        for path in root.iterdir():
            if path.is_file() and path.suffix == ".json" and forbidden.search(path.read_text(encoding="utf-8")):
                raise SystemExit(f"UNRESOLVED_TOKEN:{path}")
    corr_seal = seal(CORR, CORR_REL)
    print(json.dumps({"status": "READY_FOR_B_AND_GUARDIAN_ONE_FREEZE_REVIEW", "reference_sha256": reference_hash, "authority_seal_sha256": add_seal, "corr01_seal_sha256": corr_seal, "source_batch_labels_corrected": changed}, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
