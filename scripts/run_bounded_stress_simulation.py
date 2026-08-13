"""Run the frozen SIM-1 bounded stress simulation from a clean Git commit."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.simulation.bounded_stress import (  # noqa: E402
    execute_prepared_simulation,
    finalize_prepared_simulation,
    prepare_simulation_run,
)


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--resume", action="store_true")
    arguments = parser.parse_args()

    source_commit = _git("rev-parse", "HEAD")
    dirty = bool(_git("status", "--porcelain=v1"))
    if dirty:
        print("SIM-1 正式运行被拒绝：Git 工作树必须干净。", file=sys.stderr)
        return 2
    now = datetime.now(ZoneInfo("Europe/London"))
    output = arguments.output_directory
    if output is None:
        run_id = now.strftime("SIM-1_%Y%m%dT%H%M%S%f%z")
        output = (
            PROJECT_ROOT
            / "outputs"
            / "simulated"
            / "software_validation"
            / "bounded_stress"
            / run_id
        )
    if arguments.resume:
        if not output.is_dir():
            print(f"SIM-1 resume 目录不存在：{output}", file=sys.stderr)
            return 2
    else:
        prepare_simulation_run(
            output_directory=output,
            project_root=PROJECT_ROOT,
            source_commit=source_commit,
            git_dirty=False,
            created_at=now.isoformat(),
            timezone="Europe/London",
        )
    progress = execute_prepared_simulation(output)
    if progress.completed_run_count != 300:
        print(f"SIM-1 base run incomplete: {progress.completed_run_count}/300", file=sys.stderr)
        return 1
    final = finalize_prepared_simulation(output)
    print(f"output_directory={final.output_directory.resolve()}")
    print(f"base_run_count={final.base_run_count}")
    print(f"additional_run_count={final.additional_run_count}")
    print(f"optional_s3_64_triggered={str(final.optional_s3_64_triggered).lower()}")
    print(f"final_decision={final.final_decision}")
    print("final_test_read=false")
    print("scientifically_eligible=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
