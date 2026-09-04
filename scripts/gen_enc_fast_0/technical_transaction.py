"""Technical-fixture-only publication model used to freeze crash semantics."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".atomic.tmp")
    temp.write_bytes(_canonical(value))
    with temp.open("r+b") as stream:
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _token(run_id: str, target: Path, index: int) -> str:
    return hashlib.sha256(_canonical({"index": index, "run_id": run_id, "target": str(target.resolve())})).hexdigest()


def exact_temp(target: Path, run_id: str, index: int) -> Path:
    return target.with_name(f".{target.name}.{run_id}.{index}.txn.tmp")


def publish_one(source: Path, target: Path, journal: Path, run_id: str, crash_after_replace: bool = False) -> None:
    temp = exact_temp(target, run_id, 0)
    token = _token(run_id, target, 0)
    state = {"schema_version": "fast_0_technical_journal_v1", "identity_class": "TECHNICAL_FIXTURE_ONLY", "run_id": run_id, "state": "INTENT_DURABLE", "entries": [{"index": 0, "target_absolute_path": str(target.resolve()), "temp_absolute_path": str(temp.resolve()), "ownership_token_sha256": token, "phase": "INTENT"}]}
    _atomic(journal, state)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(source.read_bytes())
    os.replace(temp, target)
    if crash_after_replace:
        os._exit(73)
    state["entries"][0]["phase"] = "REPLACED"
    state["state"] = "COMMITTED"
    _atomic(journal, state)


def recover(journal: Path, run_id: str, allowed_target_root: Path) -> dict:
    state = json.loads(journal.read_text(encoding="utf-8"))
    if state["run_id"] != run_id or state["identity_class"] != "TECHNICAL_FIXTURE_ONLY":
        raise ValueError("JOURNAL_BINDING")
    root = allowed_target_root.resolve()
    removed = []
    for entry in state["entries"]:
        target = Path(entry["target_absolute_path"])
        temp = Path(entry["temp_absolute_path"])
        if target.resolve().parent != root or temp != exact_temp(target, run_id, entry["index"]):
            raise ValueError("CONTAINMENT_OR_EXACT_TEMP")
        if entry["ownership_token_sha256"] != _token(run_id, target, entry["index"]):
            raise ValueError("OWNERSHIP_TOKEN")
        for owned in (temp, target):
            if owned.exists():
                owned.unlink()
                removed.append(str(owned))
    state["state"] = "ROLLED_BACK"
    state["entries"][0]["phase"] = "ROLLED_BACK"
    _atomic(journal, state)
    return {"removed": removed, "state": "ROLLED_BACK"}


def write_terminal(root: Path, kind: str, payload: dict) -> Path:
    if kind not in {"SUCCESS", "FAIL_CLOSED"}:
        raise ValueError("TERMINAL_KIND")
    root.mkdir(parents=True, exist_ok=True)
    if list(root.glob("*.json")):
        raise ValueError("TERMINAL_ALREADY_EXISTS")
    path = root / ("VERIFIED_SUCCESS.json" if kind == "SUCCESS" else "FAIL_CLOSED.json")
    _atomic(path, {**payload, "record_kind": kind, "package_terminal_count": 1, "final_test_read": False})
    return path
