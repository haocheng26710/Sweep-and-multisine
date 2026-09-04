"""Printed, removable axial lock for each split-tube dry-seal joint."""

from __future__ import annotations

import cadquery as cq

from geometry_utils import box_centered


def make_joint_lock_clip() -> cq.Workplane:
    outer = box_centered(3.0, 19.0, 16.0)
    opening = box_centered(4.0, 13.2, 12.0, (0.0, 0.0, 3.0))
    clip = outer.cut(opening)
    pull_tab = box_centered(8.0, 8.0, 2.5, (2.5, 0.0, -6.5))
    shallow_wedge = box_centered(3.0, 1.2, 5.0, (0.0, 6.9, -1.0))
    return clip.union(pull_tab).union(shallow_wedge).clean()


def all_joint_parts():
    return {"ALV1_joint_lock_clip": make_joint_lock_clip()}

