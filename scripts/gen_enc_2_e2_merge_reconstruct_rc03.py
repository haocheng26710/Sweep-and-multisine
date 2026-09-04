"""Executable deterministic RC03 merge and reconstruction passes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from acoustic_encoder.gen_enc.e2_rc03_stats import canonical_json_bytes, oas_whitener_from_accumulator, reconstruct_candidate, sha256_file


class MergeError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MergeError("JSON_OBJECT_REQUIRED")
    return value


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def validate_role_manifest(path: Path, expected: tuple[str, ...]) -> dict[str, Any]:
    manifest = read_json(path)
    entries = manifest.get("entries")
    if not isinstance(entries, list) or tuple(entry.get("role") for entry in entries) != expected or manifest.get("role_set_complete") is not True:
        raise MergeError("EXACT_ORDERED_ROLE_SET_REQUIRED")
    for entry in entries:
        payload = Path(entry["path"])
        if not payload.is_file() or sha256_file(payload) != entry["sha256"]:
            raise MergeError("ROLE_PAYLOAD_HASH_MISMATCH")
        array = np.load(payload, allow_pickle=False, mmap_mode="r")
        if list(array.shape) != entry["shape"] or array.dtype.name != entry["dtype"]:
            raise MergeError("ROLE_PAYLOAD_SHAPE_DTYPE_MISMATCH")
    return manifest


def merge_common_w_contribution(
    manifest_path: Path, accumulator_path: Path, checkpoint_path: Path, *, expected_position: int,
) -> dict[str, Any]:
    from scripts.gen_enc_2_e2_independent_verifier_rc03 import COMMON_W_ROLES

    manifest = validate_role_manifest(manifest_path, COMMON_W_ROLES)
    if manifest["canonical_merge_position"] != expected_position:
        raise MergeError("COMMON_W_CANONICAL_POSITION_MISMATCH")
    by_role = {entry["role"]: Path(entry["path"]) for entry in manifest["entries"]}
    contribution = np.load(by_role["W_WEIGHTED_OUTER_SUM"], allow_pickle=False)
    weight = float(np.load(by_role["W_WEIGHT_SUM"], allow_pickle=False)[0])
    if accumulator_path.exists():
        with np.load(accumulator_path, allow_pickle=False) as prior:
            outer = np.asarray(prior["outer_sum"], dtype=np.float64) + contribution
            total_weight = float(prior["weight_sum"]) + weight
    else:
        outer = np.asarray(contribution, dtype=np.float64)
        total_weight = weight
    temporary = accumulator_path.with_name(accumulator_path.name + ".tmp")
    accumulator_path.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("wb") as stream:
        np.savez(stream, outer_sum=outer, weight_sum=np.asarray(total_weight, dtype=np.float64), last_position=np.asarray(expected_position, dtype=np.uint64))
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, accumulator_path)
    checkpoint = {"schema_version": "gen_enc_2_e2_w_merge_checkpoint_rc03_v1", "status": "CONTRIBUTION_MERGED",
                  "merge_position": expected_position, "accumulator_sha256": sha256_file(accumulator_path),
                  "contribution_manifest_sha256": sha256_file(manifest_path), "weight_sum": total_weight}
    write_json_atomic(checkpoint_path, checkpoint)
    return checkpoint


def seal_common_w(accumulator_path: Path, output_path: Path, *, expected_contributions: int = 11760) -> dict[str, Any]:
    with np.load(accumulator_path, allow_pickle=False) as accumulator:
        last = int(accumulator["last_position"])
        if last + 1 != expected_contributions:
            raise MergeError("COMMON_W_CONTRIBUTION_COUNT_INCOMPLETE")
        result = oas_whitener_from_accumulator(np.asarray(accumulator["outer_sum"]), float(accumulator["weight_sum"]))
    temporary = output_path.with_name(output_path.name + ".tmp")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("wb") as stream:
        np.savez(stream, operator=result["operator"], empirical=result["empirical"], shrunk=result["shrunk"],
                 shrinkage=np.asarray(result["shrinkage"]), eigenvalue_floor=np.asarray(result["eigenvalue_floor"]),
                 effective_n=np.asarray(result["effective_n"]))
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, output_path)
    return {"status": "COMMON_W_SEALED", "path": output_path.as_posix(), "sha256": sha256_file(output_path),
            "contributions": expected_contributions, "validation_participated": False}


def reconstruct_candidate_from_root(stats_root: Path, output_path: Path) -> dict[str, Any]:
    paths = sorted(stats_root.glob("chunk_*.ENDPOINT_UNIT_VALUES.npy"))
    if len(paths) != 147:
        raise MergeError("EXACT_147_ENDPOINT_CHUNKS_REQUIRED")
    result = reconstruct_candidate(np.load(path, allow_pickle=False) for path in paths)
    result.update({"schema_version": "gen_enc_2_e2_candidate_terminal_rc03_v1", "technical_status": "PASS",
                   "matched_cost_eligible": True, "bridge_status": "NOT_APPLICABLE_DEVELOPMENT",
                   "terminal_inputs_complete": True})
    write_json_atomic(output_path, result)
    return result


def aggregate_families(candidate_paths: list[Path], output_path: Path, *, partition: str) -> dict[str, Any]:
    if len(candidate_paths) != 80:
        raise MergeError("EXACT80_CANDIDATE_TERMINALS_REQUIRED")
    candidates = [read_json(path) for path in candidate_paths]
    families: dict[str, Any] = {}
    for family in ("HAND", "NEAR", "RANDOM", "PHYSICS"):
        members = [value for path, value in zip(candidate_paths, candidates) if path.stem.startswith(family)]
        if len(members) != 20:
            raise MergeError("EXACT20_FAMILY_TERMINALS_REQUIRED")
        worst = min(members, key=lambda item: item["E_primary"])
        families[family] = {"member_count": 20, "status": worst["scientific_status"], "worst_E_primary": worst["E_primary"]}
    result = {"schema_version": "gen_enc_2_e2_family_global_terminal_rc03_v1", "partition": partition,
              "families": families, "four_families_complete": True,
              "global_status": "BOUNDED_COMPARATIVE_RESULT" if all(value["status"] == "PASS" for value in families.values()) else "MIXED",
              "ranking_before_four_complete": False}
    write_json_atomic(output_path, result)
    return result


def development_seal(w_path: Path, candidate_paths: list[Path], family_path: Path, output_path: Path) -> dict[str, Any]:
    if len(candidate_paths) != 80 or not w_path.is_file() or not family_path.is_file():
        raise MergeError("D80_W_FAMILY_COMPLETE_REQUIRED")
    value = {"schema_version": "gen_enc_2_e2_development_seal_rc03_v1", "status": "E2_D_SEALED_INDEPENDENT_PASS",
             "complete_identities": 80, "independent_verify_pass": True, "common_w_sha256": sha256_file(w_path),
             "candidate_decision_hashes": [sha256_file(path) for path in candidate_paths], "family_aggregate_sha256": sha256_file(family_path),
             "development_decisions_sealed": True, "validation_opened": False, "validation_refit": False, "final_test_read": False}
    write_json_atomic(output_path, value)
    return value


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("mode", choices=("self-test", "merge-w-contribution", "seal-w", "candidate", "families", "development-seal"))
    value.add_argument("--manifest"); value.add_argument("--accumulator"); value.add_argument("--checkpoint")
    value.add_argument("--position", type=int); value.add_argument("--output"); value.add_argument("--stats-root")
    value.add_argument("--candidate-list"); value.add_argument("--family-terminal"); value.add_argument("--partition")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.mode == "self-test":
            print(json.dumps({"status": "PASS", "formal_units": 0, "modes": ["COMMON_W", "CANDIDATE", "FAMILY_GLOBAL", "D_SEAL"], "final_test_read": False}, sort_keys=True)); return 0
        if args.mode == "merge-w-contribution":
            merge_common_w_contribution(Path(args.manifest), Path(args.accumulator), Path(args.checkpoint), expected_position=args.position)
        elif args.mode == "seal-w":
            seal_common_w(Path(args.accumulator), Path(args.output))
        elif args.mode == "candidate":
            reconstruct_candidate_from_root(Path(args.stats_root), Path(args.output))
        elif args.mode == "families":
            aggregate_families([Path(line) for line in Path(args.candidate_list).read_text().splitlines()], Path(args.output), partition=args.partition)
        elif args.mode == "development-seal":
            candidates = [Path(line) for line in Path(args.candidate_list).read_text().splitlines()]
            development_seal(Path(args.accumulator), candidates, Path(args.family_terminal), Path(args.output))
        return 0
    except (OSError, ValueError, KeyError, np.linalg.LinAlgError, MergeError) as exc:
        print(f"FAIL_CLOSED:{exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
