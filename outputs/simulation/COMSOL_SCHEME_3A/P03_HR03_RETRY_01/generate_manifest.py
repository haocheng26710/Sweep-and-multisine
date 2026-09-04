"""Write the final non-recursive SHA-256 manifest for RETRY_01."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01"
REPORT = ROOT / "docs/progress/COMSOL_3A_P03_HR03_LOSS_MODEL_RETRY_01.md"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


files = sorted((p for p in OUT.iterdir() if p.is_file() and p.name != "SHA256SUMS"), key=lambda p: p.name.lower())
lines = [f"{digest(path)}  {path.name}" for path in files]
lines.append(f"{digest(REPORT)}  ../../../../docs/progress/{REPORT.name}")
(OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
