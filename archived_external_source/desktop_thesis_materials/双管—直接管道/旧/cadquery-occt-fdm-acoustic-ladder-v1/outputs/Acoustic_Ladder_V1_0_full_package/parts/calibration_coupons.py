"""Calibration artifacts for dry-seal fits, acoustic holes and slider preload."""

from __future__ import annotations

import cadquery as cq

import v1_params as p
from geometry_utils import box_centered, compound, cone, cylinder
from parts.supports import make_rx_slider, make_wedge


def _pair_coupon(socket_entry: float, socket_bottom: float, depth: float,
                 kind: str) -> cq.Workplane:
    items = []
    pitch = 18.0
    plate = box_centered(4.0 * pitch + 8.0, 16.0, 2.0,
                         (1.5 * pitch, 0.0, 1.0))
    for index, interference in enumerate(p.DRY_SEAL_INTERFERENCE_TEST_VALUES):
        x = index * pitch
        outer_d = max(socket_entry + 3.0, 10.0)
        boss = cylinder((x, 0.0, 2.0), (0, 0, 1), outer_d, depth + 2.0)
        socket = cone(
            (x, 0.0, depth + 4.0), (0, 0, -1),
            socket_entry + p.FDM_DRY_SEAL_SOCKET_COMPENSATION,
            socket_bottom + p.FDM_DRY_SEAL_SOCKET_COMPENSATION,
            depth,
        )
        plate = plate.union(boss.cut(socket))

        if kind == "module":
            base_d, tip_d = p.module_pilot_diameters(interference)
            plug_length = p.MODULE_DRY_SEAL_PILOT_LENGTH
        elif kind == "joint":
            base_d, tip_d = p.joint_male_diameters(interference)
            plug_length = p.JOINT_MALE_LENGTH
        else:
            base_d, tip_d = p.end_plug_diameters(interference)
            plug_length = p.END_SOCKET_DEPTH

        handle = box_centered(10.0, 8.0, 2.5, (x, 15.0, 1.25))
        plug = cone((x, 15.0, 2.5), (0, 0, 1), base_d, tip_d, plug_length)
        test_piece = handle.union(plug)
        if kind == "joint":
            key = box_centered(
                p.JOINT_KEY_WIDTH, p.JOINT_KEY_HEIGHT,
                max(1.0, plug_length - 1.0),
                (x, 15.0 + base_d / 2.0, 2.5 + plug_length / 2.0),
            )
            test_piece = test_piece.union(key)
        items.append(test_piece.clean())
    items.insert(0, plate.clean())
    return compound(items)


def make_module_dry_seal_coupon() -> cq.Workplane:
    return _pair_coupon(
        p.NODE_DRY_SEAL_SOCKET_ENTRY_TARGET_DIAMETER,
        p.NODE_DRY_SEAL_SOCKET_BOTTOM_TARGET_DIAMETER,
        p.NODE_DRY_SEAL_SOCKET_DEPTH,
        "module",
    )


def make_split_joint_coupon() -> cq.Workplane:
    return _pair_coupon(
        p.JOINT_SOCKET_ENTRY_TARGET_DIAMETER,
        p.JOINT_SOCKET_BOTTOM_TARGET_DIAMETER,
        p.JOINT_SOCKET_DEPTH,
        "joint",
    )


def make_end_dry_seal_coupon() -> cq.Workplane:
    return _pair_coupon(
        p.END_SOCKET_ENTRY_TARGET_DIAMETER,
        p.END_SOCKET_BOTTOM_TARGET_DIAMETER,
        p.END_SOCKET_DEPTH,
        "end",
    )


def make_bridge_holes_coupon() -> cq.Workplane:
    diameters = [2.8, 3.2, 4.0, 4.2, 5.0]
    plate = box_centered(58.0, 16.0, 5.0)
    for index, target in enumerate(diameters):
        x = (index - 2) * 11.0
        bore = cylinder(
            (x, 0.0, -3.0), (0, 0, 1),
            target + p.FDM_ACOUSTIC_HOLE_COMPENSATION, 6.0,
        )
        plate = plate.cut(bore)
    return plate.clean()


def make_slider_coupon() -> cq.Workplane:
    rail = box_centered(55.0, 16.0, 3.0, (0.0, 0.0, 1.5))
    ribs = box_centered(8.0, 1.0, 2.0, (-18.0, -2.2, 3.8)).union(
        box_centered(8.0, 1.0, 2.0, (-18.0, 2.2, 3.8)))
    base = rail.union(ribs).clean()
    slider = make_rx_slider(False).translate((0.0, 15.0, 2.0))
    wedges = [
        make_wedge(level).translate((offset, -18.0, 0.0))
        for level, offset in zip(("L", "M", "H"), (-18.0, 0.0, 18.0))
    ]
    return compound([base, slider, *wedges])


def all_coupons():
    return {
        "ALV1_coupon_module_dry_seal": make_module_dry_seal_coupon(),
        "ALV1_coupon_split_joint": make_split_joint_coupon(),
        "ALV1_coupon_end_dry_seal": make_end_dry_seal_coupon(),
        "ALV1_coupon_bridge_holes": make_bridge_holes_coupon(),
        "ALV1_coupon_slider": make_slider_coupon(),
    }

