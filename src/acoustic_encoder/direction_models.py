"""Shared P5 direction-model semantics and explicit frozen inference models."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


FROZEN_DIRECTION_MODEL_SCHEMA_VERSION = "1.0.0"


class DirectionModelError(ValueError):
    """Raised when a direction model cannot be fitted, trusted, or applied."""


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _require_sha256(value: str, label: str) -> str:
    digest = str(value).removeprefix("sha256:")
    if not str(value).startswith("sha256:") or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise DirectionModelError(f"{label} must be sha256:<lowercase digest>")
    return str(value)


def _rank(
    scores: NDArray[np.float64],
    labels: NDArray[np.float64],
    direction_order: tuple[float, ...],
    *,
    higher_better: bool,
) -> tuple[float, float | None, float, float | None, float | None]:
    order_index = {angle: index for index, angle in enumerate(direction_order)}
    indices = sorted(
        range(len(labels)),
        key=lambda i: ((-scores[i] if higher_better else scores[i]), order_index[float(labels[i])]),
    )
    first, second = indices[0], (indices[1] if len(indices) > 1 else None)
    second_score = None if second is None else float(scores[second])
    margin = None if second is None else float(
        (scores[first] - scores[second]) if higher_better else (scores[second] - scores[first])
    )
    return float(labels[first]), (None if second is None else float(labels[second])), float(scores[first]), second_score, margin


def predict_direction_arrays(
    model_id: str,
    x_train: NDArray[np.float64],
    y_train: NDArray[np.float64],
    x_test: NDArray[np.float64],
    direction_order: tuple[float, ...],
    random_state: int,
) -> list[tuple[float, float | None, float, float | None]]:
    """Apply the authoritative P5 fold-local semantics to numeric arrays."""
    train = np.asarray(x_train, dtype=np.float64)
    labels_train = np.asarray(y_train, dtype=np.float64)
    test = np.asarray(x_test, dtype=np.float64)
    labels = np.asarray([angle for angle in direction_order if angle in set(labels_train)], dtype=float)
    if model_id == "nearest_template_correlation":
        templates = np.vstack([np.mean(train[labels_train == label], axis=0) for label in labels])
        if np.any(np.std(templates, axis=1) <= 0):
            raise DirectionModelError("constant_training_template")
        output = []
        for row in test:
            if np.std(row) <= 0:
                raise DirectionModelError("constant_test_vector")
            scores = np.asarray([np.corrcoef(row, template)[0, 1] for template in templates])
            ranked = _rank(scores, labels, direction_order, higher_better=True)
            output.append((ranked[0], ranked[1], ranked[2], ranked[4]))
        return output
    scaler = StandardScaler().fit(train)
    transformed_train = scaler.transform(train)
    transformed_test = scaler.transform(test)
    if model_id == "nearest_centroid":
        centroids = np.vstack([np.mean(transformed_train[labels_train == label], axis=0) for label in labels])
        output = []
        for row in transformed_test:
            ranked = _rank(np.linalg.norm(centroids - row, axis=1), labels, direction_order, higher_better=False)
            output.append((ranked[0], ranked[1], ranked[2], ranked[4]))
        return output
    if model_id != "logistic_regression":
        raise DirectionModelError("unsupported direction model")
    classifier = LogisticRegression(
        solver="lbfgs", C=1.0, max_iter=1000, class_weight="balanced", random_state=random_state
    ).fit(transformed_train, labels_train)
    output = []
    for row in classifier.predict_proba(transformed_test):
        ranked = _rank(row, classifier.classes_.astype(float), direction_order, higher_better=True)
        output.append((ranked[0], ranked[1], ranked[2], ranked[4]))
    return output


@dataclass(frozen=True, slots=True)
class RankedDirectionPrediction:
    predicted_direction_deg: float
    second_direction_deg: float | None
    score: float
    second_score: float | None
    margin: float | None
    score_kind: str
    higher_is_better: bool


@dataclass(frozen=True, slots=True)
class FrozenDirectionModel:
    schema_version: str
    model_id: str
    model_role: str
    lifecycle: str
    model_domain: str
    direction_order_deg: tuple[float, ...]
    feature_names: tuple[str, ...]
    units: tuple[str, ...]
    feature_kind: str
    preprocessing_id: str
    tone_set_id: str
    tone_set_sha256: str
    normalization_method: str
    magnitude_quantity: str
    magnitude_reference: str | None
    valid_mask_policy: str
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    centroids: tuple[tuple[float, ...], ...]
    training_sample_ids: tuple[str, ...]
    training_roles: tuple[str, ...]
    training_feature_sha256s: tuple[str, ...]
    training_aggregate_sha256: str
    authority_hashes: Mapping[str, str]
    sealed_final_test_sample_ids: tuple[str, ...]
    sealed_final_test_sha256: str
    final_test_read: bool
    score_kind: str
    higher_is_better: bool
    tie_break: str
    random_state: int
    scientifically_eligible: bool
    deployment_eligible: bool

    def __post_init__(self) -> None:
        if self.schema_version != FROZEN_DIRECTION_MODEL_SCHEMA_VERSION:
            raise DirectionModelError("FrozenDirectionModel schema_version must be 1.0.0")
        if self.model_role != "frozen_inference":
            raise DirectionModelError("FrozenDirectionModel model_role must be frozen_inference")
        if self.model_id != "nearest_centroid":
            raise DirectionModelError("DEV-C15 freezes only the preregistered nearest_centroid model")
        if self.lifecycle != "software_validation_only" or self.model_domain not in {"multisine", "sweep_projection"}:
            raise DirectionModelError("unsupported frozen-model lifecycle or domain")
        if self.final_test_read or self.scientifically_eligible or self.deployment_eligible:
            raise DirectionModelError("simulated frozen model cannot read final_test or claim science/deployment")
        if not self.direction_order_deg or len(set(self.direction_order_deg)) != len(self.direction_order_deg):
            raise DirectionModelError("direction order must be non-empty and unique")
        count = len(self.feature_names)
        if not count or len(self.units) != count or len(self.scaler_mean) != count or len(self.scaler_scale) != count:
            raise DirectionModelError("frozen model feature arrays must align")
        if len(self.centroids) != len(self.direction_order_deg) or any(len(row) != count for row in self.centroids):
            raise DirectionModelError("frozen model centroids must align with directions and features")
        if any(not np.isfinite(value) for value in (*self.scaler_mean, *self.scaler_scale)) or any(value <= 0 for value in self.scaler_scale):
            raise DirectionModelError("frozen scaler parameters must be finite with positive scales")
        if any(not np.isfinite(value) for row in self.centroids for value in row):
            raise DirectionModelError("frozen centroids must be finite")
        if not self.training_sample_ids or not (
            len(self.training_sample_ids) == len(self.training_roles) == len(self.training_feature_sha256s)
        ):
            raise DirectionModelError("training membership arrays must align")
        if any(role not in {"development", "training"} for role in self.training_roles):
            raise DirectionModelError("final_test and non-training roles are forbidden in frozen model training")
        for index, digest in enumerate(self.training_feature_sha256s):
            _require_sha256(digest, f"training_feature_sha256s[{index}]")
        _require_sha256(self.training_aggregate_sha256, "training_aggregate_sha256")
        _require_sha256(self.preprocessing_id, "preprocessing_id")
        _require_sha256(self.tone_set_sha256, "tone_set_sha256")
        _require_sha256(self.sealed_final_test_sha256, "sealed_final_test_sha256")
        for name, digest in self.authority_hashes.items():
            _require_sha256(digest, f"authority_hashes.{name}")
        if self.valid_mask_policy != "require_all_frozen_features" or self.score_kind != "euclidean_distance" or self.higher_is_better:
            raise DirectionModelError("frozen nearest-centroid inference semantics are fixed")
        if self.tie_break != "configured_direction_order":
            raise DirectionModelError("unsupported tie-break policy")

    def _semantic_payload(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        for name in (
            "direction_order_deg", "feature_names", "units", "scaler_mean", "scaler_scale",
            "training_sample_ids", "training_roles", "training_feature_sha256s",
            "sealed_final_test_sample_ids",
        ):
            payload[name] = list(payload[name])
        payload["centroids"] = [list(row) for row in self.centroids]
        payload["authority_hashes"] = dict(sorted(self.authority_hashes.items()))
        return payload

    @property
    def semantic_sha256(self) -> str:
        return _canonical_sha256(self._semantic_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self._semantic_payload()
        payload["model_semantic_sha256"] = self.semantic_sha256
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FrozenDirectionModel":
        value = dict(payload)
        expected = value.pop("model_semantic_sha256", None)
        tuple_fields = (
            "direction_order_deg", "feature_names", "units", "scaler_mean", "scaler_scale",
            "training_sample_ids", "training_roles", "training_feature_sha256s", "sealed_final_test_sample_ids",
        )
        for name in tuple_fields:
            value[name] = tuple(value[name])
        value["centroids"] = tuple(tuple(row) for row in value["centroids"])
        value["authority_hashes"] = dict(value["authority_hashes"])
        result = cls(**value)
        if expected is not None and expected != result.semantic_sha256:
            raise DirectionModelError("frozen direction model semantic hash mismatch")
        return result


def fit_frozen_direction_model(
    *,
    model_id: str,
    x_train: NDArray[np.float64],
    y_train: NDArray[np.float64],
    direction_order: Sequence[float],
    feature_names: Sequence[str],
    units: Sequence[str],
    training_sample_ids: Sequence[str],
    training_roles: Sequence[str],
    training_feature_sha256s: Sequence[str],
    feature_kind: str,
    preprocessing_id: str,
    tone_set_id: str,
    tone_set_sha256: str,
    normalization_method: str,
    magnitude_quantity: str,
    magnitude_reference: str | None,
    model_domain: str,
    authority_hashes: Mapping[str, str],
    sealed_final_test_sample_ids: Sequence[str],
    sealed_final_test_sha256: str,
    random_state: int,
) -> FrozenDirectionModel:
    """Fit one preregistered full-scope inference model outside CV evaluation."""
    if model_id != "nearest_centroid":
        raise DirectionModelError("DEV-C15 supports freezing only nearest_centroid")
    roles = tuple(str(item) for item in training_roles)
    if any(role not in {"development", "training"} for role in roles):
        raise DirectionModelError("final_test and non-training roles are forbidden in frozen model training")
    x = np.asarray(x_train, dtype=np.float64)
    y = np.asarray(y_train, dtype=np.float64)
    order = tuple(float(item) for item in direction_order)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.size or x.shape[1] != len(feature_names):
        raise DirectionModelError("training arrays and feature order must align")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise DirectionModelError("frozen model training values must be finite")
    if set(y.tolist()) != set(order):
        raise DirectionModelError("training direction coverage must exactly match direction_order")
    scaler = StandardScaler().fit(x)
    transformed = scaler.transform(x)
    centroids = np.vstack([np.mean(transformed[y == label], axis=0) for label in order])
    ids = tuple(str(item) for item in training_sample_ids)
    hashes = tuple(str(item) for item in training_feature_sha256s)
    aggregate = _canonical_sha256({
        "ordered_sample_ids": list(ids), "ordered_feature_sha256s": list(hashes), "roles": list(roles)
    })
    return FrozenDirectionModel(
        FROZEN_DIRECTION_MODEL_SCHEMA_VERSION, model_id, "frozen_inference", "software_validation_only",
        model_domain, order, tuple(feature_names), tuple(units), feature_kind, preprocessing_id,
        tone_set_id, tone_set_sha256, normalization_method, magnitude_quantity, magnitude_reference,
        "require_all_frozen_features", tuple(float(v) for v in scaler.mean_),
        tuple(float(v) for v in scaler.scale_), tuple(tuple(float(v) for v in row) for row in centroids),
        ids, roles, hashes, aggregate, dict(authority_hashes), tuple(sealed_final_test_sample_ids),
        sealed_final_test_sha256, False, "euclidean_distance", False,
        "configured_direction_order", int(random_state), False, False,
    )


def predict_frozen_direction_model(
    model: FrozenDirectionModel,
    x: NDArray[np.float64],
) -> tuple[RankedDirectionPrediction, ...]:
    """Run immutable nearest-centroid inference without fitting any state."""
    values = np.asarray(x, dtype=np.float64)
    if values.ndim == 1:
        values = values.reshape(1, -1)
    if values.ndim != 2 or values.shape[1] != len(model.feature_names) or not np.all(np.isfinite(values)):
        raise DirectionModelError("inference values must be finite and match frozen feature order")
    transformed = (values - np.asarray(model.scaler_mean)) / np.asarray(model.scaler_scale)
    centroids = np.asarray(model.centroids, dtype=np.float64)
    labels = np.asarray(model.direction_order_deg, dtype=np.float64)
    output = []
    for row in transformed:
        ranked = _rank(
            np.linalg.norm(centroids - row, axis=1), labels, model.direction_order_deg,
            higher_better=False,
        )
        output.append(RankedDirectionPrediction(
            ranked[0], ranked[1], ranked[2], ranked[3], ranked[4],
            model.score_kind, model.higher_is_better,
        ))
    return tuple(output)
