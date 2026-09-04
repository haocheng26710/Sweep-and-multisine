from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs/gen_enc/GEN_ENC_FAST_START/fast_0_authority_batch_contract_freeze"
TASK = "01a0452b-ee9f-7ce0-a671-78d80cb069fe"
TOP = "01a0366d-bb5e-7a13-a1f7-b34403664543"
FAST_TASK = "01a04997-9c83-7b40-84a8-2bf57ccebade"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(rel: str):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def pointer(value, ptr: str):
    if ptr == "":
        return value
    for token in ptr.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def shape(value):
    if isinstance(value, dict):
        result = {"type": "object", "field_count": len(value), "field_names": list(value)}
        for key, child in value.items():
            if isinstance(child, list):
                result.setdefault("array_counts", {})[key] = len(child)
        return result
    if isinstance(value, list):
        result = {"type": "array", "count": len(value)}
        if value and isinstance(value[0], dict):
            result["item_field_names"] = list(value[0])
            result["all_item_field_sets_identical"] = all(set(x) == set(value[0]) for x in value)
        return result
    return {"type": type(value).__name__, "value": value}


def write(name: str, value) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


family = "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/family_design_tables_rev01.json"
manifest = "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/family_identity_manifest_rev01.json"
seeds = "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"
triples = [
    ("HAND_ROWS", family, "/hand_designed/rows"),
    ("NEAR_ROWS", family, "/near_independent/rows"),
    ("RANDOM_FAMILY_SPEC", manifest, "/families/2"),
    ("RANDOM_FIXED_SEEDS", seeds, "/topology_identity_seeds/random_disordered_members"),
    ("PHYSICS_FAMILY_SPEC_PARAMETERS_LHS", manifest, "/families/3"),
    ("PHYSICS_MASTER_SEED", seeds, "/topology_identity_seeds/physics_lhs_master"),
    ("PHYSICS_MEMBER_IDENTITY_SEEDS", seeds, "/topology_identity_seeds/physics_member_identity"),
]
cad_files = [
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev01/authority_source_table.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev01/corrected_geometry_and_z_contract.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev01/ownership_and_algorithms.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev01/root_interval_proof.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev01/slot_ledger.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev01/solid_load_path_algorithm.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev01/connectivity_disclosure_metrics.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev02/authority_source_table.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev02/carry_forward_contract.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev02/constrained_root_proof.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev02/interface_exception_contract.json",
    "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev02/static_audit_fields.json",
    "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_CAD_0_USER_CONFIRMATION_U1_U2_U3.json",
]
for i, path in enumerate(cad_files, 1):
    triples.append((f"CAD0_MULTI_SOURCE_{i:02d}", path, ""))

entries = []
for purpose, path, ptr in triples:
    doc = load(path)
    entries.append({"purpose": purpose, "path": path, "sha256": sha(REPO / path), "pointer": ptr, "object_shape": shape(pointer(doc, ptr)), "formal_authority": True, "technical_fixture": False})

allowlist = {
    "schema_version": "gen_enc_fast_0_exact_authority_allowlist_v1",
    "record_kind": "IMMUTABLE_EXACT_PATH_SHA256_JSON_POINTER_ALLOWLIST",
    "task_id": FAST_TASK,
    "intermediate_controller_task_id": TASK,
    "matching_rule": "EXACT_SET_AND_EXACT_TRIPLE_ONLY_CASE_SENSITIVE_NO_PREFIX_OR_WILDCARD",
    "entry_count": len(entries),
    "entries": entries,
    "technical_fixture_count": 0,
    "arbitrary_triple_accepted": False,
    "final_test_paths_allowed": False,
    "final_test_read": False,
}
write("authority_allowlist.json", allowlist)

all_cad_inventory = []
for folder in ["outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev01", "outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a_rev02"]:
    for path in sorted((REPO / folder).glob("*")):
        if path.is_file():
            all_cad_inventory.append({"path": path.relative_to(REPO).as_posix(), "sha256": sha(path), "content_inspected": path.suffix == ".json"})
read_files = sorted({family, manifest, seeds, *[x["path"] for x in all_cad_inventory], cad_files[-1]})
write("authority_read_log.json", {
    "schema_version": "gen_enc_fast_0_authority_read_log_v1", "authority_inspection_read": True,
    "purpose": "FAST_0_EXACT_BINDING_ADAPTER_AND_MECHANICAL_PROVENANCE_ONLY", "unique_non_final_authority_file_count": len(read_files),
    "files": [{"path": p, "sha256": sha(REPO / p), "final_test": False} for p in read_files],
    "semantic_allowlist_object_count": len(entries), "adapter_conformance_passes_planned": 2,
    "formal_identity_generation": 0, "static_eligibility_run": 0, "simulation_timing_response": 0, "final_test_read": False,
})

