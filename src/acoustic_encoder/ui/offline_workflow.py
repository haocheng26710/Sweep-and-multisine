"""UI application service for one immutable-package offline readout."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from acoustic_encoder.schemas import artifact_sha256
from acoustic_encoder.ui.p9_workflow import P9Invocation
from acoustic_encoder.ui.runtime import RuntimeContext


SCORE_EXPLANATION = (
    "nearest-centroid score 越小表示越匹配；margin 是第二名与第一名的距离差，"
    "不是概率或置信概率。"
)


@dataclass(frozen=True, slots=True)
class OfflineReadoutSummary:
    processing_status: str
    prediction_available: bool
    predicted_direction_deg: float | None
    scores: dict[str, float]
    margin: float | None
    reasons: tuple[str, ...]
    scientifically_eligible: bool
    deployment_eligible: bool
    score_explanation: str = SCORE_EXPLANATION


class OfflineReadoutService:
    def __init__(self, runtime: RuntimeContext) -> None:
        self.runtime = runtime

    def prepare(
        self,
        *,
        package_directory: Path,
        input_manifest: Path,
        output_directory: Path,
    ) -> P9Invocation:
        from acoustic_encoder.offline_readout_outputs import load_readout_package_bundle

        package_directory = Path(package_directory).resolve()
        input_manifest = Path(input_manifest).resolve()
        output_directory = Path(output_directory).resolve()
        if output_directory.exists():
            raise FileExistsError(f"offline readout output already exists: {output_directory}")
        package, _, manifest = load_readout_package_bundle(package_directory)
        if package.lifecycle not in {"software_validation_only", "frozen", "approved"}:
            raise PermissionError(f"unsupported package lifecycle: {package.lifecycle}")
        if not input_manifest.is_file():
            raise FileNotFoundError(f"explicit input manifest is missing: {input_manifest}")
        arguments = [
            "--package", str(package_directory),
            "--input-manifest", str(input_manifest),
            "--output", str(output_directory),
        ]
        program, worker_args = self.runtime.worker_process("offline", arguments)
        hashes = {
            (package_directory / "package_manifest.json").as_posix(): artifact_sha256(package_directory / "package_manifest.json"),
            input_manifest.as_posix(): artifact_sha256(input_manifest),
        }
        return P9Invocation(
            "offline-readout", str(manifest["package_id"]), program, worker_args,
            output_directory, hashes,
            scientifically_eligible=bool(manifest["scientifically_eligible"]),
            deployment_allowed=bool(manifest["deployment_eligible"]),
            final_test_read=False,
        )

    def summarize(self, output_directory: Path) -> OfflineReadoutSummary:
        output = Path(output_directory)
        manifest = json.loads((output / "readout_manifest.json").read_text(encoding="utf-8"))
        prediction = json.loads((output / "prediction.json").read_text(encoding="utf-8"))
        available = bool(manifest.get("prediction_available", False)) and bool(prediction.get("available", False))
        predicted = prediction.get("predicted_direction_deg") if available else None
        raw_scores: Any = prediction.get("scores", prediction.get("direction_scores", {}))
        scores = {str(key): float(value) for key, value in raw_scores.items()} if isinstance(raw_scores, dict) else {}
        reasons = tuple(str(item) for item in manifest.get("failure_reasons", ()))
        return OfflineReadoutSummary(
            processing_status=str(manifest.get("processing_status", "unavailable")),
            prediction_available=available,
            predicted_direction_deg=None if predicted is None else float(predicted),
            scores=scores,
            margin=(None if not available or prediction.get("margin") is None else float(prediction["margin"])),
            reasons=reasons,
            scientifically_eligible=bool(manifest.get("scientifically_eligible", False)),
            deployment_eligible=bool(manifest.get("deployment_eligible", False)),
        )
