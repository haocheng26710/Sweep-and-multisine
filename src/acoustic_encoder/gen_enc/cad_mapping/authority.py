import hashlib
import json
from pathlib import Path


APPROVING = {"GUARDIAN_APPROVE", "GUARDIAN_APPROVE_WITH_REQUIRED_DISCLOSURES"}


def load_dispatch(repo, relative, task_id, mode):
    path = repo / relative
    raw = path.read_bytes()
    record = json.loads(raw)
    if hashlib.sha256(raw).hexdigest() != "963174135167f125391f27109d5519636dd46345d202997772b1ffe059a40fc9":
        raise ValueError("DISPATCH_HASH_MISMATCH")
    if record["allowed_task_id"] != task_id or mode not in record["allowed_modes"]:
        raise ValueError("AUTHORIZATION_SCOPE_MISMATCH")
    if record["guardian_decision"] not in APPROVING or not record["guardian_implementation_execution_authorized"]:
        raise ValueError("GUARDIAN_AUTHORIZATION_INVALID")
    if record["revoked"] or not record["technical_conformance_preflight_authorized"] or record["timing_preflight_authorized"]:
        raise ValueError("AUTHORIZATION_STATE_INVALID")
    for entry in record["exact_boundaries"]["authority_hash_chain"]:
        if hashlib.sha256((repo / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("AUTHORITY_HASH_MISMATCH")
    return record, raw


def exact_relative(value):
    p = Path(value)
    if p.is_absolute() or ":" in value or "\\" in value or any(x in (".", "..") for x in p.parts):
        raise ValueError("PATH_NOT_EXACT_RELATIVE")
    return p
