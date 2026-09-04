"""Regression gate for MPh display-name lookup versus COMSOL Java study tags."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mph


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_trans0_retry01.py"
OUTPUT = HERE / "study_tag_label_audit.json"


def source_gate() -> dict:
    source = RUNNER.read_text(encoding="utf-8")
    checks = {
        "legacy_literal_absent": 'model.solve("std_freq")' not in source,
        "java_study_tags_checked": "model.java.study().tags()" in source,
        "std_freq_tag_resolved": 'model.java.study("std_freq")' in source,
        "frequency_feature_tags_checked": "study.feature().tags()" in source,
        "direct_java_run_present": "study.run()" in source,
    }
    checks["pass"] = all(checks.values())
    return checks


def live_lookup_probe(port: int) -> dict:
    client = mph.Client(version="6.4", port=port)
    model = client.create("TRANS0_RETRY01_STUDY_TAG_LABEL_PROBE")
    try:
        java = model.java
        study = java.study().create("std_freq")
        study.label("Retry 01 Display Label Probe")
        study.create("freq", "Frequency")
        study_tags = [str(tag) for tag in java.study().tags()]
        feature_tags = [str(tag) for tag in java.study("std_freq").feature().tags()]
        label = str(java.study("std_freq").label())
        legacy_error = None
        try:
            model.solve("std_freq")
        except Exception as exc:
            legacy_error = f"{type(exc).__name__}: {exc}"
        result = {
            "comsol_version": str(client.version),
            "java_study_tags": study_tags,
            "study_tag": "std_freq",
            "study_label": label,
            "feature_tags": feature_tags,
            "legacy_mph_lookup_failed": legacy_error is not None,
            "legacy_mph_error": legacy_error,
            "tag_and_label_distinct": label != "std_freq",
            "direct_java_study_resolved": str(java.study("std_freq").tag()) == "std_freq",
            "frequency_feature_present": "freq" in feature_tags,
        }
        result["pass"] = all(("std_freq" in study_tags, result["legacy_mph_lookup_failed"],
                              result["tag_and_label_distinct"], result["direct_java_study_resolved"],
                              result["frequency_feature_present"]))
        return result
    finally:
        client.remove(model)
        client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    source = source_gate()
    live = None
    if not args.static_only:
        if args.port is None:
            raise SystemExit("--port is required")
        live = live_lookup_probe(args.port)
    result = {"source_gate": source, "live_lookup_probe": live,
              "pass": bool(source["pass"] and (live is None or live["pass"]))}
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
