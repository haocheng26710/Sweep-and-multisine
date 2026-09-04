"""Three-station low-contact support, slider, retainers and L/M/H wedges."""

from __future__ import annotations

import math

import cadquery as cq

import v1_params as p
from geometry_utils import box_centered


def make_support_base(joint: bool = False) -> cq.Workplane:
    width_x = p.SUPPORT_JOINT_WIDTH_X if joint else p.SUPPORT_STANDARD_WIDTH_X
    slider_width = (
        p.SUPPORT_SLIDER_JOINT_WIDTH_X
        if joint else p.SUPPORT_SLIDER_STANDARD_WIDTH_X
    )
    slider_length = (
        p.SUPPORT_SLIDER_JOINT_LENGTH_Y
        if joint else p.SUPPORT_SLIDER_LENGTH_Y
    )
    retainer_outer_y = (
        p.SUPPORT_JOINT_RETAINER_OUTER_WIDTH_Y
        if joint else p.SUPPORT_RETAINER_OUTER_WIDTH_Y
    )
    closed_stop_y = (
        p.SUPPORT_JOINT_CLOSED_STOP_FACE_Y
        if joint else p.SUPPORT_CLOSED_STOP_FACE_Y
    )
    open_stop_y = (
        p.SUPPORT_JOINT_OPEN_STOP_FACE_Y
        if joint else p.SUPPORT_OPEN_STOP_FACE_Y
    )
    contact_z = (
        -math.sqrt(
            (p.JOINT_LOCAL_COLLAR_OD / 2.0) ** 2
            - (p.SUPPORT_LOWER_RIB_OFFSET_Y
               - p.SUPPORT_CONTACT_RIB_WIDTH / 2.0) ** 2
        )
        if joint else p.SUPPORT_TUBE_BOTTOM_Z
    )

    rail_y_min = p.TX_CENTER_Y - retainer_outer_y / 2.0
    rail_y_max = open_stop_y + p.SUPPORT_STOP_THICKNESS_Y
    rail_length = rail_y_max - rail_y_min
    rail_center_y = (rail_y_min + rail_y_max) / 2.0
    rail_center_x = (
        slider_width / 2.0 + p.SUPPORT_GUIDE_CLEARANCE_PER_SIDE
        - p.SUPPORT_RAIL_WIDTH_X / 2.0
    )
    rail_center_z = p.SUPPORT_RAIL_TOP_Z - p.SUPPORT_RAIL_HEIGHT_Z / 2.0
    rail_a = box_centered(
        p.SUPPORT_RAIL_WIDTH_X, rail_length, p.SUPPORT_RAIL_HEIGHT_Z,
        (-rail_center_x, rail_center_y, rail_center_z),
    )
    rail_b = box_centered(
        p.SUPPORT_RAIL_WIDTH_X, rail_length, p.SUPPORT_RAIL_HEIGHT_Z,
        (rail_center_x, rail_center_y, rail_center_z),
    )
    body = rail_a.union(rail_b)

    # Fixed TX cradle: two narrow lower ribs, with separate small landing pads
    # for the retainer feet.  There is no continuous plate between the tubes.
    rib_bottom = p.SUPPORT_RAIL_TOP_Z - 0.10
    rib_height = contact_z - rib_bottom
    for y in (
        p.TX_CENTER_Y - p.SUPPORT_LOWER_RIB_OFFSET_Y,
        p.TX_CENTER_Y + p.SUPPORT_LOWER_RIB_OFFSET_Y,
    ):
        body = body.union(box_centered(
            p.SUPPORT_CONTACT_RIB_LENGTH_X,
            p.SUPPORT_CONTACT_RIB_WIDTH,
            rib_height,
            (0.0, y, rib_bottom + rib_height / 2.0),
        ))
        if joint:
            # The wider joint rails sit outside the 6 mm acoustic contact rib.
            # A low, narrow tie joins them below the tube without increasing
            # the actual tube-contact area.
            body = body.union(box_centered(
                width_x - 1.0,
                0.60,
                1.0,
                (0.0, y, p.SUPPORT_RAIL_TOP_Z - 0.40),
            ))
    foot_offset_y = retainer_outer_y / 2.0 - 0.5
    for y in (p.TX_CENTER_Y - foot_offset_y, p.TX_CENTER_Y + foot_offset_y):
        pad_height = -7.0 - rib_bottom
        body = body.union(box_centered(
            width_x - 1.0, 1.0, pad_height,
            (0.0, y, rib_bottom + pad_height / 2.0),
        ))

    # L-shaped guide walls constrain X while the two thin rails carry Z load.
    guide_inner_x = slider_width / 2.0 + p.SUPPORT_GUIDE_CLEARANCE_PER_SIDE
    guide_center_x = guide_inner_x + p.SUPPORT_GUIDE_WALL_THICKNESS / 2.0
    guide_length_y = open_stop_y - closed_stop_y
    guide_center_y = (open_stop_y + closed_stop_y) / 2.0
    guide_bottom = p.SUPPORT_RAIL_TOP_Z - 0.10
    guide_height = p.SUPPORT_GUIDE_WALL_TOP_Z - guide_bottom
    for x in (-guide_center_x, guide_center_x):
        body = body.union(box_centered(
            p.SUPPORT_GUIDE_WALL_THICKNESS,
            guide_length_y,
            guide_height,
            (x, guide_center_y, guide_bottom + guide_height / 2.0),
        ))

    # These two faces, not the wedge insertion depth, define 20.0 and 22.5 mm.
    stop_height = p.SUPPORT_STOP_TOP_Z - p.SUPPORT_STOP_BOTTOM_Z
    closed_stop = box_centered(
         width_x,
         p.SUPPORT_STOP_THICKNESS_Y,
         stop_height,
         (0.0,
         closed_stop_y - p.SUPPORT_STOP_THICKNESS_Y / 2.0,
         p.SUPPORT_STOP_BOTTOM_Z + stop_height / 2.0),
    )
    open_stop = box_centered(
        width_x,
         p.SUPPORT_STOP_THICKNESS_Y,
         stop_height,
         (0.0,
         open_stop_y + p.SUPPORT_STOP_THICKNESS_Y / 2.0,
         p.SUPPORT_STOP_BOTTOM_Z + stop_height / 2.0),
    )
    return body.union(closed_stop).union(open_stop).clean()


