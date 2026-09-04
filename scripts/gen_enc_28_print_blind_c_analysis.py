"""Frozen initial blind analysis for PRINT-BLIND-C."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_28_PRINT_BLIND_C";THRESHOLD=5.731630586148788
def read(label,size,target,sources=(0,1,2,3)):
 f=np.arange(target-130,target+130.1,2.);rows=[]
 for s in sources:
  p=ROOT/f"{label}_size{size}_src{s}.txt";lines=[x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
  if len(lines)!=1:raise RuntimeError(f"BAD_EXPORT:{p.name}")
  v=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
  if len(v)!=len(f) or not np.isfinite(v).all():raise RuntimeError(f"BAD_VALUES:{p.name}")
  rows.append(v)
 return np.stack(rows)
def marker(v,target):
 f=np.arange(target-130,target+130.1,2.);db=np.mean(20*np.log10(np.maximum(np.abs(v),1e-30)),axis=0);best=(-1e99,np.nan)
 for c in np.arange(target-30,target+30.01,2.):
  q=np.abs(f-c)<=201/2;ff=f[q];yy=db[q];x=(ff-c)/(201/2);lor=1/(1+(24*(ff-c)/c)**2);amp=float(np.linalg.lstsq(np.column_stack((np.ones_like(x),x,-lor)),yy,rcond=None)[0][-1])
  if amp>best[0]:best=(amp,c)
 return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0]),"at_search_boundary":bool(best[1] in (target-30,target+30))}
def main():
 blind=[];paths=[];requests=[]
 for alpha,target in ((.04,1050.),(.06,850.)):
  a=f"A{int(alpha*100):02d}";control=read(f"BLIND_CONTROL_{a}",2,target);fine=read(f"BLIND_L0900_{a}",2,target);coarse=read(f"BLIND_L0900_{a}",3,target);cm,fm=marker(control,target),marker(fine,target)
  blind.append({"alpha":alpha,"target_hz":target,**fm,"error_hz":fm["tracked_hz"]-target,"control_depth_db":cm["fitted_depth_db"],"depth_margin_db":fm["fitted_depth_db"]-cm["fitted_depth_db"],"visible":bool(not fm["at_search_boundary"] and fm["fitted_depth_db"]>=THRESHOLD and fm["fitted_depth_db"]-cm["fitted_depth_db"]>=2)})
  for s in range(4):
   l2=float(np.linalg.norm(coarse[s]-fine[s])/np.linalg.norm(coarse[s]));row={"alpha":alpha,"source":s,"size3_to_size2_complex_l2":l2,"requires_size1":bool(l2>.03)};paths.append(row)
   if row["requires_size1"]:requests.append(row)
 endpoints=json.loads((Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_26_PRINT_CONV_B/result_summary.json").read_text(encoding="utf-8"))["cases"];five=sorted(endpoints+blind,key=lambda x:x["alpha"]);mechanism=all(x["visible"] and abs(x["error_hz"])<=30 for x in five) and all(five[i]["tracked_hz"]>five[i+1]["tracked_hz"] for i in range(4))
 result={"state":"PRINT_BLIND_C_ADAPTIVE_SIZE1_REQUIRED" if mechanism and requests else ("PRINT_BLIND_C_INITIAL_PASS" if mechanism else "PRINT_BLIND_C_MECHANISM_STOP"),"blind_cases":blind,"five_level_cases":five,"strictly_monotonic":bool(all(five[i]["tracked_hz"]>five[i+1]["tracked_hz"] for i in range(4))),"mesh_paths":paths,"adaptive_size1_requests":requests,"mechanism_pass":bool(mechanism),"final_pass":bool(mechanism and not requests)}
 (ROOT/"initial_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))
def finalize():
 initial=json.loads((ROOT/"initial_result.json").read_text(encoding="utf-8"));paths=[]
 for row in initial["mesh_paths"]:
  item=dict(row)
  if row["requires_size1"]:
   alpha=float(row["alpha"]);target=1050. if alpha==.04 else 850.;a=f"A{int(alpha*100):02d}";s=int(row["source"]);v2=read(f"BLIND_L0900_{a}",2,target,(s,))[0];v1=read(f"BLIND_L0900_{a}",1,target,(s,))[0];l2=float(np.linalg.norm(v2-v1)/np.linalg.norm(v2));item["size2_to_size1_complex_l2"]=l2;item["convergence_basis"]="size2_to_size1";item["pass"]=bool(l2<=.03)
  else:item["convergence_basis"]="size3_to_size2";item["pass"]=True
  paths.append(item)
 passed=bool(initial["mechanism_pass"] and all(x["pass"] for x in paths));failed=[x for x in paths if not x["pass"]]
 result={"state":"PRINT_BLIND_C_PASS" if passed else "PRINT_BLIND_C_MESH_STOP","blind_cases":initial["blind_cases"],"five_level_cases":initial["five_level_cases"],"strictly_monotonic":initial["strictly_monotonic"],"convergence_paths":paths,"failed_paths":failed,"pass":passed,"authorization":"Proceed to bounded manufacturing-tolerance study" if passed else "Resolve failed blind mesh paths before tolerance"}
 (ROOT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,2,figsize=(9,3.6),constrained_layout=True);cases=result["five_level_cases"];aa=[x["alpha"] for x in cases]
 axes[0].plot(aa,[x["tracked_hz"] for x in cases],"o-",label="size2 full-wave");axes[0].plot(aa,[x["target_hz"] for x in cases],"s--",label="target");axes[0].set(xlabel="alpha",ylabel="Frequency (Hz)",title="Five-level blind mapping");axes[0].grid(alpha=.25);axes[0].legend(frameon=False)
 labels=[f"a{int(x['alpha']*100):02d}s{x['source']}" for x in paths];vals=[100*(x["size2_to_size1_complex_l2"] if "size2_to_size1_complex_l2" in x else x["size3_to_size2_complex_l2"]) for x in paths];axes[1].bar(labels,vals);axes[1].axhline(3,color="#d62728",ls="--",label="3% gate");axes[1].set(ylabel="Accepted adjacent-grid complex L2 (%)",title="Blind-path convergence");axes[1].tick_params(axis="x",rotation=40);axes[1].grid(axis="y",alpha=.25);axes[1].legend(frameon=False);fig.savefig(ROOT/"print_blind_c_summary.png",dpi=220);plt.close(fig);print(json.dumps(result,indent=2))
def audit():
 specs=[("BLIND_CONTROL_A04",2,1050,range(4)),("BLIND_L0900_A04",2,1050,range(4)),("BLIND_L0900_A04",3,1050,range(4)),("BLIND_L0900_A04",1,1050,(0,1,2)),("BLIND_CONTROL_A06",2,850,range(4)),("BLIND_L0900_A06",2,850,range(4)),("BLIND_L0900_A06",3,850,range(4)),("BLIND_L0900_A06",1,850,(0,))];models=[];count=0
 for label,size,target,sources in specs:
  sources=tuple(sources);read(label,size,target,sources);mph=ROOT/f"{label}_size{size}.mph"
  if not mph.is_file() or mph.stat().st_size==0:raise RuntimeError(f"BAD_MPH:{mph.name}")
  models.append({"label":label,"mesh":size,"sources":list(sources),"mph_bytes":mph.stat().st_size});count+=len(sources)
 for name in ("initial_comsol.log","adaptive_comsol.log","initial_stdout.log","adaptive_stdout.log"):
  if not (ROOT/name).is_file() or (ROOT/name).stat().st_size==0:raise RuntimeError(f"BAD_LOG:{name}")
 result={"state":"PRINT_BLIND_C_ARTIFACT_AUDIT_PASS","model_count":len(models),"spectrum_count":count,"frequency_points_each":131,"all_finite":True,"models":models,"pass":True};(ROOT/"artifact_audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps({k:v for k,v in result.items() if k!="models"},indent=2))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("phase",nargs="?",default="initial",choices=("initial","finalize","audit"));a=p.parse_args();{"initial":main,"finalize":finalize,"audit":audit}[a.phase]()
