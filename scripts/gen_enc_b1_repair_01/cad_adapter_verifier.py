"""Independent exhaustive CAD/spec adapter; imports no driver-side code."""
from __future__ import annotations

from hashlib import sha256
from json import dumps
from math import isfinite, nextafter
from typing import Any, Mapping, Sequence

CAD_NAMES = tuple("CAD0_MULTI_SOURCE_%02d" % n for n in range(1, 14))
RAND = ("q0","q90","q180","edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270","loss_0","loss_90","loss_180","loss_270")
PHYS = ("q0","q90","q180","external_0","external_90","external_180","external_270","ring_0_90","ring_90_180","ring_180_270","ring_270_0","loss_0","loss_90","loss_180","loss_270")
MOD = 0xFFFFFFFFFFFFFFFF
STEP = 0x9E3779B97F4A7C15


class IndependentAdapterError(RuntimeError): pass


def _bytes(x: Any) -> bytes: return (dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
def _hash(x: Any) -> str: return sha256(_bytes(x)).hexdigest()


def _walk(x: Any, p: str = "") -> list[dict[str, Any]]:
    pending = [(p, x)]; leaves = []
    while pending:
        address, value = pending.pop(0)
        if isinstance(value, dict):
            pending[0:0] = [(address + "/" + k.replace("~", "~0").replace("/", "~1"), value[k]) for k in value]
        elif isinstance(value, list): pending[0:0] = [(address + "/" + str(i), child) for i, child in enumerate(value)]
        else:
            if isinstance(value, float) and not isfinite(value): raise IndependentAdapterError("NONFINITE")
            kind = "null" if value is None else "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "number" if isinstance(value, float) else "string"
            leaves.append({"pointer": address, "type": kind, "value_sha256": _hash(value)})
    return leaves


def _at(root: Any, path: str) -> Any:
    current = root
    for encoded in path[1:].split("/") if path else ():
        token = encoded.replace("~1", "/").replace("~0", "~"); current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def model(objects: Mapping[str, Any], entries_input: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]) -> dict[str, Any]:
    entries = {e["purpose"]: e for e in entries_input if e["purpose"] in CAD_NAMES}
    if tuple(sorted(entries)) != CAD_NAMES or any(name not in objects for name in CAD_NAMES): raise IndependentAdapterError("EXACT_13")
    source_records, combined = [], []
    for name in CAD_NAMES:
        document, shape = objects[name], entries[name]["object_shape"]
        if type(document) is not dict or tuple(document) != tuple(shape["field_names"]) or len(document) != shape["field_count"]: raise IndependentAdapterError("SHAPE:" + name)
        for key, count in shape.get("array_counts", {}).items():
            if type(document[key]) is not list or len(document[key]) != count: raise IndependentAdapterError("ARRAY:" + name)
        leaves = _walk(document)
        if not leaves: raise IndependentAdapterError("EMPTY:" + name)
        source_records.append({"purpose":name,"path":entries[name]["path"],"sha256":entries[name]["sha256"],"pointer":entries[name]["pointer"],"object_sha256":_hash(document),"leaf_count":len(leaves),"leaf_manifest_sha256":_hash(leaves)})
        combined += [{"purpose":name, **leaf} for leaf in leaves]
    sections = []
    for rule in contract["sections"]:
        parts = []
        for selector in rule["selectors"]:
            try: selected = _at(objects[selector["purpose"]], selector["pointer"])
            except Exception as exc: raise IndependentAdapterError("SELECTOR:" + rule["name"]) from exc
            leaves = _walk(selected)
            if not leaves: raise IndependentAdapterError("SECTION_EMPTY")
            parts.append({"purpose":selector["purpose"],"pointer":selector["pointer"],"value_sha256":_hash(selected),"leaf_count":len(leaves),"leaf_manifest_sha256":_hash(leaves)})
        sections.append({"name":rule["name"],"parts":parts,"section_sha256":_hash(parts)})
    sources = source_records
    return {"schema_version":"gen_enc_fast_b1_repair_01_cad_authority_model_v1","sources":sources,"sections":sections,"source_count":13,"leaf_count":len(combined),"all_leaf_manifest_sha256":_hash(combined),"model_sha256":_hash({"sources":sources,"sections":sections,"leaves":combined})}


