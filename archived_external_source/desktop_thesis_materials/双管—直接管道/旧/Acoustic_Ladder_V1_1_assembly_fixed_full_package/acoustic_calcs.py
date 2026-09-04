"""One-dimensional acoustic derivations requested for V1 reporting."""

from __future__ import annotations

import json
import math
from pathlib import Path

import v1_params as p


def calculate():
    r = p.MAIN_INNER_RADIUS
    h = p.MAIN_ROOF_HEIGHT
    area = 0.5 * math.pi * r * r + r * h
    wetted_perimeter = math.pi * r + 2.0 * math.hypot(r, h)
    hydraulic_diameter = 4.0 * area / wetted_perimeter
    equivalent_circle_diameter = math.sqrt(4.0 * area / math.pi)
    modal_spacing = p.SPEED_OF_SOUND_M_S / (2.0 * p.MAIN_TOTAL_ACOUSTIC_LENGTH / 1000.0)
    l_geom = p.MAIN_CENTER_SPACING - 2.0 * p.MAIN_INNER_RADIUS

    delays = {}
    for index, x_mm in enumerate(p.NODE_X_GLOBAL, start=1):
        delays[f"N{index}"] = {
            "x_mm": x_mm,
            "round_trip_delay_ms": 2.0 * (x_mm / 1000.0) / p.SPEED_OF_SOUND_M_S * 1000.0,
        }

    bridges = {}
    for diameter in p.BRIDGE_DIAMETERS_TARGET:
        key = f"D{diameter:.1f}"
        l_eff_mm = l_geom + 0.8 * diameter
        bridge_area = math.pi * diameter * diameter / 4.0
        ratios = {}
        for frequency in p.REFERENCE_FREQUENCIES_HZ:
            k_per_m = 2.0 * math.pi * frequency / p.SPEED_OF_SOUND_M_S
            ratios[str(frequency)] = (
                k_per_m * (l_eff_mm / 1000.0) * (area / bridge_area)
            )
        bridges[key] = {
            "target_diameter_mm": diameter,
            "cad_diameter_mm": diameter + p.FDM_ACOUSTIC_HOLE_COMPENSATION,
            "geometric_length_mm": l_geom,
            "effective_length_mm": l_eff_mm,
            "quarter_wave_frequency_hz": (
                p.SPEED_OF_SOUND_M_S / (4.0 * l_eff_mm / 1000.0)
            ),
            "relative_impedance_magnitude": ratios,
        }

    dead_length = p.BLOCK_TIP_TO_MAIN_LUMEN
    dead_area = math.pi * p.NODE_THROAT_TARGET_DIAMETER ** 2 / 4.0
    dead_volume = dead_area * dead_length
    dead_quarter_wave = p.SPEED_OF_SOUND_M_S / (4.0 * dead_length / 1000.0)

    return {
        "version": p.VERSION,
        "units": {"length": "mm", "frequency": "Hz", "delay": "ms"},
        "main_teardrop": {
            "area_mm2": area,
            "wetted_perimeter_mm": wetted_perimeter,
            "hydraulic_diameter_mm": hydraulic_diameter,
            "equivalent_circle_diameter_mm": equivalent_circle_diameter,
        },
        "main_tube_modal_spacing_hz": modal_spacing,
        "node_round_trip_delays": delays,
        "bridge_geometric_length_mm": l_geom,
        "bridges": bridges,
        "blocked_node_residual_dead_volume": {
            "length_mm": dead_length,
            "volume_mm3": dead_volume,
            "quarter_wave_frequency_hz": dead_quarter_wave,
        },
        "model_limitations": [
            "Relative bridge impedance is a low-frequency lumped estimate.",
            "At roughly 4-8 kHz each short bridge increasingly behaves as a distributed waveguide.",
            "Confirm final behaviour with complex transfer-function measurements.",
        ],
    }


def write_reports(report_dir: Path):
    report_dir.mkdir(parents=True, exist_ok=True)
    data = calculate()
    json_path = report_dir / "derived_acoustics_v1.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    td = data["main_teardrop"]
    lines = [
        "# Acoustic Ladder V1.0 声学设计报告",
        "",
        "所有数值均由 `acoustic_calcs.py` 重新计算。长度单位为 mm。",
        "",
        "## 主管截面",
        "",
        f"- 面积：{td['area_mm2']:.4f} mm²",
        f"- 湿周：{td['wetted_perimeter_mm']:.4f} mm",
        f"- 水力直径：{td['hydraulic_diameter_mm']:.4f} mm",
        f"- 等效圆直径：{td['equivalent_circle_diameter_mm']:.4f} mm",
        f"- 400 mm 主管模态间距尺度：{data['main_tube_modal_spacing_hz']:.3f} Hz",
        "",
        "## 节点往返传播延迟",
        "",
        "| 节点 | x (mm) | 往返延迟 (ms) |",
        "|---|---:|---:|",
    ]
    for node, row in data["node_round_trip_delays"].items():
        lines.append(f"| {node} | {row['x_mm']:.1f} | {row['round_trip_delay_ms']:.3f} |")
    lines.extend([
        "",
        "## 桥模块",
        "",
        "| 桥 | 有效长度 (mm) | 四分之一波长 (Hz) |",
        "|---|---:|---:|",
    ])
    for key, row in data["bridges"].items():
        lines.append(f"| {key} | {row['effective_length_mm']:.3f} | {row['quarter_wave_frequency_hz']:.1f} |")
    lines.extend([
        "",
        "相对阻抗幅值近似 `|Zb|/Z0 ≈ k·Leff·(Smain/Sbridge)`：",
        "",
        "| 桥 | 500 Hz | 1 kHz | 2 kHz | 4 kHz | 8 kHz |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for key, row in data["bridges"].items():
        vals = row["relative_impedance_magnitude"]
        lines.append(
            f"| {key} | {vals['500']:.3f} | {vals['1000']:.3f} | "
            f"{vals['2000']:.3f} | {vals['4000']:.3f} | {vals['8000']:.3f} |"
        )
    dead = data["blocked_node_residual_dead_volume"]
    lines.extend([
        "",
        "## 封堵接口残余死腔",
        "",
        f"残余长度 {dead['length_mm']:.3f} mm，近似体积 {dead['volume_mm3']:.3f} mm³，"
        f"四分之一波长频率 {dead['quarter_wave_frequency_hz'] / 1000.0:.1f} kHz。",
        "",
        "## 适用范围",
        "",
        "4–8 kHz 附近短桥逐渐表现为分布式波导，不能继续只用纯惯性阻抗解释。"
        "最终结果应通过复传递函数和实验确认。",
        "",
    ])
    md_path = report_dir / "acoustic_design_report_v1.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path, data

