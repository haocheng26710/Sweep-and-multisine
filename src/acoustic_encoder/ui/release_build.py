"""Clean-source provenance boundary for formal Windows release builds."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping


class ReleaseBuildError(RuntimeError):
    """A formal build cannot prove a clean, stable source revision."""


@dataclass(frozen=True, slots=True)
class ReleaseSource:
    project_root: Path
    source_commit: str
    source_branch: str
    source_git_dirty: bool = False


@dataclass(frozen=True, slots=True)
class ReleaseProvenanceAudit:
    verified: bool
    source_commit: str
    git_dirty: bool
    failures: tuple[str, ...]


def _git(project_root: Path, *arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments),
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def capture_clean_release_source(project_root: str | Path) -> ReleaseSource:
    root = Path(project_root).resolve()
    dirty = _git(root, "status", "--porcelain")
    if dirty:
        raise ReleaseBuildError(
            "正式发布构建已中止：Git 工作树不干净。请先提交或移除所有修改，"
            "再从 clean commit 重新构建。"
        )
    return ReleaseSource(
        project_root=root,
        source_commit=_git(root, "rev-parse", "HEAD"),
        source_branch=_git(root, "branch", "--show-current"),
    )


def verify_release_source_unchanged(source: ReleaseSource) -> ReleaseSource:
    current = capture_clean_release_source(source.project_root)
    if (
        current.source_commit != source.source_commit
        or current.source_branch != source.source_branch
    ):
        raise ReleaseBuildError(
            "正式发布构建已中止：构建期间 Git HEAD 或分支发生变化。"
        )
    return current


def build_verification_payload(
    source: ReleaseSource,
    *,
    verification: Mapping[str, Mapping[str, Any]],
    python_version: str,
    created_at_utc: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "purpose": "software_validation",
        "scientifically_eligible": False,
        "final_test_read": False,
        "created_at_utc": created_at_utc,
        "source_commit": source.source_commit,
        "source_branch": source.source_branch,
        "source_git_dirty": False,
        "python_version": python_version,
        "verification": {key: dict(value) for key, value in verification.items()},
    }


def audit_release_provenance(
    *,
    build_verification_path: str | Path,
    build_manifest_path: str | Path,
    acceptance_manifest_path: str | Path,
    expected_commit: str,
) -> ReleaseProvenanceAudit:
    verification = json.loads(Path(build_verification_path).read_text(encoding="utf-8-sig"))
    build = json.loads(Path(build_manifest_path).read_text(encoding="utf-8-sig"))
    acceptance = json.loads(Path(acceptance_manifest_path).read_text(encoding="utf-8-sig"))
    commits = (
        str(verification.get("source_commit", "")),
        str(build.get("source_commit", "")),
        str(build.get("git_commit", "")),
        str(acceptance.get("git_commit", "")),
        expected_commit,
    )
    failures: list[str] = []
    if any(value != expected_commit for value in commits):
        failures.append("source_commit_mismatch")
    dirty_values = (
        verification.get("source_git_dirty"),
        build.get("source_git_dirty"),
        build.get("git_dirty"),
        acceptance.get("git_dirty"),
    )
    if any(value is not False for value in dirty_values):
        failures.append("dirty_provenance")
    if acceptance.get("final_test_read") is not False:
        failures.append("final_test_read")
    if acceptance.get("scientifically_eligible") is not False:
        failures.append("unexpected_scientific_eligibility")
    return ReleaseProvenanceAudit(
        verified=not failures,
        source_commit=expected_commit,
        git_dirty=any(value is not False for value in dirty_values),
        failures=tuple(failures),
    )
