"""Frozen A03-S2-PHASE-MESH-A analysis."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_27_A03_S2_PHASE_MESH_A"
PREV=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_26_PRINT_CONV_B"
F=np.arange(1020,1280.1,2.)

def read(path:Path):
    lines=[x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
    if len(lines)!=1:raise RuntimeError(f"BAD_EXPORT:{path.name}")
    values=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
    if len(values)!=len(F) or not np.isfinite(values).all():raise RuntimeError(f"BAD_VALUES:{path.name}")
    return values

def metrics(a,b):
    gain=np.vdot(b,a)/np.vdot(b,b)
    return {"complex_relative_l2":float(np.linalg.norm(a-b)/np.linalg.norm(a)),
            "magnitude_relative_l2":float(np.linalg.norm(np.abs(a)-np.abs(b))/np.linalg.norm(np.abs(a))),
            "gain_aligned_complex_relative_l2":float(np.linalg.norm(a-gain*b)/np.linalg.norm(a)),
            "best_fit_gain_magnitude":float(abs(gain)),"best_fit_gain_phase_deg":float(np.angle(gain,deg=True))}

def marker(v):
    db=20*np.log10(np.maximum(np.abs(v),1e-30));best=(-float("inf"),float("nan"))
    for center in np.arange(1120,1180.01,2.):
        mask=np.abs(F-center)<=201/2;ff=F[mask];yy=db[mask];x=(ff-center)/(201/2);lorentz=1/(1+(2*12*(ff-center)/center)**2)
        amp=float(np.linalg.lstsq(np.column_stack((np.ones_like(x),x,-lorentz)),yy,rcond=None)[0][-1])
        if amp>best[0]:best=(amp,center)
    return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0])}

def analyze():
    center={m:read(ROOT/f"{m}_center_src2.txt") for m in ("G2","G1","F32","F26")};ref={m:read(ROOT/f"{m}_westref_src2.txt") for m in center}
    seq=[]
    for a,b in (("G2","G1"),("G1","F32"),("F32","F26")):
        ma,mb=marker(center[a]),marker(center[b]);seq.append({"coarse":a,"fine":b,"raw":metrics(center[a],center[b]),
          "reference_normalized":metrics(center[a]/ref[a],center[b]/ref[b]),"coarse_marker":ma,"fine_marker":mb,
          "frequency_shift_hz":mb["tracked_hz"]-ma["tracked_hz"],"depth_shift_db":mb["fitted_depth_db"]-ma["fitted_depth_db"]})
    final=seq[-1];passed=bool(final["raw"]["complex_relative_l2"]<=.03 and abs(final["frequency_shift_hz"])<=10 and abs(final["depth_shift_db"])<=1.5)
    prior=read(PREV/"FC_L0900_A03_size1_src2.txt");det=float(np.linalg.norm(prior-center["G1"])/np.linalg.norm(prior))
    result={"state":"A03_S2_PHASE_MESH_PASS" if passed else "A03_S2_PHASE_MESH_STOP","alpha":.03,"source":2,
            "automatic_size1_hmax_mm":4.16,"custom_hmax_mm":{"F32":3.2,"F26":2.6},"sequence":seq,
            "size1_rerun_relative_l2":det,"accepted_mesh":"F32" if passed else None,"pass":passed,
            "authorization":"Close PRINT-CONV-B convergence and open blind alpha04/06" if passed else "Stop before blind points"}
    (ROOT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(9,3.6),constrained_layout=True)
    for m,style in (("G2","-"),("G1","--"),("F32","-."),("F26",":")):axes[0].plot(F,20*np.log10(np.maximum(np.abs(center[m]),1e-30)),style,label=m)
    axes[0].set(xlabel="Frequency (Hz)",ylabel="Source-2 level (dB)",title="Custom global refinement");axes[0].grid(alpha=.25);axes[0].legend(frameon=False)
    names=[f"{x['coarse']}→{x['fine']}" for x in seq];raw=[100*x["raw"]["complex_relative_l2"] for x in seq];norm=[100*x["reference_normalized"]["complex_relative_l2"] for x in seq];xx=np.arange(3)
    axes[1].bar(xx-.18,raw,.36,label="Raw complex");axes[1].bar(xx+.18,norm,.36,label="Reference-normalized");axes[1].axhline(3,color="#d62728",ls="--",label="3% gate");axes[1].set_xticks(xx,names);axes[1].set(ylabel="Relative L2 (%)",title="Phase-reference diagnostic");axes[1].grid(axis="y",alpha=.25);axes[1].legend(frameon=False)
    fig.savefig(ROOT/"a03_s2_phase_mesh_summary.png",dpi=220);plt.close(fig);print(json.dumps(result,indent=2))

def audit():
    models=[]
    for m in ("G2","G1","F32","F26"):
        read(ROOT/f"{m}_center_src2.txt");read(ROOT/f"{m}_westref_src2.txt");mph=ROOT/f"{m}_src2.mph"
        if not mph.is_file() or mph.stat().st_size==0:raise RuntimeError(f"BAD_MPH:{mph.name}")
        models.append({"label":m,"spectra":2,"mph_bytes":mph.stat().st_size})
    for name in ("probe_stdout.log","comsol_stdout.log","probe_comsol.log","solve_comsol.log"):
        if not (ROOT/name).is_file() or (ROOT/name).stat().st_size==0:raise RuntimeError(f"BAD_LOG:{name}")
    result={"state":"A03_S2_PHASE_MESH_ARTIFACT_AUDIT_PASS","model_count":4,"spectrum_count":8,"frequency_points_each":131,"all_finite":True,"models":models,"pass":True}
    (ROOT/"artifact_audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("phase",nargs="?",default="analyze",choices=("analyze","audit"));a=p.parse_args();{"analyze":analyze,"audit":audit}[a.phase]()
