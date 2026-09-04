"""Resumable exact80 development-only execution for GEN-ENC-4 M2-B."""

from __future__ import annotations

import json
import math
import argparse
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from acoustic_encoder.gen_enc.actual_fluid_star_network import compile_member_geometry, solve_forward_block
from acoustic_encoder.gen_enc.estimator import projection_matrices, trapezoidal_weights
from acoustic_encoder.gen_enc.forward_acoustic_network import STATE_ANGLES_DEGREES, frozen_frequency_grid
from acoustic_encoder.gen_enc.robust_encoding_geometry import (
    COMPLEX_FEATURE_DIMENSION, FAMILY_ORDER, REAL_FEATURE_DIMENSION, evaluation_unit_weights,
    identity_level_family_inference, pair_anisotropy, summarize_candidate_geometry, weakest_pair_index,
)
from scripts.gen_enc_4_topology_preserving_m0_m1 import exact80_members, nuisance_rows, seeds_for


OUTPUT = REPO / "outputs/gen_enc/GEN_ENC_4_M2B_EXACT80_DEVELOPMENT"
CONTRACT = REPO / "outputs/gen_enc/GEN_ENC_4_M2B_SPINE_WINDOW_PREFLIGHT/exact80_development_contract.json"
COMMON_W = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_d_checkpoint_observer_recovery_01_attempt03/development/sealed/common_w.npz"
CELLS = 3675
REPEATS = 2
FREQUENCIES = 208
CHUNK = 75
CHUNKS = 49


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ready(value: Any) -> Any:
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, complex): return {"real": value.real, "imag": value.imag}
    if isinstance(value, dict): return {str(k): ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [ready(v) for v in value]
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ready(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry_both(raw_base: np.ndarray, raw_spine: np.ndarray, whitener: np.ndarray) -> tuple[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray]:
    weights = trapezoidal_weights(frozen_frequency_grid()[:FREQUENCIES])
    packed = []
    for raw in (raw_base, raw_spine):
        ordered = np.transpose(raw, (1, 2, 4, 3, 0)) * np.sqrt(weights)[None, None, :, None, None]
        y = ordered.reshape((raw.shape[1], REPEATS, COMPLEX_FEATURE_DIMENSION, 4), order="C")
        packed.append(np.asarray(y @ projection_matrices(4)[1], dtype=np.complex128))
    columns = []
    for ydiff in packed:
        embedded = np.concatenate((ydiff.real, ydiff.imag), axis=2)
        columns.append(np.transpose(embedded, (2, 0, 1, 3)).reshape((REAL_FEATURE_DIMENSION, raw_base.shape[1] * REPEATS * 4), order="C"))
    transformed = whitener @ np.concatenate(columns, axis=1)
    split = columns[0].shape[1]
    results = []
    z_values = []
    for index, ydiff in enumerate(packed):
        zreal = np.transpose(transformed[:, index * split:(index + 1) * split].reshape((REAL_FEATURE_DIMENSION, raw_base.shape[1], REPEATS, 4), order="C"), (1, 2, 0, 3))
        singular = np.linalg.svd(zreal, compute_uv=False)[:, :, :3]
        z = zreal[:, :, :COMPLEX_FEATURE_DIMENSION] + 1j * zreal[:, :, COMPLEX_FEATURE_DIMENSION:]
        distances = np.stack([np.linalg.norm(z[:, :, :, left] - z[:, :, :, right], axis=2) for left, right in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))], axis=2)
        grams = np.einsum("crfi,crfj->crij", z.conj(), z, optimize=True)
        grams = 0.5 * (grams + grams.conj().transpose(0, 1, 3, 2))
        trace = np.trace(grams, axis1=2, axis2=3).real
        normalized = grams / trace[:, :, None, None]
        results.append((distances, normalized, singular, ydiff))
        z_values.append(zreal)
    effect_singular = np.linalg.svd(z_values[0] - z_values[1], compute_uv=False)[:, :, :3]
    return results[0], results[1], effect_singular


def generate(member: dict[str, Any], nuisances: list[dict[str, float]], seeds: tuple[int, int], start: int, end: int, base_geometry: tuple, spine_geometry: tuple) -> tuple[np.ndarray, np.ndarray]:
    shape = (4, end - start, REPEATS, 4, FREQUENCIES)
    baseline = np.empty(shape, dtype=np.complex128)
    spine = np.empty(shape, dtype=np.complex128)
    frequencies = frozen_frequency_grid()[:FREQUENCIES]
    for local, cell in enumerate(range(start, end)):
        for repeat in range(REPEATS):
            kwargs = dict(member=member, nuisance=nuisances[cell], cell_index=cell, repeat_index=repeat, frequencies_hz=frequencies, state_angles_degrees=STATE_ANGLES_DEGREES, partition="development", repeat_seed_tuple=seeds, frequency_start_index=0, include_additive_sensor_noise=True)
            baseline[:, local, repeat] = solve_forward_block(spine_only=False, geometry_override=base_geometry, **kwargs).central_pressure
            spine[:, local, repeat] = solve_forward_block(spine_only=True, geometry_override=spine_geometry, **kwargs).central_pressure
    return baseline, spine


