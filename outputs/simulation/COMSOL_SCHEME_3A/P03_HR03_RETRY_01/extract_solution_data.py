"""Read saved COMSOL solutions and serialize complex cavity transfer data."""

from __future__ import annotations

import json
from pathlib import Path

import mph
import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01"
PORT = 64706

MODELS = {
    "reduced_coarse": ("COMSOL_3A_P03_HR03_RETRY_01_REDUCED_COARSE.mph", "aveop_cavity(acpr.p_t)"),
    "reduced_fine": ("COMSOL_3A_P03_HR03_RETRY_01_REDUCED_FINE.mph", "aveop_cavity(acpr.p_t)"),
    "thermoviscous_coarse": ("COMSOL_3A_P03_HR03_RETRY_01_THERMOVISCOUS_COARSE.mph", "aveop_cavity(ta.p_t)"),
    "thermoviscous_fine": ("COMSOL_3A_P03_HR03_RETRY_01_THERMOVISCOUS_FINE.mph", "aveop_cavity(ta.p_t)"),
}


def serial(values: np.ndarray) -> list[dict[str, float]]:
    values = np.asarray(values).reshape(-1)
    return [
        {
            "real": float(v.real),
            "imag": float(v.imag),
            "magnitude": float(abs(v)),
            "phase_deg": float(np.degrees(np.angle(v))),
        }
        for v in values
    ]


def main() -> None:
    client = mph.Client(version="6.4", port=PORT)
    output: dict[str, object] = {"comsol_version": client.version, "solutions": {}}
    for key, (filename, expression) in MODELS.items():
        model = client.load(OUT / filename)
        frequencies = np.asarray(model.evaluate("freq")).real.reshape(-1)
        values = np.asarray(model.evaluate(expression)).reshape(-1)
        output["solutions"][key] = {
            "file": filename,
            "expression": expression,
            "frequency_hz": [float(x) for x in frequencies],
            "values": serial(values),
        }
        if key == "reduced_fine":
            comp = model.java.component("comp1")
            output["named_selections"] = {
                tag: [int(x) for x in comp.selection(tag).entities()]
                for tag in [
                    "sel_fluid_all",
                    "sel_hr03_neck_inner",
                    "sel_hr03_cavity",
                    "sel_hr03_neck_outer",
                    "bnd_inlet_inner",
                    "bnd_source_outer",
                    "bnd_wall_all",
                ]
            }
        if key == "thermoviscous_fine":
            tam = model.java.component("comp1").physics("ta").feature("tam1")
            props = [
                "rho0_mat", "rho0", "c_mat", "c", "mu_mat", "mu",
                "muB_mat", "muB", "kcond_mat", "kcond", "Cp_mat", "Cp",
                "gamma_mat", "gamma", "minput_temperature_src",
                "minput_temperature", "minput_pressure_src", "minput_pressure",
            ]
            output["thermoviscous_readback"] = {p: str(tam.getString(p)) for p in props}
            mesh = model.java.component("comp1").mesh("mesh1")
            blp = mesh.feature("bl1").feature("blp1")
            output["boundary_layer_readback"] = {
                p: str(blp.getString(p))
                for p in ["blnlayers", "blstretch", "inittype", "blhminfact", "blhmin", "blhtot"]
            }
        client.remove(model)
    (OUT / "raw_solution_extract.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    client.disconnect()


if __name__ == "__main__":
    main()