def make_rx_slider(joint: bool = False) -> cq.Workplane:
    width_x = (
        p.SUPPORT_SLIDER_JOINT_WIDTH_X
        if joint else p.SUPPORT_SLIDER_STANDARD_WIDTH_X
    )
    length_y = (
        p.SUPPORT_SLIDER_JOINT_LENGTH_Y
        if joint else p.SUPPORT_SLIDER_LENGTH_Y
    )
    body = box_centered(
        width_x,
        length_y,
        p.SUPPORT_SLIDER_BODY_HEIGHT_Z,
    )
    target_contact_z = (
        -math.sqrt(
            (p.JOINT_LOCAL_COLLAR_OD / 2.0) ** 2
            - (p.SUPPORT_LOWER_RIB_OFFSET_Y
               - p.SUPPORT_CONTACT_RIB_WIDTH / 2.0) ** 2
        )
        if joint else p.SUPPORT_TUBE_BOTTOM_Z
    )
    target_local_z = target_contact_z - p.SUPPORT_SLIDER_ASSEMBLY_Z
    rib_height = target_local_z - p.SUPPORT_SLIDER_BODY_HEIGHT_Z / 2.0 + 0.10
    rib_center_z = p.SUPPORT_SLIDER_BODY_HEIGHT_Z / 2.0 + rib_height / 2.0 - 0.10
    ribs = box_centered(
        p.SUPPORT_CONTACT_RIB_LENGTH_X,
        p.SUPPORT_CONTACT_RIB_WIDTH,
        rib_height,
        (0.0, -p.SUPPORT_LOWER_RIB_OFFSET_Y, rib_center_z),
    ).union(box_centered(
        p.SUPPORT_CONTACT_RIB_LENGTH_X,
        p.SUPPORT_CONTACT_RIB_WIDTH,
        rib_height,
        (0.0, p.SUPPORT_LOWER_RIB_OFFSET_Y, rib_center_z),
    ))
    return body.union(ribs).clean()


