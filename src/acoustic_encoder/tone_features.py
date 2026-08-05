"""P3-C matched-tone FeatureSet construction without sparse-to-dense synthesis."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from .features import build_dense_feature_sets
from .quality_control import MeasurementQCResult, measurement_qc_sha256
from .schemas import (
    FeatureKind,
    FeatureSet,
    MeasurementMode,
    Representation,
    SpectrumData,
)
from .tone_sets import ToneSetDefinition


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


class ToneFeatureConstructionError(ValueError):
    """Raised when an auditable tone FeatureSet cannot be constructed."""


@dataclass(frozen=True, slots=True)
class ToneNormalizationResult:
    values: FloatArray
    valid_mask: BoolArray
    units: str
    method: str
    valid_tone_count: int
    mean_db: float | None
    standard_deviation_db: float | None


@dataclass(frozen=True, slots=True)
class ToneExtractionRecord:
    tone_index: int
    frequency_hz: float
    feature_name: str
    method: str
    valid: bool
    value_db: float | None
    reason: str | None
    source_indices: tuple[int, ...] = ()
    source_frequency_hz: tuple[float, ...] = ()
    source_weights: tuple[float, ...] = ()
    requested_bandwidth_hz: float | None = None
    band_lower_hz: float | None = None
    band_upper_hz: float | None = None
    covered_bandwidth_hz: float | None = None
    coverage_fraction: float | None = None
    valid_source_point_count: int | None = None
    boundary_interpolation_count: int | None = None


@dataclass(frozen=True, slots=True)
class ToneFeatureProcessingResult:
    sample_id: str
    feature_kind: FeatureKind
    processing_status: str
    feature_set: FeatureSet | None
    preprocessing_id: str
    tone_schema_id: str
    extraction_records: tuple[ToneExtractionRecord, ...]
    failures: tuple[str, ...]
    dense_preprocessing_id: str | None
    normalization: ToneNormalizationResult | None
    run_purpose: str


@dataclass(frozen=True, slots=True)
class MatchedToneView:
    processing_status: str
    failure_reason: str | None
    common_valid_mask: BoolArray
    sweep_invalid_count: int
    multisine_missing_count: int
    multisine_other_invalid_count: int
    common_valid_count: int
    minimum_common_valid_tones: int
    source_reference_status: str
    comparison_status: str
    cross_mode_absolute_comparable: bool


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def normalize_tone_values(
    values_db: FloatArray,
    valid_mask: BoolArray,
    config: Mapping[str, Any],
) -> ToneNormalizationResult:
    """Apply one sample-local normalization while retaining all tone positions."""
    values = np.asarray(values_db, dtype=np.float64)
    mask = np.asarray(valid_mask, dtype=bool)
    if values.ndim != 1 or mask.ndim != 1 or values.size != mask.size:
        raise ValueError("tone values and valid_mask must be equal-length 1-D arrays")
    usable = mask & np.isfinite(values)
    minimum_valid = int(config["minimum_valid_tones"])
    valid_count = int(np.count_nonzero(usable))
    if valid_count < minimum_valid:
        raise ToneFeatureConstructionError(
            f"valid tone count {valid_count} is below minimum_valid_tones {minimum_valid}"
        )
    method = str(config["method"])
    output = np.full(values.size, np.nan, dtype=np.float64)
    mean_db: float | None = None
    standard_deviation_db: float | None = None
    if method == "none":
        output[usable] = values[usable]
        units = "dB"
    elif method == "subtract_mean_db":
        mean_db = float(np.mean(values[usable]))
        output[usable] = values[usable] - mean_db
        units = "dB"
    elif method == "zscore_within_sample":
        mean_db = float(np.mean(values[usable]))
        standard_deviation_db = float(np.std(values[usable], ddof=0))
        minimum_std = float(config["minimum_std_db"])
        if standard_deviation_db < minimum_std:
            raise ToneFeatureConstructionError(
                "tone standard deviation "
                f"{standard_deviation_db:g} dB is below configured minimum {minimum_std:g} dB"
            )
        output[usable] = (values[usable] - mean_db) / standard_deviation_db
        units = "dimensionless"
    else:
        raise ToneFeatureConstructionError(
            f"unsupported tone normalization method: {method!r}"
        )
    output.setflags(write=False)
    result_mask = np.array(usable, copy=True)
    result_mask.setflags(write=False)
    return ToneNormalizationResult(
        values=output,
        valid_mask=result_mask,
        units=units,
        method=method,
        valid_tone_count=valid_count,
        mean_db=mean_db,
        standard_deviation_db=standard_deviation_db,
    )


def _single_point_extract(
    grid_frequency_hz: FloatArray,
    values_db: FloatArray,
    valid_mask: BoolArray,
    tone_set: ToneSetDefinition,
) -> tuple[FloatArray, BoolArray, tuple[ToneExtractionRecord, ...]]:
    extracted = np.full(len(tone_set.tones), np.nan, dtype=np.float64)
    extracted_mask = np.zeros(len(tone_set.tones), dtype=bool)
    records: list[ToneExtractionRecord] = []
    for tone, feature_name in zip(
        tone_set.tones,
        tone_set.feature_names,
        strict=True,
    ):
        frequency = tone.frequency_hz
        insertion = int(np.searchsorted(grid_frequency_hz, frequency, side="left"))
        if insertion < grid_frequency_hz.size and grid_frequency_hz[insertion] == frequency:
            if valid_mask[insertion]:
                value = float(values_db[insertion])
                extracted[tone.tone_index] = value
                extracted_mask[tone.tone_index] = True
                records.append(
                    ToneExtractionRecord(
                        tone_index=tone.tone_index,
                        frequency_hz=frequency,
                        feature_name=feature_name,
                        method="single_point_linear",
                        valid=True,
                        value_db=value,
                        reason=None,
                        source_indices=(insertion,),
                        source_frequency_hz=(frequency,),
                        source_weights=(1.0,),
                    )
                )
            else:
                records.append(
                    ToneExtractionRecord(
                        tone_index=tone.tone_index,
                        frequency_hz=frequency,
                        feature_name=feature_name,
                        method="single_point_linear",
                        valid=False,
                        value_db=None,
                        reason="source_grid_point_invalid",
                        source_indices=(insertion,),
                        source_frequency_hz=(frequency,),
                        source_weights=(1.0,),
                    )
                )
            continue
        if insertion == 0 or insertion == grid_frequency_hz.size:
            records.append(
                ToneExtractionRecord(
                    tone_index=tone.tone_index,
                    frequency_hz=frequency,
                    feature_name=feature_name,
                    method="single_point_linear",
                    valid=False,
                    value_db=None,
                    reason="extrapolation_forbidden",
                )
            )
            continue
        left = insertion - 1
        right = insertion
        left_frequency = float(grid_frequency_hz[left])
        right_frequency = float(grid_frequency_hz[right])
        alpha = (frequency - left_frequency) / (right_frequency - left_frequency)
        weights = (1.0 - alpha, alpha)
        if not (valid_mask[left] and valid_mask[right]):
            records.append(
                ToneExtractionRecord(
                    tone_index=tone.tone_index,
                    frequency_hz=frequency,
                    feature_name=feature_name,
                    method="single_point_linear",
                    valid=False,
                    value_db=None,
                    reason="invalid_gap_crossing_forbidden",
                    source_indices=(left, right),
                    source_frequency_hz=(left_frequency, right_frequency),
                    source_weights=weights,
                )
            )
            continue
        value = float(weights[0] * values_db[left] + weights[1] * values_db[right])
        extracted[tone.tone_index] = value
        extracted_mask[tone.tone_index] = True
        records.append(
            ToneExtractionRecord(
                tone_index=tone.tone_index,
                frequency_hz=frequency,
                feature_name=feature_name,
                method="single_point_linear",
                valid=True,
                value_db=value,
                reason=None,
                source_indices=(left, right),
                source_frequency_hz=(left_frequency, right_frequency),
                source_weights=weights,
            )
        )
    return extracted, extracted_mask, tuple(records)


def _reject_overlapping_bands(
    tone_set: ToneSetDefinition,
    full_bandwidth_hz: float,
) -> None:
    half = full_bandwidth_hz / 2.0
    for left, right in zip(tone_set.tones, tone_set.tones[1:]):
        if left.frequency_hz + half > right.frequency_hz - half:
            raise ToneFeatureConstructionError(
                "narrowband tone bands overlap; overlap_policy='reject'"
            )


def _narrowband_extract(
    grid_frequency_hz: FloatArray,
    values_db: FloatArray,
    valid_mask: BoolArray,
    tone_set: ToneSetDefinition,
    config: Mapping[str, Any],
) -> tuple[FloatArray, BoolArray, tuple[ToneExtractionRecord, ...]]:
    bandwidth = float(config["full_bandwidth_hz"])
    minimum_coverage = float(config["minimum_band_coverage"])
    if config.get("integration_domain") != "linear_power_ratio":
        raise ToneFeatureConstructionError(
            "narrowband integration_domain must be linear_power_ratio"
        )
    if config.get("overlap_policy") != "reject":
        raise ToneFeatureConstructionError(
            "narrowband overlap_policy must be reject"
        )
    _reject_overlapping_bands(tone_set, bandwidth)
    power = np.power(10.0, values_db / 10.0)
    extracted = np.full(len(tone_set.tones), np.nan, dtype=np.float64)
    extracted_mask = np.zeros(len(tone_set.tones), dtype=bool)
    records: list[ToneExtractionRecord] = []
    half = bandwidth / 2.0
    for tone, feature_name in zip(
        tone_set.tones,
        tone_set.feature_names,
        strict=True,
    ):
        lower = tone.frequency_hz - half
        upper = tone.frequency_hz + half
        integral = 0.0
        covered = 0.0
        used_indices: set[int] = set()
        boundary_interpolations = 0
        for index in range(grid_frequency_hz.size - 1):
            left_frequency = float(grid_frequency_hz[index])
            right_frequency = float(grid_frequency_hz[index + 1])
            interval_lower = max(lower, left_frequency)
            interval_upper = min(upper, right_frequency)
            if interval_upper <= interval_lower:
                continue
            if not (valid_mask[index] and valid_mask[index + 1]):
                continue
            span = right_frequency - left_frequency
            lower_alpha = (interval_lower - left_frequency) / span
            upper_alpha = (interval_upper - left_frequency) / span
            lower_power = (
                (1.0 - lower_alpha) * power[index]
                + lower_alpha * power[index + 1]
            )
            upper_power = (
                (1.0 - upper_alpha) * power[index]
                + upper_alpha * power[index + 1]
            )
            width = interval_upper - interval_lower
            integral += 0.5 * float(lower_power + upper_power) * width
            covered += width
            used_indices.update((index, index + 1))
            boundary_interpolations += int(interval_lower != left_frequency)
            boundary_interpolations += int(interval_upper != right_frequency)
        coverage = covered / bandwidth
        common = {
            "tone_index": tone.tone_index,
            "frequency_hz": tone.frequency_hz,
            "feature_name": feature_name,
            "method": "narrowband_integration",
            "requested_bandwidth_hz": bandwidth,
            "band_lower_hz": lower,
            "band_upper_hz": upper,
            "covered_bandwidth_hz": covered,
            "coverage_fraction": coverage,
            "valid_source_point_count": len(used_indices),
            "boundary_interpolation_count": boundary_interpolations,
            "source_indices": tuple(sorted(used_indices)),
            "source_frequency_hz": tuple(
                float(grid_frequency_hz[index]) for index in sorted(used_indices)
            ),
        }
        if covered <= 0.0 or coverage + 1.0e-12 < minimum_coverage:
            records.append(
                ToneExtractionRecord(
                    valid=False,
                    value_db=None,
                    reason="minimum_band_coverage_not_met",
                    **common,
                )
            )
            continue
        mean_power = integral / covered
        if not np.isfinite(mean_power) or mean_power <= 0.0:
            records.append(
                ToneExtractionRecord(
                    valid=False,
                    value_db=None,
                    reason="integrated_power_not_positive_finite",
                    **common,
                )
            )
            continue
        value = 10.0 * float(np.log10(mean_power))
        extracted[tone.tone_index] = value
        extracted_mask[tone.tone_index] = True
        records.append(
            ToneExtractionRecord(
                valid=True,
                value_db=value,
                reason=None,
                **common,
            )
        )
    return extracted, extracted_mask, tuple(records)


def _tone_schema_id(
    tone_set: ToneSetDefinition,
    normalization_config: Mapping[str, Any],
) -> str:
    units = (
        "dimensionless"
        if normalization_config["method"] == "zscore_within_sample"
        else "dB"
    )
    return _canonical_hash(
        {
            "schema_version": "1.0.0",
            "tone_set_id": tone_set.tone_set_id,
            "tone_set_sha256": tone_set.tone_set_sha256,
            "feature_names": tone_set.feature_names,
            "units": [units] * len(tone_set.tones),
            "normalization": dict(normalization_config),
        }
    )


def build_sweep_tone_feature_set(
    spectrum: SpectrumData,
    measurement_qc: MeasurementQCResult,
    dense_preprocessing_config: Mapping[str, Any],
    tone_set: ToneSetDefinition,
    matched_config: Mapping[str, Any],
) -> ToneFeatureProcessingResult:
    """Project a sweep only after the authoritative P3 dense processing path."""
    extraction = matched_config["sweep_extraction"]
    dense = build_dense_feature_sets(
        spectrum,
        measurement_qc,
        dense_preprocessing_config,
    )
    raw = dense.feature_sets.get(FeatureKind.DENSE_RAW_SPL)
    if raw is None:
        raise ToneFeatureConstructionError(
            "sweep tone projection requires a completed dense_raw_spl feature"
        )
    if extraction["method"] == "single_point_linear":
        values, mask, records = _single_point_extract(
            dense.grid_frequency_hz,
            raw.values,
            raw.valid_mask,
            tone_set,
        )
    elif extraction["method"] == "narrowband_integration":
        values, mask, records = _narrowband_extract(
            dense.grid_frequency_hz,
            raw.values,
            raw.valid_mask,
            tone_set,
            extraction,
        )
    else:
        raise ToneFeatureConstructionError(
            f"unsupported sweep tone extraction method: {extraction['method']!r}"
        )
    normalization_config = matched_config["normalization"]
    tone_schema_id = _tone_schema_id(tone_set, normalization_config)
    preprocessing_id = _canonical_hash(
        {
            "schema_version": matched_config["schema_version"],
            "feature_kind": FeatureKind.TONE_PROJECTION_FROM_SWEEP.value,
            "dense_preprocessing_id": dense.preprocessing_id,
            "tone_set_sha256": tone_set.tone_set_sha256,
            "sweep_extraction": dict(extraction),
            "normalization": dict(normalization_config),
        }
    )
    try:
        normalized = normalize_tone_values(values, mask, normalization_config)
    except ToneFeatureConstructionError as exc:
        return ToneFeatureProcessingResult(
            sample_id=spectrum.meta.sample_id,
            feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
            processing_status="failed",
            feature_set=None,
            preprocessing_id=preprocessing_id,
            tone_schema_id=tone_schema_id,
            extraction_records=records,
            failures=(str(exc),),
            dense_preprocessing_id=dense.preprocessing_id,
            normalization=None,
            run_purpose=measurement_qc.run_purpose.value,
        )
    feature = FeatureSet(
        sample_id=spectrum.meta.sample_id,
        feature_schema_version=spectrum.meta.feature_schema_version,
        feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        feature_names=tone_set.feature_names,
        values=normalized.values,
        valid_mask=normalized.valid_mask,
        units=(normalized.units,) * len(tone_set.tones),
        source_measurement_mode=spectrum.meta.measurement_mode,
        source_representation=spectrum.representation,
        preprocessing_id=preprocessing_id,
        meta=spectrum.meta,
        tone_set_id=tone_set.tone_set_id,
        tone_set_sha256=tone_set.tone_set_sha256,
        tone_schema_id=tone_schema_id,
        normalization_method=normalized.method,
        source_magnitude_quantity=spectrum.magnitude_quantity,
        source_magnitude_reference=spectrum.magnitude_reference,
        source_phase_status=spectrum.phase_status,
        source_qc_status=measurement_qc.aggregate_status,
        source_qc_sha256=measurement_qc_sha256(measurement_qc),
        source_qc_warning_reasons=measurement_qc.warning_reasons,
        source_qc_exclude_candidate_reasons=(
            measurement_qc.exclude_candidate_reasons
        ),
        source_qc_unavailable_checks=measurement_qc.unavailable_checks,
        source_qc_eligible_for_downstream=measurement_qc.eligible_for_downstream,
    )
    return ToneFeatureProcessingResult(
        sample_id=spectrum.meta.sample_id,
        feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        processing_status="completed",
        feature_set=feature,
        preprocessing_id=preprocessing_id,
        tone_schema_id=tone_schema_id,
        extraction_records=records,
        failures=(),
        dense_preprocessing_id=dense.preprocessing_id,
        normalization=normalized,
        run_purpose=measurement_qc.run_purpose.value,
    )


def _validate_multisine_tone_linkage(
    spectrum: SpectrumData,
    tone_set: ToneSetDefinition,
) -> list[Mapping[str, Any]]:
    if spectrum.representation is not Representation.SPARSE_TONES:
        raise ToneFeatureConstructionError(
            "multisine tone features require sparse_tones SpectrumData"
        )
    if spectrum.meta.measurement_mode is not MeasurementMode.SCHROEDER_MULTISINE:
        raise ToneFeatureConstructionError(
            "multisine tone features require schroeder_multisine metadata"
        )
    if spectrum.meta.tone_set_id != tone_set.tone_set_id:
        raise ToneFeatureConstructionError("SpectrumData tone_set_id mismatch")
    metrics = spectrum.quality_metrics.get("tone_set")
    if not isinstance(metrics, Mapping):
        raise ToneFeatureConstructionError("P8 tone-set quality metrics are missing")
    expected = {
        "tone_set_id": tone_set.tone_set_id,
        "tone_set_sha256": tone_set.tone_set_sha256,
        "tones_sha256": tone_set.tones_sha256,
        "verified_artifacts": True,
    }
    mismatched = [name for name, value in expected.items() if metrics.get(name) != value]
    if mismatched:
        raise ToneFeatureConstructionError(
            "P8 tone-set linkage mismatch: " + ", ".join(mismatched)
        )
    quality = spectrum.quality_metrics.get("tone_quality")
    if not isinstance(quality, list) or len(quality) != spectrum.frequency_hz.size:
        raise ToneFeatureConstructionError(
            "P8 tone_quality must contain one record per sparse tone"
        )
    for frequency, record in zip(spectrum.frequency_hz, quality, strict=True):
        if not isinstance(record, Mapping) or float(record.get("frequency_hz", np.nan)) != frequency:
            raise ToneFeatureConstructionError(
                "P8 tone_quality order does not match sparse SpectrumData"
            )
    return quality


def build_multisine_tone_feature_set(
    spectrum: SpectrumData,
    measurement_qc: MeasurementQCResult,
    tone_set: ToneSetDefinition,
    matched_config: Mapping[str, Any],
) -> ToneFeatureProcessingResult:
    """Align P8 sparse tones to authority without interpolation or densification."""
    quality = _validate_multisine_tone_linkage(spectrum, tone_set)
    values = np.full(len(tone_set.tones), np.nan, dtype=np.float64)
    mask = np.zeros(len(tone_set.tones), dtype=bool)
    records: list[ToneExtractionRecord] = []
    source_index = 0
    for tone, feature_name in zip(
        tone_set.tones,
        tone_set.feature_names,
        strict=True,
    ):
        if (
            source_index < spectrum.frequency_hz.size
            and spectrum.frequency_hz[source_index] < tone.frequency_hz
        ):
            raise ToneFeatureConstructionError(
                "sparse SpectrumData contains a frequency not in authoritative tone set"
            )
        if (
            source_index >= spectrum.frequency_hz.size
            or spectrum.frequency_hz[source_index] > tone.frequency_hz
        ):
            records.append(
                ToneExtractionRecord(
                    tone_index=tone.tone_index,
                    frequency_hz=tone.frequency_hz,
                    feature_name=feature_name,
                    method="direct_sparse_tone_alignment",
                    valid=False,
                    value_db=None,
                    reason="tone_missing_from_sparse_spectrum",
                )
            )
            continue
        source_quality = quality[source_index]
        is_valid = bool(spectrum.valid_mask[source_index])
        value = float(spectrum.magnitude_db[source_index]) if is_valid else None
        if is_valid:
            values[tone.tone_index] = float(spectrum.magnitude_db[source_index])
            mask[tone.tone_index] = True
        reasons = source_quality.get("reasons", [])
        reason = None if is_valid else (
            "p8_tone_invalid"
            if not reasons
            else "p8_tone_invalid:" + "|".join(str(item) for item in reasons)
        )
        records.append(
            ToneExtractionRecord(
                tone_index=tone.tone_index,
                frequency_hz=tone.frequency_hz,
                feature_name=feature_name,
                method="direct_sparse_tone_alignment",
                valid=is_valid,
                value_db=value,
                reason=reason,
                source_indices=(source_index,),
                source_frequency_hz=(tone.frequency_hz,),
                source_weights=(1.0,),
            )
        )
        source_index += 1
    if source_index != spectrum.frequency_hz.size:
        raise ToneFeatureConstructionError(
            "sparse SpectrumData contains a frequency not in authoritative tone set"
        )

    normalization_config = matched_config["normalization"]
    tone_schema_id = _tone_schema_id(tone_set, normalization_config)
    preprocessing_id = _canonical_hash(
        {
            "schema_version": matched_config["schema_version"],
            "feature_kind": FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE.value,
            "source_stage": "P8_sparse_tones_direct",
            "tone_set_sha256": tone_set.tone_set_sha256,
            "normalization": dict(normalization_config),
        }
    )
    try:
        normalized = normalize_tone_values(values, mask, normalization_config)
    except ToneFeatureConstructionError as exc:
        return ToneFeatureProcessingResult(
            sample_id=spectrum.meta.sample_id,
            feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
            processing_status="failed",
            feature_set=None,
            preprocessing_id=preprocessing_id,
            tone_schema_id=tone_schema_id,
            extraction_records=tuple(records),
            failures=(str(exc),),
            dense_preprocessing_id=None,
            normalization=None,
            run_purpose=measurement_qc.run_purpose.value,
        )
    feature = FeatureSet(
        sample_id=spectrum.meta.sample_id,
        feature_schema_version=spectrum.meta.feature_schema_version,
        feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
        feature_names=tone_set.feature_names,
        values=normalized.values,
        valid_mask=normalized.valid_mask,
        units=(normalized.units,) * len(tone_set.tones),
        source_measurement_mode=spectrum.meta.measurement_mode,
        source_representation=spectrum.representation,
        preprocessing_id=preprocessing_id,
        meta=spectrum.meta,
        tone_set_id=tone_set.tone_set_id,
        tone_set_sha256=tone_set.tone_set_sha256,
        tone_schema_id=tone_schema_id,
        normalization_method=normalized.method,
        source_magnitude_quantity=spectrum.magnitude_quantity,
        source_magnitude_reference=spectrum.magnitude_reference,
        source_phase_status=spectrum.phase_status,
        reliability_weights=None,
        reliability_weight_source=None,
        source_qc_status=measurement_qc.aggregate_status,
        source_qc_sha256=measurement_qc_sha256(measurement_qc),
        source_qc_warning_reasons=measurement_qc.warning_reasons,
        source_qc_exclude_candidate_reasons=(
            measurement_qc.exclude_candidate_reasons
        ),
        source_qc_unavailable_checks=measurement_qc.unavailable_checks,
        source_qc_eligible_for_downstream=measurement_qc.eligible_for_downstream,
    )
    return ToneFeatureProcessingResult(
        sample_id=spectrum.meta.sample_id,
        feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
        processing_status="completed",
        feature_set=feature,
        preprocessing_id=preprocessing_id,
        tone_schema_id=tone_schema_id,
        extraction_records=tuple(records),
        failures=(),
        dense_preprocessing_id=None,
        normalization=normalized,
        run_purpose=measurement_qc.run_purpose.value,
    )


def assert_matched_tone_schema(
    sweep_feature_set: FeatureSet,
    multisine_feature_set: FeatureSet,
) -> None:
    """Reject cross-mode tone features that do not share one exact schema."""
    if sweep_feature_set.feature_kind is not FeatureKind.TONE_PROJECTION_FROM_SWEEP:
        raise ToneFeatureConstructionError("first FeatureSet is not a sweep projection")
    if multisine_feature_set.feature_kind is not FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE:
        raise ToneFeatureConstructionError("second FeatureSet is not a multisine measurement")
    comparisons = {
        "tone_set_id": (
            sweep_feature_set.tone_set_id,
            multisine_feature_set.tone_set_id,
        ),
        "tone_set_sha256": (
            sweep_feature_set.tone_set_sha256,
            multisine_feature_set.tone_set_sha256,
        ),
        "tone_schema_id": (
            sweep_feature_set.tone_schema_id,
            multisine_feature_set.tone_schema_id,
        ),
        "feature_names": (
            sweep_feature_set.feature_names,
            multisine_feature_set.feature_names,
        ),
        "units": (sweep_feature_set.units, multisine_feature_set.units),
        "normalization_method": (
            sweep_feature_set.normalization_method,
            multisine_feature_set.normalization_method,
        ),
        "feature_count": (
            sweep_feature_set.values.size,
            multisine_feature_set.values.size,
        ),
    }
    mismatched = [name for name, pair in comparisons.items() if pair[0] != pair[1]]
    if mismatched:
        raise ToneFeatureConstructionError(
            "matched tone FeatureSet schema mismatch: " + ", ".join(mismatched)
        )


def _reference_status(sweep: FeatureSet, multisine: FeatureSet) -> str:
    if sweep.source_magnitude_quantity != multisine.source_magnitude_quantity:
        return "quantity_mismatch"
    if (
        sweep.calibration_id
        and sweep.calibration_id == multisine.calibration_id
    ):
        return "shared_calibration"
    if (
        sweep.source_magnitude_reference
        and sweep.source_magnitude_reference
        == multisine.source_magnitude_reference
    ):
        return "compatible_reference"
    if (
        sweep.source_magnitude_reference is None
        or multisine.source_magnitude_reference is None
    ):
        return "reference_unavailable"
    return "reference_mismatch"


def build_matched_tone_view(
    sweep_result: ToneFeatureProcessingResult,
    multisine_result: ToneFeatureProcessingResult,
    matched_config: Mapping[str, Any],
) -> MatchedToneView:
    """Build a non-mutating common-tone view and physical-reference decision."""
    sweep = sweep_result.feature_set
    multisine = multisine_result.feature_set
    if sweep is None or multisine is None:
        raise ToneFeatureConstructionError(
            "matched tone view requires two successfully constructed FeatureSets"
        )
    assert_matched_tone_schema(sweep, multisine)
    common = np.asarray(sweep.valid_mask & multisine.valid_mask, dtype=bool)
    common.setflags(write=False)
    multisine_missing_count = sum(
        record.reason == "tone_missing_from_sparse_spectrum"
        for record in multisine_result.extraction_records
    )
    multisine_invalid_count = int(np.count_nonzero(~multisine.valid_mask))
    minimum = int(matched_config["matching"]["minimum_common_valid_tones"])
    common_count = int(np.count_nonzero(common))
    status = _reference_status(sweep, multisine)
    if sweep.normalization_method != "none":
        comparison = "normalized_shape_only_candidate"
        absolute = False
    elif status in {"compatible_reference", "shared_calibration"}:
        comparison = "absolute_comparable"
        absolute = True
    else:
        comparison = "independent_mode_only"
        absolute = False
    if common_count < minimum:
        processing_status = "failed"
        failure_reason = (
            f"common valid tone count {common_count} is below "
            f"minimum_common_valid_tones {minimum}"
        )
    else:
        processing_status = "completed"
        failure_reason = None
    return MatchedToneView(
        processing_status=processing_status,
        failure_reason=failure_reason,
        common_valid_mask=common,
        sweep_invalid_count=int(np.count_nonzero(~sweep.valid_mask)),
        multisine_missing_count=int(multisine_missing_count),
        multisine_other_invalid_count=(
            multisine_invalid_count - int(multisine_missing_count)
        ),
        common_valid_count=common_count,
        minimum_common_valid_tones=minimum,
        source_reference_status=status,
        comparison_status=comparison,
        cross_mode_absolute_comparable=absolute,
    )
