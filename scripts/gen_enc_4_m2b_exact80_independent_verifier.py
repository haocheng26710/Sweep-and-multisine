"""Independent result verifier for M2-B exact80 development execution."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np


REPO=Path(__file__).resolve().parents[1]
ROOT=REPO/"outputs/gen_enc/GEN_ENC_4_M2B_EXACT80_DEVELOPMENT"
CONTRACT=REPO/"outputs/gen_enc/GEN_ENC_4_M2B_SPINE_WINDOW_PREFLIGHT/exact80_development_contract.json"
FAMILIES=("HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED")


def load(path:Path)->dict: return json.loads(path.read_text(encoding="utf-8"))
def digest(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()


def main()->int:
    contract=load(CONTRACT); result=load(ROOT/"result_summary.json"); inference=load(ROOT/"inference_summary.json")
    if contract["validation_authorized"] or contract["m3_authorized"] or result["validation_reads"]!=0 or result["final_test_read"]: raise RuntimeError("SCOPE_SEAL_FAIL")
    summaries=[]
    for family in FAMILIES:
        prefix={"HAND_DESIGNED":"HAND","NEAR_INDEPENDENT":"NEAR","FIXED_SEED_RANDOM_DISORDERED":"RANDOM","PHYSICS_METAMATERIAL_INSPIRED":"PHYSICS"}[family]
        for ordinal in range(1,21):
            value=load(ROOT/"candidates"/f"{prefix}_{ordinal:02d}"/"candidate_summary.json")
            if value["family_id"]!=family or value["status"]!="PASS": raise RuntimeError("ORDER_OR_STATUS_FAIL")
            summaries.append(value)
    if len(summaries)!=80 or not all(x["arms"][arm]["feasible"] for x in summaries for arm in ("baseline","spine_only")): raise RuntimeError("EXACT80_FEASIBILITY_FAIL")
    matrix=np.asarray([[x["effect"]["relative_response_mean"],x["effect"]["relative_response_median"],x["effect"]["gram_shift_mean"],x["effect"]["gram_shift_median"]] for x in summaries])
    scale=np.std(matrix,axis=0,ddof=1); usable=scale>np.finfo(float).eps; z=(matrix[:,usable]-np.mean(matrix[:,usable],axis=0))/scale[usable]
    centroids=np.stack([np.mean(z[i*20:(i+1)*20],axis=0) for i in range(4)])
    within=np.asarray([math.sqrt(float(np.mean(np.sum((z[i*20:(i+1)*20]-centroids[i])**2,axis=1)))) for i in range(4)])
    ratios=[]
    for left,right in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3)):
        ratios.append(float(np.linalg.norm(centroids[left]-centroids[right])/math.sqrt(.5*(within[left]**2+within[right]**2))))
    np.testing.assert_allclose(ratios,[x["ratio"] for x in result["effect_geometry_separation"]["pairwise"]],rtol=1e-13,atol=0.0)
    singular=np.concatenate([np.load(REPO/x["compact"]["effect_singulars"]["path"],allow_pickle=False).reshape((-1,3)) for x in summaries],axis=0)
    q=np.sort(singular,axis=0,kind="stable")[int(np.ceil(.05*singular.shape[0])-1)]; rank=int(np.sum(q>1.0))
    adjusted=np.asarray(inference["permutation"]["adjusted_p"],dtype=float)
    endpoints=int(np.sum(adjusted<.05)); pairs=int(sum(bool(adjusted[i]<.05 or adjusted[i+6]<.05) for i in range(6)))
    passed=bool(min(ratios)>=contract["terminal_pass"]["paired_effect_between_within_ratio_min"] and rank>=contract["terminal_pass"]["stable_rank_min"] and pairs>=contract["terminal_pass"]["minimum_fwer_significant_family_pairs"])
    expected="M2B_DEVELOPMENT_MECHANISM_FAMILY_STRUCTURED" if passed else "M2B_DEVELOPMENT_NO_FAMILY_STRUCTURED_MECHANISM"
    if result["terminal_state"]!=expected or result["fwer_significant_endpoint_count"]!=endpoints or result["fwer_significant_family_pair_count"]!=pairs: raise RuntimeError("TERMINAL_OR_FWER_FAIL")
    np.testing.assert_allclose(q,result["effect_sigma_0p05"],rtol=1e-13,atol=0.0)
    report={"verifier":"PASS","complete_identities":80,"all_arms_feasible":True,"minimum_between_within_ratio_recomputed":min(ratios),"effect_r_stable_recomputed":rank,"fwer_significant_endpoint_count_recomputed":endpoints,"fwer_significant_family_pair_count_recomputed":pairs,"terminal_state_recomputed":expected,"result_sha256":digest(ROOT/"result_summary.json"),"validation_reads":0,"final_test_read":False}
    (ROOT/"independent_verification.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("M2B_EXACT80_INDEPENDENT_VERIFICATION_PASS")
    return 0


if __name__=="__main__": raise SystemExit(main())
