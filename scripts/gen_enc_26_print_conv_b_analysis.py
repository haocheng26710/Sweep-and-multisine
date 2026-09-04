"""Frozen initial analysis for PRINT-CONV-B."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_26_PRINT_CONV_B"
PREV=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_24_PRINT_COMP_A"
THRESHOLD=5.731630586148788

def read_case(root:Path,label:str,size:int,target:float):
    f=np.arange(target-130,target+130.1,2.);rows=[]
    for source in range(4):
        path=root/f"{label}_size{size}_src{source}.txt";lines=[x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
        if len(lines)!=1:raise RuntimeError(f"BAD_EXPORT:{path.name}")
        values=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
        if len(values)!=len(f) or not np.isfinite(values).all():raise RuntimeError(f"BAD_VALUES:{path.name}")
        rows.append(values)
    return np.stack(rows)

def marker(values,target):
    f=np.arange(target-130,target+130.1,2.);db=np.mean(20*np.log10(np.maximum(np.abs(values),1e-30)),axis=0);best=(-float("inf"),float("nan"))
    for center in np.arange(target-30,target+30.01,2.):
        mask=np.abs(f-center)<=201/2;ff=f[mask];yy=db[mask];x=(ff-center)/(201/2);lorentz=1/(1+(2*12*(ff-center)/center)**2)
        amp=float(np.linalg.lstsq(np.column_stack((np.ones_like(x),x,-lorentz)),yy,rcond=None)[0][-1])
        if amp>best[0]:best=(amp,center)
    return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0]),"at_search_boundary":bool(best[1] in (target-30,target+30))}

def rel(a,b):return float(np.linalg.norm(a-b)/np.linalg.norm(a))

def metrics(a,b):
    gain=np.vdot(b,a)/np.vdot(b,b)
    return {"complex_relative_l2":rel(a,b),"magnitude_relative_l2":float(np.linalg.norm(np.abs(a)-np.abs(b))/np.linalg.norm(np.abs(a))),
            "gain_aligned_complex_relative_l2":float(np.linalg.norm(a-gain*b)/np.linalg.norm(a)),
            "best_fit_gain_magnitude":float(abs(gain)),"best_fit_gain_phase_deg":float(np.angle(gain,deg=True))}

def read_source(root:Path,label:str,size:int,source:int,target:float):
    f=np.arange(target-130,target+130.1,2.);path=root/f"{label}_size{size}_src{source}.txt"
    lines=[x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
    if len(lines)!=1:raise RuntimeError(f"BAD_EXPORT:{path.name}")
    values=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
    if len(values)!=len(f) or not np.isfinite(values).all():raise RuntimeError(f"BAD_VALUES:{path.name}")
    return values

def main():
    targets={.03:1150.,.05:950.,.07:750.};cases=[];controls={};mesh_paths=[]
    for alpha,target in targets.items():
        suffix=f"A{int(alpha*100):02d}";control=read_case(ROOT,f"FC_CONTROL_{suffix}",2,target);res=read_case(ROOT,f"FC_L0900_{suffix}",2,target)
        cm,rm=marker(control,target),marker(res,target);controls[suffix]=cm
        cases.append({"alpha":alpha,"target_hz":target,**rm,"error_hz":rm["tracked_hz"]-target,
                      "control_depth_db":cm["fitted_depth_db"],"depth_margin_db":rm["fitted_depth_db"]-cm["fitted_depth_db"],
                      "visible":bool(not rm["at_search_boundary"] and rm["fitted_depth_db"]>=THRESHOLD and rm["fitted_depth_db"]-cm["fitted_depth_db"]>=2)})
        if alpha in (.03,.07):
            coarse=read_case(PREV,f"FC_L0900_{suffix}",3,target)
            for source in range(4):mesh_paths.append({"alpha":alpha,"source":source,"size3_to_size2_complex_l2":rel(coarse[source],res[source]),
                                                      "requires_size1":bool(rel(coarse[source],res[source])>.03)})
    monotonic=all(cases[i]["tracked_hz"]>cases[i+1]["tracked_hz"] for i in range(2));mechanism=all(c["visible"] and abs(c["error_hz"])<=30 for c in cases) and monotonic
    pending=[x for x in mesh_paths if x["requires_size1"]]
    result={"state":"PRINT_CONV_B_ADAPTIVE_SIZE1_REQUIRED" if mechanism and pending else ("PRINT_CONV_B_INITIAL_PASS" if mechanism else "PRINT_CONV_B_MECHANISM_STOP"),
            "selected_length_mm":9.0,"mesh_size":2,"controls":controls,"cases":cases,"strictly_monotonic":bool(monotonic),
            "endpoint_mesh_paths":mesh_paths,"adaptive_size1_requests":pending,"mechanism_pass":bool(mechanism),
            "final_pass":bool(mechanism and not pending)}
    (ROOT/"initial_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))

def finalize():
    initial=json.loads((ROOT/"initial_result.json").read_text(encoding="utf-8"));paths=[]
    for row in initial["endpoint_mesh_paths"]:
        alpha=float(row["alpha"]);target={.03:1150.,.07:750.}[alpha];source=int(row["source"]);suffix=f"A{int(alpha*100):02d}"
        item=dict(row)
        if row["requires_size1"]:
            size2=read_source(ROOT,f"FC_L0900_{suffix}",2,source,target);size1=read_source(ROOT,f"FC_L0900_{suffix}",1,source,target)
            item["size2_to_size1_complex_l2"]=rel(size2,size1);item["convergence_basis"]="size2_to_size1"
            item["pass"]=bool(item["size2_to_size1_complex_l2"]<=.03)
        else:
            item["convergence_basis"]="size3_to_size2";item["pass"]=True
        paths.append(item)
    gen25=json.loads((Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_25_MESH_SOURCE0_A/result_summary.json").read_text(encoding="utf-8"))
    alpha05=[{"alpha":.05,"source":0,"convergence_basis":"size2_to_size1","complex_l2":gen25["convergence"]["size2_to_size1"]["complex_relative_l2"],"pass":bool(gen25["convergence"]["pass"])}]
    diag=json.loads((PREV/"post_gate_mesh_diagnostic.json").read_text(encoding="utf-8"))
    for r in diag["per_source"]:
        if r["source"]>0:alpha05.append({"alpha":.05,"source":r["source"],"convergence_basis":"size3_to_size2","complex_l2":r["raw_complex_relative_l2"],"pass":bool(r["raw_complex_relative_l2"]<=.03)})
    all_paths=paths+alpha05;passed=bool(initial["mechanism_pass"] and all(r["pass"] for r in all_paths))
    result={"state":"PRINT_CONV_B_PASS" if passed else "PRINT_CONV_B_MESH_STOP","selected_length_mm":9.0,"accepted_global_mesh_size":2,
            "cases":initial["cases"],"controls":initial["controls"],"strictly_monotonic":initial["strictly_monotonic"],
            "endpoint_convergence_paths":paths,"alpha05_convergence_paths":alpha05,"all_twelve_paths_pass":bool(all(r["pass"] for r in all_paths)),
            "pass":passed,"authorization":"Open sealed alpha04/alpha06 blind confirmation on global size2" if passed else "Stop before blind points and tolerance"}
    (ROOT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    import matplotlib.pyplot as plt
    alphas=[c["alpha"] for c in result["cases"]];tracked=[c["tracked_hz"] for c in result["cases"]];targets=[c["target_hz"] for c in result["cases"]]
    fig,axes=plt.subplots(1,2,figsize=(9,3.6),constrained_layout=True)
    axes[0].plot(alphas,tracked,"o-",label="size2 full-wave");axes[0].plot(alphas,targets,"s--",label="target");axes[0].set(xlabel="alpha",ylabel="Frequency (Hz)",title="Converged endpoint mapping");axes[0].grid(alpha=.25);axes[0].legend(frameon=False)
    labels=[f"a{int(r['alpha']*100):02d}s{r['source']}" for r in all_paths]
    vals=[100*(r["size2_to_size1_complex_l2"] if "size2_to_size1_complex_l2" in r else (r["complex_l2"] if "complex_l2" in r else r["size3_to_size2_complex_l2"])) for r in all_paths]
    axes[1].bar(labels,vals,color="#377eb8");axes[1].axhline(3,color="#d62728",ls="--",label="3% gate");axes[1].tick_params(axis="x",rotation=45);axes[1].set(ylabel="Accepted adjacent-grid complex L2 (%)",title="Twelve convergence paths");axes[1].grid(axis="y",alpha=.25);axes[1].legend(frameon=False)
    fig.savefig(ROOT/"print_conv_b_summary.png",dpi=220);plt.close(fig)
    print(json.dumps(result,indent=2))

def diagnostic():
    target=1150.;s3=read_source(PREV,"FC_L0900_A03",3,2,target);s2=read_source(ROOT,"FC_L0900_A03",2,2,target);s1=read_source(ROOT,"FC_L0900_A03",1,2,target)
    result={"state":"POST_GATE_READ_ONLY_A03_SOURCE2_DIAGNOSTIC","no_gate_change":True,
            "size3_to_size2":metrics(s3,s2),"size2_to_size1":metrics(s2,s1),
            "markers":{"size3":marker(s3[None,:],target),"size2":marker(s2[None,:],target),"size1":marker(s1[None,:],target)},
            "interpretation":"The sole failed path retains a stable resonance marker but its full complex response is not converged at automatic size1."}
    (ROOT/"post_gate_diagnostic.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))

def audit():
    size2=(("FC_CONTROL_A03",1150),("FC_L0900_A03",1150),("FC_CONTROL_A05",950),("FC_L0900_A05",950),("FC_CONTROL_A07",750),("FC_L0900_A07",750))
    models=[];spectra=0
    for label,target in size2:
        values=read_case(ROOT,label,2,target);mph=ROOT/f"{label}_size2.mph"
        if not mph.is_file() or mph.stat().st_size==0:raise RuntimeError(f"BAD_MPH:{mph.name}")
        models.append({"label":label,"mesh":2,"spectra":4,"shape":list(values.shape),"mph_bytes":mph.stat().st_size});spectra+=4
    for label,target,sources in (("FC_L0900_A03",1150,(0,1,2)),("FC_L0900_A07",750,(0,))):
        for source in sources:read_source(ROOT,label,1,source,target)
        mph=ROOT/f"{label}_size1.mph"
        if not mph.is_file() or mph.stat().st_size==0:raise RuntimeError(f"BAD_MPH:{mph.name}")
        models.append({"label":label,"mesh":1,"spectra":len(sources),"sources":list(sources),"mph_bytes":mph.stat().st_size});spectra+=len(sources)
    logs=("comsol.log","adaptive_comsol.log","comsol_stdout.log","adaptive_stdout.log")
    for name in logs:
        if not (ROOT/name).is_file() or (ROOT/name).stat().st_size==0:raise RuntimeError(f"BAD_LOG:{name}")
    result={"state":"PRINT_CONV_B_ARTIFACT_AUDIT_PASS","model_count":len(models),"spectrum_count":spectra,"frequency_points_each":131,
            "all_finite":True,"models":models,"logs":list(logs),"pass":True}
    (ROOT/"artifact_audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps({k:v for k,v in result.items() if k!="models"},indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("phase",nargs="?",default="initial",choices=("initial","finalize","diagnostic","audit"));a=p.parse_args();{"initial":main,"finalize":finalize,"diagnostic":diagnostic,"audit":audit}[a.phase]()
