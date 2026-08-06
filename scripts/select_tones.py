#!/usr/bin/env python
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.tone_selection_cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
