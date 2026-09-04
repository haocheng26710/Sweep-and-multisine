"""Read-only-authority, in-memory P04D coupled-physics preflight."""

from __future__ import annotations

import json
from pathlib import Path

import mph


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL"
AUTHORITY = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION/P04BN_HR03_PRODUCTION.mph"


def entities(component, tag: str) -> list[int]:
    return sorted(int(value) for value in component.selection(tag).entities())


def main() -> None:
    mph.option("session", "stand-alone")
    client = mph.start(cores=2)
    record: dict[str, object] = {
        "authority": str(AUTHORITY.relative_to(ROOT)),
        "comsol_version": client.version,
        "cores": client.cores,
        "coupling_java_type_requested": "AcousticThermoacousticBoundary",
    }
    model = client.load(AUTHORITY)
    try:
        component = model.java.component("comp1")
        fluid = set(entities(component, "sel_fluid_all"))
        module = set(entities(component, "sel_hr_module_all"))
        bulk = sorted(fluid - module)
        component.physics("acpr").selection().set(bulk)
        ta = component.physics().create("ta", "ThermoacousticsSinglePhysics", "geom1")
        ta.selection().named("sel_hr_module_all")

        geometry = component.geom("geom1")
        adjacency = geometry.getAdj(2, 3)
        leaf_domains = {
            "inner": set(entities(component, "sel_hr_neck_inner")),
            "outer": set(entities(component, "sel_hr_neck_outer")),
        }
        crossing_groups = {"inner": [], "outer": []}
        crossing_boundaries = []
        for boundary, adjacent in enumerate(adjacency):
            adjacent_domains = [int(value) for value in adjacent]
            if len(adjacent_domains) != 2:
                continue
            module_side = set(adjacent_domains) & module
            bulk_side = set(adjacent_domains) & set(bulk)
            if module_side and bulk_side:
                crossing_boundaries.append(
                    {"boundary": boundary, "adjacent_domains": adjacent_domains}
                )
                for name, domains in leaf_domains.items():
                    if module_side & domains:
                        crossing_groups[name].append(boundary)

        couplings = []
        for tag, semantic, expected in (
            ("atb_inner", "derived inner HR03-to-PA interface", crossing_groups["inner"]),
            ("atb_outer", "derived outer HR03-to-PA interface", crossing_groups["outer"]),
        ):
            feature = component.multiphysics().create(tag, "AcousticThermoacousticBoundary")
            properties = {}
            for name in feature.properties():
                try:
                    properties[str(name)] = str(feature.getString(str(name)))
                except Exception as error:
                    properties[str(name)] = f"<unreadable: {type(error).__name__}: {error}>"
            # Resolve the two semantic interfaces from adjacency, then assign
            # all partitioned boundary entities explicitly.  Direct entity
            # readback is the decisive pre-solve audit.
            feature.selection().set(expected)
            try:
                named_readback = str(feature.selection().named())
            except Exception as error:
                named_readback = f"<unreadable: {type(error).__name__}: {error}>"
            couplings.append(
                {
                    "tag": tag,
                    "semantic_interface": semantic,
                    "expected_entities": expected,
                    "readback_entities": sorted(int(value) for value in feature.selection().entities()),
                    "java_type": str(feature.getType()),
                    "label": str(feature.label()),
                    "properties_before_selection": properties,
                    "named_selection_readback": named_readback,
                }
            )
        boundary_adjacency = {}
        for boundary in (258, 267):
            # COMSOL entity numbering is one-based; getAdj arrays are indexed
            # by entity number in this model's Java representation.
            candidates = {}
            for index in (boundary - 1, boundary):
                if 0 <= index < len(adjacency):
                    candidates[str(index)] = [int(value) for value in adjacency[index]]
            boundary_adjacency[str(boundary)] = candidates
        record.update(
            {
                "status": "PASS",
                "fluid_domains": sorted(fluid),
                "module_domains": sorted(module),
                "bulk_domains": bulk,
                "pressure_acoustics_readback_domains": sorted(
                    int(value) for value in component.physics("acpr").selection().entities()
                ),
                "thermoviscous_readback_domains": sorted(
                    int(value) for value in component.physics("ta").selection().entities()
                ),
                "couplings": couplings,
                "boundary_adjacency_index_probe": boundary_adjacency,
                "derived_pa_tv_crossing_boundaries": crossing_boundaries,
                "derived_pa_tv_crossing_groups": crossing_groups,
            }
        )
    except Exception as error:
        record.update({"status": "FAIL", "error_type": type(error).__name__, "error": str(error)})
        raise
    finally:
        OUT.joinpath("coupled_physics_preflight_probe.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        try:
            client.remove(model)
        except Exception:
            pass
        client.clear()


if __name__ == "__main__":
    main()
