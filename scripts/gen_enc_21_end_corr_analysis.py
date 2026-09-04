"""Analyze staged END-CORR COMSOL phases with the frozen absolute-spectrum reader."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_21_END_CORR"
F=np.arange(650.,1250.1,2.); SPAN=201.; TEMPLATE_Q=12.; THRESHOLD=5.731630586148788
CONTROL_DEPTH=2.0239628587642144

def read_case(label,size):
    rows=[]
    for source in range(4):
        path=ROOT/f"{label}_size{size}_src{source}.txt"
        lines=[x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
        if len(lines)!=1:raise RuntimeError(f"BAD_EXPORT:{path.name}")
        values=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[2:]])
        if len(values)!=301 or not np.isfinite(values).all():raise RuntimeError(f"BAD_VALUES:{path.name}")
        rows.append(values)
    return np.stack(rows)

def marker(values):
    db=np.mean(20*np.log10(np.maximum(np.abs(values),1e-30)),axis=0);best=(-1.,float("nan"))
    for center in np.arange(700.,1200.01,2.):
        mask=np.abs(F-center)<=SPAN/2;ff=F[mask];yy=db[mask];x=(ff-center)/(SPAN/2)
        lorentz=1/(1+(2*TEMPLATE_Q*(ff-center)/center)**2)
        amp=float(np.linalg.lstsq(np.column_stack((np.ones_like(x),x,-lorentz)),yy,rcond=None)[0][-1])
        if amp>best[0]:best=(amp,center)
    return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0])}

def anchor():
    rows=[]
    for length in (9.75,10.,10.25,10.5,10.75):
        label=f"R2_L{int(round(length*100)):04d}_A05";m=marker(read_case(label,3))
        rows.append({"label":label,"physical_neck_length_mm":length,**m,"error_hz":m["tracked_hz"]-950.,"visible":bool(m["fitted_depth_db"]>=THRESHOLD and m["fitted_depth_db"]-CONTROL_DEPTH>=2)})
    (ROOT/"anchor_candidates.json").write_text(json.dumps(rows,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(rows,indent=2))

def relative_l2(a,b):
    return float(np.linalg.norm(a-b)/np.linalg.norm(a))

def confirm():
    cases=[]
    for alpha,target in ((.03,1150.),(.05,950.),(.07,750.)):
        label=f"R2_L1025_A{int(round(alpha*100)):02d}"
        values=read_case(label,3);m=marker(values)
        cases.append({"alpha":alpha,"target_hz":target,"label":label,**m,
                      "error_hz":m["tracked_hz"]-target,
                      "visible":bool(m["fitted_depth_db"]>=THRESHOLD and m["fitted_depth_db"]-CONTROL_DEPTH>=2)})
    coarse=read_case("R2_L1025_A05",3)
    fine=read_case("R2_L1025_A05_FINE",2)
    cm,fm=marker(coarse),marker(fine)
    mesh={"complex_relative_l2":relative_l2(coarse,fine),
          "frequency_shift_hz":fm["tracked_hz"]-cm["tracked_hz"],
          "depth_shift_db":fm["fitted_depth_db"]-cm["fitted_depth_db"],
          "fine_marker":fm}
    passed=(all(x["visible"] and abs(x["error_hz"])<=30 for x in cases)
            and all(cases[i]["tracked_hz"]>cases[i+1]["tracked_hz"] for i in range(2))
            and mesh["complex_relative_l2"]<=.02
            and abs(mesh["frequency_shift_hz"])<=10
            and abs(mesh["depth_shift_db"])<=1)
    result={"state":"BLIND_INTERIOR_AUTHORIZED" if passed else "CONFIRM_FAIL_STOP",
            "selected_physical_neck_length_mm":10.25,"cases":cases,"mesh":mesh,"pass":bool(passed)}
    (ROOT/"confirm_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))

def blind():
    targets={.03:1150.,.04:1050.,.05:950.,.06:850.,.07:750.}
    cases=[]
    for alpha,target in targets.items():
        label=f"R2_L1025_A{int(round(alpha*100)):02d}";m=marker(read_case(label,3))
        cases.append({"alpha":alpha,"target_hz":target,"label":label,**m,
                      "error_hz":m["tracked_hz"]-target,
                      "visible":bool(m["fitted_depth_db"]>=THRESHOLD and m["fitted_depth_db"]-CONTROL_DEPTH>=2)})
    blind_cases=[x for x in cases if x["alpha"] in (.04,.06)]
    monotonic=all(cases[i]["tracked_hz"]>cases[i+1]["tracked_hz"] for i in range(4))
    passed=(all(x["visible"] and abs(x["error_hz"])<=30 for x in cases) and monotonic)
    result={"state":"END_CORR_BLIND_PASS" if passed else "END_CORR_BLIND_FAIL",
            "selected_physical_neck_length_mm":10.25,"reader":"LF201_P1_Q12_JOINT4",
            "visibility_threshold_db":THRESHOLD,"control_depth_db":CONTROL_DEPTH,
            "cases":cases,"blind_cases":blind_cases,"strictly_monotonic":bool(monotonic),
            "max_abs_error_hz":max(abs(x["error_hz"]) for x in cases),"pass":bool(passed)}
    (ROOT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    import matplotlib.pyplot as plt
    alphas=[x["alpha"] for x in cases]; targets=[x["target_hz"] for x in cases]
    tracked=[x["tracked_hz"] for x in cases]; depths=[x["fitted_depth_db"] for x in cases]
    fig,axes=plt.subplots(1,2,figsize=(9.2,3.7),constrained_layout=True)
    axes[0].plot(alphas,targets,"--",color="0.45",label="Target")
    axes[0].plot(alphas,tracked,"o-",color="#1565c0",label="COMSOL tracked")
    axes[0].scatter([.04,.06],[tracked[1],tracked[3]],s=85,facecolors="none",edgecolors="#d32f2f",linewidths=1.8,label="Blind points")
    axes[0].set(xlabel=r"Encoding parameter $\alpha$",ylabel="Frequency (Hz)",title="Frozen 10.25 mm correction")
    axes[0].grid(alpha=.25);axes[0].legend(frameon=False,fontsize=8)
    axes[1].bar([str(x) for x in alphas],depths,color=["#78909c","#d32f2f","#1565c0","#d32f2f","#78909c"])
    axes[1].axhline(THRESHOLD,color="0.25",ls="--",lw=1,label="Frozen visibility threshold")
    axes[1].set(xlabel=r"Encoding parameter $\alpha$",ylabel="Fitted resonance depth (dB)",title="Absolute-spectrum visibility")
    axes[1].grid(axis="y",alpha=.25);axes[1].legend(frameon=False,fontsize=8)
    fig.savefig(ROOT/"end_corr_blind_summary.png",dpi=220);plt.close(fig)
    print(json.dumps(result,indent=2))

def audit():
    expected=[]
    for prefix in ("","R2_"):
        expected += [(f"{prefix}L{length}_A05",3) for length in ("0975","1000","1025","1050","1075")]
    expected += [("R2_L1025_A03",3),("R2_L1025_A07",3),("R2_L1025_A05_FINE",2),
                 ("R2_L1025_A04",3),("R2_L1025_A06",3)]
    checked=[]
    for label,size in expected:
        values=read_case(label,size)
        mph=ROOT/f"{label}_size{size}.mph"
        if not mph.is_file() or mph.stat().st_size==0:raise RuntimeError(f"BAD_MPH:{mph.name}")
        checked.append({"label":label,"mesh_size":size,"shape":list(values.shape),"finite":bool(np.isfinite(values).all()),"mph_bytes":mph.stat().st_size})
    logs=["anchor_comsol.log","anchor_r2_comsol.log","confirm_comsol.log","blind_comsol.log"]
    for name in logs:
        if not (ROOT/name).is_file() or (ROOT/name).stat().st_size==0:raise RuntimeError(f"BAD_LOG:{name}")
    result={"state":"END_CORR_ARTIFACT_AUDIT_PASS","model_count":len(checked),
            "complex_spectrum_count":4*len(checked),"frequency_points_each":301,
            "logs":logs,"models":checked,"pass":True}
    (ROOT/"artifact_audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="models"},indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("phase",choices=("anchor","confirm","blind","audit"));a=p.parse_args()
    {"anchor":anchor,"confirm":confirm,"blind":blind,"audit":audit}[a.phase]()
