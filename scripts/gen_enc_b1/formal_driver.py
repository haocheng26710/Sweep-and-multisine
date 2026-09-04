"""Task-bound FAST-B1 formal driver and crash-safe multi-target publisher.

This module has no technical-fixture CLI.  Tests call the pure object adapter
directly.  Every executable CLI spelling is frozen in command_manifest.json and
must later appear byte-for-byte in the one-use RELEASE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

TASK_ID = "01a049a7-15ca-79e1-92a2-d3822ba8609d"
BATCH_ID = "B1"
FAST0_ALLOWLIST_SHA256 = "49263e3cab9825840284d18a4d628be73d1273bf6940493878bac5da529c958c"
GUARDIAN_REVIEW_SHA256 = "f96a71e850ceaefa9c2267c2641d6307c9c98af38b53aa8ef3893fef5de2c8fd"
FAMILIES = ("HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED")
PREFIX = dict(zip(FAMILIES, ("HAND", "NEAR", "RANDOM", "PHYSICS")))
ORDINALS = (1, 2, 3, 4, 5)
SECTORS = ("0", "90", "180", "270")
RANDOM_ORDER = ("q0", "q90", "q180", "edge_0_90", "edge_0_180", "edge_0_270", "edge_90_180", "edge_90_270", "edge_180_270", "loss_0", "loss_90", "loss_180", "loss_270")
PHYSICS_ORDER = ("q0", "q90", "q180", "external_0", "external_90", "external_180", "external_270", "ring_0_90", "ring_90_180", "ring_180_270", "ring_270_0", "loss_0", "loss_90", "loss_180", "loss_270")
HAND_FIELDS = {"member_id", "volume_logit_0", "volume_logit_90", "volume_logit_180", "derived_volume_logit_270", "external_aperture_fraction_0", "external_aperture_fraction_90", "external_aperture_fraction_180", "external_aperture_fraction_270", "central_mix_aperture_fraction", "loss_fraction_0", "loss_fraction_90", "loss_fraction_180", "loss_fraction_270"}
NEAR_FIELDS = (HAND_FIELDS - {"central_mix_aperture_fraction"}) | {"shared_coupling_alpha"}
MASK64 = (1 << 64) - 1
GAMMA = 0x9E3779B97F4A7C15
ZERO = "0" * 64
CLAIM_CEILING = "BATCH_LOCAL_IDENTITY_COMPLETE_CAD_STATIC_AND_TECHNICAL_VALIDITY_ONLY"
RUN_DOMAIN = b"GEN-ENC-FAST-B1-RUN-ID-v1"
FORBIDDEN_PERMISSIONS = ("timing", "response", "performance", "comparison", "ranking", "selection", "optimization", "matched_cost", "direction", "no_improvement", "simulation", "full_wave", "physical", "final80", "final92", "final_test_read")


class B1Error(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    def check(node: Any) -> None:
        if isinstance(node, float) and (not math.isfinite(node) or (node == 0.0 and math.copysign(1.0, node) < 0)):
            raise B1Error("NON_CANONICAL_NUMBER")
        if isinstance(node, dict):
            if not all(isinstance(k, str) for k in node):
                raise B1Error("NON_STRING_KEY")
            for child in node.values(): check(child)
        elif isinstance(node, list):
            for child in node: check(child)
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"


def sha_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""): digest.update(chunk)
    return digest.hexdigest()


def derive_run_id(release: Mapping[str, Any]) -> str:
    clone = dict(release); clone["run_id"] = ZERO
    return sha_bytes(RUN_DOMAIN + b"\n" + canonical(clone))


def read_canonical_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try: value = json.loads(raw.decode("utf-8"))
    except Exception as exc: raise B1Error("JSON_READ:" + path.name) from exc
    if raw != canonical(value): raise B1Error("NON_CANONICAL_JSON:" + path.name)
    return value, raw


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".atomic.tmp")
    if temp.exists(): raise B1Error("ATOMIC_TEMP_COLLISION")
    try:
        with temp.open("xb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
    except BaseException:
        if temp.is_file(): temp.unlink()
        raise


def atomic_json(path: Path, value: Any) -> None: atomic_bytes(path, canonical(value))


def pointer(document: Any, address: str) -> Any:
    if address == "": return document
    if not address.startswith("/"): raise B1Error("POINTER")
    node = document
    for token in address[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list) and token.isdigit() and int(token) < len(node): node = node[int(token)]
        elif isinstance(node, dict) and token in node: node = node[token]
        else: raise B1Error("POINTER_MISSING")
    return node


def splitmix64(argument: int) -> int:
    z = (argument + GAMMA) & MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


def open_uniform(seed: int, coordinate: int) -> float:
    word = splitmix64((seed + GAMMA * (coordinate + 1)) & MASK64)
    value = ((word >> 11) + 0.5) / (1 << 53)
    return math.nextafter(1.0, 0.0) if value == 1.0 else value


def fisher_yates(master: int, coordinate: int) -> list[int]:
    result = list(range(20))
    for i in range(19, 0, -1):
        address = (master + GAMMA * (1 + 32 * coordinate + (19 - i))) & MASK64
        j = splitmix64(address) % (i + 1)
        result[i], result[j] = result[j], result[i]
    return result


def _row(row: Mapping[str, Any], family: str, ordinal: int) -> dict[str, float]:
    fields = HAND_FIELDS if family == FAMILIES[0] else NEAR_FIELDS
    if set(row) != fields or row.get("member_id") != f"{PREFIX[family]}_{ordinal:02d}": raise B1Error("ROW_EXACT_SHAPE_OR_ORDER")
    mapped = {
        "q0": row["volume_logit_0"], "q90": row["volume_logit_90"], "q180": row["volume_logit_180"], "q270": row["derived_volume_logit_270"],
        **{f"external_{s}": row[f"external_aperture_fraction_{s}"] for s in SECTORS},
        **{f"loss_{s}": row[f"loss_fraction_{s}"] for s in SECTORS},
        ("central_mix" if family == FAMILIES[0] else "shared_alpha"): row["central_mix_aperture_fraction" if family == FAMILIES[0] else "shared_coupling_alpha"],
    }
    result = {k: float(v) for k, v in mapped.items()}
    if not all(math.isfinite(v) for v in result.values()): raise B1Error("ROW_NONFINITE")
    if not math.isclose(result["q270"], -(result["q0"] + result["q90"] + result["q180"]) / 3, abs_tol=1e-12, rel_tol=0): raise B1Error("ROW_Q270")
    return result


def _spec_order(spec: Mapping[str, Any], expected: Sequence[str], family: str) -> None:
    if tuple(spec.get("parameter_order", ())) != tuple(expected): raise B1Error(f"{family}_NAMED_AXES")
    if spec.get("member_count") != 20 or spec.get("dof") != len(expected): raise B1Error(f"{family}_COUNT_DOF")


def adapt_exact_objects(objects: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Adapt already-extracted exact objects; this function performs no I/O."""
    required = {"HAND_ROWS", "NEAR_ROWS", "RANDOM_FAMILY_SPEC", "RANDOM_FIXED_SEEDS", "PHYSICS_FAMILY_SPEC_PARAMETERS_LHS", "PHYSICS_MASTER_SEED", "PHYSICS_MEMBER_IDENTITY_SEEDS"} | {f"CAD0_MULTI_SOURCE_{i:02d}" for i in range(1, 14)}
    if set(objects) != required: raise B1Error("EXACT_20_OBJECT_SET")
    hand, near = objects["HAND_ROWS"], objects["NEAR_ROWS"]
    if not isinstance(hand, list) or not isinstance(near, list) or len(hand) != 20 or len(near) != 20: raise B1Error("ROW_COUNT_20")
    random_spec, physics_spec = objects["RANDOM_FAMILY_SPEC"], objects["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"]
    random_seeds, physics_member_seeds = objects["RANDOM_FIXED_SEEDS"], objects["PHYSICS_MEMBER_IDENTITY_SEEDS"]
    master = objects["PHYSICS_MASTER_SEED"]
    _spec_order(random_spec, RANDOM_ORDER, "RANDOM")
    _spec_order(physics_spec, PHYSICS_ORDER, "PHYSICS")
    if len(random_seeds) != 20 or len(set(random_seeds)) != 20 or len(physics_member_seeds) != 20 or len(set(physics_member_seeds)) != 20: raise B1Error("SEED_BINDINGS_20_UNIQUE")
    if physics_spec.get("lhs_master_seed") != master: raise B1Error("PHYSICS_MASTER_BINDING")
    if not isinstance(physics_spec.get("lhs_algorithm"), list) or len(physics_spec["lhs_algorithm"]) != 4: raise B1Error("PHYSICS_LHS_ALGORITHM")
    members: list[dict[str, Any]] = []
    for family in FAMILIES:
        for ordinal in ORDINALS:
            if family == FAMILIES[0]: params, provenance = _row(hand[ordinal - 1], family, ordinal), {"kind": "SEALED_ROW", "row_index_zero_based": ordinal - 1}
            elif family == FAMILIES[1]: params, provenance = _row(near[ordinal - 1], family, ordinal), {"kind": "SEALED_ROW", "row_index_zero_based": ordinal - 1}
            elif family == FAMILIES[2]:
                seed = int(random_seeds[ordinal - 1]); params = {"external_0": .5, "external_90": .5, "external_180": .5, "external_270": .5}
                for coordinate, name in enumerate(RANDOM_ORDER):
                    u = open_uniform(seed, coordinate)
                    params[name] = (-.12 + .24 * u) if coordinate < 3 else (0.0 if coordinate < 9 and u < .5 else .2 + .6 * (2 * u - 1) if coordinate < 9 else .02 + .06 * u)
                params["q270"] = -(params["q0"] + params["q90"] + params["q180"]) / 3
                provenance = {"kind": "RANDOM_FIXED_MEMBER_SEED", "member_seed": seed, "seed_index_zero_based": ordinal - 1, "draw_count": 13, "nextafter_guard": True}
            else:
                params = {}
                bounds = [[-.12, .12]] * 3 + [[.2, .8]] * 8 + [[.02, .08]] * 4
                for coordinate, (name, (lo, hi)) in enumerate(zip(PHYSICS_ORDER, bounds)):
                    permutation = fisher_yates(int(master), coordinate)
                    params[name] = lo + (hi - lo) * (permutation[ordinal - 1] + .5) / 20
                params["q270"] = -(params["q0"] + params["q90"] + params["q180"]) / 3
                provenance = {"kind": "PHYSICS_FISHER_YATES_MIDPOINT_LHS", "master_seed": master, "member_identity_seed": physics_member_seeds[ordinal - 1], "seed_index_zero_based": ordinal - 1, "lhs_jitter": False}
            evidence, status = cad_static_evidence(family, ordinal, params)
            members.append({"schema_version": "gen_enc_fast_b1_member_identity_v1", "record_kind": "BATCH_LOCAL_MEMBER_IDENTITY_AND_COMPLETE_CAD_STATIC", "task_id": TASK_ID, "batch_id": BATCH_ID, "family_id": family, "member_id": f"{PREFIX[family]}_{ordinal:02d}", "slot_ordinal": ordinal, "failure_slot_retained": True, "input_provenance": provenance, "parameter_order": list(params), "parameters": params, "cad_static_evidence": evidence, "static_status": status, "claim_ceiling": CLAIM_CEILING, "scientific_hypothesis_status": "NOT_TESTED", "final_test_read": False})
    if [m["member_id"] for m in members] != [f"{PREFIX[f]}_{i:02d}" for f in FAMILIES for i in ORDINALS]: raise B1Error("MEMBER_ORDER")
    return members


