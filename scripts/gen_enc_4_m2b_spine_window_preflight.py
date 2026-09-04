"""Execute the frozen development-only M2-B spine/window ablation preflight."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from acoustic_encoder.gen_enc.actual_fluid_star_network import compile_member_geometry, solve_forward_block
from acoustic_encoder.gen_enc.forward_acoustic_network import STATE_ANGLES_DEGREES, frozen_frequency_grid


OUTPUT = REPO / "outputs/gen_enc/GEN_ENC_4_M2B_SPINE_WINDOW_PREFLIGHT"
ROUTE_ROOT = REPO / "outputs/gen_enc/GEN_ENC_4_CAD_TO_EDGE_ROUTE_AUDIT"
CONTRACT = ROUTE_ROOT / "m2b_preexecution_contract.json"
M2A_CONTRACT = REPO / "outputs/gen_enc/GEN_ENC_4_M2A_MECHANISM_PREFLIGHT/preflight_contract.json"
NUISANCE = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
SEEDS = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"
IDENTITIES = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances"
MODEL_SOURCE = REPO / "src/acoustic_encoder/gen_enc/actual_fluid_star_network.py"
EXACT80_CONTRACT_DOC = REPO / "docs/experiment/gen_enc/GEN_ENC_4_M2B_EXACT80_DEVELOPMENT_CONTRACT.md"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, value: dict) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def gram(response: np.ndarray) -> np.ndarray:
    flat = response.reshape(4, -1)
    flat = flat / np.linalg.norm(flat, axis=1)[:, None]
    return flat @ flat.conj().T


def main() -> int:
    contract = load(CONTRACT)
    if contract["status"] != "CONTRACT_FROZEN_EXECUTION_NOT_AUTHORIZED":
        raise RuntimeError("CONTRACT_STATE_UNEXPECTED")
    cells = load(M2A_CONTRACT)["nuisance_cell_indices_zero_based"]
    with NUISANCE.open("r", encoding="utf-8", newline="") as stream:
        nuisances = [{key: float(value) for key, value in row.items() if key not in {"design_row_id", "u3", "u5", "v5", "u7", "v7", "cell_weight"}} for row in csv.DictReader(line for line in stream if not line.startswith("#"))]
    seed_values = load(SEEDS)["nuisance_partition_seeds"]["development_training"]
    seeds = (int(seed_values[0]), int(seed_values[1]))
    member_specs = (("HAND_DESIGNED", "HAND_01.identity.json"), ("NEAR_INDEPENDENT", "NEAR_01.identity.json"), ("FIXED_SEED_RANDOM_DISORDERED", "RANDOM_01.identity.json"), ("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json"))
    members = [load(IDENTITIES / family / filename) for family, filename in member_specs]
    frequencies = frozen_frequency_grid()[:208]

    geometry_audit = []
    for member in members:
        base = compile_member_geometry(member, spine_only=False)
        ablated = compile_member_geometry(member, spine_only=True)
        geometry_audit.append({
            "member_id": member["member_id"],
            "baseline_root_lengths_m": [x.root_length_m for x in base],
            "spine_only_root_lengths_m": [x.root_length_m for x in ablated],
            "baseline_entry_areas_m2": [x.window_union_area_m2 for x in base],
            "spine_only_entry_areas_m2": [x.window_union_area_m2 for x in ablated],
            "max_sector_volume_residual_m3": max(abs(x.segment_volume_m3 - x.target_volume_m3) for x in (*base, *ablated)),
        })
    write("geometry_audit.json", {"records": geometry_audit})

    records = []
    all_valid = True
    for member in members:
        for cell in cells:
            nuisance = nuisances[cell]
            for repeat in (0, 1):
                kwargs = dict(member=member, nuisance=nuisance, cell_index=cell, repeat_index=repeat, frequencies_hz=frequencies, state_angles_degrees=STATE_ANGLES_DEGREES, partition="development", repeat_seed_tuple=seeds, frequency_start_index=0)
                baseline = solve_forward_block(spine_only=False, include_additive_sensor_noise=False, **kwargs)
                baseline_noisy = solve_forward_block(spine_only=False, include_additive_sensor_noise=True, **kwargs)
                ablated = solve_forward_block(spine_only=True, include_additive_sensor_noise=False, **kwargs)
                delta_norm = float(np.linalg.norm(baseline.central_pressure - ablated.central_pressure))
                noise_norm = float(np.linalg.norm(baseline_noisy.central_pressure - baseline.central_pressure))
                valid = baseline.passive and baseline.reciprocal and baseline.numerically_valid and ablated.passive and ablated.reciprocal and ablated.numerically_valid
                all_valid = all_valid and valid
                records.append({
                    "member_id": member["member_id"], "family_id": member["family_id"], "cell_index": cell, "repeat_index": repeat,
                    "relative_response_change": delta_norm / float(np.linalg.norm(baseline.central_pressure)),
                    "mechanism_to_sensor_noise_ratio": delta_norm / noise_norm,
                    "state_gram_frobenius_shift": float(np.linalg.norm(gram(baseline.central_pressure) - gram(ablated.central_pressure))),
                    "passive_reciprocal_finite": bool(valid),
                })
    write("case_metrics.json", {"records": records})
    gate = contract["preflight_gate"]
    summaries = []
    pass_count = 0
    for member in members:
        subset = [r for r in records if r["member_id"] == member["member_id"]]
        relative = np.asarray([r["relative_response_change"] for r in subset])
        noise = np.asarray([r["mechanism_to_sensor_noise_ratio"] for r in subset])
        grams = np.asarray([r["state_gram_frobenius_shift"] for r in subset])
        passed = bool(np.median(relative) >= gate["relative_response_change_median_min"] and np.median(noise) >= gate["mechanism_to_sensor_noise_median_min"])
        pass_count += int(passed)
        summaries.append({"member_id": member["member_id"], "family_id": member["family_id"], "case_count": len(subset), "relative_response_change_median": float(np.median(relative)), "relative_response_change_q25": float(np.quantile(relative, .25)), "mechanism_to_sensor_noise_ratio_median": float(np.median(noise)), "state_gram_frobenius_shift_median": float(np.median(grams)), "preflight_gate_pass": passed})
    max_residual = max(x["max_sector_volume_residual_m3"] for x in geometry_audit)
    gate_pass = bool(all_valid and max_residual <= gate["all_baseline_and_ablation_sector_volumes_match_targets_abs_m3"] and pass_count >= gate["minimum_representatives_passing"])
    terminal = "M2B_SPINE_WINDOW_MECHANISM_OBSERVABLE" if gate_pass else "M2B_SPINE_WINDOW_MECHANISM_NOT_ACTIONABLE"
    result = {
        "terminal_state": terminal, "preflight_gate_pass": gate_pass, "representative_pass_count": pass_count,
        "all_cases_passive_reciprocal_finite": all_valid, "max_sector_volume_residual_m3": max_residual,
        "summaries": summaries, "scope": "FOUR_REPRESENTATIVE_DEVELOPMENT_ONLY_NO_FAMILY_INFERENCE",
        "full_exact80_m2_authorized": gate_pass, "m3_authorized": False,
        "next_action": "FREEZE_EXACT80_M2B_DEVELOPMENT_CONTRACT" if gate_pass else "STOP_M2_AND_DO_NOT_ENTER_M3",
        "input_sha256": {"m2b_contract": digest(CONTRACT), "m2a_contract": digest(M2A_CONTRACT), "nuisance": digest(NUISANCE), "seeds": digest(SEEDS)},
        "validation_reads": 0, "final_test_read": False,
    }
    write("result_summary.json", result)
    if gate_pass:
        write("exact80_development_contract.json", {
            "schema_version": "gen_enc_4_m2b_exact80_development_contract_v1",
            "status": "CONTRACT_FROZEN_EXECUTION_NOT_STARTED",
            "partition": "development",
            "member_count": 80,
            "nuisance_cell_count": 3675,
            "repeat_count": 2,
            "frequency_indices": [0, 207],
            "comparison_arms": ["CAD_BASELINE", "SPINE_ONLY_ABLATION"],
            "paired_effect": "CAD_BASELINE_MINUS_SPINE_ONLY_ABLATION",
            "terminal_pass": {"all_80_feasible": True, "all_cases_passive_reciprocal_finite": True, "paired_effect_between_within_ratio_min": 1.0, "stable_rank_min": 3, "minimum_fwer_significant_family_pairs": 1},
            "validation_authorized": False,
            "final_test_read": False,
            "m3_authorized": False,
            "source_sha256": {"model": digest(MODEL_SOURCE), "contract_document": digest(EXACT80_CONTRACT_DOC), "representative_preflight_result": digest(OUTPUT / "result_summary.json")},
        })
    print(terminal)
    return 0 if all_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
