"""Create the complete source/CAD/report archive after validation."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PACKAGE_NAME = "Acoustic_Ladder_V1_0_full_package.zip"


def create_package(destination: Path | None = None):
    report = ROOT / "exports" / "reports" / "validation_report_v1.txt"
    if not report.exists() or "FAIL=0" not in report.read_text(encoding="utf-8"):
        raise RuntimeError("Validation must complete with FAIL=0 before packaging")
    destination = destination or ROOT / PACKAGE_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    excluded_dirs = {".venv", "__pycache__", ".git"}
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as archive:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if any(part in excluded_dirs for part in rel.parts):
                continue
            if path.suffix.lower() in {".pyc", ".zip"}:
                continue
            archive.write(path, rel.as_posix())
    return destination


def main():
    path = create_package()
    print(path)


if __name__ == "__main__":
    main()

