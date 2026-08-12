from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    PROJECT_ROOT
    / "validation_assets"
    / "pre_experiment_acceptance"
    / "build_verification.json"
)

COMMANDS = {
    "v1_sweep_cli": (
        sys.executable,
        str(PROJECT_ROOT / "scripts/run_pipeline.py"),
        "--config",
        str(PROJECT_ROOT / "config/experiment_v2_u4.yaml"),
    ),
    "focused_compatibility_and_leakage": (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--disable-warnings",
        "tests/test_pipeline_cli.py",
        "tests/test_io_rew.py",
        "tests/test_config.py",
        "tests/test_research_gate.py",
        "tests/test_tone_selection.py",
        "tests/test_projection_ablation.py",
        "tests/test_cross_mode_bridge.py",
        "tests/test_offline_readout.py",
    ),
    "key_dev_b_to_c15_e2e": (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--disable-warnings",
        "tests/test_matched_tone_e2e.py",
        "tests/test_dataset_quality_e2e.py",
        "tests/test_metrics_e2e.py",
        "tests/test_classification_validation.py",
        "tests/test_cross_mode_bridge_validation_e2e.py",
        "tests/test_offline_readout_validation_e2e.py",
    ),
    "full_pytest": (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--disable-warnings",
    ),
    "compileall": (
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "src",
        "scripts",
        "tests",
    ),
    "git_diff_check": ("git", "diff", "--check"),
}


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments),
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    results: dict[str, object] = {}
    failed = False
    environment = os.environ.copy()
    environment["QT_API"] = "pyside6"
    environment["QT_QPA_PLATFORM"] = "offscreen"
    # Build logs are audit evidence for developers, not frozen runtime assets.
    log_root = PROJECT_ROOT / "build" / "acceptance_verification_logs"
    log_root.mkdir(parents=True, exist_ok=True)
    # Bypass pytest's shared per-user root (which can retain restrictive ACLs)
    # while keeping deeply nested legacy Windows E2E paths below MAX_PATH.
    temp_root = Path(tempfile.mkdtemp(prefix="ac-"))
    temp_names = {
        "focused_compatibility_and_leakage": "f",
        "key_dev_b_to_c15_e2e": "k",
        "full_pytest": "a",
    }
    for command_id, original_command in COMMANDS.items():
        command = original_command
        if len(command) >= 3 and command[1:3] == ("-m", "pytest"):
            command = (
                *command[:3],
                "--basetemp",
                str(temp_root / temp_names[command_id]),
                *command[3:],
            )
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        combined = completed.stdout + completed.stderr
        (log_root / f"{command_id}.txt").write_text(combined, encoding="utf-8")
        failed = failed or completed.returncode != 0
        results[command_id] = {
            "command_id": command_id,
            "command": list(command),
            "exit_code": completed.returncode,
            "status": "pass" if completed.returncode == 0 else "fail",
            "summary_tail": combined.strip().splitlines()[-1] if combined.strip() else "",
            "output_sha256": _sha256_text(combined),
        }
    payload = {
        "schema_version": "1.0.0",
        "purpose": "software_validation",
        "scientifically_eligible": False,
        "final_test_read": False,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source_commit": _git("rev-parse", "HEAD"),
        "source_branch": _git("branch", "--show-current"),
        "source_git_dirty": bool(_git("status", "--porcelain")),
        "python_version": platform.python_version(),
        "verification": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(temp_root, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
