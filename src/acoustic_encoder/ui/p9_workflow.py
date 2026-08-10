"""Fail-closed UI orchestration for the formal P9 command entry points."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from typing import Any, Iterable

from acoustic_encoder.schemas import artifact_sha256
from acoustic_encoder.ui.runtime import RuntimeContext


@dataclass(frozen=True, slots=True)
class P9Invocation:
    stage: str
    run_id: str
    program: str
    arguments: tuple[str, ...]
    output_directory: Path
    input_hashes: dict[str, str]
    scientifically_eligible: bool = False
    deployment_allowed: bool = False
    final_test_read: bool = False
    approval_operator: str | None = None


@dataclass(frozen=True, slots=True)
class P9ManifestPreview:
    directory: Path
    scope_path: Path
    input_path: Path
    candidate_path: Path
    hashes: dict[str, str]


@dataclass(frozen=True, slots=True)
class PackageFreezeEvidence:
    package_directory: Path
    package_id: str
    package_semantic_sha256: str
    lifecycle: str
    self_check_passed: bool
    approval_record: Path
    validation_record: Path
    report_markdown: Path
    report_html: Path
    checksum_manifest: Path


def _load_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required explicit authority is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"authority JSON root must be an object: {path}")
    return value


def _contains_final_test(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"cohort_role", "role", "dataset_role"} and item == "final_test":
                return True
            if _contains_final_test(item):
                return True
    elif isinstance(value, list):
        return any(_contains_final_test(item) for item in value)
    return False


def _safe_run_id(run_id: str) -> str:
    if not run_id or Path(run_id).name != run_id or any(char in run_id for char in "/\\"):
        raise ValueError("run-id must be one non-empty filesystem-safe component")
    return run_id


class P9WorkflowService:
    """Prepare explicit, auditable P9 calls without discovering files."""

    def __init__(self, runtime: RuntimeContext) -> None:
        self.runtime = runtime

    def _verify_files(self, paths: Iterable[Path]) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for path in paths:
            resolved = Path(path).resolve()
            if not resolved.is_file():
                raise FileNotFoundError(f"required explicit authority is missing: {resolved}")
            hashes[resolved.as_posix()] = artifact_sha256(resolved)
        return hashes

    def write_p9a_manifest_preview(
        self,
        *,
        preview_directory: Path,
        scope: dict[str, Any],
        inputs: dict[str, Any],
        candidate_universe: dict[str, Any],
        selection_reason: str,
    ) -> P9ManifestPreview:
        """Persist a read-only preview from explicit operator selections only."""
        if not selection_reason.strip():
            raise ValueError("P9-A preview requires an explicit selection reason")
        if any(_contains_final_test(item) for item in (scope, inputs, candidate_universe)):
            raise PermissionError("final-test data cannot enter a P9-A manifest preview")
        directory = Path(preview_directory).resolve()
        if directory.exists():
            raise FileExistsError(f"P9-A preview already exists: {directory}")
        directory.mkdir(parents=True, exist_ok=False)
        scope_path = directory / "tone_selection_scope.json"
        input_path = directory / "tone_selection_inputs.json"
        candidate_path = directory / "candidate_tone_universe.json"
        for path, payload in (
            (scope_path, scope), (input_path, inputs), (candidate_path, candidate_universe),
        ):
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        (directory / "preview_audit.json").write_text(
            json.dumps(
                {
                    "selection_reason": selection_reason.strip(),
                    "source": "explicit_operator_selection",
                    "directory_scan_used": False,
                    "final_test_read": False,
                    "confirmed": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        hashes = self._verify_files((scope_path, input_path, candidate_path))
        return P9ManifestPreview(directory, scope_path, input_path, candidate_path, hashes)

    def prepare_p9a(
        self,
        *,
        config: Path,
        scope: Path,
        inputs: Path,
        candidate_universe: Path,
        dataset_qc_directory: Path,
        output_root: Path,
        run_id: str,
        comparison_metrics_directory: Path | None = None,
    ) -> P9Invocation:
        run_id = _safe_run_id(run_id)
        scope_payload = _load_object(Path(scope))
        if _contains_final_test(scope_payload):
            raise PermissionError("final-test members are forbidden in P9-A training/development scope")
        files = [Path(config), Path(scope), Path(inputs), Path(candidate_universe)]
        hashes = self._verify_files(files)
        p2_manifest = Path(dataset_qc_directory) / "dataset_qc_manifest.json"
        hashes.update(self._verify_files([p2_manifest]))
        arguments = [
            "--config", str(Path(config).resolve()),
            "--scope", str(Path(scope).resolve()),
            "--inputs", str(Path(inputs).resolve()),
            "--candidate-universe", str(Path(candidate_universe).resolve()),
            "--dataset-qc-dir", str(Path(dataset_qc_directory).resolve()),
        ]
        if comparison_metrics_directory is not None:
            p4_manifest = Path(comparison_metrics_directory) / "metrics_manifest.json"
            hashes.update(self._verify_files([p4_manifest]))
            arguments.extend(["--comparison-metrics-dir", str(Path(comparison_metrics_directory).resolve())])
        arguments.extend(["--output-root", str(Path(output_root).resolve()), "--run-id", run_id])
        output = Path(output_root).resolve() / "simulated" / "software_validation" / run_id / "tone_selection"
        if output.exists():
            raise FileExistsError(f"P9-A output already exists: {output}")
        program, worker_args = self.runtime.worker_process("p9a", arguments)
        return P9Invocation("P9-A", run_id, program, worker_args, output, hashes)

    def prepare_p9b(
        self,
        *,
        config: Path,
        scope: Path,
        inputs: Path,
        candidate_universe: Path,
        p9a_authority_directories: tuple[Path, ...],
        output_root: Path,
        run_id: str,
    ) -> P9Invocation:
        if not p9a_authority_directories:
            raise PermissionError("P9-B is blocked until explicit P9-A fold authority is selected")
        authority_manifests = [Path(item) / "tone_selection_manifest.json" for item in p9a_authority_directories]
        hashes = self._verify_files(
            [Path(config), Path(scope), Path(inputs), Path(candidate_universe), *authority_manifests]
        )
        if _contains_final_test(_load_object(Path(scope))):
            raise PermissionError("final-test members are forbidden in P9-B scope")
        run_id = _safe_run_id(run_id)
        arguments = [
            "--config", str(Path(config).resolve()),
            "--scope", str(Path(scope).resolve()),
            "--inputs", str(Path(inputs).resolve()),
            "--candidate-universe", str(Path(candidate_universe).resolve()),
            "--output-root", str(Path(output_root).resolve()),
            "--run-id", run_id,
        ]
        output = Path(output_root).resolve() / "simulated" / "software_validation" / run_id / "projection_ablation"
        if output.exists():
            raise FileExistsError(f"P9-B output already exists: {output}")
        program, worker_args = self.runtime.worker_process("p9b", arguments)
        return P9Invocation("P9-B", run_id, program, worker_args, output, hashes)

    def prepare_p9c(
        self,
        *,
        config: Path,
        scope: Path,
        inputs: Path,
        output_root: Path,
        run_id: str,
    ) -> P9Invocation:
        scope_payload = _load_object(Path(scope))
        modes = set(scope_payload.get("measurement_modes", ()))
        if scope_payload.get("data_origin") == "real_experiment" and "schroeder_multisine" in modes:
            raise PermissionError(
                "real Multisine/P8 is not approved; real P9-C remains blocked"
            )
        if not scope_payload.get("pairing_authority_sha256"):
            raise PermissionError("P9-C requires an explicit formal P3-C pairing authority")
        if _contains_final_test(scope_payload):
            raise PermissionError("final-test members are forbidden in P9-C calibration scope")
        hashes = self._verify_files([Path(config), Path(scope), Path(inputs)])
        run_id = _safe_run_id(run_id)
        arguments = [
            "--config", str(Path(config).resolve()),
            "--scope", str(Path(scope).resolve()),
            "--inputs", str(Path(inputs).resolve()),
            "--output-root", str(Path(output_root).resolve()),
            "--run-id", run_id,
        ]
        output = Path(output_root).resolve() / "simulated" / "software_validation" / run_id / "cross_mode_bridge"
        if output.exists():
            raise FileExistsError(f"P9-C output already exists: {output}")
        program, worker_args = self.runtime.worker_process("p9c", arguments)
        return P9Invocation("P9-C", run_id, program, worker_args, output, hashes)

    def prepare_p9d(
        self,
        *,
        config: Path,
        training_manifest: Path,
        output_directory: Path,
        approval_operator: str,
    ) -> P9Invocation:
        manifest = _load_object(Path(training_manifest))
        if _contains_final_test(manifest):
            raise PermissionError("final-test samples are forbidden in P9-D package training")
        if not approval_operator.strip():
            raise ValueError("an approval operator is required for package freeze")
        output = Path(output_directory).resolve()
        if output.exists():
            raise FileExistsError(f"frozen package output already exists: {output}")
        hashes = self._verify_files([Path(config), Path(training_manifest)])
        arguments = [
            "--config", str(Path(config).resolve()),
            "--training-manifest", str(Path(training_manifest).resolve()),
            "--output", str(output),
        ]
        program, worker_args = self.runtime.worker_process("p9d", arguments)
        return P9Invocation(
            "P9-D", output.name, program, worker_args, output, hashes,
            approval_operator=approval_operator.strip(),
        )

    def finalize_package(
        self,
        package_directory: Path,
        *,
        approval_operator: str,
    ) -> PackageFreezeEvidence:
        """Run the authoritative loader self-check, then add UI freeze evidence."""
        from acoustic_encoder.offline_readout_outputs import load_readout_package_bundle

        output = Path(package_directory).resolve()
        package, _, manifest = load_readout_package_bundle(output)
        if package.final_test_read or package.scientifically_eligible or package.deployment_eligible:
            raise PermissionError("software-validation package asserted an ineligible authority state")
        if package.lifecycle != "software_validation_only":
            raise PermissionError(f"unexpected software-validation package lifecycle: {package.lifecycle}")
        operator = approval_operator.strip()
        if not operator:
            raise ValueError("approval operator is required")
        targets = {
            "approval": output / "freeze_approval_record.json",
            "validation": output / "package_validation.json",
            "md": output / "step_report.md",
            "html": output / "step_report.html",
            "log": output / "technical_log.txt",
            "checksums": output / "ui_freeze_artifacts.sha256",
        }
        if any(path.exists() for path in targets.values()):
            raise FileExistsError("package freeze evidence already exists; create a new package revision")
        created = datetime.now(timezone.utc).isoformat()
        approval = {
            "schema_version": "1.0.0",
            "package_id": package.package_id,
            "package_semantic_sha256": package.semantic_sha256,
            "operator": operator,
            "created_utc": created,
            "approval_scope": "software_validation_only",
            "irreversible_warning_confirmed": True,
            "new_revision_required_for_change": True,
            "final_test_evaluated": False,
            "scientifically_eligible": False,
            "deployment_allowed": False,
        }
        targets["approval"].write_text(
            json.dumps(approval, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        validation = {
            "schema_version": "1.0.0",
            "package_id": package.package_id,
            "package_semantic_sha256": package.semantic_sha256,
            "package_manifest_file_sha256": artifact_sha256(output / "package_manifest.json"),
            "loader_self_check": "passed",
            "lifecycle": manifest["lifecycle"],
            "final_test_evaluated": False,
            "scientifically_eligible": False,
            "deployment_allowed": False,
            "approval_record_sha256": artifact_sha256(targets["approval"]),
            "created_utc": created,
        }
        targets["validation"].write_text(
            json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = (
            f"# P9-D package freeze report\n\n"
            f"- Package: `{package.package_id}`\n"
            f"- Semantic hash: `{package.semantic_sha256}`\n"
            f"- Lifecycle: `{package.lifecycle}`\n"
            f"- Loader self-check: `passed`\n"
            f"- Scientific eligibility: `false`\n"
            f"- Deployment allowed: `false`\n"
            f"- Final test evaluated: `false`\n"
            f"- Operator: `{operator}`\n\n"
            "Any change to tones, normalization, thresholds, calibration, model, or labels "
            "requires a new package revision; this directory must not be overwritten.\n"
        )
        targets["md"].write_text(report, encoding="utf-8")
        targets["html"].write_text(
            "<!doctype html><meta charset='utf-8'><title>P9-D package freeze</title>"
            f"<pre>{escape(report)}</pre>",
            encoding="utf-8",
        )
        targets["log"].write_text(
            f"{created} loader_self_check=passed package={package.package_id} lifecycle={package.lifecycle}\n",
            encoding="utf-8",
        )
        checksum_targets = sorted(
            path for path in output.iterdir() if path.is_file() and path != targets["checksums"]
        )
        targets["checksums"].write_text(
            "".join(f"{artifact_sha256(path)}  {path.name}\n" for path in checksum_targets),
            encoding="ascii",
        )
        return PackageFreezeEvidence(
            output, package.package_id, package.semantic_sha256, package.lifecycle, True,
            targets["approval"], targets["validation"], targets["md"], targets["html"], targets["checksums"],
        )
