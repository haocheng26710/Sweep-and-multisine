"""Build the additive repair-01 strict JSON Schemas (development freeze tool)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TASK = "01a049a7-15ca-79e1-92a2-d3822ba8609d"
REPAIR = "PRE-RELEASE-REPAIR-01"
CLAIM = "BATCH_LOCAL_IDENTITY_COMPLETE_CAD_STATIC_AND_TECHNICAL_VALIDITY_ONLY"
HEX = {"type": "string", "pattern": "^[0-9a-f]{64}$"}


def obj(required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "required": required, "properties": properties, "additionalProperties": False}


def arr(items: Any, lo: int, hi: int | None = None) -> dict[str, Any]:
    return {"type": "array", "items": items, "minItems": lo, "maxItems": lo if hi is None else hi}


def base(version: str, kind: Any, extra: dict[str, Any], required: list[str]) -> dict[str, Any]:
    props = {"schema_version": {"const": version}, "record_kind": kind if isinstance(kind, dict) else {"const": kind}, "repair_id": {"const": REPAIR}, "task_id": {"const": TASK}, "batch_id": {"const": "B1"}, **extra}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **obj(["schema_version", "record_kind", "repair_id", "task_id", "batch_id", *required], props)}


def common_tail() -> dict[str, Any]:
    return {"claim_ceiling": {"const": CLAIM}, "final_test_read": {"const": False}}


def member() -> dict[str, Any]:
    number = {"type": "number"}; nonnegative = {"type": "number", "minimum": 0}
    root_trace = obj(["iteration", "low_m", "high_m", "mid_m", "measured_volume_m3"], {"iteration": {"type": "integer", "minimum": 1, "maximum": 80}, "low_m": number, "high_m": number, "mid_m": number, "measured_volume_m3": nonnegative})
    root = obj(["sector", "initial_bracket_m", "final_bracket_m", "iterations", "trace", "root_length_m", "target_volume_m3", "measured_volume_m3", "residual_m3"], {"sector": {"enum": ["0", "90", "180", "270"]}, "initial_bracket_m": arr(number, 2), "final_bracket_m": arr(number, 2), "iterations": {"const": 80}, "trace": arr(root_trace, 80), "root_length_m": nonnegative, "target_volume_m3": nonnegative, "measured_volume_m3": nonnegative, "residual_m3": number})
    candidate = obj(["witness_id", "measured_m"], {"witness_id": {"type": "string", "minLength": 1}, "measured_m": nonnegative})
    edge = obj(["edge_id", "a", "b", "weight", "active"], {"edge_id": {"type": "string", "minLength": 1}, "a": {"type": "string", "minLength": 1}, "b": {"type": "string", "minLength": 1}, "weight": number, "active": {"type": "boolean"}})
    fluid_edge = obj(["edge_id", "a", "b", "weight", "positive_area_m2"], {"edge_id": {"type": "string", "minLength": 1}, "a": {"type": "string", "minLength": 1}, "b": {"type": "string", "minLength": 1}, "weight": {"type": "number", "exclusiveMinimum": 0}, "positive_area_m2": {"type": "number", "exclusiveMinimum": 0}})
    source = obj(["purpose", "path", "sha256", "pointer", "object_sha256", "leaf_count", "leaf_manifest_sha256"], {"purpose": {"type": "string", "pattern": "^CAD0_MULTI_SOURCE_(0[1-9]|1[0-3])$"}, "path": {"type": "string", "minLength": 1}, "sha256": HEX, "pointer": {"type": "string"}, "object_sha256": HEX, "leaf_count": {"type": "integer", "minimum": 1}, "leaf_manifest_sha256": HEX})
    part = obj(["purpose", "pointer", "value_sha256", "leaf_count", "leaf_manifest_sha256"], {"purpose": {"type": "string", "pattern": "^CAD0_MULTI_SOURCE_(0[1-9]|1[0-3])$"}, "pointer": {"type": "string"}, "value_sha256": HEX, "leaf_count": {"type": "integer", "minimum": 1}, "leaf_manifest_sha256": HEX})
    section = obj(["name", "parts", "section_sha256"], {"name": {"type": "string", "minLength": 1}, "parts": arr(part, 1, 32), "section_sha256": HEX})
    authority = obj(["schema_version", "sources", "sections", "source_count", "leaf_count", "all_leaf_manifest_sha256", "model_sha256"], {"schema_version": {"const": "gen_enc_fast_b1_repair_01_cad_authority_model_v1"}, "sources": arr(source, 13), "sections": arr(section, 1, 32), "source_count": {"const": 13}, "leaf_count": {"type": "integer", "minimum": 13}, "all_leaf_manifest_sha256": HEX, "model_sha256": HEX})
    cad = obj(["schema_version", "ownership_cells", "slot_placements", "volume_root_witnesses", "u4_exception_witnesses", "general_minima", "exception_minima", "reduced_graph", "actual_fluid_graph", "random_zero_edge_witnesses", "thresholds", "thresholds_copied_as_measurements", "complete_witness_semantics", "authority_binding"], {
        "schema_version": {"const": "gen_enc_fast_b1_repair_01_member_cad_static_v1"},
        "ownership_cells": arr(obj(["cell_id", "owner", "rule", "positive_overlap_volume_m3"], {"cell_id": {"type": "string", "minLength": 1}, "owner": {"type": "string", "minLength": 1}, "rule": {"type": "string", "minLength": 1}, "positive_overlap_volume_m3": nonnegative}), 5),
        "slot_placements": arr(obj(["slot_id", "sector", "owner_cell_id", "coordinates_m", "placement_status", "width_m"], {"slot_id": {"type": "string", "minLength": 1}, "sector": {"enum": ["0", "90", "180", "270"]}, "owner_cell_id": {"type": "string", "minLength": 1}, "coordinates_m": arr(number, 3), "placement_status": {"const": "PLACED_OR_EXPLICIT_ZERO"}, "width_m": nonnegative}), 20),
        "volume_root_witnesses": arr(root, 4),
        "u4_exception_witnesses": arr(obj(["exception_id", "sector", "local_coordinates_m", "feature_m", "load_path_m", "participation", "excluded_only_from"], {"exception_id": {"type": "string", "pattern": "^IFX_U4_[0-9]{3}_[A-Z_]+$"}, "sector": {"enum": ["0", "90", "180", "270"]}, "local_coordinates_m": arr(number, 2), "feature_m": nonnegative, "load_path_m": nonnegative, "participation": {"const": "U4_INTERFACE_EXCEPTION_ONLY"}, "excluded_only_from": {"const": "GENERAL_MINIMA"}}), 20),
        "general_minima": obj(["feature_candidates", "load_path_candidates", "measured_minimum_feature_m", "measured_minimum_load_path_m", "feature_witness_ids", "load_path_witness_ids"], {"feature_candidates": arr(candidate, 6), "load_path_candidates": arr(candidate, 2), "measured_minimum_feature_m": nonnegative, "measured_minimum_load_path_m": nonnegative, "feature_witness_ids": arr({"type": "string", "minLength": 1}, 2), "load_path_witness_ids": arr({"type": "string", "minLength": 1}, 2)}),
        "exception_minima": obj(["measured_minimum_feature_m", "measured_minimum_load_path_m", "exception_ids"], {"measured_minimum_feature_m": nonnegative, "measured_minimum_load_path_m": nonnegative, "exception_ids": arr({"type": "string", "minLength": 1}, 20)}),
        "reduced_graph": obj(["nodes", "edges", "component_count"], {"nodes": arr({"type": "string", "minLength": 1}, 4), "edges": arr(edge, 6), "component_count": {"type": "integer", "minimum": 1, "maximum": 4}}),
        "actual_fluid_graph": obj(["nodes", "edges", "component_count"], {"nodes": arr({"type": "string", "minLength": 1}, 5), "edges": arr(fluid_edge, 4), "component_count": {"const": 1}}),
        "random_zero_edge_witnesses": arr(obj(["edge_id", "exact_value", "generator_branch", "verified_exact_zero"], {"edge_id": {"type": "string", "minLength": 1}, "exact_value": {"const": 0.0}, "generator_branch": {"const": "U_LT_0P5_ATOM"}, "verified_exact_zero": {"const": True}}), 0, 6),
        "thresholds": obj(["minimum_general_feature_m", "minimum_general_load_path_m"], {"minimum_general_feature_m": {"const": .002}, "minimum_general_load_path_m": {"const": .0016}}), "thresholds_copied_as_measurements": {"const": False}, "complete_witness_semantics": {"const": True}, "authority_binding": authority})
    provenance = {"oneOf": [obj(["kind", "row_index_zero_based"], {"kind": {"const": "SEALED_ROW"}, "row_index_zero_based": {"type": "integer", "minimum": 0, "maximum": 4}}), obj(["kind", "member_seed", "seed_index_zero_based", "draw_count", "nextafter_guard", "spec_sha256"], {"kind": {"const": "RANDOM_FIXED_MEMBER_SEED"}, "member_seed": {"type": "integer"}, "seed_index_zero_based": {"type": "integer", "minimum": 0, "maximum": 4}, "draw_count": {"const": 13}, "nextafter_guard": {"const": True}, "spec_sha256": HEX}), obj(["kind", "master_seed", "member_identity_seed", "seed_index_zero_based", "lhs_jitter", "spec_sha256"], {"kind": {"const": "PHYSICS_FISHER_YATES_MIDPOINT_LHS"}, "master_seed": {"type": "integer"}, "member_identity_seed": {"type": "integer"}, "seed_index_zero_based": {"type": "integer", "minimum": 0, "maximum": 4}, "lhs_jitter": {"const": False}, "spec_sha256": HEX})]}
    extra = {"family_id": {"enum": ["HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED"]}, "member_id": {"pattern": "^(HAND|NEAR|RANDOM|PHYSICS)_0[1-5]$"}, "slot_ordinal": {"type": "integer", "minimum": 1, "maximum": 5}, "failure_slot_retained": {"const": True}, "input_provenance": provenance, "parameter_order": arr({"type": "string", "minLength": 1}, 1, 20), "parameters": {"type": "object", "minProperties": 1, "additionalProperties": number}, "cad_static_evidence": cad, "static_status": {"enum": ["ELIGIBLE", "COST_INELIGIBLE", "TEMPLATE_VALIDITY_REJECTED", "FAIL_CLOSED"]}, **common_tail(), "scientific_hypothesis_status": {"const": "NOT_TESTED"}}
    return base("gen_enc_fast_b1_repair_01_member_identity_v1", "BATCH_LOCAL_MEMBER_IDENTITY_COMPLETE_AUTHORITY_DERIVED_CAD_STATIC", extra, list(extra))


def simple_schemas() -> dict[str, Any]:
    tail = common_tail()
    entry = obj(["member_id", "path", "sha256", "static_status", "failure_slot_retained"], {"member_id": {"pattern": "^(HAND|NEAR|RANDOM|PHYSICS)_0[1-5]$"}, "path": {"type": "string", "minLength": 1}, "sha256": HEX, "static_status": {"enum": ["ELIGIBLE", "COST_INELIGIBLE", "TEMPLATE_VALIDITY_REJECTED", "FAIL_CLOSED"]}, "failure_slot_retained": {"const": True}})
    out: dict[str, Any] = {}
    out["partial_family_manifest"] = base("gen_enc_fast_b1_repair_01_partial_family_manifest_v1", "PARTIAL_FAMILY_MANIFEST_EXACTLY_5_OF_20", {"family_id": {"enum": ["HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED"]}, "slot_ordinals": {"const": [1, 2, 3, 4, 5]}, "member_entries": arr(entry, 5), "complete_family_manifest": {"const": False}, **tail}, ["family_id", "slot_ordinals", "member_entries", "complete_family_manifest", *tail])
    counts = obj(["ELIGIBLE", "COST_INELIGIBLE", "TEMPLATE_VALIDITY_REJECTED", "FAIL_CLOSED"], {x: {"type": "integer", "minimum": 0, "maximum": 20} for x in ("ELIGIBLE", "COST_INELIGIBLE", "TEMPLATE_VALIDITY_REJECTED", "FAIL_CLOSED")})
    out["static_audit"] = base("gen_enc_fast_b1_repair_01_static_audit_v1", "COMPLETE_BATCH_LOCAL_STATIC_AUDIT_20", {"member_paths": arr({"type": "string", "minLength": 1}, 20), "member_count": {"const": 20}, "complete_cad_witness_count": {"const": 20}, "failed_slots_retained": {"const": True}, "status_counts": counts, **tail}, ["member_paths", "member_count", "complete_cad_witness_count", "failed_slots_retained", "status_counts", *tail])
    out["independent_verification"] = base("gen_enc_fast_b1_repair_01_independent_verification_v1", "INDEPENDENT_VERIFICATION", {"run_id": HEX, "status": {"enum": ["PENDING_NON_SUCCESS", "PASS", "FAIL_CLOSED"]}, "verified_member_count": {"type": "integer", "minimum": 0, "maximum": 20}, "verified_manifest_count": {"type": "integer", "minimum": 0, "maximum": 4}, "authority_read_count": {"type": "integer", "minimum": 0, "maximum": 20}, "artifact_count": {"type": "integer", "minimum": 0, "maximum": 31}, "checks": arr({"type": "string", "minLength": 1}, 0, 32), "resealed": {"type": "boolean"}, **tail}, ["run_id", "status", "verified_member_count", "verified_manifest_count", "authority_read_count", "artifact_count", "checks", "resealed", *tail])
    paths = {"member_paths": arr({"type": "string"}, 20), "partial_manifest_paths": arr({"type": "string"}, 4)}
    out["batch_index"] = base("gen_enc_fast_b1_repair_01_batch_index_v1", "B1_BATCH_INDEX_NON_FINAL", {"run_id": HEX, **{x: HEX for x in ("authority_allowlist_sha256", "source_manifest_sha256", "schema_manifest_sha256", "command_manifest_sha256")}, **paths, "static_audit_path": {"const": "static_audit.json"}, "independent_verification_path": {"const": "independent_verification.json"}, "sha256sums_path": {"const": "SHA256SUMS.txt"}, "generation_terminal_path": {"const": "generation_terminal.json"}, "verifier_terminal_path": {"const": "verifier_terminal.json"}, "publication_terminal_path": {"const": "publication_terminal.json"}, "verification_complete": {"type": "boolean"}, "artifact_cardinality": {"const": 31}, "zero_unlisted_required": {"const": True}, "final_endpoint": {"const": False}, **tail}, ["run_id", "authority_allowlist_sha256", "source_manifest_sha256", "schema_manifest_sha256", "command_manifest_sha256", *paths, "static_audit_path", "independent_verification_path", "sha256sums_path", "generation_terminal_path", "verifier_terminal_path", "publication_terminal_path", "verification_complete", "artifact_cardinality", "zero_unlisted_required", "final_endpoint", *tail])
    out["generation_terminal"] = base("gen_enc_fast_b1_repair_01_generation_terminal_v1", "GENERATION_STAGED_NON_SUCCESS", {"run_id": HEX, "status": {"const": "AWAITING_INDEPENDENT_VERIFICATION"}, "authority_read_count": {"type": "integer", "minimum": 0, "maximum": 20}, "member_count": {"const": 20}, "artifact_count": {"const": 29}, "success_eligible": {"const": False}, "publication_started": {"const": False}, **tail}, ["run_id", "status", "authority_read_count", "member_count", "artifact_count", "success_eligible", "publication_started", *tail])
    out["verifier_terminal"] = base("gen_enc_fast_b1_repair_01_verifier_terminal_v1", "VERIFIED_STAGING_NON_PUBLICATION", {"run_id": HEX, "status": {"const": "VERIFIED_RESEALED_AWAITING_PUBLICATION"}, "authority_read_count": {"type": "integer", "minimum": 0, "maximum": 20}, "verified_member_count": {"const": 20}, "artifact_count": {"const": 31}, "publication_started": {"const": False}, "success_terminal_written": {"const": False}, **tail}, ["run_id", "status", "authority_read_count", "verified_member_count", "artifact_count", "publication_started", "success_terminal_written", *tail])
    out["publication_terminal"] = base("gen_enc_fast_b1_repair_01_publication_terminal_v1", "PUBLICATION_INTENT_NON_SUCCESS", {"run_id": HEX, "status": {"const": "AWAITING_MULTI_TARGET_ATOMIC_PUBLICATION"}, "target_count": {"const": 31}, "published_count": {"type": "integer", "minimum": 0, "maximum": 31}, "commit_pointer_written": {"const": False}, "success_terminal_written": {"const": False}, **tail}, ["run_id", "status", "target_count", "published_count", "commit_pointer_written", "success_terminal_written", *tail])
    honest = obj(["authority_reads", "members", "artifacts", "published"], {x: {"type": "integer", "minimum": 0} for x in ("authority_reads", "members", "artifacts", "published")})
    out["package_terminal"] = base("gen_enc_fast_b1_repair_01_package_terminal_v1", {"enum": ["FAIL_CLOSED", "VERIFIED_SUCCESS"]}, {"run_id": HEX, "release_sha256": HEX, "attestation_sha256": HEX, "status": {"enum": ["TECHNICAL_FAIL_CLOSED", "VERIFIED_SUCCESS"]}, "reason": {"type": "string", "minLength": 1}, "honest_counts": honest, "commit_pointer_sha256": {"anyOf": [HEX, {"type": "null"}]}, "package_terminal_count": {"const": 1}, **tail, "scientific_hypothesis_status": {"const": "NOT_TESTED"}}, ["run_id", "release_sha256", "attestation_sha256", "status", "reason", "honest_counts", "commit_pointer_sha256", "package_terminal_count", *tail, "scientific_hypothesis_status"])
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[2] / "schemas/gen_enc/b1_repair_01"
    root.mkdir(parents=True, exist_ok=True)
    schemas = {"member_identity": member(), **simple_schemas()}
    old = Path(__file__).resolve().parents[2] / "schemas/gen_enc/b1"
    for name in ("draft", "release", "guardian_attestation", "side_record", "journal", "commit_pointer"):
        value = json.loads((old / f"{name}.schema.json").read_text(encoding="utf-8"))
        text = json.dumps(value).replace("gen_enc_fast_b1_", "gen_enc_fast_b1_repair_01_")
        value = json.loads(text)
        value["properties"]["task_id"] = {"const": TASK}
        value["properties"]["repair_id"] = {"const": REPAIR}
        if "repair_id" not in value["required"]: value["required"].insert(3, "repair_id")
        if name == "release":
            for manifest in ("source", "schema", "command"):
                value["properties"][f"{manifest}_manifest_path"] = {"const": f"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_01/{manifest}_manifest.json"}
        if name == "draft":
            value["properties"]["schema_version"] = {"const": "gen_enc_fast_b1_repair_01_draft_v1"}
        schemas[name] = value
    for name, schema in schemas.items():
        (root / f"{name}.schema.json").write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__": main()
