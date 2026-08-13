from __future__ import annotations

import subprocess
import json
from pathlib import Path

import pytest

from acoustic_encoder.ui.release_build import (
    ReleaseBuildError,
    audit_release_provenance,
    build_verification_payload,
    capture_clean_release_source,
    verify_release_source_unchanged,
)
from acoustic_encoder.ui.acceptance_assets import audit_acceptance_assets


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _clean_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "clean source"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Release Test")
    (repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "initial")
    return repo


def test_dirty_source_is_rejected_before_release_build(tmp_path: Path) -> None:
    repo = _clean_repository(tmp_path)
    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(ReleaseBuildError, match="工作树不干净"):
        capture_clean_release_source(repo)

    assert not (repo / "dist").exists()


def test_clean_source_provenance_remains_stable_across_ignored_build_outputs(
    tmp_path: Path,
) -> None:
    repo = _clean_repository(tmp_path)
    (repo / ".gitignore").write_text("build/\ndist/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "ignore build outputs")

    source = capture_clean_release_source(repo)
    (repo / "build/staging").mkdir(parents=True)
    (repo / "build/staging/evidence.json").write_text("{}\n", encoding="utf-8")
    (repo / "dist").mkdir()
    (repo / "dist/application.exe").write_bytes(b"not-a-real-exe")

    verified = verify_release_source_unchanged(source)

    assert verified == source
    assert source.source_git_dirty is False
    assert _git(repo, "status", "--porcelain") == ""


def test_runtime_acceptance_assets_are_generated_only_in_staging(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "release staging"
    verification = staging / "validation_assets/pre_experiment_acceptance/build_verification.json"
    verification.parent.mkdir(parents=True)
    verification.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "purpose": "software_validation",
                "scientifically_eligible": False,
                "final_test_read": False,
                "source_commit": "a" * 40,
                "source_branch": "test",
                "source_git_dirty": False,
                "verification": {},
            }
        ),
        encoding="utf-8",
    )
    tracked_manifest = (
        PROJECT_ROOT
        / "validation_assets/pre_experiment_acceptance/assets_manifest.json"
    )
    assert tracked_manifest.exists() is False

    subprocess.run(
        (
            "python",
            "scripts/build_acceptance_assets.py",
            "--output-root",
            str(staging),
            "--build-verification",
            str(verification),
        ),
        cwd=PROJECT_ROOT,
        check=True,
    )

    audit = audit_acceptance_assets(staging)
    assert audit.available is True
    assert audit.hashes_verified is True
    assert tracked_manifest.exists() is False


def test_clean_build_verification_binds_exact_source_commit(tmp_path: Path) -> None:
    repo = _clean_repository(tmp_path)
    source = capture_clean_release_source(repo)

    payload = build_verification_payload(
        source,
        verification={"full_pytest": {"status": "pass", "exit_code": 0}},
        python_version="3.test",
        created_at_utc="2026-08-13T00:00:00+00:00",
    )

    assert payload["source_commit"] == _git(repo, "rev-parse", "HEAD")
    assert payload["source_branch"] == _git(repo, "branch", "--show-current")
    assert payload["source_git_dirty"] is False
    assert payload["final_test_read"] is False
    assert payload["scientifically_eligible"] is False


def test_packaged_provenance_requires_one_clean_commit(tmp_path: Path) -> None:
    commit = "b" * 40
    verification = tmp_path / "build_verification.json"
    build_manifest = tmp_path / "build_manifest.json"
    acceptance = tmp_path / "acceptance_manifest.json"
    verification.write_text(json.dumps({
        "source_commit": commit, "source_git_dirty": False,
    }), encoding="utf-8")
    build_manifest.write_text(json.dumps({
        "source_commit": commit, "git_commit": commit,
        "source_git_dirty": False, "git_dirty": False,
    }), encoding="utf-8")
    acceptance.write_text(json.dumps({
        "git_commit": commit, "git_dirty": False, "final_test_read": False,
        "scientifically_eligible": False,
    }), encoding="utf-8")

    audit = audit_release_provenance(
        build_verification_path=verification,
        build_manifest_path=build_manifest,
        acceptance_manifest_path=acceptance,
        expected_commit=commit,
    )

    assert audit.verified is True
    assert audit.source_commit == commit
    assert audit.git_dirty is False
