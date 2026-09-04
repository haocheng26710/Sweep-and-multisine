"""RC03 verifier entry point with bounded Windows sharing-violation retry only."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_ORIGINAL_REPLACE = os.replace
_DELAYS_SECONDS = (0.05, 0.10, 0.20, 0.40, 0.80, 1.60, 1.60, 1.60)


def _replace_with_bounded_retry(source: object, destination: object) -> None:
    for attempt in range(len(_DELAYS_SECONDS) + 1):
        try:
            _ORIGINAL_REPLACE(source, destination)
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == len(_DELAYS_SECONDS):
                raise
            time.sleep(_DELAYS_SECONDS[attempt])


os.replace = _replace_with_bounded_retry

from scripts.gen_enc_2_e2_independent_verifier_rc03 import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
