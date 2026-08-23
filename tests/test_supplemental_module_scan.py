from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

import numpy as np
import pytest

from acoustic_encoder.supplemental_module_scan import (
    Sup1InputError,
    choose_primary_triplet,
    classify_candidate_window,
    inspect_sup1_archive,
)


def _zip_fixture(path: Path, *, ambiguous: bool = False) -> tuple[Path, str, Path]:
    raw = path.parent / f"{path.stem}_raw"
    raw.mkdir()
    names = []
    for module in "ABCDEFGH":
        count = 3 if module in "ABC" else 4
        for repeat in range(1, count + 1):
            names.append(f"R C03_U4ENC_{module}{repeat:02d}.txt")
    if ambiguous:
        names[-1] = "unknown.txt"
    with zipfile.ZipFile(path, "w") as archive:
        for index, name in enumerate(names):
            payload = f"fixture-{index}-{name}\n".encode()
            archive.writestr(name, payload)
            (raw / name).write_bytes(payload)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest, raw


def test_sup1_inventory_requires_exact_unambiguous_29_file_mapping(tmp_path: Path) -> None:
    source, digest, raw = _zip_fixture(tmp_path / "sup1.zip")

    inventory = inspect_sup1_archive(
        source, expected_zip_sha256=digest, extracted_raw_directory=raw
    )

    assert len(inventory.members) == 29
    assert inventory.module_counts == {
        "A": 3, "B": 3, "C": 3, "D": 4, "E": 4, "F": 4, "G": 4, "H": 4,
    }
    assert inventory.members[0].sample_id == "SUP1-ENC-A-R01"

    bad, bad_digest, _ = _zip_fixture(tmp_path / "bad.zip", ambiguous=True)
    with pytest.raises(Sup1InputError, match="cannot reliably identify"):
        inspect_sup1_archive(bad, expected_zip_sha256=bad_digest)


def test_four_repeat_selection_keeps_most_coherent_triplet_and_retains_extra() -> None:
    ids = tuple(f"SUP1-ENC-D-R{repeat:02d}" for repeat in range(1, 5))
    curves = {
        ids[0]: np.asarray([0.00, 1.00, 2.00]),
        ids[1]: np.asarray([0.02, 1.01, 2.01]),
        ids[2]: np.asarray([-0.01, 0.99, 2.02]),
        ids[3]: np.asarray([2.00, -1.00, 4.00]),
    }

    selected, extra, score = choose_primary_triplet(ids, curves)

    assert selected == ids[:3]
    assert extra == ids[3]
    assert score < 0.05

    invalid = dict(curves)
    invalid[ids[0]] = np.asarray([np.nan, 1.0, 2.0])
    with pytest.raises(Sup1InputError, match="valid finite bins"):
        choose_primary_triplet(ids, invalid)

    tied_medians = {
        ids[0]: np.asarray([0.0]),
        ids[1]: np.asarray([1.0]),
        ids[2]: np.asarray([2.0]),
        ids[3]: np.asarray([3.0]),
    }
    selected, extra, _ = choose_primary_triplet(ids, tied_medians)
    assert selected == ids[1:]
    assert extra == ids[0]


def test_candidate_window_rule_needs_representative_and_seven_of_nine() -> None:
    assert classify_candidate_window(1.2, [1.1] * 7 + [0.5] * 2, 1.0) == "stable"
    assert (
        classify_candidate_window(1.2, [1.1] * 6 + [0.5] * 3, 1.0)
        == "isolated_or_repeat_sensitive"
    )
    assert classify_candidate_window(0.8, [0.8] * 9, 1.0) == "below_floor"