def process_identity(entry: dict[str, Any], member: dict[str, Any], identity_path: Path, nuisances: list[dict[str, float]], seeds: tuple[int, int], whitener: np.ndarray) -> dict[str, Any]:
    identity = member["member_id"]
    root = OUTPUT / "candidates" / identity
    summary_path = root / "candidate_summary.json"
    if summary_path.is_file():
        value = load(summary_path)
        if value.get("status") != "PASS" or value.get("identity_sha256") != sha256(identity_path):
            raise RuntimeError("RESUME_MISMATCH")
        return value
    compact = root / "compact"
    compact.mkdir(parents=True, exist_ok=True)
    arrays = {}
    for arm in ("baseline", "spine_only"):
        arrays[(arm,"distances")] = np.lib.format.open_memmap(compact / f"{arm}_distances.npy", mode="w+", dtype="float64", shape=(CELLS,REPEATS,6))
        arrays[(arm,"grams")] = np.lib.format.open_memmap(compact / f"{arm}_grams.npy", mode="w+", dtype="complex128", shape=(CELLS,REPEATS,4,4))
        arrays[(arm,"singulars")] = np.lib.format.open_memmap(compact / f"{arm}_singulars.npy", mode="w+", dtype="float64", shape=(CELLS,REPEATS,3))
    effect_singulars = np.lib.format.open_memmap(compact / "effect_singulars.npy", mode="w+", dtype="float64", shape=(CELLS,REPEATS,3))
    effect_relative = np.lib.format.open_memmap(compact / "effect_relative.npy", mode="w+", dtype="float64", shape=(CELLS,REPEATS))
    effect_gram = np.lib.format.open_memmap(compact / "effect_gram.npy", mode="w+", dtype="float64", shape=(CELLS,REPEATS))
    base_geometry = compile_member_geometry(member, spine_only=False)
    spine_geometry = compile_member_geometry(member, spine_only=True)
    for chunk in range(CHUNKS):
        start, end = chunk * CHUNK, (chunk + 1) * CHUNK
        raw_base, raw_spine = generate(member, nuisances, seeds, start, end, base_geometry, spine_geometry)
        base_result, spine_result, effect_s = geometry_both(raw_base, raw_spine, whitener)
        for arm, result in (("baseline",base_result),("spine_only",spine_result)):
            distances, grams, singulars, _ = result
            arrays[(arm,"distances")][start:end] = distances
            arrays[(arm,"grams")][start:end] = grams
            arrays[(arm,"singulars")][start:end] = singulars
        effect_singulars[start:end] = effect_s
        delta = raw_base - raw_spine
        effect_relative[start:end] = np.sqrt(np.sum(np.abs(delta) ** 2, axis=(0,3,4))) / np.sqrt(np.sum(np.abs(raw_base) ** 2, axis=(0,3,4)))
        effect_gram[start:end] = np.linalg.norm(base_result[1] - spine_result[1], ord="fro", axis=(2,3))
    summaries = {}
    for arm in ("baseline","spine_only"):
        distances = np.asarray(arrays[(arm,"distances")])
        grams = np.asarray(arrays[(arm,"grams")])
        reference = np.mean(grams, axis=(0,1)); reference = 0.5*(reference+reference.conj().T); reference /= np.trace(reference).real
        drift = np.linalg.norm(grams-reference[None,None], ord="fro", axis=(2,3))
        metrics = summarize_candidate_geometry(distances.reshape((-1,6)), drift.reshape(-1), evaluation_unit_weights())
        singular = np.sort(np.asarray(arrays[(arm,"singulars")]).reshape((-1,3)), axis=0, kind="stable")
        q = singular[int(np.ceil(.05*singular.shape[0])-1)]
        summaries[arm] = {"metrics": metrics, "sigma_0p05": q, "E_primary": float(q[2]), "r_stable": int(np.sum(q>1.0)), "feasible": bool(q[2]>1.0 and np.sum(q>1.0)==3)}
    for value in (*arrays.values(), effect_singulars, effect_relative, effect_gram): value.flush()
    summary = {
        "schema_version":"gen_enc_4_m2b_exact80_candidate_summary_v1", "status":"PASS", "identity_id":identity, "family_id":member["family_id"],
        "identity_sha256":sha256(identity_path), "arms":summaries,
        "effect":{"relative_response_mean":float(np.mean(effect_relative)), "relative_response_median":float(np.median(effect_relative)), "relative_response_q25":float(np.quantile(effect_relative,.25)), "gram_shift_mean":float(np.mean(effect_gram)), "gram_shift_median":float(np.median(effect_gram))},
        "geometry":{"baseline_root_lengths_m":[x.root_length_m for x in base_geometry], "spine_only_root_lengths_m":[x.root_length_m for x in spine_geometry], "maximum_volume_residual_m3":max(abs(x.segment_volume_m3-x.target_volume_m3) for x in (*base_geometry,*spine_geometry))},
        "compact":{"effect_singulars":{"path":(compact/"effect_singulars.npy").relative_to(REPO).as_posix(),"sha256":sha256(compact/"effect_singulars.npy")}},
        "validation_reads":0,"final_test_read":False,
    }
    write(summary_path, summary)
    return summary


