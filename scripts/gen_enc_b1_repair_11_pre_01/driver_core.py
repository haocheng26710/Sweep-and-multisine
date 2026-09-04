from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class ShapeDriverError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_canonical(path: Path) -> tuple[Any, bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShapeDriverError("NON_JSON:" + path.as_posix()) from exc
    if raw != canonical(value):
        raise ShapeDriverError("NON_CANONICAL:" + path.as_posix())
    return value, raw


def node_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise ShapeDriverError("UNSUPPORTED_JSON_NODE")


def pointer_get(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ShapeDriverError("POINTER_SYNTAX:" + pointer)
    current = value
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        try:
            current = current[int(token)] if isinstance(current, list) else current[token]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ShapeDriverError("POINTER_MISSING:" + pointer) from exc
    return current


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def structural_projection(value: Any) -> dict[str, Any]:
    pointers: list[str] = []
    types: dict[str, str] = {}
    arrays: dict[str, dict[str, Any]] = {}
    objects: dict[str, dict[str, Any]] = {}

    def visit(node: Any, ptr: str) -> None:
        kind = node_type(node)
        pointers.append(ptr)
        types[ptr] = kind
        if isinstance(node, dict):
            keys = sorted(node)
            objects[ptr] = {"child_count": len(keys), "key_names": keys}
            for key in keys:
                visit(node[key], ptr + "/" + _escape(key))
        elif isinstance(node, list):
            element_types = sorted({node_type(item) for item in node})
            arrays[ptr] = {"length": len(node), "element_types": element_types}
            for index, item in enumerate(node):
                visit(item, ptr + "/" + str(index))

    visit(value, "")
    payload = {
        "available_json_pointer_set": sorted(pointers),
        "node_type_by_pointer": {key: types[key] for key in sorted(types)},
        "array_arity_by_pointer": {key: arrays[key] for key in sorted(arrays)},
        "object_arity_by_pointer": {key: objects[key] for key in sorted(objects)},
    }
    payload["structural_digest"] = sha_bytes(canonical({"domain": "GEN-ENC-B1-R11-DRIVER-SHAPE-v1", "shape": payload}))
    return payload


def classify_selectors(obj: Any, purpose: str, selectors: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for selector in selectors:
        if selector["purpose"] != purpose:
            continue
        sid = selector["id"]
        if sid in {"OWNERSHIP_CELLS", "OWNERSHIP_RULE"}:
            try:
                pointer_get(obj, selector["pointer"])
            except ShapeDriverError:
                statuses[sid] = "ABSENT_FIXTURE_ONLY_OR_FUTURE_OUTPUT"
                continue
            raise ShapeDriverError("FIXTURE_ONLY_FUTURE_OUTPUT_PRESENT:" + sid)
        try:
            selected = pointer_get(obj, selector["pointer"])
        except ShapeDriverError as exc:
            raise ShapeDriverError("UNRESOLVED_SELECTOR:" + sid) from exc
        if node_type(selected) != selector["type"]:
            raise ShapeDriverError("SELECTOR_TYPE_MISMATCH:" + sid)
        statuses[sid] = "PRESENT_ACTUAL_AUTHORITY_INPUT"
    return statuses


def project_object(obj: Any, entry: Mapping[str, Any], selectors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    shape = structural_projection(obj)
    return {
        "purpose": entry["purpose"],
        "source_path": entry["path"],
        "source_sha256": entry["sha256"],
        "source_pointer": entry["pointer"],
        **shape,
        "candidate_selector_status_by_id": classify_selectors(obj, entry["purpose"], selectors),
    }


def snapshot(entries: Sequence[Mapping[str, Any]], objects: Mapping[str, Any], selectors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(entries) != 13 or len({e["purpose"] for e in entries}) != 13:
        raise ShapeDriverError("EXACT_13_REQUIRED")
    rows = [project_object(objects[e["purpose"]], e, selectors) for e in entries]
    digest = sha_bytes(canonical({"domain": "GEN-ENC-B1-R11-STRUCTURAL-SNAPSHOT-v1", "objects": rows}))
    return {"objects": rows, "structural_snapshot_digest": digest}
