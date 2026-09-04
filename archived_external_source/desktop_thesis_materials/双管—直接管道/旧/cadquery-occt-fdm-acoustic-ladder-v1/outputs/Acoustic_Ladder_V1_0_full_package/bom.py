"""Bill of materials for the no-flexible-seal V1 configuration."""

from __future__ import annotations

import csv
from pathlib import Path


BOM_ROWS = [
    ("ALV1_TX_front_0_200", 1, "PLA/PLA+", "TX front tube"),
    ("ALV1_TX_rear_200_400", 1, "PLA/PLA+", "TX rear tube"),
    ("ALV1_RX_front_0_200", 1, "PLA/PLA+", "RX front tube"),
    ("ALV1_RX_rear_200_400", 1, "PLA/PLA+", "RX rear tube"),
    ("ALV1_module_block", 8, "PLA/PLA+", "Six in use plus spares"),
    ("ALV1_module_bridge_D4p0", 4, "PLA/PLA+", "4.0 mm target bore"),
    ("ALV1_module_bridge_D3p2", 8, "PLA/PLA+", "3.2 mm target bore"),
    ("ALV1_module_bridge_D2p8", 4, "PLA/PLA+", "2.8 mm target bore"),
    ("ALV1_module_development_blank", 2, "PLA/PLA+", "Future development"),
    ("ALV1_joint_lock_clip", 4, "PLA/PLA+", "Two in use, two spare"),
    ("ALV1_end_adapter_hose_barb", 2, "PLA/PLA+", "Near ends"),
    ("ALV1_end_cap_closed", 2, "PLA/PLA+", "Far ends"),
    ("ALV1_end_lock_clip", 6, "PLA/PLA+", "Four in use, two spare"),
    ("ALV1_support_standard_base", 2, "PLA/PLA+", "x about 20 and 380"),
    ("ALV1_support_joint_base", 1, "PLA/PLA+", "x about 200"),
    ("ALV1_RX_slider_standard", 2, "PLA/PLA+", "Standard stations"),
    ("ALV1_RX_slider_joint", 1, "PLA/PLA+", "Joint station"),
    ("ALV1_tube_retainer_standard", 4, "PLA/PLA+", "Two per standard station"),
    ("ALV1_tube_retainer_joint", 2, "PLA/PLA+", "Joint station"),
    ("ALV1_slider_lock_wedge_L", 1, "PLA/PLA+", "Low preload option"),
    ("ALV1_slider_lock_wedge_M", 2, "PLA/PLA+", "Standard preload plus spare"),
    ("ALV1_slider_lock_wedge_H", 1, "PLA/PLA+", "High preload option"),
]


def write_bom(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["part_name", "quantity", "material", "notes"])
        writer.writerows(BOM_ROWS)
    return path

