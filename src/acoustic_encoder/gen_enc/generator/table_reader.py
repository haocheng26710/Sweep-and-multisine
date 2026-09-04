"""Exact sealed HAND/NEAR table identity validation."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .families import TECHNICAL_LABEL

_COMMON = {
    "member_id",
    "volume_logit_0",
    "volume_logit_90",
    "volume_logit_180",
    "derived_volume_logit_270",
    "external_aperture_fraction_0",
    "external_aperture_fraction_90",
    "external_aperture_fraction_180",
    "external_aperture_fraction_270",
    "loss_fraction_0",
    "loss_fraction_90",
    "loss_fraction_180",
    "loss_fraction_270",
}
_KEYS = {
    "HAND_DESIGNED": _COMMON | {"central_mix_aperture_fraction"},
    "NEAR_INDEPENDENT": _COMMON | {"shared_coupling_alpha"},
}
_POINTERS = {
    "HAND_DESIGNED": "hand_designed",
    "NEAR_INDEPENDENT": "near_independent",
}


def _bounded(row: dict[str, Any], names: list[str], lower: float, upper: float) -> bool:
    return all(
        isinstance(row.get(name), (int, float))
        and math.isfinite(row[name])
        and lower <= row[name] <= upper
        for name in names
    )


def load_literal_family_table(sealed_table_path: str | Path, expected_sha256: str, family_pointer: str) -> dict[str, Any]:
    """Read and validate one sealed literal family table without derivation."""

    family = family_pointer.upper()
    if family not in _POINTERS:
        raise ValueError("only HAND_DESIGNED and NEAR_INDEPENDENT are permitted")
    path = Path(sealed_table_path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("sealed table SHA-256 mismatch")
    payload = json.loads(raw)
    section = payload[_POINTERS[family]]
    rows = section["rows"]
    if section.get("row_count") != 20 or len(rows) != 20:
        raise ValueError("sealed table must contain exactly 20 rows")
    prefix = "HAND" if family == "HAND_DESIGNED" else "NEAR"
    expected_ids = [f"{prefix}_{index:02d}" for index in range(1, 21)]
    member_ids = [row.get("member_id") for row in rows]
    if member_ids != expected_ids or len(set(member_ids)) != 20:
        raise ValueError("member order or uniqueness mismatch")
    for index, row in enumerate(rows, start=1):
        if set(row) != _KEYS[family]:
            raise ValueError(f"row {index} has a noncanonical key set")
        q_names = ["volume_logit_0", "volume_logit_90", "volume_logit_180"]
        if not _bounded(row, q_names, -0.12, 0.12):
            raise ValueError(f"row {index} volume-logit bounds failed")
        expected_q270 = -sum(row[name] for name in q_names) / 3.0
        if not math.isclose(row["derived_volume_logit_270"], expected_q270, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"row {index} q270 failed")
        aperture_names = [f"external_aperture_fraction_{angle}" for angle in (0, 90, 180, 270)]
        if not _bounded(row, aperture_names, 0.2, 0.8):
            raise ValueError(f"row {index} aperture bounds failed")
        loss_names = [f"loss_fraction_{angle}" for angle in (0, 90, 180, 270)]
        if not _bounded(row, loss_names, 0.02, 0.08):
            raise ValueError(f"row {index} loss bounds failed")
        if family == "HAND_DESIGNED":
            if not _bounded(row, ["central_mix_aperture_fraction"], 0.1, 0.3):
                raise ValueError(f"row {index} central aperture bounds failed")
        else:
            if not _bounded(row, ["shared_coupling_alpha"], 0.03, 0.07):
                raise ValueError(f"row {index} alpha bounds failed")
            expected_alpha = 0.03 + (index - 1) * 0.04 / 19.0
            if not math.isclose(row["shared_coupling_alpha"], expected_alpha, rel_tol=0.0, abs_tol=5e-13):
                raise ValueError(f"row {index} alpha rule failed")
    if section.get("tunable_dof") != 12:
        raise ValueError("frozen DOF must equal 12")
    return {
        "object_class": TECHNICAL_LABEL,
        "validation_only": True,
        "family_id": family,
        "row_count": 20,
        "member_ids": member_ids,
        "rows": rows,
        "tunable_dof": 12,
        "derived_cad_or_topology_payload": None,
    }
