"""Unified end plug, hose adapter and printed axial lock."""

from __future__ import annotations

import cadquery as cq

import v1_params as p
from geometry_utils import box_centered, cone, cylinder


def _end_plug_shell() -> cq.Workplane:
    base_d, tip_d = p.end_plug_diameters()
    plug = cone((0.0, 0.0, 0.0), (1, 0, 0), base_d, tip_d, p.END_SOCKET_DEPTH)
    flange = cylinder((-2.0, 0.0, 0.0), (1, 0, 0), p.END_LOCAL_COLLAR_OD, 2.0)
    ear = box_centered(2.5, 16.0, 3.0, (-1.0, 0.0, 5.6))
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
    outer = box_centered(2.8, 18.0, 15.0)
    opening = box_centered(3.8, 12.8, 11.5, (0.0, 0.0, 3.0))
    pull = box_centered(7.0, 7.0, 2.4, (2.2, 0.0, -6.0))
    return outer.cut(opening).union(pull).clean()


def all_end_parts():
    return {
        "ALV1_end_adapter_hose_barb": make_hose_barb(),
        "ALV1_end_cap_closed": make_end_cap(),
        "ALV1_end_lock_clip": make_end_lock_clip(),
    }

