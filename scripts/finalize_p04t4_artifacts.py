from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize and verify P04T4 artifact inventory")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "outputs/real_experiment/research_analysis/"
            "P04T4_RETURN_CONTROL_CONFIRMATION_REV01"
        ),
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_dir():
        raise FileNotFoundError(output)

    for path in sorted(output.glob("*.json")):
        json.loads(path.read_text(encoding="utf-8"))
    for path in sorted(output.glob("*.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            list(csv.DictReader(handle))

    inventory_path = output / "artifact_inventory.json"
    targets = sorted(
        path for path in output.iterdir()
        if path.is_file() and path.name not in {"SHA256SUMS.txt", inventory_path.name}
    )
    inventory = {
        "schema_version": "p04t4_artifact_inventory_v1",
        "authority": "P04T4_RETURN_CONTROL_CONFIRMATION_REV01",
        "supersedes": "P04T4_RETURN_CONTROL_CONFIRMATION",
        "artifacts": [
            {
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in targets
        ],
        "final_test_read": False,
    }
    inventory_path.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    manifest_targets = sorted(
        path for path in output.iterdir()
        if path.is_file() and path.name != "SHA256SUMS.txt"
    )
    manifest = output / "SHA256SUMS.txt"
    with manifest.open("w", encoding="utf-8", newline="\n") as handle:
        for path in manifest_targets:
            handle.write(f"{sha256_file(path)}  {path.name}\n")

    lines = manifest.read_text(encoding="utf-8").splitlines()
    for line in lines:
        expected, name = line.split("  ", 1)
        actual = sha256_file(output / name)
        if actual != expected:
            raise RuntimeError(f"SHA mismatch after finalization: {name}")
    print(f"artifacts={len(manifest_targets)}")
    print(f"sha_verified={len(lines)}")
    print(f"output={output}")


if __name__ == "__main__":
    main()

