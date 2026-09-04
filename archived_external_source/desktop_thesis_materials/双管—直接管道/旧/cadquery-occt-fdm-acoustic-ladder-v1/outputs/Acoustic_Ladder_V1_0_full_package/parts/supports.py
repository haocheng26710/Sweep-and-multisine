"""Three-station low-contact support, slider, retainers and L/M/H wedges."""

from __future__ import annotations

import math

import cadquery as cq

import v1_params as p
from geometry_utils import box_centered, compound


def make_support_base(joint: bool = False) -> cq.Workplane:
    width_x = p.SUPPORT_JOINT_WIDTH_X if joint else p.SUPPORT_STANDARD_WIDTH_X
    rail_a = box_centered(1.2, 36.0, 2.0, (-width_x / 2.0 + 0.8, 1.25, -8.0))
    rail_b = box_centered(1.2, 36.0, 2.0, (width_x / 2.0 - 0.8, 1.25, -8.0))
    tx_pad = box_centered(width_x, 4.0, 2.0, (0.0, p.TX_CENTER_Y, -8.0))
    rx_pad = box_centered(width_x, 5.0, 2.0, (0.0, p.RX_CENTER_Y + 1.25, -8.0))
    center_tie = box_centered(width_x, 1.6, 2.0, (0.0, 0.0, -8.0))
    # Two lower contact ribs per tube. Their small area limits solid-borne coupling.
    body = rail_a.union(rail_b).union(tx_pad).union(rx_pad).union(center_tie)
    for y in (p.TX_CENTER_Y - 1.5, p.TX_CENTER_Y + 1.5,
              p.RX_CENTER_Y + 1.25 - 1.5, p.RX_CENTER_Y + 1.25 + 1.5):
        body = body.union(box_centered(
            p.SUPPORT_CONTACT_RIB_LENGTH_X, p.SUPPORT_CONTACT_RIB_WIDTH, 2.0,
            (0.0, y, -6.4),
        ))
    stop = box_centered(width_x, 1.6, 5.0,
                        (0.0, p.RX_CENTER_Y + p.RX_TRAVEL + 5.3, -5.5))
    return body.union(stop).clean()


def make_rx_slider(joint: bool = False) -> cq.Workplane:
    width_x = 9.5 if not joint else 11.5
    body = box_centered(width_x, 10.0, 2.4, (0.0, 0.0, 0.0))
    lower_ribs = box_centered(p.SUPPORT_CONTACT_RIB_LENGTH_X, 1.0, 2.0,
                              (0.0, -2.2, 2.0)).union(
        box_centered(p.SUPPORT_CONTACT_RIB_LENGTH_X, 1.0, 2.0,
                     (0.0, 2.2, 2.0)))
    hard_stop = box_centered(width_x, 1.2, 4.0, (0.0, -5.2, 1.0))
    return body.union(lower_ribs).union(hard_stop).clean()


def make_tube_retainer(joint: bool = False) -> cq.Workplane:
    width_x = 9.0 if not joint else 11.0
    outer = box_centered(width_x, 12.0, 12.5, (0.0, 0.0, 0.5))
    inner = box_centered(width_x + 1.0,
                         p.MAIN_OUTER_WIDTH_Y + 2.0 * p.SUPPORT_TUBE_CLEARANCE,
                         p.MAIN_OUTER_HEIGHT_Z + 2.0 * p.SUPPORT_TUBE_CLEARANCE,
                         (0.0, 0.0, -0.2))
    opening = box_centered(width_x + 1.0, 7.0, 7.0, (0.0, 0.0, -6.0))
    frame = outer.cut(inner).cut(opening)
    top_rib = box_centered(p.SUPPORT_CONTACT_RIB_LENGTH_X,
                           p.SUPPORT_CONTACT_RIB_WIDTH, 1.6,
                           (0.0, 0.0, 5.4))
    return frame.union(top_rib).clean()


def make_wedge(level: str) -> cq.Workplane:
    level = level.upper()
    offset = p.SLIDER_WEDGE_PRELOAD_OFFSETS[level]
    length_y = 18.0
    base_h = 2.6 + offset
    rise = math.tan(math.radians(p.SLIDER_WEDGE_ANGLE_DEG)) * length_y
    wedge = (
        cq.Workplane("YZ", origin=(-5.0, 0.0, 0.0))
        .moveTo(-length_y / 2.0, 0.0)
        .lineTo(length_y / 2.0, 0.0)
        .lineTo(length_y / 2.0, base_h + rise)
        .lineTo(-length_y / 2.0, base_h)
        .close()
        .extrude(10.0)
    )
    pull = box_centered(14.0, 5.0, 3.2, (0.0, -11.0, base_h / 2.0))
    return wedge.union(pull).clean()


def all_support_parts():
    return {
        "ALV1_support_standard_base": make_support_base(False),
        "ALV1_support_joint_base": make_support_base(True),
        "ALV1_RX_slider_standard": make_rx_slider(False),
        "ALV1_RX_slider_joint": make_rx_slider(True),
        "ALV1_tube_retainer_standard": make_tube_retainer(False),
        "ALV1_tube_retainer_joint": make_tube_retainer(True),
        "ALV1_slider_lock_wedge_L": make_wedge("L"),
        "ALV1_slider_lock_wedge_M": make_wedge("M"),
        "ALV1_slider_lock_wedge_H": make_wedge("H"),
    }
