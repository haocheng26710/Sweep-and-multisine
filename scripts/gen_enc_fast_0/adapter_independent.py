"""Independent sealed-object verifier adapter; imports no primary/legacy code."""
from __future__ import annotations

from math import nextafter

U64 = 0xFFFFFFFFFFFFFFFF
PHI = 0x9E3779B97F4A7C15


def _mix(argument: int) -> int:
    value = (argument + PHI) & U64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & U64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & U64
    return (value ^ (value >> 31)) & U64


def _u(seed: int, coordinate: int) -> float:
    bits = _mix((seed + PHI * (coordinate + 1)) & U64)
    answer = ((bits >> 11) + 0.5) / 9007199254740992
    if answer == 1.0:
        answer = nextafter(1.0, 0.0)
    return answer


def _permutation(master: int, column: int) -> list[int]:
    result = [n for n in range(20)]
    i = 19
    while i >= 1:
        address = (master + PHI * (1 + 32 * column + 19 - i)) & U64
        pick = _mix(address) % (i + 1)
        saved = result[i]
        result[i] = result[pick]
        result[pick] = saved
        i -= 1
    return result


def consume(tables: dict, manifest: dict, seeds: dict) -> dict:
    expected = {
        "hand_designed": ("HAND", {"member_id", "volume_logit_0", "volume_logit_90", "volume_logit_180", "derived_volume_logit_270", "external_aperture_fraction_0", "external_aperture_fraction_90", "external_aperture_fraction_180", "external_aperture_fraction_270", "central_mix_aperture_fraction", "loss_fraction_0", "loss_fraction_90", "loss_fraction_180", "loss_fraction_270"}),
        "near_independent": ("NEAR", {"member_id", "volume_logit_0", "volume_logit_90", "volume_logit_180", "derived_volume_logit_270", "external_aperture_fraction_0", "external_aperture_fraction_90", "external_aperture_fraction_180", "external_aperture_fraction_270", "shared_coupling_alpha", "loss_fraction_0", "loss_fraction_90", "loss_fraction_180", "loss_fraction_270"}),
    }
    selected = {}
    for key, (prefix, fields) in expected.items():
        rows = tables[key]["rows"]
        assert tables[key]["row_count"] == 20 and len(rows) == 20
        assert all(set(row) == fields and row["member_id"] == f"{prefix}_{i:02d}" for i, row in enumerate(rows, 1))
        selected[key] = rows
    families = manifest["families"]
    assert len(families) == 4
    rand, phys = families[2], families[3]
    random_seeds = seeds["topology_identity_seeds"]["random_disordered_members"]
    assert len(random_seeds) == 20 == len(set(random_seeds))
    assert len(rand["parameter_order"]) == 13 and len(rand["parameters"]) == 3
    master = seeds["topology_identity_seeds"]["physics_lhs_master"]
    assert master == phys["lhs_master_seed"] and len(phys["parameter_order"]) == 15 and len(phys["parameters"]) == 4 and len(phys["lhs_algorithm"]) == 4
    return {"hand_rows": selected["hand_designed"], "near_rows": selected["near_independent"], "random_spec": rand, "random_seeds": random_seeds, "random_uniforms": [[_u(seed, j) for j in range(13)] for seed in random_seeds], "physics_spec": phys, "physics_master_seed": master, "physics_permutations": [_permutation(master, p) for p in range(15)]}
