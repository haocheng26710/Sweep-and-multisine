"""Minimal COMSOL 6.4 regression for GeomInfo boundary-to-domain adjacency."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mph


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_trans0_preflight.py"
OUTPUT = HERE / "api_adjacency_test.json"
BAD_CALL = "getAdj(" + "3, 2, boundary)"
GOOD_CALL = "getAdj(2, 3, boundary)"


def static_source_test() -> dict:
    source = RUNNER.read_text(encoding="utf-8")
    result = {
        "bad_call_absent": BAD_CALL not in source,
        "good_call_present": GOOD_CALL in source,
        "workplane_quickz_present": 'wp.set("quickz"' in source,
        "extrude_pos_absent": 'ext.set("pos"' not in source,
    }
    result["pass"] = all(result.values())
    return result


def comsol_adjacency_test(port: int) -> dict:
    client = mph.Client(version="6.4", port=port)
    model = client.create("TRANS0_API_ADJACENCY_REGRESSION")
    try:
        java = model.java
        java.component().create("comp1", True)
        comp = java.component("comp1")
        geom = comp.geom().create("geom1", 3)
        for tag, x0 in (("left", 0.0), ("right", 0.01)):
            block = geom.feature().create(tag, "Block")
            block.set("pos", [str(x0), "0", "0"])
            block.set("size", ["0.01", "0.01", "0.01"])
        union = geom.feature().create("union_adjacent", "Union")
        union.selection("input").set(["left", "right"])
        union.set("intbnd", True)
        geom.run()

        adjacency = {}
        exterior = []
        internal = []
        invalid = []
        for boundary in range(1, int(geom.getNBoundaries()) + 1):
            try:
                domains = [int(value) for value in geom.getAdj(2, 3, boundary)]
            except Exception as exc:
                invalid.append({"boundary": boundary, "error": str(exc)})
                continue
            adjacency[str(boundary)] = domains
            if len(domains) == 1:
                exterior.append(boundary)
            elif len(domains) == 2:
                internal.append(boundary)

        # The wall selection must contain only exterior boundaries.
        walls = comp.selection().create("bnd_walls_regression", "Explicit")
        walls.geom("geom1", 2)
        walls.set(exterior)
        wall_entities = [int(value) for value in walls.entities()]
        result = {
            "comsol_version": str(client.version),
            "boundary_count": int(geom.getNBoundaries()),
            "domain_count": int(geom.getNDomains()),
            "exterior_boundary_count": len(exterior),
            "internal_boundary_count": len(internal),
            "exterior_boundaries": exterior,
            "internal_boundaries": internal,
            "boundary_adjacent_domains": adjacency,
            "invalid_boundary_queries": invalid,
            "wall_boundaries": wall_entities,
            "internal_boundary_excluded_from_walls": set(internal).isdisjoint(wall_entities),
        }
        result["pass"] = (
            not invalid
            and result["domain_count"] == 2
            and len(exterior) == 10
            and len(internal) == 1
            and all(len(adjacency[str(value)]) == 1 for value in exterior)
            and all(len(adjacency[str(value)]) == 2 for value in internal)
            and result["internal_boundary_excluded_from_walls"]
        )
        return result
    finally:
        client.remove(model)
        client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    static = static_source_test()
    result = {"static_source": static, "comsol": None, "pass": static["pass"]}
    if not args.static_only:
        if args.port is None:
            raise SystemExit("--port is required unless --static-only is used")
        result["comsol"] = comsol_adjacency_test(args.port)
        result["pass"] = bool(static["pass"] and result["comsol"]["pass"])
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