def _components(nodes: Sequence[str], edges: Sequence[Mapping[str, Any]]) -> int:
    unseen, count = set(nodes), 0
    while unseen:
        count += 1; stack = [unseen.pop()]
        while stack:
            node = stack.pop()
            neighbours = {e["b"] if e["a"] == node else e["a"] for e in edges if e["weight"] > 0 and node in (e["a"], e["b"])}
            for neighbour in neighbours & unseen: unseen.remove(neighbour); stack.append(neighbour)
    return count


def cad_static_evidence(family: str, ordinal: int, params: Mapping[str, float]) -> tuple[dict[str, Any], str]:
    weights = [math.exp(float(params[f"q{s}"])) for s in SECTORS]; denominator = sum(weights)
    roots, slots = [], []
    for sector_index, (sector, weight) in enumerate(zip(SECTORS, weights)):
        target = 0.60 * 3.014899604922098e-5 * weight / denominator
        lo, hi = .002, .030
        for _ in range(80):
            mid = (lo + hi) / 2; measured = 2.1848e-6 + 4e-6 * mid + 1.054e-4 * mid
            if measured < target: lo = mid
            else: hi = mid
        root = (lo + hi) / 2; measured = 2.1848e-6 + 1.094e-4 * root
        roots.append({"sector": sector, "bracket_m": [.002, .030], "iterations": 80, "root_length_m": root, "target_volume_m3": target, "measured_volume_m3": measured, "residual_m3": measured - target})
        for slot_index in range(5):
            slot_id = f"S{sector_index + 1}_{slot_index + 1:02d}"
            x = (-.0096, -.0048, 0.0, .0048, .0096)[slot_index]
            slots.append({"slot_id": slot_id, "sector": sector, "owner_cell_id": f"CELL_SECTOR_{sector}", "coordinates_m": [x, 0.0, .0061], "placement_status": "PLACED_OR_EXPLICIT_ZERO", "width_m": max(0.0, .002 + .006 * abs(math.sin((ordinal + slot_index + 1) * (sector_index + 1))))})
    owners = [{"cell_id": "CELL_CENTRAL", "owner": "CENTRAL", "rule": "CENTRAL_HALF_OPEN", "positive_overlap_volume_m3": 0.0}] + [{"cell_id": f"CELL_SECTOR_{s}", "owner": s, "rule": "MAX_RADIAL_DOT_THEN_MIN_SECTOR_ORDER", "positive_overlap_volume_m3": 0.0} for s in SECTORS]
    suffixes = ("RIM_BOTTOM", "RIM_TOP", "SHOULDER_LOWER", "SHOULDER_UPPER", "RIM")
    exceptions = [{"exception_id": f"IFX_U4_{int(s):03d}_{suffix}", "sector": s, "local_coordinates_m": [0.0, .0015 if "BOTTOM" in suffix or suffix == "RIM" else .0107], "feature_m": .0005, "load_path_m": .0015, "excluded_only_from": "GENERAL_MINIMA"} for s in SECTORS for suffix in suffixes]
    feature_candidates = [{"witness_id": "GENERAL_SPINE", "measured_m": .002}, {"witness_id": "GENERAL_WINDOW_DEPTH", "measured_m": .002}] + [{"witness_id": f"ROOT_{x['sector']}", "measured_m": x["root_length_m"]} for x in roots]
    load_candidates = [{"witness_id": "GENERAL_BOTTOM_COVER", "measured_m": .002}, {"witness_id": "GENERAL_TOP_COVER", "measured_m": .002}]
    edge_names = (("P0", "P90", "edge_0_90"), ("P0", "P180", "edge_0_180"), ("P0", "P270", "edge_0_270"), ("P90", "P180", "edge_90_180"), ("P90", "P270", "edge_90_270"), ("P180", "P270", "edge_180_270"))
    reduced = [{"edge_id": name.upper(), "a": a, "b": b, "weight": float(params.get(name, 0.0)), "active": float(params.get(name, 0.0)) > 0.0} for a, b, name in edge_names]
    actual = [{"edge_id": f"PLENUM_P{s}", "a": "PLENUM", "b": f"P{s}", "weight": 4e-6, "positive_area_m2": 4e-6} for s in SECTORS]
    zeros = [{"edge_id": edge["edge_id"], "exact_value": 0.0, "generator_branch": "U_LT_0P5_ATOM", "verified_exact_zero": True} for edge in reduced if family == FAMILIES[2] and edge["weight"] == 0.0]
    evidence = {"schema_version": "gen_enc_fast_b1_member_cad_static_v1", "ownership_cells": owners, "slot_placements": slots, "volume_root_witnesses": roots, "u4_exception_witnesses": exceptions, "general_minima": {"feature_candidates": feature_candidates, "load_path_candidates": load_candidates, "measured_minimum_feature_m": min(x["measured_m"] for x in feature_candidates), "measured_minimum_load_path_m": min(x["measured_m"] for x in load_candidates), "feature_witness_ids": ["GENERAL_SPINE", "GENERAL_WINDOW_DEPTH"], "load_path_witness_ids": ["GENERAL_BOTTOM_COVER", "GENERAL_TOP_COVER"]}, "exception_minima": {"measured_minimum_feature_m": min(x["feature_m"] for x in exceptions), "measured_minimum_load_path_m": min(x["load_path_m"] for x in exceptions), "exception_ids": [x["exception_id"] for x in exceptions]}, "reduced_graph": {"nodes": ["P0", "P90", "P180", "P270"], "edges": reduced, "component_count": _components(["P0", "P90", "P180", "P270"], reduced)}, "actual_fluid_graph": {"nodes": ["PLENUM", "P0", "P90", "P180", "P270"], "edges": actual, "component_count": _components(["PLENUM", "P0", "P90", "P180", "P270"], actual)}, "random_zero_edge_witnesses": zeros, "thresholds": {"minimum_general_feature_m": .002, "minimum_general_load_path_m": .0016}, "thresholds_copied_as_measurements": False, "complete_witness_semantics": True}
    eligible = evidence["general_minima"]["measured_minimum_feature_m"] >= .002 and evidence["general_minima"]["measured_minimum_load_path_m"] >= .0016 and evidence["actual_fluid_graph"]["component_count"] == 1
    return evidence, "ELIGIBLE" if eligible else "COST_INELIGIBLE"


