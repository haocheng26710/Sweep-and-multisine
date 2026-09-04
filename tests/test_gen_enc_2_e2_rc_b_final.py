from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts import gen_enc_2_e2_merge_reconstruct_rc_b_final as merge


def test_endpoint_primary_secondary_and_uncertainty_match_direct() -> None:
    values=np.zeros((3675,2,6),dtype=np.float64)
    sigma3=np.linspace(0.8,1.3,7350)
    flat=values.reshape((-1,6)); flat[:,0]=1.5; flat[:,1]=1.2; flat[:,2]=sigma3; flat[:,3:]=flat[:,:3]>1.0
    endpoint=merge.endpoint_output(values)
    ordered=np.sort(sigma3,kind="stable"); direct=float(ordered[int(np.ceil(0.05*7350)-1)])
    assert endpoint["primary_band"]["E_primary"]==direct
    assert endpoint["secondary_band"]=={"frequency_count":256,"reported_separately":True,"replaces_primary":False}
    keys=np.asarray([(cell,repeat,0,0) for cell in range(3675) for repeat in range(2)],dtype=np.uint64).reshape((3675,2,4))
    resampling=merge.resampling_output(values.copy(),values,keys)
    direct_hash=hashlib.sha256(values.reshape((-1,6)).tobytes(order="C")+keys.reshape((-1,4)).tobytes(order="C")).hexdigest()
    assert resampling["unit_payload_sha256"]==direct_hash
    assert resampling["uncertainty"]["median"]==merge.inverse_empirical(sigma3,0.5)
    assert resampling["bootstrap"]["status"]=="SEALED_FINEST_UNIT_INPUT"
    assert resampling["permutation"]["status"]=="SEALED_FINEST_UNIT_INPUT"
    components=np.zeros((3675,2,2,4,4),dtype=np.float64); components[:,:,0]=np.eye(4); components[:,:,1]=2*np.eye(4)
    shared=merge.shared_differential_output(components)
    assert shared["shared_trace_mean"]==4.0 and shared["differential_trace_mean"]==8.0
    terminal=np.empty((3675,2,12),dtype=np.float64)
    terminal[:,:,:6]=values
    for chunk in range(147):
        start=chunk*25; terminal[start:start+25,:,6:]=np.min(values[start:start+25],axis=(0,1))
    terminal_output=merge.terminal_inputs_output(terminal,values)
    assert terminal_output["candidate_family_global_reduction_inputs_validated"] is True


def test_matched_cost_and_candidate_all_terminal_paths() -> None:
    eligible=np.broadcast_to(np.asarray([3.014899604922098e-5,12,0.002,0.002]),(3675,2,4)).copy()
    matched=merge.matched_output(eligible); assert matched["eligible"] is True
    bad=eligible.copy(); bad[:,:,1]=17
    ineligible=merge.matched_output(bad); assert ineligible["eligible"] is False
    positive={"primary_band":{"stable_rank_eligible":True}}; negative={"primary_band":{"stable_rank_eligible":False}}
    available={"status":"AVAILABLE"}; unavailable={"status":"UNAVAILABLE"}; bridge_pass={"status":"PASS"}; bridge_fail={"status":"BRIDGE_FAIL"}; bridge_dev={"status":"NOT_EVALUATED_DEVELOPMENT"}
    assert merge.classify_candidate(endpoint=positive,matched=matched,throughput=available,bridge=bridge_pass,partition="single_use_validation",technical_ok=True)=="PASS"
    assert merge.classify_candidate(endpoint=negative,matched=matched,throughput=available,bridge=bridge_pass,partition="single_use_validation",technical_ok=True)=="NEGATIVE"
    assert merge.classify_candidate(endpoint=positive,matched=ineligible,throughput=available,bridge=bridge_pass,partition="single_use_validation",technical_ok=True)=="COST_INELIGIBLE"
    assert merge.classify_candidate(endpoint=positive,matched=matched,throughput=unavailable,bridge=bridge_pass,partition="single_use_validation",technical_ok=True)=="UNAVAILABLE"
    assert merge.classify_candidate(endpoint=positive,matched=matched,throughput=available,bridge=bridge_fail,partition="single_use_validation",technical_ok=True)=="BRIDGE_FAIL"
    assert merge.classify_candidate(endpoint=positive,matched=matched,throughput=available,bridge=bridge_dev,partition="development",technical_ok=True)=="PASS"
    assert merge.classify_candidate(endpoint=positive,matched=matched,throughput=available,bridge=bridge_pass,partition="single_use_validation",technical_ok=False)=="TECHNICAL_FAILURE"


def test_throughput_available_and_unavailable_match_direct() -> None:
    numerator=np.full((4,50,2,256),4.0); denominator=np.full_like(numerator,2.0)
    chunk_bits=[np.packbits(np.ones(4*25*2*256,dtype=np.uint8),bitorder="little") for _ in range(2)]
    output=merge.throughput_output(numerator,denominator,chunk_bits)
    assert output["status"]=="AVAILABLE" and output["frequency_curve_256"]==[2.0]*256
    denominator[0,0,0,0]=0.0; chunk_bits[0][0]&=np.uint8(254)
    assert merge.throughput_output(numerator,denominator,chunk_bits)["status"]=="UNAVAILABLE"


