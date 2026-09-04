from pathlib import Path
import json,numpy as np
ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_30_A04_S1_MESH_CLOSURE_C";PREV=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_29_A04_S1_PHASE_MESH_B";F=np.arange(920,1180.1,2.)
def read(p):
 lines=[x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")];v=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
 if len(lines)!=1 or len(v)!=131 or not np.isfinite(v).all():raise RuntimeError(f"BAD:{p.name}")
 return v
def met(a,b):
 g=np.vdot(b,a)/np.vdot(b,b);return {"complex_relative_l2":float(np.linalg.norm(a-b)/np.linalg.norm(a)),"magnitude_relative_l2":float(np.linalg.norm(abs(a)-abs(b))/np.linalg.norm(abs(a))),"aligned_relative_l2":float(np.linalg.norm(a-g*b)/np.linalg.norm(a)),"gain_phase_deg":float(np.angle(g,deg=True))}
def marker(v):
 db=20*np.log10(np.maximum(abs(v),1e-30));best=(-1e99,np.nan)
 for c in np.arange(1020,1080.1,2.):
  q=abs(F-c)<=100.5;ff=F[q];x=(ff-c)/100.5;lor=1/(1+(24*(ff-c)/c)**2);amp=float(np.linalg.lstsq(np.column_stack((np.ones(q.sum()),x,-lor)),db[q],rcond=None)[0][-1]);best=(amp,c) if amp>best[0] else best
 return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0])}
def main():
 a=read(PREV/"F26_center_src1.txt");b=read(ROOT/"F20_center_src1.txt");ar=read(PREV/"F26_northref_src1.txt");br=read(ROOT/"F20_northref_src1.txt");ma,mb=marker(a),marker(b);raw=met(a,b);passed=raw["complex_relative_l2"]<=.03 and abs(mb["tracked_hz"]-ma["tracked_hz"])<=10 and abs(mb["fitted_depth_db"]-ma["fitted_depth_db"])<=1.5;result={"state":"A04_S1_MESH_CLOSURE_PASS" if passed else "A04_S1_MESH_CLOSURE_STOP","coarse":"F26_hmax2.6mm","fine":"F20_hmax2.0mm","raw":raw,"reference_normalized":met(a/ar,b/br),"coarse_marker":ma,"fine_marker":mb,"frequency_shift_hz":mb["tracked_hz"]-ma["tracked_hz"],"depth_shift_db":mb["fitted_depth_db"]-ma["fitted_depth_db"],"accepted_mesh":"F26" if passed else None,"pass":bool(passed),"authorization":"Close PRINT-BLIND-C and proceed to tolerance" if passed else "Further convergence evidence required"};(ROOT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))
if __name__=="__main__":main()
