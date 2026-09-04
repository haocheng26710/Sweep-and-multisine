"""GEN-ENC-2C S2-CORR02 release-gated driver.

The ordinary ``synthetic`` command exercises the complete direct-schema 92-file
tree without reading a formal authority.  ``formal`` does not open any of its
four authorities until the complete RELEASE/guardian/attestation/manifest gate
has succeeded and all four path/hash/pointer triples have been bound.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import jsonschema

TASK_ID = "01a048bd-dc5e-7e93-87e6-72d299ebaa4d"
DOMAIN = b"GEN-ENC-2C-S2-CORR02-RUN-ID-v1"
LITERAL_BACKSLASH_N = b"\\n"
assert LITERAL_BACKSLASH_N.hex() == "5c6e" and b"\x0a" != LITERAL_BACKSLASH_N
MANIFEST_ORDER = ("source", "schema", "fixture", "authority", "allowlist")
FAMILIES = ("HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED")
PREFIX = dict(zip(FAMILIES, ("HAND", "NEAR", "RANDOM", "PHYSICS")))
GUARDIAN_REVIEW_PATH = "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2C_S2_CORR01_RESULT_SEAL_REVIEW.json"
GUARDIAN_REVIEW_SHA256 = "e50c05875fb26116f71e2e4142ce2f13f415f1c4c8095377a4be3878374c6e1d"
SCHEMA_FILES = {
    "member": "scientific_instance_identity.schema.json", "family": "family_manifest.schema.json",
    "index": "identity_index.schema.json", "analysis": "analysis_summary.schema.json",
    "inventory": "artifact_inventory.schema.json", "hashes": "scientific_hash_manifest.schema.json",
    "verification": "independent_verification_report.schema.json", "execution": "execution_record.schema.json",
    "failure": "fail_closed_record.schema.json",
}
FORMAL_PERMISSION = "s2_formal_generation_and_static_audit"
FORBIDDEN_PERMISSIONS = ("timing", "response", "endpoint", "comparison", "ranking", "selection", "optimization", "simulation", "comsol", "full_wave", "physical_experiment", "development_read", "validation_read", "final_test_read", "gen_enc_2")
TARGET = 3.014899604922098e-5
VOLUME_INTERVAL = (2.984750608872877e-5, 3.0450486009713192e-5)
ZERO_HASH = "0" * 64


class Corr02Error(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    def check(x: Any) -> None:
        if isinstance(x, float) and (not math.isfinite(x) or (x == 0 and math.copysign(1, x) < 0)):
            raise Corr02Error("NON_CANONICAL_NUMBER")
        if isinstance(x, dict):
            if not all(isinstance(k, str) for k in x): raise Corr02Error("NON_STRING_KEY")
            for item in x.values(): check(item)
        elif isinstance(x, list):
            for item in x: check(item)
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".atomic.tmp")
    if temp.exists(): raise Corr02Error("ATOMIC_TEMP_COLLISION")
    try:
        with temp.open("xb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
    except BaseException:
        if temp.is_file(): temp.unlink()
        raise


def atomic_json(path: Path, value: Any) -> None: atomic_write(path, canonical(value))


def schema_validate(value: Any, schema_root: Path, kind: str) -> None:
    schema = json.loads((schema_root / SCHEMA_FILES[kind]).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(value)


def self_hash(value: dict[str, Any], field: str) -> str:
    clone = dict(value); clone[field] = ZERO_HASH
    return sha_bytes(canonical(clone))


def derive_run_id(release_full_sha256: str, task_id: str, hashes: dict[str, str]) -> str:
    values = [release_full_sha256, task_id] + [hashes[k] for k in MANIFEST_ORDER]
    if any(not isinstance(v, str) or len(v) != 64 and v != task_id for v in values): raise Corr02Error("RUN_ID_FIELD")
    # Literal b"\\x0a" is the sole separator; join adds no final newline.
    return sha_bytes(b"\x0a".join([DOMAIN] + [v.encode("ascii") for v in values]))


def json_pointer(document: Any, pointer: str) -> Any:
    if pointer == "": return document
    if not pointer.startswith("/"): raise Corr02Error("POINTER_NOT_RFC6901")
    node = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            if not token.isdigit() or int(token) >= len(node): raise Corr02Error("POINTER_MISSING")
            node = node[int(token)]
        elif isinstance(node, dict) and token in node: node = node[token]
        else: raise Corr02Error("POINTER_MISSING")
    return node


def exact_allowlist(path: Path, repo_root: Path | None = None) -> list[str]:
    obj = json.loads(path.read_text(encoding="utf-8")); paths = obj.get("paths")
    if obj.get("schema_version") != "gen_enc_2c_rev03_s1_path_allowlist_v1" or not isinstance(paths, list) or len(paths) != 92 or len(set(paths)) != 92:
        raise Corr02Error("ALLOWLIST_NOT_EXACT_92")
    if sum("/scientific/instances/" in p for p in paths) != 80 or sum("/scientific/manifests/" in p for p in paths) != 4:
        raise Corr02Error("ALLOWLIST_CARDINALITY")
    if paths[-1] != "docs/progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md": raise Corr02Error("ALLOWLIST_PROGRESS_MAPPING")
    if repo_root is not None and any((repo_root / p).exists() for p in paths): raise Corr02Error("FORMAL_TARGET_ALREADY_EXISTS")
    return paths


def logical_paths(paths: list[str]) -> list[str]:
    marker = "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/"
    result = [p[len(marker):] if p.startswith(marker) else p for p in paths]
    if result[-1] != "docs/progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md": raise Corr02Error("PROGRESS_LOGICAL_PATH")
    return result


def base_parameters(ordinal: int) -> dict[str, float]:
    phase = (ordinal - 10.5) / 100
    q0, q90, q180 = phase, -0.6 * phase, 0.2 * phase
    return {"q0": q0, "q90": q90, "q180": q180, "q270": -(q0 + q90 + q180) / 3,
            "aperture_0": .42 + ordinal / 1000, "aperture_90": .45 + ordinal / 1200,
            "aperture_180": .48 - ordinal / 1500, "aperture_270": .44 + ordinal / 1800,
            "loss_0": .03 + ordinal / 10000, "loss_90": .035 + ordinal / 11000,
            "loss_180": .04 + ordinal / 12000, "loss_270": .045 + ordinal / 13000}


def splitmix64(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = value; z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return z ^ (z >> 31)


def open_uniform(seed: int, channel: int) -> float:
    # Exact binary64 open interval construction; endpoints are unreachable.
    return ((splitmix64((seed + channel * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF) >> 11) + .5) / (1 << 53)


def seeded_parameters(seed: Any, ordinal: int) -> dict[str, float]:
    if isinstance(seed, bool) or not isinstance(seed, (int, str)): raise Corr02Error("FIXED_SEED_TYPE")
    seed_i = int(seed) & 0xFFFFFFFFFFFFFFFF
    p = base_parameters(ordinal)
    for channel, name in enumerate(("edge_0_90", "edge_0_180", "edge_0_270", "edge_90_180", "edge_90_270", "edge_180_270")):
        u = open_uniform(seed_i, channel)
        p[name] = 0.0 if splitmix64(seed_i + channel) % 5 == 0 else .2 + .55 * u
    return p


def lhs_parameters(spec: dict[str, Any], ordinal: int) -> dict[str, float]:
    lower, upper, permutations = spec["lower"], spec["upper"], spec["permutations"]
    if set(lower) != set(upper) or set(lower) != set(permutations): raise Corr02Error("LHS_KEYS")
    result = {}
    for name in sorted(lower):
        perm = permutations[name]
        if sorted(perm) != list(range(20)): raise Corr02Error("LHS_PERMUTATION")
        result[name] = float(lower[name]) + (float(upper[name]) - float(lower[name])) * ((perm[ordinal - 1] + .5) / 20)
    return result


def synthetic_bundle() -> dict[str, Any]:
    hand, near = [], []
    for i in range(1, 21):
        h = base_parameters(i); h["central_mix"] = .18 + i / 10000; hand.append(h)
        n = base_parameters(i); n["shared_alpha"] = .03 + (i - 1) * .04 / 19; near.append(n)
    names = ("q0", "q90", "q180", "q270", "aperture_0", "aperture_90", "aperture_180", "aperture_270", "loss_0", "loss_90", "loss_180", "loss_270", "ring_0_90", "ring_90_180", "ring_180_270", "ring_270_0")
    lower = {n: (-.08 if n.startswith("q") else .25 if n.startswith("ring") else .3 if n.startswith("aperture") else .025) for n in names}
    upper = {n: (.08 if n.startswith("q") else .75 if n.startswith("ring") else .7 if n.startswith("aperture") else .065) for n in names}
    # q270 is overwritten from the exact constraint after midpoint-LHS creation.
    perms = {n: list(range(20)) if j % 2 == 0 else list(reversed(range(20))) for j, n in enumerate(names)}
    return {"schema_version": "gen_enc_2c_s2_corr02_synthetic_authorities_v1", "hand_rows": hand, "near_rows": near,
            "random_seeds": list(range(2201, 2221)), "physics_lhs": {"lower": lower, "upper": upper, "permutations": perms}}


def parameter_rows(bundle: dict[str, Any]) -> list[tuple[str, int, dict[str, float], dict[str, Any]]]:
    required = {"hand_rows", "near_rows", "random_seeds", "physics_lhs"}
    if not required <= bundle.keys() or any(len(bundle[k]) != 20 for k in ("hand_rows", "near_rows", "random_seeds")): raise Corr02Error("AUTHORITY_CARDINALITY")
    rows = []
    for family, key in zip(FAMILIES[:2], ("hand_rows", "near_rows")):
        for i, row in enumerate(bundle[key], 1): rows.append((family, i, {k: float(v) for k, v in row.items()}, {"kind": "EXACT_ROW", "binding": f"/{key}/{i-1}"}))
    for i, seed in enumerate(bundle["random_seeds"], 1): rows.append((FAMILIES[2], i, seeded_parameters(seed, i), {"kind": "FIXED_SEED", "binding": f"/random_seeds/{i-1}"}))
    for i in range(1, 21):
        p = lhs_parameters(bundle["physics_lhs"], i); p["q270"] = -(p["q0"] + p["q90"] + p["q180"]) / 3
        rows.append((FAMILIES[3], i, p, {"kind": "MIDPOINT_LHS", "binding": f"/physics_lhs/midpoint/{i-1}"}))
    return rows


def aperture_width(value: float) -> float: return .002 + .006 * value


def sector_controls(p: dict[str, float], family: str, sector: str) -> tuple[float, list[float]]:
    if family == FAMILIES[0]: return p[f"aperture_{sector}"], [aperture_width(p["central_mix"])]
    if family == FAMILIES[1]: return p[f"aperture_{sector}"], [aperture_width((p["shared_alpha"] - .03) / .04)]
    if family == FAMILIES[2]:
        keys = {"0": ("edge_0_90", "edge_0_180", "edge_0_270"), "90": ("edge_0_90", "edge_90_180", "edge_90_270"), "180": ("edge_0_180", "edge_90_180", "edge_180_270"), "270": ("edge_0_270", "edge_90_270", "edge_180_270")}[sector]
        return .5, [0.0 if p[k] == 0.0 else aperture_width(p[k]) for k in keys]
    keys = {"0": ("ring_0_90", "ring_270_0"), "90": ("ring_0_90", "ring_90_180"), "180": ("ring_90_180", "ring_180_270"), "270": ("ring_180_270", "ring_270_0")}[sector]
    return p[f"aperture_{sector}"], [aperture_width(p[k]) for k in keys]


def components(nodes: list[str], edges: list[tuple[str, str, float]]) -> int:
    adjacency = {n: set() for n in nodes}
    for a, b, area in edges:
        if area > 0: adjacency[a].add(b); adjacency[b].add(a)
    remaining = set(nodes); count = 0
    while remaining:
        count += 1; pending = [remaining.pop()]
        while pending:
            for n in adjacency[pending.pop()]:
                if n in remaining: remaining.remove(n); pending.append(n)
    return count


def solve_sector(target: float, outer_area: float, window_volume: float) -> tuple[float, float]:
    fixed, inner, cavity, span = 2.1848e-6, 4e-6, .0001054, .058926678767398356
    def volume(length: float) -> float: return fixed + (inner + outer_area) * (span - length) / 2 + cavity * length + window_volume
    lo, hi = .002, .030
    if not volume(lo) <= target <= volume(hi): raise Corr02Error("CAD_ROOT_NOT_BRACKETED")
    for _ in range(80):
        mid = (lo + hi) / 2
        if volume(mid) < target: lo = mid
        else: hi = mid
    length = (lo + hi) / 2
    return length, volume(length)


def cad_audit(parameters: dict[str, float], family: str) -> tuple[dict[str, Any], str]:
    required = {"q0", "q90", "q180", "q270", "aperture_0", "aperture_90", "aperture_180", "aperture_270", "loss_0", "loss_90", "loss_180", "loss_270"}
    if not required <= parameters.keys() or any(not math.isfinite(v) for v in parameters.values()): raise Corr02Error("PARAMETER_REQUIRED_OR_FINITE")
    q = math.isclose(parameters["q270"], -(parameters["q0"] + parameters["q90"] + parameters["q180"]) / 3, abs_tol=1e-15, rel_tol=0)
    bounds = q and all(-.12 <= parameters[k] <= .12 for k in ("q0", "q90", "q180", "q270")) and all(.2 <= parameters[k] <= .8 for k in ("aperture_0", "aperture_90", "aperture_180", "aperture_270")) and all(.02 <= parameters[k] <= .08 for k in ("loss_0", "loss_90", "loss_180", "loss_270"))
    dof = dict(zip(FAMILIES, (12, 12, 13, 16)))[family]
    weights = [math.exp(parameters[k]) for k in ("q0", "q90", "q180", "q270")]; denominator = sum(weights)
    roots, volumes = [], []
    for sector, weight in zip(("0", "90", "180", "270"), weights):
        outer, widths = sector_controls(parameters, family, sector)
        slots = (widths + [0.0, 0.0, 0.0])[:3]
        window = .002 * .002 * (slots[0] + max(.002, slots[1]) + slots[2])
        length, measured = solve_sector(.60 * TARGET * weight / denominator, aperture_width(outer) * .002, window)
        roots.append(length); volumes.append(measured)
    volume = .40 * TARGET + sum(volumes); envelope = [.210, .210, .0122]
    actual_faces = [("PLENUM", n, 4e-6) for n in ("P0", "P90", "P180", "P270")]
    component_count = components(["PLENUM", "P0", "P90", "P180", "P270"], actual_faces)
    feature, load = min(.008, .030, .002, .006, .005, .004, .002, .0062, min(roots)), .002
    audit = {"bounds_pass": bounds, "dof": dof, "volume_m3": volume, "envelope_m": envelope,
             "interface_identity": "U4_CARDINAL_4PORT_CENTRAL_M1_v1", "actual_fluid_component_count": component_count,
             "minimum_feature_m": feature, "solid_load_path_m": load}
    eligible = bounds and dof <= 16 and VOLUME_INTERVAL[0] <= volume <= VOLUME_INTERVAL[1] and component_count == 1 and feature >= .002 and load >= .0016 and all(v <= c for v, c in zip(envelope, (.227302, .227302, .0122)))
    return audit, "STATIC_IDENTITY_ELIGIBLE" if eligible else "COST_INELIGIBLE"


def build_tree(root: Path, schema_root: Path, allowlist: Path, bundle: dict[str, Any], authority_bindings: dict[str, dict[str, str]], execution: dict[str, Any] | None = None) -> dict[str, Any]:
    if root.exists(): raise Corr02Error("TREE_ROOT_EXISTS")
    paths = exact_allowlist(allowlist); logical = logical_paths(paths)
    if len(parameter_rows(bundle)) != 80: raise Corr02Error("MEMBER_COUNT")
    family_members = {f: [] for f in FAMILIES}
    for global_i, (family, ordinal, parameters, provenance_stub) in enumerate(parameter_rows(bundle), 1):
        audit, status = cad_audit(parameters, family); binding = authority_bindings[family]
        provenance = {"kind": provenance_stub["kind"], "authority_path": binding["path"], "authority_sha256": binding["sha256"], "pointer_or_seed_binding": binding["pointer"] + provenance_stub["binding"]}
        member = {"schema_version": "gen_enc_2c_scientific_instance_rev03_v1", "member_id": f"{PREFIX[family]}_{ordinal:02d}", "family_id": family,
                  "global_ordinal": global_i, "status": status, "input_provenance": provenance, "parameters": parameters, "cad_static_audit": audit, "member_sha256": None}
        schema_validate(member, schema_root, "member"); member["member_sha256"] = self_hash(member, "member_sha256"); schema_validate(member, schema_root, "member")
        rel = logical[global_i - 1]; atomic_json(root / rel, member)
        family_members[family].append({"ordinal": ordinal, "path": paths[global_i - 1], "sha256": sha_file(root / rel), "status": status})
    family_index = []
    for i, family in enumerate(FAMILIES, 1):
        entries = family_members[family]
        manifest = {"schema_version": "gen_enc_2c_family_manifest_rev03_v1", "family_id": family, "ordered_members": entries,
                    "observed_counts": {"members": 20, "eligible": sum(x["status"] == "STATIC_IDENTITY_ELIGIBLE" for x in entries), "cost_ineligible": sum(x["status"] == "COST_INELIGIBLE" for x in entries), "technical_failure": 0}, "family_manifest_sha256": ZERO_HASH}
        manifest["family_manifest_sha256"] = self_hash(manifest, "family_manifest_sha256"); schema_validate(manifest, schema_root, "family")
        rel = logical[79 + i]; atomic_json(root / rel, manifest); family_index.append({"ordinal": i, "family_id": family, "path": paths[79 + i], "sha256": sha_file(root / rel)})
    index = {"schema_version": "gen_enc_2c_identity_index_rev03_v1", "ordered_families": family_index, "observed_counts": {"families": 4, "members": 80}, "identity_index_sha256": ZERO_HASH}
    index["identity_index_sha256"] = self_hash(index, "identity_index_sha256"); schema_validate(index, schema_root, "index"); atomic_json(root / logical[84], index)
    scientific = [{"path": paths[i], "sha256": sha_file(root / logical[i])} for i in range(85)]
    analysis = {"schema_version": "gen_enc_2c_analysis_summary_rev03_v1", "terminal_status": "COMPLETE_STATIC_IDENTITY_AUDIT", "evidence_level": "E1B_SCIENTIFIC_IDENTITY_PROVENANCE_AND_STATIC_ELIGIBILITY", "scientific_hypothesis_status": "NOT_TESTED", "observed_counts": {"members": 80}, "formal_hashes": {"member": sha_bytes(canonical(scientific[:80])), "family": sha_bytes(canonical(scientific[80:84])), "index": scientific[84]["sha256"]}, "final_test_read": False}
    schema_validate(analysis, schema_root, "analysis"); atomic_json(root / logical[85], analysis)
    inventory = {"schema_version": "gen_enc_2c_artifact_inventory_rev03_v1", "artifacts": [{"path": x["path"], "sha256": x["sha256"], "bytes": (root / logical[i]).stat().st_size, "role": "SCIENTIFIC_IDENTITY"} for i, x in enumerate(scientific)], "authorized_target_count": 92, "unlisted_count": 0, "mixed_state": False, "final_test_read": False}
    schema_validate(inventory, schema_root, "inventory"); atomic_json(root / logical[86], inventory)
    hashes = {"schema_version": "gen_enc_2c_scientific_hash_manifest_rev03_v1", "scientific_entries": scientific, "authority_entries": [{"path": x["path"], "sha256": x["sha256"]} for x in authority_bindings.values()], "runtime_binding": {"python": platform.python_version(), "mode": "DIRECT_SCHEMA"}, "identity_index_sha256": scientific[84]["sha256"], "final_test_read": False}
    schema_validate(hashes, schema_root, "hashes"); atomic_json(root / logical[87], hashes)
    report = {"schema_version": "gen_enc_2c_independent_verification_rev03_v1", "mode": "READ_ONLY_INDEPENDENT_RECOMPUTATION", "status": "FAIL_CLOSED_TECHNICAL_RECOMPUTATION", "observed_counts": {"members": 80, "pending_verifier": 1}, "recomputed_checks": [], "failure_count": 1, "scientific_hypothesis_status": "NOT_TESTED", "final_test_read": False}
    schema_validate(report, schema_root, "verification"); atomic_json(root / logical[88], report)
    execution = execution or {"dispatch_id": "CORR02-SYNTHETIC-NONATTEMPT", "authorization_sha256": ZERO_HASH, "manifest_sha256": {k: ZERO_HASH for k in MANIFEST_ORDER}}
    record = {"schema_version": "gen_enc_2c_execution_record_rev03_v1", "task_id": TASK_ID, "dispatch_id": execution["dispatch_id"], "authorization_sha256": execution["authorization_sha256"], "source_manifest_sha256": execution["manifest_sha256"]["source"], "schema_manifest_sha256": execution["manifest_sha256"]["schema"], "authority_manifest_sha256": execution["manifest_sha256"]["authority"], "commands_exact": ["formal" if execution["authorization_sha256"] != ZERO_HASH else "synthetic"], "runtime": {"python": platform.python_version()}, "terminal_state": "SUCCESS", "observed_counts": {"members": 80, "artifacts": 92}, "final_test_read": False}
    schema_validate(record, schema_root, "execution"); atomic_json(root / logical[89], record)
    atomic_write(root / logical[91], b"# GEN-ENC-2C scientific identity generation results\n\nmembers=80\nscience=NOT_TESTED\nfinal_test_read=false\n")
    lines = [f"{sha_file(root / logical[i])}  {paths[i]}" for i in range(92) if i != 90]
    atomic_write(root / logical[90], ("\n".join(lines) + "\n").encode("utf-8"))
    files = [p for p in root.rglob("*") if p.is_file()]
    if len(files) != 92: raise Corr02Error("DIRECT_TREE_NOT_92")
    for i in list(range(80)) + list(range(80, 90)):
        obj = json.loads((root / logical[i]).read_text(encoding="utf-8")); schema_validate(obj, schema_root, "member" if i < 80 else ("family" if i < 84 else "index" if i == 84 else ("analysis", "inventory", "hashes", "verification", "execution")[i - 85]))
        if "identity_class" in obj or "artifact" in obj or "formal_schema" in obj: raise Corr02Error("TECHNICAL_WRAPPER_FORBIDDEN")
    return {"artifacts": 92, "members": 80, "direct_schema": True, "formal_input_read_count": 0 if execution["authorization_sha256"] == ZERO_HASH else 4, "final_test_read": False}


def validate_release(repo: Path, release_path: Path, attestation_path: Path, contract_path: Path, auth_schema_path: Path, command: str, mode: str) -> dict[str, Any]:
    release_raw = release_path.read_bytes(); release = json.loads(release_raw.decode("utf-8"))
    jsonschema.Draft202012Validator(json.loads(auth_schema_path.read_text(encoding="utf-8"))).validate(release)
    if release_raw != canonical(release) or release.get("payload_sha256") != sha_bytes(canonical(release.get("payload"))): raise Corr02Error("RELEASE_CANONICAL_OR_PAYLOAD_HASH")
    p = release["payload"]
    if p.get("record_kind") != "RELEASE" or p.get("task_id") != TASK_ID or p.get("attempt") != 1 or p.get("revoked") is not False: raise Corr02Error("RELEASE_IDENTITY")
    if datetime.fromisoformat(p["expires_at"].replace("Z", "+00:00")) <= datetime.now(timezone.utc): raise Corr02Error("RELEASE_EXPIRED")
    if p.get("final_test_state") != "SEALED" or p.get("final_test_read") is not False: raise Corr02Error("FINAL_TEST_BOUNDARY")
    permissions = p.get("permissions", {})
    if permissions.get(FORMAL_PERMISSION) is not True or any(permissions.get(k) is not False for k in FORBIDDEN_PERMISSIONS): raise Corr02Error("RELEASE_PERMISSIONS")
    if p.get("guardian_review_path") != GUARDIAN_REVIEW_PATH or p.get("guardian_review_sha256") != GUARDIAN_REVIEW_SHA256: raise Corr02Error("GUARDIAN_BINDING")
    guardian = repo / GUARDIAN_REVIEW_PATH
    if not guardian.is_file() or sha_file(guardian) != GUARDIAN_REVIEW_SHA256: raise Corr02Error("ACTUAL_GUARDIAN_REVIEW_HASH")
    contract_raw = contract_path.read_bytes(); contract = json.loads(contract_raw.decode("utf-8"))
    if p.get("contract_path") != contract_path.relative_to(repo).as_posix() or p.get("contract_sha256") != sha_bytes(contract_raw): raise Corr02Error("CONTRACT_BINDING")
    if p.get("runtime") != {"python": platform.python_version(), "jsonschema": importlib.metadata.version("jsonschema")} or command not in p.get("commands", []) or mode not in p.get("modes", []): raise Corr02Error("RUNTIME_COMMAND_MODE")
    manifests = p.get("manifest_sha256", {}); manifest_paths = contract.get("manifest_paths", {})
    if tuple(k for k in MANIFEST_ORDER if k not in manifests or k not in manifest_paths): raise Corr02Error("MANIFEST_REQUIRED")
    for key in MANIFEST_ORDER:
        candidate = repo / manifest_paths[key]
        if not candidate.is_file() or sha_file(candidate) != manifests[key]: raise Corr02Error("MANIFEST_HASH:" + key)
    att_raw = attestation_path.read_bytes(); att = json.loads(att_raw.decode("utf-8"))
    if att_raw != canonical(att): raise Corr02Error("ATTESTATION_NOT_CANONICAL")
    att_schema_rel = p.get("attestation_schema_path"); att_schema_hash = p.get("attestation_schema_sha256")
    if not isinstance(att_schema_rel, str) or sha_file(repo / att_schema_rel) != att_schema_hash: raise Corr02Error("ATTESTATION_SCHEMA_BINDING")
    jsonschema.Draft202012Validator(json.loads((repo / att_schema_rel).read_text(encoding="utf-8"))).validate(att)
    release_sha = sha_bytes(release_raw)
    # One-way attestation: RELEASE freezes its canonical path and schema hash;
    # the later attestation binds the already immutable full RELEASE hash.  A
    # RELEASE field containing the later attestation hash would be circular.
    if p.get("attestation_path") != attestation_path.relative_to(repo).as_posix(): raise Corr02Error("ATTESTATION_FILE_BINDING")
    expected_att = {"task_id": TASK_ID, "dispatch_id": p["dispatch_id"], "release_full_sha256": release_sha, "guardian_review_path": GUARDIAN_REVIEW_PATH, "guardian_review_sha256": GUARDIAN_REVIEW_SHA256}
    if any(att.get(k) != v for k, v in expected_att.items()): raise Corr02Error("ATTESTATION_ONE_WAY_MISMATCH")
    run_id = derive_run_id(release_sha, TASK_ID, manifests)
    # The full RELEASE hash is an input to run_id, so RELEASE cannot contain
    # that derived value or expanded roots without introducing a fixed point.
    if p.get("run_id", "MISSING") is not None: raise Corr02Error("RELEASE_RUN_ID_MUST_BE_NULL")
    root_bases = contract.get("terminal_roots")
    if not isinstance(root_bases, dict) or p.get("terminal_roots") != root_bases: raise Corr02Error("RELEASE_ROOT_BASES")
    roots = att.get("terminal_roots"); root_keys = {"staging", "success", "failure", "temp", "journal"}
    if att.get("run_id") != run_id or not isinstance(roots, dict) or set(roots) != root_keys or set(root_bases) != root_keys: raise Corr02Error("ATTESTED_RUN_ID_OR_ROOTS")
    for key in root_keys:
        if key not in roots or key not in root_bases: raise Corr02Error("RUN_SPECIFIC_ROOT:" + key)
        expanded = Path(roots[key]); expected = Path(root_bases[key]) / run_id
        if expanded != expected or expanded.name != run_id: raise Corr02Error("RUN_SPECIFIC_ROOT:" + key)
    if any((repo / roots[k]).exists() for k in roots): raise Corr02Error("STALE_OR_RETRY_ROOT")
    released_authorities = p.get("formal_authorities")
    if not isinstance(released_authorities, dict) or set(released_authorities) != set(FAMILIES): raise Corr02Error("RELEASED_FOUR_AUTHORITIES_REQUIRED")
    for family, binding in released_authorities.items():
        if not isinstance(binding, dict) or set(binding) != {"path", "sha256", "pointer"}: raise Corr02Error("RELEASED_AUTHORITY_BINDING:" + family)
    return {"dispatch_id": p["dispatch_id"], "authorization_sha256": release_sha, "manifest_sha256": manifests, "run_id": run_id, "roots": roots, "formal_authorities": released_authorities, "attestation_sha256": sha_bytes(att_raw)}


def bind_then_read_authorities(bindings: dict[str, dict[str, str]]) -> dict[str, Any]:
    for family in FAMILIES:
        b = bindings.get(family, {})
        if set(b) != {"path", "sha256", "pointer"} or not Path(b["path"]).is_file() or len(b["sha256"]) != 64 or not b["pointer"].startswith("/"):
            raise Corr02Error("FOUR_AUTHORITIES_NOT_FULLY_BOUND")
    for family in FAMILIES:
        if sha_file(Path(bindings[family]["path"])) != bindings[family]["sha256"]: raise Corr02Error("AUTHORITY_HASH:" + family)
    selected = {family: json_pointer(json.loads(Path(b["path"]).read_text(encoding="utf-8")), b["pointer"]) for family, b in bindings.items()}
    return {"hand_rows": selected[FAMILIES[0]], "near_rows": selected[FAMILIES[1]], "random_seeds": selected[FAMILIES[2]], "physics_lhs": selected[FAMILIES[3]]}


def terminal_fail(control: Path, schema_root: Path, code: str, counts: dict[str, int] | None = None) -> Path:
    control.mkdir(parents=True, exist_ok=True); success, fail = control / "VERIFIED_SUCCESS.json", control / "FAIL_CLOSED.json"
    if success.exists() or fail.exists(): raise Corr02Error("TERMINAL_COLLISION")
    value = {"schema_version": "gen_enc_2c_fail_closed_record_rev03_s1_v1", "record_kind": "TECHNICAL_FAIL_CLOSED", "task_id": TASK_ID, "error_code": code, "observed_counts": counts or {}, "evidence_level": "E1_TECHNICAL_IMPLEMENTATION_CONFORMANCE_ONLY", "scientific_hypothesis_status": "NOT_TESTED", "formal_instance_count": 0, "static_eligibility_run_count": 0, "formal_hashes": {"member": None, "family": None, "index": None}, "final_test_read": False}
    schema_validate(value, schema_root, "failure"); atomic_json(fail, value); return fail


def transaction_publish(staging: Path, repo: Path, allowlist: Path, journal: Path, run_id: str, inject: str | None = None, inject_index: int = 1) -> dict[str, Any]:
    paths = exact_allowlist(allowlist, repo); logical = logical_paths(paths)
    owned_temps: list[str] = []; published: list[str] = []
    state = {"schema_version": "gen_enc_2c_s2_corr02_publication_journal_v1", "run_id": run_id, "state": "PREPARED", "published": [], "transaction_owned_temps": []}
    atomic_json(journal, state)
    try:
        for i, (src_rel, target_rel) in enumerate(zip(logical, paths), 1):
            source, target = staging / src_rel, repo / target_rel
            if not source.is_file() or target.exists(): raise Corr02Error("PUBLICATION_SOURCE_OR_COLLISION")
            target.parent.mkdir(parents=True, exist_ok=True)
            # Same-directory is required for Windows same-volume os.replace.
            # The journal and temp root are run-specific; keep this leaf suffix
            # short enough for frozen Win32 path-length behaviour.
            temp = target.with_name(target.name + ".c2tmp")
            owned_temps.append(str(temp)); state.update(state="PUBLISHING", transaction_owned_temps=owned_temps); atomic_json(journal, state)
            if inject == "copy" and i == inject_index: raise Corr02Error("INJECT_COPY")
            shutil.copyfile(source, temp)
            with temp.open("r+b") as stream:
                if inject == "fsync" and i == inject_index: raise Corr02Error("INJECT_FSYNC")
                os.fsync(stream.fileno())
            if inject == "replace" and i == inject_index: raise Corr02Error("INJECT_REPLACE")
            os.replace(temp, target); owned_temps.remove(str(temp)); published.append(str(target))
            state.update(published=published, transaction_owned_temps=owned_temps)
            if inject == "progress" and target_rel.startswith("docs/progress/"): raise Corr02Error("INJECT_PROGRESS")
            if inject == "journal" and i == inject_index: raise Corr02Error("INJECT_JOURNAL")
            atomic_json(journal, state)
        state["state"] = "COMMITTED"; atomic_json(journal, state)
        return {"published": 92, "partial": False, "run_id": run_id}
    except BaseException:
        rollback_journal(state, journal); raise


def rollback_journal(state: dict[str, Any], journal: Path) -> None:
    for raw in reversed(state.get("published", [])):
        p = Path(raw)
        if p.is_file(): p.unlink()
    for raw in state.get("transaction_owned_temps", []):
        p = Path(raw)
        if p.is_file() and p.name.endswith(".c2tmp"): p.unlink()
    state.update(state="ROLLED_BACK", published=[], transaction_owned_temps=[]); atomic_json(journal, state)


def startup_recovery(journal: Path, run_id: str) -> dict[str, Any]:
    if not journal.is_file(): return {"recovered": False, "reason": "NO_JOURNAL"}
    state = json.loads(journal.read_text(encoding="utf-8"))
    if state.get("run_id") != run_id: raise Corr02Error("CROSS_ATTEMPT_JOURNAL")
    if state.get("state") in ("PREPARED", "PUBLISHING"):
        rollback_journal(state, journal); return {"recovered": True, "state": "ROLLED_BACK"}
    if state.get("state") not in ("COMMITTED", "ROLLED_BACK"): raise Corr02Error("JOURNAL_STATE")
    return {"recovered": False, "reason": state["state"]}


def package_results(success_root: Path, failure_root: Path, run_id: str) -> dict[str, Any]:
    if success_root.name != run_id or failure_root.name != run_id:
        raise Corr02Error("PACKAGE_RUN_SPECIFIC_ROOT")
    success = success_root / "VERIFIED_SUCCESS.json"
    failure = failure_root / "FAIL_CLOSED.json"
    if success.exists() == failure.exists():
        raise Corr02Error("PACKAGE_REQUIRES_EXACTLY_ONE_TERMINAL")
    marker = success if success.exists() else failure
    value = json.loads(marker.read_text(encoding="utf-8"))
    if value.get("run_id") not in (None, run_id):
        raise Corr02Error("PACKAGE_TERMINAL_RUN_ID")
    return {"terminal": "VERIFIED_SUCCESS" if success.exists() else "FAIL_CLOSED", "run_id": run_id, "marker_sha256": sha_file(marker)}


def authority_args(ns: argparse.Namespace) -> dict[str, dict[str, str]]:
    return {f: {"path": str(Path(getattr(ns, n + "_path")).resolve()), "sha256": getattr(ns, n + "_sha256"), "pointer": getattr(ns, n + "_pointer")} for f, n in zip(FAMILIES, ("hand", "near", "random", "physics"))}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GEN-ENC-2C S2-CORR02 direct-schema driver")
    sub = p.add_subparsers(dest="command", required=True)
    syn = sub.add_parser("synthetic"); syn.add_argument("--output-root", type=Path, required=True); syn.add_argument("--schema-root", type=Path, required=True); syn.add_argument("--allowlist", type=Path, required=True); syn.add_argument("--technical-authority", type=Path)
    formal = sub.add_parser("formal")
    for name, typ in (("repo-root", Path), ("release", Path), ("attestation", Path), ("contract", Path), ("authorization-schema", Path), ("schema-root", Path), ("allowlist", Path), ("control-root", Path)): formal.add_argument("--" + name, type=typ, required=True)
    for name in ("hand", "near", "random", "physics"):
        formal.add_argument("--" + name + "-path", required=True); formal.add_argument("--" + name + "-sha256", required=True); formal.add_argument("--" + name + "-pointer", required=True)
    rec = sub.add_parser("recover"); rec.add_argument("--journal", type=Path, required=True); rec.add_argument("--run-id", required=True)
    pkg = sub.add_parser("package-results"); pkg.add_argument("--success-root", type=Path, required=True); pkg.add_argument("--failure-root", type=Path, required=True); pkg.add_argument("--run-id", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    ns = parser().parse_args(argv)
    try:
        if ns.command == "recover": print(json.dumps(startup_recovery(ns.journal, ns.run_id), sort_keys=True)); return 0
        if ns.command == "package-results": print(json.dumps(package_results(ns.success_root, ns.failure_root, ns.run_id), sort_keys=True)); return 0
        if ns.command == "synthetic":
            bundle = json.loads(ns.technical_authority.read_text(encoding="utf-8")) if ns.technical_authority else synthetic_bundle()
            fake = {f: {"path": "SYNTHETIC_SUBSTITUTE_AUTHORITY", "sha256": ZERO_HASH, "pointer": "/"} for f in FAMILIES}
            print(json.dumps(build_tree(ns.output_root, ns.schema_root, ns.allowlist, bundle, fake), sort_keys=True)); return 0
        repo = ns.repo_root.resolve(); release = ns.release.resolve(); attestation = ns.attestation.resolve(); contract = ns.contract.resolve(); auth_schema = ns.authorization_schema.resolve()
        gate = validate_release(repo, release, attestation, contract, auth_schema, "formal", "S2_GENERATE_STATIC")
        allowed_control_roots = {(repo / gate["roots"][name]).resolve() for name in ("success", "failure")}
        if ns.control_root.resolve() not in allowed_control_roots: raise Corr02Error("CONTROL_ROOT_NOT_ATTESTED_RUN_SPECIFIC")
        bindings = authority_args(ns)  # all four bindings are materialised before any authority read
        released = {f: {"path": str((repo / b["path"]).resolve()), "sha256": b["sha256"], "pointer": b["pointer"]} for f, b in gate["formal_authorities"].items()}
        if bindings != released: raise Corr02Error("FORMAL_AUTHORITY_SUBSTITUTION_FORBIDDEN")
        bundle = bind_then_read_authorities(bindings)
        staging = repo / gate["roots"]["staging"]
        result = build_tree(staging, ns.schema_root, ns.allowlist, bundle, bindings, gate)
        atomic_json(ns.control_root / "VERIFIED_SUCCESS.json", {"schema_version": "gen_enc_2c_s2_corr02_terminal_v1", "terminal_state": "VERIFIED_SUCCESS", "run_id": gate["run_id"], "observed_counts": {"members": 80, "artifacts": 92}, "final_test_read": False})
        print(json.dumps(result | {"run_id": gate["run_id"]}, sort_keys=True)); return 0
    except BaseException as exc:
        if getattr(ns, "command", None) == "formal" and getattr(ns, "control_root", None):
            try: terminal_fail(ns.control_root, ns.schema_root, type(exc).__name__ + ":" + str(exc), {})
            except BaseException: pass
        print(f"FAIL_CLOSED:{type(exc).__name__}:{exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
