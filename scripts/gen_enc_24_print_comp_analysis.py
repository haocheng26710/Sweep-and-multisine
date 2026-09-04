"""Frozen staged analysis for PRINT-COMP-A."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_24_PRINT_COMP_A"
SPAN=201.;Q=12.;THRESHOLD=5.731630586148788;BASE_CONTROL=2.068928229004529

def static():
    text=(ROOT/"static_comsol.log").read_text(encoding="utf-8",errors="replace")
    found=re.findall(r"AUDIT STATIC (FC_A0[3-7]) target=(\d+) side_mm=([\d.]+) clearance_mm=([\d.]+) domains=1,1,1 ports=1,1,1,1",text)
    rows=[{"label":a,"target_hz":float(t),"each_filler_side_mm":float(s),"entrance_clearance_mm":float(c)} for a,t,s,c in found]
    passed=len(rows)==5 and all(r["entrance_clearance_mm"]>=2 for r in rows)
    result={"state":"FOUR_CORNER_COMSOL_STATIC_PASS" if passed else "FOUR_CORNER_COMSOL_STATIC_FAIL","rows":rows,"pass":passed}
    (ROOT/"static_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))

def read_case(label,size,target=950.):
    f=np.arange(target-130,target+130.1,2.);rows=[]
    for source in range(4):
        path=ROOT/f"{label}_size{size}_src{source}.txt";lines=[x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
        if len(lines)!=1:raise RuntimeError(f"BAD_EXPORT:{path.name}")
        values=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
        if len(values)!=len(f) or not np.isfinite(values).all():raise RuntimeError(f"BAD_VALUES:{path.name}")
        rows.append(values)
    return np.stack(rows)

def marker(values,target=950.):
    f=np.arange(target-130,target+130.1,2.);db=np.mean(20*np.log10(np.maximum(np.abs(values),1e-30)),axis=0);best=(-float("inf"),float("nan"))
    for center in np.arange(target-30,target+30.01,2.):
        mask=np.abs(f-center)<=SPAN/2;ff=f[mask];yy=db[mask];x=(ff-center)/(SPAN/2);lorentz=1/(1+(2*Q*(ff-center)/center)**2)
        amp=float(np.linalg.lstsq(np.column_stack((np.ones_like(x),x,-lorentz)),yy,rcond=None)[0][-1])
        if amp>best[0]:best=(amp,center)
    return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0]),"at_search_boundary":bool(best[1] in (target-30,target+30))}

def anchor():
    control=marker(read_case("FC_CONTROL_A05",3));control_depth=max(BASE_CONTROL,control["fitted_depth_db"]);rows=[]
    for length in (8.5,8.75,9.,9.25,9.5):
        label=f"FC_L{int(round(length*100)):04d}_A05";m=marker(read_case(label,3))
        rows.append({"label":label,"physical_neck_length_mm":length,**m,"error_hz":m["tracked_hz"]-950.,
                     "visible":bool(not m["at_search_boundary"] and m["fitted_depth_db"]>=THRESHOLD and m["fitted_depth_db"]-control_depth>=2)})
    eligible=[r for r in rows if r["visible"]];selected=min(eligible,key=lambda r:(abs(r["error_hz"]),-r["physical_neck_length_mm"])) if eligible else None
    result={"state":"FOUR_CORNER_CONFIRM_AUTHORIZED" if selected and abs(selected["error_hz"])<=10 else "FOUR_CORNER_ANCHOR_STOP",
            "base_control_depth_db":BASE_CONTROL,"filler_control":control,"effective_control_depth_db":control_depth,
            "candidates":rows,"selected":selected,"pass":bool(selected and abs(selected["error_hz"])<=10)}
    (ROOT/"anchor_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))

def confirm():
    targets={.03:1150.,.05:950.,.07:750.}
    controls={
        .03:marker(read_case("FC_CONTROL_A03",3,targets[.03]),targets[.03]),
        .05:marker(read_case("FC_CONTROL_A05",3,targets[.05]),targets[.05]),
        .07:marker(read_case("FC_CONTROL_A07",3,targets[.07]),targets[.07]),
    }
    cases=[]
    for alpha in (.03,.05,.07):
        target=targets[alpha];label=f"FC_L0900_A{int(alpha*100):02d}"
        m=marker(read_case(label,3,target),target);control=controls[alpha]["fitted_depth_db"]
        cases.append({"alpha":alpha,"target_hz":target,"label":label,**m,
                      "error_hz":m["tracked_hz"]-target,"control_depth_db":control,
                      "depth_margin_db":m["fitted_depth_db"]-control,
                      "visible":bool(not m["at_search_boundary"] and m["fitted_depth_db"]>=THRESHOLD and m["fitted_depth_db"]-control>=2)})
    coarse=read_case("FC_L0900_A05",3,950);fine=read_case("FC_L0900_A05",2,950)
    cm,fm=marker(coarse,950),marker(fine,950)
    mesh={"complex_relative_l2":float(np.linalg.norm(coarse-fine)/np.linalg.norm(coarse)),
          "frequency_shift_hz":fm["tracked_hz"]-cm["tracked_hz"],
          "depth_shift_db":fm["fitted_depth_db"]-cm["fitted_depth_db"],"size3_marker":cm,"size2_marker":fm}
    mesh["pass"]=bool(mesh["complex_relative_l2"]<=.03 and abs(mesh["frequency_shift_hz"])<=10 and abs(mesh["depth_shift_db"])<=1.5)
    monotonic=all(cases[i]["tracked_hz"]>cases[i+1]["tracked_hz"] for i in range(2))
    passed=all(c["visible"] and abs(c["error_hz"])<=30 for c in cases) and monotonic and mesh["pass"]
    result={"state":"PRINT_COMP_A_PASS" if passed else "PRINT_COMP_A_CONFIRM_STOP","selected_length_mm":9.0,
            "controls":{f"alpha{int(k*100):02d}":v for k,v in controls.items()},"cases":cases,
            "strictly_monotonic":bool(monotonic),"mesh":mesh,"pass":bool(passed)}
    (ROOT/"confirm_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))

def diagnostic():
    coarse=read_case("FC_L0900_A05",3,950);fine=read_case("FC_L0900_A05",2,950)
    rows=[]
    for source,(a,b) in enumerate(zip(coarse,fine)):
        gain=np.vdot(b,a)/np.vdot(b,b)
        rows.append({"source":source,
                     "raw_complex_relative_l2":float(np.linalg.norm(a-b)/np.linalg.norm(a)),
                     "gain_aligned_complex_relative_l2":float(np.linalg.norm(a-gain*b)/np.linalg.norm(a)),
                     "magnitude_relative_l2":float(np.linalg.norm(np.abs(a)-np.abs(b))/np.linalg.norm(np.abs(a))),
                     "best_fit_gain_magnitude":float(abs(gain)),"best_fit_gain_phase_deg":float(np.angle(gain,deg=True))})
    result={"state":"POST_GATE_READ_ONLY_MESH_DECOMPOSITION","no_gate_change":True,"per_source":rows,
            "interpretation":"Frozen full-complex convergence fails although the tracked resonance marker is stable; aligned and magnitude-only differences are diagnostic only."}
    (ROOT/"post_gate_mesh_diagnostic.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    import matplotlib.pyplot as plt
    f=np.arange(820,1080.1,2.);db3=np.mean(20*np.log10(np.maximum(np.abs(coarse),1e-30)),axis=0);db2=np.mean(20*np.log10(np.maximum(np.abs(fine),1e-30)),axis=0)
    fig,axes=plt.subplots(1,2,figsize=(9,3.6),constrained_layout=True)
    axes[0].plot(f,db3,label="size3");axes[0].plot(f,db2,"--",label="size2");axes[0].axvline(950,color="0.4",ls=":")
    axes[0].set(xlabel="Frequency (Hz)",ylabel="Mean level (dB)",title="alpha=0.05 mesh comparison");axes[0].grid(alpha=.25);axes[0].legend(frameon=False)
    alphas=[c["alpha"] for c in json.loads((ROOT/"confirm_result.json").read_text(encoding="utf-8"))["cases"]]
    tracked=[c["tracked_hz"] for c in json.loads((ROOT/"confirm_result.json").read_text(encoding="utf-8"))["cases"]]
    targets=[1150,950,750]
    axes[1].plot(alphas,tracked,"o-",label="Full-wave");axes[1].plot(alphas,targets,"s--",label="Target")
    axes[1].set(xlabel="alpha",ylabel="Frequency (Hz)",title="Four-corner compensated mapping");axes[1].grid(alpha=.25);axes[1].legend(frameon=False)
    fig.savefig(ROOT/"print_comp_a_summary.png",dpi=220);plt.close(fig)
    print(json.dumps(result,indent=2))

def audit():
    specs=[("FC_CONTROL_A05",3,950),("FC_L0850_A05",3,950),("FC_L0875_A05",3,950),
           ("FC_L0900_A05",3,950),("FC_L0925_A05",3,950),("FC_L0950_A05",3,950),
           ("FC_L0900_A05",2,950),("FC_CONTROL_A03",3,1150),("FC_L0900_A03",3,1150),
           ("FC_CONTROL_A07",3,750),("FC_L0900_A07",3,750)]
    models=[]
    for label,size,target in specs:
        values=read_case(label,size,target);mph=ROOT/f"{label}_size{size}.mph"
        if not mph.is_file() or mph.stat().st_size==0:raise RuntimeError(f"BAD_MPH:{mph.name}")
        models.append({"label":label,"mesh_size":size,"shape":list(values.shape),"finite":bool(np.isfinite(values).all()),"mph_bytes":mph.stat().st_size})
    logs=["static_comsol.log","anchor_comsol.log","confirm_comsol.log"]
    for name in logs:
        if not (ROOT/name).is_file() or (ROOT/name).stat().st_size==0:raise RuntimeError(f"BAD_LOG:{name}")
    result={"state":"PRINT_COMP_A_ARTIFACT_AUDIT_PASS","model_count":len(models),"complex_spectrum_count":4*len(models),
            "frequency_points_each":131,"all_finite":True,"models":models,"logs":logs,"pass":True}
    (ROOT/"artifact_audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps({k:v for k,v in result.items() if k!="models"},indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("phase",choices=("static","anchor","confirm","diagnostic","audit"));a=p.parse_args();{"static":static,"anchor":anchor,"confirm":confirm,"diagnostic":diagnostic,"audit":audit}[a.phase]()
