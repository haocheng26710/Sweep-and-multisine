"""Generate WRITE-2 dissertation figures and tables from frozen authorities."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acoustic_encoder.dissertation_assets import build_dissertation_assets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build frozen WRITE-2 thesis figures/tables without raw-data discovery."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    try:
        manifest = build_dissertation_assets(args.project_root)
    except Exception as exc:
        print(f"WRITE-2 failed closed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"figure_count={manifest['figure_count']}")
    print(f"figure_file_count={manifest['figure_file_count']}")
    print(f"table_count={manifest['table_count']}")
    print(f"table_file_count={manifest['table_file_count']}")
    print(f"disposition={manifest['disposition']}")
    print("scientifically_eligible=false")
    print("final_test_read=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