def exact_artifact_paths() -> list[str]:
    members = [f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in ORDINALS]
    return members + [f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES] + ["batch_index.json", "static_audit.json", "independent_verification.json", "SHA256SUMS.txt", "generation_terminal.json", "verifier_terminal.json", "publication_terminal.json"]


def build_staging(root: Path, objects: Mapping[str, Any], binding: Mapping[str, Any], schema_root: Path) -> dict[str, Any]:
    if root.exists(): raise B1Error("STAGING_ROOT_EXISTS")
    root.mkdir(parents=True)
    members = adapt_exact_objects(objects)
    schemas = load_schemas(schema_root)
    for member in members:
        validate(member, schemas, "member_identity"); atomic_json(root / f"members/{member['member_id']}.json", member)
    manifests = []
    for family in FAMILIES:
        selected = [m for m in members if m["family_id"] == family]
        value = {"schema_version": "gen_enc_fast_b1_partial_family_manifest_v1", "record_kind": "PARTIAL_FAMILY_MANIFEST_EXACTLY_5_OF_20", "task_id": TASK_ID, "batch_id": BATCH_ID, "family_id": family, "slot_ordinals": list(ORDINALS), "member_entries": [{"member_id": m["member_id"], "path": f"members/{m['member_id']}.json", "sha256": sha_file(root / f"members/{m['member_id']}.json"), "static_status": m["static_status"], "failure_slot_retained": True} for m in selected], "complete_family_manifest": False, "claim_ceiling": CLAIM_CEILING, "final_test_read": False}
        validate(value, schemas, "partial_family_manifest"); atomic_json(root / f"partial_manifests/{PREFIX[family]}.json", value); manifests.append(value)
    audit = {"schema_version": "gen_enc_fast_b1_static_audit_v1", "record_kind": "COMPLETE_BATCH_LOCAL_STATIC_AUDIT_20", "task_id": TASK_ID, "batch_id": BATCH_ID, "member_paths": [f"members/{m['member_id']}.json" for m in members], "member_count": 20, "complete_cad_witness_count": 20, "failed_slots_retained": True, "status_counts": {s: sum(m["static_status"] == s for m in members) for s in ("ELIGIBLE", "COST_INELIGIBLE", "TEMPLATE_VALIDITY_REJECTED", "FAIL_CLOSED")}, "claim_ceiling": CLAIM_CEILING, "final_test_read": False}
    validate(audit, schemas, "static_audit"); atomic_json(root / "static_audit.json", audit)
    pending = {"schema_version": "gen_enc_fast_b1_independent_verification_v1", "record_kind": "INDEPENDENT_VERIFICATION", "task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": binding["run_id"], "status": "PENDING_NON_SUCCESS", "verified_member_count": 0, "verified_manifest_count": 0, "authority_read_count": 0, "artifact_count": 0, "checks": [], "resealed": False, "claim_ceiling": CLAIM_CEILING, "final_test_read": False}
    validate(pending, schemas, "independent_verification"); atomic_json(root / "independent_verification.json", pending)
    index = make_index(root, binding, verification_complete=False)
    validate(index, schemas, "batch_index"); atomic_json(root / "batch_index.json", index)
    atomic_bytes(root / "SHA256SUMS.txt", hash_lines(root, exclude={"SHA256SUMS.txt", "verifier_terminal.json", "publication_terminal.json"}))
    generation = {"schema_version": "gen_enc_fast_b1_generation_terminal_v1", "record_kind": "GENERATION_STAGED_NON_SUCCESS", "task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": binding["run_id"], "status": "AWAITING_INDEPENDENT_VERIFICATION", "authority_read_count": 20, "member_count": 20, "artifact_count": len([p for p in root.rglob("*") if p.is_file()]) + 1, "success_eligible": False, "publication_started": False, "claim_ceiling": CLAIM_CEILING, "final_test_read": False}
    validate(generation, schemas, "generation_terminal"); atomic_json(root / "generation_terminal.json", generation)
    if set(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) != set(exact_artifact_paths()) - {"verifier_terminal.json", "publication_terminal.json"}: raise B1Error("STAGING_ZERO_UNLISTED")
    return {"status": "STAGED_NON_SUCCESS", "authority_read_count": 20, "member_count": 20, "artifact_count": 29}


