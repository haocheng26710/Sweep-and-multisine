"""Small, exact-BREP helpers shared by the part generators."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, Sequence

import cadquery as cq


def as_workplane(obj) -> cq.Workplane:
    if isinstance(obj, cq.Workplane):
        return obj
    return cq.Workplane("XY").newObject([obj])


def cylinder(origin, direction, diameter: float, length: float) -> cq.Workplane:
    solid = cq.Solid.makeCylinder(
        diameter / 2.0,
        length,
        cq.Vector(*origin),
        cq.Vector(*direction),
    )
    return as_workplane(solid)


def cone(origin, direction, base_diameter: float, tip_diameter: float,
         length: float) -> cq.Workplane:
    solid = cq.Solid.makeCone(
        base_diameter / 2.0,
        tip_diameter / 2.0,
        length,
        cq.Vector(*origin),
        cq.Vector(*direction),
    )
    return as_workplane(solid)


def box_centered(size_x: float, size_y: float, size_z: float,
                 center=(0.0, 0.0, 0.0)) -> cq.Workplane:
    return cq.Workplane("XY").box(size_x, size_y, size_z).translate(center)


def rounded_box(size_x: float, size_y: float, size_z: float, radius: float,
                center=(0.0, 0.0, 0.0)) -> cq.Workplane:
    body = cq.Workplane("XY").box(size_x, size_y, size_z)
    if radius > 0:
        body = body.edges("|Z").fillet(radius)
    return body.translate(center)


def rounded_rect_prism_x(x0: float, length: float, width_y: float,
                         height_z: float, radius: float, y0: float = 0.0,
                         z0: float = 0.0) -> cq.Workplane:
    profile = cq.Sketch().rect(width_y, height_z).vertices().fillet(radius)
    return cq.Workplane("YZ", origin=(x0, y0, z0)).placeSketch(profile).extrude(length)


def teardrop_prism_x(x0: float, length: float, radius: float,
                     roof_height: float, y0: float = 0.0,
                     z0: float = 0.0) -> cq.Workplane:
    return (
        cq.Workplane("YZ", origin=(x0, y0, z0))
        .moveTo(-radius, 0.0)
        .threePointArc((0.0, -radius), (radius, 0.0))
        .lineTo(0.0, roof_height)
        .close()
        .extrude(length)
    )


def compound(items: Iterable[cq.Workplane]) -> cq.Workplane:
    shapes = []
    for item in items:
        wp = as_workplane(item)
        shapes.extend(wp.vals())
    return as_workplane(cq.Compound.makeCompound(shapes))


def emboss_text(body: cq.Workplane, label: str, origin, fontsize: float,
                height: float, font: str = "Arial") -> cq.Workplane:
    try:
        windows_arial = Path(r"C:\Windows\Fonts\arial.ttf")
        font_path = str(windows_arial) if windows_arial.exists() else None
        text = (
            cq.Workplane("XY", origin=origin)
            .text(label, fontsize, height, combine=False, halign="center",
                  valign="center", font=font, fontPath=font_path)
        )
        return body.union(text)
    except Exception:
        # Geometry remains usable on minimal systems without a discoverable font.
        return body


def move_to_positive(shape: cq.Workplane, margin: float = 0.2) -> cq.Workplane:
    wp = as_workplane(shape)
    bb = wp.val().BoundingBox()
    return wp.translate((margin - bb.xmin, margin - bb.ymin, margin - bb.zmin))


def ground_z(shape: cq.Workplane, z: float = 0.0) -> cq.Workplane:
    """Move one independent printable body onto a shared print-bed Z plane."""
    wp = as_workplane(shape)
    bb = wp.val().BoundingBox()
    return wp.translate((0.0, 0.0, z - bb.zmin))


def print_oriented(shape: cq.Workplane, rotation_axis=None,
                   rotation_degrees: float = 0.0) -> cq.Workplane:
    wp = as_workplane(shape)
    if rotation_axis and abs(rotation_degrees) > 1e-9:
        wp = wp.rotate((0, 0, 0), rotation_axis, rotation_degrees)
    return move_to_positive(wp)


def export_step(shape: cq.Workplane, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(as_workplane(shape), str(path), exportType="STEP")


def export_stl(shape: cq.Workplane, path: Path, linear_tolerance: float,
               angular_tolerance: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(
        as_workplane(shape),
        str(path),
        exportType="STL",
        tolerance=linear_tolerance,
        angularTolerance=angular_tolerance,
    )


def bbox_tuple(shape: cq.Workplane):
    bb = as_workplane(shape).val().BoundingBox()
    return (bb.xlen, bb.ylen, bb.zlen)


def cone_half_angle_deg(entry_diameter: float, bottom_diameter: float,
                        depth: float) -> float:
    return math.degrees(math.atan((entry_diameter - bottom_diameter) / (2.0 * depth)))
