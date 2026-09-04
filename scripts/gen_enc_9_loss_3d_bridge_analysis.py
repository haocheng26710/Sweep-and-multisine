"""Analyze loss and dimensional controls for the HAND_01/NEAR_01 overlap."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from acoustic_encoder.gen_enc.e2_authority import directional_port_weights
from scripts.gen_enc_5_obsa_readout_bottleneck_diagnostic import state_signature


ROOT = REPO / "outputs/gen_enc/GEN_ENC_9_LOSS_3D_BRIDGE"
PILOT8 = REPO / "outputs/gen_enc/GEN_ENC_8_COMSOL_FULLWAVE_PILOT/raw_response_compact.json"
MEMBERS = ("HAND_01", "NEAR_01")


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def complex_array(value: object) -> np.ndarray:
    data = np.asarray(value, dtype=float)
    if data.shape[-1] != 2:
        raise RuntimeError("COMPLEX_PAIR_AXIS_REQUIRED")
    return data[..., 0] + 1j * data[..., 1]


def expanded_response(port_transfer: np.ndarray) -> np.ndarray:
    result = np.empty((4, 4, port_transfer.shape[1]), dtype=np.complex128)
    for state_index, angle in enumerate((0.0, 90.0, 180.0, 270.0)):
        result[state_index] = directional_port_weights(angle, 0.0)[:, None] * port_transfer
    return result


def signature(port_transfer: np.ndarray) -> np.ndarray:
    return state_signature(expanded_response(port_transfer), center=False)


def pair_distance(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.linalg.norm(signature(left) - signature(right)))


def relative_l2(reference: np.ndarray, alternative: np.ndarray) -> float:
    return float(np.linalg.norm(alternative - reference) / np.linalg.norm(reference))


def main() -> int:
    lossless = load("lossless2d_dense_raw.json")
    lossy = load("lossy2d_dense_raw.json")
    spot3d = load("spot3d_raw.json")
    fine3d = load("spot3d_hand_fine_raw.json")
    refinement3d = load("spot3d_refinement_raw.json")
    lossy3d = load("lossy3d_mesh_ladder_raw.json")
    lossy3d_final = load("lossy3d_final_refinement_raw.json")
    near_lossy3d_size1 = load("near_lossy3d_size1_raw.json")
    extruded = load("extruded_area3d_control_raw.json")
    pilot8 = json.loads(PILOT8.read_text(encoding="utf-8"))

    dense_lossless = {key: complex_array(lossless["responses"][key]) for key in MEMBERS}
    dense_distances = {"0": pair_distance(dense_lossless["HAND_01"], dense_lossless["NEAR_01"])}
    for eta in ("0.005", "0.02"):
        values = {key: complex_array(lossy["responses"][eta][key]) for key in MEMBERS}
        dense_distances[eta] = pair_distance(values["HAND_01"], values["NEAR_01"])

    anchor_positions = [2, 6, 7]
    area2d = {
        key: 1j * np.asarray(pilot8["responses_imaginary_pa"][key], dtype=float)[:, anchor_positions]
        for key in MEMBERS
    }
    extruded3d = {key: complex_array(extruded["responses"][key]) for key in MEMBERS}
    true3d_size4 = {key: complex_array(spot3d["responses"][key]) for key in MEMBERS}
    true3d_size3 = {
        "HAND_01": complex_array(fine3d["responses"]),
        "NEAR_01": complex_array(refinement3d["responses"]["NEAR_01"]["values"]),
    }
    hand_size2 = complex_array(refinement3d["responses"]["HAND_01"]["values"])

    dimensional = {
        "area2d_hand_near_signature_distance": pair_distance(area2d["HAND_01"], area2d["NEAR_01"]),
        "extruded_area3d_hand_near_signature_distance": pair_distance(extruded3d["HAND_01"], extruded3d["NEAR_01"]),
        "true_sections_3d_hand_near_signature_distance": pair_distance(true3d_size3["HAND_01"], true3d_size3["NEAR_01"]),
        "area2d_vs_extruded3d_relative_l2": {
            key: relative_l2(area2d[key], extruded3d[key]) for key in MEMBERS
        },
        "extruded3d_vs_true_sections3d_relative_l2": {
            key: relative_l2(extruded3d[key], true3d_size3[key]) for key in MEMBERS
        },
    }
    mesh_steps = {
        "HAND_size4_to_size3_relative_l2": relative_l2(true3d_size4["HAND_01"], true3d_size3["HAND_01"]),
        "HAND_size4_to_size3_signature_distance": float(np.linalg.norm(signature(true3d_size4["HAND_01"]) - signature(true3d_size3["HAND_01"]))),
        "HAND_size3_to_size2_relative_l2": relative_l2(true3d_size3["HAND_01"], hand_size2),
        "HAND_size3_to_size2_signature_distance": float(np.linalg.norm(signature(true3d_size3["HAND_01"]) - signature(hand_size2))),
        "NEAR_size4_to_size3_relative_l2": relative_l2(true3d_size4["NEAR_01"], true3d_size3["NEAR_01"]),
        "NEAR_size4_to_size3_signature_distance": float(np.linalg.norm(signature(true3d_size4["NEAR_01"]) - signature(true3d_size3["NEAR_01"]))),
    }
    lossy3d_values = {
        member: {
            size: complex_array(values)
            for size, values in lossy3d["responses"][member].items()
        }
        for member in MEMBERS
    }
    lossy3d_values["HAND_01"]["1"] = complex_array(lossy3d_final["responses"]["HAND_01"]["values"])
    lossy3d_values["NEAR_01"]["2"] = complex_array(lossy3d_final["responses"]["NEAR_01"]["values"])
    lossy3d_values["NEAR_01"]["1"] = complex_array(near_lossy3d_size1["responses"])
    lossy_mesh_steps = {
        "HAND_size4_to_size3_relative_l2": relative_l2(lossy3d_values["HAND_01"]["4"], lossy3d_values["HAND_01"]["3"]),
        "HAND_size4_to_size3_signature_distance": float(np.linalg.norm(signature(lossy3d_values["HAND_01"]["4"]) - signature(lossy3d_values["HAND_01"]["3"]))),
        "HAND_size3_to_size2_relative_l2": relative_l2(lossy3d_values["HAND_01"]["3"], lossy3d_values["HAND_01"]["2"]),
        "HAND_size3_to_size2_signature_distance": float(np.linalg.norm(signature(lossy3d_values["HAND_01"]["3"]) - signature(lossy3d_values["HAND_01"]["2"]))),
        "NEAR_size4_to_size3_relative_l2": relative_l2(lossy3d_values["NEAR_01"]["4"], lossy3d_values["NEAR_01"]["3"]),
        "NEAR_size4_to_size3_signature_distance": float(np.linalg.norm(signature(lossy3d_values["NEAR_01"]["4"]) - signature(lossy3d_values["NEAR_01"]["3"]))),
        "HAND_size2_to_size1_relative_l2": relative_l2(lossy3d_values["HAND_01"]["2"], lossy3d_values["HAND_01"]["1"]),
        "HAND_size2_to_size1_signature_distance": float(np.linalg.norm(signature(lossy3d_values["HAND_01"]["2"]) - signature(lossy3d_values["HAND_01"]["1"]))),
        "NEAR_size3_to_size2_relative_l2": relative_l2(lossy3d_values["NEAR_01"]["3"], lossy3d_values["NEAR_01"]["2"]),
        "NEAR_size3_to_size2_signature_distance": float(np.linalg.norm(signature(lossy3d_values["NEAR_01"]["3"]) - signature(lossy3d_values["NEAR_01"]["2"]))),
        "NEAR_size2_to_size1_relative_l2": relative_l2(lossy3d_values["NEAR_01"]["2"], lossy3d_values["NEAR_01"]["1"]),
        "NEAR_size2_to_size1_signature_distance": float(np.linalg.norm(signature(lossy3d_values["NEAR_01"]["2"]) - signature(lossy3d_values["NEAR_01"]["1"]))),
    }
    lossy3d_pair_distance = pair_distance(lossy3d_values["HAND_01"]["1"], lossy3d_values["NEAR_01"]["1"])

    lossless_distance = dense_distances["0"]
    loss_overturn = all(
        dense_distances[key] >= 0.10 and dense_distances[key] >= 5.0 * lossless_distance
        for key in ("0.005", "0.02")
    )
    base3d = dimensional["extruded_area3d_hand_near_signature_distance"]
    true3d_distance = dimensional["true_sections_3d_hand_near_signature_distance"]
    section_overturn = bool(true3d_distance >= 0.10 and true3d_distance >= 2.0 * base3d)
    final_mesh_keys = (
        "HAND_size2_to_size1_relative_l2", "HAND_size2_to_size1_signature_distance",
        "NEAR_size2_to_size1_relative_l2", "NEAR_size2_to_size1_signature_distance",
    )
    mesh_pass = bool(all(
        lossy_mesh_steps[key] <= (0.05 if "signature" in key else 0.02)
        for key in final_mesh_keys
    ))

    if not mesh_pass:
        terminal = "GEN_ENC_9_3D_MESH_SENSITIVE"
    elif loss_overturn or lossy3d_pair_distance >= 0.10:
        terminal = "GEN_ENC_9_OVERLAP_SENSITIVE_TO_LOSS_OR_TRUE_3D_SECTIONS"
    else:
        terminal = "GEN_ENC_9_HAND_NEAR_OVERLAP_PERSISTS_UNDER_BOUNDED_CONTROLS"

    result = {
        "schema_version": "gen_enc_9_loss_3d_bridge_result_v1",
        "scope": "HAND_01_NEAR_01_DEVELOPMENT_DIAGNOSTIC_ONLY",
        "terminal_state": terminal,
        "dense_2d_signature_distances": dense_distances,
        "loss_overturn_rule": "both eta distances >=0.10 and >=5x lossless distance",
        "loss_overturn": loss_overturn,
        "dimensional_controls": dimensional,
        "true_section_overturn_rule": "true-section 3D distance >=0.10 and >=2x extruded-area 3D distance",
        "true_section_overturn": section_overturn,
        "true3d_mesh_gate": {
            "lossless_steps_diagnostic_only": mesh_steps,
            "lossy_eta_0p02_steps_primary": lossy_mesh_steps,
            "thresholds": {"relative_l2_max": 0.02, "signature_distance_max": 0.05},
            "pass": mesh_pass,
        },
        "lossy_true_sections_3d_hand_near_signature_distance": lossy3d_pair_distance,
        "limitations": [
            "Uniform complex sound-speed loss factors are diagnostic sensitivities, not calibrated material measurements.",
            "True-section 3D blocks preserve M2-B segment lengths and areas but center the section heights in the M2-B plenum.",
            "Only two fixed development representatives are compared; no family or validation inference is permitted.",
        ],
    }
    (ROOT / "result_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if mesh_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
