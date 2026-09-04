from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from scripts.gen_enc_b1_mapping_adapter_01.driver_adapter import build as build_adapter
from scripts.gen_enc_b1_science_first.formal_run import (
    CLAIM, FAMILIES, PREFIX, canonical, evidence, load_inputs, parameters,
    sha_bytes, sha_file, write,
)

TASK = "01a0452b-ee9f-7ce0-a671-78d80cb069fe"
ORDINALS = (16, 17, 18, 19, 20)
EXPECTED_MEMBER_IDS = tuple(
    f"{prefix}_{ordinal:02d}"
    for prefix in ("HAND", "NEAR", "RANDOM", "PHYSICS")
    for ordinal in ORDINALS
)
AUTHORITY_BINDINGS = {
    "minimum_governance_override_sha256": "31a0dac1b8aeadcf95e8c5305981b11f94b8587365d18104b97d7aa8425af835",
    "interval_disposition_review_sha256": "d9f7575465197ba6c98fb6303600b3c69360a2e6a05d2256838c10bf9254c751",
    "adapter_sha256s_sha256": "963b2a90f6f333510c84bcf86071e921fb1727a722026e86c382946b803d5a00",
    "b3_results_sha256s_sha256": "f2ae7f490ee7804ba3a62de334c7be460ebc202f637d0d0121da118bf7b5bda4",
    "b3_guardian_terminal_review_sha256": "3ac6d99e8bf2fff22c9ecc6c566872906191c0a2b552a31fe40427b98906093a",
    "b3_addendum_sha256": "bfe3f3ac626e71092aaab9ba7e35f9a7ef0762f8de4597009dc444a49eeffb90",
    "b1_formal_run_source_sha256": "ebd550a843e6ba2f837395b6d0acb9ff65aef971029c38ba53b5089dad5c5541",
    "b1_independent_verifier_source_sha256": "4e38c149aace9772c1505a668a26d30eeb178481406b62c72cd932fc8a675c34",
}


def execute(repo: Path, run_id: str) -> Path:
    run = repo / "outputs/gen_enc/GEN_ENC_FAST_START/b4_science_first_exact20_runs" / run_id
    staging = run / "staging"
    results = run / "results"
    if run.exists():
        raise ValueError("RUN_EXISTS")
    try:
        objects, reads = load_inputs(repo)
        adapter = build_adapter(objects, list(EXPECTED_MEMBER_IDS))
        records = []
        for family in FAMILIES:
            for ordinal in ORDINALS:
                member_id = f"{PREFIX[family]}_{ordinal:02d}"
                params, source = parameters(objects, family, ordinal)
                cad_evidence, status, reasons = evidence(objects, adapter, family, member_id, params)
                base = {
                    "schema_version": "gen_enc_fast_b1_science_first_member_v1",
                    "record_kind": "B4_BATCH_LOCAL_IDENTITY_CAD_STATIC",
                    "task_id": TASK, "run_id": run_id, "batch_id": "B4",
                    "family_id": family, "member_id": member_id, "slot_ordinal": ordinal,
                    "failure_slot_retained": True, "input_provenance": source,
                    "parameter_order": list(params), "parameters": params,
                    "cad_static_evidence": cad_evidence, "static_status": status,
                    "failure_reasons": reasons, "claim_ceiling": CLAIM,
                    "scientific_hypothesis_status": "NOT_TESTED", "final_test_read": False,
                }
                base["identity_sha256"] = sha_bytes(canonical(base))
                write(staging / "members" / (member_id + ".json"), base)
                records.append(base)

        families = []
        for family in FAMILIES:
            subset = [row for row in records if row["family_id"] == family]
            manifest = {
                "family_id": family, "member_count": 5,
                "member_ids": [row["member_id"] for row in subset],
                "member_hashes": [row["identity_sha256"] for row in subset],
                "eligible_count": sum(row["static_status"] == "ELIGIBLE" for row in subset),
                "ineligible_count": sum(row["static_status"] != "ELIGIBLE" for row in subset),
                "claim_ceiling": CLAIM, "final_test_read": False,
            }
            write(staging / "families" / (PREFIX[family] + ".json"), manifest)
            families.append(manifest)

        index = {
            "schema_version": "gen_enc_fast_b1_science_first_index_v1",
            "task_id": TASK, "run_id": run_id, "batch_id": "B4",
            "member_count": 20, "family_count": 4,
            "members": [{"member_id": row["member_id"], "path": "members/" + row["member_id"] + ".json", "identity_sha256": row["identity_sha256"], "static_status": row["static_status"]} for row in records],
            "family_manifests": [{"family_id": row["family_id"], "path": "families/" + PREFIX[row["family_id"]] + ".json"} for row in families],
            "claim_ceiling": CLAIM, "final_test_read": False,
        }
        write(staging / "batch_index.json", index)
        audit = {
            "member_count": 20,
            "ownership_witness_count": sum(len(row["cad_static_evidence"]["ownership_witnesses"]) for row in records),
            "eligible_count": sum(row["static_status"] == "ELIGIBLE" for row in records),
            "ineligible_count": sum(row["static_status"] != "ELIGIBLE" for row in records),
            "failed_count": sum(bool(row["failure_reasons"]) for row in records),
            "reason_counts": {}, "interval_native": True,
            "midpoint_or_endface_used": False, "final_test_read": False,
        }
        for row in records:
            for reason in row["failure_reasons"]:
                audit["reason_counts"][reason] = audit["reason_counts"].get(reason, 0) + 1
        write(staging / "static_audit.json", audit)
        write(staging / "generation_provenance.json", {
            "task_id": TASK, "run_id": run_id, "batch_id": "B4",
            "authority": reads, "authority_bindings": AUTHORITY_BINDINGS,
            "raw_inputs_read_only_sha256_bound": True,
            "frozen_member_ids": list(EXPECTED_MEMBER_IDS), "member_count": 20,
            "artifact_count_before_verification": 27,
            "single_process_ordered_staging": True, "final_test_read": False,
        })

        from scripts.gen_enc_b4_science_first.independent_verifier import verify
        report = verify(repo, staging, run_id)
        shutil.copytree(staging, results)
        write(results / "independent_verification.json", report)
        checksums = [{"path": path.relative_to(results).as_posix(), "sha256": sha_file(path)} for path in sorted(results.rglob("*.json"))]
        write(results / "SHA256SUMS.json", {"files": checksums})
        return run
    except Exception as exc:
        run.mkdir(parents=True, exist_ok=True)
        write(run / "FAILURE.json", {"task_id": TASK, "run_id": run_id, "batch_id": "B4", "error": f"{type(exc).__name__}:{exc}", "final_test_read": False})
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        execute(Path(args.repo_root).resolve(), args.run_id)
        return 0
    except Exception as exc:
        print("FAIL_CLOSED:" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
