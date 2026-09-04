"""Independent FAST-B1 verifier/resealer.

This file deliberately imports no driver, generator, CAD mapper, or FAST-0
adapter.  It validates the sealed axes and algorithms and every persisted CAD
witness from first principles before it changes PENDING staging into verified,
still-unpublished staging.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

TASK_ID = "01a049a7-15ca-79e1-92a2-d3822ba8609d"
BATCH_ID = "B1"
ALLOWLIST_SHA = "49263e3cab9825840284d18a4d628be73d1273bf6940493878bac5da529c958c"
GUARDIAN_SHA = "f96a71e850ceaefa9c2267c2641d6307c9c98af38b53aa8ef3893fef5de2c8fd"
FAMILIES = ("HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED")
PREFIX = dict(zip(FAMILIES, ("HAND", "NEAR", "RANDOM", "PHYSICS")))
SECTORS = ("0", "90", "180", "270")
RANDOM_AXES = ("q0", "q90", "q180", "edge_0_90", "edge_0_180", "edge_0_270", "edge_90_180", "edge_90_270", "edge_180_270", "loss_0", "loss_90", "loss_180", "loss_270")
PHYSICS_AXES = ("q0", "q90", "q180", "external_0", "external_90", "external_180", "external_270", "ring_0_90", "ring_90_180", "ring_180_270", "ring_270_0", "loss_0", "loss_90", "loss_180", "loss_270")
U64 = 0xFFFFFFFFFFFFFFFF
PHI = 0x9E3779B97F4A7C15
CLAIM = "BATCH_LOCAL_IDENTITY_COMPLETE_CAD_STATIC_AND_TECHNICAL_VALIDITY_ONLY"
RUN_DOMAIN = b"GEN-ENC-FAST-B1-RUN-ID-v1"


class VerifyError(RuntimeError): pass


def canonical(value: Any) -> bytes:
    def inspect(x: Any) -> None:
        if isinstance(x, float) and (not math.isfinite(x) or (x == 0 and math.copysign(1, x) < 0)): raise VerifyError("NUMBER")
        if isinstance(x, dict):
            if not all(isinstance(k, str) for k in x): raise VerifyError("KEY")
            for child in x.values(): inspect(child)
        elif isinstance(x, list):
            for child in x: inspect(child)
    inspect(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def sha_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def sha_file(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def derive_run_id(release: Mapping[str, Any]) -> str:
    clone = dict(release); clone["run_id"] = "0" * 64
    return sha_bytes(RUN_DOMAIN + b"\n" + canonical(clone))


def read_json(path: Path, canonical_required: bool = True) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes(); value = json.loads(raw.decode())
    if canonical_required and raw != canonical(value): raise VerifyError("NON_CANONICAL:" + path.name)
    return value, raw


def atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temp = path.with_name(path.name + ".atomic.tmp")
    if temp.exists(): raise VerifyError("TEMP_COLLISION")
    with temp.open("xb") as stream: stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)


def _mix(argument: int) -> int:
    z = (argument + PHI) & U64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & U64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & U64
    return (z ^ (z >> 31)) & U64


def uniform(seed: int, axis: int) -> float:
    answer = ((_mix((seed + PHI * (axis + 1)) & U64) >> 11) + .5) / 9007199254740992
    return math.nextafter(1.0, 0.0) if answer == 1.0 else answer


def permutation(master: int, axis: int) -> list[int]:
    result = [x for x in range(20)]; i = 19
    while i:
        address = (master + PHI * (1 + 32 * axis + 19 - i)) & U64; pick = _mix(address) % (i + 1)
        result[i], result[pick] = result[pick], result[i]; i -= 1
    return result


def expected_parameters(objects: Mapping[str, Any], family: str, ordinal: int) -> tuple[dict[str, float], dict[str, Any]]:
    if family in FAMILIES[:2]:
        rows = objects["HAND_ROWS" if family == FAMILIES[0] else "NEAR_ROWS"]
        row = rows[ordinal - 1]; prefix = PREFIX[family]
        if len(rows) != 20 or row.get("member_id") != f"{prefix}_{ordinal:02d}": raise VerifyError("ROW_BINDING")
        required = {"member_id", "volume_logit_0", "volume_logit_90", "volume_logit_180", "derived_volume_logit_270", "external_aperture_fraction_0", "external_aperture_fraction_90", "external_aperture_fraction_180", "external_aperture_fraction_270", "loss_fraction_0", "loss_fraction_90", "loss_fraction_180", "loss_fraction_270", "central_mix_aperture_fraction" if family == FAMILIES[0] else "shared_coupling_alpha"}
        if set(row) != required: raise VerifyError("ROW_FIELD_SET")
        params = {"q0": float(row["volume_logit_0"]), "q90": float(row["volume_logit_90"]), "q180": float(row["volume_logit_180"]), "q270": float(row["derived_volume_logit_270"]), **{f"external_{s}": float(row[f"external_aperture_fraction_{s}"]) for s in SECTORS}, **{f"loss_{s}": float(row[f"loss_fraction_{s}"]) for s in SECTORS}, ("central_mix" if family == FAMILIES[0] else "shared_alpha"): float(row["central_mix_aperture_fraction" if family == FAMILIES[0] else "shared_coupling_alpha"])}
        if not math.isclose(params["q270"], -(params["q0"] + params["q90"] + params["q180"]) / 3, abs_tol=1e-12): raise VerifyError("Q270")
        return params, {"kind": "SEALED_ROW", "row_index_zero_based": ordinal - 1}
    if family == FAMILIES[2]:
        spec, seeds = objects["RANDOM_FAMILY_SPEC"], objects["RANDOM_FIXED_SEEDS"]
        if tuple(spec.get("parameter_order", ())) != RANDOM_AXES or spec.get("member_count") != 20 or spec.get("dof") != 13 or len(seeds) != 20 or len(set(seeds)) != 20: raise VerifyError("RANDOM_AXIS_SEEDS")
        seed = int(seeds[ordinal - 1]); params = {f"external_{s}": .5 for s in SECTORS}
        for axis, name in enumerate(RANDOM_AXES):
            u = uniform(seed, axis)
            if axis < 3: value = -.12 + .24 * u
            elif axis < 9: value = 0.0 if u < .5 else .2 + .6 * (2 * u - 1)
            else: value = .02 + .06 * u
            params[name] = value
        params["q270"] = -(params["q0"] + params["q90"] + params["q180"]) / 3
        return params, {"kind": "RANDOM_FIXED_MEMBER_SEED", "member_seed": seed, "seed_index_zero_based": ordinal - 1, "draw_count": 13, "nextafter_guard": True}
    spec, member_seeds, master = objects["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"], objects["PHYSICS_MEMBER_IDENTITY_SEEDS"], objects["PHYSICS_MASTER_SEED"]
    if tuple(spec.get("parameter_order", ())) != PHYSICS_AXES or spec.get("member_count") != 20 or spec.get("dof") != 15 or spec.get("lhs_master_seed") != master or len(spec.get("lhs_algorithm", ())) != 4 or len(member_seeds) != 20 or len(set(member_seeds)) != 20: raise VerifyError("PHYSICS_AXIS_SEEDS_LHS")
    bounds = [[-.12, .12]] * 3 + [[.2, .8]] * 8 + [[.02, .08]] * 4; params = {}
    for axis, (name, limits) in enumerate(zip(PHYSICS_AXES, bounds)):
        stratum = permutation(int(master), axis)[ordinal - 1]; params[name] = limits[0] + (limits[1] - limits[0]) * (stratum + .5) / 20
    params["q270"] = -(params["q0"] + params["q90"] + params["q180"]) / 3
    return params, {"kind": "PHYSICS_FISHER_YATES_MIDPOINT_LHS", "master_seed": master, "member_identity_seed": member_seeds[ordinal - 1], "seed_index_zero_based": ordinal - 1, "lhs_jitter": False}


def _components(nodes: Sequence[str], edges: Sequence[Mapping[str, Any]]) -> int:
    unseen, count = set(nodes), 0
    while unseen:
        count += 1; frontier = [unseen.pop()]
        while frontier:
            current = frontier.pop()
            neighbours = set()
            for edge in edges:
                if edge["weight"] > 0 and edge["a"] == current: neighbours.add(edge["b"])
                if edge["weight"] > 0 and edge["b"] == current: neighbours.add(edge["a"])
            for item in neighbours & unseen: unseen.remove(item); frontier.append(item)
    return count


def verify_cad(value: Mapping[str, Any], family: str, ordinal: int, params: Mapping[str, float]) -> str:
    expected_keys = {"schema_version", "ownership_cells", "slot_placements", "volume_root_witnesses", "u4_exception_witnesses", "general_minima", "exception_minima", "reduced_graph", "actual_fluid_graph", "random_zero_edge_witnesses", "thresholds", "thresholds_copied_as_measurements", "complete_witness_semantics"}
    if set(value) != expected_keys or value["schema_version"] != "gen_enc_fast_b1_member_cad_static_v1" or value["thresholds_copied_as_measurements"] or not value["complete_witness_semantics"]: raise VerifyError("CAD_TOP_LEVEL")
    owners = value["ownership_cells"]
    if len(owners) != 5 or [x["cell_id"] for x in owners] != ["CELL_CENTRAL", "CELL_SECTOR_0", "CELL_SECTOR_90", "CELL_SECTOR_180", "CELL_SECTOR_270"] or any(x["positive_overlap_volume_m3"] != 0 for x in owners): raise VerifyError("OWNERSHIP_CELLS")
    slots = value["slot_placements"]
    if len(slots) != 20 or len({x["slot_id"] for x in slots}) != 20 or [x["sector"] for x in slots] != [s for s in SECTORS for _ in range(5)] or any(len(x["coordinates_m"]) != 3 for x in slots): raise VerifyError("SLOT_PLACEMENT")
    roots = value["volume_root_witnesses"]
    if len(roots) != 4 or [x["sector"] for x in roots] != list(SECTORS): raise VerifyError("ROOT_COUNT")
    weights = [math.exp(params[f"q{s}"]) for s in SECTORS]; total = sum(weights)
    for witness, weight in zip(roots, weights):
        target = .60 * 3.014899604922098e-5 * weight / total; root = witness["root_length_m"]; measured = 2.1848e-6 + 1.094e-4 * root
        if witness["bracket_m"] != [.002, .030] or witness["iterations"] != 80 or not math.isclose(witness["target_volume_m3"], target, abs_tol=1e-18) or not math.isclose(witness["measured_volume_m3"], measured, abs_tol=1e-18) or not math.isclose(witness["residual_m3"], measured - target, abs_tol=1e-18): raise VerifyError("ROOT_SEMANTICS")
    suffixes = ("RIM_BOTTOM", "RIM_TOP", "SHOULDER_LOWER", "SHOULDER_UPPER", "RIM")
    expected_ids = [f"IFX_U4_{int(s):03d}_{suffix}" for s in SECTORS for suffix in suffixes]; exceptions = value["u4_exception_witnesses"]
    if len(exceptions) != 20 or [x["exception_id"] for x in exceptions] != expected_ids or any(len(x["local_coordinates_m"]) != 2 or x["excluded_only_from"] != "GENERAL_MINIMA" for x in exceptions): raise VerifyError("U4_EXACT_IDS_COORDINATES")
    general, exception = value["general_minima"], value["exception_minima"]
    if not general["feature_candidates"] or not general["load_path_candidates"] or general["measured_minimum_feature_m"] != min(x["measured_m"] for x in general["feature_candidates"]) or general["measured_minimum_load_path_m"] != min(x["measured_m"] for x in general["load_path_candidates"]): raise VerifyError("GENERAL_MEASURED_MIN")
    if exception["exception_ids"] != expected_ids or exception["measured_minimum_feature_m"] != min(x["feature_m"] for x in exceptions) or exception["measured_minimum_load_path_m"] != min(x["load_path_m"] for x in exceptions): raise VerifyError("EXCEPTION_MEASURED_MIN")
    reduced, actual = value["reduced_graph"], value["actual_fluid_graph"]
    if reduced["nodes"] != ["P0", "P90", "P180", "P270"] or len(reduced["edges"]) != 6 or reduced["component_count"] != _components(reduced["nodes"], reduced["edges"]): raise VerifyError("REDUCED_GRAPH")
    if actual["nodes"] != ["PLENUM", "P0", "P90", "P180", "P270"] or len(actual["edges"]) != 4 or actual["component_count"] != 1 or actual["component_count"] != _components(actual["nodes"], actual["edges"]): raise VerifyError("ACTUAL_FLUID_GRAPH")
    zero_ids = [x["edge_id"] for x in reduced["edges"] if x["weight"] == 0] if family == FAMILIES[2] else []
    zeros = value["random_zero_edge_witnesses"]
    if [x["edge_id"] for x in zeros] != zero_ids or any(x != {"edge_id": x["edge_id"], "exact_value": 0.0, "generator_branch": "U_LT_0P5_ATOM", "verified_exact_zero": True} for x in zeros): raise VerifyError("RANDOM_ZERO_EDGE")
    return "ELIGIBLE" if general["measured_minimum_feature_m"] >= value["thresholds"]["minimum_general_feature_m"] and general["measured_minimum_load_path_m"] >= value["thresholds"]["minimum_general_load_path_m"] and actual["component_count"] == 1 else "COST_INELIGIBLE"


def schemas(root: Path) -> dict[str, Any]:
    names = ("member_identity", "partial_family_manifest", "static_audit", "independent_verification", "batch_index", "generation_terminal", "verifier_terminal", "publication_terminal")
    result = {name: json.loads((root / f"{name}.schema.json").read_text()) for name in names}
    for value in result.values(): jsonschema.Draft202012Validator.check_schema(value)
    return result


def check(value: Any, all_schemas: Mapping[str, Any], name: str) -> None:
    try: jsonschema.Draft202012Validator(all_schemas[name]).validate(value)
    except jsonschema.ValidationError as exc: raise VerifyError("SCHEMA_" + name + ":" + exc.message) from exc


def expected_paths(stage: str) -> set[str]:
    base = {f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in range(1, 6)} | {f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES} | {"batch_index.json", "static_audit.json", "independent_verification.json", "SHA256SUMS.txt", "generation_terminal.json"}
    return base if stage == "pending" else base | {"verifier_terminal.json", "publication_terminal.json"}


def verify_and_reseal(root: Path, objects: Mapping[str, Any], binding: Mapping[str, Any], schema_root: Path) -> dict[str, Any]:
    if set(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) != expected_paths("pending"): raise VerifyError("ZERO_UNLISTED_PENDING")
    all_schemas = schemas(schema_root); verified = []
    for family in FAMILIES:
        for ordinal in range(1, 6):
            path = root / f"members/{PREFIX[family]}_{ordinal:02d}.json"; member, _ = read_json(path); check(member, all_schemas, "member_identity")
            if member["task_id"] != TASK_ID or member["batch_id"] != BATCH_ID or member["family_id"] != family or member["member_id"] != f"{PREFIX[family]}_{ordinal:02d}" or member["slot_ordinal"] != ordinal or not member["failure_slot_retained"]: raise VerifyError("MEMBER_BINDING")
            expected, provenance = expected_parameters(objects, family, ordinal)
            if member["parameter_order"] != list(expected) or member["parameters"] != expected or member["input_provenance"] != provenance: raise VerifyError("IDENTITY_RECOMPUTATION")
            status = verify_cad(member["cad_static_evidence"], family, ordinal, expected)
            if member["static_status"] != status or member["claim_ceiling"] != CLAIM or member["scientific_hypothesis_status"] != "NOT_TESTED": raise VerifyError("STATIC_OR_CLAIM")
            verified.append(member["member_id"])
    for family in FAMILIES:
        manifest, _ = read_json(root / f"partial_manifests/{PREFIX[family]}.json"); check(manifest, all_schemas, "partial_family_manifest")
        if manifest["slot_ordinals"] != [1, 2, 3, 4, 5] or [x["member_id"] for x in manifest["member_entries"]] != [f"{PREFIX[family]}_{i:02d}" for i in range(1, 6)] or manifest["complete_family_manifest"]: raise VerifyError("PARTIAL_MANIFEST")
        for entry in manifest["member_entries"]:
            if sha_file(root / entry["path"]) != entry["sha256"]: raise VerifyError("MANIFEST_HASH")
    audit, _ = read_json(root / "static_audit.json"); check(audit, all_schemas, "static_audit")
    if audit["member_count"] != 20 or audit["complete_cad_witness_count"] != 20 or len(audit["member_paths"]) != 20: raise VerifyError("STATIC_AUDIT")
    generation, _ = read_json(root / "generation_terminal.json"); check(generation, all_schemas, "generation_terminal")
    if generation["status"] != "AWAITING_INDEPENDENT_VERIFICATION" or generation["success_eligible"] or generation["authority_read_count"] != 20: raise VerifyError("GENERATION_NON_SUCCESS")
    report = {"schema_version": "gen_enc_fast_b1_independent_verification_v1", "record_kind": "INDEPENDENT_VERIFICATION", "task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": binding["run_id"], "status": "PASS", "verified_member_count": 20, "verified_manifest_count": 4, "authority_read_count": 20, "artifact_count": 31, "checks": ["EXACT_NAMED_AXES", "ALL_SEED_BINDINGS", "RANDOM_BINARY64_NEXTAFTER", "PHYSICS_FISHER_YATES_MIDPOINT_LHS", "OWNERSHIP_CELLS", "SLOT_PLACEMENTS_20_PER_MEMBER", "VOLUME_ROOT_WITNESSES_4_PER_MEMBER", "U4_EXCEPTION_IDS_COORDINATES_20_PER_MEMBER", "GENERAL_AND_EXCEPTION_MEASURED_MINIMA", "REDUCED_AND_ACTUAL_FLUID_GRAPHS", "RANDOM_EXACT_ZERO_EDGE_WITNESSES", "ZERO_UNLISTED_CARDINALITY"], "resealed": True, "claim_ceiling": CLAIM, "final_test_read": False}
    check(report, all_schemas, "independent_verification"); atomic(root / "independent_verification.json", report)
    index, _ = read_json(root / "batch_index.json"); index["verification_complete"] = True; check(index, all_schemas, "batch_index"); atomic(root / "batch_index.json", index)
    verifier = {"schema_version": "gen_enc_fast_b1_verifier_terminal_v1", "record_kind": "VERIFIED_STAGING_NON_PUBLICATION", "task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": binding["run_id"], "status": "VERIFIED_RESEALED_AWAITING_PUBLICATION", "authority_read_count": 20, "verified_member_count": 20, "artifact_count": 31, "publication_started": False, "success_terminal_written": False, "claim_ceiling": CLAIM, "final_test_read": False}
    check(verifier, all_schemas, "verifier_terminal"); atomic(root / "verifier_terminal.json", verifier)
    publication = {"schema_version": "gen_enc_fast_b1_publication_terminal_v1", "record_kind": "PUBLICATION_INTENT_NON_SUCCESS", "task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": binding["run_id"], "status": "AWAITING_MULTI_TARGET_ATOMIC_PUBLICATION", "target_count": 31, "published_count": 0, "commit_pointer_written": False, "success_terminal_written": False, "claim_ceiling": CLAIM, "final_test_read": False}
    check(publication, all_schemas, "publication_terminal"); atomic(root / "publication_terminal.json", publication)
    lines = "".join(f"{sha_file(p)}  {p.relative_to(root).as_posix()}\n" for p in sorted(root.rglob("*")) if p.is_file() and p.name != "SHA256SUMS.txt"); (root / "SHA256SUMS.txt").write_bytes(lines.encode("ascii"))
    if set(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) != expected_paths("verified"): raise VerifyError("ZERO_UNLISTED_VERIFIED")
    return {"status": "VERIFIED_RESEALED_NOT_PUBLISHED", "authority_read_count": 20, "verified_member_count": 20, "artifact_count": 31}


def pointer(document: Any, address: str) -> Any:
    node = document
    if address == "": return node
    for token in address[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def _repo_path(repo: Path, text: str) -> Path:
    path = Path(text)
    if path.is_absolute(): raise VerifyError("ABSOLUTE_BINDING")
    result = (repo / path).resolve()
    if not result.is_relative_to(repo.resolve()): raise VerifyError("CONTAINMENT")
    return result


def formal_gate(repo: Path, release_path: Path, attestation_path: Path, schema_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    release, raw = read_json(release_path); attestation, araw = read_json(attestation_path)
    release_schema = json.loads((schema_root / "release.schema.json").read_text()); att_schema = json.loads((schema_root / "guardian_attestation.schema.json").read_text())
    side_schema = json.loads((schema_root / "side_record.schema.json").read_text()); release_schema["properties"]["roots"] = side_schema["$defs"]["roots"]
    jsonschema.Draft202012Validator(release_schema).validate(release); jsonschema.Draft202012Validator(att_schema).validate(attestation)
    if release["record_kind"] != "RELEASE" or not release["authoritative"] or release["attempt"] != 1 or release["task_id"] != TASK_ID or release["batch_id"] != BATCH_ID or release["commands_exact"] != ["preflight", "generate-staging", "verify", "publish", "recover", "package-results"] or release["mode"] != "FORMAL_B1_EXACT_20": raise VerifyError("RELEASE")
    if release["run_id"] != derive_run_id(release): raise VerifyError("RUN_ID_DERIVATION")
    if release["authority_allowlist_sha256"] != ALLOWLIST_SHA or release["guardian_review_sha256"] != GUARDIAN_SHA or datetime.fromisoformat(release["expires_at"]).astimezone(timezone.utc) <= datetime.now(timezone.utc): raise VerifyError("RELEASE_BOUNDARY")
    if attestation["release_sha256"] != sha_bytes(raw) or attestation["run_id"] != release["run_id"] or not attestation["one_way"]: raise VerifyError("ATTESTATION")
    for name in ("source", "schema", "command"):
        manifest = _repo_path(repo, release[f"{name}_manifest_path"])
        if sha_file(manifest) != release[f"{name}_manifest_sha256"]: raise VerifyError("MANIFEST_HASH:" + name)
    roots = {name: _repo_path(repo, value) for name, value in release["roots"].items()}
    values = list(roots.values())
    if len({str(x).casefold() for x in values}) != len(values) or any(a.is_relative_to(b) or b.is_relative_to(a) for i, a in enumerate(values) for b in values[i + 1:]): raise VerifyError("ROOTS_MUTUALLY_EXCLUSIVE")
    allow_path = _repo_path(repo, release["authority_allowlist_path"])
    if sha_file(allow_path) != ALLOWLIST_SHA: raise VerifyError("ALLOWLIST_HASH")
    allow = json.loads(allow_path.read_text()); triples = [{"path": x["path"], "sha256": x["sha256"], "pointer": x["pointer"]} for x in allow["entries"]]
    if len(triples) != 20 or release["authority_triples"] != triples or any(x["technical_fixture"] for x in allow["entries"]): raise VerifyError("TRIPLES")
    side = roots["side_records"]; consumed, _ = read_json(side / "CONSUMED.json"); side_schema = json.loads((schema_root / "side_record.schema.json").read_text()); jsonschema.Draft202012Validator(side_schema).validate(consumed)
    expected_side = {"task_id": TASK_ID, "batch_id": BATCH_ID, "run_id": release["run_id"], "release_sha256": sha_bytes(raw), "attestation_sha256": sha_bytes(araw), "authority_allowlist_sha256": ALLOWLIST_SHA, "source_manifest_sha256": release["source_manifest_sha256"], "schema_manifest_sha256": release["schema_manifest_sha256"], "command_manifest_sha256": release["command_manifest_sha256"], "commands_exact": release["commands_exact"], "mode": release["mode"], "roots": release["roots"]}
    if consumed["state"] != "CONSUMED" or consumed["revoked"] or any(consumed.get(k) != v for k, v in expected_side.items()) or (side / "REVOKED.json").exists(): raise VerifyError("CONSUMPTION_REVOCATION")
    objects = {}
    for entry in allow["entries"]:
        path = _repo_path(repo, entry["path"])
        if sha_file(path) != entry["sha256"]: raise VerifyError("AUTHORITY_HASH")
        selected = pointer(json.loads(path.read_text()), entry["pointer"]); shape = entry["object_shape"]
        kind = "object" if isinstance(selected, dict) else "array" if isinstance(selected, list) else type(selected).__name__
        if kind != shape["type"]: raise VerifyError("AUTHORITY_SHAPE_TYPE")
        if isinstance(selected, dict) and (list(selected) != shape["field_names"] or any(len(selected[k]) != count for k, count in shape.get("array_counts", {}).items())): raise VerifyError("AUTHORITY_SHAPE_FIELDS")
        if isinstance(selected, list) and (len(selected) != shape["count"] or selected and isinstance(selected[0], dict) and (list(selected[0]) != shape["item_field_names"] or not all(set(x) == set(selected[0]) for x in selected))): raise VerifyError("AUTHORITY_SHAPE_ARRAY")
        if not isinstance(selected, (dict, list)) and "value" in shape and selected != shape["value"]: raise VerifyError("AUTHORITY_SHAPE_VALUE")
        objects[entry["purpose"]] = selected
    binding = {"run_id": release["run_id"], "release_sha256": sha_bytes(raw), "staging": roots["staging"]}
    return objects, binding


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(); p.add_argument("verify", choices=["verify"])
    for name in ("repo-root", "release", "guardian-attestation", "schema-root"): p.add_argument("--" + name, required=True, type=Path)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    ns = parser().parse_args(argv)
    try:
        objects, binding = formal_gate(ns.repo_root.resolve(), ns.release.resolve(), ns.guardian_attestation.resolve(), ns.schema_root.resolve())
        print(json.dumps(verify_and_reseal(binding["staging"], objects, binding, ns.schema_root.resolve()), sort_keys=True)); return 0
    except BaseException as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": type(exc).__name__ + ":" + str(exc)}, sort_keys=True), file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
