"""Explicit-file package build and single-readout entry points for P9-D."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .config import load_config
from .dataset_quality_control import feature_set_content_sha256
from .direction_models import fit_frozen_direction_model
from .offline_readout import (
    FrozenReadoutPackage, OfflineReadoutError, ReadoutInputReference,
    canonical_sha256, normalize_sha256, run_offline_readout,
)
from .offline_readout_outputs import (
    load_readout_package_bundle, write_offline_readout_failure_outputs,
    write_offline_readout_outputs, write_readout_package,
)
from .quality_control import MeasurementQCResult
from .schemas import FeatureKind, artifact_sha256, load_feature_set, load_spectrum
from .tone_sets import load_tone_set
from .version import CONFIG_SCHEMA_VERSION, FEATURE_SCHEMA_VERSION, MEASUREMENT_SCHEMA_VERSION, PIPELINE_VERSION


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OfflineReadoutError(f"JSON root must be an object: {path}")
    return value


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _exact_hash(path: Path) -> str:
    return normalize_sha256(artifact_sha256(path))


def _verify_declared(path: Path, declared: str, label: str) -> str:
    if not path.is_file():
        raise OfflineReadoutError(f"missing explicit {label}: {path}")
    actual = _exact_hash(path)
    if actual != normalize_sha256(declared):
        raise OfflineReadoutError(f"{label} hash mismatch")
    return actual


def build_readout_package_from_manifest(
    config_path: str | Path,
    training_manifest_path: str | Path,
    output_directory: str | Path,
    *,
    default_config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Fit and persist one full-scope model from explicit non-final FeatureSets."""
    config = load_config(config_path, default_path=default_config_path)
    policy = config["offline_fast_readout"]
    if not policy["enabled"]:
        raise OfflineReadoutError("offline_fast_readout must be explicitly enabled to build a package")
    manifest_path = Path(training_manifest_path).resolve()
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != "1.0.0":
        raise OfflineReadoutError("readout training manifest schema must be 1.0.0")
    base = manifest_path.parent
    stimulus_path = _resolve(base, str(manifest["stimulus_manifest_path"]))
    _verify_declared(stimulus_path, str(manifest["stimulus_manifest_file_sha256"]), "stimulus manifest")
    stimulus = _read_json(stimulus_path)
    tone_set = load_tone_set(stimulus_path)
    entries = manifest.get("training_features")
    if not isinstance(entries, list) or not entries:
        raise OfflineReadoutError("explicit training_features are required")
    features = []
    roles: list[str] = []
    content_hashes: list[str] = []
    for entry in entries:
        role = str(entry["cohort_role"])
        if role not in {"development", "training"}:
            raise OfflineReadoutError("final_test and non-training roles are forbidden in package training")
        base_path = _resolve(base, str(entry["feature_base_path"]))
        json_path, npz_path = base_path.with_suffix(".json"), base_path.with_suffix(".npz")
        _verify_declared(json_path, str(entry["feature_json_sha256"]), "training FeatureSet JSON")
        _verify_declared(npz_path, str(entry["feature_npz_sha256"]), "training FeatureSet NPZ")
        feature = load_feature_set(base_path)
        content_hash = feature_set_content_sha256(feature)
        if content_hash != str(entry["feature_content_sha256"]):
            raise OfflineReadoutError("training FeatureSet content hash mismatch")
        if feature.sample_id != str(entry["sample_id"]):
            raise OfflineReadoutError("training FeatureSet sample ID mismatch")
        features.append(feature)
        roles.append(role)
        content_hashes.append(content_hash)
    first = features[0]
    expected_kind = FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
    for feature in features:
        if feature.feature_kind is not expected_kind or feature.source_measurement_mode.value != "schroeder_multisine":
            raise OfflineReadoutError("package training requires multisine matched-tone FeatureSets")
        if (
            feature.feature_names != first.feature_names or feature.units != first.units
            or feature.preprocessing_id != first.preprocessing_id
            or feature.tone_set_id != tone_set.tone_set_id
            or normalize_sha256(feature.tone_set_sha256 or "") != normalize_sha256(tone_set.tone_set_sha256)
        ):
            raise OfflineReadoutError("training FeatureSet contracts are incompatible")
        if not np.all(feature.valid_mask):
            raise OfflineReadoutError("frozen training requires every preregistered feature to be valid")
    authority_entries = manifest.get("authority_files")
    if not isinstance(authority_entries, Mapping) or set(authority_entries) != {"p2b", "p4b", "p5", "p9a", "p9b"}:
        raise OfflineReadoutError("exact P2-B/P4-B/P5/P9-A/P9-B authority files are required")
    authority_hashes: dict[str, str] = {}
    for name, entry in authority_entries.items():
        path = _resolve(base, str(entry["path"]))
        authority_hashes[str(name)] = _verify_declared(path, str(entry["sha256"]), f"{name} authority")
        authority = _read_json(path)
        if authority.get("lifecycle") not in {"software_validation_only", "software_validation_candidate"}:
            raise OfflineReadoutError(f"{name} authority lifecycle is not valid for software validation")
        if authority.get("final_test_read") is not False or authority.get("scientifically_eligible") is not False or authority.get("deployment_eligible") is not False:
            raise OfflineReadoutError(f"{name} authority exceeds the package lifecycle")
        if tuple(authority.get("explicit_training_sample_ids", ())) != tuple(feature.sample_id for feature in features):
            raise OfflineReadoutError(f"{name} authority training scope mismatch")
        if name in {"p9a", "p9b"} and tuple(float(item) for item in authority.get("selected_tone_frequencies_hz", ())) != tuple(float(item) for item in tone_set.frequency_hz):
            raise OfflineReadoutError(f"{name} tone authority mismatch")
    sealed_ids = tuple(str(item) for item in manifest.get("sealed_final_test_sample_ids", ()))
    sealed_hash = str(manifest["sealed_final_test_sha256"])
    if canonical_sha256({"ordered_sample_ids": list(sealed_ids)}) != sealed_hash:
        raise OfflineReadoutError("sealed final-test hash mismatch")
    if set(sealed_ids) & {feature.sample_id for feature in features}:
        raise OfflineReadoutError("final_test sample entered package training")
    model = fit_frozen_direction_model(
        model_id=str(policy["model"]["model_id"]),
        x_train=np.vstack([feature.values for feature in features]),
        y_train=np.asarray([feature.meta.angle_deg for feature in features], dtype=np.float64),
        direction_order=tuple(float(item) for item in manifest["direction_order_deg"]),
        feature_names=first.feature_names, units=first.units,
        training_sample_ids=tuple(feature.sample_id for feature in features), training_roles=tuple(roles),
        training_feature_sha256s=tuple(content_hashes), feature_kind=first.feature_kind.value,
        preprocessing_id=first.preprocessing_id, tone_set_id=str(first.tone_set_id),
        tone_set_sha256=normalize_sha256(str(first.tone_set_sha256)),
        normalization_method=str(first.normalization_method),
        magnitude_quantity=str(first.source_magnitude_quantity),
        magnitude_reference=first.source_magnitude_reference,
        model_domain=str(policy["model"]["model_domain"]), authority_hashes=authority_hashes,
        sealed_final_test_sample_ids=sealed_ids, sealed_final_test_sha256=sealed_hash,
        random_state=int(config["random_state"]),
    )
    package = FrozenReadoutPackage.create(
        package_id=str(manifest["package_id"]), created_utc=str(manifest["created_utc"]),
        stimulus_id=str(stimulus["stimulus_id"]),
        stimulus_waveform_sha256=normalize_sha256(str(stimulus["waveform_sha256"])),
        stimulus_manifest_file_sha256=_exact_hash(stimulus_path),
        stimulus_manifest_semantic_sha256=canonical_sha256(stimulus), tone_set=tone_set,
        model=model, matched_tone_config=config["matched_tone_features"],
        qc_policy=policy["qc"], authority_hashes=authority_hashes,
        pipeline_version=PIPELINE_VERSION, config_schema_version=CONFIG_SCHEMA_VERSION,
        measurement_schema_version=MEASUREMENT_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        stable_period_count=int(stimulus["stable_period_count"]),
        discard_initial_period_count=int(stimulus["discard_initial_period_count"]),
    )
    normalized_manifest = {
        **manifest,
        "training_features": [
            {**dict(entry), "feature_content_sha256": digest}
            for entry, digest in zip(entries, content_hashes, strict=True)
        ],
        "authority_hashes": authority_hashes,
        "final_test_files_read": [],
        "source_manifest_sha256": _exact_hash(manifest_path),
    }
    return write_readout_package(output_directory, package, model, package_input_manifest=normalized_manifest)


