"""Windows-compatible process-tree resource accounting for formal E2."""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
import time
from typing import Sequence

import psutil


@dataclass
class ResourceLedger:
    wall_start: float
    parent: psutil.Process
    parent_cpu_start: float
    child_cpu_seconds: float = 0.0
    aggregate_peak_rss_bytes: int = 0

    @classmethod
    def start(cls) -> "ResourceLedger":
        parent = psutil.Process()
        times = parent.cpu_times()
        ledger = cls(time.perf_counter(), parent, times.user + times.system)
        ledger.sample_tree()
        return ledger

    def sample_tree(self) -> None:
        processes = [self.parent]
        try:
            processes.extend(self.parent.children(recursive=True))
        except (psutil.Error, OSError):
            pass
        rss = 0
        for process in processes:
            try:
                rss += int(process.memory_info().rss)
            except (psutil.Error, OSError):
                continue
        self.aggregate_peak_rss_bytes = max(self.aggregate_peak_rss_bytes, rss)

    def run_child(self, argv: Sequence[str], *, cwd: str) -> subprocess.CompletedProcess[str]:
        process = subprocess.Popen(list(argv), cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        child = psutil.Process(process.pid)
        maximum_cpu = 0.0
        while process.poll() is None:
            self.sample_tree()
            try:
                members = [child] + child.children(recursive=True)
                maximum_cpu = max(maximum_cpu, sum(p.cpu_times().user + p.cpu_times().system for p in members if p.is_running()))
            except (psutil.Error, OSError):
                pass
            time.sleep(0.01)
        stdout, stderr = process.communicate()
        self.sample_tree()
        self.child_cpu_seconds += maximum_cpu
        return subprocess.CompletedProcess(list(argv), process.returncode, stdout, stderr)

    def snapshot(self) -> dict[str, float | int]:
        self.sample_tree()
        times = self.parent.cpu_times()
        parent_cpu = times.user + times.system - self.parent_cpu_start
        return {"wall_seconds": time.perf_counter() - self.wall_start,
                "cpu_core_seconds": parent_cpu + self.child_cpu_seconds,
                "aggregate_peak_rss_bytes": self.aggregate_peak_rss_bytes,
                "method_version": "PSUTIL_WINDOWS_PROCESS_TREE_SAMPLE_10MS_V1"}
