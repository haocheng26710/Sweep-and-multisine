"""Mechanically validate and seal the additive E2-R package."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    json_files = sorted(ROOT.glob("*.json"))
    for path in json_files:
        with path.open("r", encoding="utf-8") as f:
            json.load(f)
    csv_counts = {}
    for path in sorted(ROOT.glob("*.csv")):
        with path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        csv_counts[path.name] = len(rows)
    assert csv_counts == {
        "candidate_metrics.csv": 160,
        "family_summary.csv": 8,
        "topology_associations_exploratory.csv": 12,
    }
    summary = json.loads((ROOT / "scientific_summary.json").read_text(encoding="utf-8"))
    integrity = json.loads((ROOT / "integrity_verification.json").read_text(encoding="utf-8"))
    assert summary["final_test_read"] is integrity["final_test_read"] is False
    assert integrity["status"] == "PASS" and integrity["identities"] == 80
    global_summary = summary["global_summary"]
    assert global_summary["global_terminal"] == "BOUNDED_COMPARATIVE_RESULT"
    assert global_summary["ranking"] == [
        "FIXED_SEED_RANDOM_DISORDERED",
        "PHYSICS_METAMATERIAL_INSPIRED",
        "NEAR_INDEPENDENT",
        "HAND_DESIGNED",
    ]
    assert global_summary["all_80_pass"] is global_summary["all_80_stable_rank_eligible"] is True
    assert global_summary["bridge24_pass"] == global_summary["held_out4_pass"] == 80
    report = (ROOT / "REPORT.md").read_text(encoding="utf-8")
    for token in (
        "final_test_read=false", "BOUNDED_COMPARATIVE_RESULT", "RANDOM_20", "PHYSICS_19",
        "NEAR_16", "HAND_11", "不能确认某类拓扑优于其他类", "没有启动打印、实测、E3、COMSOL",
    ):
        assert token in report
    for stem in ("validation_E_primary_by_family", "family_mechanism_descriptives", "development_validation_stability"):
        png = ROOT / f"{stem}.png"
        svg = ROOT / f"{stem}.svg"
        assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert "<svg" in svg.read_text(encoding="utf-8")[:1000]
    validation = {
        "schema_version": "gen_enc_2_e2_r_package_validation_v1",
        "status": "PASS",
        "final_test_read": False,
        "json_files_parsed": len(json_files),
        "csv_row_counts": csv_counts,
        "png_files_verified": 3,
        "svg_files_verified": 3,
        "mechanical_assertions": [
            "integrity status and 80 identities",
            "global terminal and exact ranking",
            "80/80 PASS and stable-rank eligibility",
            "80/80 bridge24 and held_out4",
            "report terminal/worst-member/scope tokens",
        ],
        "scope": "No response arrays, forward solve, W refit, COMSOL, final-test, E3, printing, or measurement.",
    }
    (ROOT / "validation_report.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    role_map = {
        "REPORT.md": "HUMAN_SCIENTIFIC_REPORT",
        "scientific_summary.json": "MACHINE_SCIENTIFIC_SUMMARY",
        "candidate_metrics.csv": "CANDIDATE_LEVEL_D_V_TABLE",
        "family_summary.csv": "FAMILY_PARTITION_SUMMARY",
        "topology_associations_exploratory.csv": "EXPLORATORY_TOPOLOGY_ASSOCIATIONS",
        "integrity_verification.json": "SOURCE_INTEGRITY_VERIFICATION",
        "validation_report.json": "MECHANICAL_PACKAGE_VALIDATION",
        "build_synthesis.py": "REPRODUCIBLE_READ_ONLY_SYNTHESIS_BUILDER",
        "finalize_and_verify.py": "PACKAGE_SEAL_AND_VERIFIER",
    }
    excluded = {"artifact_inventory.json", "SHA256SUMS.txt"}
    files = [p for p in sorted(ROOT.iterdir(), key=lambda p: p.name) if p.is_file() and p.name not in excluded]
    entries = []
    for path in files:
        if path.suffix == ".png":
            role = "FIGURE_PNG"
        elif path.suffix == ".svg":
            role = "FIGURE_SVG"
        else:
            role = role_map.get(path.name, "SUPPORTING_ARTIFACT")
        entries.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path), "role": role})
    inventory = {
        "schema_version": "gen_enc_2_e2_r_artifact_inventory_v1",
        "status": "COMPLETE",
        "final_test_read": False,
        "entry_count": len(entries),
        "entries": entries,
        "self_exclusions": ["artifact_inventory.json", "SHA256SUMS.txt"],
    }
    (ROOT / "artifact_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum_files = [p for p in sorted(ROOT.iterdir(), key=lambda p: p.name) if p.is_file() and p.name != "SHA256SUMS.txt"]
    lines = [f"{sha(path)}  {path.name}" for path in checksum_files]
    (ROOT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        expected, name = line.split("  ", 1)
        assert sha(ROOT / name) == expected
    print(json.dumps({"status": "PASS", "inventory_entries": len(entries), "checksum_entries": len(lines), "final_test_read": False}, sort_keys=True))


if __name__ == "__main__":
    main()