cad_provenance = {
    "schema_version": "gen_enc_fast_0_cad_multisource_provenance_v1", "record_kind": "MECHANICAL_COMPOSITE_PROVENANCE_NOT_AUTHORITY",
    "authority_created": False, "new_geometry_constants": 0, "technical_fixture_promoted": False,
    "fields": {
        "geometry_and_z": {"source": entries[8], "pointers": ["/z_intervals_m", "/intentional_interfaces", "/central", "/sector", "/derived_envelopes_m", "/derived_cover_m"], "derivation": "COPY_EXACT_VALUES_ONLY"},
        "ownership_cells": {"source": entries[9], "pointers": ["/transforms", "/ownership", "/clip_order", "/fluid_box_union", "/solid_polyhedral_arrangement"], "derivation": "COPY_ALGORITHM_AND_FUTURE_OUTPUT_FIELDS_ONLY"},
        "volume_root_witnesses": {"sources": [entries[10], entries[16]], "pointers": ["/common", "/families", "/derived_sector_proof", "/independent_sector_proof", "/root_bracket"], "derivation": "DIRECT_MULTI_SOURCE_BINDING_NO_RECOMPUTATION"},
        "slot_placement": {"source": entries[11], "pointers": ["/sector_order", "/slots", "/mapping_by_family_and_sector", "/required_burden_fields"], "derivation": "COPY_EXACT_SLOT_IDS_COORDINATES_AND_MAPPING"},
        "solid_load_path": {"source": entries[12], "pointers": ["/preprocess", "/sheet_identity", "/excluded_pairs", "/eligible_pair", "/metrics"], "derivation": "COPY_FROZEN_ALGORITHM_ONLY"},
        "reduced_and_actual_fluid_graphs": {"source": entries[13], "pointers": ["/D2_A", "/descriptive_only_fields", "/definitions"], "derivation": "COPY_SEPARATE_GRAPH_SEMANTICS"},
        "u4_exceptions": {"source": entries[17], "pointers": ["/collar_common_local_coordinates_m", "/objects", "/counts", "/participation"], "derivation": "EXPAND_4_RIMS_8_COMPONENTS_8_SHOULDERS_TO_20_EXACT_WITNESSES_WITHOUT_NEW_VALUES"},
        "general_and_exception_minima": {"source": entries[18], "pointers": ["/fields", "/fail_rules"], "derivation": "COPY_VALUES_THRESHOLDS_WITNESS_IDS"},
        "approval": {"source": entries[19], "pointers": ["/selections/U1", "/selections/U2", "/selections/U3", "/mandatory_carry_forward"], "derivation": "BIND_USER_CONFIRMED_SEMANTICS"},
    },
    "future_member_evidence_schema": "schemas/gen_enc/fast_0/member_cad_static_evidence.schema.json",
    "required_complete_fields": ["ownership_cells", "slot_placements", "volume_root_witnesses", "all_20_u4_exception_ids_and_coordinates", "general_minima", "exception_minima", "reduced_graph", "actual_fluid_graph", "random_zero_edge_witnesses"],
    "final_test_read": False,
}
write("cad_multisource_provenance.json", cad_provenance)

families = ["HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED"]
batches = []
for n in range(4):
    ordinals = list(range(n * 5 + 1, n * 5 + 6))
    slots = [{"family_id": f, "slot_ordinal": i, "slot_id": ({"HAND_DESIGNED": "HAND", "NEAR_INDEPENDENT": "NEAR", "FIXED_SEED_RANDOM_DISORDERED": "RANDOM", "PHYSICS_METAMATERIAL_INSPIRED": "PHYSICS"}[f] + f"_{i:02d}"), "failure_slot_retained": True} for f in families for i in ordinals]
    batches.append({"batch_id": f"B{n+1}", "family_ordinals": ordinals, "member_count": 20, "members": slots, "cumulative_member_count": (n + 1) * 20, "completed": [], "remaining": ["formal_identity_generation", "complete_CAD_static_evidence", "independent_verification", "atomic_commit"], "evidence_ceiling": "STAGED_IDENTITY_AND_TECHNICAL_VALIDITY_ONLY", "reentry_condition": "PRIOR_CHECKPOINT_AND_DISTINCT_ACCEPTED_TASK_BOUND_RELEASE_ATTESTATION"})
write("four_batch_ledger.json", {"schema_version": "gen_enc_fast_0_four_batch_ledger_v1", "selection_rule": "FROZEN_ORDINAL_ORDER_NO_REDRAW_REPAIR_REPLACEMENT_REORDER_RESULT_FILTER", "batches": batches, "union_member_count": 80, "overlap_count": 0, "failed_slots_retained": True, "integration_order": ["B1", "B2", "B3", "B4"], "final_integration_obligations": {"scientific_objects": 85, "result_objects": 6, "progress_objects": 1, "total": 92, "complete_80_of_80_required": True}, "formal_execution_authorized": False, "final_test_read": False})

