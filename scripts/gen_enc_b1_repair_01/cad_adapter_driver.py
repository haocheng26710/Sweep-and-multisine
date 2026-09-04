"""Primary exhaustive CAD/spec authority adapter; imports no verifier code."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

CAD_PURPOSES = tuple(f"CAD0_MULTI_SOURCE_{i:02d}" for i in range(1, 14))
RANDOM_AXES = ("q0","q90","q180","edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270","loss_0","loss_90","loss_180","loss_270")
PHYSICS_AXES = ("q0","q90","q180","external_0","external_90","external_180","external_270","ring_0_90","ring_90_180","ring_180_270","ring_270_0","loss_0","loss_90","loss_180","loss_270")
MASK = (1 << 64) - 1
GAMMA = 0x9E3779B97F4A7C15


class AdapterError(RuntimeError): pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def digest(value: Any) -> str: return hashlib.sha256(canonical(value)).hexdigest()


def _pointer(value: Any, address: str) -> Any:
    node = value
    if address == "": return node
    for raw in address.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node


def _leaves(value: Any, address: str = "") -> list[dict[str, Any]]:
    if isinstance(value, dict):
        result = []
        for key in value:
            escaped = key.replace("~", "~0").replace("/", "~1")
            result.extend(_leaves(value[key], address + "/" + escaped))
        return result
    if isinstance(value, list):
        result = []
        for index, child in enumerate(value): result.extend(_leaves(child, address + f"/{index}"))
        return result
    if isinstance(value, float) and not math.isfinite(value): raise AdapterError("CAD_NONFINITE_LEAF")
    return [{"pointer": address, "type": "null" if value is None else "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "number" if isinstance(value, float) else "string", "value_sha256": digest(value)}]


def parse_cad(objects: Mapping[str, Any], authority_entries: Sequence[Mapping[str, Any]], projection_contract: Mapping[str, Any]) -> dict[str, Any]:
    entries = {x["purpose"]: x for x in authority_entries if x["purpose"] in CAD_PURPOSES}
    if set(entries) != set(CAD_PURPOSES) or any(p not in objects for p in CAD_PURPOSES): raise AdapterError("CAD_EXACT_13_SET")
    sources, all_leaves = [], []
    for purpose in CAD_PURPOSES:
        value, entry = objects[purpose], entries[purpose]; shape = entry["object_shape"]
        if not isinstance(value, dict) or list(value) != shape["field_names"] or len(value) != shape["field_count"]: raise AdapterError("CAD_TOP_SHAPE:" + purpose)
        if any(not isinstance(value[key], list) or len(value[key]) != count for key, count in shape.get("array_counts", {}).items()): raise AdapterError("CAD_ARRAY_SHAPE:" + purpose)
        leaves = _leaves(value)
        if not leaves: raise AdapterError("CAD_EMPTY_SOURCE:" + purpose)
        source = {"purpose": purpose, "path": entry["path"], "sha256": entry["sha256"], "pointer": entry["pointer"], "object_sha256": digest(value), "leaf_count": len(leaves), "leaf_manifest_sha256": digest(leaves)}
        sources.append(source); all_leaves.extend({"purpose": purpose, **leaf} for leaf in leaves)
    sections = []
    for section in projection_contract["sections"]:
        parts = []
        for selector in section["selectors"]:
            if selector["purpose"] not in CAD_PURPOSES: raise AdapterError("CAD_SELECTOR_PURPOSE")
            try: selected = _pointer(objects[selector["purpose"]], selector["pointer"])
            except (KeyError, IndexError, TypeError): raise AdapterError("CAD_SELECTOR_MISSING:" + section["name"])
            leaves = _leaves(selected)
            if not leaves: raise AdapterError("CAD_SELECTOR_EMPTY:" + section["name"])
            parts.append({"purpose": selector["purpose"], "pointer": selector["pointer"], "value_sha256": digest(selected), "leaf_count": len(leaves), "leaf_manifest_sha256": digest(leaves)})
        sections.append({"name": section["name"], "parts": parts, "section_sha256": digest(parts)})
    return {"schema_version": "gen_enc_fast_b1_repair_01_cad_authority_model_v1", "sources": sources, "sections": sections, "source_count": 13, "leaf_count": len(all_leaves), "all_leaf_manifest_sha256": digest(all_leaves), "model_sha256": digest({"sources": sources, "sections": sections, "leaves": all_leaves})}


def _group_map(parameters: Any, expected_groups: Sequence[str], axes: Sequence[str]) -> dict[str, tuple[float, float]]:
    if not isinstance(parameters, list) or len(parameters) != len(expected_groups): raise AdapterError("SPEC_PARAMETER_GROUP_COUNT")
    result: dict[str, tuple[float, float]] = {}
    for item, group in zip(parameters, expected_groups):
        if set(item) != {"group", "axes", "bounds"} or item["group"] != group or not isinstance(item["bounds"], list) or len(item["bounds"]) != 2: raise AdapterError("SPEC_PARAMETER_GROUP")
        lo, hi = map(float, item["bounds"])
        if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi: raise AdapterError("SPEC_BOUND")
        for axis in item["axes"]:
            if axis in result: raise AdapterError("SPEC_DUPLICATE_AXIS")
            result[axis] = (lo, hi)
    if tuple(result) != tuple(axes): raise AdapterError("SPEC_GROUP_AXIS_ORDER")
    return result


def parse_random_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    if tuple(spec.get("parameter_order", ())) != RANDOM_AXES or spec.get("member_count") != 20 or spec.get("dof") != 13: raise AdapterError("RANDOM_NAMED_AXES")
    if spec.get("uniform_algorithm") != {"interval":"OPEN_0_1_BINARY64","word_to_uniform":"((word>>11)+0.5)/2^53","one_guard":"nextafter(1.0,0.0)"}: raise AdapterError("RANDOM_UNIFORM_ALGORITHM")
    if spec.get("splitmix64") != {"gamma_hex":"9e3779b97f4a7c15","mix":"SPLITMIX64_FROZEN","address":"seed+gamma*(axis+1) mod 2^64"}: raise AdapterError("RANDOM_SPLITMIX64")
    if spec.get("canonical_generator") != {"draw_count":13,"redraw_count":0,"edge_zero_atom_probability":0.5,"edge_positive":"0.2+0.6*(2*u-1)"}: raise AdapterError("RANDOM_GENERATOR")
    bounds = _group_map(spec.get("parameters"), ("VOLUME_LOGIT","RECIPROCAL_EDGE_POSITIVE","LOSS"), RANDOM_AXES)
    return {"bounds": bounds, "spec_sha256": digest({"parameter_order":spec["parameter_order"],"parameters":spec["parameters"],"uniform_algorithm":spec["uniform_algorithm"],"splitmix64":spec["splitmix64"],"canonical_generator":spec["canonical_generator"]})}


def parse_physics_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    if tuple(spec.get("parameter_order", ())) != PHYSICS_AXES or spec.get("member_count") != 20 or spec.get("dof") != 15: raise AdapterError("PHYSICS_NAMED_AXES")
    exact_lhs = ["STRATA=20", "SAMPLE=(PERMUTATION[row]+0.5)/20", "JITTER=false", "FISHER_YATES_SPLITMIX64=i19_TO_1"]
    if spec.get("lhs_algorithm") != exact_lhs: raise AdapterError("PHYSICS_EXACT_LHS")
    bounds = _group_map(spec.get("parameters"), ("VOLUME_LOGIT","EXTERNAL_APERTURE","RING_COUPLING","LOSS"), PHYSICS_AXES)
    return {"bounds": bounds, "spec_sha256": digest({"parameter_order":spec["parameter_order"],"parameters":spec["parameters"],"lhs_algorithm":spec["lhs_algorithm"]})}


def mix64(argument: int) -> int:
    z = (argument + GAMMA) & MASK; z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK; z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return (z ^ (z >> 31)) & MASK


def uniform(seed: int, axis: int) -> float:
    value = ((mix64((seed + GAMMA * (axis + 1)) & MASK) >> 11) + .5) / (1 << 53)
    return math.nextafter(1.0, 0.0) if value == 1.0 else value


def permutation(master: int, axis: int) -> list[int]:
    result = list(range(20))
    for i in range(19, 0, -1):
        j = mix64((master + GAMMA * (1 + 32 * axis + 19 - i)) & MASK) % (i + 1); result[i], result[j] = result[j], result[i]
    return result


def random_parameters(spec: Mapping[str, Any], seed: int) -> dict[str, float]:
    parsed = parse_random_spec(spec); result = {f"external_{s}": .5 for s in ("0","90","180","270")}
    for index, axis in enumerate(RANDOM_AXES):
        lo, hi = parsed["bounds"][axis]; u = uniform(seed, index)
        result[axis] = (lo + (hi - lo) * u) if index < 3 or index >= 9 else (0.0 if u < .5 else lo + (hi - lo) * (2 * u - 1))
    result["q270"] = -(result["q0"] + result["q90"] + result["q180"]) / 3
    return result


def physics_parameters(spec: Mapping[str, Any], master: int, ordinal: int) -> dict[str, float]:
    parsed = parse_physics_spec(spec); result = {}
    for index, axis in enumerate(PHYSICS_AXES):
        lo, hi = parsed["bounds"][axis]; result[axis] = lo + (hi - lo) * (permutation(master, index)[ordinal - 1] + .5) / 20
    result["q270"] = -(result["q0"] + result["q90"] + result["q180"]) / 3
    return result
