"""Four reusable main-tube segment generators in global assembly coordinates."""

from __future__ import annotations

import cadquery as cq

import v1_params as p
from geometry_utils import box_centered, cone, cylinder, rounded_rect_prism_x, teardrop_prism_x


def _add_end_socket(body: cq.Workplane, x_face: float, direction: int,
                    y_center: float) -> cq.Workplane:
    if direction > 0:
        collar_x = x_face
        cone_origin = (x_face, y_center, 0.0)
        axis = (1, 0, 0)
    else:
        collar_x = x_face - p.END_LOCAL_COLLAR_LENGTH
        cone_origin = (x_face, y_center, 0.0)
        axis = (-1, 0, 0)
    collar = cylinder(
        (collar_x, y_center, 0.0), (1, 0, 0),
        p.END_LOCAL_COLLAR_OD, p.END_LOCAL_COLLAR_LENGTH,
    )
    body = body.union(collar)
    socket = cone(
        cone_origin, axis,
        p.END_SOCKET_ENTRY_TARGET_DIAMETER + p.FDM_DRY_SEAL_SOCKET_COMPENSATION,
        p.END_SOCKET_BOTTOM_TARGET_DIAMETER + p.FDM_DRY_SEAL_SOCKET_COMPENSATION,
        p.END_SOCKET_DEPTH,
    )
    body = body.cut(socket)
    ear_x = x_face + direction * p.END_LOCK_EAR_SIZE_X / 2.0
    ear = box_centered(
        p.END_LOCK_EAR_SIZE_X,
        p.END_LOCK_EAR_SPAN_Y,
        p.END_LOCK_EAR_HEIGHT_Z,
        (ear_x, y_center, p.END_LOCK_EAR_CENTER_Z),
    )
    return body.union(ear)


def _add_split_male(body: cq.Workplane, x_face: float,
                    y_center: float) -> cq.Workplane:
    base_d, tip_d = p.joint_male_diameters()
    male = cone((x_face, y_center, 0.0), (1, 0, 0), base_d, tip_d,
                p.JOINT_MALE_LENGTH)
    key = box_centered(
        p.JOINT_MALE_LENGTH - 1.0,
        p.JOINT_KEY_WIDTH,
        p.JOINT_KEY_HEIGHT,
        (x_face + (p.JOINT_MALE_LENGTH - 1.0) / 2.0,
         y_center,
         max(base_d, tip_d) / 2.0 + p.JOINT_KEY_HEIGHT / 2.0 - 0.15),
    )
    shoulder = cylinder(
        (x_face - p.JOINT_LOCAL_COLLAR_LENGTH, y_center, 0.0),
        (1, 0, 0), p.JOINT_LOCAL_COLLAR_OD, p.JOINT_LOCAL_COLLAR_LENGTH,
    )
    ear = box_centered(
        p.JOINT_LOCK_EAR_SIZE_X,
        p.JOINT_LOCK_EAR_SPAN_Y,
        p.JOINT_LOCK_EAR_HEIGHT_Z,
        (x_face - 2.0, y_center, p.JOINT_LOCK_EAR_CENTER_Z),
    )
    return body.union(shoulder).union(male).union(key).union(ear)


def _add_split_socket(body: cq.Workplane, x_face: float,
                      y_center: float) -> cq.Workplane:
    collar = cylinder(
        (x_face, y_center, 0.0), (1, 0, 0),
        p.JOINT_LOCAL_COLLAR_OD, p.JOINT_LOCAL_COLLAR_LENGTH,
    )
    body = body.union(collar)
    socket = cone(
        (x_face, y_center, 0.0), (1, 0, 0),
        p.JOINT_SOCKET_ENTRY_TARGET_DIAMETER + p.FDM_DRY_SEAL_SOCKET_COMPENSATION,
        p.JOINT_SOCKET_BOTTOM_TARGET_DIAMETER + p.FDM_DRY_SEAL_SOCKET_COMPENSATION,
        p.JOINT_SOCKET_DEPTH,
    )
    key_slot = box_centered(
        p.JOINT_SOCKET_DEPTH + 0.4,
        p.JOINT_KEY_WIDTH + p.JOINT_KEY_CLEARANCE,
        p.JOINT_KEY_HEIGHT + p.JOINT_KEY_CLEARANCE,
        (x_face + p.JOINT_SOCKET_DEPTH / 2.0,
         y_center,
         p.JOINT_SOCKET_ENTRY_TARGET_DIAMETER / 2.0 + p.JOINT_KEY_HEIGHT / 2.0 - 0.10),
    )
    ear = box_centered(
        p.JOINT_LOCK_EAR_SIZE_X,
        p.JOINT_LOCK_EAR_SPAN_Y,
        p.JOINT_LOCK_EAR_HEIGHT_Z,
        (x_face + p.JOINT_LOCAL_COLLAR_LENGTH - 1.5,
         y_center, p.JOINT_LOCK_EAR_CENTER_Z),
    )
    return body.cut(socket).cut(key_slot).union(ear)


