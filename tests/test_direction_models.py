from __future__ import annotations

import numpy as np
import pytest

from acoustic_encoder.direction_models import (
    DirectionModelError,
    FrozenDirectionModel,
    fit_frozen_direction_model,
    predict_direction_arrays,
    predict_frozen_direction_model,
)


def _training_data() -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(
        [
            [-2.1, -1.0, 0.0], [-1.9, -1.1, 0.1],
            [0.0, 2.0, 1.0], [0.1, 2.2, 0.9],
            [2.0, -0.2, -1.0], [2.2, -0.1, -1.1],
        ],
        dtype=np.float64,
    )
    return x, np.asarray([0.0, 0.0, 90.0, 90.0, 180.0, 180.0])


def _fit() -> FrozenDirectionModel:
    x, y = _training_data()
    return fit_frozen_direction_model(
        model_id="nearest_centroid",
        x_train=x,
        y_train=y,
        direction_order=(0.0, 90.0, 180.0),
        feature_names=("tone_001", "tone_002", "tone_003"),
        units=("dB", "dB", "dB"),
        training_sample_ids=tuple(f"train-{index}" for index in range(x.shape[0])),
        training_roles=("development",) * x.shape[0],
        training_feature_sha256s=tuple("sha256:" + f"{index + 1:064x}" for index in range(x.shape[0])),
        feature_kind="tone_measurement_from_multisine",
        preprocessing_id="sha256:" + "a" * 64,
        tone_set_id="validation-readout-tones-v1",
        tone_set_sha256="sha256:" + "b" * 64,
        normalization_method="subtract_mean_db",
        magnitude_quantity="transfer_ratio",
        magnitude_reference="sha256:" + "c" * 64,
        model_domain="multisine",
        authority_hashes={"p2b": "sha256:" + "d" * 64, "p9": "sha256:" + "e" * 64},
        sealed_final_test_sample_ids=("sealed-final-001",),
        sealed_final_test_sha256="sha256:" + "f" * 64,
        random_state=20260806,
    )


def test_frozen_centroid_round_trip_and_prediction_match_p5_semantics() -> None:
    x, y = _training_data()
    model = _fit()
    restored = FrozenDirectionModel.from_dict(model.to_dict())
    test = np.asarray([[-2.0, -1.0, 0.05], [0.05, 2.1, 0.95]])

    frozen = predict_frozen_direction_model(restored, test)
    fold = predict_direction_arrays(
        "nearest_centroid", x, y, test, (0.0, 90.0, 180.0), 20260806
    )

    assert restored.semantic_sha256 == model.semantic_sha256
    assert [(item.predicted_direction_deg, item.second_direction_deg, item.score, item.margin) for item in frozen] == pytest.approx(fold)
    assert all(item.score_kind == "euclidean_distance" for item in frozen)
    assert all(item.higher_is_better is False for item in frozen)
    assert all(item.second_score is not None and item.margin == pytest.approx(item.second_score - item.score) for item in frozen)


def test_frozen_model_rejects_cv_role_final_test_and_parameter_tamper() -> None:
    model = _fit()
    payload = model.to_dict()
    payload["model_role"] = "cv_fold_temporary"
    with pytest.raises(DirectionModelError, match="frozen_inference"):
        FrozenDirectionModel.from_dict(payload)

    x, y = _training_data()
    with pytest.raises(DirectionModelError, match="final_test"):
        fit_frozen_direction_model(
            model_id="nearest_centroid", x_train=x, y_train=y,
            direction_order=(0.0, 90.0, 180.0), feature_names=("a", "b", "c"),
            units=("dB",) * 3, training_sample_ids=tuple(f"s{i}" for i in range(6)),
            training_roles=("development", "development", "development", "development", "development", "final_test"),
            training_feature_sha256s=tuple("sha256:" + f"{i + 1:064x}" for i in range(6)),
            feature_kind="tone_measurement_from_multisine", preprocessing_id="sha256:" + "a" * 64,
            tone_set_id="tones", tone_set_sha256="sha256:" + "b" * 64,
            normalization_method="none", magnitude_quantity="transfer_ratio",
            magnitude_reference=None, model_domain="multisine",
            authority_hashes={"p2b": "sha256:" + "d" * 64},
            sealed_final_test_sample_ids=("s5",), sealed_final_test_sha256="sha256:" + "f" * 64,
            random_state=0,
        )

    payload = model.to_dict()
    payload["centroids"][0][0] += 1.0
    with pytest.raises(DirectionModelError, match="semantic hash"):
        FrozenDirectionModel.from_dict(payload)


def test_frozen_model_tie_break_is_direction_order_and_deterministic() -> None:
    model = _fit()
    payload = model.to_dict()
    payload.pop("model_semantic_sha256")
    payload["centroids"] = [[0.0, 0.0, 0.0]] * 3
    tied = FrozenDirectionModel.from_dict(payload)

    first = predict_frozen_direction_model(tied, np.asarray([[0.0, 0.0, 0.0]]))[0]
    second = predict_frozen_direction_model(tied, np.asarray([[0.0, 0.0, 0.0]]))[0]

    assert first == second
    assert first.predicted_direction_deg == 0.0
    assert first.second_direction_deg == 90.0
    assert first.margin == 0.0
