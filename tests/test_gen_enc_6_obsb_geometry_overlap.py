from __future__ import annotations

import numpy as np

from scripts.gen_enc_4_topology_preserving_m0_m1 import exact80_members
from scripts.gen_enc_6_obsb_geometry_overlap_diagnostic import exact80_bundle_digest, physical_geometry_signature, separation


def test_common_geometry_signature_is_finite_and_has_frozen_shapes() -> None:
    _, member, _ = exact80_members()[0]
    primary, realized = physical_geometry_signature(member)
    assert primary.shape == (16,)
    assert realized.shape == (20,)
    assert np.all(np.isfinite(primary))
    assert np.all(np.isfinite(realized))


def test_exact80_bundle_digest_uses_source_files() -> None:
    members = exact80_members()
    value = exact80_bundle_digest(members)
    assert len(value) == 64
    assert all(character in "0123456789abcdef" for character in value)


def test_separation_emits_all_six_family_pairs() -> None:
    rng = np.random.default_rng(20260902)
    result = separation(rng.normal(size=(80, 16)))
    assert result["usable_dimensions"] == 16
    assert len(result["pairwise"]) == 6
    assert np.isfinite(result["minimum_between_within_ratio"])
    assert np.isfinite(result["mean_between_within_ratio"])
