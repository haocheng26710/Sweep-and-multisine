"""Result-blind small-sample bridge from collapsed to resolved-plenum star models."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from acoustic_encoder.gen_enc.actual_fluid_star_network import solve_clean_node_pressure_block
from acoustic_encoder.gen_enc.forward_acoustic_network import STATE_ANGLES_DEGREES, frozen_frequency_grid
from acoustic_encoder.gen_enc.resolved_plenum_star_network import (
    PLENUM_HALF_SIDE_M,
    PLENUM_HEIGHT_M,
    PLENUM_LINK_AREA_M2,
    PLENUM_LINK_LENGTH_M,
    solve_resolved_clean_block,
)
from scripts.gen_enc_4_topology_preserving_m0_m1 import exact80_members, seeds_for
from scripts.gen_enc_5_obsa_readout_bottleneck_diagnostic import state_signature


OUTPUT = REPO / "outputs/gen_enc/GEN_ENC_7_MODEL_BRIDGE"
NUISANCE = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
M2B_SOURCE = REPO / "src/acoustic_encoder/gen_enc/actual_fluid_star_network.py"
RESOLVED_SOURCE = REPO / "src/acoustic_encoder/gen_enc/resolved_plenum_star_network.py"
OBSB_RESULT = REPO / "outputs/gen_enc/GEN_ENC_6_OBSB_GEOMETRY_OVERLAP/result_summary.json"
LABEL = "GEN_ENC_7_MODEL_BRIDGE_V1"
CELL_COUNT = 8
FREQUENCIES = 208
CENTER_FRACTIONS = (0.125, 0.25, 0.5)
PRIMARY_CENTER_FRACTION = 0.25
PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    def convert(item: Any) -> Any:
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        if isinstance(item, dict):
            return {str(key): convert(inner) for key, inner in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(inner) for inner in item]
        return item

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(convert(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def selected_cells() -> list[int]:
    ranked = sorted(
        range(3675),
        key=lambda index: hashlib.sha256(f"{LABEL}|cell|{index}".encode()).hexdigest(),
    )
    return sorted(ranked[:CELL_COUNT])


def representative_members() -> list[tuple[dict[str, Any], Path]]:
    exact80 = exact80_members()
    return [(exact80[index][1], exact80[index][2]) for index in (0, 20, 40, 60)]


def response_discrepancy(reference: np.ndarray, alternative: np.ndarray) -> tuple[float, float]:
    ref = np.asarray(reference, dtype=np.complex128).reshape(4, -1).copy()
    alt = np.asarray(alternative, dtype=np.complex128).reshape(4, -1).copy()
    relative = float(np.linalg.norm(alt - ref) / np.linalg.norm(ref))
    ref /= np.linalg.norm(ref)
    alt /= np.linalg.norm(alt)
    ref_gram = ref @ ref.conj().T
    alt_gram = alt @ alt.conj().T
    gram_shift = float(np.linalg.norm(alt_gram - ref_gram, ord="fro"))
    return relative, gram_shift


def representative_distances(signatures: np.ndarray, names: list[str]) -> dict[str, Any]:
    rows = []
    for left, right in PAIRS:
        rows.append(
            {
                "representatives": [names[left], names[right]],
                "distance": float(np.linalg.norm(signatures[left] - signatures[right])),
            }
        )
    values = np.asarray([row["distance"] for row in rows])
    return {"minimum": float(np.min(values)), "mean": float(np.mean(values)), "pairwise": rows}


def main() -> int:
    if load(OBSB_RESULT)["terminal_state"] != "OBSB_PRIMARY_GENERATOR_OVERLAP":
        raise RuntimeError("OBSB_CLOSEOUT_REQUIRED")
    representatives = representative_members()
    cells = selected_cells()
    contract = {
        "schema_version": "gen_enc_7_model_bridge_contract_v1",
        "scope": "FOUR_FIXED_REPRESENTATIVES_DEVELOPMENT_ONLY_MODEL_DIFFERENCE_NO_FAMILY_INFERENCE",
        "representatives": [member["member_id"] for member, _ in representatives],
        "representative_rule": "FIRST_FROZEN_MEMBER_OF_EACH_FAMILY_REUSED_FROM_M2_PREFLIGHT",
        "nuisance_cell_indices_zero_based": cells,
        "cell_selection_rule": f"LOWEST_{CELL_COUNT}_SHA256({LABEL}|cell|index)",
        "repeats": [0, 1],
        "frequency_indices": [0, FREQUENCIES - 1],
        "baseline": "M2B_COLLAPSED_SINGLE_CENTRAL_PLENUM_NODE_CLEAN",
        "bridge": "NINE_NODES_EQUALS_FOUR_LOCAL_PLUS_FOUR_BOUNDARY_PLENUM_PLUS_ONE_CENTER_MIC",
        "physical_topology": "SECTOR_I_TO_BOUNDARY_I_TO_CENTER_ONLY_NO_DIRECT_SECTOR_TO_SECTOR_EDGE",
        "plenum_geometry_m": {
            "half_side": PLENUM_HALF_SIDE_M,
            "height": PLENUM_HEIGHT_M,
            "boundary_to_center_link_length": PLENUM_LINK_LENGTH_M,
            "boundary_to_center_link_area": PLENUM_LINK_AREA_M2,
        },
        "center_volume_fractions": list(CENTER_FRACTIONS),
        "primary_center_volume_fraction": PRIMARY_CENTER_FRACTION,
        "thresholds": {
            "observable_median_relative_response_change": 0.01,
            "minimum_observable_representatives": 2,
            "minimum_pair_distance_relative_gain": 0.20,
        },
        "terminal_rules": {
            "SPATIAL_RESOLUTION_RESTORES_CONTRAST": "AT_LEAST_2_OF_4_RESPONSE_CHANGES_GE_1PCT_AND_PRIMARY_MIN_DISTANCE_GAIN_GE_20PCT",
            "SPATIAL_RESOLUTION_OBSERVABLE_NO_CONTRAST_RESCUE": "AT_LEAST_2_OF_4_RESPONSE_CHANGES_GE_1PCT_AND_PRIMARY_MIN_DISTANCE_GAIN_LT_20PCT",
            "FIVE_NODE_ADEQUATE_FOR_FIXED_REPRESENTATIVES": "FEWER_THAN_2_OF_4_RESPONSE_CHANGES_GE_1PCT_AND_ABS_PRIMARY_MIN_DISTANCE_GAIN_LT_20PCT",
            "INCONCLUSIVE_DISCRETIZATION_SENSITIVE": "MIN_DISTANCE_GAIN_SIGN_REVERSES_ACROSS_FIXED_VOLUME_SENSITIVITIES",
        },
        "input_sha256": {
            "nuisance": digest(NUISANCE),
            "m2b_source": digest(M2B_SOURCE),
            "resolved_source": digest(RESOLVED_SOURCE),
            "obsb_result": digest(OBSB_RESULT),
            "representatives": {member["member_id"]: digest(path) for member, path in representatives},
        },
        "candidate_ranking_emitted": False,
        "parameter_search_performed": False,
        "validation_reads": 0,
        "final_test_read": False,
        "m3_authorized": False,
    }
    write(OUTPUT / "diagnostic_contract.json", contract)

    with NUISANCE.open("r", encoding="utf-8", newline="") as stream:
        nuisances = [
            {key: float(value) for key, value in row.items() if key not in {"design_row_id", "u3", "u5", "v5", "u7", "v7", "cell_weight"}}
            for row in csv.DictReader(line for line in stream if not line.startswith("#"))
        ]
    seeds = seeds_for("development")
    frequencies = frozen_frequency_grid()[:FREQUENCIES]
    names = [member["member_id"] for member, _ in representatives]
    baseline_signatures = []
    resolved_signatures: dict[float, list[np.ndarray]] = {fraction: [] for fraction in CENTER_FRACTIONS}
    discrepancy_records: dict[float, list[dict[str, Any]]] = {fraction: [] for fraction in CENTER_FRACTIONS}
    discrepancy_units: dict[float, list[np.ndarray]] = {fraction: [] for fraction in CENTER_FRACTIONS}

    for member, _ in representatives:
        baseline_units = []
        resolved_units = {fraction: [] for fraction in CENTER_FRACTIONS}
        per_fraction_metrics = {fraction: {"relative": [], "gram": []} for fraction in CENTER_FRACTIONS}
        for cell in cells:
            for repeat in (0, 1):
                kwargs = dict(
                    member=member,
                    nuisance=nuisances[cell],
                    cell_index=cell,
                    repeat_index=repeat,
                    frequencies_hz=frequencies,
                    state_angles_degrees=STATE_ANGLES_DEGREES,
                    partition="development",
                    repeat_seed_tuple=seeds,
                    frequency_start_index=0,
                )
                baseline = solve_clean_node_pressure_block(**kwargs, spine_only=False)[..., 4]
                baseline_units.append(state_signature(baseline[..., None], center=True))
                for fraction in CENTER_FRACTIONS:
                    resolved = solve_resolved_clean_block(
                        **kwargs, center_volume_fraction=fraction
                    ).central_pressure
                    resolved_units[fraction].append(state_signature(resolved[..., None], center=True))
                    relative, gram = response_discrepancy(baseline, resolved)
                    per_fraction_metrics[fraction]["relative"].append(relative)
                    per_fraction_metrics[fraction]["gram"].append(gram)
        baseline_signatures.append(np.mean(np.stack(baseline_units), axis=0))
        for fraction in CENTER_FRACTIONS:
            resolved_signatures[fraction].append(np.mean(np.stack(resolved_units[fraction]), axis=0))
            relative = np.asarray(per_fraction_metrics[fraction]["relative"])
            gram = np.asarray(per_fraction_metrics[fraction]["gram"])
            discrepancy_units[fraction].append(np.column_stack((relative, gram)))
            discrepancy_records[fraction].append(
                {
                    "representative": member["member_id"],
                    "median_relative_response_change": float(np.median(relative)),
                    "maximum_relative_response_change": float(np.max(relative)),
                    "median_state_gram_shift": float(np.median(gram)),
                    "audit_units": int(relative.size),
                }
            )

    baseline_matrix = np.stack(baseline_signatures)
    np.save(OUTPUT / "baseline_representative_signatures.npy", baseline_matrix, allow_pickle=False)
    baseline_distances = representative_distances(baseline_matrix, names)
    fraction_results = {}
    gains = []
    for fraction in CENTER_FRACTIONS:
        matrix = np.stack(resolved_signatures[fraction])
        token = str(fraction).replace(".", "p")
        np.save(OUTPUT / f"resolved_center_fraction_{token}_representative_signatures.npy", matrix, allow_pickle=False)
        np.save(
            OUTPUT / f"resolved_center_fraction_{token}_unit_discrepancy.npy",
            np.stack(discrepancy_units[fraction]),
            allow_pickle=False,
        )
        distances = representative_distances(matrix, names)
        minimum_gain = float(distances["minimum"] / baseline_distances["minimum"] - 1.0)
        mean_gain = float(distances["mean"] / baseline_distances["mean"] - 1.0)
        gains.append(minimum_gain)
        fraction_results[str(fraction)] = {
            "representative_discrepancy": discrepancy_records[fraction],
            "representative_distances": distances,
            "minimum_pair_distance_relative_gain": minimum_gain,
            "mean_pair_distance_relative_gain": mean_gain,
            "observable_representative_count": int(
                sum(
                    row["median_relative_response_change"]
                    >= contract["thresholds"]["observable_median_relative_response_change"]
                    for row in discrepancy_records[fraction]
                )
            ),
        }

    sign_reversal = bool(min(gains) < 0.0 < max(gains))
    primary = fraction_results[str(PRIMARY_CENTER_FRACTION)]
    count = primary["observable_representative_count"]
    gain = primary["minimum_pair_distance_relative_gain"]
    if sign_reversal:
        terminal = "MODEL_BRIDGE_INCONCLUSIVE_DISCRETIZATION_SENSITIVE"
    elif count >= 2 and gain >= 0.20:
        terminal = "MODEL_BRIDGE_SPATIAL_RESOLUTION_RESTORES_CONTRAST"
    elif count >= 2 and gain < 0.20:
        terminal = "MODEL_BRIDGE_SPATIAL_RESOLUTION_OBSERVABLE_NO_CONTRAST_RESCUE"
    elif count < 2 and abs(gain) < 0.20:
        terminal = "MODEL_BRIDGE_FIVE_NODE_ADEQUATE_FOR_FIXED_REPRESENTATIVES"
    else:
        terminal = "MODEL_BRIDGE_INCONCLUSIVE_MIXED_SIGNAL"
    result = {
        "terminal_state": terminal,
        "baseline_representative_distances": baseline_distances,
        "center_fraction_results": fraction_results,
        "primary_center_volume_fraction": PRIMARY_CENTER_FRACTION,
        "sensitivity_minimum_gain_sign_reversal": sign_reversal,
        "claim_boundary": "FOUR_FIXED_REPRESENTATIVES_MODEL_DIFFERENCE_ONLY_NOT_EXACT80_FAMILY_INFERENCE_NOT_PHYSICAL_VALIDATION",
        "candidate_ranking_emitted": False,
        "parameter_search_performed": False,
        "validation_reads": 0,
        "final_test_read": False,
        "m3_authorized": False,
        "next_action": "REVIEW_MODEL_BRIDGE_BEFORE_ANY_EXACT80_OR_FULL_WAVE_EXTENSION",
    }
    write(OUTPUT / "result_summary.json", result)
    print(terminal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
