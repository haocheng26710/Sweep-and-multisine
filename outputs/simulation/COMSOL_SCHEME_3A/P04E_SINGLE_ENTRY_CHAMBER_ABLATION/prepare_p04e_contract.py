"""Verify authorities and freeze the P04E contract before any acoustic solve."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import p04e_analysis as p

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION"
P04B = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION"
P04C = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC"
CONTRACT = OUT / "ablation_contract.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def verify_manifest(path: Path) -> dict[str, object]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        actual_path = ROOT / relative
        actual = sha256(actual_path) if actual_path.exists() else None
        rows.append({"path": relative, "expected_sha256": expected, "actual_sha256": actual, "match": actual == expected})
    return {"manifest": str(path.relative_to(ROOT)), "entries": len(rows),
            "matches": sum(bool(row["match"]) for row in rows), "all_match": all(row["match"] for row in rows),
            "mismatches": [row for row in rows if not row["match"]]}


def state_record(state: str, fraction: float, width: float | None) -> dict[str, object]:
    volume = p.ORIGINAL_VOLUME_MM3 if width is None else p.retained_volume_mm3(width)
    corridor_width = 36.0 if width is None else width
    return {
        "state": state,
        "target_fraction": fraction,
        "target_volume_mm3": fraction * p.ORIGINAL_VOLUME_MM3,
        "corridor_width_mm": corridor_width,
        "geometry_role": "unmodified authority cylinder" if width is None else "orthogonal cross intersected with authority cylinder",
        "central_well_diameter_mm": p.WELL_DIAMETER_MM,
        "remaining_air_volume_mm3": volume,
        "insert_volume_mm3": p.ORIGINAL_VOLUME_MM3 - volume,
        "achieved_fraction": volume / p.ORIGINAL_VOLUME_MM3,
        "fixed_channel_shared_area_each_mm2": 8.0 * 9.2,
        "minimum_lateral_clearance_beyond_fixed_channel_mm": corridor_width - 8.0,
    }


def main() -> None:
    if CONTRACT.exists():
        raise RuntimeError("Frozen ablation_contract.json already exists; refusing to modify it")
    audits = [verify_manifest(P04B / "SHA256SUMS"), verify_manifest(P04C / "SHA256SUMS")]
    hr03 = P04B / "P04BN_HR03_PRODUCTION.mph"
    diag = P04C / "diagnostic_contract.json"
    direct = {
        "P04B_HR03_MPH": {"path": str(hr03.relative_to(ROOT)), "expected_sha256": "33bf573dddc0c0b163e7f0a5e177fc227d16aa541479606e971cb4a3a9398db7", "actual_sha256": sha256(hr03)},
        "P04C_contract": {"path": str(diag.relative_to(ROOT)), "expected_sha256": "1be500f1dad6de4a1b14cf97ce772113d5b50408e2f2eca4dfc12efd6fe5bdc0", "actual_sha256": sha256(diag)},
    }
    if not all(audit["all_match"] for audit in audits) or not all(v["expected_sha256"] == v["actual_sha256"] for v in direct.values()):
        raise RuntimeError("P04E BLOCKED_BY_PROVENANCE")
    authority_audit = {
        "phase_id": "P04E_SINGLE_ENTRY_CHAMBER_ABLATION",
        "audited_at_with_timezone": datetime.now().astimezone().isoformat(),
        "direct_authorities": direct,
        "manifest_audits": audits,
        "authority_mismatch": False,
        "preserved_statuses": {"P03": "as_designed_close", "P04A": "P04A INADEQUATE", "P04B-N": "MODEL NOT CREDIBLE FOR U4", "P04C": "TOPOLOGY HYBRIDIZATION SUPPORTED", "P04D": "BLOCKED_BY_SOLVER", "P04D_RETRY_01": "BLOCKED_BY_SOLVER"},
        "final_test_read": False,
    }
    atomic_json(OUT / "authority_audit.json", authority_audit)

    states = [state_record("100pct", 1.0, None), state_record("75pct", 0.75, p.solve_corridor_width(0.75 * p.ORIGINAL_VOLUME_MM3)), state_record("50pct", 0.50, p.solve_corridor_width(0.50 * p.ORIGINAL_VOLUME_MM3))]
    contract = {
        "schema_version": "comsol_scheme_3a_p04e_ablation_contract_v1.0.0",
        "phase_id": "P04E_SINGLE_ENTRY_CHAMBER_ABLATION",
        "frozen_before_new_p04e_acoustic_values": True,
        "module": "HR03",
        "assembly": "P04B-N nominal S1 single-entry topology",
        "sole_design_variable": "remaining effective central-chamber air volume after symmetric four-corner filling",
        "states": states,
        "physics": {"interface": "Pressure Acoustics, Frequency Domain", "wall_loss": "P03/P04B nominal Thermoviscous Boundary Layer Impedance", "hr_neck_effective_length_delta_mm": 0.0, "effective_loss_scale": 1.0, "sound_speed_m_per_s": 343.0, "density_kg_per_m3": 1.2041, "module_geometry": "unchanged P04B-N HR03"},
        "mesh": {"automatic_level": 6, "maximum_frequency_hz": 2100.0, "meshes_per_state": 1, "convergence_claim": False},
        "regular_frequencies_hz": list(range(1400, 2101, 25)),
        "landmarks_hz": [1646.88357862959, 1986.97249931757],
        "landmarks_excluded_from_peak_search": True,
        "peak_rule": "all strict interior local maxima of cavity total energy on the regular grid; three-point quadratic in log2(f)-log10(E), accepted only for a finite concave vertex strictly between neighbors; endpoints excluded",
        "branch_continuity": {"features": ["log-frequency", "cavity/module participation", "kinetic fraction", "cavity-chamber phase"], "cost": "0.40 frequency + 0.30 participation + 0.15 kinetic fraction + 0.15 wrapped phase", "nearest_to_1904_only_forbidden": True},
        "classification_states": ["P04E RESTORATION TREND SUPPORTED", "P04E PARTIAL RESTORATION", "P04E NO USEFUL RESTORATION", "P04E ADVERSE_OR_SPLIT_RESPONSE", "P04E BLOCKED_BY_PROVENANCE", "P04E INVALID_INTERVENTION_GEOMETRY", "P04E BLOCKED_BY_MESH", "P04E BLOCKED_BY_SOLVER"],
        "classification_thresholds": {"restoration_min_total_octave_shift": 1.0 / 12.0, "no_useful_change_octaves": 1.0 / 24.0, "reference_isolated_full_tv_fine_hz": p.ISOLATED_FULL_TV_FINE_HZ, "reference_integrated_reduced_hz": p.BASELINE_INTEGRATED_HZ},
        "prohibitions": ["no parameter fitting", "no fourth volume", "no result-driven shape changes", "no alternative insert rescue", "no second mesh", "no P05/P06/U4", "no full thermoviscous S1", "no PA-TV coupling repair", "no final-test read", "no STL", "no commit/push/tag/release"],
        "authority_sha256": {key: value["actual_sha256"] for key, value in direct.items()},
        "final_test_read": False,
    }
    atomic_json(CONTRACT, contract)
    contract_hash = sha256(CONTRACT)
    atomic_json(OUT / "intervention_geometry_definition.json", {
        "phase_id": contract["phase_id"], "ablation_contract_sha256": contract_hash,
        "original": {"radius_mm": 18.0, "height_mm": 9.2, "volume_mm3": p.ORIGINAL_VOLUME_MM3, "fixed_inner_channel_width_mm": 8.0, "fixed_inner_radial_range_mm": [17.0, 32.0], "microphone_disk_diameter_mm": 8.8},
        "construction": "At both z=3..7 mm and z=7..12.2 mm, retain the union of x- and y-aligned full-height rectangular corridors, intersect it with the original radius-18 cylinder, preserve the existing radius-4.4 microphone-plane partition, and remove the four diagonal complements from the acoustic air domain.",
        "well_containment_proof": "At width>=8 mm, any point outside both strips has radius>sqrt(4^2+4^2)=5.657 mm, so the radius-4.5 mm well is wholly retained.",
        "states": states, "root_method": "100-iteration deterministic monotonic bisection on the exact disk-cross analytic area, completed before acoustics", "acoustic_result_used_to_choose_geometry": False,
    })
    print(json.dumps({"ablation_contract_sha256": contract_hash, "states": states}, indent=2))


if __name__ == "__main__":
    main()
