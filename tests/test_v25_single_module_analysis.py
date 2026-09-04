from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

import numpy as np
import pytest

from acoustic_encoder.v25_single_module_analysis import (
    V25S1InputError,
    _repeatability_rows,
    extract_target_feature,
    inspect_v25_s1_archive,
    parse_v25_s1_filename,
)


CONDITIONS = ("base", *(f"HR{index:02d}" for index in range(1, 9)))


def _archive_fixture(path: Path, *, ambiguous: bool = False) -> tuple[Path, str, Path, Path]:
    raw_txt = path.parent / f"{path.stem}_raw_txt"
    raw_mdat = path.parent / f"{path.stem}_raw_mdat"
    raw_txt.mkdir()
    raw_mdat.mkdir()
    with zipfile.ZipFile(path, "w") as archive:
        for condition in CONDITIONS:
            for repeat in range(1, 7):
                stem = f"R V2.5_{condition}_{repeat:02d}"
                txt_name = f"{stem}.txt"
                if ambiguous and condition == "HR08" and repeat == 6:
                    txt_name = "unknown.txt"
                txt_payload = f"fixture-{condition}-{repeat}-txt\n".encode()
                mdat_payload = f"fixture-{condition}-{repeat}-mdat\n".encode()
                archive.writestr(f"V25-S1/{txt_name}", txt_payload)
                archive.writestr(f"V25-S1/{stem}.mdat", mdat_payload)
                (raw_txt / txt_name).write_bytes(txt_payload)
                (raw_mdat / f"{stem}.mdat").write_bytes(mdat_payload)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest, raw_txt, raw_mdat


def test_filename_mapping_freezes_user_block_definition() -> None:
    first = parse_v25_s1_filename("R V2.5_HR03_03.txt")
    second = parse_v25_s1_filename("R V2.5_base_04.mdat")

    assert first == ("HR03", 3, "B01", 3)
    assert second == ("base", 4, "B02", 1)
    with pytest.raises(V25S1InputError, match="cannot reliably identify"):
        parse_v25_s1_filename("HR3 test.txt")


def test_inventory_requires_54_paired_txt_and_mdat_files(tmp_path: Path) -> None:
    source, digest, raw_txt, raw_mdat = _archive_fixture(tmp_path / "v25s1.zip")

    inventory = inspect_v25_s1_archive(
        source,
        expected_zip_sha256=digest,
        extracted_txt_directory=raw_txt,
        extracted_mdat_directory=raw_mdat,
    )

    assert len(inventory.txt_members) == 54
    assert len(inventory.mdat_members) == 54
    assert inventory.condition_counts == {condition: 6 for condition in CONDITIONS}
    assert inventory.txt_members[0].block_id == "B01"
    assert inventory.txt_members[3].block_id == "B02"

    bad, bad_digest, _, _ = _archive_fixture(tmp_path / "bad.zip", ambiguous=True)
    with pytest.raises(V25S1InputError, match="cannot reliably identify"):
        inspect_v25_s1_archive(bad, expected_zip_sha256=bad_digest)


def test_target_feature_finds_signed_repeatable_local_contrast() -> None:
    frequency = 800.0 * np.exp2(np.arange(0, 96, dtype=float) / 48.0)
    target = 1200.0

    def notch(center: float, amplitude: float) -> np.ndarray:
        distance = np.log2(frequency / center)
        return -amplitude * np.exp(-0.5 * np.square(distance / 0.035))

    result = extract_target_feature(
        frequency,
        {"B01": notch(1185.0, 5.0), "B02": notch(1210.0, 4.5)},
        target_hz=target,
        local_floor_db=0.5,
    )

    assert result["polarity"] == "notch"
    assert abs(np.log2(float(result["measured_feature_hz"]) / target)) < 1 / 12
    assert result["block_sign_consistent"] is True
    assert result["block_frequency_consistent"] is True
    assert result["both_blocks_effect_above_floor"] is True
    assert float(result["contrast_bandwidth_hz"]) > 0
    assert float(result["effective_q"]) > 1


def test_repeatability_ignores_the_preprocessing_invalid_edge_bin() -> None:
    frequency = np.array([200.0, 400.0, 800.0, 4000.0, 8000.0])
    curves: dict[str, np.ndarray] = {}
    for condition in CONDITIONS:
        for block in ("B01", "B02"):
            for repeat in range(1, 4):
                curves[f"V25S1-{condition.upper()}-{block}-R{repeat:02d}"] = np.array(
                    [np.nan, 1.0 + repeat * 0.1, 2.0, 3.0, 4.0]
                )

    _, _, floors = _repeatability_rows(curves, frequency)

    assert np.isfinite(floors["base_technical_primary_descriptive_p95_db"])
    assert np.isfinite(floors["base_cross_block_primary_centroid_rms_db"])