def separation(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    matrix = np.asarray([[x["effect"]["relative_response_mean"],x["effect"]["relative_response_median"],x["effect"]["gram_shift_mean"],x["effect"]["gram_shift_median"]] for x in summaries])
    scale=np.std(matrix,axis=0,ddof=1); usable=scale>np.finfo(float).eps; z=(matrix[:,usable]-np.mean(matrix[:,usable],axis=0))/scale[usable]
    centroids=np.stack([np.mean(z[i*20:(i+1)*20],axis=0) for i in range(4)])
    within=np.asarray([math.sqrt(float(np.mean(np.sum((z[i*20:(i+1)*20]-centroids[i])**2,axis=1)))) for i in range(4)])
    records=[]
    for left,right in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3)):
        pooled=math.sqrt(.5*(within[left]**2+within[right]**2)); records.append({"families":[FAMILY_ORDER[left],FAMILY_ORDER[right]],"ratio":float(np.linalg.norm(centroids[left]-centroids[right])/pooled)})
    return {"signature":"MEAN_MEDIAN_RELATIVE_RESPONSE_AND_GRAM_ABLATION_EFFECT", "usable_dimensions":int(np.sum(usable)), "pairwise":records, "minimum_between_within_ratio":min(x["ratio"] for x in records), "mean_between_within_ratio":float(np.mean([x["ratio"] for x in records]))}


def arm_separation(summaries: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    rows=[]
    for item in summaries:
        metric=item["arms"][arm]["metrics"]
        pair=np.asarray(metric["pair_lower_tail_es_0p05"],dtype=float); pair/=np.mean(pair)
        rows.append(np.concatenate((pair,np.asarray([metric["pair_anisotropy_mean"],metric["pair_anisotropy_upper_tail_es_0p05"],metric["gram_frobenius_drift_mean"],metric["gram_frobenius_drift_upper_tail_es_0p05"]]))))
    matrix=np.stack(rows); scale=np.std(matrix,axis=0,ddof=1); usable=scale>np.finfo(float).eps; z=(matrix[:,usable]-np.mean(matrix[:,usable],axis=0))/scale[usable]
    centroids=np.stack([np.mean(z[i*20:(i+1)*20],axis=0) for i in range(4)]); within=np.asarray([math.sqrt(float(np.mean(np.sum((z[i*20:(i+1)*20]-centroids[i])**2,axis=1)))) for i in range(4)])
    ratios=[]
    for left,right in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3)):
        ratios.append(float(np.linalg.norm(centroids[left]-centroids[right])/math.sqrt(.5*(within[left]**2+within[right]**2))))
    return {"minimum_between_within_ratio":min(ratios),"mean_between_within_ratio":float(np.mean(ratios)),"pairwise_ratios":ratios,"usable_dimensions":int(np.sum(usable))}


