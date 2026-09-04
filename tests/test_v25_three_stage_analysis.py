from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

import numpy as np
import pytest

from acoustic_encoder.v25_three_stage_analysis import (
    V25JointInputError,
    direction_code_score,
    direction_discriminability_spectrum,
    inspect_v25_array_archive,
    parse_v25_array_filename,
    select_farthest_repeat,
)


def test_array_filename_mapping_is_exact() -> None:
    assert parse_v25_array_filename("R V2.5_U4SYM_090_04.txt") == (
        "U4SYM", 90, 4, ".txt",
    )
    assert parse_v25_array_filename("R V2.5_U4HR_270_01.mdat") == (
        "U4HR", 270, 1, ".mdat",
    )
    with pytest.raises(V25JointInputError, match="cannot reliably identify"):
        parse_v25_array_filename("U4HR_90_repeat1.txt")


def test_array_inventory_requires_16_paired_txt_and_mdat(tmp_path: Path) -> None:
    source = tmp_path / "s2.zip"
    raw_txt = tmp_path / "raw_txt"
    raw_mdat = tmp_path / "raw_mdat"
    raw_txt.mkdir()
    raw_mdat.mkdir()
    with zipfile.ZipFile(source, "w") as archive:
        for angle in (0, 90, 180, 270):
            for repeat in range(1, 5):
                stem = f"R V2.5_U4SYM_{angle:03d}_{repeat:02d}"
                for extension, directory in ((".txt", raw_txt), (".mdat", raw_mdat)):
                    payload = f"{stem}{extension}\n".encode()
                    name = f"fixture/{stem}{extension}"
                    archive.writestr(name, payload)
                    (directory / f"{stem}{extension}").write_bytes(payload)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    inventory = inspect_v25_array_archive(
        source, expected_configuration="U4SYM", expected_zip_sha256=digest,
        extracted_txt_directory=raw_txt, extracted_mdat_directory=raw_mdat,
    )

    assert len(inventory.txt_members) == 16
    assert len(inventory.mdat_members) == 16
    assert inventory.direction_counts == {0: 4, 90: 4, 180: 4, 270: 4}


def test_selection_drops_only_the_farthest_repeat() -> None:
    frequency = np.array([200.0, 400.0, 800.0, 1600.0, 3200.0, 4000.0])
    curves = {
        "R01": np.zeros(6),
        "R02": np.full(6, 0.1),
        "R03": np.full(6, -0.1),
        "R04": np.array([0.0, 0.0, 0.0, 0.0, 0.0, 5.0]),
    }

    result = select_farthest_repeat(curves, frequency, keep_count=3)

    assert result.dropped_sample_id == "R04"
    assert result.selected_sample_ids == ("R01", "R02", "R03")
    assert set(result.distances_db) == set(curves)


def test_direction_code_score_rewards_expected_diagonal() -> None:
    matrix = np.array([
        [3.0, 0.0, 0.0, 0.0],
        [0.0, 3.0, 0.0, 0.0],
        [0.0, 0.0, 3.0, 0.0],
        [0.0, 0.0, 0.0, 3.0],
    ])

    result = direction_code_score(matrix)

    assert result["score_db"] == pytest.approx(3.0)
    assert result["correct_direction_top1_count"] == 4
    assert result["exact_mapping_permutation_p"] == pytest.approx(1.0 / 24.0)


def test_direction_discriminability_separates_between_from_within_variation() -> None:
    curves = {
        "D0R1": np.array([0.0, 0.0]),
        "D0R2": np.array([0.2, 0.2]),
        "D1R1": np.array([0.0, 4.0]),
        "D1R2": np.array([0.2, 4.2]),
    }
    groups = {0: ("D0R1", "D0R2"), 90: ("D1R1", "D1R2")}

    result = direction_discriminability_spectrum(curves, groups)

    assert result["between_direction_rms_db"][0] == pytest.approx(0.0)
    assert result["between_direction_rms_db"][1] == pytest.approx(2.0)
    assert result["within_direction_rms_db"][0] == pytest.approx(0.1)
    assert result["within_direction_rms_db"][1] == pytest.approx(0.1)
    assert result["between_to_within_ratio"][1] == pytest.approx(20.0)
