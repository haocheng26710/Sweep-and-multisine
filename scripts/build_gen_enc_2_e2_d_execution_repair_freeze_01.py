"""Build the additive E2-D floating-point endpoint execution-repair freeze."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any


REPO = Path(__file__).resolve().parents[1]
REL = Path(
    "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/"
    "e2_d_execution_repair_freeze_01"
)
OUT = REPO / REL
PREV = Path(
    "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/"
    "e2_preexecution_contract_freeze_02_rc_b_final"
)
OLD_ROOT = Path(
    "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/"
    "e2_formal_freeze02_rc_b_final/development"
)
FORMAL_ROOT = Path(
    "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/"
    "e2_formal_d_execution_repair_freeze_01/development"
)
RUN_ID = (
    "GEN-ENC-2-E2-D-REPAIR01-01a04cae-35de-73f1-b9bd-c7e45fc3de25-"
    "20260829T100039523Z-407c6944b5d5475ca1ed48f6d9101fb3"
)
CONTROLLER_ROOT = Path(
    "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/"
    "e2_controller_d_execution_repair_freeze_01/development"
) / RUN_ID
AUTHORIZATION = Path(
    "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/"
    "GEN_ENC_2_E2_D_EXECUTION_REPAIR_FREEZE_01_DEVELOPMENT_AUTHORIZATION.json"
)
ADVISOR = Path(
    "outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/"
    "GEN_ENC_2_E2_D_RUN01_APERTURE_FP_ENDPOINT_EXECUTION_REPAIR_DECISION.json"
)
GUARDIAN = Path(
    "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/"
    "GEN_ENC_2_E2_D_ATTEMPT01_FAIL_CLOSED_TECHNICAL_FAILURE_SEAL.json"
)
OLD_AUTHORIZATION = Path(
    "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/"
    "GEN_ENC_2_E2_RC_B_FINAL_DEVELOPMENT_AUTHORIZATION.json"
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bind(path: str | Path, role: str) -> dict[str, Any]:
    relative = Path(path)
    actual = REPO / relative
    return {
        "path": relative.as_posix(),
        "sha256": sha(actual),
        "bytes": actual.stat().st_size,
        "role": role,
    }


def write(name: str, value: Any) -> None:
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def tree_digest(root: Path) -> dict[str, Any]:
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    digest = hashlib.sha256()
    total = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        total += size
        digest.update(
            (relative + "\0" + sha(path) + "\0" + str(size) + "\n").encode(
                "utf-8"
            )
        )
    return {
        "definition": "SHA256_SORTED_RELPATH_NUL_FILESHA_NUL_DECIMALBYTES_LF",
        "sha256": digest.hexdigest(),
        "files": len(files),
        "bytes": total,
    }


def main() -> int:
    if sha(REPO / ADVISOR) != "20366fb77535a71cbee7210ea2e6206ddcf723f5adcdcbc01367870e089b332b":
        raise SystemExit("ADVISOR_REPAIR_DECISION_HASH_MISMATCH")
    if sha(REPO / GUARDIAN) != "78665752cd01f7431f99c9618268e5b7bbb59c8d0de426d666ba0b1c7571ea10":
        raise SystemExit("GUARDIAN_FAILURE_SEAL_HASH_MISMATCH")
    if sha(REPO / OLD_AUTHORIZATION) != "52c258f8e6396bfbd27f0c379459588a14481309395d02a2f86105c864148be9":
        raise SystemExit("OLD_AUTHORIZATION_HASH_MISMATCH")
    old_tree = tree_digest(REPO / OLD_ROOT)
    if old_tree != {
        "definition": "SHA256_SORTED_RELPATH_NUL_FILESHA_NUL_DECIMALBYTES_LF",
        "sha256": "eb5cbba00f7ff27f496e6130e613fce1c6d412533326f1d597127f2bdf524fc2",
        "files": 11469,
        "bytes": 39667355,
    }:
        raise SystemExit("OLD_UNSEALED_ROOT_CHANGED")
    if any((REPO / path).exists() for path in (FORMAL_ROOT, CONTROLLER_ROOT, AUTHORIZATION)):
        raise SystemExit("SUCCESSOR_ROOT_OR_AUTHORIZATION_NOT_ABSENT")

    OUT.mkdir(parents=True, exist_ok=True)
    for path in OUT.iterdir():
        if path.is_file():
            path.unlink()

    repair_spec = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_spec_v1",
        "classification": "ORDINARY_NONSCIENTIFIC_FLOATING_POINT_CLOSED_INTERVAL_ENDPOINT_NORMALIZATION_DEFECT",
        "repair_budget_used": 1,
        "repair_budget_total": 1,
        "repair_budget_remaining": 0,
        "permitted_change": "AFTER_EXISTING_ALPHA_CLOSED_INTERVAL_CHECK_CLAMP_ONLY_NORMALIZED_COORDINATE_TO_CLOSED_ZERO_ONE",
        "alpha_authority_interval": {"lower": 0.03, "upper": 0.07, "closed": True},
        "required_regressions": {
            "alpha_0_03": 0.0,
            "alpha_0_07": 1.0,
            "nextafter_below_0_03": "NEAR_SHARED_ALPHA_OUT_OF_RANGE",
            "nextafter_above_0_07": "NEAR_SHARED_ALPHA_OUT_OF_RANGE",
        },
        "prohibited_changes": [
            "SCIENTIFIC_MODEL_OR_MAPPING_OTHER_THAN_ENDPOINT_NORMALIZATION",
            "EXACT80_OR_FAMILY_COUNTS",
            "SAMPLES_SEEDS_THRESHOLDS_METRICS_OR_PRECISION",
            "WORKLOAD_RESOURCE_OR_STORAGE_GATES",
            "COMMON_W_SEMANTICS",
            "DEVELOPMENT_VALIDATION_ISOLATION",
            "FINAL_TEST_ACCESS",
        ],
        "formal_execution": False,
        "final_test_read": False,
    }
    write("repair_spec.json", repair_spec)

    old_run = {
        "schema_version": "gen_enc_2_e2_d_attempt01_immutable_provenance_v1",
        "operational_status": "CONSUMED_REVOKED_UNSEALED_NO_RESUME_NO_REUSE_NO_MUTATION",
        "same_run_retry": False,
        "formal_root": OLD_ROOT.as_posix(),
        "formal_root_tree": old_tree,
        "authorization": bind(OLD_AUTHORIZATION, "CONSUMED_REVOKED_ATTEMPT01_AUTHORIZATION"),
        "checkpoint": bind(OLD_ROOT / "checkpoint.json", "LAST_DURABLE_UNSEALED_CHECKPOINT"),
        "partial_accumulator": bind(OLD_ROOT / "merge/common_w_accumulator.npz", "UNSEALED_PROVENANCE_ONLY"),
        "merge_checkpoint": bind(OLD_ROOT / "merge/common_w_checkpoint.json", "UNSEALED_PROVENANCE_ONLY"),
        "completed_common_w_receipts": 5733,
        "development_seal_present": False,
        "reusable": False,
        "formal_execution": False,
        "final_test_read": False,
    }
    write("old_run_immutability.json", old_run)

    source_entries = [
        ("src/acoustic_encoder/gen_enc/forward_acoustic_network.py", "REPAIRED_CORE_ENDPOINT_NORMALIZATION"),
        ("scripts/gen_enc_2_e2_formal_driver_rc_b_final.py", "UNCHANGED_FORMAL_DRIVER_OVERLAY"),
        ("scripts/gen_enc_2_e2_formal_driver_rc03.py", "UNCHANGED_FORMAL_DRIVER_BASE"),
        ("scripts/gen_enc_2_e2_independent_verifier_rc03.py", "UNCHANGED_INDEPENDENT_VERIFIER"),
        ("scripts/gen_enc_2_e2_merge_reconstruct_rc_b_final.py", "UNCHANGED_FINAL_RECONSTRUCTION"),
        ("scripts/gen_enc_2_e2_merge_reconstruct_rc03.py", "UNCHANGED_BASE_RECONSTRUCTION"),
        ("src/acoustic_encoder/gen_enc/e2_rc03_stats.py", "UNCHANGED_ROLE_AND_STATS_CODE"),
        ("src/acoustic_encoder/gen_enc/e2_rc03_resource.py", "UNCHANGED_RESOURCE_GATES"),
        ("tests/test_gen_enc_2_e2_d_execution_repair_freeze_01.py", "ENDPOINT_REPAIR_REGRESSION"),
        ("scripts/build_gen_enc_2_e2_d_execution_repair_freeze_01.py", "NO_FORMAL_FREEZE_BUILDER"),
    ]
    source = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_source_v1",
        "entries": [bind(path, role) for path, role in source_entries],
        "functional_source_changes": [
            {
                "path": "src/acoustic_encoder/gen_enc/forward_acoustic_network.py",
                "before_sha256": "a1d3a5e7211079fc33e2e07d4fdda8a342d1182a94429f3b52a0593705bfa1a8",
                "after_sha256": sha(REPO / "src/acoustic_encoder/gen_enc/forward_acoustic_network.py"),
                "change": "POST_ALPHA_GATE_NORMALIZED_COORDINATE_CLAMP_ONLY",
            }
        ],
        "scientific_scope_changed": False,
        "formal_execution": False,
        "final_test_read": False,
    }
    write("source_manifest.json", source)

    runtime = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_runtime_v1",
        "predecessor_runtime": bind(PREV / "runtime_manifest.json", "UNCHANGED_RUNTIME_AND_RESOURCE_METHOD"),
        "source_manifest": bind(REL / "source_manifest.json", "REPAIRED_EXECUTION_SOURCE_CLOSURE"),
        "limits": {
            "cpu_core_seconds": 72000,
            "wall_seconds": 36000,
            "aggregate_peak_rss_bytes": 8589934592,
            "managed_storage_bytes": 51539607552,
            "startup_free_bytes": 85899345920,
            "free_reserve_bytes": 34359738368,
        },
        "blas_threads": 1,
        "resource_or_runtime_method_changed": False,
        "formal_execution": False,
        "final_test_read": False,
    }
    write("runtime_manifest.json", runtime)

    base = [
        "--contract", (REL / "contract.json").as_posix(),
        "--exact80", "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01/exact80_manifest.json",
        "--nuisance-csv", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv",
        "--seed-split", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json",
        "--source-manifest", (REL / "source_manifest.json").as_posix(),
        "--runtime-manifest", (REL / "runtime_manifest.json").as_posix(),
        "--verifier", "scripts/gen_enc_2_e2_independent_verifier_rc03.py",
        "--stats-code", "src/acoustic_encoder/gen_enc/e2_rc03_stats.py",
        "--merge-code", "scripts/gen_enc_2_e2_merge_reconstruct_rc_b_final.py",
        "--through-reference", "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_authority_addendum_01/THROUGH_REFERENCE_U4_IDENTITY_V1.json",
    ]
    development_argv = [
        "D:/Anaconda3/python.exe", "-B",
        "scripts/gen_enc_2_e2_formal_driver_rc_b_final.py", "development",
        "--authorization", AUTHORIZATION.as_posix(),
        "--output-root", FORMAL_ROOT.as_posix(),
    ] + base
    argv_bytes = canonical_json_bytes(development_argv)
    command = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_command_v1",
        "task_id": "01a04cae-35de-73f1-b9bd-c7e45fc3de25",
        "proposed_controller_run_id": RUN_ID,
        "working_directory": REPO.as_posix(),
        "authorization_path": AUTHORIZATION.as_posix(),
        "roots": {
            "formal_root": FORMAL_ROOT.as_posix(),
            "temp_root": (FORMAL_ROOT / "temp").as_posix(),
            "audit_root": (FORMAL_ROOT / "raw_audit").as_posix(),
            "receipt_root": (FORMAL_ROOT / "receipts").as_posix(),
            "stats_root": (FORMAL_ROOT / "stats").as_posix(),
            "quarantine_root": (FORMAL_ROOT / "quarantine").as_posix(),
            "controller_root": CONTROLLER_ROOT.as_posix(),
        },
        "development_argv": development_argv,
        "development_argv_canonical_json": {
            "canonicalization": "UTF8_JSON_SORT_KEYS_NO_WHITESPACE_ENSURE_ASCII_FALSE_NO_TRAILING_LF",
            "bytes": len(argv_bytes),
            "sha256": hashlib.sha256(argv_bytes).hexdigest(),
        },
        "single_use_validation_argv": None,
        "single_use_validation_status": "BLOCKED_NOT_AUTHORIZED_NOT_FROZEN_FOR_EXECUTION",
        "formal_commands_executed": 0,
        "final_test_read": False,
    }
    write("command_manifest.json", command)

    prior_storage = json.loads((REPO / PREV / "storage_bound_ledger.json").read_text(encoding="utf-8"))
    free = shutil.disk_usage(REPO).free
    storage = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_storage_v1",
        "predecessor": bind(PREV / "storage_bound_ledger.json", "UNCHANGED_STORAGE_BOUND"),
        "worst_case_retained_bytes": prior_storage["worst_case_retained_bytes"],
        "worst_case_retained_gib": prior_storage["worst_case_retained_gib"],
        "managed_cap_bytes": prior_storage["managed_cap_bytes"],
        "startup_free_bytes_min": 85899345920,
        "free_reserve_bytes_min": 34359738368,
        "freeze_free_bytes": free,
        "startup_gate_pass_at_freeze": free >= 85899345920,
        "resource_or_storage_bound_changed": False,
        "formal_execution": False,
        "final_test_read": False,
    }
    write("storage_bound_ledger.json", storage)

    authority = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_authority_v1",
        "status": "ADDITIVE_REPAIR_IMPLEMENTED_EXECUTION_UNAUTHORIZED",
        "advisor_repair_decision": bind(ADVISOR, "SOLE_BOUNDED_REPAIR_AUTHORITY"),
        "guardian_attempt01_failure_seal": bind(GUARDIAN, "ATTEMPT01_CONSUMED_FAILURE_AUTHORITY"),
        "predecessor_package": bind(PREV / "SHA256SUMS.txt", "RC_B_FINAL_PREDECESSOR"),
        "repair_budget": {"used": 1, "total": 1, "remaining": 0},
        "old_run_reusable": False,
        "same_run_retry": False,
        "successor_authorization_created": False,
        "development_execution_authorized": False,
        "validation_authorized": False,
        "formal_execution": False,
        "final_test_read": False,
    }
    write("authority_record.json", authority)

    bindings = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_bindings_v1",
        "authority": bind(REL / "authority_record.json", "ADDITIVE_REPAIR_AUTHORITY"),
        "repair_spec": bind(REL / "repair_spec.json", "SOLE_ALLOWED_SEMANTIC_DELTA"),
        "old_run_immutability": bind(REL / "old_run_immutability.json", "NONREUSABLE_ATTEMPT01_PROVENANCE"),
        "source": bind(REL / "source_manifest.json", "REPAIRED_SOURCE_CLOSURE"),
        "runtime": bind(REL / "runtime_manifest.json", "UNCHANGED_RUNTIME_WITH_REPAIRED_SOURCE_BINDING"),
        "command": bind(REL / "command_manifest.json", "SUCCESSOR_DEVELOPMENT_COMMAND_ONLY"),
        "storage": bind(REL / "storage_bound_ledger.json", "UNCHANGED_STORAGE_AND_RESOURCE_GATES"),
        "exact80": bind("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01/exact80_manifest.json", "UNCHANGED_EXACT80"),
        "nuisance": bind("outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv", "UNCHANGED_EXACT3675"),
        "seed_split": bind("outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json", "UNCHANGED_DEVELOPMENT_SEEDS"),
        "through_reference": bind("outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_authority_addendum_01/THROUGH_REFERENCE_U4_IDENTITY_V1.json", "UNCHANGED_REFERENCE"),
        "formal_execution": False,
        "final_test_read": False,
    }
    write("binding_manifest.json", bindings)

    tests = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_test_evidence_v1",
        "red": {"result": "EXPECTED_FAIL", "passed": 3, "failed": 1, "failure": "ALPHA_0_POINT07_COORDINATE_1_POINT0000000000000002"},
        "green_focused": {"result": "PASS", "passed": 6, "failed": 0, "seconds": 0.20},
        "green_current_e2_combined": {"result": "PASS", "passed": 30, "failed": 0, "seconds": 1.07},
        "interior_exact20_points_byte_identical": 18,
        "near20_original_repro_optimized_scalar_equivalence": "PASS_RTOL_1E_MINUS12_ATOL_1E_MINUS12",
        "formal_driver_invocations": 0,
        "validation_invocations": 0,
        "final_test_read": False,
    }
    write("test_evidence.json", tests)

    contract = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_contract_v1",
        "status": "READY_FOR_ADVISOR_ZERO_SCOPE_AND_GUARDIAN_SUCCESSOR_D_SIGNING",
        "authority": bind(REL / "authority_record.json", "BOUNDED_REPAIR_AUTHORITY"),
        "bindings": bind(REL / "binding_manifest.json", "SUCCESSOR_COMPLETE_BINDINGS"),
        "source": bind(REL / "source_manifest.json", "REPAIRED_SOURCE"),
        "runtime": bind(REL / "runtime_manifest.json", "UNCHANGED_RUNTIME_GATES"),
        "command": bind(REL / "command_manifest.json", "EXACT_SUCCESSOR_DEVELOPMENT_ARGV"),
        "storage": bind(REL / "storage_bound_ledger.json", "UNCHANGED_STORAGE_BOUND"),
        "tests": bind(REL / "test_evidence.json", "RED_GREEN_AND_EQUIVALENCE"),
        "old_run": bind(REL / "old_run_immutability.json", "IMMUTABLE_UNSEALED_PROVENANCE"),
        "scientific_scope_changed": False,
        "samples_thresholds_precision_resources_changed": False,
        "common_w_or_development_semantics_changed": False,
        "validation_authorized": False,
        "development_execution_authorized": False,
        "formal_execution": False,
        "final_test_read": False,
    }
    write("contract.json", contract)

    zero = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_zero_state_v1",
        "status": "NO_SUCCESSOR_FORMAL_EXECUTION",
        "proposed_run_id_persisted_as_proposal_only": RUN_ID,
        "successor_authorization_created": False,
        "successor_formal_roots_created": False,
        "successor_controller_roots_created": False,
        "successor_controls_receipts_stats_checkpoints": 0,
        "formal_driver_invocations": 0,
        "development_units": 0,
        "validation_units": 0,
        "old_attempt01_provenance_mutated": False,
        "final_test_read": False,
    }
    write("DRAFT_ZERO_STATE.json", zero)

    no_run = {
        "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_no_run_report_v1",
        "status": "PASS",
        "advisor_hash_match": True,
        "guardian_hash_match": True,
        "old_root_tree_match": tree_digest(REPO / OLD_ROOT) == old_tree,
        "successor_authorization_absent": not (REPO / AUTHORIZATION).exists(),
        "successor_formal_root_absent": not (REPO / FORMAL_ROOT).exists(),
        "successor_controller_root_absent": not (REPO / CONTROLLER_ROOT).exists(),
        "repair_budget_remaining": 0,
        "formal_driver_invocations": 0,
        "validation_invocations": 0,
        "final_test_read": False,
    }
    write("no_run_validation_report.json", no_run)

    inventory_files = sorted(
        path for path in OUT.iterdir()
        if path.is_file() and path.name not in {"artifact_inventory.json", "SHA256SUMS.txt"}
    )
    write(
        "artifact_inventory.json",
        {
            "schema_version": "gen_enc_2_e2_d_execution_repair_freeze_01_inventory_v1",
            "entries": [bind(REL / path.name, "ADDITIVE_REPAIR_FREEZE_ARTIFACT") for path in inventory_files],
            "formal_artifacts": 0,
            "final_test_read": False,
        },
    )
    all_files = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt")
    (OUT / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha(path)}  {(REL / path.name).as_posix()}" for path in all_files) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": contract["status"],
                "package": REL.as_posix(),
                "sha256sums_sha256": sha(OUT / "SHA256SUMS.txt"),
                "development_argv_bytes": len(argv_bytes),
                "development_argv_sha256": hashlib.sha256(argv_bytes).hexdigest(),
                "old_root_tree_sha256": old_tree["sha256"],
                "free_bytes": free,
                "final_test_read": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
