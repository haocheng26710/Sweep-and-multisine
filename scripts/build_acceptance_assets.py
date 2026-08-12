from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = PROJECT_ROOT / "validation_assets" / "pre_experiment_acceptance"
FIXTURE_SOURCE = PROJECT_ROOT / "tests" / "fixtures" / "rew" / "external_reference"

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


def main() -> int:
    fixture_target = ASSET_ROOT / "rew" / "external_reference"
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
                "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
                "data_origin": "external_reference",
                "dataset_role": "parser_fixture",
                "eligible_for_scientific_analysis": False,
            }
        )
    for name in CONFIG_FILES:
        path = PROJECT_ROOT / "config" / name
        assets.append(
            {
                "asset_role": "config",
                "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    for name in DOCUMENT_FILES:
        path = PROJECT_ROOT / name
        assets.append(
            {
                "asset_role": "documentation",
                "relative_path": path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    build_verification = ASSET_ROOT / "build_verification.json"
    if build_verification.is_file():
        assets.append(
            {
                "asset_role": "build_verification",
                "relative_path": build_verification.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": _sha256(build_verification),
                "size_bytes": build_verification.stat().st_size,
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
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    (ASSET_ROOT / "assets_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