def aggregate(members: list[tuple[dict[str, Any], dict[str, Any], Path]], started: float) -> int:
    summaries=[]
    for _, member, _ in members:
        path=OUTPUT/"candidates"/member["member_id"]/"candidate_summary.json"
        if not path.is_file(): raise RuntimeError(f"MISSING_EXACT80_SUMMARY:{member['member_id']}")
        summaries.append(load(path))
    if len(summaries)!=80: raise RuntimeError("EXACT80_REQUIRED")
    sep=separation(summaries)
    margin={family:np.asarray([x["effect"]["relative_response_mean"] for x in summaries if x["family_id"]==family]) for family in FAMILY_ORDER}
    drift={family:np.asarray([x["effect"]["gram_shift_mean"] for x in summaries if x["family_id"]==family]) for family in FAMILY_ORDER}
    inference=identity_level_family_inference(margin,drift)
    adjusted=np.asarray(inference["permutation"]["adjusted_p"]) if inference.get("permutation") else np.asarray([])
    fwer_endpoints=int(np.sum(adjusted<.05))
    fwer_pairs=int(sum(bool(adjusted[index] < .05 or adjusted[index + 6] < .05) for index in range(6))) if adjusted.size == 12 else 0
    effect_singular=np.concatenate([np.load(REPO/x["compact"]["effect_singulars"]["path"],allow_pickle=False).reshape((-1,3)) for x in summaries],axis=0)
    q=np.sort(effect_singular,axis=0,kind="stable")[int(np.ceil(.05*effect_singular.shape[0])-1)]
    effect_rank=int(np.sum(q>1.0))
    all_feasible=all(x["arms"][arm]["feasible"] for x in summaries for arm in ("baseline","spine_only"))
    passed=bool(all_feasible and sep["minimum_between_within_ratio"]>=1.0 and effect_rank>=3 and fwer_pairs>=1)
    terminal="M2B_DEVELOPMENT_MECHANISM_FAMILY_STRUCTURED" if passed else "M2B_DEVELOPMENT_NO_FAMILY_STRUCTURED_MECHANISM"
    write(OUTPUT/"inference_summary.json",inference)
    result={"terminal_state":terminal,"complete_identities":80,"all_arms_feasible":all_feasible,"effect_sigma_0p05":q,"effect_r_stable":effect_rank,"effect_geometry_separation":sep,"arm_geometry_separation":{"CAD_BASELINE":arm_separation(summaries,"baseline"),"SPINE_ONLY_ABLATION":arm_separation(summaries,"spine_only")},"fwer_significant_endpoint_count":fwer_endpoints,"fwer_significant_family_pair_count":fwer_pairs,"minimum_adjusted_p":float(np.min(adjusted)) if adjusted.size else None,"validation_authorized":False,"m3_authorized":False,"next_action":"REQUEST_SEPARATE_M2B_VALIDATION_CONTRACT" if passed else "STOP_M2_AND_DO_NOT_ENTER_M3","aggregation_wall_seconds":time.perf_counter()-started,"validation_reads":0,"final_test_read":False,"technical_correction":"NEAR_SHARED_ALPHA_BINARY64_NORMALIZED_COORDINATE_CLAMP_REUSED_FROM_M1"}
    write(OUTPUT/"result_summary.json",result); write(OUTPUT/"checkpoint.json",{"status":"COMPLETE","terminal_sha256":sha256(OUTPUT/"result_summary.json"),"final_test_read":False})
    write(OUTPUT/"source_manifest.json",{"entries":{name:{"path":path.relative_to(REPO).as_posix(),"sha256":sha256(path)} for name,path in {"runner":Path(__file__).resolve(),"model":REPO/"src/acoustic_encoder/gen_enc/actual_fluid_star_network.py","contract":CONTRACT,"common_w":COMMON_W,"independent_verifier":REPO/"scripts/gen_enc_4_m2b_exact80_independent_verifier.py"}.items()},"validation_reads":0,"final_test_read":False})
    print(terminal)
    return 0


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--start",type=int,default=0)
    parser.add_argument("--end",type=int,default=80)
    parser.add_argument("--aggregate-only",action="store_true")
    args=parser.parse_args()
    contract=load(CONTRACT)
    if contract["status"]!="CONTRACT_FROZEN_EXECUTION_NOT_STARTED" or contract["validation_authorized"] or contract["m3_authorized"]: raise RuntimeError("CONTRACT_SCOPE_FAIL")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    members=exact80_members(); nuisances=nuisance_rows(); seeds=seeds_for("development")
    started=time.perf_counter()
    if args.aggregate_only:
        return aggregate(members,started)
    if not 0<=args.start<args.end<=80: raise RuntimeError("INVALID_WORKER_RANGE")
    with np.load(COMMON_W,allow_pickle=False) as data: whitener=np.asarray(data["operator"],dtype=float)
    completed=0
    for absolute in range(args.start,args.end):
        entry,member,path=members[absolute]
        process_identity(entry,member,path,nuisances,seeds,whitener); completed+=1
        write(OUTPUT/f"checkpoint_worker_{args.start:02d}_{args.end:02d}.json",{"status":"IN_PROGRESS","range":[args.start,args.end],"completed_in_range":completed,"last_identity":member["member_id"],"validation_reads":0,"final_test_read":False})
        print(json.dumps({"worker_range":[args.start,args.end],"completed":absolute+1,"identity":member["member_id"]}),flush=True)
    write(OUTPUT/f"checkpoint_worker_{args.start:02d}_{args.end:02d}.json",{"status":"COMPLETE","range":[args.start,args.end],"completed_in_range":completed,"validation_reads":0,"final_test_read":False})
    print(f"WORKER_COMPLETE_{args.start}_{args.end}")
    return 0


if __name__=="__main__": raise SystemExit(main())
