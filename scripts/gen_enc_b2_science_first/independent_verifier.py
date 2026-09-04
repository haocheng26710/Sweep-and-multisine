from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from scripts.gen_enc_b1_mapping_adapter_01.verifier_adapter import verify as verify_adapter

TASK = "01a0452b-ee9f-7ce0-a671-78d80cb069fe"
PREFIXES = ("HAND", "NEAR", "RANDOM", "PHYSICS")
ORDINALS = (6, 7, 8, 9, 10)
CLAIM = "BATCH_LOCAL_IDENTITY_COMPLETE_CAD_STATIC_AND_TECHNICAL_VALIDITY_ONLY"
EXPECTED_MEMBER_IDS = tuple(
    f"{prefix}_{ordinal:02d}" for prefix in PREFIXES for ordinal in ORDINALS
)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def pointer(root: Any, address: str) -> Any:
    current = root
    for raw in address[1:].split("/") if address else []:
        key = raw.replace("~1", "/").replace("~0", "~")
        current = current[int(key)] if type(current) is list else current[key]
    return current


def load_inputs_independently(repo: Path):
    allow = load(repo / "outputs/gen_enc/GEN_ENC_FAST_START/fast_0_authority_batch_contract_freeze/authority_allowlist.json")
    if allow["entry_count"] != 20:
        raise ValueError("ALLOWLIST_COUNT")
    cache = {}
    objects = {}
    for entry in allow["entries"]:
        path = repo / entry["path"]
        if entry["path"] not in cache:
            raw = path.read_bytes()
            if sha_bytes(raw) != entry["sha256"]:
                raise ValueError("AUTHORITY_SHA:" + entry["purpose"])
            cache[entry["path"]] = json.loads(raw.decode("utf-8"))
        objects[entry["purpose"]] = pointer(cache[entry["path"]], entry["pointer"])
    numeric_path = repo / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/family_identity_manifest_rev01.json"
    numeric_raw = numeric_path.read_bytes()
    if sha_bytes(numeric_raw) != "e09bcd2293f8c4b6acc2e61e74eeb31b4218b719d023d8387a15f69d980e2ee6":
        raise ValueError("NUMERIC_SHA")
    objects["NUMERIC_IDENTITY"] = json.loads(numeric_raw.decode("utf-8"))
    return objects


def verify_member(member: dict, expected_ownership: list[dict]):
    claimed = member["identity_sha256"]
    base = dict(member)
    base.pop("identity_sha256")
    if digest(base) != claimed:
        raise ValueError("IDENTITY_HASH:" + member["member_id"])
    params = member["parameters"]
    if not math.isclose(params["q270"], -(params["q0"] + params["q90"] + params["q180"]) / 3, rel_tol=0, abs_tol=1e-15):
        raise ValueError("Q270:" + member["member_id"])
    evidence = member["cad_static_evidence"]
    if evidence["ownership_witnesses"] != expected_ownership:
        raise ValueError("OWNERSHIP_RECOMPUTE:" + member["member_id"])
    for row in evidence["slot_interval_witnesses"]:
        z = row["z_interval_m"]
        collector = row["collector_z_interval_m"]
        if len(z) != 2 or not all(math.isfinite(x) for x in z) or not z[0] < z[1]:
            raise ValueError("INTERVAL:" + member["member_id"])
        if row["thickness_m"] != z[1] - z[0] or row["contained_in_internal_fluid"] is not True:
            raise ValueError("INTERVAL_DERIVATION:" + member["member_id"])
        if (max(z[0], collector[0]) < min(z[1], collector[1])) != row["non_empty_collector_overlap"]:
            raise ValueError("INTERVAL_OVERLAP:" + member["member_id"])
    if evidence["midpoint_or_endface_used"] is not False or evidence["interval_native"] is not True:
        raise ValueError("SCALAR_Z:" + member["member_id"])
    root_fail = False
    for root in evidence["volume_root_witnesses"]:
        if root["status"] != "PASS" or root["iterations"] != 80 or len(root["trace"]) != 80 or abs(root["residual_m3"]) > 1e-12:
            root_fail = True
        elif not math.isclose(root["measured_volume_m3"] - root["target_volume_m3"], root["residual_m3"], rel_tol=0, abs_tol=1e-18):
            raise ValueError("ROOT_RESIDUAL:" + member["member_id"])
    general = evidence["general_minima"]
    general_ok = general["feature_m"] >= general["feature_threshold_m"] and general["load_path_m"] >= general["load_path_threshold_m"]
    expected = "ELIGIBLE" if general_ok and not root_fail else "COST_INELIGIBLE"
    if member["static_status"] != expected or bool(member["failure_reasons"]) != (expected != "ELIGIBLE"):
        raise ValueError("STATUS:" + member["member_id"])
    if member["claim_ceiling"] != CLAIM or member["final_test_read"] is not False:
        raise ValueError("CLAIM:" + member["member_id"])


