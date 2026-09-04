"""Unified bridge, block and development modules."""

from __future__ import annotations

import math

import cadquery as cq

import v1_params as p
from geometry_utils import box_centered, cone, cylinder, emboss_text, rounded_box


def _module_body() -> cq.Workplane:
    return rounded_box(
        p.MODULE_WIDTH_X,
        p.MODULE_RIGID_SHOULDER_SPAN_Y,
        p.MODULE_HEIGHT_Z,
        p.MODULE_CORNER_RADIUS,
    )


def _add_pilots(body: cq.Workplane, interference: float):
    base_d, tip_d = p.module_pilot_diameters(interference)
    y_face = p.MODULE_RIGID_SHOULDER_SPAN_Y / 2.0
    right = cone((0.0, y_face, 0.0), (0, 1, 0), base_d, tip_d,
                 p.MODULE_DRY_SEAL_PILOT_LENGTH)
    left = cone((0.0, -y_face, 0.0), (0, -1, 0), base_d, tip_d,
                p.MODULE_DRY_SEAL_PILOT_LENGTH)
    return body.union(right).union(left), base_d, tip_d


def make_bridge(target_diameter: float, label: str) -> cq.Workplane:
    body, _, _ = _add_pilots(_module_body(), p.MODULE_DRY_SEAL_DIAMETRAL_INTERFERENCE)
    total_length = (p.MODULE_RIGID_SHOULDER_SPAN_Y +
                    2.0 * p.MODULE_DRY_SEAL_PILOT_LENGTH + 0.8)
    y0 = -total_length / 2.0
    bore = cylinder(
        (0.0, y0, 0.0), (0, 1, 0),
        target_diameter + p.FDM_ACOUSTIC_HOLE_COMPENSATION,
        total_length,
    )
    body = body.cut(bore).clean()
    return emboss_text(
        body, label, (0.0, 0.0, p.MODULE_HEIGHT_Z / 2.0),
        p.MODULE_LABEL_TEXT_HEIGHT, p.MODULE_LABEL_HEIGHT,
    ).clean()


def make_block() -> cq.Workplane:
    body, _, tip_d = _add_pilots(_module_body(), p.MODULE_DRY_SEAL_DIAMETRAL_INTERFERENCE)
    y_tip = (p.MODULE_RIGID_SHOULDER_SPAN_Y / 2.0 +
             p.MODULE_DRY_SEAL_PILOT_LENGTH)
    extra = max(0.1, p.BLOCK_FILL_PIN_TOTAL_PROJECTION_FROM_SHOULDER -
                p.MODULE_DRY_SEAL_PILOT_LENGTH)
    pin_base_d = p.BLOCK_FILL_PIN_TARGET_DIAMETER
    pin_tip_d = pin_base_d - 2.0 * extra * math.tan(math.radians(p.BLOCK_FILL_PIN_TAPER_DEG))
    pin_tip_d = max(pin_tip_d, pin_base_d - 0.25)
    body = body.union(cone((0, y_tip, 0), (0, 1, 0), pin_base_d, pin_tip_d, extra))
    body = body.union(cone((0, -y_tip, 0), (0, -1, 0), pin_base_d, pin_tip_d, extra))
    return emboss_text(
        body, "BLK", (0.0, 0.0, p.MODULE_HEIGHT_Z / 2.0),
        p.MODULE_LABEL_TEXT_HEIGHT, p.MODULE_LABEL_HEIGHT,
    ).clean()


def make_development_blank() -> cq.Workplane:
    body, _, _ = _add_pilots(_module_body(), p.MODULE_DRY_SEAL_DIAMETRAL_INTERFERENCE)
    development_zone = rounded_box(11.0, 6.0, 5.0, 0.8, (0.0, 0.0, 8.5))
    body = body.union(development_zone)
    return emboss_text(body, "DEV", (0.0, 0.0, 11.0), 2.7,
                       p.MODULE_LABEL_HEIGHT).clean()


def all_modules():
    return {
        "ALV1_module_block": make_block(),
        "ALV1_module_bridge_D4p0": make_bridge(4.0, "B40"),
        "ALV1_module_bridge_D3p2": make_bridge(3.2, "B32"),
        "ALV1_module_bridge_D2p8": make_bridge(2.8, "B28"),
        "ALV1_module_development_blank": make_development_blank(),
    }

