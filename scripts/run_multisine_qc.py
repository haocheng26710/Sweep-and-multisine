"""Run P8 synchronization, transfer estimation, and auditable QC views."""

from __future__ import annotations

import argparse
from dataclasses import fields
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.config import load_config  # noqa: E402
from acoustic_encoder.io_multisine import analyze_multisine_measurement  # noqa: E402
from acoustic_encoder.multisine_outputs import write_multisine_qc_outputs  # noqa: E402
from acoustic_encoder.schemas import MeasurementMeta  # noqa: E402


def _meta_from_sidecar(path: Path) -> MeasurementMeta:
    payload = json.loads(path.read_text(encoding="utf-8"))
    names = {field.name for field in fields(MeasurementMeta)}
    return MeasurementMeta.from_dict(
        {name: value for name, value in payload.items() if name in names}
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording", required=True, type=Path)
    parser.add_argument("--stimulus-manifest", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml",
    )
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    arguments = parser.parse_args()

    resolved = load_config(
        arguments.config,
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    estimation = resolved["multisine_estimation"]
    meta = _meta_from_sidecar(arguments.sidecar)
    if Path(meta.source_path).resolve() != arguments.recording.resolve():
        raise ValueError("Sidecar source_path does not identify --recording")
    analysis = analyze_multisine_measurement(
        arguments.recording,
        arguments.stimulus_manifest,
        meta,
        run_purpose=resolved["run_purpose"],
        period_averaging=estimation["period_averaging"],
        clock_drift_config=estimation["clock_drift"],
        tone_quality_config=estimation["tone_quality"],
    )
    artifacts = write_multisine_qc_outputs(
        analysis,
        arguments.output_directory,
        refuse_existing=not arguments.overwrite,
    )
    print(
        json.dumps(
            {
                "sample_id": meta.sample_id,
                "measurement_qc_status": analysis.measurement_qc["status"],
                "data_origin": meta.data_origin.value,
                "run_purpose": resolved["run_purpose"],
                "eligible_for_scientific_analysis": (
                    meta.eligible_for_scientific_analysis
                ),
                "artifacts": {
                    name: path.resolve().as_posix()
                    for name, path in artifacts.items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