def verify(repo: Path, staging: Path, run_id: str):
    member_root = staging / "members"
    observed = list(member_root.glob("*.json"))
    expected_names = {member_id + ".json" for member_id in EXPECTED_MEMBER_IDS}
    if {path.name for path in observed} != expected_names:
        raise ValueError("EXACT20_FILE_SET")
    files = [member_root / (member_id + ".json") for member_id in EXPECTED_MEMBER_IDS]
    members = [load(path) for path in files]
    if [member["member_id"] for member in members] != list(EXPECTED_MEMBER_IDS):
        raise ValueError("EXACT20_ORDER")

    objects = load_inputs_independently(repo)
    adapter = verify_adapter(objects, list(EXPECTED_MEMBER_IDS))
    ownership_by_member = {
        row["member_id"]: row["witnesses"]
        for row in adapter["ownership_derivation"]["members"]
    }
    for member in members:
        verify_member(member, ownership_by_member[member["member_id"]])

    index = load(staging / "batch_index.json")
    audit = load(staging / "static_audit.json")
    provenance = load(staging / "generation_provenance.json")
    if index["member_count"] != 20 or index["family_count"] != 4 or index["run_id"] != run_id or index["batch_id"] != "B2":
        raise ValueError("INDEX")
    if [row["member_id"] for row in index["members"]] != list(EXPECTED_MEMBER_IDS):
        raise ValueError("INDEX_ORDER")
    for row, member in zip(index["members"], members):
        if row["identity_sha256"] != member["identity_sha256"] or row["static_status"] != member["static_status"]:
            raise ValueError("INDEX_MEMBER")

    family_hashes = {}
    for prefix in PREFIXES:
        family = load(staging / "families" / (prefix + ".json"))
        subset = [member for member in members if member["member_id"].startswith(prefix + "_")]
        if family["member_count"] != 5 or family["member_ids"] != [member["member_id"] for member in subset]:
            raise ValueError("FAMILY:" + prefix)
        if family["member_hashes"] != [member["identity_sha256"] for member in subset]:
            raise ValueError("FAMILY_HASH:" + prefix)
        family_hashes[prefix] = digest(family)

    eligible = sum(member["static_status"] == "ELIGIBLE" for member in members)
    ineligible = 20 - eligible
    if audit["member_count"] != 20 or audit["ownership_witness_count"] != 100:
        raise ValueError("AUDIT_COUNT")
    if audit["eligible_count"] != eligible or audit["ineligible_count"] != ineligible:
        raise ValueError("AUDIT_STATUS")
    if audit["failed_count"] != sum(bool(member["failure_reasons"]) for member in members):
        raise ValueError("AUDIT_FAILURE")
    if audit["midpoint_or_endface_used"] is not False or audit["interval_native"] is not True:
        raise ValueError("AUDIT_INTERVAL")
    if provenance["frozen_member_ids"] != list(EXPECTED_MEMBER_IDS) or provenance["final_test_read"] is not False:
        raise ValueError("PROVENANCE")

    allowed = {"batch_index.json", "static_audit.json", "generation_provenance.json"}
    if {path.name for path in staging.iterdir() if path.is_file()} != allowed:
        raise ValueError("ZERO_UNLISTED")
    if len(files) != 20 or len(list((staging / "families").glob("*.json"))) != 4:
        raise ValueError("ZERO_UNLISTED_COUNT")

    return {
        "schema_version": "gen_enc_fast_b1_science_first_verification_v1",
        "record_kind": "INDEPENDENT_B2_EXACT20_VERIFICATION",
        "task_id": TASK,
        "run_id": run_id,
        "batch_id": "B2",
        "verdict": "PASS",
        "member_count": 20,
        "family_count": 4,
        "ownership_witness_count": 100,
        "eligible_count": eligible,
        "ineligible_count": ineligible,
        "failed_count": audit["failed_count"],
        "member_identity_hashes": {member["member_id"]: member["identity_sha256"] for member in members},
        "family_manifest_hashes": family_hashes,
        "batch_index_sha256": digest(index),
        "static_audit_sha256": digest(audit),
        "generation_provenance_sha256": digest(provenance),
        "authority_inputs_independently_reread": True,
        "frozen_order_recomputed": list(EXPECTED_MEMBER_IDS),
        "claim_ceiling": CLAIM,
        "scientific_hypothesis_status": "NOT_TESTED",
        "final_test_read": False,
    }
