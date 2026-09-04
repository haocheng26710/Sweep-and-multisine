from __future__ import annotations

import pytest

from fine_mesh_repair import require_positive_volume_mesh


def test_retry04_zero_element_mesh_is_rejected_before_study():
    with pytest.raises(RuntimeError, match="positive volume mesh"):
        require_positive_volume_mesh({
            "elements": 0,
            "vertices": 0,
            "minimum_quality": 0.0,
            "mean_quality": 0.0,
        })


def test_positive_mesh_passes_hard_gate():
    result = require_positive_volume_mesh({
        "elements": 100,
        "vertices": 40,
        "minimum_quality": 0.01,
        "mean_quality": 0.5,
    })

    assert result["hard_gate_pass"] is True


@pytest.mark.parametrize("key", ["elements", "vertices", "minimum_quality", "mean_quality"])
def test_each_required_mesh_stat_is_individually_guarded(key):
    values = {
        "elements": 100,
        "vertices": 40,
        "minimum_quality": 0.01,
        "mean_quality": 0.5,
    }
    values[key] = float("nan")

    with pytest.raises(RuntimeError, match="positive volume mesh"):
        require_positive_volume_mesh(values)
