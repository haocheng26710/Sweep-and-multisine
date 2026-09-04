"""Inspect the exact COMSOL 6.4 node structures used as P04D authorities."""

from __future__ import annotations

import json
from pathlib import Path

import mph


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL"
P03 = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01/COMSOL_3A_P03_HR03_RETRY_01_THERMOVISCOUS_FINE.mph"
P04B = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION/P04BN_HR03_PRODUCTION.mph"


def strings(node) -> dict[str, str]:
    values = {}
    for prop in node.properties():
        try:
            values[str(prop)] = str(node.getString(str(prop)))
        except Exception as error:
            values[str(prop)] = f"<unreadable:{type(error).__name__}>"
    return values


def selection(node) -> dict[str, object]:
    try:
        entities = sorted(int(value) for value in node.selection().entities())
    except Exception as error:
        entities = [f"<unreadable:{type(error).__name__}>"]
    try:
        named = str(node.selection().named())
    except Exception as error:
        named = f"<unreadable:{type(error).__name__}>"
    return {"named": named, "entities": entities}


def features(parent) -> list[dict[str, object]]:
    output = []
    for tag in parent.feature().tags():
        node = parent.feature(str(tag))
        item = {
            "tag": str(tag),
            "type": str(node.getType()),
            "label": str(node.label()),
            "selection": selection(node),
            "properties": strings(node),
        }
        try:
            item["subfeatures"] = features(node)
        except Exception:
            item["subfeatures"] = []
        output.append(item)
    return output


def main() -> None:
    mph.option("session", "stand-alone")
    client = mph.start(cores=2)
    output = {"comsol_version": client.version}
    p03 = client.load(P03)
    try:
        comp = p03.java.component("comp1")
        output["p03_tv_physics_features"] = features(comp.physics("ta"))
        output["p03_tv_mesh_features"] = features(comp.mesh("mesh1"))
    finally:
        client.remove(p03)
    p04b = client.load(P04B)
    try:
        comp = p04b.java.component("comp1")
        output["p04b_acpr_features"] = features(comp.physics("acpr"))
        output["p04b_mesh_features"] = features(comp.mesh("mesh1"))
    finally:
        client.remove(p04b)
        client.clear()
    OUT.joinpath("authority_node_inspection.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
