from __future__ import annotations

import pytest

from acoustic_encoder.hr_outputs import load_hr_calibration_bundle
from acoustic_encoder.hr_validation import run_hr_calibration_validation


PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def test_dev_c10_validation_recovers_known_peaks_drift_and_energy_ratios(tmp_path) -> None:
    output = run_hr_calibration_validation(
        output_root=tmp_path / "outputs",
        run_id="DEV-C10-P6A-TEST",
        project_root=PROJECT_ROOT,
    )
    result = load_hr_calibration_bundle(output)

    assert result.calibration_status == "software_validation_only"
    assert result.scientifically_eligible is False
    expected_peaks = {
        "CONT": {(1499.0, 1679.0, 2199.0), (1501.0, 1681.0, 2201.0)},
        "REPOS": {(1495.0, 1675.0, 2195.0), (1505.0, 1685.0, 2205.0)},
        "REASM": {(1490.0, 1670.0, 2190.0), (1510.0, 1690.0, 2210.0)},
    }
    by_sample = {}
    for item in result.detected_peaks:
        by_sample.setdefault(item.sample_id, []).append(item.peak_frequency_hz)
    for sample_id, values in by_sample.items():
        repeat = next(item.repeat_type for item in result.peak_drifts if sample_id in item.sample_ids)
        assert tuple(values) in expected_peaks[repeat]
    drift = {(item.resonator_id, item.repeat_type): item.peak_to_peak_hz for item in result.peak_drifts}
    for resonator_id in ("R1", "R2", "R3"):
        assert drift[(resonator_id, "CONT")] == pytest.approx(2.0)
        assert drift[(resonator_id, "REPOS")] == pytest.approx(10.0)
        assert drift[(resonator_id, "REASM")] == pytest.approx(20.0)
    by_fraction_group = {}
    for item in result.energy_fractions:
        by_fraction_group.setdefault(item.energy_fraction_group_id, []).append(item.q_i)
    for values in by_fraction_group.values():
        assert values == pytest.approx([4 / 7, 2 / 7, 1 / 7], abs=1e-9)
        assert sum(values) == pytest.approx(1.0, abs=1e-12)

    with pytest.raises(FileExistsError):
        run_hr_calibration_validation(
            output_root=tmp_path / "outputs", run_id="DEV-C10-P6A-TEST", project_root=PROJECT_ROOT
        )
