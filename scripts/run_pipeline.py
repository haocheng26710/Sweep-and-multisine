"""Unified pipeline entry point (DEV-A configuration gate only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.config import load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate and print the resolved configuration without analyzing data.",
    )
    arguments = parser.parse_args()
    config = load_config(arguments.config, default_path=PROJECT_ROOT / "config" / "default.yaml")
    print(json.dumps(config, indent=2, sort_keys=True, ensure_ascii=False))
    if not arguments.validate_only:
        print(
            "DEV-A gate: configuration is valid; P1-P6 execution is intentionally not implemented yet.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