def _add_node(body: cq.Workplane, x: float, y_center: float,
              inward_sign: int) -> cq.Workplane:
    half_width = p.MAIN_OUTER_WIDTH_Y / 2.0
    boss_face_y = y_center + inward_sign * (half_width + p.NODE_BOSS_PROTRUSION)
    boss = cylinder(
        (x, y_center, 0.0), (0, inward_sign, 0), p.NODE_BOSS_OD,
        half_width + p.NODE_BOSS_PROTRUSION,
    )
    body = body.union(boss)
    socket_axis = (0, -inward_sign, 0)
    socket = cone(
        (x, boss_face_y, 0.0), socket_axis,
        p.NODE_DRY_SEAL_SOCKET_ENTRY_TARGET_DIAMETER + p.FDM_DRY_SEAL_SOCKET_COMPENSATION,
        p.NODE_DRY_SEAL_SOCKET_BOTTOM_TARGET_DIAMETER + p.FDM_DRY_SEAL_SOCKET_COMPENSATION,
        p.NODE_DRY_SEAL_SOCKET_DEPTH,
    )
    throat_start_y = boss_face_y - inward_sign * p.NODE_DRY_SEAL_SOCKET_DEPTH
    throat = cylinder(
        (x, throat_start_y, 0.0), socket_axis,
        p.NODE_THROAT_TARGET_DIAMETER + p.FDM_ACOUSTIC_HOLE_COMPENSATION,
        p.NODE_THROAT_LENGTH_APPROX + 0.8,
    )
    return body.cut(socket).cut(throat)


def make_tube_segment(role: str, section: str) -> cq.Workplane:
    role = role.upper()
    section = section.lower()
    if role not in {"TX", "RX"} or section not in {"front", "rear"}:
        raise ValueError("role must be TX/RX and section front/rear")

    y_center = p.TX_CENTER_Y if role == "TX" else p.RX_CENTER_Y
    inward_sign = 1 if role == "TX" else -1
    x0 = 0.0 if section == "front" else p.SPLIT_X
    x1 = p.SPLIT_X if section == "front" else p.MAIN_TOTAL_ACOUSTIC_LENGTH

    body = rounded_rect_prism_x(
        x0, x1 - x0, p.MAIN_OUTER_WIDTH_Y, p.MAIN_OUTER_HEIGHT_Z,
        p.MAIN_OUTER_CORNER_RADIUS, y_center, 0.0,
    )
    if section == "front":
        body = _add_end_socket(body, x0, 1, y_center)
        body = _add_split_male(body, x1, y_center)
        lumen_end = x1 + p.JOINT_MALE_LENGTH + 0.2
        node_positions = [x for x in p.NODE_X_GLOBAL if x < p.SPLIT_X]
    else:
        body = _add_split_socket(body, x0, y_center)
        body = _add_end_socket(body, x1, -1, y_center)
        lumen_end = x1 + 0.2
        node_positions = [x for x in p.NODE_X_GLOBAL if x > p.SPLIT_X]

    for x in node_positions:
        body = _add_node(body, x, y_center, inward_sign)

    # Exact teardrop BREP cut; extended slightly through every mating boundary.
    lumen = teardrop_prism_x(
        x0 - 0.2, lumen_end - x0 + 0.4,
        p.MAIN_INNER_RADIUS, p.MAIN_ROOF_HEIGHT, y_center, 0.0,
    )
    return body.cut(lumen).clean()


def all_main_tubes():
    return {
        "ALV1_TX_front_0_200": make_tube_segment("TX", "front"),
        "ALV1_TX_rear_200_400": make_tube_segment("TX", "rear"),
        "ALV1_RX_front_0_200": make_tube_segment("RX", "front"),
        "ALV1_RX_rear_200_400": make_tube_segment("RX", "rear"),
    }
