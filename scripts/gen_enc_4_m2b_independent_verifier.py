"""Independent arithmetic verifier for the M2-B representative preflight."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "outputs/gen_enc/GEN_ENC_4_M2B_SPINE_WINDOW_PREFLIGHT"
CONTRACT = REPO / "outputs/gen_enc/GEN_ENC_4_CAD_TO_EDGE_ROUTE_AUDIT/m2b_preexecution_contract.json"
M2A_CONTRACT = REPO / "outputs/gen_enc/GEN_ENC_4_M2A_MECHANISM_PREFLIGHT/preflight_contract.json"
NUISANCE = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
SEEDS = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    result = load(ROOT / "result_summary.json")
    records = load(ROOT / "case_metrics.json")["records"]
    geometry = load(ROOT / "geometry_audit.json")["records"]
    contract = load(CONTRACT)
    expected_hashes = {"m2b_contract": digest(CONTRACT), "m2a_contract": digest(M2A_CONTRACT), "nuisance": digest(NUISANCE), "seeds": digest(SEEDS)}
    if result["input_sha256"] != expected_hashes:
        raise RuntimeError("INPUT_HASH_MISMATCH")
    if len(records) != 4 * 8 * 2 or any(not row["passive_reciprocal_finite"] for row in records):
        raise RuntimeError("CASE_OR_VALIDITY_FAIL")
    max_residual = max(row["max_sector_volume_residual_m3"] for row in geometry)
    gate = contract["preflight_gate"]
    summaries = []
    pass_count = 0
    for member_id in ("HAND_01", "NEAR_01", "RANDOM_01", "PHYSICS_01"):
        subset = [row for row in records if row["member_id"] == member_id]
        relative = np.asarray([row["relative_response_change"] for row in subset])
        noise = np.asarray([row["mechanism_to_sensor_noise_ratio"] for row in subset])
        grams = np.asarray([row["state_gram_frobenius_shift"] for row in subset])
        passed = bool(np.median(relative) >= gate["relative_response_change_median_min"] and np.median(noise) >= gate["mechanism_to_sensor_noise_median_min"])
        pass_count += int(passed)
        summaries.append((member_id, float(np.median(relative)), float(np.quantile(relative, .25)), float(np.median(noise)), float(np.median(grams)), passed))
    overall = bool(pass_count >= gate["minimum_representatives_passing"] and max_residual <= gate["all_baseline_and_ablation_sector_volumes_match_targets_abs_m3"])
    expected_terminal = "M2B_SPINE_WINDOW_MECHANISM_OBSERVABLE" if overall else "M2B_SPINE_WINDOW_MECHANISM_NOT_ACTIONABLE"
    if result["terminal_state"] != expected_terminal or result["representative_pass_count"] != pass_count or result["preflight_gate_pass"] != overall:
        raise RuntimeError("TERMINAL_RECOMPUTE_FAIL")
    for stored, rebuilt in zip(result["summaries"], summaries):
        member_id, relative, q25, noise, grams, passed = rebuilt
        if stored["member_id"] != member_id or stored["preflight_gate_pass"] != passed:
            raise RuntimeError("SUMMARY_GATE_FAIL")
        np.testing.assert_allclose([stored["relative_response_change_median"], stored["relative_response_change_q25"], stored["mechanism_to_sensor_noise_ratio_median"], stored["state_gram_frobenius_shift_median"]], [relative, q25, noise, grams], rtol=1e-14, atol=0.0)
    report = {"verifier": "PASS", "case_count": len(records), "representative_pass_count_recomputed": pass_count, "terminal_state_recomputed": expected_terminal, "maximum_volume_residual_recomputed_m3": max_residual, "validation_reads": 0, "final_test_read": False}
    (ROOT / "independent_verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M2B_INDEPENDENT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
