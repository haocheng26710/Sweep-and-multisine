"""P8-B2 tone and digital-integrity quality control."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from .multisine_estimation import PeriodTransferEstimate
from .schemas import SpectrumData

FloatArray = NDArray[np.float64]

_SEVERITY = {"valid": 0, "warning": 1, "exclude_candidate": 2}


@dataclass(frozen=True, slots=True)
class ToneQualityRecord:
    frequency_hz: float
    snr_db: float | None
    snr_status: str
    snr_method: str
    snr_noise_bin_count: int
    leakage_ratio: float | None
    leakage_status: str
    leakage_method: str
    leakage_bin_count: int
    leakage_guard_bins: int
    leakage_radius_bins: int
    period_variance: float | None
    period_variance_status: str
    period_variance_method: str
    magnitude_variance_db2: float | None
    phase_circular_variance: float | None
    period_count: int
    missing_tone: bool | None
    valid_tone: bool
    qc_status: str
    qc_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MultisineQCAnalysis:
    spectrum: SpectrumData
    tone_quality: tuple[ToneQualityRecord, ...]
    measurement_qc: Mapping[str, Any]
    estimate: PeriodTransferEstimate
    clipping_metrics: Mapping[str, Any]


def _higher_is_worse(value: float, warning: float, exclude: float) -> str:
    if value >= exclude:
        return "exclude_candidate"
    if value >= warning:
        return "warning"
    return "valid"


def _lower_is_worse(value: float, warning: float, exclude: float) -> str:
    if value <= exclude:
        return "exclude_candidate"
    if value <= warning:
        return "warning"
    return "valid"


def _longest_true_run(mask: NDArray[np.bool_]) -> int:
    longest = 0
    current = 0
    for value in mask:
        if value:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def analyze_clipping(
    audio: FloatArray,
    config: Mapping[str, Any],
    *,
    channel: int,
    sample_format: str,
) -> dict[str, Any]:
    """Count every full-scale-like sample without mutating the recording."""
    threshold = float(config["sample_threshold_fraction_full_scale"])
    values = np.asarray(audio, dtype=np.float64)
    clipped = np.abs(values) >= threshold
    count = int(np.count_nonzero(clipped))
    fraction = count / int(values.size)
    if count == 0:
        status = "valid"
    else:
        status = _higher_is_worse(
            fraction,
            float(config["warning_fraction"]),
            float(config["exclude_candidate_fraction"]),
        )
    return {
        "status": status,
        "sample_count": count,
        "fraction": fraction,
        "channel": channel,
        "sample_format": sample_format,
        "sample_threshold_fraction_full_scale": threshold,
        "warning_fraction": float(config["warning_fraction"]),
        "exclude_candidate_fraction": float(
            config["exclude_candidate_fraction"]
        ),
        "longest_run_samples": (
            _longest_true_run(clipped)
            if bool(config.get("record_longest_run", True))
            else None
        ),
    }


def evaluate_tone_and_audio_quality(
    estimate: PeriodTransferEstimate,
    magnitude_db: FloatArray,
    config: Mapping[str, Any],
    *,
    clipping_metrics: Mapping[str, Any],
    clock_drift_metrics: str | Mapping[str, Any],
) -> tuple[tuple[ToneQualityRecord, ...], dict[str, Any], NDArray[np.bool_]]:
    """Evaluate P8-B2 metrics from corrected stable periods and raw clipping QC."""
    neighborhood = config["neighborhood"]
    guard = int(neighborhood["tone_guard_bins"])
    leakage_radius = int(neighborhood["leakage_radius_bins"])
    noise_inner = int(neighborhood["noise_inner_radius_bins"])
    noise_outer = int(neighborhood["noise_outer_radius_bins"])
    minimum_noise_bins = int(neighborhood["minimum_noise_bins"])
    minimum_leakage_bins = int(neighborhood["minimum_leakage_bins"])

    spectrum = estimate.spectrum_by_period
    bin_power = np.mean(np.abs(spectrum) ** 2, axis=0)
    tone_bins = np.asarray(estimate.tone_bins, dtype=np.int64)
    max_bin = int(bin_power.size - 1)
    guarded = np.zeros(bin_power.size, dtype=bool)
    for tone_bin in tone_bins:
        guarded[max(0, tone_bin - guard) : min(max_bin, tone_bin + guard) + 1] = True

    records: list[ToneQualityRecord] = []
    unavailable_metrics: set[str] = set()
    snr_config = config["snr"]
    leakage_config = config["leakage"]
    missing_config = config["missing_tone"]
    stability_config = config["period_stability"]
    stability_method = str(stability_config["method"])
    period_count = int(estimate.transfer_by_period.shape[0])

    for tone_index, (frequency, tone_bin) in enumerate(
        zip(estimate.frequency_hz, tone_bins, strict=True)
    ):
        tone_power = float(bin_power[tone_bin])
        noise_bins = [
            candidate
            for candidate in range(max(1, tone_bin - noise_outer), min(max_bin, tone_bin + noise_outer) + 1)
            if noise_inner <= abs(candidate - tone_bin) <= noise_outer
            and not guarded[candidate]
        ]
        if (
            len(noise_bins) < minimum_noise_bins
            or not np.isfinite(tone_power)
            or tone_power <= 0.0
        ):
            snr_db = None
            snr_status = "unavailable"
            unavailable_metrics.add("snr")
        else:
            noise_power = float(np.median(bin_power[noise_bins]))
            if not np.isfinite(noise_power) or noise_power <= 0.0:
                snr_db = None
                snr_status = "unavailable"
                unavailable_metrics.add("snr")
            else:
                snr_db = 10.0 * np.log10(tone_power / noise_power)
                snr_status = _lower_is_worse(
                    snr_db,
                    float(snr_config["warning_below_db"]),
                    float(snr_config["exclude_candidate_below_db"]),
                )

        leakage_bins = [
            candidate
            for candidate in range(max(1, tone_bin - leakage_radius), min(max_bin, tone_bin + leakage_radius) + 1)
            if guard < abs(candidate - tone_bin) <= leakage_radius
            and all(
                other == tone_bin or abs(candidate - other) > guard
                for other in tone_bins
            )
        ]
        if (
            len(leakage_bins) < minimum_leakage_bins
            or not np.isfinite(tone_power)
            or tone_power <= 0.0
        ):
            leakage_ratio = None
            leakage_status = "unavailable"
            unavailable_metrics.add("leakage")
        else:
            leakage_ratio = float(np.sum(bin_power[leakage_bins]) / tone_power)
            leakage_status = _higher_is_worse(
                leakage_ratio,
                float(leakage_config["warning_ratio"]),
                float(leakage_config["exclude_candidate_ratio"]),
            )

        transfers = estimate.transfer_by_period[:, tone_index]
        transfer_power = float(np.mean(np.abs(transfers) ** 2))
        minimum_periods = int(stability_config["minimum_periods"])
        if (
            period_count < minimum_periods
            or not np.isfinite(transfer_power)
            or transfer_power <= 0.0
        ):
            period_variance = None
            period_variance_status = "unavailable"
            magnitude_variance_db2 = None
            phase_circular_variance = None
            unavailable_metrics.add("period_variance")
        else:
            if stability_method == "complex_relative_variance":
                mean_transfer = np.mean(transfers)
                period_variance = float(
                    np.mean(np.abs(transfers - mean_transfer) ** 2)
                    / transfer_power
                )
            elif stability_method == "power_relative_variance":
                powers = np.abs(transfers) ** 2
                mean_power = float(np.mean(powers))
                period_variance = float(np.var(powers) / mean_power**2)
            else:
                raise ValueError(
                    f"Unsupported period stability method: {stability_method!r}"
                )
            period_variance_status = _higher_is_worse(
                period_variance,
                float(stability_config["warning_variance_ratio"]),
                float(stability_config["exclude_candidate_variance_ratio"]),
            )
            transfer_magnitudes = np.abs(transfers)
            magnitudes = 20.0 * np.log10(
                np.maximum(transfer_magnitudes, np.finfo(float).tiny)
            )
            magnitude_variance_db2 = float(np.var(magnitudes, ddof=1))
            unit_phase = np.divide(
                transfers,
                transfer_magnitudes,
                out=np.zeros_like(transfers),
                where=transfer_magnitudes > 0.0,
            )
            phase_circular_variance = float(1.0 - np.abs(np.mean(unit_phase)))

        tone_magnitude_db = float(magnitude_db[tone_index])
        magnitude_missing = (
            not np.isfinite(tone_magnitude_db)
            or tone_magnitude_db <= float(missing_config["minimum_magnitude_db"])
        )
        if magnitude_missing:
            missing_tone: bool | None = True
        elif snr_db is None:
            missing_tone = None
            unavailable_metrics.add("missing_tone")
        else:
            missing_tone = bool(
                snr_db <= float(missing_config["minimum_snr_db"])
            )

        reasons: list[str] = []
        for name, status in (
            ("snr", snr_status),
            ("leakage", leakage_status),
            ("period_variance", period_variance_status),
        ):
            if status != "valid":
                reasons.append(f"{name}_{status}")
        if missing_tone is True:
            reasons.append("missing_tone")
        elif missing_tone is None:
            reasons.append("missing_tone_unavailable")
        tone_statuses = (snr_status, leakage_status, period_variance_status)
        if missing_tone is True or "exclude_candidate" in tone_statuses:
            qc_status = "exclude_candidate"
        elif missing_tone is None or any(
            status in {"warning", "unavailable"} for status in tone_statuses
        ):
            qc_status = "warning"
        else:
            qc_status = "valid"
        valid_tone = qc_status != "exclude_candidate"
        records.append(
            ToneQualityRecord(
                frequency_hz=float(frequency),
                snr_db=snr_db,
                snr_status=snr_status,
                snr_method=str(snr_config["method"]),
                snr_noise_bin_count=len(noise_bins),
                leakage_ratio=leakage_ratio,
                leakage_status=leakage_status,
                leakage_method=(
                    "local_non_excited_bin_energy_over_tone_bin_energy"
                ),
                leakage_bin_count=len(leakage_bins),
                leakage_guard_bins=guard,
                leakage_radius_bins=leakage_radius,
                period_variance=period_variance,
                period_variance_status=period_variance_status,
                period_variance_method=stability_method,
                magnitude_variance_db2=magnitude_variance_db2,
                phase_circular_variance=phase_circular_variance,
                period_count=period_count,
                missing_tone=missing_tone,
                valid_tone=valid_tone,
                qc_status=qc_status,
                qc_reasons=tuple(reasons),
            )
        )

    off_tone_config = config["non_excited_energy"]
    off_bins = [candidate for candidate in range(1, max_bin + 1) if not guarded[candidate]]
    total_non_dc_power = float(np.sum(bin_power[1:]))
    if (
        len(off_bins) < int(off_tone_config["minimum_bin_count"])
        or not np.isfinite(total_non_dc_power)
        or total_non_dc_power <= 0.0
    ):
        non_excited = {
            "status": "unavailable",
            "energy_ratio": None,
            "bin_count": len(off_bins),
            "guard_bins": guard,
            "method": "non_excited_bin_energy_over_total_non_dc_energy",
        }
        unavailable_metrics.add("non_excited_energy")
    else:
        off_ratio = float(np.sum(bin_power[off_bins]) / total_non_dc_power)
        non_excited = {
            "status": _higher_is_worse(
                off_ratio,
                float(off_tone_config["warning_ratio"]),
                float(off_tone_config["exclude_candidate_ratio"]),
            ),
            "energy_ratio": off_ratio,
            "bin_count": len(off_bins),
            "guard_bins": guard,
            "method": "non_excited_bin_energy_over_total_non_dc_energy",
        }

    statuses = [str(clipping_metrics["status"]), str(non_excited["status"])]
    if isinstance(clock_drift_metrics, Mapping):
        statuses.append(str(clock_drift_metrics["final_decision"]))
    else:
        unavailable_metrics.add("clock_drift")
    for record in records:
        statuses.extend(
            [record.snr_status, record.leakage_status, record.period_variance_status]
        )
        if record.missing_tone is True:
            statuses.append("exclude_candidate")
    available_statuses = [status for status in statuses if status in _SEVERITY]
    measurement_status = max(available_statuses, key=_SEVERITY.__getitem__)
    if unavailable_metrics and measurement_status == "valid":
        measurement_status = "warning"
    measurement_qc = {
        "qc_schema_version": "1.0.0",
        "status": measurement_status,
        "clipping": dict(clipping_metrics),
        "missing_tone_count": sum(record.missing_tone is True for record in records),
        "missing_tone_unavailable_count": sum(
            record.missing_tone is None for record in records
        ),
        "valid_tone_count": sum(record.qc_status == "valid" for record in records),
        "warning_tone_count": sum(
            record.qc_status == "warning" for record in records
        ),
        "exclude_candidate_tone_count": sum(
            record.qc_status == "exclude_candidate" for record in records
        ),
        "non_excited_energy": non_excited,
        "unavailable_items": sorted(unavailable_metrics),
        "aggregation_policy": (
            "exclude_candidate_over_warning_over_valid; unavailable promotes "
            "otherwise-valid measurement to warning"
        ),
        "configuration": dict(config),
    }
    valid_mask = np.asarray([record.valid_tone for record in records], dtype=bool)
    return tuple(records), measurement_qc, valid_mask
