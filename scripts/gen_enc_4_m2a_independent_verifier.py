"""Independent arithmetic verifier for GEN-ENC-4 M2-A preflight outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "outputs/gen_enc/GEN_ENC_4_M2A_MECHANISM_PREFLIGHT"


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    contract = load("preflight_contract.json")
    result = load("result_summary.json")
    records = load("case_metrics.json")["records"]
    if contract["final_test_read"] or contract["validation_reads"] != 0 or contract["family_inference_authorized"]:
        raise RuntimeError("SCOPE_SEAL_FAIL")
    for key, relative in (("exact80", "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01/exact80_manifest.json"), ("nuisance", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"), ("seeds", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"), ("cad_authority", "docs/experiment/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT_PROPOSAL_REV02.md"), ("m1_results", "docs/progress/GEN_ENC_4_TOPOLOGY_PRESERVING_M0_M1_RESULTS.md")):
        if sha256(REPO / relative) != contract["input_sha256"][key]:
            raise RuntimeError(f"INPUT_HASH_FAIL:{key}")
    expected_cases = 4 * len(contract["nuisance_cell_indices_zero_based"]) * len(contract["repeat_indices"]) * len(contract["path_length_bracket_m"])
    if len(records) != expected_cases:
        raise RuntimeError("CASE_COUNT_FAIL")
    if not all(r["passive"] and r["reciprocal"] and r["numerically_valid"] for r in records):
        raise RuntimeError("PHYSICAL_VALIDITY_FAIL")
    rebuilt = []
    pass_counts = {}
    for path in contract["path_length_bracket_m"]:
        count = 0
        for ordinal in contract["representative_global_ordinals"]:
            member_index = contract["representative_global_ordinals"].index(ordinal)
            member_id = ("HAND_01", "NEAR_01", "RANDOM_01", "PHYSICS_01")[member_index]
            subset = [r for r in records if r["member_id"] == member_id and r["path_length_m"] == path]
            relative = np.asarray([r["relative_response_change"] for r in subset])
            noise = np.asarray([r["mechanism_to_sensor_noise_ratio"] for r in subset])
            grams = np.asarray([r["state_gram_frobenius_shift"] for r in subset])
            passed = bool(subset[0]["active_edge_count"] > 0 and np.median(relative) >= contract["gate"]["relative_response_change_median_min"] and np.median(noise) >= contract["gate"]["mechanism_to_sensor_noise_median_min"])
            count += int(passed)
            rebuilt.append((path, member_id, float(np.median(relative)), float(np.median(noise)), float(np.median(grams)), passed))
        pass_counts[str(path)] = count
    if pass_counts != result["active_family_pass_count_by_path"]:
        raise RuntimeError("PASS_COUNT_RECOMPUTE_FAIL")
    observable = max(pass_counts.values()) >= contract["gate"]["minimum_active_edge_families"]
    expected_terminal = "M2A_MECHANISM_OBSERVABLE_PATH_AUTHORITY_REQUIRED" if observable else "M2A_NO_ACTIONABLE_MECHANISM_SIGNAL"
    if result["terminal_state"] != expected_terminal or result["full_m2_authorized"]:
        raise RuntimeError("TERMINAL_DECISION_FAIL")
    for stored, recomputed in zip(result["summaries"], rebuilt):
        _, member_id, relative, noise, gram, passed = recomputed
        if stored["member_id"] != member_id or stored["observable_gate_pass"] != passed:
            raise RuntimeError("SUMMARY_ID_OR_GATE_FAIL")
        np.testing.assert_allclose([stored["relative_response_change_median"], stored["mechanism_to_sensor_noise_ratio_median"], stored["state_gram_frobenius_shift_median"]], [relative, noise, gram], rtol=1e-14, atol=0.0)
    report = {"verifier": "PASS", "case_count": len(records), "terminal_state_recomputed": expected_terminal, "input_hashes_match": True, "final_test_read": False, "validation_reads": 0}
    (ROOT / "independent_verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M2A_INDEPENDENT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