def _bounds(items: Any, groups: Sequence[str], axes: Sequence[str]) -> dict[str, tuple[float,float]]:
    if type(items) is not list or len(items) != len(groups): raise IndependentAdapterError("GROUP_COUNT")
    answer = {}
    for position, group in enumerate(groups):
        item = items[position]
        if set(item) != {"group","axes","bounds"} or item["group"] != group or type(item["bounds"]) is not list or len(item["bounds"]) != 2: raise IndependentAdapterError("GROUP")
        lower, upper = float(item["bounds"][0]), float(item["bounds"][1])
        if not (isfinite(lower) and isfinite(upper) and lower < upper): raise IndependentAdapterError("BOUNDS")
        for axis in item["axes"]:
            if axis in answer: raise IndependentAdapterError("DUP_AXIS")
            answer[axis] = (lower, upper)
    if tuple(answer) != tuple(axes): raise IndependentAdapterError("AXIS_ORDER")
    return answer


def random_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    if tuple(spec.get("parameter_order", ())) != RAND or spec.get("member_count") != 20 or spec.get("dof") != 13: raise IndependentAdapterError("RANDOM_HEADER")
    uniform = {"interval":"OPEN_0_1_BINARY64","word_to_uniform":"((word>>11)+0.5)/2^53","one_guard":"nextafter(1.0,0.0)"}
    split = {"gamma_hex":"9e3779b97f4a7c15","mix":"SPLITMIX64_FROZEN","address":"seed+gamma*(axis+1) mod 2^64"}
    generator = {"draw_count":13,"redraw_count":0,"edge_zero_atom_probability":0.5,"edge_positive":"0.2+0.6*(2*u-1)"}
    if spec.get("uniform_algorithm") != uniform or spec.get("splitmix64") != split or spec.get("canonical_generator") != generator: raise IndependentAdapterError("RANDOM_ALGORITHM")
    return {"bounds":_bounds(spec.get("parameters"), ("VOLUME_LOGIT","RECIPROCAL_EDGE_POSITIVE","LOSS"), RAND),"spec_sha256":_hash({"parameter_order":spec["parameter_order"],"parameters":spec["parameters"],"uniform_algorithm":uniform,"splitmix64":split,"canonical_generator":generator})}


def physics_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    algorithm = ["STRATA=20","SAMPLE=(PERMUTATION[row]+0.5)/20","JITTER=false","FISHER_YATES_SPLITMIX64=i19_TO_1"]
    if tuple(spec.get("parameter_order", ())) != PHYS or spec.get("member_count") != 20 or spec.get("dof") != 15 or spec.get("lhs_algorithm") != algorithm: raise IndependentAdapterError("PHYSICS_SPEC")
    return {"bounds":_bounds(spec.get("parameters"), ("VOLUME_LOGIT","EXTERNAL_APERTURE","RING_COUPLING","LOSS"), PHYS),"spec_sha256":_hash({"parameter_order":spec["parameter_order"],"parameters":spec["parameters"],"lhs_algorithm":algorithm})}


def _mix(x: int) -> int:
    z = (x + STEP) & MOD; z = ((z ^ z >> 30) * 0xBF58476D1CE4E5B9) & MOD; z = ((z ^ z >> 27) * 0x94D049BB133111EB) & MOD
    return (z ^ z >> 31) & MOD


def _uniform(seed: int, coordinate: int) -> float:
    u = ((_mix((seed + STEP * (coordinate + 1)) & MOD) >> 11) + .5) / 9007199254740992
    return nextafter(1.0, 0.0) if u == 1.0 else u


def _permutation(seed: int, coordinate: int) -> list[int]:
    values = [n for n in range(20)]; index = 19
    while index > 0:
        pick = _mix((seed + STEP * (1 + 32 * coordinate + 19 - index)) & MOD) % (index + 1); values[index], values[pick] = values[pick], values[index]; index -= 1
    return values


def random_values(spec: Mapping[str, Any], seed: int) -> dict[str,float]:
    parsed = random_spec(spec); output = {"external_0":.5,"external_90":.5,"external_180":.5,"external_270":.5}
    for i, axis in enumerate(RAND):
        lo, hi = parsed["bounds"][axis]; u = _uniform(seed, i); output[axis] = lo + (hi-lo)*u if i < 3 or i >= 9 else (0.0 if u < .5 else lo + (hi-lo)*(2*u-1))
    output["q270"] = -(output["q0"]+output["q90"]+output["q180"])/3
    return output


def physics_values(spec: Mapping[str, Any], master: int, ordinal: int) -> dict[str,float]:
    parsed = physics_spec(spec); output = {}
    for i, axis in enumerate(PHYS):
        lo, hi = parsed["bounds"][axis]; output[axis] = lo + (hi-lo)*(_permutation(master,i)[ordinal-1]+.5)/20
    output["q270"] = -(output["q0"]+output["q90"]+output["q180"])/3
    return output
