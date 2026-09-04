"""Assembly STEP generation for the four requested configurations."""

from __future__ import annotations

from pathlib import Path

import cadquery as cq

import v1_params as p


def _add(assembly: cq.Assembly, shape, name: str, color, translation=(0, 0, 0)):
    assembly.add(shape, name=name, color=cq.Color(*color),
                 loc=cq.Location(cq.Vector(*translation)))


def _far_oriented(shape):
    return shape.rotate((0, 0, 0), (0, 1, 0), 180.0).translate(
        (p.MAIN_TOTAL_ACOUSTIC_LENGTH, 0.0, 0.0)
    )


def build_configuration(name: str, parts: dict, module_by_node: dict,
                        exploded: bool = False) -> cq.Assembly:
    assy = cq.Assembly(name=name)
    rx_shift = p.RX_TRAVEL if exploded else 0.0
    tube_color = (0.78, 0.78, 0.82, 1.0)
    rx_color = (0.67, 0.76, 0.88, 1.0)
    module_colors = {
        "block": (0.86, 0.58, 0.28, 1.0),
        "D4p0": (0.30, 0.70, 0.38, 1.0),
        "D3p2": (0.28, 0.62, 0.78, 1.0),
        "D2p8": (0.58, 0.46, 0.78, 1.0),
    }

    _add(assy, parts["ALV1_TX_front_0_200"], "TX_front", tube_color)
    _add(assy, parts["ALV1_TX_rear_200_400"], "TX_rear", tube_color)
    _add(assy, parts["ALV1_RX_front_0_200"], "RX_front", rx_color,
         (0.0, rx_shift, 0.0))
    _add(assy, parts["ALV1_RX_rear_200_400"], "RX_rear", rx_color,
         (0.0, rx_shift, 0.0))

    for index, x in enumerate(p.NODE_X_GLOBAL, start=1):
        module_kind = module_by_node.get(index, "block")
        part_name = (
            "ALV1_module_block" if module_kind == "block"
            else f"ALV1_module_bridge_{module_kind}"
        )
        z_shift = (index - 3.5) * 2.0 if exploded else 0.0
        _add(
            assy, parts[part_name], f"N{index}_{module_kind}",
            module_colors[module_kind], (x, rx_shift / 2.0, z_shift),
        )

    # Two split locks, four end locks, near adapters and far caps.
    for y, tag in ((p.TX_CENTER_Y, "TX"), (p.RX_CENTER_Y + rx_shift, "RX")):
        _add(assy, parts["ALV1_joint_lock_clip"], f"joint_lock_{tag}",
             (0.35, 0.35, 0.38, 1.0), (p.SPLIT_X, y, 0.0))
        near_adapter = parts["ALV1_end_adapter_hose_barb"].translate((0.0, y, 0.0))
        assy.add(near_adapter, name=f"near_adapter_{tag}",
                 color=cq.Color(0.45, 0.45, 0.48))
        far_cap = _far_oriented(parts["ALV1_end_cap_closed"]).translate((0.0, y, 0.0))
        assy.add(far_cap, name=f"far_cap_{tag}", color=cq.Color(0.38, 0.38, 0.42))
        _add(assy, parts["ALV1_end_lock_clip"], f"near_end_lock_{tag}",
             (0.25, 0.25, 0.28, 1.0), (0.0, y, 0.0))
        far_lock = _far_oriented(parts["ALV1_end_lock_clip"]).translate((0.0, y, 0.0))
        assy.add(far_lock, name=f"far_end_lock_{tag}", color=cq.Color(0.25, 0.25, 0.28))

    # Three isolated support stations, never a continuous base.
    for station_index, x in enumerate(p.SUPPORT_STATION_X):
        joint = station_index == 1
        base_name = "ALV1_support_joint_base" if joint else "ALV1_support_standard_base"
        slider_name = "ALV1_RX_slider_joint" if joint else "ALV1_RX_slider_standard"
        retainer_name = "ALV1_tube_retainer_joint" if joint else "ALV1_tube_retainer_standard"
        _add(assy, parts[base_name], f"support_base_{station_index+1}",
             (0.25, 0.25, 0.28, 1.0), (x, 0.0, 0.0))
        _add(assy, parts[slider_name], f"rx_slider_{station_index+1}",
             (0.55, 0.55, 0.60, 1.0),
             (x, p.RX_CENTER_Y + rx_shift, p.SUPPORT_SLIDER_ASSEMBLY_Z))
        retainer_x = x + (p.SUPPORT_JOINT_RETAINER_X_OFFSET if joint else 0.0)
        _add(assy, parts[retainer_name], f"tx_retainer_{station_index+1}",
             (0.38, 0.38, 0.42, 1.0), (retainer_x, p.TX_CENTER_Y, 0.0))
        _add(assy, parts[retainer_name], f"rx_retainer_{station_index+1}",
             (0.45, 0.45, 0.50, 1.0),
             (retainer_x, p.RX_CENTER_Y + rx_shift, 0.0))
        wedge_y = (
            p.SLIDER_WEDGE_JOINT_ASSEMBLY_CENTER_Y
            if joint else p.SLIDER_WEDGE_ASSEMBLY_CENTER_Y
        )
        open_stop_y = (
            p.SUPPORT_JOINT_OPEN_STOP_FACE_Y
            if joint else p.SUPPORT_OPEN_STOP_FACE_Y
        )
        wedge_position = (
            (x, wedge_y, p.SLIDER_WEDGE_ASSEMBLY_BOTTOM_Z)
            if not exploded
            else (x, open_stop_y + 5.0, -3.0)
        )
        _add(assy, parts["ALV1_slider_lock_wedge_M"], f"wedge_M_{station_index+1}",
             (0.92, 0.75, 0.20, 1.0), wedge_position)
    return assy


def save_all_assemblies(parts: dict, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    configs = {
        "ALV1_assembly_all_blocked.step": ({}, False),
        "ALV1_assembly_single_B40_N4.step": ({4: "D4p0"}, False),
        "ALV1_assembly_four_B32.step": ({1: "D3p2", 3: "D3p2", 4: "D3p2", 6: "D3p2"}, False),
        "ALV1_assembly_exploded.step": ({4: "D4p0"}, True),
    }
    saved = []
    for filename, (nodes, exploded) in configs.items():
        assy = build_configuration(filename[:-5], parts, nodes, exploded)
        path = output_dir / filename
        assy.save(str(path), exportType="STEP", mode="default")
        saved.append(path)
    return saved
