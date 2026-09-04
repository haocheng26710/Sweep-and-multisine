"""Regression checks for the direct speaker/microphone end adapters."""

from __future__ import annotations

import tempfile
from pathlib import Path

import trimesh

import v1_params as p
from geometry_utils import export_stl, ground_z, print_oriented
from parts.end_adapters import make_end_lock_clip
from parts.integrated_io_adapters import (
    ADAPTER_SPECS,
    make_integrated_microphone_adapter,
    make_integrated_speaker_adapter,
)
from parts.main_tubes import all_main_tubes_round


EXPECTED = {
    "speaker": {"socket_id": 6.2, "socket_od": 10.2},
    "microphone": {"socket_id": 8.8, "socket_od": 13.0},
}


def _mesh_for_print(shape) -> trimesh.Trimesh:
    printable = ground_z(print_oriented(shape, (0, 1, 0), -90.0))
    with tempfile.TemporaryDirectory(prefix="alv1_io_adapter_test_") as temp_dir:
        path = Path(temp_dir) / "part.stl"
        export_stl(
            printable,
            path,
            p.STL_LINEAR_TOLERANCE,
            p.STL_ANGULAR_TOLERANCE,
        )
        return trimesh.load_mesh(path, process=True)


def main() -> None:
    cases = {
        "speaker": make_integrated_speaker_adapter(),
        "microphone": make_integrated_microphone_adapter(),
    }
    tube = all_main_tubes_round()["ALV1_TX_front_0_200"]
    lock = make_end_lock_clip().translate((0.0, p.TX_CENTER_Y, 0.0))
    failures: list[str] = []

    for name, shape in cases.items():
        spec = ADAPTER_SPECS[name]
        expected = EXPECTED[name]
        bb = shape.val().BoundingBox()
        placed = shape.translate((0.0, p.TX_CENTER_Y, 0.0))
        mesh = _mesh_for_print(shape)
        shells = len(mesh.split(only_watertight=False))
        downward = mesh.face_normals[:, 2] < -0.707
        above_bed = mesh.triangles_center[:, 2] > 0.25
        unsupported_z = mesh.triangles_center[downward & above_bed, 2]
        seal_overlap = float(placed.intersect(tube).val().Volume())
        seal_gap = float(placed.val().distance(tube.val()))
        lock_overlap = float(placed.intersect(lock).val().Volume())

        print(
            f"{name}: bbox=({bb.xmin:.3f},{bb.xmax:.3f}), "
            f"shells={shells}, watertight={mesh.is_watertight}, "
            f"seal_overlap={seal_overlap:.6f}, seal_gap={seal_gap:.6f}, "
            f"lock_overlap={lock_overlap:.6f}"
        )

        if abs(spec.socket_id_mm - expected["socket_id"]) > 1e-9:
            failures.append(f"{name}: device socket ID changed")
        if abs(spec.socket_od_mm - expected["socket_od"]) > 1e-9:
            failures.append(f"{name}: device socket OD changed")
        if abs(spec.socket_depth_mm - 10.0) > 1e-9:
            failures.append(f"{name}: device socket depth changed")
        if abs(spec.transition_length_mm - 4.0) > 1e-9:
            failures.append(f"{name}: required integral transition changed")
        if abs(spec.acoustic_bore_mm - 2.8) > 1e-9:
            failures.append(f"{name}: 2.8 mm acoustic restriction changed")
        if abs(spec.main_tube_bore_mm - 4.15) > 1e-9:
            failures.append(f"{name}: V1.3 end-plug bore changed")
        if abs(spec.external_extension_mm - 16.0) > 1e-9:
            failures.append(f"{name}: unexpected external extension")
        if abs(bb.xmin + 16.0) > 0.01 or abs(bb.xmax - 8.0) > 0.01:
            failures.append(f"{name}: axial envelope is not -16..8 mm")
        if not shape.val().isValid():
            failures.append(f"{name}: invalid BREP")
        if not mesh.is_watertight or shells != 1:
            failures.append(f"{name}: STL is not one watertight shell")
        if abs(float(mesh.bounds[0, 2])) > 0.01:
            failures.append(f"{name}: print STL is not grounded")
        if any(z < 13.70 or z > 13.80 for z in unsupported_z):
            failures.append(f"{name}: unsupported face exists outside the lock ear")
        if seal_overlap > 1.0e-5 or seal_gap > 1.0e-4:
            failures.append(f"{name}: calibrated end fit changed")
        if lock_overlap > 1.0e-5:
            failures.append(f"{name}: end lock collision")

    if failures:
        raise AssertionError("\n".join(failures))
    print("PASS: both integrated heads preserve all mating dimensions")


if __name__ == "__main__":
    main()
