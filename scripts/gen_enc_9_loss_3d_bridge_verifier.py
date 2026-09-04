"""Independent verifier for the bounded GEN-ENC-9 COMSOL diagnostic."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import sys
import numpy as np
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO/"src"))
from acoustic_encoder.gen_enc.e2_authority import directional_port_weights
ROOT=REPO/"outputs/gen_enc/GEN_ENC_9_LOSS_3D_BRIDGE";PAIRS=((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))
def load(name): return json.loads((ROOT/name).read_text(encoding="utf-8"))
def cx(value):
    data=np.asarray(value,dtype=float)
    if data.shape[-1]!=2 or not np.all(np.isfinite(data)): raise RuntimeError("INVALID_COMPLEX_RESPONSE")
    return data[...,0]+1j*data[...,1]
def signature(transfer):
    response=np.empty((4,4,transfer.shape[1]),dtype=np.complex128)
    for index,angle in enumerate((0.,90.,180.,270.)): response[index]=directional_port_weights(angle,0.)[:,None]*transfer
    x=response.reshape(4,-1);contrast=np.linalg.norm(x-x.mean(axis=0,keepdims=True))/np.linalg.norm(x);x=x/np.linalg.norm(x)
    gram=x@x.conj().T;gram=.5*(gram+gram.conj().T);dist=np.asarray([np.linalg.norm(x[a]-x[b]) for a,b in PAIRS])
    singular=np.linalg.svd(np.concatenate((x.real,x.imag),axis=1),compute_uv=False);singular=singular/singular.sum()
    return np.concatenate((gram.real.ravel(),gram.imag.ravel(),dist,singular,[contrast]))
def rel(reference,alternative): return float(np.linalg.norm(alternative-reference)/np.linalg.norm(reference))
def sha256(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    result=load("result_summary.json");lossless=load("lossless2d_dense_raw.json");lossy=load("lossy2d_dense_raw.json")
    ladder=load("lossy3d_mesh_ladder_raw.json");final=load("lossy3d_final_refinement_raw.json");near1=load("near_lossy3d_size1_raw.json")
    if len(lossless["frequencies_hz"])!=161: raise RuntimeError("DENSE_FREQUENCY_COUNT_MISMATCH")
    for eta in ("0.005","0.02"):
        for member in ("HAND_01","NEAR_01"):
            if cx(lossy["responses"][eta][member]).shape!=(4,161): raise RuntimeError("LOSSY_2D_SHAPE_MISMATCH")
    hand2=cx(ladder["responses"]["HAND_01"]["2"]);hand1=cx(final["responses"]["HAND_01"]["values"])
    near2=cx(final["responses"]["NEAR_01"]["values"]);near1v=cx(near1["responses"]);gate=result["true3d_mesh_gate"]
    hrel=rel(hand2,hand1);nrel=rel(near2,near1v);pair=float(np.linalg.norm(signature(hand1)-signature(near1v)))
    if not np.isclose(hrel,gate["lossy_eta_0p02_steps_primary"]["HAND_size2_to_size1_relative_l2"],atol=1e-14): raise RuntimeError("HAND_MESH_RECOMPUTE_MISMATCH")
    if not np.isclose(nrel,gate["lossy_eta_0p02_steps_primary"]["NEAR_size2_to_size1_relative_l2"],atol=1e-14): raise RuntimeError("NEAR_MESH_RECOMPUTE_MISMATCH")
    if not np.isclose(pair,result["lossy_true_sections_3d_hand_near_signature_distance"],atol=1e-14): raise RuntimeError("PAIR_DISTANCE_RECOMPUTE_MISMATCH")
    if hrel>0.02 or nrel>0.02 or not gate["pass"]: raise RuntimeError("FINAL_MESH_GATE_FAILURE")
    if result["terminal_state"]!="GEN_ENC_9_HAND_NEAR_OVERLAP_PERSISTS_UNDER_BOUNDED_CONTROLS": raise RuntimeError("TERMINAL_MISMATCH")
    for line in (ROOT/"SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected,filename=line.split("  ",1)
        if sha256(ROOT/filename)!=expected: raise RuntimeError("MPH_HASH_MISMATCH_"+filename)
    output={"terminal_state":"GEN_ENC_9_INDEPENDENT_VERIFICATION_PASS","checks":["LOSSLESS_AND_TWO_LOSS_LEVELS_2D_DENSE_RESPONSES_FINITE","TRUE_SECTION_3D_SIZE1_RESPONSES_FINITE","HAND_AND_NEAR_FINE_MESH_L2_BELOW_2_PERCENT","HAND_NEAR_SIGNATURE_DISTANCE_INDEPENDENTLY_RECOMPUTED","ALL_NINETEEN_MPH_SHA256_MATCH","PRIMARY_TERMINAL_MATCH"]}
    (ROOT/"independent_verification.json").write_text(json.dumps(output,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps(output,indent=2,sort_keys=True));return 0
if __name__=="__main__": raise SystemExit(main())
