"""Hash-audited read-only assets required by frozen DEV-C16 acceptance."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AcceptanceAssetRecord:
    asset_role: str
    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class AcceptanceAssetAudit:
    root: Path
    manifest_path: Path
    assets: tuple[AcceptanceAssetRecord, ...]
    available: bool
    hashes_verified: bool
    failures: tuple[str, ...]


def audit_acceptance_assets(resource_root: str | Path) -> AcceptanceAssetAudit:
    resources = Path(resource_root).resolve()
    manifest = (
        resources
        / "validation_assets"
        / "pre_experiment_acceptance"
        / "assets_manifest.json"
    )
    failures: list[str] = []
    records: list[AcceptanceAssetRecord] = []
    if not manifest.is_file():
        return AcceptanceAssetAudit(
            resources,
            manifest,
            (),
            False,
            False,
            (f"missing_asset_manifest:{manifest}",),
        )
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "1.0.0":
            failures.append("unsupported_asset_manifest_schema")
        if payload.get("purpose") != "software_validation":
            failures.append("invalid_asset_purpose")
        if payload.get("scientifically_eligible") is not False:
            failures.append("invalid_scientific_eligibility")
        for item in payload.get("assets", ()):
            record = AcceptanceAssetRecord(
                asset_role=str(item["asset_role"]),
                relative_path=str(item["relative_path"]),
                sha256=str(item["sha256"]),
                size_bytes=int(item["size_bytes"]),
            )
            records.append(record)
            path = resources / record.relative_path
            if not path.is_file():
                failures.append(f"missing:{record.relative_path}")
                continue
            if path.stat().st_size != record.size_bytes:
                failures.append(f"size_mismatch:{record.relative_path}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != record.sha256:
                failures.append(f"sha256_mismatch:{record.relative_path}")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        failures.append(f"invalid_asset_manifest:{type(exc).__name__}:{exc}")
    return AcceptanceAssetAudit(
        resources,
        manifest,
        tuple(records),
        not any(item.startswith("missing") for item in failures),
        not failures,
        tuple(failures),
    )


def external_rew_asset_root(resource_root: str | Path) -> Path:
    return (
        Path(resource_root).resolve()
        / "validation_assets"
        / "pre_experiment_acceptance"
        / "rew"
        / "external_reference"
    )
