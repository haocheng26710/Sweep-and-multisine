"""OBS-A development-only localisation of GEN-ENC information loss."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO)); sys.path.insert(0,str(REPO/"src"))

from acoustic_encoder.gen_enc.actual_fluid_star_network import compile_member_geometry, solve_clean_node_pressure_block, solve_forward_block
from acoustic_encoder.gen_enc.forward_acoustic_network import STATE_ANGLES_DEGREES, frozen_frequency_grid
from acoustic_encoder.gen_enc.robust_encoding_geometry import FAMILY_ORDER
from scripts.gen_enc_4_topology_preserving_m0_m1 import exact80_members, seeds_for


OUTPUT=REPO/"outputs/gen_enc/GEN_ENC_5_OBSA_READOUT_BOTTLENECK"
NUISANCE=REPO/"outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
M2B_RESULT=REPO/"outputs/gen_enc/GEN_ENC_4_M2B_EXACT80_DEVELOPMENT/result_summary.json"
LABEL="GEN_ENC_5_OBSA_V1"
CELL_COUNT=32
FREQUENCIES=208
LAYERS=("LOCAL_FULL_CLEAN","CENTRAL_RAW_CLEAN","CENTRAL_DIFF_CLEAN","CENTRAL_DIFF_NOISY")
PAIRS=((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))


def load(path:Path)->dict[str,Any]: return json.loads(path.read_text(encoding="utf-8"))
def digest(path:Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path:Path,value:Any)->None:
    def convert(x:Any)->Any:
        if isinstance(x,np.ndarray): return x.tolist()
        if isinstance(x,np.generic): return x.item()
        if isinstance(x,dict): return {str(k):convert(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)): return [convert(v) for v in x]
        return x
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(convert(value),ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def selected_cells()->list[int]:
    return sorted(sorted(range(3675),key=lambda i:hashlib.sha256(f"{LABEL}|cell|{i}".encode()).hexdigest())[:CELL_COUNT])


def state_signature(response:np.ndarray,*,center:bool)->np.ndarray:
    x=np.asarray(response,dtype=np.complex128).reshape(4,-1)
    contrast_fraction=float(np.linalg.norm(x-np.mean(x,axis=0,keepdims=True))/np.linalg.norm(x))
    if center: x=x-np.mean(x,axis=0,keepdims=True)
    norm=float(np.linalg.norm(x))
    if norm<=0 or not math.isfinite(norm): raise RuntimeError("ZERO_OR_NONFINITE_LAYER_RESPONSE")
    x=x/norm; gram=x@x.conj().T; gram=0.5*(gram+gram.conj().T)
    distances=np.asarray([np.linalg.norm(x[left]-x[right]) for left,right in PAIRS],dtype=float)
    singular=np.linalg.svd(np.concatenate((x.real,x.imag),axis=1),compute_uv=False)
    singular=singular/singular.sum()
    return np.concatenate((gram.real.reshape(-1),gram.imag.reshape(-1),distances,singular,np.asarray([contrast_fraction])))


def separation(matrix:np.ndarray)->dict[str,Any]:
    scale=np.std(matrix,axis=0,ddof=1); usable=scale>np.finfo(float).eps
    z=(matrix[:,usable]-np.mean(matrix[:,usable],axis=0))/scale[usable]
    centroids=np.stack([np.mean(z[i*20:(i+1)*20],axis=0) for i in range(4)])
    within=np.asarray([math.sqrt(float(np.mean(np.sum((z[i*20:(i+1)*20]-centroids[i])**2,axis=1)))) for i in range(4)])
    rows=[]
    for left,right in PAIRS:
        pooled=math.sqrt(.5*(within[left]**2+within[right]**2)); rows.append({"families":[FAMILY_ORDER[left],FAMILY_ORDER[right]],"ratio":float(np.linalg.norm(centroids[left]-centroids[right])/pooled)})
    ratios=[x["ratio"] for x in rows]
    return {"usable_dimensions":int(np.sum(usable)),"minimum_between_within_ratio":min(ratios),"mean_between_within_ratio":float(np.mean(ratios)),"pairwise":rows}


def main()->int:
    if load(M2B_RESULT)["terminal_state"]!="M2B_DEVELOPMENT_NO_FAMILY_STRUCTURED_MECHANISM": raise RuntimeError("M2B_CLOSEOUT_REQUIRED")
    cells=selected_cells(); contract={"schema_version":"gen_enc_5_obsa_contract_v1","scope":"EXACT80_DEVELOPMENT_ONLY_DIAGNOSTIC_NO_PARAMETER_SEARCH_NO_CANDIDATE_RANKING","members":80,"nuisance_cell_indices_zero_based":cells,"cell_selection_rule":f"LOWEST_{CELL_COUNT}_SHA256({LABEL}|cell|index)","repeats":[0,1],"frequency_indices":[0,FREQUENCIES-1],"layers":list(LAYERS),"hypothesis_order":["H1_CENTRAL_PLENUM_PROJECTION","H2_FAMILY_GEOMETRY_OVERLAP","H3_SENSOR_NOISE_GAIN","H4_STATE_DIFFERENTIAL_PROJECTION"],"localisation_rules":{"family_geometry_overlap":"LOCAL_FULL_CLEAN_MIN_RATIO_LT_1","central_projection":"LOCAL_MIN_GE_1_AND_CENTRAL_CLEAN_LT_0P8_LOCAL","sensor_noise":"NOISY_DIFF_LT_0P8_CLEAN_DIFF","differential_projection":"CLEAN_DIFF_LT_0P8_CENTRAL_RAW"},"validation_reads":0,"final_test_read":False,"m3_authorized":False,"input_sha256":{"m2b_result":digest(M2B_RESULT),"nuisance":digest(NUISANCE)}}
    write(OUTPUT/"diagnostic_contract.json",contract)
    with NUISANCE.open("r",encoding="utf-8",newline="") as stream:
        nuisances=[{k:float(v) for k,v in row.items() if k not in {"design_row_id","u3","u5","v5","u7","v7","cell_weight"}} for row in csv.DictReader(line for line in stream if not line.startswith("#"))]
    seeds=seeds_for("development"); frequencies=frozen_frequency_grid()[:FREQUENCIES]
    identity_records=[]; matrices={layer:[] for layer in LAYERS}
    for ordinal,(_,member,_) in enumerate(exact80_members(),1):
        geometry=compile_member_geometry(member,spine_only=False); per_layer={layer:[] for layer in LAYERS}
        for cell in cells:
            for repeat in (0,1):
                kwargs=dict(member=member,nuisance=nuisances[cell],cell_index=cell,repeat_index=repeat,frequencies_hz=frequencies,state_angles_degrees=STATE_ANGLES_DEGREES,partition="development",repeat_seed_tuple=seeds,spine_only=False,frequency_start_index=0,geometry_override=geometry)
                nodes=solve_clean_node_pressure_block(**kwargs)
                noisy=solve_forward_block(include_additive_sensor_noise=True,**kwargs).central_pressure[...,None]
                local=nodes[...,:4]; central=nodes[...,4:5]
                per_layer["LOCAL_FULL_CLEAN"].append(state_signature(local,center=False))
                per_layer["CENTRAL_RAW_CLEAN"].append(state_signature(central,center=False))
                per_layer["CENTRAL_DIFF_CLEAN"].append(state_signature(central,center=True))
                per_layer["CENTRAL_DIFF_NOISY"].append(state_signature(noisy,center=True))
        layer_summary={}
        for layer in LAYERS:
            values=np.stack(per_layer[layer]); signature=np.mean(values,axis=0); matrices[layer].append(signature)
            layer_summary[layer]={"mean_contrast_fraction":float(np.mean(values[:,-1])),"signature_dimension":int(signature.size)}
        identity_records.append({"identity_id":member["member_id"],"family_id":member["family_id"],"layers":layer_summary})
        print(json.dumps({"completed":ordinal,"identity":member["member_id"]}),flush=True)
    layer_results={}
    for layer in LAYERS:
        matrix=np.stack(matrices[layer]); np.save(OUTPUT/f"{layer.lower()}_identity_signatures.npy",matrix,allow_pickle=False); layer_results[layer]=separation(matrix)
    local=layer_results["LOCAL_FULL_CLEAN"]["minimum_between_within_ratio"]; raw=layer_results["CENTRAL_RAW_CLEAN"]["minimum_between_within_ratio"]; clean=layer_results["CENTRAL_DIFF_CLEAN"]["minimum_between_within_ratio"]; noisy=layer_results["CENTRAL_DIFF_NOISY"]["minimum_between_within_ratio"]
    flags={"H1_CENTRAL_PLENUM_PROJECTION":bool(local>=1 and raw<.8*local),"H2_FAMILY_GEOMETRY_OVERLAP":bool(local<1),"H3_SENSOR_NOISE_GAIN":bool(noisy<.8*clean),"H4_STATE_DIFFERENTIAL_PROJECTION":bool(clean<.8*raw)}
    if flags["H2_FAMILY_GEOMETRY_OVERLAP"]: primary="H2_FAMILY_GEOMETRY_OVERLAP"
    elif flags["H1_CENTRAL_PLENUM_PROJECTION"]: primary="H1_CENTRAL_PLENUM_PROJECTION"
    elif flags["H3_SENSOR_NOISE_GAIN"]: primary="H3_SENSOR_NOISE_GAIN"
    elif flags["H4_STATE_DIFFERENTIAL_PROJECTION"]: primary="H4_STATE_DIFFERENTIAL_PROJECTION"
    else: primary="NO_SINGLE_DOMINANT_BOTTLENECK"
    result={"terminal_state":f"OBSA_PRIMARY_{primary}","reproduced_existing_central_collapse":bool(clean<1 and noisy<1),"layer_results":layer_results,"hypothesis_flags":flags,"primary_localisation":primary,"identity_records":identity_records,"candidate_ranking_emitted":False,"parameter_search_performed":False,"validation_reads":0,"final_test_read":False,"m3_authorized":False,"next_action":"CLOSE_GEN_ENC_WITH_GEOMETRY_FAMILY_OVERLAP_AS_PRIMARY_LIMIT" if primary=="H2_FAMILY_GEOMETRY_OVERLAP" else "REVIEW_OBSERVATION_ARCHITECTURE_BEFORE_ANY_NEW_MODEL"}
    write(OUTPUT/"result_summary.json",result); print(result["terminal_state"]); return 0


if __name__=="__main__": raise SystemExit(main())