def make_tube_retainer(joint: bool = False) -> cq.Workplane:
    width_x = 9.0 if not joint else p.SUPPORT_JOINT_RETAINER_WIDTH_X
    if joint:
        outer_height = (
            p.SUPPORT_JOINT_RETAINER_TOP_Z
            - p.SUPPORT_JOINT_RETAINER_BOTTOM_Z
        )
        outer = box_centered(
            width_x,
            p.SUPPORT_JOINT_RETAINER_OUTER_WIDTH_Y,
            outer_height,
            (0.0, 0.0,
             (p.SUPPORT_JOINT_RETAINER_TOP_Z
              + p.SUPPORT_JOINT_RETAINER_BOTTOM_Z) / 2.0),
        )
        inner_bottom = p.SUPPORT_JOINT_RETAINER_BOTTOM_Z - 0.2
        inner_top = p.JOINT_LOCAL_COLLAR_OD / 2.0 + p.SUPPORT_TUBE_CLEARANCE
        inner = box_centered(
            width_x + 1.0,
            p.SUPPORT_JOINT_RETAINER_INNER_WIDTH_Y,
            inner_top - inner_bottom,
            (0.0, 0.0, (inner_top + inner_bottom) / 2.0),
        )
        frame = outer.cut(inner)
        joint_rib_height = (
            p.SUPPORT_JOINT_RETAINER_TOP_Z - p.JOINT_LOCAL_COLLAR_OD / 2.0
        )
        top_rib = box_centered(
            p.SUPPORT_CONTACT_RIB_LENGTH_X,
            p.SUPPORT_CONTACT_RIB_WIDTH,
            joint_rib_height,
            (0.0, 0.0,
             p.JOINT_LOCAL_COLLAR_OD / 2.0 + joint_rib_height / 2.0),
        )
        return frame.union(top_rib).clean()

    outer = box_centered(
        width_x,
        p.SUPPORT_RETAINER_OUTER_WIDTH_Y,
        p.SUPPORT_RETAINER_OUTER_HEIGHT_Z,
    )
    inner = box_centered(width_x + 1.0,
                         p.MAIN_OUTER_WIDTH_Y + 2.0 * p.SUPPORT_TUBE_CLEARANCE,
                         p.MAIN_OUTER_HEIGHT_Z + 2.0 * p.SUPPORT_TUBE_CLEARANCE,
                         (0.0, 0.0, 0.0))
    opening = box_centered(width_x + 1.0, 7.0, 3.0, (0.0, 0.0, -5.5))
    frame = outer.cut(inner).cut(opening)
    top_rib = box_centered(p.SUPPORT_CONTACT_RIB_LENGTH_X,
                           p.SUPPORT_CONTACT_RIB_WIDTH,
                           p.SUPPORT_RETAINER_TOP_RIB_HEIGHT_Z,
                           (0.0, 0.0,
                            p.MAIN_OUTER_HEIGHT_Z / 2.0
                            + p.SUPPORT_RETAINER_TOP_RIB_HEIGHT_Z / 2.0))
    feet = box_centered(
        width_x,
        1.0,
        p.SUPPORT_RETAINER_FOOT_HEIGHT_Z,
        (0.0, -5.5,
         -p.SUPPORT_RETAINER_OUTER_HEIGHT_Z / 2.0
         - p.SUPPORT_RETAINER_FOOT_HEIGHT_Z / 2.0),
    ).union(box_centered(
        width_x,
        1.0,
        p.SUPPORT_RETAINER_FOOT_HEIGHT_Z,
        (0.0, 5.5,
         -p.SUPPORT_RETAINER_OUTER_HEIGHT_Z / 2.0
         - p.SUPPORT_RETAINER_FOOT_HEIGHT_Z / 2.0),
    ))
    return frame.union(top_rib).union(feet).clean()


def make_wedge(level: str) -> cq.Workplane:
    level = level.upper()
    offset = p.SLIDER_WEDGE_PRELOAD_OFFSETS[level]
    bottom_t = p.SLIDER_WEDGE_BOTTOM_THICKNESS_Y + offset
    rise = (
        math.tan(math.radians(p.SLIDER_WEDGE_ANGLE_DEG))
        * p.SLIDER_WEDGE_LENGTH_Z
    )
    top_t = bottom_t + rise
    wedge = (
        cq.Workplane("YZ", origin=(-p.SLIDER_WEDGE_WIDTH_X / 2.0, 0.0, 0.0))
        .moveTo(-bottom_t / 2.0, 0.0)
        .lineTo(bottom_t / 2.0, 0.0)
        .lineTo(top_t / 2.0, p.SLIDER_WEDGE_LENGTH_Z)
        .lineTo(-top_t / 2.0, p.SLIDER_WEDGE_LENGTH_Z)
        .close()
        .extrude(p.SLIDER_WEDGE_WIDTH_X)
    )
    pull = box_centered(
        p.SLIDER_WEDGE_WIDTH_X + 4.0,
        top_t + 3.0,
        1.5,
        (0.0, 0.0, p.SLIDER_WEDGE_LENGTH_Z + 0.75),
    )
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
