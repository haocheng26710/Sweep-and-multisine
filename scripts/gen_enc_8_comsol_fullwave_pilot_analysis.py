"""Analyze the frozen small-sample COMSOL full-wave pilot responses."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import numpy as np


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from acoustic_encoder.gen_enc.actual_fluid_star_network import assemble_system_matrices
from acoustic_encoder.gen_enc.e2_authority import directional_port_weights
from scripts.gen_enc_4_topology_preserving_m0_m1 import exact80_members, seeds_for
from scripts.gen_enc_5_obsa_readout_bottleneck_diagnostic import state_signature


ROOT = REPO / "outputs/gen_enc/GEN_ENC_8_COMSOL_FULLWAVE_PILOT"
RAW = ROOT / "raw_response_compact.json"
ORDER = ("HAND_01", "NEAR_01", "RANDOM_01", "PHYSICS_01")
PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def expanded_response(port_transfer: np.ndarray) -> np.ndarray:
    """Rebuild the frozen four-state x four-port response by linearity."""
    result = np.empty((4, 4, port_transfer.shape[1]), dtype=np.complex128)
    for state_index, angle in enumerate((0.0, 90.0, 180.0, 270.0)):
        weights = directional_port_weights(angle, 0.0)
        result[state_index] = weights[:, None] * port_transfer
    return result


def nominal_network_transfer(member: dict[str, object], frequencies: np.ndarray, *, lossless: bool) -> np.ndarray:
    working = json.loads(json.dumps(member))
    if lossless:
        parameters = working["parameters"]
        for angle in (0, 90, 180, 270):
            parameters[f"loss_{angle}"] = 0.0
    nuisance = {
        "common_frequency_axis_shift_relative": 0.0,
        "batch_correlated_manufacturing_percent": 0.0,
        "independent_manufacturing_percent": 0.0,
    }
    matrices, _, passive, reciprocal = assemble_system_matrices(
        working,
        nuisance,
        cell_index=0,
        repeat_index=0,
        frequencies_hz=frequencies,
        partition="development",
        repeat_seed_tuple=seeds_for("development"),
        spine_only=False,
    )
    if not passive or not reciprocal:
        raise RuntimeError("NOMINAL_NETWORK_VALIDITY_FAILURE")
    sources = np.zeros((5, 4), dtype=np.complex128)
    sources[:4, :] = np.eye(4)
    solution = np.linalg.solve(matrices, np.broadcast_to(sources, (frequencies.size, 5, 4)))
    return solution[:, 4, :].T


def distances(signatures: np.ndarray) -> dict[str, object]:
    rows = []
    for left, right in PAIRS:
        rows.append({
            "representatives": [ORDER[left], ORDER[right]],
            "distance": float(np.linalg.norm(signatures[left] - signatures[right])),
        })
    values = np.asarray([row["distance"] for row in rows])
    return {"minimum": float(values.min()), "mean": float(values.mean()), "pairwise": rows}


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    frequencies = np.asarray(raw["frequencies_hz"], dtype=float)
    members = {m[1]["member_id"]: m[1] for m in exact80_members() if m[1]["member_id"] in ORDER}

    coarse_hand = 1j * np.asarray(raw["responses_imaginary_pa"]["HAND_01"], dtype=float)
    fine_hand = 1j * np.asarray(raw["hand_fine_responses_imaginary_pa"], dtype=float)
    relative_l2 = float(np.linalg.norm(fine_hand - coarse_hand) / np.linalg.norm(fine_hand))
    coarse_signature = state_signature(expanded_response(coarse_hand), center=False)
    fine_signature = state_signature(expanded_response(fine_hand), center=False)
    signature_shift = float(np.linalg.norm(fine_signature - coarse_signature))

    full_signatures = []
    lossy_signatures = []
    lossless_signatures = []
    representatives = []
    for member_id in ORDER:
        transfer = 1j * np.asarray(raw["responses_imaginary_pa"][member_id], dtype=float)
        full_response = expanded_response(transfer)
        lossy_response = expanded_response(nominal_network_transfer(members[member_id], frequencies, lossless=False))
        lossless_response = expanded_response(nominal_network_transfer(members[member_id], frequencies, lossless=True))
        full_sig = state_signature(full_response, center=False)
        lossy_sig = state_signature(lossy_response, center=False)
        lossless_sig = state_signature(lossless_response, center=False)
        full_signatures.append(full_sig)
        lossy_signatures.append(lossy_sig)
        lossless_signatures.append(lossless_sig)
        representatives.append({
            "member_id": member_id,
            "fullwave_state_contrast_fraction": float(full_sig[-1]),
            "m2b_lossy_state_contrast_fraction": float(lossy_sig[-1]),
            "m2b_lossless_state_contrast_fraction": float(lossless_sig[-1]),
            "fullwave_vs_m2b_lossy_signature_distance": float(np.linalg.norm(full_sig - lossy_sig)),
            "fullwave_vs_m2b_lossless_signature_distance": float(np.linalg.norm(full_sig - lossless_sig)),
        })

    full_distance = distances(np.stack(full_signatures))
    lossy_distance = distances(np.stack(lossy_signatures))
    lossless_distance = distances(np.stack(lossless_signatures))
    terminal = (
        "COMSOL_PILOT_NUMERICALLY_STABLE_MODEL_DISCREPANCY_OBSERVED"
        if relative_l2 <= 0.02 and signature_shift <= 0.05
        else "COMSOL_PILOT_MESH_SENSITIVE"
    )
    result = {
        "schema_version": "gen_enc_8_comsol_fullwave_pilot_result_v1",
        "scope": "FOUR_FIXED_REPRESENTATIVES_DEVELOPMENT_ONLY_2D_AREA_EQUIVALENT_NO_FAMILY_INFERENCE",
        "terminal_state": terminal,
        "mesh_gate": {
            "member": "HAND_01",
            "coarse_automatic_size": raw["mesh_automatic_size"],
            "fine_automatic_size": raw["hand_fine_mesh_automatic_size"],
            "relative_l2_response_change": relative_l2,
            "state_signature_distance": signature_shift,
            "thresholds": {"relative_l2_response_change_max": 0.02, "state_signature_distance_max": 0.05},
            "pass": bool(relative_l2 <= 0.02 and signature_shift <= 0.05),
        },
        "representatives": representatives,
        "representative_signature_distances": {
            "comsol_fullwave": full_distance,
            "m2b_lossy": lossy_distance,
            "m2b_lossless": lossless_distance,
        },
        "interpretation_limits": [
            "This is a 2D area-equivalent pressure-acoustics pilot, not a 3D manufactured-geometry validation.",
            "The COMSOL pilot is lossless; lossy and lossless M2-B comparisons are both reported to expose that mismatch.",
            "Only four pre-fixed development representatives and twelve sparse frequencies were used.",
            "No family-level, exact80, validation, final-test, printing, or experimental claim is authorized.",
        ],
    }
    write_json(ROOT / "result_summary.json", result)
    write_json(ROOT / "terminal.json", {"terminal_state": terminal, "mesh_gate_pass": result["mesh_gate"]["pass"]})
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["mesh_gate"]["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
