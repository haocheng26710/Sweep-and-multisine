from pathlib import Path
import json,numpy as np
ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_32_TOL_A03_S2_MESH_B";PREV=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_31_PRINT_TOL_A";F=np.arange(1020,1280.1,2.)
def read(p):
 lines=[x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")];v=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
 if len(lines)!=1 or len(v)!=131 or not np.isfinite(v).all():raise RuntimeError(f"BAD:{p.name}")
 return v
def met(a,b):
 g=np.vdot(b,a)/np.vdot(b,b);return {"complex_relative_l2":float(np.linalg.norm(a-b)/np.linalg.norm(a)),"magnitude_relative_l2":float(np.linalg.norm(abs(a)-abs(b))/np.linalg.norm(abs(a))),"aligned_relative_l2":float(np.linalg.norm(a-g*b)/np.linalg.norm(a)),"gain_phase_deg":float(np.angle(g,deg=True))}
def marker(v):
 db=20*np.log10(np.maximum(abs(v),1e-30));best=(-1e99,np.nan)
 for c in np.arange(1090,1210.1,2.):
  q=abs(F-c)<=100.5;ff=F[q];x=(ff-c)/100.5;lor=1/(1+(24*(ff-c)/c)**2);amp=float(np.linalg.lstsq(np.column_stack((np.ones(q.sum()),x,-lor)),db[q],rcond=None)[0][-1]);best=(amp,c) if amp>best[0] else best
 return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0])}
def main():
 c={"G2":read(PREV/"CORNER_LOW_A03_size2_src2.txt")};r={}
 for m in ("F32","F26","F20"):c[m]=read(ROOT/f"{m}_center_src2.txt");r[m]=read(ROOT/f"{m}_westref_src2.txt")
 seq=[]
 for a,b in (("G2","F32"),("F32","F26"),("F26","F20")):
  ma,mb=marker(c[a]),marker(c[b]);row={"coarse":a,"fine":b,"raw":met(c[a],c[b]),"coarse_marker":ma,"fine_marker":mb,"frequency_shift_hz":mb["tracked_hz"]-ma["tracked_hz"],"depth_shift_db":mb["fitted_depth_db"]-ma["fitted_depth_db"]}
  if a!="G2":row["reference_normalized"]=met(c[a]/r[a],c[b]/r[b])
  seq.append(row)
 final=seq[-1];passed=final["raw"]["complex_relative_l2"]<=.03 and abs(final["frequency_shift_hz"])<=10 and abs(final["depth_shift_db"])<=1.5;result={"state":"TOL_A03_S2_MESH_PASS" if passed else "TOL_A03_S2_MESH_STOP","corner":"LOW_A03","source":2,"sequence":seq,"accepted_mesh":"F26" if passed else None,"pass":bool(passed),"authorization":"Accept PRINT-TOL-A and prepare paper synthesis" if passed else "Do not claim tolerance robustness"};(ROOT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))
if __name__=="__main__":main()
