"""Build the additive GEN-ENC-2 E2-R synthesis from sealed D/V JSON outputs only.

This script does not read response arrays, final-test assets, or refit W.  It
verifies the sealed terminals and summarizes already reconstructed output-contract
JSON files.  Derived ratios/correlations are explicitly descriptive/exploratory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median, pstdev

import matplotlib.pyplot as plt


REPO = Path(__file__).resolve().parents[4]
PACKAGE = Path(__file__).resolve().parent
BASE = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE"
D_ROOT = BASE / "e2_formal_d_checkpoint_observer_recovery_01_attempt03/development"
V_ROOT = BASE / "e2_formal_v_single_use_validation_01/single_use_validation"
IDENTITY_ROOT = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances"
OUTPUT_CONTRACT = BASE / "e2_preexecution_contract_freeze_02_rc_b_final/output_contract.json"

EXPECTED = {
    "d_terminal": "c90dec4278f8a88d2cbd117c6959e93587434ec3cad72a4a21f7a30ed7857678",
    "v_terminal": "fa3e10c46703534e97518bb9e15e5f00e0906fb17a822ab8873f158626e8630e",
    "common_w": "3ba1ec8926dcbd60f9b670bbcf3079426d54c93330427089fa4b8ade5a44bc04",
    "d_family": "d500258f12c4386ae5dc8f435a321c0c252eaf23574fb16c119f454d65ce3b88",
    "v_family": "9f27902bdf2026a432b09339014190dbf456500aff2595f76a223754c87d84ca",
}

FAMILIES = [
    ("HAND_DESIGNED", "HAND", "Hand-designed"),
    ("NEAR_INDEPENDENT", "NEAR", "Near-independent"),
    ("FIXED_SEED_RANDOM_DISORDERED", "RANDOM", "Random-disordered"),
    ("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS", "Physics-inspired"),
]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    lowered = path.as_posix().lower()
    assert "final-test" not in lowered and "final_test" not in lowered
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    assert isinstance(value, dict)
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        rank = (i + j - 1) / 2 + 1
        for k in range(i, j):
            result[order[k]] = rank
        i = j
    return result


def pearson(x: list[float], y: list[float]) -> float:
    mx, my = mean(x), mean(y)
    dx, dy = [v - mx for v in x], [v - my for v in y]
    den = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    return float("nan") if den == 0 else sum(a * b for a, b in zip(dx, dy)) / den


def spearman(x: list[float], y: list[float]) -> float:
    return pearson(ranks(x), ranks(y))


def topology_descriptor(family: str, params: dict) -> tuple[str, float]:
    if family == "HAND_DESIGNED":
        return "central_mix", float(params["central_mix"])
    if family == "NEAR_INDEPENDENT":
        return "shared_alpha", float(params["shared_alpha"])
    if family == "FIXED_SEED_RANDOM_DISORDERED":
        edges = [float(v) for k, v in params.items() if k.startswith("edge_")]
        return "mean_edge_strength", mean(edges)
    rings = [float(v) for k, v in params.items() if k.startswith("ring_")]
    return "mean_ring_coupling", mean(rings)


def verify_and_collect() -> tuple[list[dict], dict]:
    d_terminal_path = D_ROOT / "partition_terminal.json"
    v_terminal_path = V_ROOT / "partition_terminal.json"
    d_family_path = D_ROOT / "family_global_terminal.json"
    v_family_path = V_ROOT / "family_global_terminal.json"
    assert sha(d_terminal_path) == EXPECTED["d_terminal"]
    assert sha(v_terminal_path) == EXPECTED["v_terminal"]
    assert sha(d_family_path) == EXPECTED["d_family"]
    assert sha(v_family_path) == EXPECTED["v_family"]
    d_terminal, v_terminal = read_json(d_terminal_path), read_json(v_terminal_path)
    d_family, v_family = read_json(d_family_path), read_json(v_family_path)
    assert d_terminal["status"] == "E2_D_SEALED_INDEPENDENT_PASS"
    assert v_terminal["status"] == "E2_V_SINGLE_USE_TERMINAL"
    assert d_terminal["complete_identities"] == v_terminal["complete_identities"] == 80
    assert d_terminal["common_w_sha256"] == v_terminal["common_w_sha256"] == EXPECTED["common_w"]
    assert d_terminal["family_aggregate_sha256"] == EXPECTED["d_family"]
    assert v_terminal["family_global_terminal_sha256"] == EXPECTED["v_family"]
    assert v_terminal["development_seal_sha256"] == EXPECTED["d_terminal"]
    assert d_terminal["independent_verify_pass"] is v_terminal["independent_verify_pass"] is True
    assert d_terminal["validation_refit"] is v_terminal["validation_refit"] is False
    assert v_terminal["single_use_consumed"] is True
    assert d_terminal["final_test_read"] is v_terminal["final_test_read"] is False
    assert d_family["four_families_complete"] is v_family["four_families_complete"] is True
    assert d_family["ranking"] == [] and d_family["ranking_before_four_complete"] is False
    assert v_family["ranking_before_four_complete"] is False

    expected_ids: list[tuple[str, str]] = []
    for family, prefix, _ in FAMILIES:
        expected_ids += [(family, f"{prefix}_{i:02d}") for i in range(1, 21)]
        assert d_family["families"][family]["member_count"] == 20
        assert v_family["families"][family]["member_count"] == 20
    rows: list[dict] = []
    d_hashes: list[str] = []
    v_hashes: list[str] = []
    for family, identity in expected_ids:
        identity_path = IDENTITY_ROOT / family / f"{identity}.identity.json"
        ident = read_json(identity_path)
        assert ident["family_id"] == family and ident["member_id"] == identity
        descriptor_name, descriptor_value = topology_descriptor(family, ident["parameters"])
        for partition, root in (("development", D_ROOT), ("single_use_validation", V_ROOT)):
            out = root / "candidate_outputs" / identity
            terminal_path = root / "candidate_terminals" / f"{identity}.json"
            terminal = read_json(terminal_path)
            endpoint = read_json(out / "endpoint.json")
            shared = read_json(out / "shared_differential.json")
            matched = read_json(out / "matched_cost.json")
            throughput = read_json(out / "throughput.json")
            bridge = read_json(out / "bridge.json")
            held = read_json(out / "held_out.json")
            uncertainty = read_json(out / "resampling_uncertainty.json")
            assert terminal["identity_id"] == identity and terminal["family_id"] == family
            assert terminal["technical_status"] == terminal["scientific_status"] == "PASS"
            assert terminal["all_required_roles_consumed"] is True
            assert endpoint["primary_band"] == terminal["primary"]
            assert endpoint["unit_count"] == shared["unit_count"] == uncertainty["unit_count"] == 7350
            assert matched["eligible"] is True and all(matched["checks"].values())
            assert throughput["status"] == "AVAILABLE" and throughput["descriptive_only"] is True
            if partition == "development":
                assert bridge["status"] == held["status"] == "NOT_EVALUATED_DEVELOPMENT"
                d_hashes.append(sha(terminal_path))
            else:
                assert bridge["status"] == held["status"] == "PASS"
                assert all(bridge[k] for k in ("angular_order_pass", "derivative_orientation_pass", "differential_margin_pass", "circular_continuity_pass"))
                assert held["payload_matches_bridge"] is True
                v_hashes.append(sha(terminal_path))
            primary = endpoint["primary_band"]
            ratio = shared["differential_trace_mean"] / shared["shared_trace_mean"]
            row = {
                "partition": partition,
                "family_id": family,
                "identity_id": identity,
                "global_ordinal": ident["global_ordinal"],
                "topology_descriptor": descriptor_name,
                "topology_descriptor_value": descriptor_value,
                "E_primary": primary["E_primary"],
                "r_stable": primary["r_stable"],
                "stable_rank_eligible": primary["stable_rank_eligible"],
                "sigma1_q05": primary["sigma_quantiles_q05"][0],
                "sigma2_q05": primary["sigma_quantiles_q05"][1],
                "sigma3_q05": primary["sigma_quantiles_q05"][2],
                "shared_trace_mean": shared["shared_trace_mean"],
                "differential_trace_mean": shared["differential_trace_mean"],
                "differential_to_shared_ratio_exploratory": ratio,
                "matched_cost_eligible": matched["eligible"],
                "volume_m3": matched["inputs"]["volume_m3"],
                "dof": matched["inputs"]["dof"],
                "minimum_feature_m": matched["inputs"]["minimum_feature_m"],
                "solid_load_path_m": matched["inputs"]["solid_load_path_m"],
                "throughput_primary_208": throughput["primary"]["mean"],
                "throughput_secondary_256": throughput["secondary"]["mean"],
                "bridge24_status": bridge["status"],
                "held_out4_status": held["status"],
                "bootstrap_status": uncertainty["bootstrap"]["status"],
                "permutation_status": uncertainty["permutation"]["status"],
                "uncertainty_q025": uncertainty["uncertainty"]["empirical_q025"],
                "uncertainty_median": uncertainty["uncertainty"]["median"],
                "uncertainty_q975": uncertainty["uncertainty"]["empirical_q975"],
                "scientific_status": terminal["scientific_status"],
            }
            rows.append(row)
    assert d_hashes == d_terminal["candidate_decision_hashes"]
    v_concat = hashlib.sha256("".join(v_hashes).encode()).hexdigest()
    assert v_concat == v_terminal["candidate_terminals_sha256"]
    for family, _, _ in FAMILIES:
        d_actual = [sha(D_ROOT / "candidate_terminals" / f"{identity}.json") for fam, identity in expected_ids if fam == family]
        v_actual = [sha(V_ROOT / "candidate_terminals" / f"{identity}.json") for fam, identity in expected_ids if fam == family]
        assert d_actual == d_family["families"][family]["member_terminal_hashes"]
        assert v_actual == v_family["families"][family]["member_terminal_hashes"]
    integrity = {
        "status": "PASS",
        "final_test_read": False,
        "source_scope": "sealed terminal and candidate-output JSON only; no response arrays read; no W refit",
        "d_terminal_sha256": sha(d_terminal_path),
        "v_terminal_sha256": sha(v_terminal_path),
        "d_family_terminal_sha256": sha(d_family_path),
        "v_family_terminal_sha256": sha(v_family_path),
        "common_w_sha256": EXPECTED["common_w"],
        "identities": 80,
        "family_counts": {family: 20 for family, _, _ in FAMILIES},
        "candidate_rows": len(rows),
        "development": {"status": d_terminal["status"], "independent_verify_pass": True, "validation_opened": False},
        "validation": {"status": v_terminal["status"], "independent_verify_pass": True, "single_use_consumed": True, "validation_refit": False},
        "output_contract_sha256": sha(OUTPUT_CONTRACT),
    }
    return rows, {"integrity": integrity, "d_family": d_family, "v_family": v_family}


def summarize(rows: list[dict], terminals: dict) -> tuple[list[dict], list[dict], dict]:
    family_rows: list[dict] = []
    labels = {family: label for family, _, label in FAMILIES}
    for partition in ("development", "single_use_validation"):
        for family, _, _ in FAMILIES:
            subset = [r for r in rows if r["partition"] == partition and r["family_id"] == family]
            e = [r["E_primary"] for r in subset]
            ratio = [r["differential_to_shared_ratio_exploratory"] for r in subset]
            tp208 = [r["throughput_primary_208"] for r in subset]
            tp256 = [r["throughput_secondary_256"] for r in subset]
            family_rows.append({
                "partition": partition,
                "family_id": family,
                "member_count": len(subset),
                "pass_count": sum(r["scientific_status"] == "PASS" for r in subset),
                "stable_rank_eligible_count": sum(r["stable_rank_eligible"] for r in subset),
                "r_stable_min": min(r["r_stable"] for r in subset),
                "r_stable_max": max(r["r_stable"] for r in subset),
                "E_primary_min": min(e),
                "E_primary_median": median(e),
                "E_primary_mean": mean(e),
                "E_primary_max": max(e),
                "E_primary_sd_population": pstdev(e),
                "differential_to_shared_ratio_median_exploratory": median(ratio),
                "throughput_primary_208_median": median(tp208),
                "throughput_secondary_256_median": median(tp256),
                "bridge24_pass_count": sum(r["bridge24_status"] == "PASS" for r in subset),
                "held_out4_pass_count": sum(r["held_out4_status"] == "PASS" for r in subset),
                "matched_cost_eligible_count": sum(r["matched_cost_eligible"] for r in subset),
                "uncertainty_q025_median": median(r["uncertainty_q025"] for r in subset),
                "uncertainty_median_median": median(r["uncertainty_median"] for r in subset),
                "uncertainty_q975_median": median(r["uncertainty_q975"] for r in subset),
            })
    associations: list[dict] = []
    v_rows = [r for r in rows if r["partition"] == "single_use_validation"]
    for family, _, _ in FAMILIES:
        subset = [r for r in v_rows if r["family_id"] == family]
        x = [r["topology_descriptor_value"] for r in subset]
        for metric in ("E_primary", "differential_to_shared_ratio_exploratory", "throughput_primary_208"):
            y = [r[metric] for r in subset]
            associations.append({
                "family_id": family,
                "descriptor": subset[0]["topology_descriptor"],
                "outcome": metric,
                "n": len(subset),
                "pearson_r_exploratory": pearson(x, y),
                "spearman_rho_exploratory": spearman(x, y),
                "evidence_class": "EXPLORATORY_DESCRIPTIVE_NO_MULTIPLICITY_CLAIM",
            })
    paired = []
    for family, identity in [(f, f"{p}_{i:02d}") for f, p, _ in FAMILIES for i in range(1, 21)]:
        d = next(r for r in rows if r["partition"] == "development" and r["identity_id"] == identity)
        v = next(r for r in rows if r["partition"] == "single_use_validation" and r["identity_id"] == identity)
        paired.append(v["E_primary"] - d["E_primary"])
    v_e = [r["E_primary"] for r in v_rows]
    global_summary = {
        "global_terminal": terminals["v_family"]["global_status"],
        "ranking": terminals["v_family"]["ranking"],
        "all_80_pass": all(r["scientific_status"] == "PASS" for r in v_rows),
        "all_80_stable_rank_eligible": all(r["stable_rank_eligible"] for r in v_rows),
        "r_stable_range": [min(r["r_stable"] for r in v_rows), max(r["r_stable"] for r in v_rows)],
        "E_primary_validation_range": [min(v_e), max(v_e)],
        "E_primary_validation_relative_range_percent": (max(v_e) - min(v_e)) / median(v_e) * 100.0,
        "D_to_V_E_primary_delta": {
            "min": min(paired), "median": median(paired), "mean": mean(paired), "max": max(paired),
            "max_absolute": max(abs(x) for x in paired),
            "max_absolute_relative_percent": max(abs(x) for x in paired) / median(v_e) * 100.0,
        },
        "matched_cost": {
            "eligible": 80,
            "volume_m3": sorted(set(r["volume_m3"] for r in v_rows)),
            "dof_range": [min(r["dof"] for r in v_rows), max(r["dof"] for r in v_rows)],
            "minimum_feature_m": sorted(set(r["minimum_feature_m"] for r in v_rows)),
            "solid_load_path_m": sorted(set(r["solid_load_path_m"] for r in v_rows)),
        },
        "bridge24_pass": sum(r["bridge24_status"] == "PASS" for r in v_rows),
        "held_out4_pass": sum(r["held_out4_status"] == "PASS" for r in v_rows),
        "bootstrap_inputs": "80/80 SEALED_FINEST_UNIT_INPUT; CELL_REPEAT; frequency_resampling=false",
        "permutation_inputs": "80/80 SEALED_FINEST_UNIT_INPUT; CELL_REPEAT; frequency_permutation=false",
        "note": "No bootstrap or permutation inferential result is present in the frozen outputs; empirical q0.025/median/q0.975 are unit-value intervals, not confidence intervals for family contrasts.",
        "family_labels": labels,
    }
    return family_rows, associations, global_summary


def make_plots(rows: list[dict], family_summary: list[dict]) -> None:
    plt.rcParams.update({"font.size": 9, "figure.dpi": 150})
    colors = ["#3366cc", "#109618", "#ff9900", "#dc3912"]
    labels = [label for _, _, label in FAMILIES]
    v = [r for r in rows if r["partition"] == "single_use_validation"]
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    origin = min(r["E_primary"] for r in v)
    for i, ((family, _, _), color) in enumerate(zip(FAMILIES, colors)):
        values = [r["E_primary"] - origin for r in v if r["family_id"] == family]
        jitter = [i + ((j % 5) - 2) * 0.035 for j in range(len(values))]
        ax.scatter(jitter, values, s=18, alpha=.72, color=color)
        ax.hlines(median(values), i - .28, i + .28, color="black", lw=1.5)
    ax.set_xticks(range(4), labels, rotation=12, ha="right")
    ax.set_ylabel(f"Validation E_primary minus {origin:,.3f}")
    ax.set_title("All 80 candidates are stable-rank eligible; family separation is very small")
    ax.grid(axis="y", alpha=.25)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(PACKAGE / f"validation_E_primary_by_family.{ext}")
    plt.close(fig)

    fs = [r for r in family_summary if r["partition"] == "single_use_validation"]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2))
    axes[0].bar(labels, [r["differential_to_shared_ratio_median_exploratory"] for r in fs], color=colors)
    axes[0].set_ylabel("Median differential/shared trace ratio")
    axes[0].set_title("Exploratory contrast-energy balance")
    axes[1].bar(labels, [r["throughput_primary_208_median"] for r in fs], color=colors)
    axes[1].set_ylabel("Median throughput ratio (208 frequencies)")
    axes[1].set_title("Descriptive throughput")
    for ax in axes:
        ax.tick_params(axis="x", rotation=20)
        ax.grid(axis="y", alpha=.25)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(PACKAGE / f"family_mechanism_descriptives.{ext}")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.3, 5.0))
    d_map = {r["identity_id"]: r for r in rows if r["partition"] == "development"}
    for (family, _, label), color in zip(FAMILIES, colors):
        subset = [r for r in v if r["family_id"] == family]
        ax.scatter([d_map[r["identity_id"]]["E_primary"] for r in subset], [r["E_primary"] for r in subset], label=label, color=color, s=20)
    lo = min(r["E_primary"] for r in rows); hi = max(r["E_primary"] for r in rows)
    ax.plot([lo, hi], [lo, hi], "k--", lw=1)
    ax.set_xlabel("Development E_primary")
    ax.set_ylabel("Single-use validation E_primary")
    ax.set_title("D/V terminal stability under sealed common W")
    ax.legend(fontsize=7)
    ax.grid(alpha=.25)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(PACKAGE / f"development_validation_stability.{ext}")
    plt.close(fig)


def main() -> None:
    rows, terminals = verify_and_collect()
    family_rows, associations, global_summary = summarize(rows, terminals)
    write_csv(PACKAGE / "candidate_metrics.csv", rows)
    write_csv(PACKAGE / "family_summary.csv", family_rows)
    write_csv(PACKAGE / "topology_associations_exploratory.csv", associations)
    write_json(PACKAGE / "integrity_verification.json", terminals["integrity"])
    write_json(PACKAGE / "scientific_summary.json", {
        "schema_version": "gen_enc_2_e2_r_scientific_synthesis_v1",
        "evidence_class": "IDEALIZED_GEN_ENC_SEALED_D_V_COMPARATIVE_SYNTHESIS",
        "final_test_read": False,
        "integrity": terminals["integrity"],
        "development_family_terminal": terminals["d_family"],
        "validation_family_terminal": terminals["v_family"],
        "global_summary": global_summary,
        "family_summary": family_rows,
        "topology_associations": associations,
        "interpretation_guardrail": "Family ranking is contract-defined by exact-20 worst-member E_primary after all four families complete. Derived family medians, ratios, and correlations are descriptive/exploratory and do not replace that ranking.",
    })
    make_plots(rows, family_rows)
    print(json.dumps({"status": "PASS", "candidate_rows": len(rows), "family_rows": len(family_rows), "final_test_read": False}, sort_keys=True))


if __name__ == "__main__":
    main()
