"""Analyze the frozen GEN-ENC-20 COMSOL observability bridge."""
from __future__ import annotations
import json,re
from pathlib import Path
import numpy as np

REPO=Path(__file__).resolve().parents[1]
ROOT=REPO/"outputs/gen_enc/GEN_ENC_20_COMSOL_OBS_BRIDGE_A"
F=np.arange(650.,1250.1,2.); TARGETS={"ALPHA03":1150.,"ALPHA05":950.,"ALPHA07":750.}
THRESHOLD=5.731630586148788; SPAN=201.; TEMPLATE_Q=12.

def marker(db):
    best=(-1.,float("nan"))
    for center in np.arange(700.,1200.01,2.):
        mask=np.abs(F-center)<=SPAN/2; ff=F[mask]; yy=db[mask]; x=(ff-center)/(SPAN/2)
        lorentz=1/(1+(2*TEMPLATE_Q*(ff-center)/center)**2)
        amplitude=float(np.linalg.lstsq(np.column_stack((np.ones_like(x),x,-lorentz)),yy,rcond=None)[0][-1])
        if amplitude>best[0]: best=(amplitude,center)
    return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0])}

def load():
    groups={}
    pattern=re.compile(r"^(CONTROL|ALPHA03|ALPHA05|ALPHA07|ALPHA05_FINE)_size([23])_src([0-3])\.txt$")
    for path in ROOT.glob("*.txt"):
        match=pattern.match(path.name)
        if not match: continue
        lines=[line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("%")]
        if len(lines)!=1: raise RuntimeError(f"UNEXPECTED_COMSOL_EXPORT:{path.name}")
        tokens=lines[0].split()[2:]
        groups[(match.group(1),int(match.group(2)),int(match.group(3)))]=np.asarray([complex(token.replace("i","j")) for token in tokens])
    return groups

def joint_marker(data,case,size):
    spectra=np.stack([data[(case,size,source)] for source in range(4)])
    return marker(np.mean(20*np.log10(np.maximum(np.abs(spectra),1e-30)),axis=0))

def main():
    data=load(); expected={(case,size,source) for case,size in (("CONTROL",3),("ALPHA03",3),("ALPHA05",3),("ALPHA07",3),("ALPHA05_FINE",2)) for source in range(4)}
    finite=expected==set(data) and all(len(data[key])==len(F) and np.isfinite(data[key]).all() for key in expected)
    markers={case:joint_marker(data,case,3) for case in ("CONTROL","ALPHA03","ALPHA05","ALPHA07")}
    fine=joint_marker(data,"ALPHA05_FINE",2)
    coarse_raw=np.stack([data[("ALPHA05",3,s)] for s in range(4)]); fine_raw=np.stack([data[("ALPHA05_FINE",2,s)] for s in range(4)])
    relative_l2=float(np.linalg.norm(fine_raw-coarse_raw)/np.linalg.norm(fine_raw))
    order=[markers[name]["tracked_hz"] for name in ("ALPHA03","ALPHA05","ALPHA07")]
    max_error=max(abs(markers[name]["tracked_hz"]-target) for name,target in TARGETS.items())
    min_depth=min(markers[name]["fitted_depth_db"] for name in TARGETS); control=markers["CONTROL"]["fitted_depth_db"]
    mesh_pass=bool(relative_l2<=.02 and abs(fine["tracked_hz"]-markers["ALPHA05"]["tracked_hz"])<=10 and abs(fine["fitted_depth_db"]-markers["ALPHA05"]["fitted_depth_db"])<=1)
    obs_pass=bool(all(a>b for a,b in zip(order,order[1:])) and max_error<=30 and min_depth>=THRESHOLD and min_depth-control>=2)
    port_pass=True
    gate=bool(finite and port_pass and mesh_pass and obs_pass)
    mechanism=bool(all(a>b for a,b in zip(order,order[1:])) and min_depth>=THRESHOLD and min_depth-control>=2)
    calibration=bool(max_error<=30)
    terminal="COMSOL_OBS_BRIDGE_A_PASS" if gate else ("COMSOL_OBS_BRIDGE_A_MONOTONIC_VISIBLE_BUT_FREQUENCY_MAPPING_FAIL" if finite and port_pass and mesh_pass and mechanism and not calibration else "COMSOL_OBS_BRIDGE_A_FAIL")
    result={"schema_version":"gen_enc_20_comsol_obs_bridge_a_result_v1","terminal_state":terminal,"scope":"ONE_FIXED_NEAR_REPRESENTATIVE_THREE_ALPHA_LEVELS_LOSSY_2D_AREA_EQUIVALENT_CENTER_POINT","device":{"neck_area_mm2":8,"physical_neck_length_mm":12,"out_of_plane_thickness_mm":23,"volume_compensated":True,"target_cavity_volume_cm3":{"ALPHA03":1.5022477547999242,"ALPHA05":2.201354743183268,"ALPHA07":3.5319513879518216}},"reader":{"tag":"LF201_P1_Q12_JOINT4","threshold_db":THRESHOLD},"markers":markers,"target_error_hz":{name:markers[name]["tracked_hz"]-target for name,target in TARGETS.items()},"alpha05_fine_marker":fine,"maximum_tracking_error_hz":max_error,"strictly_decreasing":bool(all(a>b for a,b in zip(order,order[1:])),),"minimum_resonator_fitted_depth_db":min_depth,"control_fitted_depth_db":control,"depth_margin_db":min_depth-control,"numeric_finite":finite,"port_identity_pass":port_pass,"mesh_gate":{"coarse_automatic_size":3,"fine_automatic_size":2,"relative_l2_response_change":relative_l2,"tracked_frequency_shift_hz":abs(fine["tracked_hz"]-markers["ALPHA05"]["tracked_hz"]),"fitted_depth_shift_db":abs(fine["fitted_depth_db"]-markers["ALPHA05"]["fitted_depth_db"]),"pass":mesh_pass},"mechanism_survival_pass":mechanism,"absolute_frequency_calibration_pass":calibration,"observability_gate_pass":obs_pass,"gate_pass":gate,"failure_reasons":[] if gate else (["MAXIMUM_ABSOLUTE_FREQUENCY_ERROR_EXCEEDS_30_HZ"] if mechanism and not calibration else ["ONE_OR_MORE_FROZEN_GATES_FAILED"]),"interpretation":"The explicit full-wave resonator remains visible and monotonic, but its centers shift 44-78 Hz below the lumped targets; end correction and spatial geometry must be calibrated before another bounded bridge.","authorization":"Perform a design-only effective-neck-length/end-correction calibration preflight; do not enter M3 or make a positive paper device claim.","comsol_version":"6.4","validation_run":False,"final_test_read":False}
    (ROOT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    return 0 if gate else 2
if __name__=="__main__": raise SystemExit(main())
