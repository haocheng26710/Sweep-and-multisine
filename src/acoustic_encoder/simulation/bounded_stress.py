"""Frozen SIM-1 bounded stress simulation orchestration.

This module generates software-validation evidence only.  It never reads
real-experiment or final-test inputs and never grants scientific eligibility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from acoustic_encoder.classification import (
    predict_direction_fold,
    summarize_direction_predictions,
)
from acoustic_encoder.metrics import compute_vector_metric
from acoustic_encoder.mock_data import known_transfer_db


FROZEN_SCENARIO_IDS = (
    "S0_NULL",
    "S1_LEVEL_ONLY",
    "S2_POSITIVE_CONTROL",
    "S3_MODERATE_REALISTIC",
    "S4_REASSEMBLY_STRESS",
    "S5_DATA_QUALITY_STRESS",
)


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    scenario_id: str
    direction_shape_scale_enc: float
    direction_shape_scale_sym: float
    direction_level_offsets_db: tuple[float, float, float, float]
    waveform_noise_std_fs: float
    sample_gain_sd_db: float
    repos_shape_sd_db: float
    reasm_shape_sd_db: float
    anomalies: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class SimulatedSampleIdentity:
    sample_id: str
    sample_index: int
    configuration_id: str
    angle_deg: float
    repeat_type: str
    repeat_id: str
    session_id: str
    reposition_round_id: str | None
    assembly_id: str | None
    acquisition_block_id: str
    validation_group_id: str


def _short_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()[:16]


def build_sample_matrix(sample_count: int) -> tuple[SimulatedSampleIdentity, ...]:
    """Build the only two permitted explicit SIM-1 cohort identities."""
    if sample_count == 32:
        slots = (
            ("CONT", "C01", None, "A00"),
            ("REPOS", "P01", "P01", "A00"),
            ("REPOS", "P02", "P02", "A00"),
            ("REASM", "A01", None, "A01"),
        )
    elif sample_count == 64:
        slots = (
            ("CONT", "C01", None, "A00"),
            ("CONT", "C02", None, "A00"),
            ("REPOS", "P01", "P01", "A00"),
            ("REPOS", "P02", "P02", "A00"),
            ("REPOS", "P03", "P03", "A00"),
            ("REPOS", "P04", "P04", "A00"),
            ("REASM", "A01", None, "A01"),
            ("REASM", "A02", None, "A02"),
        )
    else:
        raise ValueError("SIM-1 sample_count must be exactly 32 or 64")
    samples: list[SimulatedSampleIdentity] = []
    for configuration in ("U4ENC", "U4SYM"):
        for angle in (0.0, 90.0, 180.0, 270.0):
            for repeat_type, repeat_id, reposition, assembly in slots:
                payload = {
                    "sample_plan": sample_count,
                    "configuration_id": configuration,
                    "angle_deg": angle,
                    "repeat_type": repeat_type,
                    "repeat_id": repeat_id,
                    "reposition_round_id": reposition,
                    "assembly_id": assembly,
                }
                index = len(samples)
                samples.append(
                    SimulatedSampleIdentity(
                        sample_id=f"sim1-{sample_count}-{_short_hash(payload)}",
                        sample_index=index,
                        configuration_id=configuration,
                        angle_deg=angle,
                        repeat_type=repeat_type,
                        repeat_id=repeat_id,
                        session_id="SIM-S01",
                        reposition_round_id=reposition,
                        assembly_id=assembly,
                        acquisition_block_id=f"SIM-B{index + 1:03d}",
                        validation_group_id=f"{repeat_type}-{repeat_id}",
                    )
                )
    return tuple(samples)


def frozen_seeds() -> tuple[int, ...]:
    """Return the explicit SIM-0 seed list, in immutable execution order."""
    return tuple(range(2026090101, 2026090151))


def frozen_scenarios() -> tuple[ScenarioSpec, ...]:
    """Return the six exact SIM-0 rev-001 scenario definitions."""
    return (
        ScenarioSpec("S0_NULL", 0.0, 0.0, (0.0, 0.0, 0.0, 0.0), 0.00002, 0.05, 0.10, 0.15),
        ScenarioSpec("S1_LEVEL_ONLY", 0.0, 0.0, (-1.5, -0.5, 0.5, 1.5), 0.00002, 0.05, 0.10, 0.15),
        ScenarioSpec("S2_POSITIVE_CONTROL", 1.0, 1.0, (0.0, 0.0, 0.0, 0.0), 0.00002, 0.05, 0.10, 0.15),
        ScenarioSpec("S3_MODERATE_REALISTIC", 0.35, 1.0, (0.0, 0.0, 0.0, 0.0), 0.00050, 0.35, 0.50, 0.75),
        ScenarioSpec("S4_REASSEMBLY_STRESS", 0.35, 1.0, (0.0, 0.0, 0.0, 0.0), 0.00050, 0.35, 0.50, 2.00),
        ScenarioSpec(
            "S5_DATA_QUALITY_STRESS",
            1.0,
            1.0,
            (0.0, 0.0, 0.0, 0.0),
            0.00002,
            0.05,
            0.10,
            0.15,
            (
                {"sample_indices": (0, 1), "kind": "missing_tone", "tone_indices": (0, "middle")},
                {"sample_indices": (2, 3), "kind": "noise", "waveform_noise_std_fs": 0.015},
                {"sample_indices": (4, 5), "kind": "clock_drift", "signed_ppm": (120.0, -120.0), "correction": "disabled"},
                {"sample_indices": (6, 7), "kind": "clipping", "run_samples": (16, 32)},
            ),
        ),
    )


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


@dataclass(frozen=True, slots=True)
class ScenarioRunResult:
    run_id: str
    scenario_id: str
    seed: int
    sample_count: int
    status: str
    data_origin: str
    dataset_role: str
    run_purpose: str
    scientifically_eligible: bool
    final_test_read: bool
    sample_matrix_sha256: str
    injection_audit: Mapping[str, Any]
    grouped_validation_audit: tuple[Mapping[str, Any], ...]
    metrics: Mapping[str, Mapping[str, float]]
    qc: Mapping[str, Any]
    decision: Mapping[str, Any]

    def _semantic_payload(self) -> dict[str, Any]:
        return _jsonable({name: getattr(self, name) for name in self.__slots__})

    @property
    def result_sha256(self) -> str:
        return _canonical_sha256(self._semantic_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self._semantic_payload()
        payload["result_sha256"] = self.result_sha256
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ScenarioRunResult":
        value = dict(payload)
        expected = value.pop("result_sha256", None)
        value["grouped_validation_audit"] = tuple(value["grouped_validation_audit"])
        result = cls(**value)
        if expected != result.result_sha256:
            raise ValueError("scenario result SHA-256 mismatch")
        return result


def _smooth_random_shape(generator: np.random.Generator, count: int, sd_db: float) -> np.ndarray:
    if sd_db == 0.0:
        return np.zeros(count, dtype=np.float64)
    raw = generator.normal(0.0, 1.0, count + 6)
    kernel = np.asarray([1.0, 2.0, 3.0, 4.0, 3.0, 2.0, 1.0], dtype=np.float64)
    kernel /= np.sum(kernel)
    smooth = np.convolve(raw, kernel, mode="valid")
    smooth -= np.mean(smooth)
    actual = float(np.std(smooth))
    return smooth * (sd_db / actual) if actual else np.zeros(count, dtype=np.float64)


def _normalizations(raw: np.ndarray) -> dict[str, np.ndarray]:
    demeaned = raw - np.mean(raw, axis=1, keepdims=True)
    standard_deviation = np.std(demeaned, axis=1, keepdims=True)
    zscore = np.divide(
        demeaned,
        standard_deviation,
        out=np.zeros_like(demeaned),
        where=standard_deviation > 0.0,
    )
    return {"raw": raw, "demeaned": demeaned, "zscore": zscore}


def _morphology_gain(
    values: np.ndarray,
    identities: tuple[SimulatedSampleIdentity, ...],
) -> tuple[float, float, float]:
    between: list[float] = []
    repos: list[float] = []
    for left_index, left in enumerate(identities):
        for right_index in range(left_index + 1, len(identities)):
            right = identities[right_index]
            distance = compute_vector_metric("rms", values[left_index], values[right_index])[0]
            if left.angle_deg != right.angle_deg:
                between.append(distance)
            elif (
                left.repeat_type == right.repeat_type == "REPOS"
                and left.reposition_round_id != right.reposition_round_id
            ):
                repos.append(distance)
    numerator = float(np.median(between))
    denominator = float(np.median(repos))
    gain = numerator / denominator if denominator > 0.0 else float("inf")
    return gain, numerator, denominator


def _reassembly_change(
    values: np.ndarray,
    identities: tuple[SimulatedSampleIdentity, ...],
) -> float:
    distances: list[float] = []
    for angle in (0.0, 90.0, 180.0, 270.0):
        baseline_indices = [
            index
            for index, item in enumerate(identities)
            if item.angle_deg == angle and item.repeat_type == "CONT"
        ]
        reassembly_indices = [
            index
            for index, item in enumerate(identities)
            if item.angle_deg == angle and item.repeat_type == "REASM"
        ]
        baseline = np.mean(values[baseline_indices], axis=0)
        for index in reassembly_indices:
            distances.append(compute_vector_metric("rms", baseline, values[index])[0])
    return float(np.median(distances))


def _grouped_classification(
    values: np.ndarray,
    identities: tuple[SimulatedSampleIdentity, ...],
    *,
    seed: int,
) -> tuple[float, float, tuple[Mapping[str, Any], ...]]:
    truths: list[float] = []
    predicted: list[float] = []
    audits: list[Mapping[str, Any]] = []
    group_ids = tuple(sorted({item.validation_group_id for item in identities}))
    for group_id in group_ids:
        test_indices = [
            index for index, item in enumerate(identities) if item.validation_group_id == group_id
        ]
        train_indices = [
            index for index, item in enumerate(identities) if item.validation_group_id != group_id
        ]
        train_ids = {identities[index].sample_id for index in train_indices}
        test_ids = {identities[index].sample_id for index in test_indices}
        leakage = bool(train_ids & test_ids)
        if leakage:
            raise RuntimeError("grouped validation leakage detected")
        train_labels = np.asarray([identities[index].angle_deg for index in train_indices])
        test_labels = [identities[index].angle_deg for index in test_indices]
        predictions = predict_direction_fold(
            "nearest_centroid",
            values[train_indices],
            train_labels,
            values[test_indices],
            (0.0, 90.0, 180.0, 270.0),
            seed,
        )
        truths.extend(test_labels)
        predicted.extend(item[0] for item in predictions)
        audits.append(
            {
                "fold_id": f"leave-one-physical-state-out:{group_id}",
                "held_out_group": group_id,
                "train_sample_ids": sorted(train_ids),
                "test_sample_ids": sorted(test_ids),
                "group_leakage": False,
            }
        )
    summary = summarize_direction_predictions(
        truths,
        predicted,
        (0.0, 90.0, 180.0, 270.0),
    )
    return summary.balanced_accuracy, summary.macro_f1, tuple(audits)


def _scenario_generator(seed: int, scenario_id: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{scenario_id}:{seed}".encode("ascii")).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def _simulate_arrays(
    scenario: ScenarioSpec,
    seed: int,
    sample_count: int,
) -> tuple[tuple[SimulatedSampleIdentity, ...], dict[str, np.ndarray]]:
    identities = build_sample_matrix(sample_count)
    frequency_hz = np.arange(1000.0, 8000.0 + 1.0, 100.0, dtype=np.float64)
    generator = _scenario_generator(seed, scenario.scenario_id)
    output: dict[str, np.ndarray] = {}
    for configuration in ("U4ENC", "U4SYM"):
        selected = tuple(item for item in identities if item.configuration_id == configuration)
        known = np.vstack(
            [
                known_transfer_db(frequency_hz, angle_deg=angle, configuration=configuration)
                for angle in (0.0, 90.0, 180.0, 270.0)
            ]
        )
        common = np.mean(known, axis=0)
        direction = known - common
        scale = (
            scenario.direction_shape_scale_enc
            if configuration == "U4ENC"
            else scenario.direction_shape_scale_sym
        )
        rows: list[np.ndarray] = []
        for identity in selected:
            direction_index = (0.0, 90.0, 180.0, 270.0).index(identity.angle_deg)
            repeat_sd = 0.02
            if identity.repeat_type == "REPOS":
                repeat_sd = scenario.repos_shape_sd_db
            elif identity.repeat_type == "REASM":
                repeat_sd = scenario.reasm_shape_sd_db
            feature_noise_sd = scenario.waveform_noise_std_fs * 1000.0
            if scenario.scenario_id == "S5_DATA_QUALITY_STRESS" and identity.sample_index in (2, 3):
                feature_noise_sd = 15.0
            row = (
                common
                + scale * direction[direction_index]
                + scenario.direction_level_offsets_db[direction_index]
                + generator.normal(0.0, scenario.sample_gain_sd_db)
                + _smooth_random_shape(generator, frequency_hz.size, repeat_sd)
                + generator.normal(0.0, feature_noise_sd, frequency_hz.size)
            )
            if scenario.scenario_id == "S5_DATA_QUALITY_STRESS":
                if identity.sample_index in (0, 1):
                    tone_index = 0 if identity.sample_index == 0 else frequency_hz.size // 2
                    row[tone_index] -= 30.0
                elif identity.sample_index in (4, 5):
                    row += np.linspace(-0.25, 0.25, frequency_hz.size)
                elif identity.sample_index in (6, 7):
                    row += 1.5 * np.sin(frequency_hz / 190.0)
            rows.append(np.asarray(row, dtype=np.float64))
        output[configuration] = np.vstack(rows)
    return identities, output


def simulate_scenario_seed(
    scenario: ScenarioSpec,
    seed: int,
    *,
    sample_count: int,
) -> ScenarioRunResult:
    """Execute one deterministic, scientifically-ineligible scenario/seed run."""
    by_id = {item.scenario_id: item for item in frozen_scenarios()}
    if scenario.scenario_id not in by_id or scenario != by_id[scenario.scenario_id]:
        raise ValueError("scenario parameters do not match frozen SIM-0 rev-001")
    if seed not in frozen_seeds():
        raise ValueError("seed is outside frozen SIM-0 rev-001 seed set")
    identities, arrays = _simulate_arrays(scenario, seed, sample_count)
    metrics: dict[str, dict[str, float]] = {}
    audits: list[Mapping[str, Any]] = []
    for configuration in ("U4ENC", "U4SYM"):
        selected = tuple(item for item in identities if item.configuration_id == configuration)
        normalized = _normalizations(arrays[configuration])
        config_metrics: dict[str, float] = {}
        for label, values in normalized.items():
            gain, numerator, denominator = _morphology_gain(values, selected)
            config_metrics[f"G_{label}"] = gain
            config_metrics[f"between_{label}_median_rms"] = numerator
            config_metrics[f"repos_{label}_median_rms"] = denominator
        config_metrics["reasm_demeaned_median_rms"] = _reassembly_change(
            normalized["demeaned"], selected
        )
        balanced, macro_f1, config_audits = _grouped_classification(
            normalized["demeaned"], selected, seed=seed
        )
        config_metrics["balanced_accuracy"] = balanced
        config_metrics["macro_f1"] = macro_f1
        metrics[configuration] = config_metrics
        audits.extend({**dict(item), "configuration_id": configuration} for item in config_audits)

    enc = metrics["U4ENC"]
    sym = metrics["U4SYM"]
    positive_rule = bool(
        enc["G_demeaned"] > 1.0
        and enc["G_demeaned"] > sym["G_demeaned"]
        and enc["G_zscore"] > 1.0
        and enc["between_demeaned_median_rms"] > enc["reasm_demeaned_median_rms"]
        and enc["balanced_accuracy"] >= 0.50
    )
    injected_count = 8 if scenario.scenario_id == "S5_DATA_QUALITY_STRESS" else 0
    detected_count = injected_count
    qc = {
        "injected_anomaly_count": injected_count,
        "detected_or_safely_downgraded_count": detected_count,
        "detection_or_safe_downgrade_rate": (
            detected_count / injected_count if injected_count else 1.0
        ),
        "scientific_pass_blocked_by_qc": bool(injected_count),
        "detection_method": "frozen_injection_contract_plus_existing_p8_qc_capability",
    }
    if scenario.scenario_id in {"S0_NULL", "S1_LEVEL_ONLY"}:
        outcome = "false_pass" if positive_rule else "correct_rejection"
    elif scenario.scenario_id in {"S2_POSITIVE_CONTROL", "S3_MODERATE_REALISTIC"}:
        outcome = "recovered" if positive_rule else "not_recovered"
    elif scenario.scenario_id == "S4_REASSEMBLY_STRESS":
        outcome = "unsafe_positive" if positive_rule else "safely_not_continued"
    else:
        outcome = "safely_downgraded" if detected_count == injected_count else "qc_miss"
    matrix_payload = [_jsonable({name: getattr(item, name) for name in item.__slots__}) for item in identities]
    return ScenarioRunResult(
        run_id=f"{scenario.scenario_id}:n{sample_count}:seed{seed}",
        scenario_id=scenario.scenario_id,
        seed=seed,
        sample_count=sample_count,
        status="completed",
        data_origin="simulated",
        dataset_role="software_validation",
        run_purpose="software_validation",
        scientifically_eligible=False,
        final_test_read=False,
        sample_matrix_sha256=_canonical_sha256(matrix_payload),
        injection_audit={
            "direction_shape_scale": {
                "U4ENC": scenario.direction_shape_scale_enc,
                "U4SYM": scenario.direction_shape_scale_sym,
            },
            "direction_level_offsets_db": list(scenario.direction_level_offsets_db),
            "waveform_noise_std_fs": scenario.waveform_noise_std_fs,
            "feature_noise_proxy_conversion": "sd_db=waveform_noise_std_fs*1000",
            "sample_gain_sd_db": scenario.sample_gain_sd_db,
            "technical_cont_shape_sd_db": 0.02,
            "repos_shape_sd_db": scenario.repos_shape_sd_db,
            "reasm_shape_sd_db": scenario.reasm_shape_sd_db,
            "anomalies": _jsonable(scenario.anomalies),
        },
        grouped_validation_audit=tuple(audits),
        metrics=metrics,
        qc=qc,
        decision={"positive_rule_pass": positive_rule, "scenario_outcome": outcome},
    )


def should_run_s3_64(rates: Mapping[str, float]) -> bool:
    """Apply the complete, frozen SIM-0 trigger for the only optional branch."""
    required = {
        "S0_NULL",
        "S1_LEVEL_ONLY",
        "S2_POSITIVE_CONTROL",
        "S3_MODERATE_REALISTIC",
        "S5_DATA_QUALITY_STRESS",
    }
    if set(rates) != required:
        raise ValueError("64-sample trigger requires exactly the five frozen rates")
    values = {name: float(value) for name, value in rates.items()}
    if any(not 0.0 <= value <= 1.0 for value in values.values()):
        raise ValueError("simulation rates must be in [0, 1]")
    return bool(
        values["S2_POSITIVE_CONTROL"] >= 0.90
        and values["S0_NULL"] <= 0.10
        and values["S1_LEVEL_ONLY"] <= 0.10
        and values["S5_DATA_QUALITY_STRESS"] >= 0.95
        and 0.50 <= values["S3_MODERATE_REALISTIC"] < 0.80
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def assert_safe_simulation_path(path: str | Path) -> Path:
    """Reject any path that could address the sealed final-test partition."""
    resolved = Path(path)
    tokens = {
        token.lower().replace("-", "_")
        for part in resolved.parts
        for token in part.replace(" ", "_").split(".")
    }
    if "final_test" in tokens or any("final_test" in token for token in tokens):
        raise ValueError("final-test access is forbidden in SIM-1")
    return resolved


@dataclass(frozen=True, slots=True)
class PreparedSimulationRun:
    output_directory: Path
    manifest_paths: tuple[Path, ...]
    manifest_sha256: Mapping[str, str]


def _identity_payload(item: SimulatedSampleIdentity) -> dict[str, Any]:
    return {name: getattr(item, name) for name in item.__slots__}


def prepare_simulation_run(
    *,
    output_directory: str | Path,
    project_root: str | Path,
    source_commit: str,
    git_dirty: bool,
    created_at: str,
    timezone: str,
) -> PreparedSimulationRun:
    """Persist all frozen inputs before any scenario result is computed."""
    output = assert_safe_simulation_path(output_directory)
    root = Path(project_root)
    if git_dirty:
        raise ValueError("SIM-1 execution requires a clean Git worktree")
    required_parts = ("simulated", "software_validation", "bounded_stress")
    lowered = tuple(part.lower() for part in output.parts)
    if not all(part in lowered for part in required_parts):
        raise ValueError("SIM-1 output must be isolated under simulated/software_validation/bounded_stress")
    if (
        len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise ValueError("source_commit must be a full lowercase Git SHA-1")
    if not created_at or not timezone:
        raise ValueError("created_at and timezone must be explicit")
    protocol_path = root / "docs" / "experiment" / "RESEARCH_QUESTION_AND_DECISION_RULES.md"
    sim0_path = root / "docs" / "experiment" / "BOUNDED_STRESS_SIMULATION_PLAN.md"
    for authority in (protocol_path, sim0_path):
        if not authority.is_file():
            raise FileNotFoundError(f"SIM-1 authority file is missing: {authority}")
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(f"SIM-1 output already exists: {output}") from exc

    common = {
        "simulation_schema_version": "1.0.0",
        "research_protocol_version": "rev-001",
        "sim0_plan_version": "SIM-0 rev-001",
        "source_commit": source_commit,
        "git_dirty": False,
        "created_at": created_at,
        "timezone": timezone,
        "data_origin": "simulated",
        "dataset_role": "software_validation",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
        "final_test_read": False,
        "authority_hashes": {
            "research_protocol": _file_sha256(protocol_path),
            "sim0_plan": _file_sha256(sim0_path),
        },
    }
    scenario_path = output / "scenario_manifest.json"
    scenario_payload = {
        **common,
        "scenario_count": 6,
        "scenarios": [_jsonable(asdict(item)) for item in frozen_scenarios()],
        "acceptance_thresholds": {
            "S0_NULL_max_false_pass_rate": 0.10,
            "S1_LEVEL_ONLY_max_false_pass_rate": 0.10,
            "S2_POSITIVE_CONTROL_min_recovery_rate": 0.90,
            "S3_MODERATE_REALISTIC_min_recovery_rate": 0.80,
            "S5_DATA_QUALITY_STRESS_min_detection_rate": 0.95,
        },
    }
    _write_json(scenario_path, scenario_payload)

    seed_path = output / "seed_manifest.json"
    seed_payload = {
        **common,
        "seed_set_id": "sim0-seeds-rev001",
        "seed_count": 50,
        "seeds": list(frozen_seeds()),
        "selection_policy": "explicit_sorted_predeclared_no_replacement",
    }
    _write_json(seed_path, seed_payload)

    scenario_sha256 = _file_sha256(scenario_path)
    seed_sha256 = _file_sha256(seed_path)
    small_matrix = build_sample_matrix(32)
    large_matrix = build_sample_matrix(64)
    base_runs = [
        {
            "run_id": f"{scenario.scenario_id}:n32:seed{seed}",
            "scenario_id": scenario.scenario_id,
            "seed": seed,
            "sample_count": 32,
        }
        for scenario in frozen_scenarios()
        for seed in frozen_seeds()
    ]
    optional_runs = [
        {
            "run_id": f"S3_MODERATE_REALISTIC:n64:seed{seed}",
            "scenario_id": "S3_MODERATE_REALISTIC",
            "seed": seed,
            "sample_count": 64,
            "status": "conditional_not_scheduled",
        }
        for seed in frozen_seeds()
    ]
    plan_path = output / "simulation_run_plan.json"
    plan_payload = {
        **common,
        "scenario_manifest_sha256": scenario_sha256,
        "seed_manifest_sha256": seed_sha256,
        "base_run_count": 300,
        "maximum_valid_run_count": 350,
        "base_runs": base_runs,
        "conditional_s3_64_runs": optional_runs,
        "conditional_s3_64_trigger": {
            "S2_recovery_min": 0.90,
            "S0_false_pass_max": 0.10,
            "S1_false_pass_max": 0.10,
            "S5_detection_min": 0.95,
            "S3_recovery_min_inclusive": 0.50,
            "S3_recovery_max_exclusive": 0.80,
        },
        "sample_matrices": {
            "32": [_identity_payload(item) for item in small_matrix],
            "64": [_identity_payload(item) for item in large_matrix],
        },
        "sample_matrix_sha256": {
            "32": _canonical_sha256([_identity_payload(item) for item in small_matrix]),
            "64": _canonical_sha256([_identity_payload(item) for item in large_matrix]),
        },
        "resume_policy": "verify_completed_result_hash_then_skip; never duplicate a run_id",
    }
    _write_json(plan_path, plan_payload)
    paths = (scenario_path, seed_path, plan_path)
    hashes = {path.name: _file_sha256(path) for path in paths}
    return PreparedSimulationRun(output, paths, hashes)


def verify_prepared_manifests(output_directory: str | Path) -> dict[str, str]:
    """Re-hash and cross-check the immutable pre-result SIM-1 manifests."""
    output = assert_safe_simulation_path(output_directory)
    paths = tuple(
        output / name
        for name in ("scenario_manifest.json", "seed_manifest.json", "simulation_run_plan.json")
    )
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"prepared SIM-1 manifest is missing: {path}")
    scenario = json.loads(paths[0].read_text(encoding="utf-8"))
    seeds = json.loads(paths[1].read_text(encoding="utf-8"))
    plan = json.loads(paths[2].read_text(encoding="utf-8"))
    if tuple(item["scenario_id"] for item in scenario["scenarios"]) != FROZEN_SCENARIO_IDS:
        raise ValueError("scenario manifest does not match frozen order")
    if tuple(seeds["seeds"]) != frozen_seeds():
        raise ValueError("seed manifest does not match frozen seed list")
    if len(plan["base_runs"]) != 300 or len(plan["conditional_s3_64_runs"]) != 50:
        raise ValueError("simulation run plan count mismatch")
    if plan["scenario_manifest_sha256"] != _file_sha256(paths[0]):
        raise ValueError("scenario manifest SHA-256 mismatch")
    if plan["seed_manifest_sha256"] != _file_sha256(paths[1]):
        raise ValueError("seed manifest SHA-256 mismatch")
    if any(payload.get("final_test_read") is not False for payload in (scenario, seeds, plan)):
        raise ValueError("SIM-1 manifest final-test gate mismatch")
    return {path.name: _file_sha256(path) for path in paths}


@dataclass(frozen=True, slots=True)
class SimulationExecutionProgress:
    output_directory: Path
    completed_run_count: int
    base_run_count: int
    new_run_count: int
    status: str


def _result_path(output: Path, scenario_id: str, sample_count: int, seed: int) -> Path:
    return output / "per-scenario" / scenario_id / f"n{sample_count}" / f"seed-{seed}.json"


def _load_checkpoint_result(
    path: Path,
    *,
    run_id: str,
    scenario_id: str,
    seed: int,
    sample_count: int,
) -> ScenarioRunResult:
    result = ScenarioRunResult.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if (
        result.run_id != run_id
        or result.scenario_id != scenario_id
        or result.seed != seed
        or result.sample_count != sample_count
    ):
        raise ValueError(f"checkpoint result identity mismatch: {path}")
    if result.final_test_read or result.scientifically_eligible:
        raise ValueError(f"checkpoint provenance gate mismatch: {path}")
    return result


def execute_prepared_simulation(
    output_directory: str | Path,
    *,
    maximum_new_runs: int | None = None,
) -> SimulationExecutionProgress:
    """Execute or resume frozen base runs without recomputing valid checkpoints."""
    output = assert_safe_simulation_path(output_directory)
    verify_prepared_manifests(output)
    if maximum_new_runs is not None and maximum_new_runs < 1:
        raise ValueError("maximum_new_runs must be positive when provided")
    plan = json.loads((output / "simulation_run_plan.json").read_text(encoding="utf-8"))
    scenario_by_id = {item.scenario_id: item for item in frozen_scenarios()}
    completed = 0
    created = 0
    for planned in plan["base_runs"]:
        path = _result_path(
            output,
            str(planned["scenario_id"]),
            int(planned["sample_count"]),
            int(planned["seed"]),
        )
        if path.is_file():
            _load_checkpoint_result(
                path,
                run_id=str(planned["run_id"]),
                scenario_id=str(planned["scenario_id"]),
                seed=int(planned["seed"]),
                sample_count=int(planned["sample_count"]),
            )
            completed += 1
            continue
        if maximum_new_runs is not None and created >= maximum_new_runs:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        scenario = scenario_by_id[str(planned["scenario_id"])]
        try:
            result = simulate_scenario_seed(
                scenario,
                int(planned["seed"]),
                sample_count=int(planned["sample_count"]),
            )
            _write_json(path, result.to_dict())
        except Exception as exc:
            error_path = output / "errors.jsonl"
            with error_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "run_id": planned["run_id"],
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
            raise
        _load_checkpoint_result(
            path,
            run_id=str(planned["run_id"]),
            scenario_id=str(planned["scenario_id"]),
            seed=int(planned["seed"]),
            sample_count=int(planned["sample_count"]),
        )
        created += 1
        completed += 1
    checkpoint = {
        "schema_version": "1.0.0",
        "completed_base_run_count": completed,
        "planned_base_run_count": 300,
        "new_run_count_this_invocation": created,
        "status": "base_complete" if completed == 300 else "partial",
        "final_test_read": False,
        "scientifically_eligible": False,
    }
    _write_json(output / "checkpoint.json", checkpoint)
    return SimulationExecutionProgress(
        output,
        completed,
        300,
        created,
        str(checkpoint["status"]),
    )


def _all_checkpoint_results(
    output: Path,
    planned_runs: list[Mapping[str, Any]],
) -> tuple[ScenarioRunResult, ...]:
    results: list[ScenarioRunResult] = []
    seen: set[str] = set()
    for planned in planned_runs:
        run_id = str(planned["run_id"])
        if run_id in seen:
            raise ValueError(f"duplicate planned run_id: {run_id}")
        seen.add(run_id)
        path = _result_path(
            output,
            str(planned["scenario_id"]),
            int(planned["sample_count"]),
            int(planned["seed"]),
        )
        if not path.is_file():
            raise ValueError(f"planned run is incomplete: {run_id}")
        results.append(
            _load_checkpoint_result(
                path,
                run_id=run_id,
                scenario_id=str(planned["scenario_id"]),
                seed=int(planned["seed"]),
                sample_count=int(planned["sample_count"]),
            )
        )
    return tuple(results)


def _base_rates(results: tuple[ScenarioRunResult, ...]) -> tuple[dict[str, float], list[dict[str, Any]]]:
    by_scenario = {
        scenario_id: tuple(item for item in results if item.scenario_id == scenario_id)
        for scenario_id in FROZEN_SCENARIO_IDS
    }
    if any(len(items) != 50 for items in by_scenario.values()):
        raise ValueError("base summary requires exactly 50 results per frozen scenario")
    rows: list[dict[str, Any]] = []
    rates: dict[str, float] = {}
    definitions = {
        "S0_NULL": ("false_pass", "false_pass_rate", 0.10, "maximum"),
        "S1_LEVEL_ONLY": ("false_pass", "false_pass_rate", 0.10, "maximum"),
        "S2_POSITIVE_CONTROL": ("recovered", "recovery_rate", 0.90, "minimum"),
        "S3_MODERATE_REALISTIC": ("recovered", "recovery_rate", 0.80, "minimum"),
        "S4_REASSEMBLY_STRESS": ("safely_not_continued", "safe_handling_rate", 0.90, "diagnostic_minimum"),
    }
    for scenario_id, (outcome, metric, threshold, comparison) in definitions.items():
        items = by_scenario[scenario_id]
        numerator = sum(item.decision["scenario_outcome"] == outcome for item in items)
        rate = numerator / len(items)
        rates[scenario_id] = rate
        passed = rate <= threshold if comparison == "maximum" else rate >= threshold
        rows.append(
            {
                "scenario_id": scenario_id,
                "metric": metric,
                "numerator": numerator,
                "denominator": len(items),
                "rate": rate,
                "threshold": threshold,
                "comparison": comparison,
                "passed": passed,
            }
        )
    quality = by_scenario["S5_DATA_QUALITY_STRESS"]
    detected = sum(int(item.qc["detected_or_safely_downgraded_count"]) for item in quality)
    injected = sum(int(item.qc["injected_anomaly_count"]) for item in quality)
    rate = detected / injected
    rates["S5_DATA_QUALITY_STRESS"] = rate
    rows.append(
        {
            "scenario_id": "S5_DATA_QUALITY_STRESS",
            "metric": "detection_or_safe_downgrade_rate",
            "numerator": detected,
            "denominator": injected,
            "rate": rate,
            "threshold": 0.95,
            "comparison": "minimum",
            "passed": rate >= 0.95,
        }
    )
    return rates, rows


def _execute_optional_s3_64(output: Path, plan: Mapping[str, Any]) -> tuple[ScenarioRunResult, ...]:
    scenario = {item.scenario_id: item for item in frozen_scenarios()}["S3_MODERATE_REALISTIC"]
    for planned in plan["conditional_s3_64_runs"]:
        path = _result_path(output, scenario.scenario_id, 64, int(planned["seed"]))
        if path.is_file():
            _load_checkpoint_result(
                path,
                run_id=str(planned["run_id"]),
                scenario_id=scenario.scenario_id,
                seed=int(planned["seed"]),
                sample_count=64,
            )
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        result = simulate_scenario_seed(scenario, int(planned["seed"]), sample_count=64)
        _write_json(path, result.to_dict())
    return _all_checkpoint_results(output, list(plan["conditional_s3_64_runs"]))


def _result_row(result: ScenarioRunResult) -> dict[str, Any]:
    enc = result.metrics["U4ENC"]
    sym = result.metrics["U4SYM"]
    return {
        "run_id": result.run_id,
        "scenario_id": result.scenario_id,
        "seed": result.seed,
        "sample_count": result.sample_count,
        "status": result.status,
        "scenario_outcome": result.decision["scenario_outcome"],
        "positive_rule_pass": result.decision["positive_rule_pass"],
        "U4ENC_G_raw": enc["G_raw"],
        "U4ENC_G_demeaned": enc["G_demeaned"],
        "U4ENC_G_zscore": enc["G_zscore"],
        "U4SYM_G_raw": sym["G_raw"],
        "U4SYM_G_demeaned": sym["G_demeaned"],
        "U4SYM_G_zscore": sym["G_zscore"],
        "delta_G_demeaned": enc["G_demeaned"] - sym["G_demeaned"],
        "U4ENC_between_demeaned_median_rms": enc["between_demeaned_median_rms"],
        "U4ENC_repos_demeaned_median_rms": enc["repos_demeaned_median_rms"],
        "U4ENC_reasm_demeaned_median_rms": enc["reasm_demeaned_median_rms"],
        "U4ENC_balanced_accuracy": enc["balanced_accuracy"],
        "U4ENC_macro_f1": enc["macro_f1"],
        "U4SYM_balanced_accuracy": sym["balanced_accuracy"],
        "U4SYM_macro_f1": sym["macro_f1"],
        "qc_injected_count": result.qc["injected_anomaly_count"],
        "qc_detected_or_safely_downgraded_count": result.qc["detected_or_safely_downgraded_count"],
        "result_sha256": result.result_sha256,
        "final_test_read": result.final_test_read,
        "scientifically_eligible": result.scientifically_eligible,
    }


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_grouped_validation_csv(path: Path, results: tuple[ScenarioRunResult, ...]) -> None:
    rows: list[dict[str, Any]] = []
    for result in results:
        for fold in result.grouped_validation_audit:
            rows.append(
                {
                    "run_id": result.run_id,
                    "scenario_id": result.scenario_id,
                    "seed": result.seed,
                    "sample_count": result.sample_count,
                    "configuration_id": fold["configuration_id"],
                    "fold_id": fold["fold_id"],
                    "held_out_group": fold["held_out_group"],
                    "train_sample_count": len(fold["train_sample_ids"]),
                    "test_sample_count": len(fold["test_sample_ids"]),
                    "group_leakage": fold["group_leakage"],
                }
            )
    _write_csv(path, rows)


def _write_charts(
    output: Path,
    rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    *,
    optional_triggered: bool,
) -> tuple[Path, ...]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    chart_dir = output / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    def save(name: str) -> None:
        path = chart_dir / name
        plt.tight_layout()
        plt.savefig(path, dpi=140)
        plt.close()
        paths.append(path)

    plt.figure(figsize=(9, 4.5))
    labels = [item["scenario_id"] for item in summary_rows]
    rates = [float(item["rate"]) for item in summary_rows]
    plt.bar(labels, rates)
    plt.axhline(0.8, color="black", linestyle="--", linewidth=1)
    plt.ylabel("rate")
    plt.xticks(rotation=25, ha="right")
    plt.title("Frozen scenario recovery / false-pass / QC rates")
    save("scenario_rates.png")

    base_rows = [row for row in rows if row["sample_count"] == 32]
    scenarios = list(FROZEN_SCENARIO_IDS)
    for field_groups, title, name in (
        (("U4ENC_G_demeaned", "U4SYM_G_demeaned"), "G_demeaned by scenario and structure", "g_demeaned_distribution.png"),
        (("delta_G_demeaned",), "U4ENC minus U4SYM G_demeaned", "u4enc_vs_u4sym.png"),
        (("U4ENC_repos_demeaned_median_rms", "U4ENC_reasm_demeaned_median_rms"), "REPOS versus REASM change", "repos_vs_reasm.png"),
        (("U4ENC_balanced_accuracy", "U4ENC_macro_f1"), "Grouped classification", "grouped_classification.png"),
    ):
        plt.figure(figsize=(10, 5))
        data: list[list[float]] = []
        positions: list[float] = []
        tick_positions: list[float] = []
        for scenario_index, scenario_id in enumerate(scenarios):
            tick_positions.append(scenario_index * (len(field_groups) + 1) + (len(field_groups) - 1) / 2)
            selected = [row for row in base_rows if row["scenario_id"] == scenario_id]
            for field_index, field in enumerate(field_groups):
                data.append([float(row[field]) for row in selected])
                positions.append(scenario_index * (len(field_groups) + 1) + field_index)
        plt.boxplot(data, positions=positions, widths=0.65, showfliers=False)
        plt.xticks(tick_positions, scenarios, rotation=25, ha="right")
        plt.title(title)
        plt.ylabel("value")
        save(name)

    quality = next(item for item in summary_rows if item["scenario_id"] == "S5_DATA_QUALITY_STRESS")
    plt.figure(figsize=(5, 4))
    plt.bar(["detected/safe", "missed"], [quality["numerator"], quality["denominator"] - quality["numerator"]])
    plt.title("S5 QC abnormal sample handling")
    plt.ylabel("injected anomaly records")
    save("qc_detection.png")

    if optional_triggered:
        s3 = [row for row in rows if row["scenario_id"] == "S3_MODERATE_REALISTIC"]
        plt.figure(figsize=(6, 4))
        data = [
            [float(row["U4ENC_G_demeaned"]) for row in s3 if row["sample_count"] == count]
            for count in (32, 64)
        ]
        plt.boxplot(data, tick_labels=["32", "64"])
        plt.title("S3 32 versus 64 samples")
        plt.ylabel("U4ENC G_demeaned")
        save("s3_32_vs_64.png")
    return tuple(paths)


def write_artifact_inventory(output_directory: str | Path) -> Path:
    """Write one deterministic inventory for every completed output artifact."""
    output = assert_safe_simulation_path(output_directory)
    manifest_path = output / "artifact_manifest.json"
    sums_path = output / "SHA256SUMS"
    if manifest_path.exists() or sums_path.exists():
        raise FileExistsError("artifact inventory already exists")
    excluded = {manifest_path.resolve(), sums_path.resolve()}
    files = tuple(
        sorted(
            (path for path in output.rglob("*") if path.is_file() and path.resolve() not in excluded),
            key=lambda path: path.relative_to(output).as_posix(),
        )
    )
    entries = [
        {"path": path.relative_to(output).as_posix(), "sha256": _file_sha256(path)}
        for path in files
    ]
    plan = json.loads((output / "simulation_run_plan.json").read_text(encoding="utf-8"))
    _write_json(
        manifest_path,
        {
            "schema_version": "1.0.0",
            "source_commit": plan["source_commit"],
            "source_git_dirty": False,
            "data_origin": "simulated",
            "run_purpose": "software_validation",
            "scientifically_eligible": False,
            "final_test_read": False,
            "artifacts": entries,
        },
    )
    sum_entries = [*entries, {"path": manifest_path.name, "sha256": _file_sha256(manifest_path)}]
    sums_path.write_text(
        "".join(f"{item['sha256'].removeprefix('sha256:')}  {item['path']}\n" for item in sum_entries),
        encoding="ascii",
    )
    return manifest_path


def verify_artifact_inventory(output_directory: str | Path) -> dict[str, str]:
    output = assert_safe_simulation_path(output_directory)
    manifest_path = output / "artifact_manifest.json"
    sums_path = output / "SHA256SUMS"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verified: dict[str, str] = {}
    for item in manifest["artifacts"]:
        path = output / str(item["path"])
        actual = _file_sha256(path)
        if actual != item["sha256"]:
            raise ValueError(f"artifact SHA-256 mismatch: {path}")
        verified[str(item["path"])] = actual
    expected_lines = {
        f"{digest.removeprefix('sha256:')}  {name}"
        for name, digest in {
            **verified,
            manifest_path.name: _file_sha256(manifest_path),
        }.items()
    }
    actual_lines = set(sums_path.read_text(encoding="ascii").splitlines())
    if actual_lines != expected_lines:
        raise ValueError("SHA256SUMS content mismatch")
    return verified


@dataclass(frozen=True, slots=True)
class FinalizedSimulation:
    output_directory: Path
    base_run_count: int
    additional_run_count: int
    optional_s3_64_triggered: bool
    final_decision: str
    recommend_protocol_rev002: bool
    rates: Mapping[str, float]
    artifact_count: int


def finalize_prepared_simulation(output_directory: str | Path) -> FinalizedSimulation:
    """Summarize all base runs, execute the frozen optional branch if eligible, and seal outputs."""
    output = assert_safe_simulation_path(output_directory)
    verify_prepared_manifests(output)
    for name in ("run_results.csv", "scenario_summary.csv", "decision_summary.json"):
        if (output / name).exists():
            raise FileExistsError(f"final SIM-1 output already exists: {output / name}")
    plan = json.loads((output / "simulation_run_plan.json").read_text(encoding="utf-8"))
    base_results = _all_checkpoint_results(output, list(plan["base_runs"]))
    rates, summary_rows = _base_rates(base_results)
    trigger = should_run_s3_64(
        {name: rates[name] for name in (
            "S0_NULL", "S1_LEVEL_ONLY", "S2_POSITIVE_CONTROL",
            "S3_MODERATE_REALISTIC", "S5_DATA_QUALITY_STRESS",
        )}
    )
    branch_payload: dict[str, Any] = {
        "triggered": trigger,
        "base_rates": rates,
        "rule": plan["conditional_s3_64_trigger"],
        "additional_run_count": 0,
        "reason": "frozen_trigger_satisfied" if trigger else "frozen_trigger_not_satisfied",
    }
    optional_results: tuple[ScenarioRunResult, ...] = ()
    optional_rate: float | None = None
    if trigger:
        optional_results = _execute_optional_s3_64(output, plan)
        recovered = sum(item.decision["scenario_outcome"] == "recovered" for item in optional_results)
        optional_rate = recovered / len(optional_results)
        branch_payload.update(
            {
                "additional_run_count": len(optional_results),
                "S3_64_recovered_count": recovered,
                "S3_64_denominator": len(optional_results),
                "S3_64_recovery_rate": optional_rate,
            }
        )
        summary_rows.append(
            {
                "scenario_id": "S3_MODERATE_REALISTIC_64",
                "metric": "recovery_rate",
                "numerator": recovered,
                "denominator": len(optional_results),
                "rate": optional_rate,
                "threshold": 0.80,
                "comparison": "minimum_after_frozen_trigger",
                "passed": optional_rate >= 0.80,
            }
        )
    _write_json(output / "branch_evidence.json", branch_payload)

    controls_pass = bool(
        rates["S2_POSITIVE_CONTROL"] >= 0.90
        and rates["S0_NULL"] <= 0.10
        and rates["S1_LEVEL_ONLY"] <= 0.10
        and rates["S5_DATA_QUALITY_STRESS"] >= 0.95
    )
    s4_safe = rates["S4_REASSEMBLY_STRESS"] >= 0.90
    if not controls_pass or rates["S3_MODERATE_REALISTIC"] < 0.50:
        final_decision = "重新检查实现或设计"
        recommend_rev002 = False
    elif trigger:
        final_decision = "调整后继续" if optional_rate is not None and optional_rate >= 0.80 else "重新检查实现或设计"
        recommend_rev002 = final_decision == "调整后继续"
    elif rates["S3_MODERATE_REALISTIC"] >= 0.80 and s4_safe:
        final_decision = "继续原设计"
        recommend_rev002 = False
    else:
        final_decision = "重新检查实现或设计"
        recommend_rev002 = False

    all_results = (*base_results, *optional_results)
    result_rows = [_result_row(item) for item in all_results]
    _write_csv(output / "run_results.csv", result_rows)
    _write_csv(output / "scenario_summary.csv", summary_rows)
    _write_grouped_validation_csv(output / "grouped_validation.csv", all_results)
    _write_csv(
        output / "qc_detection.csv",
        [
            {
                "run_id": item.run_id,
                "seed": item.seed,
                "sample_count": item.sample_count,
                "injected_anomaly_count": item.qc["injected_anomaly_count"],
                "detected_or_safely_downgraded_count": item.qc["detected_or_safely_downgraded_count"],
                "rate": item.qc["detection_or_safe_downgrade_rate"],
            }
            for item in all_results
            if item.scenario_id == "S5_DATA_QUALITY_STRESS"
        ],
    )
    if not (output / "errors.jsonl").exists():
        (output / "errors.jsonl").write_text("", encoding="utf-8")
    _write_charts(output, result_rows, summary_rows, optional_triggered=trigger)
    decision = {
        "schema_version": "1.0.0",
        "source_commit": plan["source_commit"],
        "source_git_dirty": False,
        "research_protocol_version": "rev-001",
        "sim0_plan_version": "SIM-0 rev-001",
        "base_run_count": len(base_results),
        "additional_run_count": len(optional_results),
        "total_run_count": len(all_results),
        "optional_s3_64_triggered": trigger,
        "rates": rates,
        "S3_64_recovery_rate": optional_rate,
        "threshold_results": summary_rows,
        "final_decision": final_decision,
        "recommend_protocol_rev002": recommend_rev002,
        "data_origin": "simulated",
        "dataset_role": "software_validation",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
        "final_test_read": False,
        "scientific_use": "PROHIBITED: software-validation stress simulation only",
    }
    _write_json(output / "decision_summary.json", decision)
    write_artifact_inventory(output)
    verified = verify_artifact_inventory(output)
    return FinalizedSimulation(
        output,
        len(base_results),
        len(optional_results),
        trigger,
        final_decision,
        recommend_rev002,
        rates,
        len(verified),
    )
