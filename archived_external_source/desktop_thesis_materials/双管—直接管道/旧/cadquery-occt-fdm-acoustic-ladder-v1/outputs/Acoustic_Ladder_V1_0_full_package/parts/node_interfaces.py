"""Analytic node-interface dimensions shared by tubes, modules and reports."""

from __future__ import annotations

import math

import v1_params as p


def node_interface_dimensions():
    return {
        "boss_outer_diameter": p.NODE_BOSS_OD,
        "boss_protrusion": p.NODE_BOSS_PROTRUSION,
        "socket_depth": p.NODE_DRY_SEAL_SOCKET_DEPTH,
        "socket_entry_target_diameter": p.NODE_DRY_SEAL_SOCKET_ENTRY_TARGET_DIAMETER,
        "socket_bottom_target_diameter": p.NODE_DRY_SEAL_SOCKET_BOTTOM_TARGET_DIAMETER,
        "socket_half_angle_deg": math.degrees(math.atan(
            (p.NODE_DRY_SEAL_SOCKET_ENTRY_TARGET_DIAMETER -
             p.NODE_DRY_SEAL_SOCKET_BOTTOM_TARGET_DIAMETER) /
            (2.0 * p.NODE_DRY_SEAL_SOCKET_DEPTH)
        )),
        "throat_target_diameter": p.NODE_THROAT_TARGET_DIAMETER,
        "throat_cad_diameter": (
            p.NODE_THROAT_TARGET_DIAMETER + p.FDM_ACOUSTIC_HOLE_COMPENSATION
        ),
        "face_gap": p.NODE_SEAT_FACE_GAP,
    }

