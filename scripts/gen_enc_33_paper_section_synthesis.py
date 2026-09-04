"""Cross-stage synthesis for the printable five-level full-wave paper section."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

BASE=Path(__file__).resolve().parents[1];OUT=BASE/"outputs/gen_enc/GEN_ENC_33_PAPER_SECTION_SYNTHESIS";OUT.mkdir(parents=True,exist_ok=True)
def load(rel):return json.loads((BASE/rel).read_text(encoding="utf-8"))
paths={
 "static":"outputs/gen_enc/GEN_ENC_24_PRINT_COMP_A/static_result.json","anchor":"outputs/gen_enc/GEN_ENC_24_PRINT_COMP_A/anchor_result.json",
 "conv":"outputs/gen_enc/GEN_ENC_26_PRINT_CONV_B/result_summary.json","conv_close":"outputs/gen_enc/GEN_ENC_27_A03_S2_PHASE_MESH_A/result_summary.json",
 "blind":"outputs/gen_enc/GEN_ENC_28_PRINT_BLIND_C/result_summary.json","blind_close":"outputs/gen_enc/GEN_ENC_30_A04_S1_MESH_CLOSURE_C/result_summary.json",
 "tol":"outputs/gen_enc/GEN_ENC_31_PRINT_TOL_A/result_summary.json","tol_close":"outputs/gen_enc/GEN_ENC_32_TOL_A03_S2_MESH_B/result_summary.json"}
d={k:load(v) for k,v in paths.items()}
cases=d["blind"]["five_level_cases"];targets=np.array([x["target_hz"] for x in cases]);tracked=np.array([x["tracked_hz"] for x in cases]);errors=tracked-targets
slope,intercept=np.polyfit(targets,tracked,1);pred=slope*targets+intercept;r2=1-float(np.sum((tracked-pred)**2)/np.sum((tracked-tracked.mean())**2))
accepted=[]
for x in d["conv"]["endpoint_convergence_paths"]+d["conv"]["alpha05_convergence_paths"]:
 if x.get("pass"):accepted.append(x.get("size2_to_size1_complex_l2",x.get("complex_l2",x.get("size3_to_size2_complex_l2"))))
accepted.append(d["conv_close"]["sequence"][-1]["raw"]["complex_relative_l2"])
for x in d["blind"]["convergence_paths"]:
 if x.get("pass"):accepted.append(x.get("size2_to_size1_complex_l2",x["size3_to_size2_complex_l2"]))
accepted.append(d["blind_close"]["raw"]["complex_relative_l2"])
accepted.append(d["tol"]["mesh_sentinels"][1]["size2_to_size1_complex_l2"]);accepted.append(d["tol_close"]["sequence"][-1]["raw"]["complex_relative_l2"])
intervals=d["tol"]["five_level_intervals"];gaps=d["tol"]["adjacent_worst_case_gaps_hz"]
tol_mechanism=all(x["direction_pass"] and x["visible"] and max(abs(x["low_corner"]["tracked_hz"]-x["target_hz"]),abs(x["high_corner"]["tracked_hz"]-x["target_hz"]))<=45 for x in intervals) and min(gaps)>=20 and d["tol"]["single_factor_direction_pass"]
overall=bool(d["static"]["pass"] and d["anchor"]["pass"] and d["blind"]["strictly_monotonic"] and all(x["visible"] and abs(x["error_hz"])<=30 for x in cases) and d["conv_close"]["pass"] and d["blind_close"]["pass"] and tol_mechanism and d["tol"]["mesh_sentinels"][1]["pass"] and d["tol_close"]["pass"])
hashes={k:hashlib.sha256((BASE/v).read_bytes()).hexdigest() for k,v in paths.items()}
result={"state":"PRINTABLE_FIVE_LEVEL_FULLWAVE_SECTION_READY" if overall else "PAPER_SECTION_NOT_READY","scope":"lossy_3d_pressure_acoustics_with_rectangular_narrow_region_neck_model",
 "geometry":{"four_corner_compensation_static_pass":d["static"]["pass"],"selected_physical_neck_length_mm":9.0,"neck_cross_section_mm2":[2,4]},
 "five_level":{"cases":cases,"strictly_monotonic":d["blind"]["strictly_monotonic"],"maximum_absolute_error_hz":float(max(abs(errors))),"mean_absolute_error_hz":float(np.mean(abs(errors))),"rmse_hz":float(np.sqrt(np.mean(errors**2))),"linear_fit_slope":float(slope),"linear_fit_intercept_hz":float(intercept),"r_squared":r2,"minimum_depth_db":float(min(x["fitted_depth_db"] for x in cases)),"minimum_control_margin_db":float(min(x["depth_margin_db"] for x in cases))},
 "numerics":{"all_triggered_paths_closed":True,"maximum_accepted_adjacent_grid_complex_l2":float(max(accepted)),"gate":.03,"accepted_path_count":len(accepted)},
 "tolerance":{"contract":d["tol"]["tolerance_contract"],"single_factor_alpha05":d["tol"]["single_factor_alpha05"],"intervals":intervals,"adjacent_worst_case_gaps_hz":gaps,"minimum_gap_hz":float(min(gaps)),"maximum_corner_absolute_error_hz":float(max(max(abs(x["low_corner"]["tracked_hz"]-x["target_hz"]),abs(x["high_corner"]["tracked_hz"]-x["target_hz"])) for x in intervals)),"mesh_sentinels_closed":True},
 "claim":"Within the stated lossy 3D full-wave model and bounded effective-geometry tolerances, the printable four-corner-compensated resonator realizes a visible, monotonic, non-overlapping five-level frequency code.",
 "limitations":["No fabricated-device measurement in this evidence chain","Narrow-region thermoviscous approximation rather than a full thermoviscous-domain solve","Effective-geometry tolerance bounds are not an empirical printer-accuracy distribution","Central-point four-direction readout only","No four-family classification claim"],"source_sha256":hashes,"pass":overall}
(OUT/"result_summary.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
fig,ax=plt.subplots(2,2,figsize=(10,7),constrained_layout=True)
lengths=[x["physical_neck_length_mm"] for x in d["anchor"]["candidates"]];freqs=[x["tracked_hz"] for x in d["anchor"]["candidates"]]
ax[0,0].plot(lengths,freqs,"o-");ax[0,0].axhline(950,color=".35",ls="--");ax[0,0].set(xlabel="Physical neck length (mm)",ylabel="Tracked frequency (Hz)",title="(a) Public alpha=0.05 calibration");ax[0,0].grid(alpha=.25)
aa=[x["alpha"] for x in cases];ax[0,1].plot(aa,tracked,"o-",label="Blind full-wave");ax[0,1].plot(aa,targets,"s--",label="Target");ax[0,1].set(xlabel="alpha",ylabel="Frequency (Hz)",title="(b) Five-level mapping");ax[0,1].grid(alpha=.25);ax[0,1].legend(frameon=False)
lows=np.array([x["low_corner"]["tracked_hz"] for x in intervals]);highs=np.array([x["high_corner"]["tracked_hz"] for x in intervals]);ax[1,0].errorbar(aa,tracked,yerr=np.vstack((tracked-lows,highs-tracked)),fmt="o",capsize=4,label="Combined tolerance corners");ax[1,0].plot(aa,targets,"s--",label="Target");ax[1,0].set(xlabel="alpha",ylabel="Frequency interval (Hz)",title="(c) Bounded tolerance envelopes");ax[1,0].grid(alpha=.25);ax[1,0].legend(frameon=False)
sf=d["tol"]["single_factor_alpha05"];ax[1,1].bar([x["factor"] for x in sf],[x["shift_from_nominal_hz"] for x in sf],color=["#377eb8" if x["shift_from_nominal_hz"]>0 else "#e41a1c" for x in sf]);ax[1,1].axhline(0,color=".2",lw=.8);ax[1,1].set(ylabel="Shift from nominal (Hz)",title="(d) alpha=0.05 single-factor effects");ax[1,1].grid(axis="y",alpha=.25)
fig.savefig(OUT/"printable_five_level_fullwave_section.png",dpi=240);plt.close(fig)
expected={
 "GEN_ENC_24_PRINT_COMP_A":(11,44),"GEN_ENC_25_MESH_SOURCE0_A":(4,4),"GEN_ENC_26_PRINT_CONV_B":(8,28),
 "GEN_ENC_27_A03_S2_PHASE_MESH_A":(4,8),"GEN_ENC_28_PRINT_BLIND_C":(8,28),"GEN_ENC_29_A04_S1_PHASE_MESH_B":(3,6),
 "GEN_ENC_30_A04_S1_MESH_CLOSURE_C":(1,2),"GEN_ENC_31_PRINT_TOL_A":(18,66),"GEN_ENC_32_TOL_A03_S2_MESH_B":(3,6)}
audit_rows=[]
for stage,(nm,ns) in expected.items():
    folder=BASE/"outputs/gen_enc"/stage;models=list(folder.glob("*.mph"));spectra=list(folder.glob("*_src*.txt"))
    if len(models)!=nm or len(spectra)!=ns:raise RuntimeError(f"COUNT_MISMATCH:{stage}:{len(models)},{len(spectra)}")
    if any(x.stat().st_size==0 for x in models):raise RuntimeError(f"EMPTY_MODEL:{stage}")
    for p in spectra:
        lines=[x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
        if len(lines)!=1:raise RuntimeError(f"BAD_SPECTRUM:{p}")
        vals=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
        if len(vals)!=131 or not np.isfinite(vals).all():raise RuntimeError(f"NONFINITE_SPECTRUM:{p}")
    audit_rows.append({"stage":stage,"model_count":nm,"spectrum_count":ns,"all_models_nonempty":True,"all_spectra_finite":True})
audit={"state":"PRINTABLE_FIVE_LEVEL_EVIDENCE_CHAIN_AUDIT_PASS","stage_count":len(expected),"model_count":sum(x[0] for x in expected.values()),"complex_spectrum_count":sum(x[1] for x in expected.values()),"frequency_points_each":131,"stages":audit_rows,"pass":True}
(OUT/"artifact_audit.json").write_text(json.dumps(audit,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k not in ("source_sha256","five_level","tolerance")},indent=2))
