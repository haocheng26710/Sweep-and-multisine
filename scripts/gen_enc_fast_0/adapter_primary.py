"""Primary direct adapter for sealed REV01 family objects (read-only)."""
from __future__ import annotations

import math

MASK = (1 << 64) - 1
GAMMA = 0x9E3779B97F4A7C15


class AuthorityShapeError(ValueError):
    pass


def _exact_keys(value: dict, keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise AuthorityShapeError(f"{label}_FIELD_SET")


def splitmix64(x: int) -> int:
    z = (x + GAMMA) & MASK
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return (z ^ (z >> 31)) & MASK


def open_uniform(seed: int, parameter_index: int) -> float:
    z = splitmix64((seed + GAMMA * (parameter_index + 1)) & MASK)
    u = ((z >> 11) + 0.5) / (1 << 53)
    return math.nextafter(1.0, 0.0) if u == 1.0 else u


def fisher_yates(master_seed: int, parameter_index: int) -> list[int]:
    permutation = list(range(20))
    for i in range(19, 0, -1):
        x = (master_seed + GAMMA * (1 + 32 * parameter_index + (19 - i))) & MASK
        j = splitmix64(x) % (i + 1)
        permutation[i], permutation[j] = permutation[j], permutation[i]
    return permutation


def _table_rows(table: dict, name: str, prefix: str, fields: set[str]) -> list[dict]:
    node = table[name]
    _exact_keys(node, {"tunable_dof", "row_count", "columns", "rows"} | ({"alpha_rule"} if name == "near_independent" else set()), name)
    rows = node["rows"]
    if node["row_count"] != 20 or len(rows) != 20:
        raise AuthorityShapeError(f"{name}_COUNT")
    for i, row in enumerate(rows, 1):
        _exact_keys(row, fields, f"{name}_{i}")
        if row["member_id"] != f"{prefix}_{i:02d}":
            raise AuthorityShapeError(f"{name}_ORDER")
    return rows


def adapt(family_tables: dict, family_manifest: dict, seed_split: dict) -> dict:
    hand_fields = {"member_id", "volume_logit_0", "volume_logit_90", "volume_logit_180", "derived_volume_logit_270", "external_aperture_fraction_0", "external_aperture_fraction_90", "external_aperture_fraction_180", "external_aperture_fraction_270", "central_mix_aperture_fraction", "loss_fraction_0", "loss_fraction_90", "loss_fraction_180", "loss_fraction_270"}
    near_fields = (hand_fields - {"central_mix_aperture_fraction"}) | {"shared_coupling_alpha"}
    hand = _table_rows(family_tables, "hand_designed", "HAND", hand_fields)
    near = _table_rows(family_tables, "near_independent", "NEAR", near_fields)
    families = family_manifest["families"]
    if len(families) != 4 or [x["family_id"] for x in families] != ["HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED"]:
        raise AuthorityShapeError("FAMILY_ORDER")
    random_spec, physics_spec = families[2], families[3]
    random_seeds = seed_split["topology_identity_seeds"]["random_disordered_members"]
    if len(random_seeds) != len(set(random_seeds)) or len(random_seeds) != 20:
        raise AuthorityShapeError("RANDOM_SEEDS")
    if random_spec["parameter_order"] != ["q0", "q90", "q180", "edge_0_90", "edge_0_180", "edge_0_270", "edge_90_180", "edge_90_270", "edge_180_270", "loss_0", "loss_90", "loss_180", "loss_270"]:
        raise AuthorityShapeError("RANDOM_PARAMETER_ORDER")
    if physics_spec["parameter_order"] != ["q0", "q90", "q180", "external_0", "external_90", "external_180", "external_270", "ring_0_90", "ring_90_180", "ring_180_270", "ring_270_0", "loss_0", "loss_90", "loss_180", "loss_270"]:
        raise AuthorityShapeError("PHYSICS_PARAMETER_ORDER")
    master = seed_split["topology_identity_seeds"]["physics_lhs_master"]
    if physics_spec["lhs_master_seed"] != master or len(physics_spec["lhs_algorithm"]) != 4:
        raise AuthorityShapeError("PHYSICS_MASTER_OR_ALGORITHM")
    random_vectors = [[open_uniform(seed, j) for j in range(13)] for seed in random_seeds]
    physics_permutations = [fisher_yates(master, p) for p in range(15)]
    return {"hand_rows": hand, "near_rows": near, "random_spec": random_spec, "random_seeds": random_seeds, "random_uniforms": random_vectors, "physics_spec": physics_spec, "physics_master_seed": master, "physics_permutations": physics_permutations}
