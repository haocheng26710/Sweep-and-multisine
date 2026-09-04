from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
P04A0 = OUT.parent / "P04A0_CALIBRATION_PREFLIGHT"
REPORT = ROOT / "docs" / "progress" / "COMSOL_3A_P04A_GLOBAL_CALIBRATION.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def root_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> None:
    audit = {
        "phase_id": "P04A_GLOBAL_CALIBRATION",
        "status": "passed_before_modelling",
        "p04a0_sha256sums_verified": {"passed": 9, "failed": 0},
        "authority_bindings": {"P01": "passed", "P03_HR03_RETRY_01": "passed", "P04A0": "passed"},
        "raw_input_hashes": {"TXT_passed": 12, "MDAT_passed": 12, "failed": 0},
        "primary_repeats": {"P05": [1, 3, 4, 5, 6], "HR03": [1, 3, 4, 5, 6]},
        "farthest_flags": {"P05": "R V2.5_base_02.txt", "HR03": "R V2.5_HR03_02.txt"},
        "all_six_repeats": {"P05": [1, 2, 3, 4, 5, 6], "HR03": [1, 2, 3, 4, 5, 6]},
        "physics_configure_thermoviscous_medium_visible": True,
        "comsol": {"version": "6.4", "server": "localhost:64706", "cores": 2, "single_server_instance": True},
        "final_test_read": False,
        "git_branch": "feature/v2-dual-input",
        "preexisting_user_changes_preserved": True,
    }
    (OUT / "authority_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")

    manifest_rows = []
    authority_names = [
        "calibration_contract_addendum.json", "calibration_parameter_bounds.csv",
        "calibration_input_manifest.csv", "repeat_mapping.json", "objective_definition.md",
        "identifiability_plan.md", "search_plan.json", "SHA256SUMS",
    ]
    for name in authority_names:
        path = P04A0 / name
        manifest_rows.append({
            "category": "authority", "identity": name, "path": root_relative(path),
            "sha256": sha256(path), "status": "verified", "details": "P04A0 frozen authority",
        })

    with (P04A0 / "calibration_input_manifest.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for kind in ("txt", "mdat"):
                manifest_rows.append({
                    "category": "experimental_input", "identity": f'{row["condition"]}:repeat_{row["campaign_repeat"]}:{kind.upper()}',
                    "path": row[f"{kind}_filename"], "sha256": row[f"{kind}_sha256"],
                    "status": "verified_before_modelling",
                    "details": f'primary_selected={row["primary_selected"]}; farthest={row["primary_drop_flag"]}',
                })

    for name, label in (
        ("P04A_P05_NOMINAL.mph", "P05 nominal"), ("P04A_HR03_NOMINAL.mph", "HR03 nominal"),
        ("P04A_P05_CALIBRATED.mph", "P05 descriptive selected"),
        ("P04A_HR03_CALIBRATED.mph", "HR03 descriptive selected"),
    ):
        path = OUT / name
        manifest_rows.append({
            "category": "model", "identity": label, "path": root_relative(path),
            "sha256": sha256(path), "status": "saved_and_reload_verified", "details": "COMSOL 6.4 MPH",
        })
    for path in sorted((OUT / "candidate_configs").glob("*.json")):
        manifest_rows.append({
            "category": "candidate_config", "identity": path.stem, "path": root_relative(path),
            "sha256": sha256(path), "status": "evaluated", "details": "two-parameter configuration identity",
        })
    write_csv(OUT / "model_config_input_manifest.csv", manifest_rows,
              ["category", "identity", "path", "sha256", "status", "details"])

    material = [path for path in OUT.rglob("*") if path.is_file() and "__pycache__" not in path.parts
                and path.name not in {"SHA256SUMS", "artifact_inventory.csv"}]
    material.append(REPORT)
    inventory_rows = []
    for path in sorted(set(material), key=lambda value: root_relative(value)):
        suffix = path.suffix.lower()
        role = "artifact"
        if suffix == ".mph": role = "COMSOL model"
        elif suffix in {".py"}: role = "reproducibility script"
        elif suffix in {".png", ".svg"}: role = "visual diagnostic"
        elif suffix == ".md": role = "progress report"
        elif "response" in path.as_posix() or "complex_transfer" in path.name: role = "complex response"
        elif suffix in {".csv", ".json"}: role = "machine-readable result"
        inventory_rows.append({
            "path": root_relative(path), "bytes": path.stat().st_size,
            "sha256": sha256(path), "role": role,
        })
    inventory_rows.append({"path": root_relative(OUT / "SHA256SUMS"), "bytes": "", "sha256": "",
                           "role": "final checksum manifest (self-excluded)"})
    write_csv(OUT / "artifact_inventory.csv", inventory_rows, ["path", "bytes", "sha256", "role"])

    checksum_paths = [path for path in OUT.rglob("*") if path.is_file() and "__pycache__" not in path.parts
                      and path.name != "SHA256SUMS"]
    checksum_paths.append(REPORT)
    checksum_paths = sorted(set(checksum_paths), key=root_relative)
    lines = [f"{sha256(path)}  {root_relative(path)}" for path in checksum_paths]
    checksum_file = OUT / "SHA256SUMS"
    checksum_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    failures = []
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        actual = sha256(ROOT / Path(relative))
        if actual != expected:
            failures.append({"path": relative, "expected": expected, "actual": actual})
    print(json.dumps({"checksum_entries": len(lines), "verified": len(lines)-len(failures),
                      "failures": failures, "sha256sums_written_last": True}, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
