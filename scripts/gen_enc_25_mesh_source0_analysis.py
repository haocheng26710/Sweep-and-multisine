"""Frozen MESH-SOURCE0-A analysis."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_25_MESH_SOURCE0_A"
PREV=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_24_PRINT_COMP_A"

def read_one(path:Path):
    lines=[x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
    if len(lines)!=1:raise RuntimeError(f"BAD_EXPORT:{path.name}")
    values=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
    if len(values)!=131 or not np.isfinite(values).all():raise RuntimeError(f"BAD_VALUES:{path.name}")
    return values

def prior(size:int):
    path=PREV/f"FC_L0900_A05_size{size}_src0.txt"
    return read_one(path)

def marker(values):
    f=np.arange(820,1080.1,2.);db=20*np.log10(np.maximum(np.abs(values),1e-30));best=(-float("inf"),float("nan"))
    for center in np.arange(920,980.01,2.):
        mask=np.abs(f-center)<=201/2;ff=f[mask];yy=db[mask];x=(ff-center)/(201/2);lorentz=1/(1+(2*12*(ff-center)/center)**2)
        amp=float(np.linalg.lstsq(np.column_stack((np.ones_like(x),x,-lorentz)),yy,rcond=None)[0][-1])
        if amp>best[0]:best=(amp,center)
    return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0])}

def metrics(a,b):
    gain=np.vdot(b,a)/np.vdot(b,b)
    return {"complex_relative_l2":float(np.linalg.norm(a-b)/np.linalg.norm(a)),
            "magnitude_relative_l2":float(np.linalg.norm(np.abs(a)-np.abs(b))/np.linalg.norm(np.abs(a))),
            "gain_aligned_complex_relative_l2":float(np.linalg.norm(a-gain*b)/np.linalg.norm(a)),
            "best_fit_gain_magnitude":float(abs(gain)),"best_fit_gain_phase_deg":float(np.angle(gain,deg=True))}

def main():
    s3=prior(3);s2=prior(2);g1=read_one(ROOT/"G1_SOURCE0_src0.txt")
    convergence={"size3_to_size2":metrics(s3,s2),"size2_to_size1":metrics(s2,g1),
                 "markers":{"size3":marker(s3),"size2":marker(s2),"size1":marker(g1)}}
    convergence["pass"]=bool(convergence["size2_to_size1"]["complex_relative_l2"]<=.03
                              and abs(convergence["markers"]["size1"]["tracked_hz"]-convergence["markers"]["size2"]["tracked_hz"])<=10
                              and abs(convergence["markers"]["size1"]["fitted_depth_db"]-convergence["markers"]["size2"]["fitted_depth_db"])<=1.5)
    local=[]
    for label in ("LN2_SOURCE0","LN1_SOURCE0","LR2_SOURCE0"):
        values=read_one(ROOT/f"{label}_src0.txt");m=metrics(g1,values)
        local.append({"label":label,**m,"marker":marker(values),"matches_size1":bool(m["complex_relative_l2"]<=.03)})
    eligible=[x for x in local if x["matches_size1"]]
    selected=min(eligible,key=lambda x:(x["complex_relative_l2"],x["label"])) if eligible else None
    state="SOURCE0_GLOBAL_SIZE2_CONVERGED_LOCAL_REPAIR_FOUND" if convergence["pass"] and selected else ("SOURCE0_GLOBAL_SIZE2_CONVERGED_LOCAL_REPAIR_NOT_FOUND" if convergence["pass"] else "SOURCE0_SIZE2_NOT_CONVERGED_STOP")
    result={"state":state,"frozen_geometry":"alpha05_L9.00mm_four_corner","source":0,"convergence":convergence,
            "local_candidates_vs_global_size1":local,"selected_local_candidate":selected,
            "pass":bool(convergence["pass"]),"authorization":"Confirm all four sources and alpha endpoints on the converged grid only" if convergence["pass"] else "Stop before expanding alpha or tolerance"}
    (ROOT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    import matplotlib.pyplot as plt
    f=np.arange(820,1080.1,2.);fig,axes=plt.subplots(1,2,figsize=(9,3.6),constrained_layout=True)
    for label,v,style in (("size3",s3,"-"),("size2",s2,"--"),("size1",g1,":")):
        axes[0].plot(f,20*np.log10(np.maximum(np.abs(v),1e-30)),style,label=label)
    axes[0].set(xlabel="Frequency (Hz)",ylabel="Source-0 level (dB)",title="Global mesh sequence");axes[0].grid(alpha=.25);axes[0].legend(frameon=False)
    names=[x["label"].replace("_SOURCE0","") for x in local];errs=[100*x["complex_relative_l2"] for x in local]
    axes[1].bar(names,errs,color="#377eb8");axes[1].axhline(3,color="#d62728",ls="--",label="3% gate")
    axes[1].set(ylabel="Complex L2 vs global size1 (%)",title="Local refinement candidates");axes[1].grid(axis="y",alpha=.25);axes[1].legend(frameon=False)
    fig.savefig(ROOT/"mesh_source0_summary.png",dpi=220);plt.close(fig)
    print(json.dumps(result,indent=2))

def audit():
    specs=("G1_SOURCE0","LN2_SOURCE0","LN1_SOURCE0","LR2_SOURCE0")
    rows=[]
    for label in specs:
        values=read_one(ROOT/f"{label}_src0.txt");mph=ROOT/f"{label}.mph"
        if not mph.is_file() or mph.stat().st_size==0:raise RuntimeError(f"BAD_MPH:{mph.name}")
        rows.append({"label":label,"points":len(values),"finite":bool(np.isfinite(values).all()),"mph_bytes":mph.stat().st_size})
    logs=("global_comsol.log","local_comsol.log","comsol_stdout.log","comsol_local_stdout.log")
    for name in logs:
        if not (ROOT/name).is_file() or (ROOT/name).stat().st_size==0:raise RuntimeError(f"BAD_LOG:{name}")
    result={"state":"MESH_SOURCE0_A_ARTIFACT_AUDIT_PASS","model_count":len(rows),"spectrum_count":len(rows),
            "frequency_points_each":131,"all_finite":True,"models":rows,"logs":list(logs),"pass":True}
    (ROOT/"artifact_audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("phase",nargs="?",default="analyze",choices=("analyze","audit"));a=p.parse_args()
    {"analyze":main,"audit":audit}[a.phase]()
