from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SOURCE = (
    PROJECT_ROOT
    / "validation_assets"
    / "pre_experiment_acceptance"
    / "rew"
    / "external_reference"
)

CONFIG_FILES = (
    "default.yaml",
    "validation_dev_c16_acceptance.yaml",
    "validation_dev_c4_matched_tones.yaml",
    "experiment_v2_u4.yaml",
    "experiment_v2_u4_multisine.yaml",
    "stimulus_multisine_broadband.yaml",
    "validation_dev_c13_p9b.yaml",
    "validation_dev_c14_p9c.yaml",
    "validation_dev_c15_p9d.yaml",
)
DOCUMENT_FILES = (
    "README.md",
    "MIGRATION_V1_TO_V2.md",
    "docs/progress/DEV-C16_PRE_EXPERIMENT_ACCEPTANCE.md",
    "docs/experiment/DEV_D_REAL_EXPERIMENT_ENTRY_CHECKLIST.md",
    "docs/experiment/REAL_DATA_REPLACEMENT_GUIDE.md",
    "docs/experiment/DEV_D_ACQUISITION_PLAN_TEMPLATE.md",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_acceptance_assets(
    *, output_root: str | Path, build_verification: str | Path,
) -> Path:
    runtime_root = Path(output_root).resolve()
    asset_root = runtime_root / "validation_assets" / "pre_experiment_acceptance"
    fixture_target = asset_root / "rew" / "external_reference"
    fixture_target.mkdir(parents=True, exist_ok=True)
    fixture_manifest = json.loads(
        (FIXTURE_SOURCE / "manifest.json").read_text(encoding="utf-8")
    )
    fixture_names = ("manifest.json",) + tuple(
        str(item["file_name"]) for item in fixture_manifest["files"]
    )
    for name in fixture_names:
        shutil.copyfile(FIXTURE_SOURCE / name, fixture_target / name)

    assets: list[dict[str, object]] = []
    for name in fixture_names:
        path = fixture_target / name
        assets.append(
            {
                "asset_role": "rew_manifest" if name == "manifest.json" else "rew_fixture",
                "relative_path": path.relative_to(runtime_root).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
                "data_origin": "external_reference",
                "dataset_role": "parser_fixture",
                "eligible_for_scientific_analysis": False,
            }
        )
    for name in CONFIG_FILES:
        source = PROJECT_ROOT / "config" / name
        path = runtime_root / "config" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)
        assets.append(
            {
                "asset_role": "config",
                "relative_path": path.relative_to(runtime_root).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    for name in DOCUMENT_FILES:
        source = PROJECT_ROOT / name
        path = runtime_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)
        assets.append(
            {
                "asset_role": "documentation",
                "relative_path": path.relative_to(runtime_root).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    verification_source = Path(build_verification).resolve()
    if not verification_source.is_file():
        raise FileNotFoundError(f"build verification is missing: {verification_source}")
    verification_target = asset_root / "build_verification.json"
    if verification_source != verification_target:
        shutil.copyfile(verification_source, verification_target)
    assets.append(
        {
            "asset_role": "build_verification",
            "relative_path": verification_target.relative_to(runtime_root).as_posix(),
            "sha256": _sha256(verification_target),
            "size_bytes": verification_target.stat().st_size,
        }
    )
    payload = {
        "schema_version": "1.0.0",
        "asset_set_id": "dev-ui4-pre-experiment-acceptance",
        "purpose": "software_validation",
        "scientifically_eligible": False,
        "final_test_read": False,
        "assets": sorted(assets, key=lambda item: str(item["relative_path"])),
    }
    asset_root.mkdir(parents=True, exist_ok=True)
    manifest_path = asset_root / "assets_manifest.json"
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage immutable DEV-C16 runtime validation assets"
    )
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--build-verification", required=True)
    args = parser.parse_args(argv)
    build_acceptance_assets(
        output_root=args.output_root,
        build_verification=args.build_verification,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
