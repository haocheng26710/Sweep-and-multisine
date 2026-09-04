import hashlib
import json
import math


def _finite(value):
    if isinstance(value, float):
        if not math.isfinite(value) or (value == 0.0 and math.copysign(1.0, value) < 0):
            raise ValueError("NONFINITE_OR_NEGATIVE_ZERO")
    elif isinstance(value, list):
        for item in value:
            _finite(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("NON_STRING_KEY")
            _finite(item)


def canonical_json_bytes(value):
    _finite(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_lower_hex(data):
    return hashlib.sha256(data).hexdigest()
