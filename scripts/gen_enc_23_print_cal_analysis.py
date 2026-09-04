"""Frozen PRINT-CAL-A staged analysis."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_23_PRINT_CAL_A"
SPAN=201.;Q=12.;THRESHOLD=5.731630586148788;CONTROL=2.068928229004529

def read_case(label,size,target=950.,require_finite=True):
    f=np.arange(target-130,target+130.1,2.)
    rows=[]
    for source in range(4):
        path=ROOT/f"{label}_size{size}_src{source}.txt"
        lines=[x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
        if len(lines)!=1:raise RuntimeError(f"BAD_EXPORT:{path.name}")
        values=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
        if len(values)!=len(f) or (require_finite and not np.isfinite(values).all()):raise RuntimeError(f"BAD_VALUES:{path.name}")
        rows.append(values)
    return np.stack(rows)

def marker(values,target=950.):
    f=np.arange(target-130,target+130.1,2.)
    db=np.mean(20*np.log10(np.maximum(np.abs(values),1e-30)),axis=0);best=(-float("inf"),float("nan"))
    for center in np.arange(target-30,target+30.01,2.):
        mask=np.abs(f-center)<=SPAN/2;ff=f[mask];yy=db[mask];x=(ff-center)/(SPAN/2)
        lorentz=1/(1+(2*Q*(ff-center)/center)**2)
        amp=float(np.linalg.lstsq(np.column_stack((np.ones_like(x),x,-lorentz)),yy,rcond=None)[0][-1])
        if amp>best[0]:best=(amp,center)
    return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0]),"at_search_boundary":bool(best[1] in (target-30,target+30))}

def anchor():
    rows=[]
    for length in (8.,8.25,8.5,8.75,9.):
        label=f"L{int(round(length*100)):04d}_A05";m=marker(read_case(label,4))
        rows.append({"label":label,"physical_neck_length_mm":length,**m,"error_hz":m["tracked_hz"]-950.,
                     "visible":bool(not m["at_search_boundary"] and m["fitted_depth_db"]>=THRESHOLD and m["fitted_depth_db"]-CONTROL>=2)})
    (ROOT/"anchor_candidates.json").write_text(json.dumps(rows,indent=2)+"\n",encoding="utf-8")
    eligible=[r for r in rows if r["visible"]]
    selected=min(eligible,key=lambda r:(abs(r["error_hz"]),-r["physical_neck_length_mm"])) if eligible else None
    decision={"state":"PRINT_CONFIRM_AUTHORIZED" if selected and abs(selected["error_hz"])<=10 else "PRINT_ANCHOR_STOP",
              "selected":selected,"eligible_count":len(eligible)}
    (ROOT/"anchor_result.json").write_text(json.dumps(decision,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(rows,indent=2))

def confirm():
    cases=[]
    controls={.03:marker(read_case("TRUE3D_CONTROL_A03",4,1150),1150),.05:{"fitted_depth_db":CONTROL},.07:marker(read_case("TRUE3D_CONTROL_A07",4,750),750)}
    for alpha,target in ((.03,1150.),(.05,950.)):
        label=f"L0900_A{int(alpha*100):02d}";m=marker(read_case(label,4,target),target);control=controls[alpha]["fitted_depth_db"]
        cases.append({"alpha":alpha,"target_hz":target,"label":label,**m,"error_hz":m["tracked_hz"]-target,
                      "control_depth_db":control,"visible":bool(not m["at_search_boundary"] and m["fitted_depth_db"]>=THRESHOLD and m["fitted_depth_db"]-control>=2)})
    invalid=read_case("L0900_A07",4,750,require_finite=False)
    finite_fraction=float(np.isfinite(invalid).sum()/invalid.size)
    filler_side_mm=float(np.sqrt((8e-6*343**2/(.012*(2*np.pi*750)**2))/.0082)*1000)
    cases.append({"alpha":.07,"target_hz":750.,"label":"L0900_A07","geometry_valid":False,
                  "reason":"SINGLE_SE_CORNER_FILLER_CONTAINS_CENTRAL_READOUT_POINT","finite_fraction":finite_fraction,
                  "filler_side_mm":filler_side_mm,"tracked_hz":None,"fitted_depth_db":None,"error_hz":None,"visible":False})
    coarse=read_case("L0900_A05",4,950);fine_values=read_case("L0900_A05_FINE",3,950)
    cm,fm=marker(coarse,950),marker(fine_values,950)
    mesh={"complex_relative_l2":float(np.linalg.norm(coarse-fine_values)/np.linalg.norm(coarse)),"frequency_shift_hz":fm["tracked_hz"]-cm["tracked_hz"],
          "depth_shift_db":fm["fitted_depth_db"]-cm["fitted_depth_db"],"fine_marker":fm}
    mesh["pass"]=bool(mesh["complex_relative_l2"]<=.03 and abs(mesh["frequency_shift_hz"])<=10 and abs(mesh["depth_shift_db"])<=1.5)
    passed=(all(x["visible"] and x["error_hz"] is not None and abs(x["error_hz"])<=30 for x in cases)
            and all(x["tracked_hz"] is not None for x in cases)
            and all(cases[i]["tracked_hz"]>cases[i+1]["tracked_hz"] for i in range(2))
            and mesh["complex_relative_l2"]<=.03 and abs(mesh["frequency_shift_hz"])<=10 and abs(mesh["depth_shift_db"])<=1.5)
    result={"state":"PRINT_TOLERANCE_AUTHORIZED" if passed else "PRINT_CONFIRM_LAYOUT_INVALID_STOP","selected_length_mm":9.0,
            "controls":controls,"cases":cases,"mesh":mesh,"pass":bool(passed)}
    (ROOT/"confirm_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))

def diagnostic():
    coarse=read_case("L0900_A05",4,950);fine=read_case("L0900_A05_FINE",3,950)
    per_source=[float(np.linalg.norm(a-b)/np.linalg.norm(a)) for a,b in zip(coarse,fine)]
    volumes={alpha:8e-6*343**2/(.012*(2*np.pi*target)**2) for alpha,target in ((.03,1150.),(.05,950.),(.07,750.))}
    half=.0362053299278368/2;max_side=np.sqrt(volumes[.07]/4/.0082)
    proposal={"layout":"FOUR_SYMMETRIC_CORNER_FILLERS","alpha07_each_filler_side_mm":float(max_side*1000),
              "alpha07_inner_edge_from_center_mm":float((half-max_side)*1000),"clearance_from_2mm_central_inlet_halfwidth_mm":float((half-max_side-.001)*1000)}
    result={"state":"POST_GATE_READ_ONLY_DIAGNOSTIC","no_gate_change":True,"mesh_relative_l2_by_source":per_source,
            "four_corner_proposal":proposal}
    (ROOT/"post_gate_diagnostic.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    rows=json.loads((ROOT/"anchor_candidates.json").read_text(encoding="utf-8"))
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(9,3.7),constrained_layout=True)
    lengths=[r["physical_neck_length_mm"] for r in rows];freqs=[r["tracked_hz"] for r in rows];depths=[r["fitted_depth_db"] for r in rows]
    axes[0].plot(lengths,freqs,"o-",color="#1565c0");axes[0].axhline(950,color="0.3",ls="--",label="950 Hz target")
    axes[0].scatter([9.0],[946],s=85,facecolors="none",edgecolors="#d32f2f",linewidths=1.8,label="Selected")
    axes[0].set(xlabel="Physical neck length (mm)",ylabel="Tracked frequency (Hz)",title="Public alpha=0.05 calibration");axes[0].grid(alpha=.25);axes[0].legend(frameon=False,fontsize=8)
    axes[1].plot(lengths,depths,"o-",color="#00897b");axes[1].axhline(THRESHOLD,color="0.3",ls="--",label="Visibility threshold")
    axes[1].set(xlabel="Physical neck length (mm)",ylabel="Fitted depth (dB)",title="Frozen-reader visibility");axes[1].grid(alpha=.25);axes[1].legend(frameon=False,fontsize=8)
    fig.savefig(ROOT/"print_cal_anchor_summary.png",dpi=220);plt.close(fig)
    print(json.dumps(result,indent=2))

def audit():
    specs=[(f"L{length}_A05",4,950,True) for length in ("0800","0825","0850","0875","0900")]
    specs += [("TRUE3D_CONTROL_A03",4,1150,True),("L0900_A03",4,1150,True),("TRUE3D_CONTROL_A07",4,750,True),("L0900_A07",4,750,False),("L0900_A05_FINE",3,950,True)]
    models=[];finite_spectra=0
    for label,size,target,expected_finite in specs:
        values=read_case(label,size,target,require_finite=False);finite=bool(np.isfinite(values).all());finite_spectra+=4 if finite else 0
        if finite!=expected_finite:raise RuntimeError(f"UNEXPECTED_FINITE_STATE:{label}")
        mph=ROOT/f"{label}_size{size}.mph"
        if not mph.is_file() or mph.stat().st_size==0:raise RuntimeError(f"BAD_MPH:{mph.name}")
        models.append({"label":label,"shape":list(values.shape),"finite":finite,"mph_bytes":mph.stat().st_size})
    logs=["anchor_comsol.log","confirm_comsol.log"]
    result={"state":"PRINT_CAL_ARTIFACT_AUDIT_PASS","model_count":len(models),"complex_spectrum_count":4*len(models),
            "finite_spectrum_count":finite_spectra,"known_geometry_invalid_spectrum_count":4,"frequency_points_each":131,
            "models":models,"logs":logs,"pass":True}
    for name in logs:
        if not (ROOT/name).is_file() or (ROOT/name).stat().st_size==0:raise RuntimeError(f"BAD_LOG:{name}")
    (ROOT/"artifact_audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="models"},indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("phase",choices=("anchor","confirm","diagnostic","audit"));a=p.parse_args()
    {"anchor":anchor,"confirm":confirm,"diagnostic":diagnostic,"audit":audit}[a.phase]()
