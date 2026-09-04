"""GEN-ENC-2C S2-CORR03 release-gated staged-generation/publication driver.

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
DOMAIN = b"GEN-ENC-2C-S2-CORR03-RUN-ID-v1"
LITERAL_BACKSLASH_N = b"\\n"
assert LITERAL_BACKSLASH_N.hex() == "5c6e" and b"\x0a" != LITERAL_BACKSLASH_N
MANIFEST_ORDER = ("source", "schema", "fixture", "authority", "allowlist")
FAMILIES = ("HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED")
PREFIX = dict(zip(FAMILIES, ("HAND", "NEAR", "RANDOM", "PHYSICS")))
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
MASK64 = 0xFFFFFFFFFFFFFFFF
GOLDEN_GAMMA = 0x9E3779B97F4A7C15


class Corr03Error(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    def check(x: Any) -> None:
        if isinstance(x, float) and (not math.isfinite(x) or (x == 0 and math.copysign(1, x) < 0)):
            raise Corr03Error("NON_CANONICAL_NUMBER")
        if isinstance(x, dict):
            if not all(isinstance(k, str) for k in x): raise Corr03Error("NON_STRING_KEY")
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


def native_path(path: Path) -> str:
    """Use Win32 extended paths for deeply nested exact publication targets."""
    value = str(path.resolve())
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        return "\\\\?\\" + value
    return value


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".atomic.tmp")
    if temp.exists(): raise Corr03Error("ATOMIC_TEMP_COLLISION")
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


def control_schema(name: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "schemas/gen_enc/gen_enc_2c_s2_corr03" / name
    return json.loads(path.read_text(encoding="utf-8"))


def validate_control(value: Any, name: str, code: str) -> None:
    try:
        jsonschema.Draft202012Validator(control_schema(name)).validate(value)
    except jsonschema.ValidationError as exc:
        raise Corr03Error(code + ":" + exc.message) from exc


def self_hash(value: dict[str, Any], field: str) -> str:
    clone = dict(value); clone[field] = ZERO_HASH
    return sha_bytes(canonical(clone))


def derive_run_id(release_full_sha256: str, task_id: str, hashes: dict[str, str]) -> str:
    values = [release_full_sha256, task_id] + [hashes[k] for k in MANIFEST_ORDER]
    if any(not isinstance(v, str) or len(v) != 64 and v != task_id for v in values): raise Corr03Error("RUN_ID_FIELD")
    # Literal b"\\x0a" is the sole separator; join adds no final newline.
    return sha_bytes(b"\x0a".join([DOMAIN] + [v.encode("ascii") for v in values]))


def json_pointer(document: Any, pointer: str) -> Any:
    if pointer == "": return document
    if not pointer.startswith("/"): raise Corr03Error("POINTER_NOT_RFC6901")
    node = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            if not token.isdigit() or int(token) >= len(node): raise Corr03Error("POINTER_MISSING")
            node = node[int(token)]
        elif isinstance(node, dict) and token in node: node = node[token]
        else: raise Corr03Error("POINTER_MISSING")
    return node


def exact_allowlist(path: Path, repo_root: Path | None = None) -> list[str]:
    obj = json.loads(path.read_text(encoding="utf-8")); paths = obj.get("paths")
    if obj.get("schema_version") != "gen_enc_2c_rev03_s1_path_allowlist_v1" or not isinstance(paths, list) or len(paths) != 92 or len(set(paths)) != 92:
        raise Corr03Error("ALLOWLIST_NOT_EXACT_92")
    if sum("/scientific/instances/" in p for p in paths) != 80 or sum("/scientific/manifests/" in p for p in paths) != 4:
        raise Corr03Error("ALLOWLIST_CARDINALITY")
    if paths[-1] != "docs/progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md": raise Corr03Error("ALLOWLIST_PROGRESS_MAPPING")
    if repo_root is not None:
        resolved_repo = repo_root.resolve()
        for relative in paths:
            candidate = repo_root / relative
            if not candidate.resolve().is_relative_to(resolved_repo): raise Corr03Error("ALLOWLIST_CONTAINMENT")
            if candidate.exists(): raise Corr03Error("FORMAL_TARGET_ALREADY_EXISTS")
            ancestor = candidate.parent
            while ancestor != repo_root and ancestor != ancestor.parent:
                if ancestor.exists() and ancestor.is_symlink(): raise Corr03Error("ALLOWLIST_REPARSE_ANCESTOR")
                ancestor = ancestor.parent
    return paths


def logical_paths(paths: list[str]) -> list[str]:
    marker = "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/"
    result = [p[len(marker):] if p.startswith(marker) else p for p in paths]
    if result[-1] != "docs/progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md": raise Corr03Error("PROGRESS_LOGICAL_PATH")
    return result


STORED_TO_CANONICAL = {
    "q0": "q0", "q90": "q90", "q180": "q180", "q270": "q270", "external_0": "aperture_0", "external_90": "aperture_90", "external_180": "aperture_180", "external_270": "aperture_270",
    "loss_0": "loss_0", "loss_90": "loss_90", "loss_180": "loss_180", "loss_270": "loss_270", "edge_0_90": "edge_0_90", "edge_0_180": "edge_0_180", "edge_0_270": "edge_0_270", "edge_90_180": "edge_90_180", "edge_90_270": "edge_90_270", "edge_180_270": "edge_180_270", "ring_0_90": "ring_0_90", "ring_90_180": "ring_90_180", "ring_180_270": "ring_180_270", "ring_270_0": "ring_270_0",
    "volume_logit_0": "q0", "volume_logit_90": "q90", "volume_logit_180": "q180",
    "derived_volume_logit_270": "q270", "external_aperture_fraction_0": "aperture_0",
    "external_aperture_fraction_90": "aperture_90", "external_aperture_fraction_180": "aperture_180",
    "external_aperture_fraction_270": "aperture_270", "central_mix_aperture_fraction": "central_mix",
    "shared_coupling_alpha": "shared_alpha", "loss_fraction_0": "loss_0", "loss_fraction_90": "loss_90",
    "loss_fraction_180": "loss_180", "loss_fraction_270": "loss_270",
    "reciprocal_edge_0_90": "edge_0_90", "reciprocal_edge_0_180": "edge_0_180",
    "reciprocal_edge_0_270": "edge_0_270", "reciprocal_edge_90_180": "edge_90_180",
    "reciprocal_edge_90_270": "edge_90_270", "reciprocal_edge_180_270": "edge_180_270",
    "ring_coupling_0_90": "ring_0_90", "ring_coupling_90_180": "ring_90_180",
    "ring_coupling_180_270": "ring_180_270", "ring_coupling_270_0": "ring_270_0",
}


def map_stored_parameters(stored: dict[str, Any], required_stored: set[str]) -> dict[str, float]:
    if set(stored) != required_stored: raise Corr03Error("AUTHORITY_STORED_PARAMETER_SHAPE")
    result = {STORED_TO_CANONICAL[name]: float(stored[name]) for name in required_stored}
    if any(not math.isfinite(v) for v in result.values()): raise Corr03Error("AUTHORITY_NONFINITE")
    return result


def adapt_exact_row(row: dict[str, Any], family: str, ordinal: int) -> dict[str, float]:
    expected_member = f"{PREFIX[family]}_{ordinal:02d}"
    if row.get("member_id") != expected_member: raise Corr03Error("AUTHORITY_MEMBER_ID")
    common = {f"volume_logit_{s}" for s in ("0", "90", "180")} | {"derived_volume_logit_270"} | {f"external_aperture_fraction_{s}" for s in ("0", "90", "180", "270")} | {f"loss_fraction_{s}" for s in ("0", "90", "180", "270")}
    required = common | ({"central_mix_aperture_fraction"} if family == FAMILIES[0] else {"shared_coupling_alpha"})
    if set(row) != required | {"member_id"}: raise Corr03Error("AUTHORITY_EXACT_ROW_SHAPE")
    result = map_stored_parameters({k: v for k, v in row.items() if k != "member_id"}, required)
    if any(not -.12 <= result[k] <= .12 for k in ("q0", "q90", "q180", "q270")): raise Corr03Error("EXACT_ROW_VOLUME_LOGIT_BOUNDS")
    if not math.isclose(result["q270"], -(result["q0"] + result["q90"] + result["q180"]) / 3, rel_tol=0, abs_tol=1e-12): raise Corr03Error("EXACT_ROW_DERIVED_270")
    if any(not .2 <= result[k] <= .8 for k in ("aperture_0", "aperture_90", "aperture_180", "aperture_270")) or any(not .02 <= result[k] <= .08 for k in ("loss_0", "loss_90", "loss_180", "loss_270")): raise Corr03Error("EXACT_ROW_APERTURE_OR_LOSS_BOUNDS")
    if family == FAMILIES[0] and not .1 <= result["central_mix"] <= .4: raise Corr03Error("HAND_CENTRAL_MIX_BOUNDS")
    if family == FAMILIES[1]:
        expected = .03 + (ordinal - 1) * .04 / 19
        if not .03 <= result["shared_alpha"] <= .07 or not math.isclose(result["shared_alpha"], expected, rel_tol=0, abs_tol=5e-13): raise Corr03Error("NEAR_ALPHA_SEQUENCE")
    return result


def splitmix64(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = value; z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return z ^ (z >> 31)


def open_uniform(seed: int, channel: int) -> float:
    # Exact binary64 open interval construction; endpoints are unreachable.
    return ((splitmix64((seed + GOLDEN_GAMMA * (channel + 1)) & MASK64) >> 11) + .5) / (1 << 53)


def fisher_yates(master_seed: int, coordinate: int) -> list[int]:
    values = list(range(20))
    for i in range(19, 0, -1):
        x = (master_seed + GOLDEN_GAMMA * (1 + 32 * coordinate + (19 - i))) & MASK64
        j = splitmix64(x) % (i + 1)
        values[i], values[j] = values[j], values[i]
    return values


def physics_parameters(spec: dict[str, Any], ordinal: int) -> dict[str, float]:
    wrapper_fields = {"schema_version", "identity_class", "authority_kind", "formal_values", "master_seed", "parameter_order", "bounds", "lhs", "permutation_algorithm", "final_test_read"}
    if set(spec) == wrapper_fields:
        if spec["authority_kind"] != "PHYSICS_MASTER_SPEC_EXACT_SHAPE" or spec["formal_values"] is not False or spec["final_test_read"] is not False or spec["lhs"] != {"strata": 20, "sample": "L+(U-L)*(perm[r]+0.5)/20", "jitter": False}: raise Corr03Error("PHYSICS_WRAPPER")
    elif set(spec) != {"master_seed", "parameter_order", "bounds", "algorithm"} or spec["algorithm"] != "FISHER_YATES_MIDPOINT_LHS": raise Corr03Error("PHYSICS_SPEC_SHAPE")
    order, bounds = spec["parameter_order"], spec["bounds"]
    expected_stored = tuple([f"volume_logit_{s}" for s in ("0", "90", "180")] + [f"external_aperture_fraction_{s}" for s in ("0", "90", "180", "270")] + ["ring_coupling_0_90", "ring_coupling_90_180", "ring_coupling_180_270", "ring_coupling_270_0"] + [f"loss_fraction_{s}" for s in ("0", "90", "180", "270")])
    expected_canonical = ("q0", "q90", "q180", "external_0", "external_90", "external_180", "external_270", "ring_0_90", "ring_90_180", "ring_180_270", "ring_270_0", "loss_0", "loss_90", "loss_180", "loss_270")
    if tuple(order) not in (expected_stored, expected_canonical) or not isinstance(bounds, list) or len(bounds) != 15: raise Corr03Error("PHYSICS_15_PARAMETERS")
    result = {}
    for coordinate, stored_name in enumerate(order):
        if stored_name not in STORED_TO_CANONICAL or not isinstance(bounds[coordinate], list) or len(bounds[coordinate]) != 2: raise Corr03Error("PHYSICS_BOUND")
        lo, hi = map(float, bounds[coordinate]); permutation = fisher_yates(int(spec["master_seed"]), coordinate)
        result[STORED_TO_CANONICAL[stored_name]] = lo + (hi - lo) * (permutation[ordinal - 1] + .5) / 20.0
    result["q270"] = -(result["q0"] + result["q90"] + result["q180"]) / 3
    return result


def random_parameters(spec: dict[str, Any], seed: Any) -> dict[str, float]:
    wrapper_fields = {"schema_version", "identity_class", "authority_kind", "formal_values", "parameter_order", "draw_addressing", "inverse_cdf", "final_test_read"}
    required = {"parameter_order", "bounds", "external_aperture_fractions", "algorithm"}
    wrapped = set(spec) == wrapper_fields
    if wrapped:
        if spec["authority_kind"] != "RANDOM_FAMILY_SPEC_EXACT_SHAPE" or spec["formal_values"] is not False or spec["final_test_read"] is not False or spec["draw_addressing"].get("one_uniform_per_coordinate") is not True or spec["inverse_cdf"].get("edge", {}).get("same_uniform_for_atom_and_positive_branch") is not True: raise Corr03Error("RANDOM_WRAPPER")
    elif set(spec) != required or spec["algorithm"] != "SPLITMIX64_FROZEN_INVERSE_CDF": raise Corr03Error("RANDOM_SPEC_SHAPE")
    order = spec["parameter_order"]
    expected_stored = tuple([f"volume_logit_{s}" for s in ("0", "90", "180")] + [f"reciprocal_edge_{a}_{b}" for a, b in (("0", "90"), ("0", "180"), ("0", "270"), ("90", "180"), ("90", "270"), ("180", "270"))] + [f"loss_fraction_{s}" for s in ("0", "90", "180", "270")])
    expected_canonical = ("q0", "q90", "q180", "edge_0_90", "edge_0_180", "edge_0_270", "edge_90_180", "edge_90_270", "edge_180_270", "loss_0", "loss_90", "loss_180", "loss_270")
    if tuple(order) not in (expected_stored, expected_canonical): raise Corr03Error("RANDOM_COORDINATE_NAMES_OR_ORDER")
    if not wrapped and spec["bounds"] != [[-.12, .12]] * 3 + [[.02, .08]] * 4: raise Corr03Error("RANDOM_FROZEN_BOUNDS")
    apertures = [.5, .5, .5, .5] if wrapped else spec["external_aperture_fractions"]
    result = {f"aperture_{s}": float(v) for s, v in zip(("0", "90", "180", "270"), apertures)}; seed_i = int(seed) & MASK64
    for channel, stored_name in enumerate(order):
        u = open_uniform(seed_i, channel)
        is_edge = STORED_TO_CANONICAL[stored_name].startswith("edge_")
        if is_edge:
            value = 0.0 if u < .5 else .2 + .6 * (2 * u - 1)
        else:
            continuous_index = sum(not STORED_TO_CANONICAL[x].startswith("edge_") for x in order[:channel])
            value = (-.12 + .24 * u) if continuous_index < 3 else (.02 + .06 * u)
        result[STORED_TO_CANONICAL[stored_name]] = value
    result["q270"] = -(result["q0"] + result["q90"] + result["q180"]) / 3
    return result


def synthetic_bundle() -> dict[str, Any]:
    hand, near = [], []
    for i in range(1, 21):
        phase = (i - 10.5) / 100; q = (phase, -.6 * phase, .2 * phase); common = {
            "volume_logit_0": q[0], "volume_logit_90": q[1], "volume_logit_180": q[2], "derived_volume_logit_270": -sum(q) / 3,
            "external_aperture_fraction_0": .42 + i / 1000, "external_aperture_fraction_90": .45 + i / 1200,
            "external_aperture_fraction_180": .48 - i / 1500, "external_aperture_fraction_270": .44 + i / 1800,
            "loss_fraction_0": .03 + i / 10000, "loss_fraction_90": .035 + i / 11000,
            "loss_fraction_180": .04 + i / 12000, "loss_fraction_270": .045 + i / 13000}
        hand.append({"member_id": f"HAND_{i:02d}", **common, "central_mix_aperture_fraction": .18 + i / 10000})
        near.append({"member_id": f"NEAR_{i:02d}", **common, "shared_coupling_alpha": .03 + (i - 1) * .04 / 19})
    random_order = [f"volume_logit_{s}" for s in ("0", "90", "180")] + [f"reciprocal_edge_{a}_{b}" for a, b in (("0", "90"), ("0", "180"), ("0", "270"), ("90", "180"), ("90", "270"), ("180", "270"))] + [f"loss_fraction_{s}" for s in ("0", "90", "180", "270")]
    random_bounds = [[-.12, .12]] * 3 + [[.02, .08]] * 4
    random_spec = {"algorithm": "SPLITMIX64_FROZEN_INVERSE_CDF", "parameter_order": random_order, "bounds": random_bounds, "external_aperture_fractions": [.5, .5, .5, .5]}
    physics_order = [f"volume_logit_{s}" for s in ("0", "90", "180")] + [f"external_aperture_fraction_{s}" for s in ("0", "90", "180", "270")] + ["ring_coupling_0_90", "ring_coupling_90_180", "ring_coupling_180_270", "ring_coupling_270_0"] + [f"loss_fraction_{s}" for s in ("0", "90", "180", "270")]
    bounds = [([-.08, .08] if n.startswith("volume") else [.3, .7] if n.startswith("external") else [.025, .065] if n.startswith("loss") else [.25, .75]) for n in physics_order]
    physics = {"master_seed": 930241, "parameter_order": physics_order, "bounds": bounds, "algorithm": "FISHER_YATES_MIDPOINT_LHS"}
    cad = {"root_span_m": .058926678767398356, "root_length_bounds_m": [.002, .030], "fixed_volume_m3": 2.1848e-6,
           "inner_area_m2": 4e-6, "cavity_area_m2": .0001054, "internal_z_m": [.002, .0102], "collar_z_m": [.0015, .0107],
           "central_half_side_m": .019073321232601637, "window_centres_m": [-.0096, 0.0, .0096], "minimum_feature_m": .002,
           "minimum_load_path_m": .0016, "ownership_algorithm": "CAD0_EXACT_CELL_OWNERSHIP", "connectivity_algorithm": "CAD0_POSITIVE_AREA_FACE_BFS",
           "solid_load_path_algorithm": "CAD0_Z_PARTITION_MINIMUM", "interface_exception_witnesses": [{"id": f"IFX_U4_{sector}_{suffix}", "feature_m": .0005, "load_path_m": .0015} for sector in ("000", "090", "180", "270") for suffix in ("RIM_BOTTOM", "RIM_TOP", "SHOULDER_LOWER", "SHOULDER_UPPER")] + [{"id": f"IFX_U4_{sector}_RIM", "feature_m": .0005, "load_path_m": .0015} for sector in ("000", "090", "180", "270")]}
    return {"schema_version": "gen_enc_2c_s2_corr03_exact_shape_substitutes_v1", "hand_rows": hand, "near_rows": near,
            "random_authority": {"seeds": list(range(2201, 2221)), "family_specification": random_spec}, "physics_authority": physics, "cad0_mapping": cad}


def adapt_authority_bundle(hand: Any, near: Any, random_authority: Any, physics_authority: Any) -> dict[str, Any]:
    def unwrap_rows(value: Any, kind: str) -> Any:
        if isinstance(value, dict):
            required = {"schema_version", "identity_class", "authority_kind", "formal_values", "rows", "final_test_read"}
            if set(value) != required or value["authority_kind"] != kind or value["formal_values"] is not False or value["final_test_read"] is not False: raise Corr03Error("EXACT_ROW_WRAPPER")
            return value["rows"]
        return value
    hand = unwrap_rows(hand, "HAND_ROWS_EXACT_SHAPE"); near = unwrap_rows(near, "NEAR_ROWS_EXACT_SHAPE")
    if not isinstance(hand, list) or not isinstance(near, list) or len(hand) != 20 or len(near) != 20: raise Corr03Error("EXACT_ROW_CARDINALITY")
    if not isinstance(random_authority, dict) or set(random_authority) != {"seeds", "family_specification"}: raise Corr03Error("RANDOM_SEED_SPLIT_SHAPE")
    seeds = random_authority["seeds"]
    if isinstance(seeds, dict):
        required_seed = {"schema_version", "identity_class", "authority_kind", "formal_values", "random", "final_test_read"}
        if set(seeds) != required_seed or seeds["authority_kind"] != "RANDOM_SEED_SPLIT_EXACT_SHAPE" or seeds["formal_values"] is not False or seeds["final_test_read"] is not False: raise Corr03Error("RANDOM_SEED_WRAPPER")
        seeds = seeds["random"]
    if not isinstance(seeds, list) or len(seeds) != 20: raise Corr03Error("RANDOM_SEED_SPLIT_SHAPE")
    canonical_rows = []
    for family, rows in ((FAMILIES[0], hand), (FAMILIES[1], near)):
        canonical_rows.extend((family, i, adapt_exact_row(row, family, i), {"kind": "EXACT_ROW", "binding": f"/{i-1}"}) for i, row in enumerate(rows, 1))
    for i, seed in enumerate(seeds, 1): canonical_rows.append((FAMILIES[2], i, random_parameters(random_authority["family_specification"], seed), {"kind": "FIXED_SEED", "binding": f"/seeds/{i-1}"}))
    for i in range(1, 21): canonical_rows.append((FAMILIES[3], i, physics_parameters(physics_authority, i), {"kind": "MIDPOINT_LHS", "binding": f"/master_seed/{i-1}"}))
    return {"canonical_rows": canonical_rows, "hand_rows": hand, "near_rows": near, "random_authority": random_authority, "physics_authority": physics_authority}


def parameter_rows(bundle: dict[str, Any]) -> list[tuple[str, int, dict[str, float], dict[str, Any]]]:
    if "canonical_rows" in bundle: return bundle["canonical_rows"]
    return adapt_authority_bundle(bundle["hand_rows"], bundle["near_rows"], bundle["random_authority"], bundle["physics_authority"])["canonical_rows"]


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


def solve_sector(target: float, outer_area: float, window_volume: float, cad: dict[str, Any]) -> tuple[float, float]:
    fixed, inner, cavity, span = cad["fixed_volume_m3"], cad["inner_area_m2"], cad["cavity_area_m2"], cad["root_span_m"]
    def volume(length: float) -> float: return fixed + (inner + outer_area) * (span - length) / 2 + cavity * length + window_volume
    lo, hi = cad["root_length_bounds_m"]
    if not volume(lo) <= target <= volume(hi): raise Corr03Error("CAD_ROOT_NOT_BRACKETED")
    for _ in range(80):
        mid = (lo + hi) / 2
        if volume(mid) < target: lo = mid
        else: hi = mid
    length = (lo + hi) / 2
    return length, volume(length)


def validate_cad_adapter(cad: dict[str, Any]) -> dict[str, Any]:
    if isinstance(cad, dict) and set(cad) == {"schema_version", "identity_class", "formal_member_values", "facts", "final_test_read"}:
        if cad["schema_version"] != "gen_enc_2c_s2_corr03_cad0_technical_facts_v2" or cad["identity_class"] != "TECHNICAL_CONTRACT_FACTS_ONLY" or cad["formal_member_values"] is not False or cad["final_test_read"] is not False: raise Corr03Error("CAD0_FACTS_WRAPPER")
        cad = cad["facts"]
    required = {"root_span_m", "root_length_bounds_m", "fixed_volume_m3", "inner_area_m2", "cavity_area_m2", "internal_z_m", "collar_z_m", "central_half_side_m", "window_centres_m", "minimum_feature_m", "minimum_load_path_m", "ownership_algorithm", "connectivity_algorithm", "solid_load_path_algorithm", "interface_exception_witnesses"}
    if not isinstance(cad, dict) or not required <= cad.keys(): raise Corr03Error("CAD0_FACTS_SHAPE")
    exact = {"root_span_m": .058926678767398356, "root_length_bounds_m": [.002, .030], "fixed_volume_m3": 2.1848e-6, "inner_area_m2": 4e-6, "cavity_area_m2": .0001054, "internal_z_m": [.002, .0102], "collar_z_m": [.0015, .0107], "central_half_side_m": .019073321232601637, "window_centres_m": [-.0096, 0.0, .0096], "minimum_feature_m": .002, "minimum_load_path_m": .0016}
    if any(cad[k] != v for k, v in exact.items()) or any(not isinstance(cad[k], str) or not cad[k] for k in ("ownership_algorithm", "connectivity_algorithm", "solid_load_path_algorithm")): raise Corr03Error("CAD0_FACTS_VALUE_OR_ALGORITHM")
    witnesses = cad["interface_exception_witnesses"]
    if not isinstance(witnesses, list) or len(witnesses) != 20 or len({w.get("id") for w in witnesses}) != 20: raise Corr03Error("CAD0_INTERFACE_WITNESSES")
    return {**cad, "target_volume_m3": TARGET, "volume_interval_m3": list(VOLUME_INTERVAL), "envelope_m": [.210, .210, .0122], "caps_m": [.227302, .227302, .0122]}


def cad_audit_complete(parameters: dict[str, float], family: str, cad: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    required = {"q0", "q90", "q180", "q270", "aperture_0", "aperture_90", "aperture_180", "aperture_270", "loss_0", "loss_90", "loss_180", "loss_270"}
    if not required <= parameters.keys() or any(not math.isfinite(v) for v in parameters.values()): raise Corr03Error("PARAMETER_REQUIRED_OR_FINITE")
    q = math.isclose(parameters["q270"], -(parameters["q0"] + parameters["q90"] + parameters["q180"]) / 3, abs_tol=1e-12, rel_tol=0)
    bounds = q and all(-.12 <= parameters[k] <= .12 for k in ("q0", "q90", "q180", "q270")) and all(.2 <= parameters[k] <= .8 for k in ("aperture_0", "aperture_90", "aperture_180", "aperture_270")) and all(.02 <= parameters[k] <= .08 for k in ("loss_0", "loss_90", "loss_180", "loss_270"))
    dof = dict(zip(FAMILIES, (12, 12, 13, 15)))[family]
    cad = validate_cad_adapter(cad)
    weights = [math.exp(parameters[k]) for k in ("q0", "q90", "q180", "q270")]; denominator = sum(weights)
    roots, volumes, sector_evidence = [], [], []
    for sector, weight in zip(("0", "90", "180", "270"), weights):
        outer, widths = sector_controls(parameters, family, sector)
        slots = (widths + [0.0, 0.0, 0.0])[:3]
        window = .002 * .002 * (slots[0] + max(.002, slots[1]) + slots[2])
        length, measured = solve_sector(.60 * cad["target_volume_m3"] * weight / denominator, aperture_width(outer) * .002, window, cad)
        roots.append(length); volumes.append(measured)
        sector_evidence.append({"sector": sector, "softmax_weight": weight / denominator, "outer_aperture_width_m": aperture_width(outer), "slot_widths_m": widths, "active_slot_count": sum(w > 0 for w in widths), "disabled_slot_count": sum(w == 0 for w in widths), "window_union_volume_m3": window, "root_length_m": length, "partition_volume_m3": measured, "residual_m3": measured - .60 * cad["target_volume_m3"] * weight / denominator})
    volume = .40 * cad["target_volume_m3"] + sum(volumes); envelope = cad["envelope_m"]
    nodes = ["PLENUM", "P0", "P90", "P180", "P270"]; actual_faces = [("PLENUM", n, cad["inner_area_m2"]) for n in nodes if n != "PLENUM"]
    component_count = components(nodes, actual_faces)
    window_widths = [w for sector in sector_evidence for w in sector["slot_widths_m"] if w > 0]
    feature_candidates = [.008, .030, cad["internal_z_m"][0], .0122 - cad["internal_z_m"][1], .006, .005, .004, .0062, *roots, *window_widths]
    eligible_t_ff = []
    for sector in sector_evidence:
        widths = (sector["slot_widths_m"] + [0.0, 0.0, 0.0])[:3]
        placed = [(-.0096, widths[0]), (0.0, max(.002, widths[1])), (.0096, widths[2])]
        active = [item for item in placed if item[1] > 0]
        for left, right in zip(active, active[1:]):
            gap = right[0] - left[0] - (left[1] + right[1]) / 2
            if gap > 0: eligible_t_ff.append(gap)
        for centre, slot_width in active:
            gap = .015 - abs(centre) - slot_width / 2
            if gap > 0: eligible_t_ff.append(gap)
    t_ff = min(eligible_t_ff, default=.0028)
    load_candidates = [cad["internal_z_m"][0], .0122 - cad["internal_z_m"][1], t_ff]
    feature, load = min(feature_candidates), min(load_candidates)
    audit = {"bounds_pass": bounds, "dof": dof, "volume_m3": volume, "envelope_m": envelope,
             "interface_identity": "U4_CARDINAL_4PORT_CENTRAL_M1_v1", "actual_fluid_component_count": component_count,
             "minimum_feature_m": feature, "solid_load_path_m": load}
    eligible = bounds and dof <= 16 and cad["volume_interval_m3"][0] <= volume <= cad["volume_interval_m3"][1] and component_count == 1 and feature >= cad["minimum_feature_m"] and load >= cad["minimum_load_path_m"] and all(v <= c for v, c in zip(envelope, cad["caps_m"]))
    reduced_edges = []
    if family == FAMILIES[2]:
        for a, b, key in (("P0", "P90", "edge_0_90"), ("P0", "P180", "edge_0_180"), ("P0", "P270", "edge_0_270"), ("P90", "P180", "edge_90_180"), ("P90", "P270", "edge_90_270"), ("P180", "P270", "edge_180_270")):
            reduced_edges.append({"a": a, "b": b, "coordinate": key, "value": parameters[key], "active": parameters[key] != 0.0})
    evidence = {"ownership_algorithm": cad["ownership_algorithm"], "ownership_assignments": [{"primitive": "CENTRAL_PLENUM", "owner": "CENTRAL"}] + [{"primitive": f"SECTOR_{s}", "owner": s} for s in ("0", "90", "180", "270")],
                "sector_derivations": sector_evidence, "root_iterations": 80, "central_partition_volume_m3": .40 * cad["target_volume_m3"], "sector_partition_volume_m3": sum(volumes), "total_residual_m3": volume - cad["target_volume_m3"],
                "interface_exception_witnesses": cad["interface_exception_witnesses"], "feature_candidates": [{"name": f"candidate_{i:02d}", "value_m": value} for i, value in enumerate(feature_candidates)], "measured_minimum_feature_m": feature, "minimum_feature_threshold_m": cad["minimum_feature_m"],
                "load_candidates": [{"name": "t_fe_bottom_general_cover", "value_m": cad["internal_z_m"][0]}, {"name": "t_fe_top_general_cover", "value_m": .0122 - cad["internal_z_m"][1]}] + [{"name": f"t_ff_slot_collector_{i:02d}", "value_m": value} for i, value in enumerate(eligible_t_ff)], "excluded_u4_collar_rim_exception_m": cad["collar_z_m"][0], "measured_solid_load_path_m": load, "minimum_load_path_threshold_m": cad["minimum_load_path_m"],
                "reduced_edges": reduced_edges, "reduced_component_count": components(nodes, [(x["a"], x["b"], abs(x["value"])) for x in reduced_edges]) if reduced_edges else component_count,
                "actual_positive_area_faces": [{"a": a, "b": b, "area_m2": area} for a, b, area in actual_faces], "actual_fluid_component_count": component_count, "connectivity_algorithm": cad["connectivity_algorithm"], "thresholds_copied_as_measurements": False}
    return audit, evidence, "STATIC_IDENTITY_ELIGIBLE" if eligible else "COST_INELIGIBLE"


def cad_audit(parameters: dict[str, float], family: str, cad: dict[str, Any]) -> tuple[dict[str, Any], str]:
    audit, _evidence, status = cad_audit_complete(parameters, family, cad)
    return audit, status


def _seal_algebraic(nodes: tuple[str, ...], edges: list[tuple[str, str, float]]) -> tuple[list[float], float]:
    ix = {n: i for i, n in enumerate(nodes)}; n = len(nodes); matrix = [[0.0] * n for _ in range(n)]; degree = [0.0] * n
    for left, right, weight in edges:
        if weight <= 0: continue
        i, j = ix[left], ix[right]; degree[i] += weight; degree[j] += weight; matrix[i][j] -= weight; matrix[j][i] -= weight
    for i in range(n): matrix[i][i] = degree[i]
    for _ in range(80):
        p, q = max(((i, j) for i in range(n) for j in range(i + 1, n)), key=lambda pair: abs(matrix[pair[0]][pair[1]]))
        if abs(matrix[p][q]) < 1e-15: break
        angle = .5 * math.atan2(2 * matrix[p][q], matrix[q][q] - matrix[p][p]); c, s = math.cos(angle), math.sin(angle); app, aqq, apq = matrix[p][p], matrix[q][q], matrix[p][q]
        matrix[p][p] = c*c*app - 2*s*c*apq + s*s*aqq; matrix[q][q] = s*s*app + 2*s*c*apq + c*c*aqq; matrix[p][q] = matrix[q][p] = 0.0
        for k in range(n):
            if k in (p, q): continue
            akp, akq = matrix[k][p], matrix[k][q]; matrix[k][p] = matrix[p][k] = c*akp - s*akq; matrix[k][q] = matrix[q][k] = s*akp + c*akq
    eigen = sorted(max(0.0, matrix[i][i]) for i in range(n)); return degree, eigen[1] if n > 1 else 0.0


def cad_evidence_for_verifier_seal(p: dict[str, float], family: str) -> dict[str, Any]:
    sectors = ("0", "90", "180", "270"); weights = [math.exp(p[f"q{s}"]) for s in sectors]; denominator = sum(weights); roots = []; slot_evidence = []; gaps = []; features = [("SPINE_WIDTH", .002), ("WINDOW_DEPTH", .002), ("COLLECTOR_U", .008), ("STEP_1", .006), ("STEP_2", .005), ("STEP_3", .004), ("CAVITY_HEIGHT", .0062)]
    edge_names = ("edge_0_90", "edge_0_180", "edge_0_270", "edge_90_180", "edge_90_270", "edge_180_270"); ring_names = ("ring_0_90", "ring_90_180", "ring_180_270", "ring_270_0")
    for sector, weight in zip(sectors, weights):
        if family == FAMILIES[0]: outer, slots = p[f"aperture_{sector}"], [("WINDOW_1", aperture_width(p["central_mix"]))]
        elif family == FAMILIES[1]: outer, slots = p[f"aperture_{sector}"], [("WINDOW_1", aperture_width((p["shared_alpha"]-.03)/.04))]
        elif family == FAMILIES[2]:
            names = {"0":edge_names[:3],"90":(edge_names[0],edge_names[3],edge_names[4]),"180":(edge_names[1],edge_names[3],edge_names[5]),"270":(edge_names[2],edge_names[4],edge_names[5])}[sector]; outer, slots = .5, [(f"WINDOW_{i+1}", 0.0 if p[k] == 0 else aperture_width(p[k])) for i, k in enumerate(names)]
        else:
            names = {"0":(ring_names[0],ring_names[3]),"90":(ring_names[0],ring_names[1]),"180":(ring_names[1],ring_names[2]),"270":(ring_names[2],ring_names[3])}[sector]; outer, slots = p[f"aperture_{sector}"], [("WINDOW_1", aperture_width(p[names[0]])), ("WINDOW_2", aperture_width(p[names[1]]))]
        by_id = dict(slots); window = .002*.002*(by_id.get("WINDOW_1",0)+max(.002,by_id.get("WINDOW_2",0))+by_id.get("WINDOW_3",0)); length, measured = solve_sector(.6*TARGET*weight/denominator, aperture_width(outer)*.002, window, validate_cad_adapter(synthetic_bundle()["cad0_mapping"])); roots.append(length); features.append((f"ROOT_LENGTH_{sector}",length)); features.extend((f"{name}_{sector}_WIDTH",value) for name,value in slots if value>0)
        placed=[(-.0096,by_id.get("WINDOW_1",0),"WINDOW_1"),(0.0,max(.002,by_id.get("WINDOW_2",0)),"WINDOW_2_OR_SPINE"),(.0096,by_id.get("WINDOW_3",0),"WINDOW_3")]; active=[x for x in placed if x[1]>0]
        for left,right in zip(active,active[1:]): gaps.append((f"{sector}:{left[2]}__{right[2]}",right[0]-left[0]-(left[1]+right[1])/2,[left[0]+left[1]/2,right[0]-right[1]/2]))
        for centre,width,name in active:gaps.append((f"{sector}:{name}__COLLECTOR_SIDE",.015-abs(centre)-width/2,[math.copysign(abs(centre)+width/2,centre or 1),math.copysign(.015,centre or 1)]))
        slot_evidence.append({"sector":sector,"owner":f"SECTOR_{sector}","root_length_m":length,"root_residual_m3":measured-.6*TARGET*weight/denominator,"slots":slots,"active_slot_count":sum(value>0 for _,value in slots)+1,"disabled_slot_count":3-sum(value>0 for _,value in slots)})
    reduced=[("P0","P90",p[edge_names[0]]),("P0","P180",p[edge_names[1]]),("P0","P270",p[edge_names[2]]),("P90","P180",p[edge_names[3]]),("P90","P270",p[edge_names[4]]),("P180","P270",p[edge_names[5]])] if family==FAMILIES[2] else []; actual=[("PLENUM",f"P{s}",4e-6) for s in sectors]
    feature_name,feature=min(features,key=lambda x:(x[1],x[0]));positive=[x for x in gaps if x[1]>0];tff=min((x[1] for x in positive),default=.0028);covers=[("BOTTOM_COVER_Z",[0,.002],.002),("TOP_COVER_Z",[.0102,.0122],.002)];cover_name,cover_coords,tfe=min(covers,key=lambda x:(x[2],x[0]));load=min(tff,tfe);degree,lamb=_seal_algebraic(("P0","P90","P180","P270"),reduced) if reduced else ([],0.0)
    return {"ownership_algorithm":"CENTRAL_HALF_OPEN_THEN_MAX_RADIAL_DOT_MIN_SECTOR_ORDER","sector_witnesses":slot_evidence,"fixed_u4_exception_witnesses":[{"sector":s,"collar_z":[.0015,.0107],"rim_m":.0015,"excluded_from_load_metric":True} for s in sectors],"reduced_graph":{"edges":[list(x) for x in reduced],"component_count":components(["P0","P90","P180","P270"],reduced) if reduced else None,"positive_edge_count":sum(x[2]>0 for x in reduced),"positive_edge_density":sum(x[2]>0 for x in reduced)/6 if reduced else None,"weighted_degree_sequence":degree,"weighted_algebraic_connectivity":lamb},"actual_fluid_graph":{"edges":[list(x) for x in actual],"component_count":components(["PLENUM","P0","P90","P180","P270"],actual)},"minimum_feature_witness":{"candidate":feature_name,"length_m":feature,"all_candidates":features,"threshold_m":.002,"passes":feature>=.002},"solid_load_witness":{"algorithm":"EXACT_POLYHEDRAL_SUPPORTED_COMPONENT_OPPOSING_SHEETS","pair":"GENERAL_BOTTOM_TOP_COVER","length_m":load,"supported_from_z0":True,"t_ff_m":tff,"t_fe_m":tfe,"t_fe_witness":{"id":cover_name,"z_coordinates_m":cover_coords},"t_ff_candidates":positive,"excluded_interfaces":[{"id":"FOUR_OUTER_COLLARS","rim_m":.0015,"reason":"DECLARED_INTERFACE_EXCEPTION"},{"id":"SENSOR_TOP_OPENING","reason":"INTENTIONAL_OPENING"}],"threshold_m":.0016,"passes":load>=.0016,"threshold_equal_passes":True},"sensor_owner":"CENTRAL","positive_volume_overlap_m3":0.0,"thresholds_copied_as_measurements":False}


def build_tree(root: Path, schema_root: Path, allowlist: Path, bundle: dict[str, Any], authority_bindings: dict[str, dict[str, str]], execution: dict[str, Any] | None = None, cad_contract: dict[str, Any] | None = None) -> dict[str, Any]:
    if root.exists(): raise Corr03Error("TREE_ROOT_EXISTS")
    paths = exact_allowlist(allowlist); logical = logical_paths(paths)
    if len(parameter_rows(bundle)) != 80: raise Corr03Error("MEMBER_COUNT")
    family_members = {f: [] for f in FAMILIES}
    for global_i, (family, ordinal, parameters, provenance_stub) in enumerate(parameter_rows(bundle), 1):
        audit, status = cad_audit(parameters, family, cad_contract or bundle.get("cad0_mapping", {})); family_binding = authority_bindings[family]
        binding = family_binding.get("seed_split", family_binding) if family == FAMILIES[2] else family_binding
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
    flat_bindings = flatten_bindings(authority_bindings)
    hashes = {"schema_version": "gen_enc_2c_scientific_hash_manifest_rev03_v1", "scientific_entries": scientific, "authority_entries": [{"path": x["path"], "sha256": x["sha256"]} for x in flat_bindings], "runtime_binding": {"python": platform.python_version(), "mode": "DIRECT_SCHEMA"}, "identity_index_sha256": scientific[84]["sha256"], "final_test_read": False}
    schema_validate(hashes, schema_root, "hashes"); atomic_json(root / logical[87], hashes)
    report = {"schema_version": "gen_enc_2c_independent_verification_rev03_v1", "mode": "READ_ONLY_INDEPENDENT_RECOMPUTATION", "status": "FAIL_CLOSED_TECHNICAL_RECOMPUTATION", "observed_counts": {"members": 80, "pending_verifier": 1}, "recomputed_checks": [], "failure_count": 1, "scientific_hypothesis_status": "NOT_TESTED", "final_test_read": False}
    schema_validate(report, schema_root, "verification"); atomic_json(root / logical[88], report)
    execution = execution or {"dispatch_id": "CORR03-SYNTHETIC-NONATTEMPT", "authorization_sha256": ZERO_HASH, "manifest_sha256": {k: ZERO_HASH for k in MANIFEST_ORDER}}
    record = {"schema_version": "gen_enc_2c_execution_record_rev03_v1", "task_id": TASK_ID, "dispatch_id": execution["dispatch_id"], "authorization_sha256": execution["authorization_sha256"], "source_manifest_sha256": execution["manifest_sha256"]["source"], "schema_manifest_sha256": execution["manifest_sha256"]["schema"], "authority_manifest_sha256": execution["manifest_sha256"]["authority"], "commands_exact": ["generate-staging" if execution["authorization_sha256"] != ZERO_HASH else "synthetic"], "runtime": {"python": platform.python_version()}, "terminal_state": "FAIL_CLOSED", "observed_counts": {"members": 80, "artifacts": 92, "verification_pending": 1}, "final_test_read": False}
    schema_validate(record, schema_root, "execution"); atomic_json(root / logical[89], record)
    atomic_write(root / logical[91], b"# GEN-ENC-2C scientific identity generation results\n\nmembers=80\nscience=NOT_TESTED\nfinal_test_read=false\n")
    lines = [f"{sha_file(root / logical[i])}  {paths[i]}" for i in range(92) if i != 90]
    atomic_write(root / logical[90], ("\n".join(lines) + "\n").encode("utf-8"))
    files = [p for p in root.rglob("*") if p.is_file()]
    if len(files) != 92: raise Corr03Error("DIRECT_TREE_NOT_92")
    for i in list(range(80)) + list(range(80, 90)):
        obj = json.loads((root / logical[i]).read_text(encoding="utf-8")); schema_validate(obj, schema_root, "member" if i < 80 else ("family" if i < 84 else "index" if i == 84 else ("analysis", "inventory", "hashes", "verification", "execution")[i - 85]))
        if "identity_class" in obj or "artifact" in obj or "formal_schema" in obj: raise Corr03Error("TECHNICAL_WRAPPER_FORBIDDEN")
    return {"status": "GENERATION_STAGED", "artifacts": 92, "members": 80, "direct_schema": True, "formal_input_read_count": 0 if execution["authorization_sha256"] == ZERO_HASH else 6, "final_test_read": False}


def generate_staging(root: Path, schema_root: Path, allowlist: Path, authorities: dict[str, Any], authority_bindings: dict[str, dict[str, str]], execution: dict[str, Any] | None = None, cad_contract: dict[str, Any] | None = None) -> dict[str, Any]:
    """Generate only staging bytes; never writes VERIFIED_SUCCESS or final paths."""
    result = build_tree(root, schema_root, allowlist, authorities, authority_bindings, execution, cad_contract)
    if any(p.name == "VERIFIED_SUCCESS.json" for p in root.rglob("*")): raise Corr03Error("DRIVER_SUCCESS_FORBIDDEN")
    return result


def write_generation_record(path: Path, staging: Path, allowlist: Path, release_context: dict[str, Any]) -> dict[str, Any]:
    paths, logical = exact_allowlist(allowlist), logical_paths(exact_allowlist(allowlist))
    entries = [{"path": paths[i], "sha256": sha_file(staging / logical[i])} for i in range(92)]
    value = {"schema_version": "gen_enc_2c_s2_corr03_generation_terminal_v1", "record_kind": "GENERATION_STAGED", "task_id": TASK_ID,
             "dispatch_id": release_context["dispatch_id"], "release_full_sha256": release_context["authorization_sha256"], "run_id": release_context["run_id"],
             "status": "STAGED_AWAITING_INDEPENDENT_VERIFICATION", "staging_tree_sha256": sha_bytes(canonical(entries)), "artifact_count": 92, "member_count": 80,
             "member_self_hash_null_count": 0, "verification_complete": False, "publication_started": False, "success_eligible": False, "final_test_read": False}
    atomic_json(path, value); return value


def validate_release(repo: Path, release_path: Path, attestation_path: Path, contract_path: Path, auth_schema_path: Path, command: str, mode: str) -> dict[str, Any]:
    release_raw = release_path.read_bytes(); release = json.loads(release_raw.decode("utf-8"))
    jsonschema.Draft202012Validator(json.loads(auth_schema_path.read_text(encoding="utf-8"))).validate(release)
    if release_raw != canonical(release) or release.get("payload_sha256") != sha_bytes(canonical(release.get("payload"))): raise Corr03Error("RELEASE_CANONICAL_OR_PAYLOAD_HASH")
    p = release["payload"]
    if p.get("record_kind") != "RELEASE" or p.get("task_id") != TASK_ID or not isinstance(p.get("attempt"), int) or p["attempt"] < 1 or p.get("revoked") is not False or p.get("expired") is not False or p.get("consumed") is not False or p.get("reusable") is not False or p.get("draft_promoted") is not False: raise Corr03Error("RELEASE_IDENTITY_CONSUMPTION")
    if datetime.fromisoformat(p["expires_at"].replace("Z", "+00:00")) <= datetime.now(timezone.utc): raise Corr03Error("RELEASE_EXPIRED")
    if p.get("final_test_state") != "SEALED" or p.get("final_test_read") is not False: raise Corr03Error("FINAL_TEST_BOUNDARY")
    permissions = p.get("permissions", {})
    if permissions.get(FORMAL_PERMISSION) is not True or any(permissions.get(k) is not False for k in FORBIDDEN_PERMISSIONS): raise Corr03Error("RELEASE_PERMISSIONS")
    guardian_rel, guardian_sha = p.get("guardian_approval_path"), p.get("guardian_approval_sha256")
    if not isinstance(guardian_rel, str) or not guardian_rel.startswith("outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/") or "CORR03" not in Path(guardian_rel).name or not isinstance(guardian_sha, str) or len(guardian_sha) != 64: raise Corr03Error("FUTURE_CORR03_GUARDIAN_BINDING")
    guardian = repo / guardian_rel
    if not guardian.is_file() or sha_file(guardian) != guardian_sha: raise Corr03Error("ACTUAL_GUARDIAN_REVIEW_HASH")
    guardian_record = json.loads(guardian.read_text(encoding="utf-8"))
    if guardian_record.get("stage") != "GEN-ENC-2C-S2-CORR03" or guardian_record.get("verdict") not in ("ACCEPT", "APPROVE") or "APPROVE" not in guardian_record.get("decision", ""): raise Corr03Error("GUARDIAN_NOT_APPROVAL")
    contract_raw = contract_path.read_bytes(); contract = json.loads(contract_raw.decode("utf-8"))
    if p.get("contract_path") != contract_path.relative_to(repo).as_posix() or p.get("contract_sha256") != sha_bytes(contract_raw): raise Corr03Error("CONTRACT_BINDING")
    expected_runtime = {"python": platform.python_version(), "jsonschema": importlib.metadata.version("jsonschema")}
    if contract.get("runtime") != expected_runtime or p.get("commands") != contract.get("commands") or p.get("modes") != contract.get("modes") or command not in p["commands"] or mode not in p["modes"]: raise Corr03Error("RUNTIME_COMMAND_MODE")
    manifests = p.get("manifest_sha256", {}); manifest_paths = contract.get("manifest_paths", {})
    if tuple(k for k in MANIFEST_ORDER if k not in manifests or k not in manifest_paths): raise Corr03Error("MANIFEST_REQUIRED")
    for key in MANIFEST_ORDER:
        candidate = repo / manifest_paths[key]
        if not candidate.is_file() or sha_file(candidate) != manifests[key]: raise Corr03Error("MANIFEST_HASH:" + key)
    att_raw = attestation_path.read_bytes(); att = json.loads(att_raw.decode("utf-8"))
    if att_raw != canonical(att): raise Corr03Error("ATTESTATION_NOT_CANONICAL")
    att_schema_rel = p.get("attestation_schema_path"); att_schema_hash = p.get("attestation_schema_sha256")
    if not isinstance(att_schema_rel, str) or sha_file(repo / att_schema_rel) != att_schema_hash: raise Corr03Error("ATTESTATION_SCHEMA_BINDING")
    jsonschema.Draft202012Validator(json.loads((repo / att_schema_rel).read_text(encoding="utf-8"))).validate(att)
    release_sha = sha_bytes(release_raw)
    # One-way attestation: RELEASE freezes its canonical path and schema hash;
    # the later attestation binds the already immutable full RELEASE hash.  A
    # RELEASE field containing the later attestation hash would be circular.
    if p.get("attestation_path") != attestation_path.relative_to(repo).as_posix(): raise Corr03Error("ATTESTATION_FILE_BINDING")
    expected_att = {"task_id": TASK_ID, "dispatch_id": p["dispatch_id"], "release_full_sha256": release_sha, "guardian_approval_path": guardian_rel, "guardian_approval_sha256": guardian_sha}
    if any(att.get(k) != v for k, v in expected_att.items()): raise Corr03Error("ATTESTATION_ONE_WAY_MISMATCH")
    attested_authorities = att.get("formal_authority_bindings")
    released_authorities = p.get("formal_authorities")
    if not isinstance(attested_authorities, dict) or not isinstance(released_authorities, dict): raise Corr03Error("ATTESTED_AUTHORITY_BINDINGS_REQUIRED")
    def strip_attested(binding: Any) -> dict[str, str]:
        if not isinstance(binding, dict) or set(binding) != {"path", "sha256", "pointer", "bound_before_read"} or binding.get("bound_before_read") is not True:
            raise Corr03Error("ATTESTED_AUTHORITY_BINDING_SHAPE")
        return {key: binding[key] for key in ("path", "sha256", "pointer")}
    expected_flat = flatten_bindings(released_authorities)
    observed_flat = []
    for name in (*FAMILIES, "CAD0_MAPPING"):
        binding = attested_authorities.get(name)
        if name == FAMILIES[2]:
            if not isinstance(binding, dict) or set(binding) != {"spec", "seed_split"}: raise Corr03Error("ATTESTED_RANDOM_BINDINGS")
            observed_flat.extend((strip_attested(binding["spec"]), strip_attested(binding["seed_split"])))
        else:
            observed_flat.append(strip_attested(binding))
    if observed_flat != expected_flat: raise Corr03Error("ATTESTED_AUTHORITY_BINDING_MISMATCH")
    run_id = derive_run_id(release_sha, TASK_ID, manifests)
    # The full RELEASE hash is an input to run_id, so RELEASE cannot contain
    # that derived value or expanded roots without introducing a fixed point.
    if p.get("run_id", "MISSING") is not None: raise Corr03Error("RELEASE_RUN_ID_MUST_BE_NULL")
    root_bases = contract.get("terminal_root_bases")
    if not isinstance(root_bases, dict) or p.get("terminal_root_bases") != root_bases: raise Corr03Error("RELEASE_ROOT_BASES")
    roots = att.get("terminal_roots"); root_keys = {"staging", "success", "failure", "temp", "journal"}
    if att.get("run_id") != run_id or not isinstance(roots, dict) or set(roots) != root_keys or set(root_bases) != root_keys: raise Corr03Error("ATTESTED_RUN_ID_OR_ROOTS")
    for key in root_keys:
        if key not in roots or key not in root_bases: raise Corr03Error("RUN_SPECIFIC_ROOT:" + key)
        expanded = Path(roots[key]); expected = Path(root_bases[key]) / run_id
        if expanded != expected or expanded.name != run_id: raise Corr03Error("RUN_SPECIFIC_ROOT:" + key)
    expanded = {k: repo / roots[k] for k in roots}
    if command == "generate-staging" and any(path.exists() for path in expanded.values()): raise Corr03Error("STALE_OR_RETRY_ROOT")
    if command == "publish" and (not expanded["staging"].is_dir() or expanded["success"].exists() or expanded["failure"].exists()): raise Corr03Error("PUBLISH_ROOT_STATE")
    if command == "recover" and (expanded["success"].exists() or expanded["failure"].exists()): raise Corr03Error("RECOVERY_TERMINAL_ALREADY_EXISTS")
    required_authorities = {FAMILIES[0], FAMILIES[1], FAMILIES[2], FAMILIES[3], "CAD0_MAPPING"}
    if not isinstance(released_authorities, dict) or set(released_authorities) != required_authorities: raise Corr03Error("RELEASED_AUTHORITIES_REQUIRED")
    for name, binding in released_authorities.items():
        if name == FAMILIES[2]:
            if not isinstance(binding, dict) or set(binding) != {"spec", "seed_split"}: raise Corr03Error("RELEASED_RANDOM_BINDINGS")
            candidates = binding.values()
        else: candidates = (binding,)
        if any(not isinstance(item, dict) or set(item) != {"path", "sha256", "pointer"} for item in candidates): raise Corr03Error("RELEASED_AUTHORITY_BINDING:" + name)
    return {"dispatch_id": p["dispatch_id"], "authorization_sha256": release_sha, "manifest_sha256": manifests, "run_id": run_id, "roots": roots, "formal_authorities": released_authorities, "attestation_sha256": sha_bytes(att_raw), "contract": contract}


def flatten_bindings(bindings: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    names = list(FAMILIES) + (["CAD0_MAPPING"] if "CAD0_MAPPING" in bindings else [])
    for name in names:
        binding = bindings[name]
        result.extend((binding["spec"], binding["seed_split"]) if name == FAMILIES[2] and "spec" in binding else (binding,))
    return result


def bind_then_read_authorities(bindings: dict[str, Any], observed_counts: dict[str, int] | None = None) -> tuple[dict[str, Any], Any]:
    observed_counts = observed_counts if observed_counts is not None else {}
    flat = flatten_bindings(bindings)
    if len(flat) != 6 or any(set(b) != {"path", "sha256", "pointer"} or not Path(b["path"]).is_file() or len(b["sha256"]) != 64 or not b["pointer"].startswith("/") for b in flat): raise Corr03Error("SIX_AUTHORITIES_NOT_FULLY_BOUND")
    observed_counts["authority_bindings_complete"] = 6; observed_counts.setdefault("authority_hash_reads", 0); observed_counts.setdefault("authority_content_reads", 0)
    # No file is opened until all six path/hash/pointer triples above exist.
    for binding in flat:
        actual = sha_file(Path(binding["path"])); observed_counts["authority_hash_reads"] += 1
        if actual != binding["sha256"]: raise Corr03Error("AUTHORITY_HASH")
    def selected(binding: dict[str, str]) -> Any:
        raw = Path(binding["path"]).read_text(encoding="utf-8"); observed_counts["authority_content_reads"] += 1
        return json_pointer(json.loads(raw), binding["pointer"])
    hand, near = selected(bindings[FAMILIES[0]]), selected(bindings[FAMILIES[1]])
    random_authority = {"seeds": selected(bindings[FAMILIES[2]]["seed_split"]), "family_specification": selected(bindings[FAMILIES[2]]["spec"])}
    physics, cad = selected(bindings[FAMILIES[3]]), selected(bindings["CAD0_MAPPING"])
    observed_counts["rows_read"] = 40; observed_counts["seeds_read"] = 21
    return adapt_authority_bundle(hand, near, random_authority, physics), cad


def terminal_fail(control: Path, schema_root: Path, code: str, counts: dict[str, int] | None = None, dispatch_id: str | None = None, run_id: str | None = None, fatal_stage: str = "GENERATION") -> Path:
    control.mkdir(parents=True, exist_ok=True); success, fail = control / "VERIFIED_SUCCESS.json", control / "FAIL_CLOSED.json"
    if success.exists() or fail.exists(): raise Corr03Error("TERMINAL_COLLISION")
    supplied = counts or {}; honest = {"authority_files_read": supplied.get("authority_files_read", 0), "rows_read": supplied.get("rows_read", 0), "seeds_read": supplied.get("seeds_read", 0), "members_staged": supplied.get("members_staged", 0), "members_verified": supplied.get("members_verified", 0), "artifacts_staged": supplied.get("artifacts_staged", 0), "artifacts_published": supplied.get("published", supplied.get("artifacts_published", 0)), "static_audits": supplied.get("static_audits", supplied.get("members_staged", 0))}
    value = {"schema_version": "gen_enc_2c_s2_corr03_fail_closed_terminal_v1", "record_kind": "FAIL_CLOSED", "status": "FAIL_CLOSED_S2_CORR03_INCOMPLETE", "task_id": TASK_ID, "dispatch_id": dispatch_id, "run_id": run_id, "fatal_stage": fatal_stage, "error_code": code, "honest_observed_counts": honest, "published_count_after_rollback": 0, "package_terminal_count": 1, "atomic_write": True, "science": "NOT_TESTED", "final_test_read": False}
    atomic_json(fail, value); return fail


def transaction_publish(staging: Path, repo: Path, allowlist: Path, journal: Path, run_id: str, inject: str | None = None, inject_index: int = 1, release_context: dict[str, Any] | None = None) -> dict[str, Any]:
    paths = exact_allowlist(allowlist, repo); logical = logical_paths(paths)
    owned_temps: list[dict[str, Any]] = []; published: list[dict[str, Any]] = []
    if release_context is None: raise Corr03Error("PUBLICATION_RELEASE_CONTEXT_REQUIRED")
    dispatch_id = release_context.get("dispatch_id", "GEN-ENC-2C-S2-CORR03-RELEASE-SYNTHETIC-FAULT-001")
    state = {"schema_version": "gen_enc_2c_s2_corr03_publication_journal_v1", "task_id": TASK_ID, "dispatch_id": dispatch_id,
             "release_full_sha256": release_context["authorization_sha256"], "attestation_sha256": release_context.get("attestation_sha256", ZERO_HASH),
             "run_id": run_id, "transaction_id": f"tx-s2-corr03-{run_id}-1", "state": "PREPARED", "repository_root": str(repo.resolve()),
             "allowlist_path": str(allowlist.resolve()), "allowlist_sha256": sha_file(allowlist), "ordered_target_count": 92,
             "verified_staging_sha256": release_context.get("verified_staging_sha256", ZERO_HASH), "published": [], "transaction_owned_temps": [],
             "recovery_authorized": True, "final_test_read": False}
    validate_control(state, "publication_journal.schema.json", "PUBLICATION_JOURNAL_SCHEMA")
    atomic_json(journal, state)
    try:
        for i, (src_rel, target_rel) in enumerate(zip(logical, paths), 1):
            source, target = staging / src_rel, repo / target_rel
            if not source.is_file() or target.exists(): raise Corr03Error("PUBLICATION_SOURCE_OR_COLLISION")
            target.parent.mkdir(parents=True, exist_ok=True)
            # Same-directory is required for Windows same-volume os.replace.
            # The journal and temp root are run-specific; keep this leaf suffix
            # short enough for frozen Win32 path-length behaviour.
            temp = target.with_name(target.name + f".corr03-{run_id}-{i}.tmp")
            temp_record = {"allowlist_index": i - 1, "target_relative_path": target_rel, "temp_absolute_path": str(temp.resolve()),
                           "ownership_token_sha256": sha_bytes(canonical({"run_id": run_id, "index": i - 1, "target": target_rel})), "created_by_transaction": True}
            owned_temps.append(temp_record); state.update(state="PUBLISHING", transaction_owned_temps=owned_temps); validate_control(state, "publication_journal.schema.json", "PUBLICATION_JOURNAL_SCHEMA"); atomic_json(journal, state)
            if inject == "copy" and i == inject_index: raise Corr03Error("INJECT_COPY")
            shutil.copyfile(native_path(source), native_path(temp))
            with open(native_path(temp), "r+b") as stream:
                if inject == "fsync" and i == inject_index: raise Corr03Error("INJECT_FSYNC")
                os.fsync(stream.fileno())
            if inject == "replace" and i == inject_index: raise Corr03Error("INJECT_REPLACE")
            os.replace(native_path(temp), native_path(target)); owned_temps.remove(temp_record)
            published.append({"allowlist_index": i - 1, "target_relative_path": target_rel, "target_sha256": sha_file(target), "preexisting": False})
            state.update(published=published, transaction_owned_temps=owned_temps)
            if inject == "progress" and target_rel.startswith("docs/progress/"): raise Corr03Error("INJECT_PROGRESS")
            if inject == "journal" and i == inject_index: raise Corr03Error("INJECT_JOURNAL")
            validate_control(state, "publication_journal.schema.json", "PUBLICATION_JOURNAL_SCHEMA"); atomic_json(journal, state)
        state["state"] = "COMMITTED"; validate_control(state, "publication_journal.schema.json", "PUBLICATION_JOURNAL_SCHEMA"); atomic_json(journal, state)
        return {"published": 92, "partial": False, "run_id": run_id}
    except BaseException:
        rollback_journal(state, journal); raise


def rollback_journal(state: dict[str, Any], journal: Path) -> None:
    repository_root = Path(state.get("repository_root", "."))
    for raw in reversed(state.get("published", [])):
        p = repository_root / raw["target_relative_path"] if isinstance(raw, dict) else Path(raw)
        if p.is_file(): p.unlink()
    for raw in state.get("transaction_owned_temps", []):
        p = Path(raw["temp_absolute_path"] if isinstance(raw, dict) else raw)
        owned = isinstance(raw, dict) and raw.get("created_by_transaction") is True and f".corr03-{state.get('run_id')}-" in p.name
        if p.is_file() and (owned or p.name.endswith(".c3tmp")): p.unlink()
    state.update(state="ROLLED_BACK", published=[], transaction_owned_temps=[])
    if "repository_root" in state: validate_control(state, "publication_journal.schema.json", "PUBLICATION_JOURNAL_SCHEMA")
    atomic_json(journal, state)


def startup_recovery(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise Corr03Error("UNAUTHENTICATED_RECOVERY_REMOVED_USE_SAFE_STARTUP_RECOVERY")


def safe_startup_recovery(journal: Path, release_context: dict[str, Any], repo: Path, allowlist: Path) -> dict[str, Any]:
    """Recover only a validated task/release/run journal and exact owned targets."""
    if release_context.get("task_id", TASK_ID) != TASK_ID or not isinstance(release_context.get("authorization_sha256"), str) or len(release_context["authorization_sha256"]) != 64: raise Corr03Error("RECOVERY_RELEASE_CONTEXT")
    run_id = release_context.get("run_id")
    if not isinstance(run_id, str) or len(run_id) != 64: raise Corr03Error("RECOVERY_RUN_ID")
    expected_journal = repo / release_context["roots"]["journal"] / "publication.json"
    if "contract" in release_context:
        if journal.resolve() != expected_journal.resolve(): raise Corr03Error("RECOVERY_JOURNAL_ROOT")
    elif journal.name != "publication.json" or journal.parent.name != run_id:
        raise Corr03Error("RECOVERY_SYNTHETIC_JOURNAL_ROOT")
    if not journal.is_file(): return {"recovered": False, "reason": "NO_JOURNAL"}
    raw = journal.read_bytes(); state = json.loads(raw.decode("utf-8"))
    if state.get("schema_version") != "gen_enc_2c_s2_corr03_publication_journal_v1" or not isinstance(state.get("published"), list) or not isinstance(state.get("transaction_owned_temps"), list): raise Corr03Error("RECOVERY_JOURNAL_SCHEMA")
    allowed = {(repo / p).resolve() for p in exact_allowlist(allowlist)}
    published = [(repo / p["target_relative_path"]).resolve() if isinstance(p, dict) and "target_relative_path" in p else Path(p).resolve() for p in state.get("published", [])]
    if any(p not in allowed for p in published): raise Corr03Error("RECOVERY_NON_ALLOWLIST_TARGET")
    for raw_temp in state.get("transaction_owned_temps", []):
        if not isinstance(raw_temp, dict): raise Corr03Error("RECOVERY_TEMP_OWNERSHIP")
        temp = Path(raw_temp.get("temp_absolute_path", "")).resolve()
        target = (repo / raw_temp.get("target_relative_path", "")).resolve()
        if raw_temp.get("created_by_transaction") is not True or f".corr03-{run_id}-" not in temp.name or target not in allowed: raise Corr03Error("RECOVERY_TEMP_OWNERSHIP")
    validate_control(state, "publication_journal.schema.json", "RECOVERY_JOURNAL_SCHEMA")
    if raw != canonical(state) or state.get("run_id") != run_id or state.get("task_id") != TASK_ID or state.get("release_full_sha256") != release_context["authorization_sha256"] or state.get("allowlist_sha256") != sha_file(allowlist) or Path(state.get("repository_root", "")).resolve() != repo.resolve(): raise Corr03Error("RECOVERY_CANONICAL_BINDING")
    if state.get("state") in ("PREPARED", "PUBLISHING"):
        rollback_journal(state, journal); return {"recovered": True, "state": "ROLLED_BACK", "published_after": 0}
    if state.get("state") not in ("COMMITTED", "ROLLED_BACK"): raise Corr03Error("JOURNAL_STATE")
    return {"recovered": False, "reason": state["state"]}


def verify_staging_for_publication(staging: Path, schema_root: Path, allowlist: Path) -> dict[str, int]:
    paths, logical = exact_allowlist(allowlist), logical_paths(exact_allowlist(allowlist))
    if len([p for p in staging.rglob("*") if p.is_file()]) != 92: raise Corr03Error("PUBLICATION_TREE_COUNT")
    for i in range(80):
        member = json.loads((staging / logical[i]).read_text(encoding="utf-8")); schema_validate(member, schema_root, "member")
        if member["member_sha256"] is None or member["member_sha256"] != self_hash(member, "member_sha256"): raise Corr03Error("MEMBER_SELF_HASH")
    report = json.loads((staging / logical[88]).read_text(encoding="utf-8")); schema_validate(report, schema_root, "verification")
    if report["status"] != "PASS_STATIC_IDENTITY_RECOMPUTATION" or report["failure_count"] != 0: raise Corr03Error("VERIFIER_REPORT_NOT_SUCCESS")
    execution = json.loads((staging / logical[89]).read_text(encoding="utf-8")); schema_validate(execution, schema_root, "execution")
    if execution["terminal_state"] != "SUCCESS" or execution["observed_counts"].get("verification_pending", 0) != 0: raise Corr03Error("VERIFIER_EXECUTION_NOT_RESEALED")
    manifest = json.loads((staging / logical[87]).read_text(encoding="utf-8")); schema_validate(manifest, schema_root, "hashes")
    if manifest["scientific_entries"] != [{"path": paths[i], "sha256": sha_file(staging / logical[i])} for i in range(85)]: raise Corr03Error("SCIENTIFIC_HASH_CHAIN")
    checksum_lines = (staging / logical[90]).read_text(encoding="utf-8").splitlines()
    expected_lines = [f"{sha_file(staging / logical[i])}  {paths[i]}" for i in range(92) if i != 90]
    if checksum_lines != expected_lines: raise Corr03Error("COMPLETE_RESULT_PROGRESS_HASH_CHAIN")
    return {"members": 80, "artifacts": len(paths)}


def publish_verified(staging: Path, repo: Path, schema_root: Path, allowlist: Path, journal: Path, control_root: Path, release_context: dict[str, Any], verifier_attestation: dict[str, Any], verifier_terminal_schema: Path | dict[str, Any] | None = None, inject_terminal_write: bool = False) -> dict[str, Any]:
    run_id = release_context["run_id"]
    if verifier_terminal_schema is None:
        verifier_terminal_schema = schema_root.parent / "gen_enc_2c_s2_corr03" / "verifier_terminal.schema.json"
    verifier_schema = json.loads(verifier_terminal_schema.read_text(encoding="utf-8")) if isinstance(verifier_terminal_schema, Path) else verifier_terminal_schema
    try:
        jsonschema.Draft202012Validator(verifier_schema).validate(verifier_attestation)
    except jsonschema.ValidationError as exc:
        raise Corr03Error("VERIFIER_TERMINAL_SCHEMA:" + exc.message) from exc
    generation_sha = release_context.get("generation_terminal_sha256")
    if generation_sha is None and "temp" in release_context.get("roots", {}):
        generation_path = repo / release_context["roots"]["temp"] / "generation_terminal.json"
        if generation_path.is_file(): generation_sha = sha_file(generation_path)
    # Ordinary synthetic E2E passes the already schema-validated verifier
    # binding directly.  A formal gate always carries contract+temp roots and
    # therefore must bind this value to the durable generation terminal above.
    if generation_sha is None and "contract" not in release_context:
        generation_sha = verifier_attestation.get("generation_terminal_sha256")
    expected = {"task_id": TASK_ID, "dispatch_id": release_context["dispatch_id"], "run_id": run_id,
                "release_full_sha256": release_context["authorization_sha256"], "record_kind": "VERIFIED_STAGING",
                "status": "VERIFIED_STAGING", "staging_root": str(staging), "generation_terminal_sha256": generation_sha,
                "artifact_count": 92, "member_count": 80, "member_self_hash_null_count": 0,
                "all_required_fields_verified": True, "publication_authorized": True, "success_written": False,
                "final_test_read": False}
    if generation_sha is None or any(verifier_attestation.get(k) != v for k, v in expected.items()): raise Corr03Error("VERIFIER_ATTESTATION")
    counts = verify_staging_for_publication(staging, schema_root, allowlist)
    paths, logical = exact_allowlist(allowlist), logical_paths(exact_allowlist(allowlist))
    tree_sha = sha_bytes(canonical([{"path": paths[i], "sha256": sha_file(staging / logical[i])} for i in range(92)]))
    expected_seal = {"verified_staging_sha256": tree_sha,
                     "final_independent_verification_report_sha256": sha_file(staging / logical[88]),
                     "final_scientific_hash_manifest_sha256": sha_file(staging / logical[87])}
    if any(verifier_attestation.get(k) != v for k, v in expected_seal.items()): raise Corr03Error("VERIFIER_STAGING_SEAL")
    if control_root.name != run_id or (control_root.exists() and any(control_root.iterdir())): raise Corr03Error("TERMINAL_ROOT_OR_COLLISION")
    safe_startup_recovery(journal, release_context, repo, allowlist)
    result = transaction_publish(staging, repo, allowlist, journal, run_id, release_context=release_context)
    if result["published"] != 92: raise Corr03Error("PUBLICATION_NOT_92")
    terminal = {"schema_version": "gen_enc_2c_s2_corr03_publication_terminal_v1", "record_kind": "PUBLICATION_SUCCESS", "status": "PUBLISHED_SUCCESS", "task_id": TASK_ID,
                "dispatch_id": release_context["dispatch_id"], "release_full_sha256": release_context["authorization_sha256"], "run_id": run_id,
                "verifier_terminal_sha256": sha_bytes(canonical(verifier_attestation)), "journal_sha256": sha_file(journal), "allowlist_sha256": sha_file(allowlist),
                "published_count": 92, "partial_publication_count": 0, "transaction_state": "COMMITTED", "package_terminal_count": 1, "final_test_read": False}
    publication_schema_path = schema_root.parent / "gen_enc_2c_s2_corr03" / "publication_terminal.schema.json"
    jsonschema.Draft202012Validator(json.loads(publication_schema_path.read_text(encoding="utf-8"))).validate(terminal)
    try:
        if inject_terminal_write: raise Corr03Error("INJECT_TERMINAL_WRITE")
        atomic_json(control_root / "VERIFIED_SUCCESS.json", terminal)
    except BaseException:
        # COMMITTED is not success until the one terminal is durable.  The
        # journal owns the exact allowlisted targets, so a marker failure can
        # still return the system to zero publication without touching any
        # unrelated file or temp.
        state = json.loads(journal.read_text(encoding="utf-8"))
        if state.get("state") != "COMMITTED" or state.get("run_id") != run_id or state.get("task_id") != TASK_ID:
            raise Corr03Error("POST_COMMIT_ROLLBACK_JOURNAL_INVALID")
        rollback_journal(state, journal)
        marker = control_root / "VERIFIED_SUCCESS.json"
        if marker.exists() or any((repo / path).exists() for path in paths): raise Corr03Error("POST_COMMIT_ROLLBACK_INCOMPLETE")
        raise
    return {"status": "PUBLISHED_SUCCESS", **counts, "run_id": run_id}


def package_results_gated(repo: Path, release_context: dict[str, Any]) -> dict[str, Any]:
    run_id = release_context["run_id"]; success_root, failure_root = repo / release_context["roots"]["success"], repo / release_context["roots"]["failure"]
    success, failure = success_root / "VERIFIED_SUCCESS.json", failure_root / "FAIL_CLOSED.json"
    if success.exists() == failure.exists(): raise Corr03Error("PACKAGE_EXACTLY_ONE_TERMINAL")
    marker = success if success.exists() else failure; raw = marker.read_bytes(); value = json.loads(raw.decode("utf-8"))
    if raw != canonical(value) or value.get("task_id") != TASK_ID or value.get("run_id") != run_id: raise Corr03Error("PACKAGE_TERMINAL_BINDING")
    if success.exists() and (value.get("status") != "PUBLISHED_SUCCESS" or value.get("release_full_sha256") != release_context["authorization_sha256"] or value.get("published_count") != 92 or value.get("package_terminal_count") != 1): raise Corr03Error("PACKAGE_SUCCESS_BINDING")
    if failure.exists() and (value.get("status") != "FAIL_CLOSED_S2_CORR03_INCOMPLETE" or value.get("package_terminal_count") != 1): raise Corr03Error("PACKAGE_FAILURE_BINDING")
    return {"status": value["status"], "run_id": run_id, "terminal_sha256": sha_bytes(raw), "package_terminal_count": 1}


def authority_args(ns: argparse.Namespace) -> dict[str, dict[str, str]]:
    def one(name: str) -> dict[str, str]: return {"path": str(Path(getattr(ns, name + "_path")).resolve()), "sha256": getattr(ns, name + "_sha256"), "pointer": getattr(ns, name + "_pointer")}
    return {FAMILIES[0]: one("hand"), FAMILIES[1]: one("near"), FAMILIES[2]: {"spec": one("random_spec"), "seed_split": one("random_seed")}, FAMILIES[3]: one("physics"), "CAD0_MAPPING": one("cad0")}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GEN-ENC-2C S2-CORR03 exact-authority staged driver")
    sub = p.add_subparsers(dest="command", required=True)
    syn = sub.add_parser("synthetic"); syn.add_argument("--output-root", type=Path, required=True); syn.add_argument("--schema-root", type=Path, required=True); syn.add_argument("--allowlist", type=Path, required=True); syn.add_argument("--technical-authority", type=Path)
    for command_name in ("generate-staging", "formal"):
        formal = sub.add_parser(command_name)
        for name, typ in (("repo-root", Path), ("release", Path), ("attestation", Path), ("contract", Path), ("authorization-schema", Path), ("schema-root", Path), ("allowlist", Path), ("control-root", Path)): formal.add_argument("--" + name, type=typ, required=True)
        for name in ("hand", "near", "random-spec", "random-seed", "physics", "cad0"):
            formal.add_argument("--" + name + "-path", required=True); formal.add_argument("--" + name + "-sha256", required=True); formal.add_argument("--" + name + "-pointer", required=True)
    publish = sub.add_parser("publish")
    for name, typ in (("repo-root", Path), ("release", Path), ("guardian-attestation", Path), ("verifier-attestation", Path), ("verifier-terminal-schema", Path), ("contract", Path), ("authorization-schema", Path), ("schema-root", Path), ("allowlist", Path)): publish.add_argument("--" + name, type=typ, required=True)
    publish.add_argument("--verifier-terminal-schema-sha256", required=True)
    recover = sub.add_parser("recover")
    for name, typ in (("repo-root", Path), ("release", Path), ("guardian-attestation", Path), ("contract", Path), ("authorization-schema", Path), ("schema-root", Path), ("allowlist", Path), ("journal", Path)): recover.add_argument("--" + name, type=typ, required=True)
    package = sub.add_parser("package-results")
    for name, typ in (("repo-root", Path), ("release", Path), ("guardian-attestation", Path), ("contract", Path), ("authorization-schema", Path), ("schema-root", Path), ("allowlist", Path)): package.add_argument("--" + name, type=typ, required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    ns = parser().parse_args(argv)
    try:
        if ns.command == "synthetic":
            bundle = json.loads(ns.technical_authority.read_text(encoding="utf-8")) if ns.technical_authority else synthetic_bundle()
            one = {"path": "SYNTHETIC_SUBSTITUTE_AUTHORITY", "sha256": ZERO_HASH, "pointer": "/"}
            fake = {FAMILIES[0]: dict(one), FAMILIES[1]: dict(one), FAMILIES[2]: {"spec": dict(one), "seed_split": dict(one)}, FAMILIES[3]: dict(one), "CAD0_MAPPING": dict(one)}
            print(json.dumps(generate_staging(ns.output_root, ns.schema_root, ns.allowlist, bundle, fake), sort_keys=True)); return 0
        if ns.command == "publish":
            repo = ns.repo_root.resolve(); gate = validate_release(repo, ns.release.resolve(), ns.guardian_attestation.resolve(), ns.contract.resolve(), ns.authorization_schema.resolve(), "publish", "S2_VERIFIED_PUBLICATION")
            verifier_schema_path = ns.verifier_terminal_schema.resolve()
            expected_schema_path = (repo / "schemas/gen_enc/gen_enc_2c_s2_corr03/verifier_terminal.schema.json").resolve()
            if verifier_schema_path != expected_schema_path or sha_file(verifier_schema_path) != ns.verifier_terminal_schema_sha256: raise Corr03Error("VERIFIER_TERMINAL_SCHEMA_BINDING")
            verifier_raw = ns.verifier_attestation.read_bytes(); verifier = json.loads(verifier_raw.decode("utf-8"))
            if verifier_raw != canonical(verifier): raise Corr03Error("VERIFIER_ATTESTATION_CANONICAL")
            result = publish_verified(repo / gate["roots"]["staging"], repo, ns.schema_root, ns.allowlist, repo / gate["roots"]["journal"] / "publication.json", repo / gate["roots"]["success"], {**gate, "task_id": TASK_ID}, verifier, verifier_schema_path)
            print(json.dumps(result, sort_keys=True)); return 0
        if ns.command == "recover":
            repo = ns.repo_root.resolve(); gate = validate_release(repo, ns.release.resolve(), ns.guardian_attestation.resolve(), ns.contract.resolve(), ns.authorization_schema.resolve(), "recover", "S2_SAFE_RECOVERY")
            result = safe_startup_recovery(ns.journal.resolve(), {**gate, "task_id": TASK_ID}, repo, ns.allowlist)
            print(json.dumps(result, sort_keys=True)); return 0
        if ns.command == "package-results":
            repo = ns.repo_root.resolve(); gate = validate_release(repo, ns.release.resolve(), ns.guardian_attestation.resolve(), ns.contract.resolve(), ns.authorization_schema.resolve(), "package-results", "S2_VERIFIED_PUBLICATION")
            print(json.dumps(package_results_gated(repo, gate), sort_keys=True)); return 0
        repo = ns.repo_root.resolve(); release = ns.release.resolve(); attestation = ns.attestation.resolve(); contract = ns.contract.resolve(); auth_schema = ns.authorization_schema.resolve()
        gate = validate_release(repo, release, attestation, contract, auth_schema, "generate-staging", "S2_FORMAL_GENERATION")
        if ns.control_root.resolve() != (repo / gate["roots"]["failure"]).resolve(): raise Corr03Error("DRIVER_CONTROL_MUST_BE_FAILURE_ROOT")
        bindings = authority_args(ns)  # all four bindings are materialised before any authority read
        released = gate["formal_authorities"]
        released = {FAMILIES[0]: {**released[FAMILIES[0]], "path": str((repo / released[FAMILIES[0]]["path"]).resolve())}, FAMILIES[1]: {**released[FAMILIES[1]], "path": str((repo / released[FAMILIES[1]]["path"]).resolve())}, FAMILIES[2]: {k: {**v, "path": str((repo / v["path"]).resolve())} for k, v in released[FAMILIES[2]].items()}, FAMILIES[3]: {**released[FAMILIES[3]], "path": str((repo / released[FAMILIES[3]]["path"]).resolve())}, "CAD0_MAPPING": {**released["CAD0_MAPPING"], "path": str((repo / released["CAD0_MAPPING"]["path"]).resolve())}}
        if bindings != released: raise Corr03Error("FORMAL_AUTHORITY_SUBSTITUTION_FORBIDDEN")
        observed_authority_counts: dict[str, int] = {}
        bundle, cad_contract = bind_then_read_authorities(bindings, observed_authority_counts)
        staging = repo / gate["roots"]["staging"]
        result = generate_staging(staging, ns.schema_root, ns.allowlist, bundle, bindings, gate, cad_contract)
        generation_record = write_generation_record(repo / gate["roots"]["temp"] / "generation_terminal.json", staging, ns.allowlist, gate)
        print(json.dumps(result | {"run_id": gate["run_id"], "generation_record_sha256": sha_bytes(canonical(generation_record))}, sort_keys=True)); return 0
    except BaseException as exc:
        if getattr(ns, "command", None) in ("formal", "generate-staging", "publish", "recover", "package-results") and "gate" in locals():
            try:
                failure_root = repo / gate["roots"]["failure"]
                staging_root = repo / gate["roots"]["staging"]
                allow_paths = exact_allowlist(ns.allowlist); logical = logical_paths(allow_paths)
                counts = {"authority_files_read": observed_authority_counts.get("authority_content_reads", 0) if "observed_authority_counts" in locals() else 0,
                          "authority_hash_reads": observed_authority_counts.get("authority_hash_reads", 0) if "observed_authority_counts" in locals() else 0,
                          "rows_read": observed_authority_counts.get("rows_read", 0) if "observed_authority_counts" in locals() else 0,
                          "seeds_read": observed_authority_counts.get("seeds_read", 0) if "observed_authority_counts" in locals() else 0,
                          "members_staged": sum((staging_root / logical[i]).is_file() for i in range(80)) if staging_root.exists() else 0,
                          "artifacts_staged": sum((staging_root / item).is_file() for item in logical) if staging_root.exists() else 0,
                          "published": sum((repo / item).is_file() for item in allow_paths)}
                stage = "PUBLICATION" if ns.command == "publish" else "RECOVERY" if ns.command == "recover" else "PACKAGE" if ns.command == "package-results" else "GENERATION"
                terminal_fail(failure_root, ns.schema_root, type(exc).__name__ + ":" + str(exc), counts, gate.get("dispatch_id"), gate.get("run_id"), stage)
            except BaseException: pass
        print(f"FAIL_CLOSED:{type(exc).__name__}:{exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
