"""Frozen A04-S1-PHASE-MESH-B analysis."""
from pathlib import Path
import json,numpy as np
ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_29_A04_S1_PHASE_MESH_B";PREV=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_28_PRINT_BLIND_C";F=np.arange(920,1180.1,2.)
def read(p):
 lines=[x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
 if len(lines)!=1:raise RuntimeError(f"BAD_EXPORT:{p.name}")
 v=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
 if len(v)!=131 or not np.isfinite(v).all():raise RuntimeError(f"BAD_VALUES:{p.name}")
 return v
def met(a,b):
 g=np.vdot(b,a)/np.vdot(b,b);return {"complex_relative_l2":float(np.linalg.norm(a-b)/np.linalg.norm(a)),"magnitude_relative_l2":float(np.linalg.norm(abs(a)-abs(b))/np.linalg.norm(abs(a))),"gain_aligned_complex_relative_l2":float(np.linalg.norm(a-g*b)/np.linalg.norm(a)),"gain_phase_deg":float(np.angle(g,deg=True))}
def marker(v):
 db=20*np.log10(np.maximum(abs(v),1e-30));best=(-1e99,np.nan)
 for c in np.arange(1020,1080.01,2.):
  q=abs(F-c)<=201/2;ff=F[q];x=(ff-c)/(201/2);lor=1/(1+(24*(ff-c)/c)**2);amp=float(np.linalg.lstsq(np.column_stack((np.ones(q.sum()),x,-lor)),db[q],rcond=None)[0][-1])
  if amp>best[0]:best=(amp,c)
 return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0])}
def main():
 c={m:read(ROOT/f"{m}_center_src1.txt") for m in ("G1","F32","F26")};r={m:read(ROOT/f"{m}_northref_src1.txt") for m in c};seq=[]
 for a,b in (("G1","F32"),("F32","F26")):
  ma,mb=marker(c[a]),marker(c[b]);seq.append({"coarse":a,"fine":b,"raw":met(c[a],c[b]),"reference_normalized":met(c[a]/r[a],c[b]/r[b]),"coarse_marker":ma,"fine_marker":mb,"frequency_shift_hz":mb["tracked_hz"]-ma["tracked_hz"],"depth_shift_db":mb["fitted_depth_db"]-ma["fitted_depth_db"]})
 final=seq[-1];passed=final["raw"]["complex_relative_l2"]<=.03 and abs(final["frequency_shift_hz"])<=10 and abs(final["depth_shift_db"])<=1.5;prior=read(PREV/"BLIND_L0900_A04_size1_src1.txt");det=float(np.linalg.norm(prior-c["G1"])/np.linalg.norm(prior));result={"state":"A04_S1_PHASE_MESH_PASS" if passed else "A04_S1_PHASE_MESH_STOP","alpha":.04,"source":1,"sequence":seq,"size1_rerun_relative_l2":det,"accepted_mesh":"F32" if passed else None,"pass":bool(passed),"authorization":"Close PRINT-BLIND-C and proceed to tolerance" if passed else "Stop before tolerance"};(ROOT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
 import matplotlib.pyplot as plt
 fig,ax=plt.subplots(figsize=(6,3.6),constrained_layout=True)
 for m,s in (("G1","--"),("F32","-."),("F26",":")):ax.plot(F,20*np.log10(np.maximum(abs(c[m]),1e-30)),s,label=m)
 ax.set(xlabel="Frequency (Hz)",ylabel="Source-1 level (dB)",title="alpha=0.04 custom mesh closure");ax.grid(alpha=.25);ax.legend(frameon=False);fig.savefig(ROOT/"a04_s1_phase_mesh_summary.png",dpi=220);plt.close(fig);print(json.dumps(result,indent=2))
if __name__=="__main__":main()
