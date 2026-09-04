"""Hard assembly-fit gates for locks, supports, retainers and wedges."""

from __future__ import annotations

import csv
from pathlib import Path

import cadquery as cq

import v1_params as p


BOOLEAN_TOLERANCE_MM3 = 1.0e-5
CONTACT_TOLERANCE_MM = 1.0e-4


def _volume(a, b) -> float:
    return float(a.intersect(b).val().Volume())


def _distance(a, b) -> float:
    return float(a.val().distance(b.val()))


def validate_mechanics(project_root: Path, records: dict):
    entries = []

    def add(status, check, detail):
        entries.append((status, check, detail))

    def no_overlap(check, first, second):
        volume = _volume(first, second)
        add(
            "PASS" if volume <= BOOLEAN_TOLERANCE_MM3 else "FAIL",
            check,
            f"non-seal intersection {volume:.6f} mm^3",
        )

    def touches(check, first, second):
        gap = _distance(first, second)
        add(
            "PASS" if gap <= CONTACT_TOLERANCE_MM else "FAIL",
            check,
            f"minimum gap {gap:.6f} mm",
        )

    shapes = {name: record.shape for name, record in records.items()}

    # Split-joint cap spans both retaining ears but has zero volume collision.
    joint_lock = shapes["ALV1_joint_lock_clip"].translate(
        (p.SPLIT_X, p.TX_CENTER_Y, 0.0)
    )
    tx_front = shapes["ALV1_TX_front_0_200"]
    tx_rear = shapes["ALV1_TX_rear_200_400"]
    no_overlap("Joint lock / TX front", joint_lock, tx_front)
    no_overlap("Joint lock / TX rear", joint_lock, tx_rear)
    joint_bb = joint_lock.val().BoundingBox()
    front_ear_min = p.SPLIT_X - 2.0 - p.JOINT_LOCK_EAR_SIZE_X / 2.0
    rear_ear_max = (
        p.SPLIT_X + p.JOINT_LOCAL_COLLAR_LENGTH - 1.5
        + p.JOINT_LOCK_EAR_SIZE_X / 2.0
    )
    covers_joint = joint_bb.xmin < front_ear_min and joint_bb.xmax > rear_ear_max
    add(
        "PASS" if covers_joint else "FAIL",
        "Joint lock axial ear coverage",
        f"lock=[{joint_bb.xmin:.3f},{joint_bb.xmax:.3f}], "
        f"ears=[{front_ear_min:.3f},{rear_ear_max:.3f}] mm",
    )

    # Near and far end locks use mirrored geometry and touch neither rigid part.
    near_lock = shapes["ALV1_end_lock_clip"].translate(
        (0.0, p.TX_CENTER_Y, 0.0)
    )
    near_adapter = shapes["ALV1_end_adapter_hose_barb"].translate(
        (0.0, p.TX_CENTER_Y, 0.0)
    )
    no_overlap("Near end lock / tube", near_lock, tx_front)
    no_overlap("Near end lock / adapter", near_lock, near_adapter)

    far_lock = (
        shapes["ALV1_end_lock_clip"]
        .rotate((0, 0, 0), (0, 1, 0), 180.0)
        .translate((p.MAIN_TOTAL_ACOUSTIC_LENGTH, p.TX_CENTER_Y, 0.0))
    )
    far_cap = (
        shapes["ALV1_end_cap_closed"]
        .rotate((0, 0, 0), (0, 1, 0), 180.0)
        .translate((p.MAIN_TOTAL_ACOUSTIC_LENGTH, p.TX_CENTER_Y, 0.0))
    )
    no_overlap("Far end lock / tube", far_lock, tx_rear)
    no_overlap("Far end lock / cap", far_lock, far_cap)

    def support_station(joint: bool, x: float):
        suffix = "joint" if joint else "standard"
        base_name = (
            "ALV1_support_joint_base" if joint
            else "ALV1_support_standard_base"
        )
        slider_name = (
            "ALV1_RX_slider_joint" if joint
            else "ALV1_RX_slider_standard"
        )
        retainer_name = (
            "ALV1_tube_retainer_joint" if joint
            else "ALV1_tube_retainer_standard"
        )
        retainer_x = x + (p.SUPPORT_JOINT_RETAINER_X_OFFSET if joint else 0.0)
        wedge_y = (
            p.SLIDER_WEDGE_JOINT_ASSEMBLY_CENTER_Y
            if joint else p.SLIDER_WEDGE_ASSEMBLY_CENTER_Y
        )
        base = shapes[base_name].translate((x, 0.0, 0.0))
        slider = shapes[slider_name].translate(
            (x, p.RX_CENTER_Y, p.SUPPORT_SLIDER_ASSEMBLY_Z)
        )
        tx_retainer = shapes[retainer_name].translate(
            (retainer_x, p.TX_CENTER_Y, 0.0)
        )
        rx_retainer = shapes[retainer_name].translate(
            (retainer_x, p.RX_CENTER_Y, 0.0)
        )
        wedge = shapes["ALV1_slider_lock_wedge_M"].translate(
            (x, wedge_y, p.SLIDER_WEDGE_ASSEMBLY_BOTTOM_Z)
        )

        tube_pairs = (
            ((tx_front, tx_rear),
             (shapes["ALV1_RX_front_0_200"], shapes["ALV1_RX_rear_200_400"]))
            if joint else
            ((tx_front,), (shapes["ALV1_RX_front_0_200"],))
        )
        tx_tubes, rx_tubes = tube_pairs

        rigid_pairs = [
            ("base / slider", base, slider),
            ("base / wedge", base, wedge),
            ("slider / wedge", slider, wedge),
            ("base / TX retainer", base, tx_retainer),
            ("slider / RX retainer", slider, rx_retainer),
        ]
        for label, first, second in rigid_pairs:
            no_overlap(f"{suffix} support {label}", first, second)

        for index, tube in enumerate(tx_tubes, start=1):
            no_overlap(f"{suffix} base / TX tube {index}", base, tube)
            no_overlap(f"{suffix} TX retainer / tube {index}", tx_retainer, tube)
        for index, tube in enumerate(rx_tubes, start=1):
            no_overlap(f"{suffix} slider / RX tube {index}", slider, tube)
            no_overlap(f"{suffix} RX retainer / tube {index}", rx_retainer, tube)

        touch_pairs = [
            ("base / slider rail", base, slider),
            ("base / wedge", base, wedge),
            ("slider / wedge", slider, wedge),
            ("base / TX retainer feet", base, tx_retainer),
            ("slider / RX retainer feet", slider, rx_retainer),
            ("base / TX tube", base, tx_tubes[0]),
            ("slider / RX tube", slider, rx_tubes[0]),
            ("TX retainer / tube", tx_retainer, tx_tubes[0]),
            ("RX retainer / tube", rx_retainer, rx_tubes[0]),
        ]
        for label, first, second in touch_pairs:
            touches(f"{suffix} support contact {label}", first, second)

        closed_face = (
            p.SUPPORT_JOINT_CLOSED_STOP_FACE_Y
            if joint else p.SUPPORT_CLOSED_STOP_FACE_Y
        )
        open_face = (
            p.SUPPORT_JOINT_OPEN_STOP_FACE_Y
            if joint else p.SUPPORT_OPEN_STOP_FACE_Y
        )
        length_y = (
            p.SUPPORT_SLIDER_JOINT_LENGTH_Y
            if joint else p.SUPPORT_SLIDER_LENGTH_Y
        )
        closed_ok = abs(closed_face - (p.RX_CENTER_Y - length_y / 2.0)) < 1e-9
        open_ok = abs(open_face - (p.RX_CENTER_Y + p.RX_TRAVEL + length_y / 2.0)) < 1e-9
        add(
            "PASS" if closed_ok and open_ok else "FAIL",
            f"{suffix} rigid 20.0/22.5 mm stops",
            f"closed center={p.RX_CENTER_Y:.3f}, "
            f"open center={p.RX_CENTER_Y + p.RX_TRAVEL:.3f}, "
            f"travel={p.RX_TRAVEL:.3f} mm",
        )

        open_slider = shapes[slider_name].translate(
            (x, p.RX_CENTER_Y + p.RX_TRAVEL, p.SUPPORT_SLIDER_ASSEMBLY_Z)
        )
        no_overlap(f"{suffix} open slider / base", open_slider, base)
        touches(f"{suffix} open hard stop", open_slider, base)

        if joint:
            no_overlap("Joint lock / joint TX retainer", joint_lock, tx_retainer)

    support_station(False, p.SUPPORT_STATION_X[0])
    support_station(True, p.SUPPORT_STATION_X[1])

    # Preview STEP must contain the six retainers in addition to the old 29 solids.
    assembly_dir = project_root / "exports" / "assemblies"
    for path in sorted(assembly_dir.glob("*.step")):
        assembly = cq.importers.importStep(str(path))
        solids = len(assembly.val().Solids())
        add(
            "PASS" if solids >= 35 else "FAIL",
            f"Assembly includes retainers: {path.name}",
            f"solids={solids}; expected at least 35",
        )

    # Three installed M wedges plus one spare are required by the previews.
    bom_path = project_root / "exports" / "reports" / "BOM.csv"
    quantity = 0
    if bom_path.exists():
        with bom_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["part_name"] == "ALV1_slider_lock_wedge_M":
                    quantity = int(row["quantity"])
                    break
    add(
        "PASS" if quantity >= 4 else "FAIL",
        "M-wedge installed/spare quantity",
        f"quantity={quantity}; required=4",
    )
    return entries

