"""Frozen PRINT-TOL-A analysis."""
from pathlib import Path
import json,numpy as np
ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_31_PRINT_TOL_A";TH=5.731630586148788
def read(label,size,target,sources=(0,1,2,3)):
 f=np.arange(target-130,target+130.1,2.);rows=[]
 for s in sources:
  p=ROOT/f"{label}_size{size}_src{s}.txt";lines=[x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")];v=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
  if len(lines)!=1 or len(v)!=131 or not np.isfinite(v).all():raise RuntimeError(f"BAD:{p.name}")
  rows.append(v)
 return np.stack(rows)
def marker(v,target):
 f=np.arange(target-130,target+130.1,2.);db=np.mean(20*np.log10(np.maximum(abs(v),1e-30)),axis=0);best=(-1e99,np.nan)
 for c in np.arange(target-60,target+60.1,2.):
  q=abs(f-c)<=100.5;ff=f[q];x=(ff-c)/100.5;lor=1/(1+(24*(ff-c)/c)**2);amp=float(np.linalg.lstsq(np.column_stack((np.ones(q.sum()),x,-lor)),db[q],rcond=None)[0][-1]);best=(amp,c) if amp>best[0] else best
 return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0]),"boundary":bool(best[1] in (target-60,target+60))}
def main():
 nominal={.03:1152.,.04:1058.,.05:954.,.06:860.,.07:756.};single=[]
 for name in ("LMIN","LMAX","AMIN","AMAX","VMIN","VMAX"):
  m=marker(read(f"SF_{name}_A05",3,950),950);single.append({"factor":name,**m,"shift_from_nominal_hz":m["tracked_hz"]-nominal[.05]})
 intervals=[]
 for alpha,target in ((.03,1150.),(.04,1050.),(.05,950.),(.06,850.),(.07,750.)):
  a=f"A{int(alpha*100):02d}";lo=marker(read(f"CORNER_LOW_{a}",2,target),target);hi=marker(read(f"CORNER_HIGH_{a}",2,target),target);intervals.append({"alpha":alpha,"target_hz":target,"nominal_hz":nominal[alpha],"low_corner":lo,"high_corner":hi,"low_shift_hz":lo["tracked_hz"]-nominal[alpha],"high_shift_hz":hi["tracked_hz"]-nominal[alpha],"direction_pass":bool(lo["tracked_hz"]<nominal[alpha]<hi["tracked_hz"]),"visible":bool(not lo["boundary"] and not hi["boundary"] and lo["fitted_depth_db"]>=TH and hi["fitted_depth_db"]>=TH)})
 gaps=[intervals[i]["low_corner"]["tracked_hz"]-intervals[i+1]["high_corner"]["tracked_hz"] for i in range(4)];sent=[]
 for alpha,target,label,source in ((.03,1150.,"CORNER_LOW_A03",2),(.07,750.,"CORNER_HIGH_A07",0)):
  v2=read(label,2,target,(source,))[0];v1=read(label,1,target,(source,))[0];sent.append({"alpha":alpha,"corner":label,"source":source,"size2_to_size1_complex_l2":float(np.linalg.norm(v2-v1)/np.linalg.norm(v2)),"pass":bool(np.linalg.norm(v2-v1)/np.linalg.norm(v2)<=.03)})
 sf_sign=next(x for x in single if x["factor"]=="LMIN")["shift_from_nominal_hz"]>0 and next(x for x in single if x["factor"]=="LMAX")["shift_from_nominal_hz"]<0 and next(x for x in single if x["factor"]=="AMIN")["shift_from_nominal_hz"]<0 and next(x for x in single if x["factor"]=="AMAX")["shift_from_nominal_hz"]>0 and next(x for x in single if x["factor"]=="VMIN")["shift_from_nominal_hz"]>0 and next(x for x in single if x["factor"]=="VMAX")["shift_from_nominal_hz"]<0
 passed=all(x["direction_pass"] and x["visible"] and max(abs(x["low_corner"]["tracked_hz"]-x["target_hz"]),abs(x["high_corner"]["tracked_hz"]-x["target_hz"]))<=45 for x in intervals) and min(gaps)>=20 and all(x["pass"] for x in sent) and sf_sign
 result={"state":"PRINT_TOL_A_PASS" if passed else "PRINT_TOL_A_STOP","tolerance_contract":{"neck_length_mm":9.0,"neck_length_delta_mm":.2,"neck_area_relative_delta":.02,"cavity_volume_relative_delta":.02,"combined_corners":"all frequency-lowering or all frequency-raising"},"single_factor_alpha05":single,"five_level_intervals":intervals,"adjacent_worst_case_gaps_hz":gaps,"minimum_gap_hz":min(gaps),"mesh_sentinels":sent,"single_factor_direction_pass":bool(sf_sign),"pass":bool(passed),"authorization":"Prepare paper-section synthesis" if passed else "Do not claim bounded tolerance robustness"};(ROOT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))
if __name__=="__main__":main()