def _execute_offline_readout_from_manifest(
    package_directory: str | Path,
    input_manifest_path: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Load one explicit persisted P8 input and run inference without fitting."""
    package, model, _ = load_readout_package_bundle(package_directory)
    path = Path(input_manifest_path).resolve()
    manifest = _read_json(path)
    if manifest.get("schema_version") != "1.0.0":
        raise OfflineReadoutError("readout input manifest schema must be 1.0.0")
    base = path.parent
    spectrum_base = _resolve(base, str(manifest["spectrum_base_path"]))
    files = {
        "spectrum_json_sha256": spectrum_base.with_suffix(".json"),
        "spectrum_npz_sha256": spectrum_base.with_suffix(".npz"),
        "p8_manifest_sha256": _resolve(base, str(manifest["p8_manifest_path"])),
        "tone_quality_sha256": _resolve(base, str(manifest["tone_quality_path"])),
        "measurement_qc_sha256": _resolve(base, str(manifest["measurement_qc_path"])),
        "metadata_sha256": _resolve(base, str(manifest["metadata_path"])),
    }
    actual: dict[str, str] = {}
    for name, file_path in files.items():
        actual[name] = _verify_declared(file_path, str(manifest[name]), name)
    stimulus_path = _resolve(base, str(manifest["stimulus_manifest_path"]))
    if _exact_hash(stimulus_path) != package.stimulus_manifest_file_sha256:
        raise OfflineReadoutError("input stimulus manifest hash mismatch")
    spectrum = load_spectrum(spectrum_base)
    qc = MeasurementQCResult.from_dict(_read_json(files["measurement_qc_sha256"]))
    tone_set = load_tone_set(stimulus_path)
    reference = ReadoutInputReference(
        "1.0.0", spectrum.meta.sample_id, actual["spectrum_json_sha256"],
        actual["spectrum_npz_sha256"], actual["p8_manifest_sha256"],
        actual["tone_quality_sha256"], actual["measurement_qc_sha256"], actual["metadata_sha256"],
    )
    result = run_offline_readout(
        spectrum, qc, tone_set, package.p3_preprocessing_snapshot, package, model, reference,
        calibration_model=None,
    )
    return write_offline_readout_outputs(output_directory, result)


def execute_offline_readout_from_manifest(
    package_directory: str | Path,
    input_manifest_path: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Run one readout and retain a blocked audit if pre-core verification fails."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"offline readout output already exists: {output}")
    evidence = {
        "package_directory": Path(package_directory).resolve().as_posix(),
        "input_manifest_path": Path(input_manifest_path).resolve().as_posix(),
    }
    input_path = Path(input_manifest_path).resolve()
    if input_path.is_file():
        evidence["input_manifest_sha256"] = _exact_hash(input_path)
    try:
        return _execute_offline_readout_from_manifest(
            package_directory, input_manifest_path, output_directory,
        )
    except FileExistsError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as exc:
        return write_offline_readout_failure_outputs(
            output, reason=f"{type(exc).__name__}:{exc}", input_evidence=evidence,
        )
