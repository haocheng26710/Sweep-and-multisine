from __future__ import annotations

from pathlib import Path

from scripts.gen_enc_b1_mapping_adapter_01.verifier_adapter import verify as verify_adapter
from scripts.gen_enc_b2_science_first.independent_verifier import (
    CLAIM, digest, load, load_inputs_independently, verify_member,
)

TASK = "01a0452b-ee9f-7ce0-a671-78d80cb069fe"
PREFIXES = ("HAND", "NEAR", "RANDOM", "PHYSICS")
ORDINALS = (16, 17, 18, 19, 20)
EXPECTED_MEMBER_IDS = tuple(
    f"{prefix}_{ordinal:02d}" for prefix in PREFIXES for ordinal in ORDINALS
)


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
    ownership_by_member = {row["member_id"]: row["witnesses"] for row in adapter["ownership_derivation"]["members"]}
    for member in members:
        verify_member(member, ownership_by_member[member["member_id"]])

    index = load(staging / "batch_index.json")
    audit = load(staging / "static_audit.json")
    provenance = load(staging / "generation_provenance.json")
    if index["member_count"] != 20 or index["family_count"] != 4 or index["run_id"] != run_id or index["batch_id"] != "B4":
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
        "record_kind": "INDEPENDENT_B4_EXACT20_VERIFICATION",
        "task_id": TASK, "run_id": run_id, "batch_id": "B4", "verdict": "PASS",
        "member_count": 20, "family_count": 4, "ownership_witness_count": 100,
        "eligible_count": eligible, "ineligible_count": ineligible,
        "failed_count": audit["failed_count"],
        "member_identity_hashes": {member["member_id"]: member["identity_sha256"] for member in members},
        "family_manifest_hashes": family_hashes,
        "batch_index_sha256": digest(index), "static_audit_sha256": digest(audit),
        "generation_provenance_sha256": digest(provenance),
        "authority_inputs_independently_reread": True,
        "frozen_order_recomputed": list(EXPECTED_MEMBER_IDS),
        "claim_ceiling": CLAIM, "scientific_hypothesis_status": "NOT_TESTED",
        "final_test_read": False,
    }
