"""Live COMSOL regression for TRANS-0 RETRY_02 selections."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import mph


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run_trans0_retry02.py"
OUTPUT = HERE / "port_selection_regression.json"


def load_runner():
    spec = importlib.util.spec_from_file_location("trans0_retry02_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def source_gate(runner) -> dict:
    source = RUNNER_PATH.read_text(encoding="utf-8")
    checks = {
        "north_inside_explicit": 'add_box_selection(comp, "bnd_port_N", 2, bounds_N, "inside")' in source,
        "south_inside_explicit": 'add_box_selection(comp, "bnd_port_S", 2, bounds_S, "inside")' in source,
        "no_hardcoded_port_boundary_ids": "set_explicit(comp, \"bnd_port_N\"" not in source
        and "set_explicit(comp, \"bnd_port_S\"" not in source,
        "adjacency_direction_preserved": "geom.getAdj(2, 3, boundary)" in source,
        "quickz_preserved": 'wp.set("quickz"' in source,
        "direct_java_study_run_preserved": "study.run()" in source,
    }
    checks["pass"] = all(checks.values())
    return checks


def build_geometry(runner, client):
    model = client.create("TRANS0_RETRY02_SELECTION_REGRESSION")
    java = model.java
    java.component().create("comp1", True)
    comp = java.component("comp1")
    geom = comp.geom().create("geom1", 3)
    runner.add_cylinder(geom, "plenum", 0, 0, 5.2)
    runner.add_block(geom, "north_readout", -4, 4, 4.6, 32.1)
    runner.add_block(geom, "south_readout", -4, 4, -32.1, -4.6)
    runner.add_hr_branch(geom, "HR03", "N")
    runner.add_hr_branch(geom, "HR07", "S")
    runner.add_polygon_extrusion(geom, [(-4, 88), (4, 88), (8, 105), (10, 117), (-10, 117), (-8, 105)], "north_horn")
    runner.add_polygon_extrusion(geom, [(4, -88), (-4, -88), (-8, -105), (-10, -117), (10, -117), (8, -105)], "south_horn")
    runner.add_cylinder(geom, "mic_core", 0, 0, runner.MIC_FACE_R * 1000, runner.MIC_FACE_Z, runner.AIR_Z0 - runner.MIC_FACE_Z)
    runner.add_cylinder(geom, "mic_outer", 0, 0, runner.MIC_BORE_R * 1000, runner.MIC_FACE_Z, runner.AIR_Z0 - runner.MIC_FACE_Z)
    geom.run()
    return model, comp, geom


def boundary_record(runner, geom, boundary: int) -> dict:
    measure = geom.measureFinal()
    measure.selection().geom("geom1", 2)
    measure.selection().set([boundary])
    bbox = [float(value) for value in measure.getBoundingBox()]
    return {
        "boundary": boundary,
        "adjacent_domains": [int(value) for value in geom.getAdj(2, 3, boundary)],
        "area_m2": float(measure.getArea()),
        "bounding_box_m": bbox,
        "center_m": [(bbox[0] + bbox[1]) / 2, (bbox[2] + bbox[3]) / 2, (bbox[4] + bbox[5]) / 2],
    }


def live_gate(runner, port: int) -> dict:
    client = mph.Client(version="6.4", port=port)
    model, comp, geom = build_geometry(runner, client)
    try:
        eps = 2e-7
        bounds_n = (-0.0101, 0.0101, 0.1169, 0.1171, runner.AIR_Z0 - eps, runner.AIR_Z0 + runner.AIR_H + eps)
        bounds_s = (-0.0101, 0.0101, -0.1171, -0.1169, runner.AIR_Z0 - eps, runner.AIR_Z0 + runner.AIR_H + eps)
        runner.add_box_selection(comp, "old_N_intersects", 2, bounds_n, "intersects")
        runner.add_box_selection(comp, "old_S_intersects", 2, bounds_s, "intersects")
        runner.add_box_selection(comp, "new_N_inside", 2, bounds_n, "inside")
        runner.add_box_selection(comp, "new_S_inside", 2, bounds_s, "inside")
        old_n = runner.selection_entities(comp, "old_N_intersects")
        old_s = runner.selection_entities(comp, "old_S_intersects")
        new_n = runner.selection_entities(comp, "new_N_inside")
        new_s = runner.selection_entities(comp, "new_S_inside")
        actual_tags = [str(tag) for tag in comp.selection().tags()]
        cavity_features = {
            "hr03": ["N_HR03_cavity_radial", "N_HR03_cavity_tangent"]
            + [f"N_HR03_cavity_corner{i}" for i in range(1, 5)],
            "hr07": ["S_HR07_cavity_radial", "S_HR07_cavity_tangent"]
            + [f"S_HR07_cavity_corner{i}" for i in range(1, 5)],
        }
        matched = {
            name: {feature: [tag for tag in actual_tags if feature in tag] for feature in features}
            for name, features in cavity_features.items()
        }
        expected_area = 0.020 * runner.AIR_H
        records_n = [boundary_record(runner, geom, value) for value in new_n]
        records_s = [boundary_record(runner, geom, value) for value in new_s]
        pass_checks = {
            "legacy_intersects_selects_five_each": len(old_n) == 5 and len(old_s) == 5,
            "inside_selects_one_each": len(new_n) == 1 and len(new_s) == 1,
            "each_port_has_one_adjacent_domain": all(len(row["adjacent_domains"]) == 1 for row in records_n + records_s),
            "north_center_y_117mm": len(records_n) == 1 and abs(records_n[0]["center_m"][1] - 0.117) <= 1e-8,
            "south_center_y_minus117mm": len(records_s) == 1 and abs(records_s[0]["center_m"][1] + 0.117) <= 1e-8,
            "areas_within_half_percent": all(abs(row["area_m2"] / expected_area - 1) <= 0.005 for row in records_n + records_s),
            "all_cavity_feature_selection_tags_observed": all(len(tags) > 0 for group in matched.values() for tags in group.values()),
        }
        return {
            "comsol_version": str(client.version),
            "old_intersects": {"N": old_n, "S": old_s},
            "new_inside": {"N": records_n, "S": records_s},
            "expected_port_area_m2": expected_area,
            "actual_component_selection_tags": actual_tags,
            "cavity_primitive_feature_tags": cavity_features,
            "matched_feature_output_selection_tags": matched,
            "checks": pass_checks,
            "pass": all(pass_checks.values()),
        }
    finally:
        client.remove(model)
        client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    runner = load_runner()
    source = source_gate(runner)
    live = None if args.static_only else live_gate(runner, args.port)
    result = {"source_gate": source, "live_regression": live,
              "pass": source["pass"] and (live is None or live["pass"])}
    if live is not None:
        OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
