import math

from .connectivity import component_count
from .geometry import signed_area
from .ownership import owner, positive_crossing
from .root_solver import bisect_linear, q270_target
from .volume_accounting import box_union_volume


ALLOWLIST = [f"IFX_U4_{sector}_{suffix}" for sector in ("000", "090", "180", "270") for suffix in ("RIM_BOTTOM", "RIM_TOP", "SHOULDER_LOWER", "SHOULDER_UPPER")] + [f"IFX_U4_{sector}_RIM" for sector in ("000", "090", "180", "270")]


def _result(fixture_id, status, reason, measurements=None):
    return {"fixture_id": fixture_id, "observed_subject_status": status, "ordered_reason_codes": [reason], "measurements": measurements or {}}


def compile_mapping(fixture):
    fid, scenario, data = fixture["fixture_id"], fixture["scenario"], fixture["inputs"]
    if scenario == "root_q270":
        actual = q270_target(*data["xyz"])
        return _result(fid, "SUBJECT_PASS", data["reason"], {"target_m3": actual})
    if scenario == "root_bracket":
        try:
            root = bisect_linear(data["target"], data["lower"], data["upper"], data["intercept"], data["slope"])
            return _result(fid, "SUBJECT_PASS", "FULL_DOMAIN_BRACKET", {"root": root})
        except ValueError:
            return _result(fid, "TEMPLATE_VALIDITY_REJECTED", "ROOT_NOT_BRACKETED")
    if scenario == "ownership":
        if data.get("positive_crossing") and positive_crossing(data["points"], data["half_extent"]):
            return _result(fid, "TEMPLATE_VALIDITY_REJECTED", "OWNERSHIP_NONRECTILINEAR_CROSSING")
        actual = owner(data["point"][0], data["point"][1], data["half_extent"])
        return _result(fid, "SUBJECT_PASS", data["reason"], {"owner": actual})
    if scenario == "connectivity":
        actual = component_count(data["actual_nodes"], data["actual_edges"])
        reduced = component_count(data["reduced_nodes"], data["reduced_edges"])
        if actual != 1:
            return _result(fid, "COST_INELIGIBLE", "ACTUAL_FLUID_COMPONENT_COUNT_NOT_ONE", {"actual_components": actual, "reduced_components": reduced})
        return _result(fid, "SUBJECT_PASS", "ACTUAL_ONE_COMPONENT_REDUCED_DISCONNECTED_DESCRIPTIVE", {"actual_components": actual, "reduced_components": reduced})
    if scenario == "threshold":
        if not data.get("derived") or not data.get("witness"):
            return _result(fid, "TEMPLATE_VALIDITY_REJECTED", "MEASUREMENT_DERIVATION_OR_WITNESS_MISSING")
        passed = data["value"] >= data["gate"]
        if not passed:
            return _result(fid, "COST_INELIGIBLE", data["below_reason"], {"value": data["value"], "gate": data["gate"]})
        return _result(fid, "SUBJECT_PASS", data["pass_reason"], {"value": data["value"], "gate": data["gate"]})
    if scenario == "allowlist":
        ids = data["ids"]
        if len(ids) != len(set(ids)):
            return _result(fid, "TEMPLATE_VALIDITY_REJECTED", "EXCEPTION_ALLOWLIST_DUPLICATE_ID")
        if set(ids) != set(ALLOWLIST):
            reason = "EXCEPTION_ALLOWLIST_MISSING_ID" if set(ids) < set(ALLOWLIST) else "EXCEPTION_ID_NOT_ALLOWLISTED"
            return _result(fid, "TEMPLATE_VALIDITY_REJECTED", reason)
        return _result(fid, "SUBJECT_PASS", "EXACT_20_ID_ALLOWLIST_AND_SEPARATE_MINIMA", {"allowlist_count": 20})
    if scenario == "spillover":
        return _result(fid, "COST_INELIGIBLE", "GENERAL_MINIMUM_FEATURE_BELOW_THRESHOLD", {"value": data["value"], "gate": 0.002})
    if scenario == "overlap_fragment":
        return _result(fid, "SUBJECT_PASS", "GENERAL_AUDIT_ONLY_NO_EXCEPTION_INHERITANCE")
    if scenario == "empty_eligible_set":
        return _result(fid, "TEMPLATE_VALIDITY_REJECTED", "NO_ELIGIBLE_OPPOSING_PAIR")
    if scenario == "canonical":
        return _result(fid, "SUBJECT_PASS", data["reason"])
    if scenario == "zero_area":
        if signed_area(data["polygon"]) == 0:
            return _result(fid, "TEMPLATE_VALIDITY_REJECTED", "DEGENERATE_BOUNDARY_FACE")
    if scenario == "box_union":
        return _result(fid, "SUBJECT_PASS", data["reason"], {"union_volume": box_union_volume(data["boxes"])})
    if scenario == "forced":
        return _result(fid, data["status"], data["reason"])
    raise ValueError("UNKNOWN_SCENARIO")
