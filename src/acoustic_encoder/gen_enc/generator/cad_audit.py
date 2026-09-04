"""Pure abstract CAD bisection and fail-closed audit."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

from .families import TECHNICAL_LABEL


def _result(status: str, **fields: Any) -> dict[str, Any]:
    return {"object_class": TECHNICAL_LABEL, "status": status, **fields}


def solve_cavity_length_bisection(
    monotone_abstract_volume_function: Callable[[float], float],
    lower: float,
    upper: float,
    target: float,
    tolerance_m3: float,
    max_iterations: int,
) -> dict[str, Any]:
    """Solve a monotone abstract volume root with the frozen tie rule."""

    if not 1 <= max_iterations <= 80 or tolerance_m3 <= 0.0:
        return _result("FAIL_INVALID_CONTROL")
    if not all(math.isfinite(value) for value in (lower, upper, target, tolerance_m3)):
        return _result("FAIL_NONFINITE")
    if not lower < upper:
        return _result("FAIL_INVALID_CONTROL")
    try:
        f_lower = monotone_abstract_volume_function(lower)
        f_upper = monotone_abstract_volume_function(upper)
    except Exception:
        return _result("FAIL_FUNCTION_ERROR")
    if not all(math.isfinite(value) for value in (f_lower, f_upper)):
        return _result("FAIL_NONFINITE")
    if f_lower > f_upper:
        return _result("FAIL_NONMONOTONE_ENDPOINTS")
    if target < f_lower or target > f_upper:
        return _result("FAIL_NO_BRACKETED_ROOT")
    if abs(f_lower - target) <= tolerance_m3:
        return _result("PASS", value=lower, iterations=0, residual_m3=abs(f_lower - target))

    lo = lower
    hi = upper
    for iteration in range(1, max_iterations + 1):
        midpoint = (lo + hi) / 2.0
        try:
            f_midpoint = monotone_abstract_volume_function(midpoint)
        except Exception:
            return _result("FAIL_FUNCTION_ERROR", iterations=iteration)
        if not math.isfinite(f_midpoint):
            return _result("FAIL_NONFINITE", iterations=iteration)
        residual = f_midpoint - target
        if abs(residual) <= tolerance_m3:
            return _result(
                "PASS",
                value=midpoint,
                iterations=iteration,
                residual_m3=abs(residual),
                tie_policy="LOWER_SIDE_EXACT_TIE",
            )
        if residual < 0.0:
            lo = midpoint
        else:
            hi = midpoint
    return _result("FAIL_MAX_ITERATIONS", iterations=max_iterations)


def audit_abstract_cad(cad_audit_payload: Mapping[str, Any], frozen_cost_interface: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the frozen fail-closed checks to an abstract CAD audit payload."""

    reasons: list[str] = []
    try:
        interval = frozen_cost_interface["matched_target_interval_m3"]
        caps = frozen_cost_interface["envelope_caps_m"]
        counts = frozen_cost_interface["counts"]
        identity = frozen_cost_interface["interface_identity"]
        interface_dimensions = frozen_cost_interface["interface_dimensions_m"]
        interface_tolerance = frozen_cost_interface["interface_tolerance_m"]
        min_feature = frozen_cost_interface["minimum_designed_feature_m"]
        min_load_path = frozen_cost_interface["minimum_solid_load_path_m"]
        volume = cad_audit_payload["connected_volume_m3"]
        envelope = cad_audit_payload["envelope_m"]
    except (KeyError, TypeError):
        return _result("COST_INELIGIBLE", eligible=False, retained=True, reasons=["MISSING_FIELD"])

    payload_dimensions = cad_audit_payload.get("interface_dimensions_m", {})
    numeric_values = [
        volume,
        *interval,
        *caps.values(),
        *envelope.values(),
        *interface_dimensions.values(),
        *payload_dimensions.values(),
        interface_tolerance,
        min_feature,
        min_load_path,
    ]
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in numeric_values):
        reasons.append("NONFINITE_OR_NONNUMERIC")
    else:
        if not interval[0] <= volume <= interval[1]:
            reasons.append("VOLUME_OUTSIDE_CLOSED_INTERVAL")
        for axis in ("x", "y", "z"):
            if envelope[axis] > caps[axis]:
                reasons.append(f"ENVELOPE_{axis.upper()}_CAP")
        if cad_audit_payload.get("minimum_feature_m", -math.inf) < min_feature:
            reasons.append("MINIMUM_FEATURE")
        if cad_audit_payload.get("minimum_solid_load_path_m", -math.inf) < min_load_path:
            reasons.append("SOLID_LOAD_PATH")

    if cad_audit_payload.get("connected_components") != 1:
        reasons.append("CONNECTED_COMPONENT_COUNT")
    if cad_audit_payload.get("counts") != counts:
        reasons.append("PORT_STATE_SENSOR_COUNTS")
    if cad_audit_payload.get("interface_identity") != identity:
        reasons.append("INTERFACE_IDENTITY")
    dimensions_numeric = all(
        isinstance(value, (int, float)) and math.isfinite(value)
        for value in payload_dimensions.values()
    )
    if (
        set(payload_dimensions) != set(interface_dimensions)
        or not dimensions_numeric
        or any(
            abs(payload_dimensions[name] - expected) > interface_tolerance
            for name, expected in interface_dimensions.items()
            if name in payload_dimensions and dimensions_numeric
        )
    ):
        reasons.append("INTERFACE_DIMENSIONS")

    return _result(
        "PASS" if not reasons else "COST_INELIGIBLE",
        eligible=not reasons,
        retained=True,
        reasons=reasons,
        redraw_count=0,
    )