def test_bridge_and_heldout_pass_and_fail_are_direct() -> None:
    bridge=np.zeros((1,1,24,6),dtype=np.float64)
    bridge[0,0,:,0]=np.deg2rad(np.arange(0,360,15)); bridge[0,0,:,1]=1; bridge[0,0,:,2]=2; bridge[0,0,:,3]=1; bridge[0,0,[3,9,15,21],4]=1; bridge[0,0,:,5]=1
    bridge=np.broadcast_to(bridge,(3675,2,24,6)).copy()
    held=bridge[:,:,[3,9,15,21]][:,:,:,[1,2,3,5]].copy()
    passed,held_pass=merge.bridge_outputs(bridge,held)
    assert passed["status"]=="PASS" and held_pass["status"]=="PASS"
    bridge[:,:,0,1]=-1
    failed,_=merge.bridge_outputs(bridge,held)
    assert failed["status"]=="BRIDGE_FAIL"


def test_dedup_moved_path_resolves_and_verifies_receipt_hash(tmp_path: Path) -> None:
    original=tmp_path/"moved.npy"; canonical=tmp_path/"canonical.npy"; np.save(canonical,np.asarray([2.0]))
    receipt=tmp_path/"receipt.json"; receipt.write_text("{}\n",encoding="utf-8")
    payload_hash=merge.sha256_file(canonical); receipt_hash=merge.sha256_file(receipt)
    manifest={"partition":"development","chunk_id":"chunk_000","_manifest_path":(tmp_path/"manifest.json").as_posix()}
    entry={"role":"THROUGHPUT_REFERENCE_DENOMINATOR_256","path":original.as_posix(),"sha256":payload_hash,"shape":[1],"dtype":"float64"}
    key=merge.dedup_key("development","chunk_000",entry["role"])
    index={"entries":{key:{"source_sha256":payload_hash,"canonical_payload_path":canonical.as_posix(),"canonical_payload_sha256":payload_hash,"origins":[{"original_manifest_path":manifest["_manifest_path"],"original_role_path":original.as_posix(),"original_role_sha256":payload_hash,"receipt_path":receipt.as_posix(),"receipt_sha256":receipt_hash}]}}}
    assert merge.resolve_entry(entry,manifest,index)==canonical
    receipt.write_text("changed\n",encoding="utf-8")
    with pytest.raises(merge.FinalReconstructionError,match="RECEIPT_HASH"):
        merge.resolve_entry(entry,manifest,index)


def test_missing_any_required_role_fails_closed_before_payload_read(tmp_path: Path) -> None:
    dedup=tmp_path/"dedup.json"; dedup.write_text(json.dumps({"schema_version":"gen_enc_2_e2_reference_dedup_index_rc_b_final_v1","partition":"development","entries":{}}),encoding="utf-8")
    roles=list(merge.DEVELOPMENT_METRIC_ROLES[:-1])
    entries=[{"role":role} for role in roles]
    for chunk in range(147):
        value={"partition":"development","canonical_merge_position":chunk,"cell_start":chunk*25,"cell_end_exclusive":chunk*25+25,"role_set_complete":True,"entries":entries}
        (tmp_path/f"chunk_{chunk:03d}.full_role_manifest.json").write_text(json.dumps(value),encoding="utf-8")
    with pytest.raises(merge.FinalReconstructionError,match="EXACT_ORDERED_ROLE_SET"):
        merge.load_all_roles(tmp_path,"development",dedup)


def test_family_worst_member_mixed_global_and_incomplete_block(tmp_path: Path) -> None:
    families=[("HAND_DESIGNED","HAND"),("NEAR_INDEPENDENT","NEAR"),("FIXED_SEED_RANDOM_DISORDERED","RANDOM"),("PHYSICS_METAMATERIAL_INSPIRED","PHYSICS")]
    paths=[]
    for family,prefix in families:
        for ordinal in range(1,21):
            status="NEGATIVE" if family=="NEAR_INDEPENDENT" and ordinal==20 else "PASS"
            value={"identity_id":f"{prefix}_{ordinal:02d}","family_id":family,"scientific_status":status,"primary":{"E_primary":1.2 if status=="PASS" else 0.9}}
            path=tmp_path/f"{prefix}_{ordinal:02d}.json"; path.write_text(json.dumps(value)+"\n",encoding="utf-8"); paths.append(path)
    result=merge.aggregate_families(paths,tmp_path/"global.json",partition="single_use_validation")
    assert result["families"]["NEAR_INDEPENDENT"]["status"]=="NEGATIVE"
    assert result["global_status"]=="MIXED" and len(result["ranking"])==4
    development=merge.aggregate_families(paths,tmp_path/"development.json",partition="development")
    assert development["global_status"]=="NOT_EVALUATED_DEVELOPMENT" and development["ranking"]==[]
    with pytest.raises(merge.FinalReconstructionError,match="EXACT80"):
        merge.aggregate_families(paths[:-1],tmp_path/"bad.json",partition="single_use_validation")
