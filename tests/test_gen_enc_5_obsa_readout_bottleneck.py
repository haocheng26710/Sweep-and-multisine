from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from acoustic_encoder.gen_enc.actual_fluid_star_network import compile_member_geometry, solve_clean_node_pressure_block
from acoustic_encoder.gen_enc.forward_acoustic_network import STATE_ANGLES_DEGREES, frozen_frequency_grid
from scripts.gen_enc_5_obsa_readout_bottleneck_diagnostic import selected_cells, state_signature
from scripts.gen_enc_5_obsa_independent_verifier import recompute_separation


REPO=Path(__file__).resolve().parents[1]
IDENTITY=REPO/"outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances/HAND_DESIGNED/HAND_01.identity.json"
SEEDS=(2026091001,2026091002)


def nuisance()->dict[str,float]: return {"snr_db":30.0,"common_gain_db":0.0,"sensor_independent_gain_db":0.0,"common_frequency_axis_shift_relative":0.0,"independent_manufacturing_percent":0.0,"batch_correlated_manufacturing_percent":0.0,"angle_offset_degrees":0.0}


def test_obsa_cell_selection_is_deterministic_unique_and_bounded()->None:
    assert selected_cells()==selected_cells() and len(selected_cells())==32 and len(set(selected_cells()))==32
    assert min(selected_cells())>=0 and max(selected_cells())<3675


def test_node_instrumentation_preserves_central_slice_and_signature_is_finite()->None:
    member=json.loads(IDENTITY.read_text(encoding="utf-8")); geometry=compile_member_geometry(member,spine_only=False); frequencies=frozen_frequency_grid()[:8]
    nodes=solve_clean_node_pressure_block(member,nuisance(),cell_index=0,repeat_index=0,frequencies_hz=frequencies,state_angles_degrees=STATE_ANGLES_DEGREES,partition="development",repeat_seed_tuple=SEEDS,spine_only=False,geometry_override=geometry)
    assert nodes.shape==(4,4,8,5) and np.all(np.isfinite(nodes))
    signature=state_signature(nodes[...,:4],center=False)
    assert signature.shape==(43,) and np.all(np.isfinite(signature))


def test_independent_separation_recomputation_has_six_finite_family_pairs()->None:
    rng=np.random.default_rng(20260902)
    matrix=rng.normal(size=(80,43))
    result=recompute_separation(matrix)
    assert result["usable_dimensions"]==43
    assert len(result["pairwise"])==6
    assert np.isfinite(result["minimum_between_within_ratio"])
    assert np.isfinite(result["mean_between_within_ratio"])