write("batch_publication_contract.json", {
    "schema_version": "gen_enc_fast_0_batch_publication_contract_v1", "record_kind": "FUTURE_MINIMUM_BATCH_PUBLICATION_CONTRACT",
    "run_directory": "ONE_NEW_EMPTY_IMMUTABLE_MUTUALLY_EXCLUSIVE_DIRECTORY_PER_BATCH_AND_RUN_ID", "contents": {"identity_objects": 20, "partial_family_manifests": 4, "batch_index": 1, "static_audit": 1, "independent_verification": 1, "sha256sums": 1, "terminal": 1},
    "partial_schema": "schemas/gen_enc/fast_0/partial_family_manifest.schema.json", "index_schema": "schemas/gen_enc/fast_0/batch_index.schema.json", "static_audit_schema": "schemas/gen_enc/fast_0/batch_static_audit.schema.json", "independent_verification_schema": "schemas/gen_enc/fast_0/independent_verification.schema.json", "terminal_schema": "schemas/gen_enc/fast_0/terminal.schema.json", "commit_pointer_schema": "schemas/gen_enc/fast_0/atomic_commit_pointer.schema.json", "release_side_record_schema": "schemas/gen_enc/fast_0/release_side_record.schema.json",
    "atomic_commit": "SINGLE_TARGET_POINTER_WRITTEN_ONLY_AFTER_ALL_BYTES_HASHED_SCHEMA_VALIDATED_AND_INDEPENDENTLY_VERIFIED",
    "single_terminal": "EXACTLY_ONE_OF_VERIFIED_SUCCESS_OR_FAIL_CLOSED_SCHEMA_VALIDATED_ATOMIC_NO_MIXED_TERMINAL",
    "crash_recovery": {"intent_before_replace": True, "real_subprocess_termination_test_required": True, "temp_path": "EXACT_TARGET_DERIVED_SAME_PARENT", "ownership_token": "SHA256_CANONICAL_RUN_ID_INDEX_ABSOLUTE_TARGET", "recompute_before_delete": True, "containment_reparse_recheck": True},
    "release_side_record": {"immutable": True, "one_use": True, "states": ["ISSUED", "CONSUMED", "REVOKED"], "binds": ["task_id", "batch_id", "run_id", "release_sha256", "attestation_sha256", "allowlist_sha256", "source_manifest_sha256", "schema_manifest_sha256", "command", "mode", "roots"]},
    "batch_is_final_92_endpoint": False, "final_80_integration_default": "85_SCIENTIFIC_PLUS_6_RESULT_PLUS_1_PROGRESS", "final_test_read": False,
})
write("b1_start_and_continuation_contract.json", {"schema_version": "gen_enc_fast_0_b1_start_contract_v1", "B1_may_start_now": False, "required_before_B1": ["FAST_0_GUARDIAN_ACCEPT", "DISTINCT_TASK_BOUND_RELEASE_AND_ATTESTATION", "B1_20_SLOTS_FROZEN", "PARTIAL_SCHEMAS_VALID", "BOTH_EXACT_ADAPTERS_PASS", "SINGLE_TERMINAL_PASS", "REAL_SUBPROCESS_CRASH_RECOVERY_PASS", "FORMAL_STATIC_FINAL_TEST_COUNTERS_ZERO"], "after_B1_default": "PROCEED_DIRECTLY_B2_B3_B4_AFTER_IMPLEMENTATION_AND_SEMANTIC_CHECKPOINT", "timing_or_forward_after_B1": False, "timing_reentry": "ONLY_AFTER_COMPLETE_GEN_ENC_2C_RESULT_SEAL_THEN_SEPARATE_TIMING_PREFLIGHT_AND_GEN_ENC_2_CONTRACT", "release_or_attestation_generated_by_FAST_0": False, "final_test_read": False})
write("parallel_boundary.json", {"schema_version": "gen_enc_fast_0_parallel_boundary_v1", "B2_B4_before_B1_checkpoint": False, "B2_B4_parallel_after_B1": True, "conditions": ["one_use_distinct_release_attestation_and_run_id", "mutually_exclusive_roots", "no_shared_mutable_state", "identical_source_and_schema_hashes", "read_only_hash_verified_authority", "fixed_B1_to_B4_integration_order", "failure_cannot_mutate_other_batch"], "semantic_or_invariant_defect_action": "PAUSE_ALL_NOT_YET_COMMITTED_BATCHES", "final_test_read": False})
write("draft_authorization_state.json", {"schema_version": "gen_enc_fast_0_authorization_v1", "record_kind": "DRAFT", "non_authoritative": True, "attempt": 0, "run_id": None, "permissions": {"authority_inspection_read": False, "formal_identity_generation": False, "static_eligibility_run": False, "formal_batch_publication": False, "simulation": False, "timing": False, "response": False, "endpoint": False, "comparison": False, "ranking": False, "selection": False, "optimization": False, "final_test_read": False}, "may_flip_or_promote": False})
write("relates_to.json", {"schema_version": "gen_enc_fast_0_relates_to_v1", "task_id": FAST_TASK, "intermediate_controller_task_id": TASK, "top_level_task_id": TOP, "additive": True, "overrides": False, "historical_corr03_verdict_preserved": "REJECT", "source_paths": ["outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_FAST_START_BATCH_PROPOSAL_REVIEW.json", "outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/stage_integrity_ledger.json", "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2C_S2_CORR03_PREEXECUTION_IMPLEMENTATION_FREEZE_REVIEW.json"], "guardian_contacted": False, "B1_started": False, "final_test_read": False})

