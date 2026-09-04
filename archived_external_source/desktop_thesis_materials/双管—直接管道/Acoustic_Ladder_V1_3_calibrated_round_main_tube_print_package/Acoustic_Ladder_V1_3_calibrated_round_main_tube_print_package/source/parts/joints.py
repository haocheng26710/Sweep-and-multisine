"""Printed, removable axial lock for each split-tube dry-seal joint."""

from __future__ import annotations

import cadquery as cq

import v1_params as p
from geometry_utils import box_centered


def make_snap_bridge_lock(
    ear_x_min: float,
    ear_x_max: float,
    ear_span_y: float,
    ear_bottom_z: float,
    ear_top_z: float,
    obstruction_top_z: float,
) -> cq.Workplane:
    """Create a printable cap that snaps over two ears without touching tubes.

    Axial walls sit outside the two ear end faces.  Thin side skirts and shallow
    under-lips retain the cap vertically, while the top bridge carries the axial
    load in the XY print layers.
    """
    x_left_inner = ear_x_min - p.LOCK_RUNNING_CLEARANCE
    x_right_inner = ear_x_max + p.LOCK_RUNNING_CLEARANCE
    x_min = x_left_inner - p.LOCK_AXIAL_WALL_THICKNESS
    x_max = x_right_inner + p.LOCK_AXIAL_WALL_THICKNESS
    length_x = x_max - x_min

    y_inner = ear_span_y / 2.0 + p.LOCK_RUNNING_CLEARANCE
    y_outer = y_inner + p.LOCK_SIDE_WALL
    top_bottom = ear_top_z + p.LOCK_TOP_CLEARANCE
    top = box_centered(
        length_x,
        2.0 * y_outer,
        p.LOCK_TOP_THICKNESS,
        ((x_min + x_max) / 2.0, 0.0,
         top_bottom + p.LOCK_TOP_THICKNESS / 2.0),
    )

    lip_top = ear_bottom_z - p.LOCK_RUNNING_CLEARANCE
    lip_bottom = lip_top - p.LOCK_SIDE_LIP_HEIGHT
    side_height = top_bottom - lip_bottom + 0.10
    side_center_z = lip_bottom + side_height / 2.0
    side_a = box_centered(
        length_x,
        p.LOCK_SIDE_WALL,
        side_height,
        ((x_min + x_max) / 2.0,
         y_inner + p.LOCK_SIDE_WALL / 2.0,
         side_center_z),
    )
    side_b = side_a.mirror("XZ")

    lip_width = p.LOCK_SIDE_WALL + p.LOCK_SIDE_LIP_UNDERCUT
    lip_a = box_centered(
        length_x,
        lip_width,
        p.LOCK_SIDE_LIP_HEIGHT,
        ((x_min + x_max) / 2.0,
         y_outer - lip_width / 2.0,
         (lip_bottom + lip_top) / 2.0),
    )
    lip_b = lip_a.mirror("XZ")

    wall_bottom = max(
        obstruction_top_z + 0.10,
        ear_top_z - p.LOCK_AXIAL_WALL_HEIGHT,
    )
    wall_height = top_bottom - wall_bottom + 0.10
    wall_z = wall_bottom + wall_height / 2.0
    wall_y = 2.0 * y_inner
    left_wall = box_centered(
        p.LOCK_AXIAL_WALL_THICKNESS,
        wall_y,
        wall_height,
        (x_min + p.LOCK_AXIAL_WALL_THICKNESS / 2.0, 0.0, wall_z),
    )
    right_wall = box_centered(
        p.LOCK_AXIAL_WALL_THICKNESS,
        wall_y,
        wall_height,
        (x_max - p.LOCK_AXIAL_WALL_THICKNESS / 2.0, 0.0, wall_z),
    )
    return (
        top.union(side_a).union(side_b)
        .union(lip_a).union(lip_b)
        .union(left_wall).union(right_wall)
        .clean()
    )


def make_joint_lock_clip() -> cq.Workplane:
    front_min = -2.0 - p.JOINT_LOCK_EAR_SIZE_X / 2.0
    rear_center = p.JOINT_LOCAL_COLLAR_LENGTH - 1.5
    rear_max = rear_center + p.JOINT_LOCK_EAR_SIZE_X / 2.0
    ear_bottom = p.JOINT_LOCK_EAR_CENTER_Z - p.JOINT_LOCK_EAR_HEIGHT_Z / 2.0
    ear_top = p.JOINT_LOCK_EAR_CENTER_Z + p.JOINT_LOCK_EAR_HEIGHT_Z / 2.0
    return make_snap_bridge_lock(
        front_min,
        rear_max,
        p.JOINT_LOCK_EAR_SPAN_Y,
        ear_bottom,
        ear_top,
        p.JOINT_LOCAL_COLLAR_OD / 2.0,
    )


def all_joint_parts():
    return {"ALV1_joint_lock_clip": make_joint_lock_clip()}
