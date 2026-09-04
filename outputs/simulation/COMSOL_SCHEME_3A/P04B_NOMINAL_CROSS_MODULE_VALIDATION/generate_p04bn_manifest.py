"""Generate and verify the final P04B-N artifact inventory and SHA manifest."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT/"outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION"
REPORT = ROOT/"docs/progress/COMSOL_3A_P04B_NOMINAL_CROSS_MODULE_VALIDATION.md"
EXCLUDED = {"SHA256SUMS", "artifact_inventory.csv", "sha256_verification.json"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def role(path: Path) -> str:
    text = str(path).replace("\\", "/")
    if "superseded_rectangular_attempts" in text:
        return "superseded pre-geometry-gate execution evidence; excluded from scientific summary"
    if path.suffix.lower() == ".mph": return "auditable solved COMSOL model"
    if path.suffix.lower() == ".csv": return "numeric audit/result table"
    if path.suffix.lower() == ".json": return "machine-readable authority/audit/result"
    if path.suffix.lower() == ".png": return "visual result"
    if path.suffix.lower() == ".py": return "reproducibility script"
    if path.suffix.lower() == ".md": return "phase report"
    if path.suffix.lower() == ".log": return "solver/session log"
    return "supporting artifact"


def main() -> None:
    files = [path for path in OUT.rglob("*") if path.is_file() and path.name not in EXCLUDED
             and "__pycache__" not in path.parts and not path.name.endswith(".tmp")]
    files.append(REPORT)
    files = sorted(set(files), key=lambda item: str(item.relative_to(ROOT)).replace("\\", "/"))
    rows = [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size,
             "sha256": digest(path), "role": role(path)} for path in files]
    with (OUT/"artifact_inventory.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    manifest_files = files+[OUT/"artifact_inventory.csv"]
    entries = [(digest(path), str(path.relative_to(ROOT)).replace("\\", "/")) for path in manifest_files]
    (OUT/"SHA256SUMS").write_text("".join(f"{sha}  {name}\n" for sha, name in entries), encoding="utf-8")
    failures = []
    for expected, name in entries:
        actual = digest(ROOT/name)
        if actual != expected:
            failures.append({"path": name, "expected": expected, "actual": actual})
    verification = {"phase_id": "P04B-NOMINAL_AS_DESIGNED_CROSS_MODULE_VALIDATION",
        "entries": len(entries), "all_hashes_match": not failures, "failures": failures,
        "manifest_self_excluded": True, "verification_file_self_excluded": True, "final_test_read": False}
    (OUT/"sha256_verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    if failures:
        raise RuntimeError(f"SHA verification failed: {failures}")
    print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()