source_paths = ["scripts/gen_enc_fast_0/adapter_primary.py", "scripts/gen_enc_fast_0/adapter_independent.py", "scripts/gen_enc_fast_0/authority_gate.py", "scripts/gen_enc_fast_0/technical_transaction.py", "scripts/gen_enc_fast_0/build_freeze.py", "tests/test_gen_enc_fast_0.py"]
schema_paths = sorted(p.relative_to(REPO).as_posix() for p in (REPO / "schemas/gen_enc/fast_0").glob("*.json"))
fixture_paths = sorted(p.relative_to(REPO).as_posix() for p in (REPO / "tests/fixtures/gen_enc_fast_0").glob("*.json"))
write("source_manifest.json", {"schema_version": "gen_enc_fast_0_source_manifest_v1", "files": [{"path": p, "sha256": sha(REPO / p)} for p in source_paths], "adapters_import_each_other": False, "legacy_driver_generator_cad_mapper_imported": False})
write("schema_manifest.json", {"schema_version": "gen_enc_fast_0_schema_manifest_v1", "files": [{"path": p, "sha256": sha(REPO / p)} for p in schema_paths]})
write("fixture_manifest.json", {"schema_version": "gen_enc_fast_0_fixture_manifest_v1", "identity_class": "TECHNICAL_FIXTURE_ONLY", "formal_allowlist_membership": False, "files": [{"path": p, "sha256": sha(REPO / p)} for p in fixture_paths]})
write("execution_state.json", {"schema_version": "gen_enc_fast_0_execution_state_v1", "status": "DRAFT_FROZEN_PENDING_GUARDIAN_REVIEW", "evidence_ceiling": "E1_TECHNICAL_PREEXECUTION_CONTRACT_AND_AUTHORITY_BINDING_ONLY", "authority_inspection_read": True, "formal_identity_generation": 0, "static_eligibility_run": 0, "formal_batch_publication": 0, "simulation": 0, "timing": 0, "response": 0, "endpoint": 0, "comparison_ranking_selection_optimization": 0, "release_created": 0, "attestation_created": 0, "B1_started": False, "scientific_hypothesis_status": "NOT_TESTED", "final_test_state": "SEALED", "final_test_read": False})

residue = []
for base in [REPO / ".tmp", REPO / ".t"]:
    if base.exists():
        for path in sorted(base.rglob("*")):
            if path.is_file():
                residue.append({"path": path.relative_to(REPO).as_posix(), "size": path.stat().st_size})
write("temporary_residue_inventory.json", {"schema_version": "gen_enc_fast_0_temp_residue_inventory_v1", "cleanup_authorized": False, "cleanup_performed": False, "file_count": len(residue), "files": residue})

governance = [
    "outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_FAST_START_BATCH_PROPOSAL_REVIEW.json",
    "outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/stage_integrity_ledger.json",
    "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2C_S2_CORR03_PREEXECUTION_IMPLEMENTATION_FREEZE_REVIEW.json",
]
write("governance_source_hashes.json", {"schema_version": "gen_enc_fast_0_governance_sources_v1", "files": [{"path": p, "sha256": sha(REPO / p)} for p in governance], "corr03_required_sha256_matches": sha(REPO / governance[2]) == "75c56577cc79c81e9aa7960a8f82059193adeb05aedc5f0ba8587eae33eed14c"})

def sums():
    files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
    (OUT / "SHA256SUMS.txt").write_text("".join(f"{sha(p)}  {p.relative_to(OUT).as_posix()}\n" for p in files), encoding="ascii", newline="\n")

sums()
