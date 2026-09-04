"""Unified end plug, hose adapter and printed axial lock."""

from __future__ import annotations

import cadquery as cq

import v1_params as p
from geometry_utils import box_centered, cone, cylinder
from parts.joints import make_snap_bridge_lock


def _end_plug_shell() -> cq.Workplane:
    base_d, tip_d = p.end_plug_diameters()
    plug = cone((0.0, 0.0, 0.0), (1, 0, 0), base_d, tip_d, p.END_SOCKET_DEPTH)
    flange = cylinder((-2.0, 0.0, 0.0), (1, 0, 0), p.END_LOCAL_COLLAR_OD, 2.0)
    # Keep a real axial gap to the tube ear.  The earlier 2.5 mm ear crossed
    # x=0 and created a non-seal collision before the lock was even installed.
    ear = box_centered(
        p.END_LOCK_EAR_SIZE_X,
        p.END_LOCK_EAR_SPAN_Y,
        p.END_LOCK_EAR_HEIGHT_Z,
        (p.END_PART_EAR_CENTER_X, 0.0, p.END_LOCK_EAR_CENTER_Z),
    )
    return plug.union(flange).union(ear)


def make_hose_barb() -> cq.Workplane:
    body = _end_plug_shell()
    x0 = -2.0 - p.BARB_LENGTH
    shaft = cylinder((x0, 0.0, 0.0), (1, 0, 0), p.BARB_ROOT_OD, p.BARB_LENGTH)
    body = body.union(shaft)
    for offset in (1.0, 4.0, 7.0):
        tooth = cone((x0 + offset, 0.0, 0.0), (1, 0, 0),
                     p.BARB_MAX_OD, p.BARB_ROOT_OD, 2.2)
        body = body.union(tooth)
    bore = cylinder((x0 - 0.2, 0.0, 0.0), (1, 0, 0),
                    p.BARB_INTERNAL_BORE + p.FDM_ACOUSTIC_HOLE_COMPENSATION,
                    p.BARB_LENGTH + p.END_SOCKET_DEPTH + 2.4)
    return body.cut(bore).clean()


def make_end_cap() -> cq.Workplane:
    body = _end_plug_shell()
    nose = cylinder((p.END_SOCKET_DEPTH, 0.0, 0.0), (1, 0, 0),
                    p.BLOCK_FILL_PIN_TARGET_DIAMETER, 0.45)
    handle = cylinder((-5.0, 0.0, 0.0), (1, 0, 0), 9.0, 3.0)
    return body.union(nose).union(handle).clean()


def make_end_lock_clip() -> cq.Workplane:
    part_min = p.END_PART_EAR_CENTER_X - p.END_LOCK_EAR_SIZE_X / 2.0
    tube_max = p.END_LOCK_EAR_SIZE_X
    ear_bottom = p.END_LOCK_EAR_CENTER_Z - p.END_LOCK_EAR_HEIGHT_Z / 2.0
    ear_top = p.END_LOCK_EAR_CENTER_Z + p.END_LOCK_EAR_HEIGHT_Z / 2.0
    return make_snap_bridge_lock(
        part_min,
        tube_max,
        p.END_LOCK_EAR_SPAN_Y,
        ear_bottom,
        ear_top,
        p.END_LOCAL_COLLAR_OD / 2.0,
    )


def all_end_parts():
    return {
        "ALV1_end_adapter_hose_barb": make_hose_barb(),
        "ALV1_end_cap_closed": make_end_cap(),
        "ALV1_end_lock_clip": make_end_lock_clip(),
    }