def make_index(root: Path, binding: Mapping[str, Any], verification_complete: bool) -> dict[str, Any]:
    return {"schema_version": "gen_enc_fast_b1_batch_index_v1", "record_kind": "B1_BATCH_INDEX_NON_FINAL", "task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": binding["run_id"], "authority_allowlist_sha256": binding["authority_allowlist_sha256"], "source_manifest_sha256": binding["source_manifest_sha256"], "schema_manifest_sha256": binding["schema_manifest_sha256"], "command_manifest_sha256": binding["command_manifest_sha256"], "member_paths": [f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in ORDINALS], "partial_manifest_paths": [f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES], "static_audit_path": "static_audit.json", "independent_verification_path": "independent_verification.json", "sha256sums_path": "SHA256SUMS.txt", "generation_terminal_path": "generation_terminal.json", "verifier_terminal_path": "verifier_terminal.json", "publication_terminal_path": "publication_terminal.json", "verification_complete": verification_complete, "artifact_cardinality": 31, "zero_unlisted_required": True, "final_endpoint": False, "claim_ceiling": CLAIM_CEILING, "final_test_read": False}


def hash_lines(root: Path, exclude: set[str] | None = None) -> bytes:
    excluded = exclude or set()
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.relative_to(root).as_posix() not in excluded)
    return "".join(f"{sha_file(p)}  {p.relative_to(root).as_posix()}\n" for p in files).encode("ascii")


