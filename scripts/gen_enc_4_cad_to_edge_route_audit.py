"""Audit whether GEN-ENC-4 M1 reduced edges have an authorized physical CAD route."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from acoustic_encoder.gen_enc.topology_preserving_network import topology_audit


ROOT = REPO / "outputs/gen_enc/GEN_ENC_4_CAD_TO_EDGE_ROUTE_AUDIT"
BINDINGS = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_a_integration_rev03/authority_bindings.json"
CONFIRMATION = REPO / "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_CAD_0_USER_CONFIRMATION_U1_U2_U3.json"
M2A = REPO / "outputs/gen_enc/GEN_ENC_4_M2A_MECHANISM_PREFLIGHT/result_summary.json"
IDENTITIES = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, value: dict) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    bindings = load(BINDINGS)
    confirmation = load(CONFIRMATION)
    u2 = bindings["approved_cad0_authority"]["U2"]
    bound_confirmation = bindings["approved_cad0_authority"]["user_confirmation"]
    bound_contract = bindings["approved_cad0_authority"]["contract"]
    if digest(CONFIRMATION) != bound_confirmation["sha256"]:
        raise RuntimeError("USER_CONFIRMATION_HASH_MISMATCH")
    if digest(REPO / bound_contract["path"]) != bound_contract["sha256"]:
        raise RuntimeError("CAD0_CONTRACT_HASH_MISMATCH")
    u2_selected = confirmation["selections"]["U2"]["selected_option"]
    if u2_selected != "APPROVE_D2_A_WITH_PERMANENT_SHARED_PLENUM_DISCLOSURE":
        raise RuntimeError("U2_SELECTION_MISMATCH")
    semantic = u2["semantics"]
    required_phrases = ("shared plenum", "Reduced disconnection is descriptive", "actual fluid connectivity")
    if not all(phrase in semantic for phrase in required_phrases):
        raise RuntimeError("U2_SEMANTIC_MISSING")

    representatives = (
        ("HAND_DESIGNED", "HAND_01.identity.json"),
        ("NEAR_INDEPENDENT", "NEAR_01.identity.json"),
        ("FIXED_SEED_RANDOM_DISORDERED", "RANDOM_01.identity.json"),
        ("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json"),
    )
    edge_counts = {}
    for family, filename in representatives:
        member = load(IDENTITIES / family / filename)
        edge_counts[member["member_id"]] = len(topology_audit(member).active_edges)

    audit = {
        "schema_version": "gen_enc_4_cad_to_edge_route_audit_v1",
        "evidence_level": "E1_AUTHORITY_CONSISTENCY_AUDIT_NO_RESPONSE",
        "final_test_read": False,
        "validation_reads": 0,
        "input_sha256": {"authority_bindings": digest(BINDINGS), "user_confirmation": digest(CONFIRMATION), "m2a_summary": digest(M2A)},
        "m1_representative_active_edge_counts": edge_counts,
        "sealed_actual_fluid_topology": {
            "nodes": ["CENTRAL_PLENUM", "SECTOR_0", "SECTOR_90", "SECTOR_180", "SECTOR_270"],
            "positive_area_edges": [["CENTRAL_PLENUM", f"SECTOR_{angle}"] for angle in (0, 90, 180, 270)],
            "direct_sector_to_sector_positive_area_edges": [],
            "component_count": 1,
        },
        "route_candidate_audit": [
            {"candidate": "DIRECT_SECTOR_TO_SECTOR_CHANNEL", "status": "REJECTED", "reason": "NO_AUTHORIZED_POSITIVE_AREA_FACE_OR_CENTERLINE_CONNECTS_ANY_SECTOR_PAIR"},
            {"candidate": "WINDOW_DEPTH_AS_EDGE_PATH_LENGTH", "status": "REJECTED", "reason": "WINDOW_IS_AN_INTRA_SECTOR_2MM_THROTTLING_APERTURE_NOT_AN_ENDPOINT_TO_ENDPOINT_SECTOR_PAIR_ROUTE"},
            {"candidate": "SECTOR_TO_PLENUM_TO_SECTOR_AS_ONE_EDGE", "status": "REJECTED", "reason": "WOULD_DUPLICATE_SHARED_PLENUM_AND_RADIAL_ARM_VOLUME_AND_CHANGE_THE_SEALED_FIVE_NODE_TOPOLOGY"},
        ],
        "terminal_state": "M2_DIRECT_EDGE_PHYSICAL_MAPPING_REJECTED",
        "full_m2_direct_edge_authorized": False,
        "authority_reason": "U2_REDUCED_GRAPH_DESCRIPTIVE_ONLY_AND_CAUSAL_EDGE_CLAIM_REQUIRES_SEPARATE_SPINE_WINDOW_ABLATION",
    }
    write("route_mapping_audit.json", audit)

    m2b = {
        "schema_version": "gen_enc_4_m2b_spine_window_ablation_preexecution_contract_v1",
        "status": "CONTRACT_FROZEN_EXECUTION_NOT_AUTHORIZED",
        "evidence_level": "E0_PREEXECUTION_CONTRACT_ONLY",
        "final_test_read": False,
        "validation_reads": 0,
        "scientific_question": "DO_VARIABLE_WINDOWS_CHANGE_THE_SHARED_PLENUM_TRANSFER_BEYOND_THE_FIXED_SPINE_CONNECTIVITY_FLOOR",
        "physical_graph": audit["sealed_actual_fluid_topology"],
        "comparison_arms": [
            {"id": "CAD_BASELINE", "geometry": "FROZEN_SPINE_PLUS_ACTIVE_WINDOW_SLOTS"},
            {"id": "SPINE_ONLY_ABLATION", "geometry": "FROZEN_SPINE_WITH_ALL_VARIABLE_WINDOWS_DISABLED"},
        ],
        "cost_preservation": "RECOMPUTE_EACH_SECTOR_ROOT_LENGTH_WITH_THE_EXISTING_80_STEP_BISECTION_TO_RESTORE_ITS_FROZEN_Q_VOLUME_TARGET; DO_NOT_ADD_VOLUME_OR_FIT_LENGTH_TO_RESPONSE",
        "prohibited_controls": ["SEAL_FIXED_SPINE", "CREATE_DIRECT_SECTOR_PAIR_DUCT", "INTERPRET_REDUCED_EDGE_AS_PHYSICAL_FACE", "SELECT_PATH_LENGTH_FROM_M2A_OUTPUT", "READ_VALIDATION_OR_FINAL_TEST"],
        "first_execution_scope": {
            "partition": "development",
            "representatives": ["HAND_01", "NEAR_01", "RANDOM_01", "PHYSICS_01"],
            "nuisance_cell_rule": "REUSE_GEN_ENC_4_M2A_EIGHT_HASH_SELECTED_CELLS",
            "repeats": [0, 1],
            "frequency_bins": [0, 207],
            "family_inference": False,
        },
        "preflight_gate": {
            "relative_response_change_median_min": 0.01,
            "mechanism_to_sensor_noise_median_min": 1.0,
            "minimum_representatives_passing": 2,
            "all_cases_passive_reciprocal_finite_required": True,
            "all_baseline_and_ablation_sector_volumes_match_targets_abs_m3": 1e-12,
        },
        "required_before_execution": [
            "PIECEWISE_ACTUAL_FLUID_STAR_ARM_COMPILER_WITH_EXPLICIT_SPINE_WINDOW_COLLECTOR_ROOT_CAVITY_OUTER_STEP_SEGMENTS",
            "VOLUME_AND_POSITIVE_AREA_FACE_AUDIT_FOR_BOTH_ARMS",
            "PASSIVE_RECIPROCAL_CASCADE_REFERENCE_TEST",
            "INDEPENDENT_RESULT_VERIFIER",
        ],
        "entry_gate": "EXECUTE_ONLY_AFTER_ALL_REQUIRED_COMPONENTS_ARE_HASH_FROZEN_AND_STATIC_ABLATION_GEOMETRIES_REMAIN_ELIGIBLE",
        "full_m2_or_m3_authorized": False,
    }
    write("m2b_preexecution_contract.json", m2b)
    print("M2_DIRECT_EDGE_PHYSICAL_MAPPING_REJECTED__M2B_CONTRACT_FROZEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
