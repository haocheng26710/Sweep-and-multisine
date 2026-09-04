from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np
import pytest


REPO = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rc01_authorization_is_first_and_formal_modes_are_exact(tmp_path: Path) -> None:
    driver = _load("e2_freeze02_driver_auth", "scripts/gen_enc_2_e2_formal_driver_freeze02.py")
    with pytest.raises(driver.FormalDriverError, match="ABSENT_PRE_READ_STOP"):
        driver.authorization_pre_read_gate(tmp_path / "absent.json", "development")
    assert driver._parser().parse_args(["development"]).mode == "development"
    assert driver._parser().parse_args(["single-use-validation"]).mode == "single-use-validation"


def test_rc02_verifier_recomputes_from_frozen_inputs_and_detects_driver_perturbation() -> None:
    verifier = _load("e2_freeze02_verifier_recompute", "scripts/gen_enc_2_e2_independent_verifier_freeze02.py")
    recomputed = verifier.recompute_chunk_from_frozen_inputs(
        member_path=REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances/HAND_DESIGNED/HAND_01.identity.json",
        nuisance_csv=REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv",
        seed_split_path=REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json",
        partition="development", cell_start=0, cell_end_exclusive=1,
    )
    assert recomputed.shape == (4, 1, 2, 4, 256)
    verifier.compare_driver_raw_to_recomputed(recomputed.copy(), recomputed)
    perturbed = recomputed.copy()
    perturbed[0, 0, 0, 0, 0] += 1e-3
    with pytest.raises(verifier.VerificationError, match="RECOMPUTATION_MISMATCH"):
        verifier.compare_driver_raw_to_recomputed(perturbed, recomputed)


def _write_pass_fixture(driver, root: Path, raw: Path, receipt: Path, stats_manifest: Path) -> None:
    stats = root / "stats.npy"
    stats.parent.mkdir(parents=True, exist_ok=True)
    np.save(stats, np.asarray([1.0], dtype=np.float64), allow_pickle=False)
    manifest = {
        "entries": [{"path": stats.as_posix(), "sha256": driver.sha256_file(stats)}]
    }
    driver.write_json_atomic(stats_manifest, manifest)
    driver.write_json_atomic(receipt, {
        "status": "PASS", "sufficient_stat_manifest_sha256": driver.sha256_file(stats_manifest)
    })


def test_rc04_pass_order_deletes_only_after_receipt_stats_and_checkpoint(tmp_path: Path) -> None:
    driver = _load("e2_freeze02_driver_pass", "scripts/gen_enc_2_e2_formal_driver_freeze02.py")
    raw = tmp_path / "temp" / "chunk.npy"
    driver.write_npy_atomic(raw, np.asarray([1 + 0j], dtype=np.complex128))
    receipt = tmp_path / "receipts" / "chunk.json"
    stats_manifest = tmp_path / "stats" / "chunk.stats_manifest.json"
    _write_pass_fixture(driver, tmp_path, raw, receipt, stats_manifest)
    checkpoint = tmp_path / "checkpoint.json"
    driver.process_verified_chunk(
        raw_path=raw, receipt_path=receipt, stats_manifest_path=stats_manifest,
        audit_path=tmp_path / "audit.npy", quarantine_path=tmp_path / "quarantine.npy",
        checkpoint_path=checkpoint, verifier_command=[sys.executable, "-c", "raise SystemExit(0)"],
        is_audit=False, merge_position=0, resource_root=tmp_path,
        wall_start=time.perf_counter(), cpu_start=time.process_time(),
    )
    assert not raw.exists()
    assert receipt.exists() and stats_manifest.exists() and checkpoint.exists()
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["status"] == "PASS_VERIFIED_CHECKPOINTED"


def test_rc04_failure_quarantines_one_chunk_stops_and_never_merges_or_retries(tmp_path: Path) -> None:
    driver = _load("e2_freeze02_driver_fail", "scripts/gen_enc_2_e2_formal_driver_freeze02.py")
    raw = tmp_path / "temp" / "chunk.npy"
    driver.write_npy_atomic(raw, np.asarray([1 + 0j], dtype=np.complex128))
    quarantine = tmp_path / "quarantine" / "chunk.npy"
    checkpoint = tmp_path / "checkpoint.json"
    with pytest.raises(driver.FormalDriverError, match="PARTITION_STOP"):
        driver.process_verified_chunk(
            raw_path=raw, receipt_path=tmp_path / "receipt.json", stats_manifest_path=tmp_path / "stats.json",
            audit_path=tmp_path / "audit.npy", quarantine_path=quarantine, checkpoint_path=checkpoint,
            verifier_command=[sys.executable, "-c", "raise SystemExit(7)"], is_audit=False,
            merge_position=3, resource_root=tmp_path,
            wall_start=time.perf_counter(), cpu_start=time.process_time(),
        )
    terminal = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert quarantine.exists() and not raw.exists()
    assert terminal == {"failure_chunk": "chunk.npy", "later_merge": False, "merge_position": 3, "same_run_retry": False, "status": "PARTITION_STOP"}


def test_rc03_storage_bound_and_exact_audit_selection() -> None:
    driver = _load("e2_freeze02_driver_storage", "scripts/gen_enc_2_e2_formal_driver_freeze02.py")
    assert len(driver.audit_chunks("development", "HAND_01")) == 2
    components = {
        "metric_payload": 33_718_272_000 + 94_080_000 + 677_376_000,
        "audit_raw": 3_670_016_000,
        "common_w": 66_453_504,
        "receipts": 578_027_520,
        "manifests": 289_013_760,
        "checkpoint": 268_435_456,
        "quarantine": 19_660_800,
        "misc": 536_870_912,
        "filesystem_overhead": 4_294_967_296,
    }
    total = sum(components.values())
    assert total == 44_213_173_248
    assert total <= 48 * 1024**3