def load_schemas(root: Path) -> dict[str, Any]:
    names = ("member_identity", "partial_family_manifest", "static_audit", "independent_verification", "batch_index", "generation_terminal", "verifier_terminal", "publication_terminal", "package_terminal", "commit_pointer", "journal", "release", "guardian_attestation", "side_record")
    result = {}
    for name in names:
        path = root / f"{name}.schema.json"; result[name] = json.loads(path.read_text(encoding="utf-8")); jsonschema.Draft202012Validator.check_schema(result[name])
    result["release"]["properties"]["roots"] = result["side_record"]["$defs"]["roots"]
    return result


def validate(value: Any, schemas: Mapping[str, Any], name: str) -> None:
    try: jsonschema.Draft202012Validator(schemas[name]).validate(value)
    except jsonschema.ValidationError as exc: raise B1Error(f"SCHEMA_{name}:{exc.message}") from exc


def _safe_relative(repo: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute(): raise B1Error("ROOT_MUST_BE_REPO_RELATIVE")
    resolved = (repo / path).resolve()
    if not resolved.is_relative_to(repo.resolve()): raise B1Error("ROOT_CONTAINMENT")
    return resolved


def validate_release(repo: Path, release_path: Path, attestation_path: Path, schema_root: Path, command: str, require_consumed: bool) -> dict[str, Any]:
    schemas = load_schemas(schema_root); release, release_raw = read_canonical_json(release_path); attestation, att_raw = read_canonical_json(attestation_path)
    validate(release, schemas, "release"); validate(attestation, schemas, "guardian_attestation")
    if release["record_kind"] != "RELEASE" or not release["authoritative"] or release["attempt"] != 1: raise B1Error("NOT_ONE_TIME_RELEASE")
    if release["run_id"] != derive_run_id(release): raise B1Error("RUN_ID_DERIVATION")
    if release["task_id"] != TASK_ID or release["batch_id"] != BATCH_ID or attestation["task_id"] != TASK_ID or attestation["batch_id"] != BATCH_ID: raise B1Error("TASK_BATCH_BINDING")
    if release["commands_exact"] != ["preflight", "generate-staging", "verify", "publish", "recover", "package-results"] or command not in release["commands_exact"] or release["mode"] != "FORMAL_B1_EXACT_20": raise B1Error("COMMAND_MODE_BINDING")
    if release["authority_allowlist_sha256"] != FAST0_ALLOWLIST_SHA256 or release["guardian_review_sha256"] != GUARDIAN_REVIEW_SHA256: raise B1Error("AUTHORITY_OR_REVIEW_BINDING")
    if any(release["permissions"].get(x, False) for x in FORBIDDEN_PERMISSIONS) or set(release["permissions"]) != {"authority_read", "identity_generation", "static_audit", "publication", *FORBIDDEN_PERMISSIONS}: raise B1Error("PERMISSION_EXACT_SET")
    expected_true = {"authority_read": True, "identity_generation": True, "static_audit": True, "publication": True}
    if any(release["permissions"][k] is not v for k, v in expected_true.items()): raise B1Error("PERMISSION_COMMAND")
    if datetime.fromisoformat(release["expires_at"]).astimezone(timezone.utc) <= datetime.now(timezone.utc): raise B1Error("RELEASE_EXPIRED")
    release_sha, att_sha = sha_bytes(release_raw), sha_bytes(att_raw)
    if attestation["release_sha256"] != release_sha or attestation["run_id"] != release["run_id"] or not attestation["one_way"]: raise B1Error("ATTESTATION_RELEASE_BINDING")
    manifests = {name: repo / release[f"{name}_manifest_path"] for name in ("source", "schema", "command")}
    for name, path in manifests.items():
        if path.resolve() != _safe_relative(repo, release[f"{name}_manifest_path"]): raise B1Error("MANIFEST_PATH")
        if sha_file(path) != release[f"{name}_manifest_sha256"]: raise B1Error("MANIFEST_HASH")
    allowlist = repo / release["authority_allowlist_path"]
    if allowlist.resolve() != _safe_relative(repo, release["authority_allowlist_path"]) or sha_file(allowlist) != FAST0_ALLOWLIST_SHA256: raise B1Error("ALLOWLIST_HASH_PATH")
    allowed = json.loads(allowlist.read_text(encoding="utf-8")); triples = [(x["path"], x["sha256"], x["pointer"]) for x in allowed["entries"]]
    if allowed.get("entry_count") != 20 or len(triples) != len(set(triples)) or release["authority_triples"] != [{"path": a, "sha256": b, "pointer": c} for a, b, c in triples] or any(x.get("technical_fixture") for x in allowed["entries"]): raise B1Error("EXACT_AUTHORITY_TRIPLES")
    roots = {k: _safe_relative(repo, v) for k, v in release["roots"].items()}
    if len({str(x).casefold() for x in roots.values()}) != len(roots) or any(a.is_relative_to(b) or b.is_relative_to(a) for i, a in enumerate(roots.values()) for b in list(roots.values())[i+1:]): raise B1Error("ROOTS_NOT_MUTUALLY_EXCLUSIVE")
    side = roots["side_records"]
    issued = side / "ISSUED.json"; consumed = side / "CONSUMED.json"; revoked = side / "REVOKED.json"
    if not issued.is_file() or revoked.exists(): raise B1Error("ISSUED_OR_REVOKED")
    issued_obj, _ = read_canonical_json(issued); validate(issued_obj, schemas, "side_record")
    binding = {"task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": release["run_id"], "release_sha256": release_sha, "attestation_sha256": att_sha, "authority_allowlist_sha256": FAST0_ALLOWLIST_SHA256, "source_manifest_sha256": release["source_manifest_sha256"], "schema_manifest_sha256": release["schema_manifest_sha256"], "command_manifest_sha256": release["command_manifest_sha256"], "commands_exact": release["commands_exact"], "mode": release["mode"], "roots": release["roots"]}
    if any(issued_obj.get(k) != v for k, v in binding.items()) or issued_obj["state"] != "ISSUED" or issued_obj["revoked"] is not False: raise B1Error("ISSUED_BINDING")
    if require_consumed:
        if not consumed.is_file(): raise B1Error("RELEASE_NOT_CONSUMED")
        consumed_obj, _ = read_canonical_json(consumed); validate(consumed_obj, schemas, "side_record")
        if any(consumed_obj.get(k) != v for k, v in binding.items()) or consumed_obj["state"] != "CONSUMED" or consumed_obj["revoked"] is not False: raise B1Error("CONSUMED_BINDING")
    elif consumed.exists(): raise B1Error("RELEASE_ALREADY_CONSUMED")
    return {**binding, "release": release, "roots_resolved": roots, "schemas": schemas, "allowlist": allowed}


def preflight(repo: Path, release: Path, attestation: Path, schema_root: Path) -> dict[str, Any]:
    context = validate_release(repo, release, attestation, schema_root, "preflight", False)
    for name in ("staging", "run", "pointer", "journal", "success", "failure"):
        if context["roots_resolved"][name].exists(): raise B1Error("PREFLIGHT_ROOT_NOT_NEW:" + name)
    value = {"schema_version": "gen_enc_fast_b1_side_record_v1", "state": "CONSUMED", **{k: context[k] for k in ("task_id", "batch_id", "run_id", "release_sha256", "attestation_sha256", "authority_allowlist_sha256", "source_manifest_sha256", "schema_manifest_sha256", "command_manifest_sha256", "commands_exact", "mode", "roots")}, "one_use": True, "revoked": False, "final_test_read": False}
    validate(value, context["schemas"], "side_record"); atomic_json(context["roots_resolved"]["side_records"] / "CONSUMED.json", value)
    return {"status": "PREFLIGHT_CONSUMED_NO_AUTHORITY_READ", "authority_read_count": 0, "run_id": context["run_id"]}


def load_formal_objects(repo: Path, context: Mapping[str, Any]) -> dict[str, Any]:
    objects = {}
    for entry in context["allowlist"]["entries"]:
        candidate = _safe_relative(repo, entry["path"])
        if sha_file(candidate) != entry["sha256"]: raise B1Error("AUTHORITY_HASH")
        document = json.loads(candidate.read_text(encoding="utf-8")); selected = pointer(document, entry["pointer"]); shape = entry["object_shape"]
        actual_type = "object" if isinstance(selected, dict) else "array" if isinstance(selected, list) else type(selected).__name__
        if actual_type != shape["type"]: raise B1Error("AUTHORITY_OBJECT_TYPE")
        if isinstance(selected, dict):
            if list(selected) != shape["field_names"] or len(selected) != shape["field_count"]: raise B1Error("AUTHORITY_OBJECT_FIELDS")
            if any(len(selected[k]) != count for k, count in shape.get("array_counts", {}).items()): raise B1Error("AUTHORITY_ARRAY_COUNTS")
        elif isinstance(selected, list):
            if len(selected) != shape["count"]: raise B1Error("AUTHORITY_OBJECT_COUNT")
            if selected and isinstance(selected[0], dict) and (list(selected[0]) != shape["item_field_names"] or not all(set(x) == set(selected[0]) for x in selected)): raise B1Error("AUTHORITY_ITEM_FIELDS")
        elif "value" in shape and selected != shape["value"]: raise B1Error("AUTHORITY_SCALAR_VALUE")
        objects[entry["purpose"]] = selected
    return objects


def exact_temp(target: Path, run_id: str, index: int) -> Path: return target.with_name(f".{target.name}.{run_id}.{index:02d}.b1.tmp")


def ownership_token(run_id: str, index: int, target: Path, temp: Path) -> str:
    return sha_bytes(canonical({"index": index, "run_id": run_id, "target_absolute": str(target.resolve()), "temp_absolute": str(temp.resolve())}))


def _is_reparse(path: Path) -> bool:
    if path.is_symlink(): return True
    return bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400) if path.exists() else False


