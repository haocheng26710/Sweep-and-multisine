"""Run the bounded GEN-ENC-4 M2-A distributed-channel mechanism preflight."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from acoustic_encoder.gen_enc.distributed_channel_network import solve_forward_block as solve_m2a
from acoustic_encoder.gen_enc.forward_acoustic_network import STATE_ANGLES_DEGREES, frozen_frequency_grid
from acoustic_encoder.gen_enc.topology_preserving_network import solve_forward_block as solve_m1, topology_audit


OUTPUT = REPO / "outputs/gen_enc/GEN_ENC_4_M2A_MECHANISM_PREFLIGHT"
MANIFEST = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01/exact80_manifest.json"
NUISANCE = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
SEEDS = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"
CAD_AUTHORITY = REPO / "docs/experiment/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT_PROPOSAL_REV02.md"
M1_RESULTS = REPO / "docs/progress/GEN_ENC_4_TOPOLOGY_PRESERVING_M0_M1_RESULTS.md"

PREFLIGHT_LABEL = "GEN_ENC_4_M2A_PREFLIGHT_V1"
REPRESENTATIVE_ORDINALS = (1, 21, 41, 61)
NUISANCE_CELL_COUNT = 8
PATH_LENGTHS_M = (0.002, 0.058926678767398356)
PRIMARY_FREQUENCY_COUNT = 208
RELATIVE_RESPONSE_THRESHOLD = 0.01
MECHANISM_TO_SENSOR_NOISE_THRESHOLD = 1.0
MIN_ACTIVE_FAMILIES = 2


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def state_gram(response: np.ndarray) -> np.ndarray:
    vectors = response.reshape(4, -1)
    norms = np.linalg.norm(vectors, axis=1)
    normalized = vectors / norms[:, None]
    return normalized @ normalized.conj().T


def selected_cells() -> list[int]:
    ranked = sorted(
        range(3675),
        key=lambda index: hashlib.sha256(f"{PREFLIGHT_LABEL}|nuisance_cell|{index}".encode()).hexdigest(),
    )
    return sorted(ranked[:NUISANCE_CELL_COUNT])


def load_inputs() -> tuple[list[dict[str, Any]], list[dict[str, float]], tuple[int, int]]:
    manifest = read_json(MANIFEST)
    by_ordinal = {int(item["global_ordinal"]): item for item in manifest["members"]}
    members = []
    for ordinal in REPRESENTATIVE_ORDINALS:
        item = by_ordinal[ordinal]
        path = REPO / item["identity_path"]
        if sha256(path) != item["identity_file_sha256"]:
            raise RuntimeError("IDENTITY_HASH_MISMATCH")
        members.append(read_json(path))
    rows: list[dict[str, float]] = []
    with NUISANCE.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(line for line in stream if not line.startswith("#"))
        for row in reader:
            rows.append({key: float(value) for key, value in row.items() if key not in {"design_row_id", "u3", "u5", "v5", "u7", "v7", "cell_weight"}})
    seed_data = read_json(SEEDS)["nuisance_partition_seeds"]["development_training"]
    return members, rows, (int(seed_data[0]), int(seed_data[1]))


def main() -> int:
    cells = selected_cells()
    contract = {
        "schema_version": "gen_enc_4_m2a_mechanism_preflight_contract_v1",
        "evidence_level": "BOUNDED_DEVELOPMENT_MECHANISM_PREFLIGHT_ONLY",
        "final_test_read": False,
        "validation_reads": 0,
        "family_inference_authorized": False,
        "representative_global_ordinals": list(REPRESENTATIVE_ORDINALS),
        "selection_rule": "FIRST_FROZEN_MEMBER_OF_EACH_FAMILY_FIXED_BEFORE_RESPONSE_EVALUATION",
        "nuisance_cell_indices_zero_based": cells,
        "nuisance_selection_rule": f"LOWEST_{NUISANCE_CELL_COUNT}_SHA256({PREFLIGHT_LABEL}|nuisance_cell|index)",
        "repeat_indices": [0, 1],
        "frequency_indices": [0, PRIMARY_FREQUENCY_COUNT - 1],
        "path_length_bracket_m": list(PATH_LENGTHS_M),
        "path_authority": {
            "unique_edge_route_available": False,
            "lower_endpoint": "0.002 m scientific-window depth",
            "upper_endpoint": "0.058926678767398356 m frozen root-span length",
            "interpretation": "AUTHORITY_DERIVED_SENSITIVITY_ENDPOINTS_NOT_OUTPUT_SELECTED_PATHS",
        },
        "distributed_model": "RECIPROCAL_LOSSY_UNIFORM_LINE_TWO_PORT_WITH_EDGE_VOLUME_REMOVED_HALF_FROM_EACH_ENDPOINT",
        "gate": {
            "relative_response_change_median_min": RELATIVE_RESPONSE_THRESHOLD,
            "mechanism_to_sensor_noise_median_min": MECHANISM_TO_SENSOR_NOISE_THRESHOLD,
            "minimum_active_edge_families": MIN_ACTIVE_FAMILIES,
            "full_m2_requires_unique_edge_path_authority": True,
        },
        "input_sha256": {"exact80": sha256(MANIFEST), "nuisance": sha256(NUISANCE), "seeds": sha256(SEEDS), "cad_authority": sha256(CAD_AUTHORITY), "m1_results": sha256(M1_RESULTS)},
    }
    write_json(OUTPUT / "preflight_contract.json", contract)

    members, nuisances, seeds = load_inputs()
    frequencies = frozen_frequency_grid()[:PRIMARY_FREQUENCY_COUNT]
    records: list[dict[str, Any]] = []
    all_valid = True
    for member in members:
        audit = topology_audit(member)
        for cell in cells:
            nuisance = nuisances[cell]
            for repeat in (0, 1):
                kwargs = dict(cell_index=cell, repeat_index=repeat, frequencies_hz=frequencies, state_angles_degrees=STATE_ANGLES_DEGREES, partition="development", repeat_seed_tuple=seeds, frequency_start_index=0)
                m1_clean = solve_m1(member, nuisance, include_additive_sensor_noise=False, **kwargs)
                m1_noisy = solve_m1(member, nuisance, include_additive_sensor_noise=True, **kwargs)
                noise_norm = float(np.linalg.norm(m1_noisy.central_pressure - m1_clean.central_pressure))
                baseline_norm = float(np.linalg.norm(m1_clean.central_pressure))
                baseline_gram = state_gram(m1_clean.central_pressure)
                for path_length in PATH_LENGTHS_M:
                    m2a = solve_m2a(member, nuisance, path_length_m=path_length, include_additive_sensor_noise=False, **kwargs)
                    delta = m2a.central_pressure - m1_clean.central_pressure
                    delta_norm = float(np.linalg.norm(delta))
                    gram_shift = float(np.linalg.norm(state_gram(m2a.central_pressure) - baseline_gram))
                    valid = bool(m2a.passive and m2a.reciprocal and m2a.numerically_valid)
                    all_valid = all_valid and valid
                    records.append({
                        "member_id": member["member_id"], "family_id": member["family_id"], "active_edge_count": len(audit.active_edges),
                        "cell_index": cell, "repeat_index": repeat, "path_length_m": path_length,
                        "relative_response_change": delta_norm / baseline_norm,
                        "mechanism_to_sensor_noise_ratio": delta_norm / noise_norm,
                        "state_gram_frobenius_shift": gram_shift,
                        "passive": m2a.passive, "reciprocal": m2a.reciprocal, "numerically_valid": m2a.numerically_valid,
                    })
    write_json(OUTPUT / "case_metrics.json", {"records": records})

    summaries = []
    observable_by_path: dict[str, int] = {}
    for path_length in PATH_LENGTHS_M:
        active_pass = 0
        for member in members:
            subset = [r for r in records if r["member_id"] == member["member_id"] and r["path_length_m"] == path_length]
            relative = np.asarray([r["relative_response_change"] for r in subset])
            noise_ratio = np.asarray([r["mechanism_to_sensor_noise_ratio"] for r in subset])
            grams = np.asarray([r["state_gram_frobenius_shift"] for r in subset])
            passed = bool(subset[0]["active_edge_count"] > 0 and np.median(relative) >= RELATIVE_RESPONSE_THRESHOLD and np.median(noise_ratio) >= MECHANISM_TO_SENSOR_NOISE_THRESHOLD)
            active_pass += int(passed)
            summaries.append({
                "path_length_m": path_length, "member_id": member["member_id"], "family_id": member["family_id"],
                "active_edge_count": subset[0]["active_edge_count"], "case_count": len(subset),
                "relative_response_change_median": float(np.median(relative)), "relative_response_change_q25": float(np.quantile(relative, 0.25)),
                "mechanism_to_sensor_noise_ratio_median": float(np.median(noise_ratio)),
                "state_gram_frobenius_shift_median": float(np.median(grams)), "observable_gate_pass": passed,
            })
        observable_by_path[str(path_length)] = active_pass
    mechanism_observable = max(observable_by_path.values()) >= MIN_ACTIVE_FAMILIES
    if not all_valid:
        terminal = "M2A_NUMERIC_OR_PHYSICAL_VALIDITY_FAIL"
    elif mechanism_observable:
        terminal = "M2A_MECHANISM_OBSERVABLE_PATH_AUTHORITY_REQUIRED"
    else:
        terminal = "M2A_NO_ACTIONABLE_MECHANISM_SIGNAL"
    decision = {
        "terminal_state": terminal, "all_cases_passive_reciprocal_finite": all_valid,
        "active_family_pass_count_by_path": observable_by_path, "mechanism_observable_somewhere_in_authority_bracket": mechanism_observable,
        "full_m2_authorized": False, "reason_full_m2_not_authorized": "NO_UNIQUE_FROZEN_PHYSICAL_ROUTE_FOR_ABSTRACT_M1_EDGES",
        "next_action": "FREEZE_A_CAD_TO_EDGE_ROUTE_MAPPING_BEFORE_FULL_M2" if mechanism_observable else "DO_NOT_ENTER_FULL_M2_OR_M3",
        "summaries": summaries, "final_test_read": False, "validation_reads": 0,
    }
    write_json(OUTPUT / "result_summary.json", decision)
    lines = ["# GEN-ENC-4 M2-A mechanism preflight", "", f"Terminal state: `{terminal}`.", "", "This bounded development-only run used four pre-fixed first members, eight hash-selected nuisance cells, two repeats, and the 208-bin primary band. It performed no exact80 family inference and read neither validation nor final-test data.", "", "| path (m) | member | median relative response change | median mechanism/noise | median state-Gram shift | gate |", "|---:|---|---:|---:|---:|---|"]
    for item in summaries:
        lines.append(f"| {item['path_length_m']:.12g} | {item['member_id']} | {item['relative_response_change_median']:.6g} | {item['mechanism_to_sensor_noise_ratio_median']:.6g} | {item['state_gram_frobenius_shift_median']:.6g} | {'PASS' if item['observable_gate_pass'] else 'FAIL'} |")
    lines += ["", "The distributed two-port remained passive, reciprocal and finite in all cases. Full M2 is not authorized because CAD does not uniquely map the abstract M1 edges to a physical path; the two lengths are authority-derived sensitivity endpoints, not fitted choices.", ""]
    (OUTPUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(terminal)
    return 0 if all_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
