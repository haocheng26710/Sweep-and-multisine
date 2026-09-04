"""Build geometry-only HR03 seed models in the active COMSOL 6.4 server.

The script intentionally creates no physics.  Physics is added through the
COMSOL MCP, including the dedicated thermoviscous-medium tool.
"""

from __future__ import annotations

import json
from pathlib import Path

import mph


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01"
PORT = 64706


def add_box_selection(comp, tag: str, dim: int, bounds: tuple[float, ...], condition: str = "inside"):
    sel = comp.selection().create(tag, "Box")
    sel.geom("geom1", dim)
    names = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
    for name, value in zip(names, bounds):
        sel.set(name, f"{value:.12g}[m]")
    sel.set("condition", condition)


def build(client: mph.Client, name: str, path: Path) -> dict:
    model = client.create(name)
    java = model.java
    java.label(name)
    java.component().create("comp1", True)
    comp = java.component("comp1")
    geom = comp.geom().create("geom1", 3)

    # Frozen HR03 module-local coordinates.  x<0 is inward; x>0 is outward.
    # The three blocks share exact planar interfaces.
    features = {
        "hr03_neck_inner": ((-0.0286, -0.0014, 0.0), (0.0236, 0.0028, 0.0064)),
        "hr03_cavity": ((-0.0050, -0.0075, 0.0), (0.0260, 0.0150, 0.0064)),
        "hr03_neck_outer": ((0.0210, -0.0022, 0.0), (0.0076, 0.0044, 0.0064)),
    }
    for tag, (pos, size) in features.items():
        feat = geom.feature().create(tag, "Block")
        feat.set("pos", [str(v) for v in pos])
        feat.set("size", [str(v) for v in size])
        feat.set("selresult", True)

    geom.run()

    eps = 1e-7
    add_box_selection(comp, "sel_fluid_all", 3, (-0.0286-eps, 0.0286+eps, -0.0075-eps, 0.0075+eps, -eps, 0.0064+eps))
    add_box_selection(comp, "sel_hr03_neck_inner", 3, (-0.0286-eps, -0.0050+eps, -0.0014-eps, 0.0014+eps, -eps, 0.0064+eps))
    add_box_selection(comp, "sel_hr03_cavity", 3, (-0.0050-eps, 0.0210+eps, -0.0075-eps, 0.0075+eps, -eps, 0.0064+eps))
    add_box_selection(comp, "sel_hr03_neck_outer", 3, (0.0210-eps, 0.0286+eps, -0.0022-eps, 0.0022+eps, -eps, 0.0064+eps))
    add_box_selection(comp, "bnd_inlet_inner", 2, (-0.0286-eps, -0.0286+eps, -0.0014-eps, 0.0014+eps, -eps, 0.0064+eps))
    add_box_selection(comp, "bnd_source_outer", 2, (0.0286-eps, 0.0286+eps, -0.0022-eps, 0.0022+eps, -eps, 0.0064+eps))
    add_box_selection(comp, "bnd_all", 2, (-0.0286-eps, 0.0286+eps, -0.0075-eps, 0.0075+eps, -eps, 0.0064+eps))

    # Stable boundary selection built from geometry-derived Box selections.
    ports = comp.selection().create("bnd_ports", "Union")
    ports.geom("geom1", 2)
    ports.set("input", ["bnd_inlet_inner", "bnd_source_outer"])
    walls = comp.selection().create("bnd_wall_all", "Difference")
    walls.geom("geom1", 2)
    walls.set("add", ["bnd_all"])
    walls.set("subtract", ["bnd_ports"])

    ave = comp.cpl().create("aveop_cavity", "Average")
    ave.selection().named("sel_hr03_cavity")

    java.param().set("rho0", "1.2041[kg/m^3]")
    java.param().set("c0", "343[m/s]")
    java.param().set("mu0", "1.814e-5[Pa*s]")
    java.param().set("mub0", "1.09e-5[Pa*s]")
    java.param().set("k0", "0.0257[W/(m*K)]")
    java.param().set("Cp0", "1005[J/(kg*K)]")
    java.param().set("gamma0", "1.4")
    java.param().set("T0", "293.15[K]")
    java.param().set("p0eq", "101325[Pa]")
    java.param().set("p_inc", "1[Pa]")

    model.save(path)
    info = {
        "model": name,
        "path": str(path),
        "features": features,
        "volume_mm3": 23.6*2.8*6.4 + 26.0*15.0*6.4 + 7.6*4.4*6.4,
        "cavity_volume_mm3": 26.0*15.0*6.4,
    }
    client.remove(model)
    return info


def main() -> None:
    client = mph.Client(version="6.4", port=PORT)
    created = [
        build(client, "P03_HR03_RETRY01_REDUCED", OUT / "hr03_reduced_seed.mph"),
        build(client, "P03_HR03_RETRY01_TV", OUT / "hr03_thermoviscous_seed.mph"),
    ]
    (OUT / "seed_build_summary.json").write_text(json.dumps(created, indent=2), encoding="utf-8")
    client.disconnect()


if __name__ == "__main__":
    main()
