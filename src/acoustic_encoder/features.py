"""P3-A/P3-B construction of dense, sample-local FeatureSet objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from .preprocessing import (
    build_dense_grid,
    interpolate_dense_grid,
    preprocessing_id,
    smooth_dense_grid,
)
from .quality_control import MeasurementQCResult, measurement_qc_sha256
from .research_gate import enforce_research_gate
from .schemas import (
    FeatureKind,
    FeatureSet,
    MeasurementMeta,
    Representation,
    SpectrumData,
)


@dataclass(frozen=True, slots=True)
class FeatureProcessingFailure:
    feature_kind: FeatureKind
    reason: str
    message: str


@dataclass(frozen=True, slots=True)
class DenseFeatureProcessingResult:
    sample_id: str
    processing_status: str
    preprocessing_id: str
    grid_frequency_hz: np.ndarray
    feature_names: tuple[str, ...]
    feature_sets: Mapping[FeatureKind, FeatureSet]
    failures: tuple[FeatureProcessingFailure, ...]
    warnings: tuple[str, ...]
    valid_grid_fraction: float
    interpolated_valid_grid_fraction: float
    smoothing_definition: Mapping[str, object]
    measurement_qc: MeasurementQCResult
    magnitude_quantity: str
    magnitude_reference: str | None
    meta: MeasurementMeta
    preprocessing_config: Mapping[str, object]


_DENSE_FEATURE_KINDS = (
    FeatureKind.DENSE_RAW_SPL,
    FeatureKind.DENSE_DEMEANED_DB,
    FeatureKind.DENSE_ZSCORE,
)


def _fail_all(
    spectrum: SpectrumData,
    measurement_qc: MeasurementQCResult,
    grid_frequency_hz: np.ndarray,
    feature_names: tuple[str, ...],
    prep_id: str,
    valid_grid_fraction: float,
    interpolated_valid_grid_fraction: float,
    smoothing_definition: Mapping[str, object],
    preprocessing_config: Mapping[str, object],
    *,
    reason: str,
    message: str,
) -> DenseFeatureProcessingResult:
    return DenseFeatureProcessingResult(
        sample_id=spectrum.meta.sample_id,
        processing_status="failed",
        preprocessing_id=prep_id,
        grid_frequency_hz=grid_frequency_hz,
        feature_names=feature_names,
        feature_sets={},
        failures=tuple(
            FeatureProcessingFailure(kind, reason, message)
            for kind in _DENSE_FEATURE_KINDS
        ),
        warnings=(),
        valid_grid_fraction=valid_grid_fraction,
        interpolated_valid_grid_fraction=interpolated_valid_grid_fraction,
        smoothing_definition=smoothing_definition,
        measurement_qc=measurement_qc,
        magnitude_quantity=spectrum.magnitude_quantity,
        magnitude_reference=spectrum.magnitude_reference,
        meta=spectrum.meta,
        preprocessing_config=dict(preprocessing_config),
    )


def _feature(
    spectrum: SpectrumData,
    kind: FeatureKind,
    names: tuple[str, ...],
    values: np.ndarray,
    valid_mask: np.ndarray,
    units: str,
    prep_id: str,
    measurement_qc: MeasurementQCResult,
) -> FeatureSet:
    return FeatureSet(
        sample_id=spectrum.meta.sample_id,
        feature_schema_version=spectrum.meta.feature_schema_version,
        feature_kind=kind,
        feature_names=names,
        values=values,
        valid_mask=valid_mask,
        units=(units,) * len(names),
        source_measurement_mode=spectrum.meta.measurement_mode,
        source_representation=spectrum.representation,
        preprocessing_id=prep_id,
        meta=spectrum.meta,
        source_qc_status=measurement_qc.aggregate_status,
        source_qc_sha256=measurement_qc_sha256(measurement_qc),
        source_qc_warning_reasons=measurement_qc.warning_reasons,
        source_qc_exclude_candidate_reasons=(
            measurement_qc.exclude_candidate_reasons
        ),
        source_qc_unavailable_checks=measurement_qc.unavailable_checks,
        source_qc_eligible_for_downstream=(
            measurement_qc.eligible_for_downstream
        ),
    )


def build_dense_feature_sets(
    spectrum: SpectrumData,
    measurement_qc: MeasurementQCResult,
    preprocessing_config: Mapping[str, object],
) -> DenseFeatureProcessingResult:
    """Build the three dense features without reading source artifacts."""
    if spectrum.representation is not Representation.DENSE_SPECTRUM:
        raise ValueError("Dense P3 supports only dense_spectrum input")
    qc_linkage = {
        "sample_id": (
            measurement_qc.sample_id,
            spectrum.meta.sample_id,
        ),
        "measurement_mode": (
            measurement_qc.measurement_mode,
            spectrum.meta.measurement_mode,
        ),
        "data_origin": (
            measurement_qc.data_origin,
            spectrum.meta.data_origin,
        ),
        "dataset_role": (
            measurement_qc.dataset_role,
            spectrum.meta.dataset_role,
        ),
        "human_valid": (
            measurement_qc.human_valid,
            spectrum.meta.valid,
        ),
        "human_exclusion_reason": (
            measurement_qc.human_exclusion_reason,
            spectrum.meta.exclusion_reason,
        ),
        "manual_review_reasons": (
            measurement_qc.manual_review_reasons,
            spectrum.meta.manual_review_reasons,
        ),
    }
    mismatched = [
        name for name, (qc_value, meta_value) in qc_linkage.items()
        if qc_value != meta_value
    ]
    if mismatched:
        raise ValueError(
            "MeasurementQCResult does not correspond to SpectrumData: "
            + ", ".join(mismatched)
        )
    enforce_research_gate(measurement_qc.run_purpose, [spectrum.meta])
    grid = build_dense_grid(preprocessing_config)
    prep_id = preprocessing_id(preprocessing_config)
    interpolated_values, interpolated_mask = interpolate_dense_grid(
        spectrum.frequency_hz,
        spectrum.magnitude_db,
        spectrum.valid_mask,
        grid.frequency_hz,
        method=str(preprocessing_config["interpolation"]),
        maximum_gap_hz=float(
            preprocessing_config["maximum_interpolation_gap_hz"]
        ),
    )
    interpolated_fraction = float(np.mean(interpolated_mask))
    smoothing_result = smooth_dense_grid(
        grid.frequency_hz,
        interpolated_values,
        interpolated_mask,
        preprocessing_config,
    )
    values = smoothing_result.values_db
    valid_mask = smoothing_result.valid_mask
    valid_fraction = float(np.mean(valid_mask))
    minimum_fraction = float(preprocessing_config["minimum_valid_grid_fraction"])
    if valid_fraction < minimum_fraction:
        return _fail_all(
            spectrum,
            measurement_qc,
            grid.frequency_hz,
            grid.feature_names,
            prep_id,
            valid_fraction,
            interpolated_fraction,
            smoothing_result.definition,
            preprocessing_config,
            reason="minimum_valid_grid_fraction_not_met",
            message=(
                f"valid grid fraction {valid_fraction:g} is below configured "
                f"minimum {minimum_fraction:g}"
            ),
        )

    feature_sets: dict[FeatureKind, FeatureSet] = {}
    failures: list[FeatureProcessingFailure] = []
    if spectrum.magnitude_quantity == "spl":
        feature_sets[FeatureKind.DENSE_RAW_SPL] = _feature(
            spectrum,
            FeatureKind.DENSE_RAW_SPL,
            grid.feature_names,
            values,
            valid_mask,
            "dB",
            prep_id,
            measurement_qc,
        )
    else:
        failures.append(
            FeatureProcessingFailure(
                FeatureKind.DENSE_RAW_SPL,
                "raw_spl_requires_spl_quantity",
                "dense_raw_spl requires source magnitude_quantity='spl'; "
                f"received {spectrum.magnitude_quantity!r}",
            )
        )

    normalization_low, normalization_high = (
        float(value) for value in preprocessing_config["normalization_band_hz"]  # type: ignore[index]
    )
    normalization_mask = (
        valid_mask
        & (grid.frequency_hz >= normalization_low)
        & (grid.frequency_hz <= normalization_high)
    )
    minimum_points = int(preprocessing_config["minimum_normalization_points"])
    normalization_count = int(np.count_nonzero(normalization_mask))
    if normalization_count < minimum_points:
        message = (
            f"normalization valid point count {normalization_count} is below "
            f"configured minimum {minimum_points}"
        )
        failures.extend(
            FeatureProcessingFailure(
                kind,
                "minimum_normalization_points_not_met",
                message,
            )
            for kind in (
                FeatureKind.DENSE_DEMEANED_DB,
                FeatureKind.DENSE_ZSCORE,
            )
        )
        return DenseFeatureProcessingResult(
            sample_id=spectrum.meta.sample_id,
            processing_status="partial_failure" if feature_sets else "failed",
            preprocessing_id=prep_id,
            grid_frequency_hz=grid.frequency_hz,
            feature_names=grid.feature_names,
            feature_sets=feature_sets,
            failures=tuple(failures),
            warnings=(
                () if valid_fraction == 1.0 else ("partial_grid_coverage",)
            ),
            valid_grid_fraction=valid_fraction,
            interpolated_valid_grid_fraction=interpolated_fraction,
            smoothing_definition=smoothing_result.definition,
            measurement_qc=measurement_qc,
            magnitude_quantity=spectrum.magnitude_quantity,
            magnitude_reference=spectrum.magnitude_reference,
            meta=spectrum.meta,
            preprocessing_config=dict(preprocessing_config),
        )

    mean_db = float(np.mean(values[normalization_mask]))
    std_db = float(np.std(values[normalization_mask], ddof=0))
    demeaned = values - mean_db
    feature_sets[FeatureKind.DENSE_DEMEANED_DB] = _feature(
        spectrum,
        FeatureKind.DENSE_DEMEANED_DB,
        grid.feature_names,
        demeaned,
        valid_mask,
        "dB",
        prep_id,
        measurement_qc,
    )
    minimum_std_db = float(preprocessing_config["minimum_zscore_std_db"])
    if std_db < minimum_std_db:
        failures.append(
            FeatureProcessingFailure(
                FeatureKind.DENSE_ZSCORE,
                "zscore_standard_deviation_too_small",
                f"normalization std {std_db:g} dB is below configured "
                f"minimum {minimum_std_db:g} dB",
            )
        )
    else:
        feature_sets[FeatureKind.DENSE_ZSCORE] = _feature(
            spectrum,
            FeatureKind.DENSE_ZSCORE,
            grid.feature_names,
            demeaned / std_db,
            valid_mask,
            "dimensionless",
            prep_id,
            measurement_qc,
        )
    return DenseFeatureProcessingResult(
        sample_id=spectrum.meta.sample_id,
        processing_status="partial_failure" if failures else "completed",
        preprocessing_id=prep_id,
        grid_frequency_hz=grid.frequency_hz,
        feature_names=grid.feature_names,
        feature_sets=feature_sets,
        failures=tuple(failures),
        warnings=(() if valid_fraction == 1.0 else ("partial_grid_coverage",)),
        valid_grid_fraction=valid_fraction,
        interpolated_valid_grid_fraction=interpolated_fraction,
        smoothing_definition=smoothing_result.definition,
        measurement_qc=measurement_qc,
        magnitude_quantity=spectrum.magnitude_quantity,
        magnitude_reference=spectrum.magnitude_reference,
        meta=spectrum.meta,
        preprocessing_config=dict(preprocessing_config),
    )