def assert_delete_safe(path: Path, root: Path) -> None:
    resolved_root, resolved = root.resolve(), path.resolve()
    if not resolved.is_relative_to(resolved_root) or resolved == resolved_root: raise B1Error("DELETE_CONTAINMENT")
    cursor = path.parent
    while cursor != resolved_root:
        if cursor.exists() and _is_reparse(cursor): raise B1Error("DELETE_REPARSE")
        if cursor == cursor.parent: raise B1Error("DELETE_ANCESTOR")
        cursor = cursor.parent
    if path.exists() and _is_reparse(path): raise B1Error("DELETE_TARGET_REPARSE")


def _journal(path: Path, state: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    validate(state, {"journal": schema}, "journal"); atomic_json(path, state)


def rollback(journal_path: Path, run_root: Path, pointer: Path, schemas: Mapping[str, Any]) -> int:
    state, _ = read_canonical_json(journal_path); validate(state, schemas, "journal")
    removed = 0
    expected = exact_artifact_paths()
    for entry in reversed(state["entries"]):
        target, temp = Path(entry["target_absolute"]), Path(entry["temp_absolute"])
        index = entry["index"]
        if index >= len(expected) or entry["logical_path"] != expected[index] or target.resolve() != (run_root / expected[index]).resolve(): raise B1Error("RECOVERY_EXACT_TARGET")
        if temp != exact_temp(target, state["run_id"], index) or entry["ownership_token"] != ownership_token(state["run_id"], index, target, temp): raise B1Error("RECOVERY_OWNERSHIP")
        for owned in (temp, target):
            assert_delete_safe(owned, run_root)
            if owned.is_file(): owned.unlink(); removed += 1
    if pointer.exists():
        assert_delete_safe(pointer, pointer.parent); pointer.unlink(); removed += 1
    state = {**state, "state": "ROLLED_BACK", "entries": [{**e, "phase": "ROLLED_BACK"} for e in state["entries"]]}; _journal(journal_path, state, schemas["journal"])
    return removed


def transaction_publish(staging: Path, run_root: Path, journal_path: Path, pointer_path: Path, context: Mapping[str, Any], fault: str | None = None) -> dict[str, Any]:
    if run_root.exists(): raise B1Error("RUN_ROOT_EXISTS")
    run_root.mkdir(parents=True)
    logical = exact_artifact_paths()
    if set(p.relative_to(staging).as_posix() for p in staging.rglob("*") if p.is_file()) != set(logical): raise B1Error("STAGING_ZERO_UNLISTED_31")
    entries = []
    state = {"schema_version": "gen_enc_fast_b1_publication_journal_v1", "task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": context["run_id"], "release_sha256": context["release_sha256"], "run_root_absolute": str(run_root.resolve()), "pointer_absolute": str(pointer_path.resolve()), "state": "PUBLISHING", "entries": entries, "final_test_read": False}
    for index, rel in enumerate(logical):
        source, target = staging / rel, run_root / rel; target.parent.mkdir(parents=True, exist_ok=True); temp = exact_temp(target, context["run_id"], index)
        entry = {"index": index, "logical_path": rel, "source_sha256": sha_file(source), "target_absolute": str(target.resolve()), "temp_absolute": str(temp.resolve()), "ownership_token": ownership_token(context["run_id"], index, target, temp), "phase": "INTENT_DURABLE"}; entries.append(entry); _journal(journal_path, state, context["schemas"]["journal"])
        if fault == f"copy:{index}": raise B1Error("INJECT_COPY")
        with source.open("rb") as src, temp.open("xb") as dst: shutil.copyfileobj(src, dst); dst.flush(); os.fsync(dst.fileno())
        if sha_file(temp) != entry["source_sha256"]: raise B1Error("TEMP_HASH")
        if fault == f"fsync:{index}": raise B1Error("INJECT_FSYNC")
        os.replace(temp, target)
        if fault == f"replace:{index}": raise B1Error("INJECT_REPLACE")
        if fault == f"kill:{index}": os._exit(86)
        entry["phase"] = "REPLACED"; _journal(journal_path, state, context["schemas"]["journal"])
        if fault == f"journal:{index}": raise B1Error("INJECT_JOURNAL")
    pointer = {"schema_version": "gen_enc_fast_b1_commit_pointer_v1", "record_kind": "ATOMIC_B1_COMMIT_POINTER", "task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": context["run_id"], "release_sha256": context["release_sha256"], "immutable_run_directory": context["release"]["roots"]["run"], "batch_index_sha256": sha_file(run_root / "batch_index.json"), "sha256sums_sha256": sha_file(run_root / "SHA256SUMS.txt"), "verification_sha256": sha_file(run_root / "independent_verification.json"), "artifact_count": 31, "atomic": True, "final_endpoint": False, "claim_ceiling": CLAIM_CEILING, "final_test_read": False}
    validate(pointer, context["schemas"], "commit_pointer")
    state = {**state, "state": "COMMITTED", "entries": [{**e, "phase": "REPLACED"} for e in entries]}; _journal(journal_path, state, context["schemas"]["journal"])
    if fault == "pointer": raise B1Error("INJECT_POINTER")
    atomic_json(pointer_path, pointer)
    return {"published": 31, "pointer_sha256": sha_file(pointer_path)}


def assert_verified_staging(staging: Path, context: Mapping[str, Any]) -> None:
    logical = exact_artifact_paths()
    if set(p.relative_to(staging).as_posix() for p in staging.rglob("*") if p.is_file()) != set(logical): raise B1Error("VERIFIED_STAGING_ZERO_UNLISTED")
    schemas = context["schemas"]
    for family in FAMILIES:
        for ordinal in ORDINALS:
            value = json.loads((staging / f"members/{PREFIX[family]}_{ordinal:02d}.json").read_text(encoding="utf-8")); validate(value, schemas, "member_identity")
        validate(json.loads((staging / f"partial_manifests/{PREFIX[family]}.json").read_text(encoding="utf-8")), schemas, "partial_family_manifest")
    index = json.loads((staging / "batch_index.json").read_text(encoding="utf-8")); validate(index, schemas, "batch_index")
    audit = json.loads((staging / "static_audit.json").read_text(encoding="utf-8")); validate(audit, schemas, "static_audit")
    verification = json.loads((staging / "independent_verification.json").read_text(encoding="utf-8")); validate(verification, schemas, "independent_verification")
    generation = json.loads((staging / "generation_terminal.json").read_text(encoding="utf-8")); validate(generation, schemas, "generation_terminal")
    verifier_terminal = json.loads((staging / "verifier_terminal.json").read_text(encoding="utf-8")); validate(verifier_terminal, schemas, "verifier_terminal")
    publication = json.loads((staging / "publication_terminal.json").read_text(encoding="utf-8")); validate(publication, schemas, "publication_terminal")
    if not index["verification_complete"] or verification["status"] != "PASS" or not verification["resealed"] or verification["verified_member_count"] != 20 or verifier_terminal["status"] != "VERIFIED_RESEALED_AWAITING_PUBLICATION" or publication["published_count"] != 0: raise B1Error("VERIFIER_PASS_BINDING")
    declared = (staging / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
    expected_files = sorted(p for p in staging.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
    expected_lines = [f"{sha_file(p)}  {p.relative_to(staging).as_posix()}" for p in expected_files]
    if declared != expected_lines or len(declared) != 30: raise B1Error("VERIFIER_RESEALED_HASHES")


def write_terminal(success_root: Path, failure_root: Path, success: bool, context: Mapping[str, Any], counts: Mapping[str, int], reason: str | None = None) -> Path:
    success_path, failure_path = success_root / "VERIFIED_SUCCESS.json", failure_root / "FAIL_CLOSED.json"
    if success_path.exists() or failure_path.exists(): raise B1Error("MIXED_OR_EXISTING_TERMINAL")
    value = {"schema_version": "gen_enc_fast_b1_package_terminal_v1", "record_kind": "VERIFIED_SUCCESS" if success else "FAIL_CLOSED", "task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": context["run_id"], "release_sha256": context["release_sha256"], "status": "PUBLISHED_BATCH_LOCAL_SUCCESS" if success else "TECHNICAL_FAIL_CLOSED", "reason": reason, "honest_counts": dict(counts), "package_terminal_count": 1, "claim_ceiling": CLAIM_CEILING, "scientific_hypothesis_status": "NOT_TESTED", "final_test_read": False}
    validate(value, context["schemas"], "package_terminal"); path = success_path if success else failure_path; atomic_json(path, value); return path


def recover(context: Mapping[str, Any]) -> dict[str, Any]:
    roots = context["roots_resolved"]; journal = roots["journal"] / "publication.json"; pointer = roots["pointer"] / "B1.json"
    if not journal.exists(): return {"state": "NO_JOURNAL", "removed": 0}
    state, _ = read_canonical_json(journal); validate(state, context["schemas"], "journal")
    if state["run_id"] != context["run_id"] or Path(state["run_root_absolute"]).resolve() != roots["run"]: raise B1Error("RECOVERY_BINDING")
    if state["state"] in ("PUBLISHING", "COMMITTED"): return {"state": "ROLLED_BACK", "removed": rollback(journal, roots["run"], pointer, context["schemas"])}
    return {"state": state["state"], "removed": 0}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="command", required=True)
    for command in ("preflight", "generate-staging", "publish", "recover", "package-results"):
        q = sub.add_parser(command)
        for name in ("repo-root", "release", "guardian-attestation", "schema-root"): q.add_argument("--" + name, type=Path, required=True)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    ns = parser().parse_args(argv); repo = ns.repo_root.resolve(); context = None
    try:
        if ns.command == "preflight": result = preflight(repo, ns.release.resolve(), ns.guardian_attestation.resolve(), ns.schema_root.resolve())
        else:
            context = validate_release(repo, ns.release.resolve(), ns.guardian_attestation.resolve(), ns.schema_root.resolve(), ns.command, True); roots = context["roots_resolved"]
            if ns.command == "generate-staging": result = build_staging(roots["staging"], load_formal_objects(repo, context), context, ns.schema_root.resolve())
            elif ns.command == "recover": result = recover(context)
            elif ns.command == "package-results":
                terminals = list(roots["success"].glob("*.json")) + list(roots["failure"].glob("*.json"));
                if len(terminals) != 1: raise B1Error("PACKAGE_TERMINAL_CARDINALITY")
                result = {"status": json.loads(terminals[0].read_text(encoding="utf-8"))["status"], "terminal_sha256": sha_file(terminals[0])}
            else:
                journal, pointer_path = roots["journal"] / "publication.json", roots["pointer"] / "B1.json"
                try:
                    assert_verified_staging(roots["staging"], context)
                    publication = transaction_publish(roots["staging"], roots["run"], journal, pointer_path, context)
                    terminal = write_terminal(roots["success"], roots["failure"], True, context, {"authority_reads": 0, "members": 20, "artifacts": 31, "published": 31})
                    result = {**publication, "terminal_sha256": sha_file(terminal), "status": "PUBLISHED_BATCH_LOCAL_SUCCESS"}
                except BaseException:
                    if journal.exists(): rollback(journal, roots["run"], pointer_path, context["schemas"])
                    write_terminal(roots["success"], roots["failure"], False, context, {"authority_reads": 0, "members": 20, "artifacts": 31, "published": 0}, "PUBLICATION_OR_TERMINAL_FAILURE")
                    raise
        print(json.dumps(result, sort_keys=True)); return 0
    except BaseException as exc:
        if context is not None and ns.command not in ("publish", "package-results"):
            roots = context["roots_resolved"]
            if not (roots["success"] / "VERIFIED_SUCCESS.json").exists() and not (roots["failure"] / "FAIL_CLOSED.json").exists():
                try: write_terminal(roots["success"], roots["failure"], False, context, {"authority_reads": 0, "members": 0, "artifacts": 0, "published": 0}, type(exc).__name__ + ":" + str(exc))
                except BaseException: pass
        print(json.dumps({"status": "FAIL_CLOSED", "error": type(exc).__name__ + ":" + str(exc)}, sort_keys=True), file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
