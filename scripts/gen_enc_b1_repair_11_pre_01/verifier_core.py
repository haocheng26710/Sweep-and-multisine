from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class ShapeVerifierError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    with path.open("rb") as stream:
        return sha_bytes(stream.read())


def read_canonical(path: Path) -> tuple[Any, bytes]:
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ShapeVerifierError("BAD_CANONICAL_JSON") from exc
    if canonical(parsed) != raw:
        raise ShapeVerifierError("BAD_CANONICAL_BYTES")
    return parsed, raw


def kind(node: Any) -> str:
    if node is None: return "null"
    if type(node) is bool: return "boolean"
    if type(node) is int: return "integer"
    if type(node) is float: return "number"
    if type(node) is str: return "string"
    if type(node) is list: return "array"
    if type(node) is dict: return "object"
    raise ShapeVerifierError("NON_JSON_NODE")


def resolve(root: Any, address: str) -> Any:
    if address == "": return root
    if not address.startswith("/"): raise ShapeVerifierError("BAD_POINTER")
    cursor = root
    for encoded in address.split("/")[1:]:
        part = encoded.replace("~1", "/").replace("~0", "~")
        try:
            cursor = cursor[int(part)] if type(cursor) is list else cursor[part]
        except Exception as exc:
            raise ShapeVerifierError("MISSING_POINTER:" + address) from exc
    return cursor


def _token(text: str) -> str:
    return text.replace("~", "~0").replace("/", "~1")


def shape_of(root: Any) -> dict[str, Any]:
    found: list[tuple[str, str]] = []
    array_meta: list[tuple[str, dict[str, Any]]] = []
    object_meta: list[tuple[str, dict[str, Any]]] = []
    stack: list[tuple[str, Any]] = [("", root)]
    while stack:
        address, node = stack.pop()
        node_kind = kind(node)
        found.append((address, node_kind))
        if type(node) is dict:
            names = sorted(node)
            object_meta.append((address, {"child_count": len(names), "key_names": names}))
            for name in reversed(names): stack.append((address + "/" + _token(name), node[name]))
        elif type(node) is list:
            array_meta.append((address, {"length": len(node), "element_types": sorted({kind(item) for item in node})}))
            for index in range(len(node) - 1, -1, -1): stack.append((address + "/" + str(index), node[index]))
    found.sort()
    body = {
        "available_json_pointer_set": [p for p, _ in found],
        "node_type_by_pointer": {p: t for p, t in found},
        "array_arity_by_pointer": dict(sorted(array_meta)),
        "object_arity_by_pointer": dict(sorted(object_meta)),
    }
    body["structural_digest"] = sha_bytes(canonical({"domain": "GEN-ENC-B1-R11-DRIVER-SHAPE-v1", "shape": body}))
    return body


def statuses(root: Any, purpose: str, selectors: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in selectors:
        if item["purpose"] != purpose: continue
        name = item["id"]
        if name == "OWNERSHIP_CELLS" or name == "OWNERSHIP_RULE":
            try: resolve(root, item["pointer"])
            except ShapeVerifierError:
                result[name] = "ABSENT_FIXTURE_ONLY_OR_FUTURE_OUTPUT"
                continue
            raise ShapeVerifierError("FIXTURE_ONLY_FUTURE_OUTPUT_PRESENT:" + name)
        try: selected = resolve(root, item["pointer"])
        except ShapeVerifierError as exc: raise ShapeVerifierError("UNRESOLVED_SELECTOR:" + name) from exc
        if kind(selected) != item["type"]: raise ShapeVerifierError("WRONG_SELECTOR_TYPE:" + name)
        result[name] = "PRESENT_ACTUAL_AUTHORITY_INPUT"
    return result


def verify_snapshot(entries: Sequence[Mapping[str, Any]], objects: Mapping[str, Any], selectors: Sequence[Mapping[str, Any]], driver_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if len(entries) != 13 or len(set(e["purpose"] for e in entries)) != 13: raise ShapeVerifierError("NOT_13_UNIQUE")
    rebuilt = []
    for entry in entries:
        shape = shape_of(objects[entry["purpose"]])
        rebuilt.append({"purpose": entry["purpose"], "source_path": entry["path"], "source_sha256": entry["sha256"], "source_pointer": entry["pointer"], **shape, "candidate_selector_status_by_id": statuses(objects[entry["purpose"]], entry["purpose"], selectors)})
    digest = sha_bytes(canonical({"domain": "GEN-ENC-B1-R11-STRUCTURAL-SNAPSHOT-v1", "objects": rebuilt}))
    if rebuilt != driver_snapshot.get("objects") or digest != driver_snapshot.get("structural_snapshot_digest"):
        raise ShapeVerifierError("INDEPENDENT_SHAPE_MISMATCH")
    return {"objects": rebuilt, "structural_snapshot_digest": digest}
