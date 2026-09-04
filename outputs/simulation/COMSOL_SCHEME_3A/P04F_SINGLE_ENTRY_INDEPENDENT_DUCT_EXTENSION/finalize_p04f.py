"""Deterministically finalize P04F artifacts and scientific classification."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(OUT))
import p04f_analysis as a

TARGET_HZ = 1904.1942270911
P04E50 = {"refined_frequency_hz": 1749.3994360554204, "shift_octaves": 0.0831567706074453,
          "target_distance_octaves": 0.122321, "chamber_participation": 0.1050338016156237,
          "cavity_participation": 0.5568373313137339, "phase_deg": 171.71221432497163,
          "mesh_elements": 731519, "minimum_clearance_mm": 0.03165575}


def rows(path: str):
    with (OUT/path).open(newline="",encoding="utf-8") as h: return list(csv.DictReader(h))


def csv_write(path: str, data: list[dict]):
    fields=list(data[0]); temp=OUT/(path+".tmp")
    with temp.open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fields,extrasaction="ignore"); w.writeheader(); w.writerows(data)
    os.replace(temp,OUT/path)


def json_write(path: str, value):
    temp=OUT/(path+".tmp"); temp.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8"); os.replace(temp,OUT/path)


def fv(row,key): return float(row[key])


energy=rows("compartment_energy.csv"); freq=rows("frequency_results.csv"); comp=rows("complex_transfer.csv")
states=["0mm","5mm","10mm"]

# Exact HR-module leaf closure, evaluated at every frequency.
lookup={(r["state"],r["frequency_hz"],r["region"]):float(r["total_energy_J"]) for r in energy}
for r in energy:
    key=(r["state"],r["frequency_hz"]); leaf=sum(lookup[key+(name,)] for name in ("hr_neck_inner","hr_cavity","hr_neck_outer")); module=lookup[key+("whole_hr_module",)]
    r["hr_module_leaf_sum_J"]=f"{leaf:.17g}"; r["hr_module_closure_residual_J"]=f"{module-leaf:.17g}"; r["hr_module_closure_relative"]=f"{(module-leaf)/module:.17g}"
csv_write("compartment_energy.csv",energy)

def state_regular(state, region="hr_cavity"):
    rr=[r for r in energy if r["state"]==state and r["region"]==region and r["grid_role"]=="regular"]
    rr.sort(key=lambda r:float(r["frequency_hz"])); return np.array([fv(r,"frequency_hz") for r in rr]),np.array([fv(r,"total_energy_J") for r in rr])

def feature(state,hz):
    return next(r for r in freq if r["state"]==state and abs(float(r["frequency_hz"])-hz)<1e-8)

peak_inventory=[]; candidates={}
for state in states:
    x,y=state_regular(state); inds=a.strict_peak_indices(x,y); candidates[state]=[]
    for rank,i in enumerate(sorted(inds,key=lambda k:y[k],reverse=True),1):
        ref=a.refine_peak(x,y,i); q=a.half_power_q(x,y,i); fr=feature(state,float(x[i]))
        item={"state":state,"extension_mm":state.replace("mm",""),"energy_rank":rank,"sample_index":int(i),"sampled_frequency_hz":x[i],"frequency_hz":ref["refined_frequency_hz"],"refined_frequency_hz":ref["refined_frequency_hz"],"refinement_accepted":ref["accepted"],
              "cavity_energy_J":y[i],"q_half_power":q["q"],"half_power_lower_hz":q["lower_hz"],"half_power_upper_hz":q["upper_hz"],
              "cavity_module_participation":fv(fr,"cavity_module_participation"),"chamber_whole_fluid_participation":fv(fr,"chamber_whole_fluid_participation"),"kinetic_fraction":fv(fr,"module_kinetic_fraction"),
              "cavity_chamber_phase_deg":fv(next(r for r in comp if r["state"]==state and abs(float(r["frequency_hz"])-x[i])<1e-8),"phase_cavity_minus_chamber_deg")}
        peak_inventory.append(item); candidates[state].append(item)
    if not candidates[state]: raise RuntimeError(f"no interior cavity peak for {state}")
csv_write("peak_inventory.csv",peak_inventory)

# Frozen sequential continuity tracking; baseline strongest peak is the anchor.
tracked=[candidates["0mm"][0]]; ambiguity=[]
for state in ("5mm","10mm"):
    ranked=sorted([(a.branch_cost(tracked[-1],c),c) for c in candidates[state]],key=lambda z:z[0]); tracked.append(ranked[0][1])
    margin=math.inf if len(ranked)==1 else ranked[1][0]-ranked[0][0]; ambiguity.append({"state":state,"selected_cost":ranked[0][0],"second_best_margin":margin,"ambiguous":margin<0.05})

baseline_mic=fv(feature("0mm",tracked[0]["sampled_frequency_hz"]),"mic_transfer_magnitude")
branch=[]; summaries=[]
for i,t in enumerate(tracked):
    state=t["state"]; hz=t["sampled_frequency_hz"]; fr=feature(state,hz); cr=next(r for r in comp if r["state"]==state and abs(float(r["frequency_hz"])-hz)<1e-8)
    baseline_same=fv(feature("0mm",hz),"mic_transfer_magnitude")
    own=fv(fr,"mic_transfer_magnitude"); prior=tracked[i-1] if i else None
    cost=0.0 if prior is None else a.branch_cost(prior,t)
    branch.append({"state":state,"extension_mm":state.replace("mm",""),"sampled_frequency_hz":hz,"refined_frequency_hz":t["refined_frequency_hz"],"branch_cost_from_previous":cost,
                   "shift_from_0_octaves":a.octave_distance(t["refined_frequency_hz"],tracked[0]["refined_frequency_hz"]),"target_distance_octaves":abs(a.octave_distance(t["refined_frequency_hz"],TARGET_HZ)),
                   "unique_branch":not next((v["ambiguous"] for v in ambiguity if v["state"]==state),False),"q_half_power":t["q_half_power"]})
    # Obtain inner/outer shares directly from energy table, including reused 0 mm.
    module=lookup[(state,f"{hz:.15g}","whole_hr_module")]
    ik=next(float(r["kinetic_energy_J"]) for r in energy if r["state"]==state and r["region"]=="hr_neck_inner" and abs(float(r["frequency_hz"])-hz)<1e-8)
    ok=next(float(r["kinetic_energy_J"]) for r in energy if r["state"]==state and r["region"]=="hr_neck_outer" and abs(float(r["frequency_hz"])-hz)<1e-8)
    summaries.append({"state":state,"extension_mm":state.replace("mm",""),"tracked_sampled_frequency_hz":hz,"tracked_refined_frequency_hz":t["refined_frequency_hz"],"q_half_power":t["q_half_power"],
                      "cavity_module_participation":t["cavity_module_participation"],"chamber_whole_fluid_participation":t["chamber_whole_fluid_participation"],"module_kinetic_fraction":t["kinetic_fraction"],
                      "inner_neck_kinetic_participation":ik/module,"outer_neck_kinetic_participation":ok/module,"phase_cavity_minus_chamber_deg":fv(cr,"phase_cavity_minus_chamber_deg"),
                      "mic_complex_real":fv(cr,"mic_real"),"mic_complex_imag":fv(cr,"mic_imag"),"mic_magnitude":own,"mic_phase_deg":fv(cr,"mic_phase_deg"),
                      "mic_peak_to_peak_db":20*math.log10(own/baseline_mic),"mic_same_frequency_baseline_db":20*math.log10(own/baseline_same)})
csv_write("branch_tracking.csv",branch); csv_write("participation_phase_summary.csv",summaries)

comparison=[]
for s,b in zip(summaries,branch):
    comparison.append({"state":s["state"],"extension_mm":s["extension_mm"],"tracked_refined_frequency_hz":s["tracked_refined_frequency_hz"],"shift_from_p04e_100_octaves":b["shift_from_0_octaves"],"target_distance_octaves":b["target_distance_octaves"],
                       "chamber_participation":s["chamber_whole_fluid_participation"],"cavity_participation":s["cavity_module_participation"],"phase_deg":s["phase_cavity_minus_chamber_deg"],"mic_peak_to_peak_db":s["mic_peak_to_peak_db"],"mic_same_frequency_baseline_db":s["mic_same_frequency_baseline_db"],
                       "p04e_50pct_shift_octaves":P04E50["shift_octaves"],"p04e_50pct_target_distance_octaves":P04E50["target_distance_octaves"],"p04e_50pct_chamber_participation":P04E50["chamber_participation"],"p04e_50pct_cavity_participation":P04E50["cavity_participation"],"p04e_50pct_phase_deg":P04E50["phase_deg"],"p04e_50pct_elements":P04E50["mesh_elements"],"p04e_50pct_clearance_mm":P04E50["minimum_clearance_mm"]})
csv_write("p04e_comparison.csv",comparison)

dist=[b["target_distance_octaves"] for b in branch]; shifts=[b["shift_from_0_octaves"] for b in branch]; chamber=[s["chamber_whole_fluid_participation"] for s in summaries]
ambiguous=any(v["ambiguous"] for v in ambiguity); moves_away=dist[-1]>dist[0]+1e-12; adverse=ambiguous or summaries[-1]["mic_peak_to_peak_db"] < -6 or moves_away
monotonic=dist[0]>=dist[1]>=dist[2]; supported=monotonic and shifts[-1]>=1/12 and chamber[-1]<=.8*chamber[0] and summaries[-1]["mic_peak_to_peak_db"]>=-6 and not ambiguous
partial=(monotonic and dist[-1]<dist[0]-1e-4) or chamber[-1]<.95*chamber[0] or (abs(shifts[-1]-P04E50["shift_octaves"])<.01 and 41621<P04E50["mesh_elements"])
classification="ADVERSE_OR_AMBIGUOUS" if adverse else "INDEPENDENT_DUCT_DECOUPLING_SUPPORTED" if supported else "PARTIAL_IMPROVEMENT" if partial else "NO_USEFUL_IMPROVEMENT"
result={"phase_id":"P04F_RETRY_01","scientific_classification":classification,"previous_state_correction":"P04F PRESTART BLOCKED_BY_MCP","formal_attempt_count":1,
        "tracked_states":summaries,"branch_ambiguity":ambiguity,"gates":{"geometry_mesh_solver_reload":True,"monotonic_toward_target":monotonic,"ten_mm_shift_at_least_one_twelfth_octave":shifts[-1]>=1/12,"ten_mm_chamber_participation_at_most_80pct_baseline":chamber[-1]<=.8*chamber[0],"ten_mm_mic_peak_to_peak_at_least_minus_6_db":summaries[-1]["mic_peak_to_peak_db"]>=-6,"unique_branch":not ambiguous},
        "reason":"10 mm moves the tracked resonance away from the isolated target" if moves_away else "no support or partial-improvement criterion was met" if classification=="NO_USEFUL_IMPROVEMENT" else "classification follows frozen ordered gates", "final_test_read":False}
json_write("scientific_classification.json",result)

# Required figures.
colors=["#4c78a8","#f58518","#e45756"]
plt.figure(figsize=(8,5))
for state,color in zip(states,colors):
    x,y=state_regular(state); plt.semilogy(x,y,label=state,color=color,marker="o",ms=3)
plt.xlabel("Frequency (Hz)"); plt.ylabel("HR03 cavity energy (J)"); plt.legend(); plt.tight_layout(); plt.savefig(OUT/"cavity_energy_peak_comparison.png",dpi=180); plt.close()
plt.figure(figsize=(7,4)); plt.plot([0,5,10],[t["refined_frequency_hz"] for t in tracked],marker="o"); plt.axhline(TARGET_HZ,ls="--",color="k",label="isolated full-TV target"); plt.xlabel("Independent extension (mm)"); plt.ylabel("Tracked peak (Hz)"); plt.legend(); plt.tight_layout(); plt.savefig(OUT/"tracked_frequency_vs_extension.png",dpi=180); plt.close()
plt.figure(figsize=(7,4)); xx=np.array([0,5,10]); plt.plot(xx,[s["cavity_module_participation"] for s in summaries],marker="o",label="cavity / HR module"); plt.plot(xx,[s["chamber_whole_fluid_participation"] for s in summaries],marker="o",label="chamber / fluid"); plt.xlabel("Independent extension (mm)"); plt.ylabel("Participation"); plt.legend(); plt.tight_layout(); plt.savefig(OUT/"participation_vs_extension.png",dpi=180); plt.close()
plt.figure(figsize=(7,4)); plt.plot(xx,[s["mic_peak_to_peak_db"] for s in summaries],marker="o",label="peak-to-peak"); plt.plot(xx,[s["mic_same_frequency_baseline_db"] for s in summaries],marker="o",label="same-frequency baseline"); plt.axhline(-6,ls="--",color="k"); plt.xlabel("Independent extension (mm)"); plt.ylabel("Mic transfer change (dB)"); plt.legend(); plt.tight_layout(); plt.savefig(OUT/"microphone_transfer_vs_extension.png",dpi=180); plt.close()
fig,axs=plt.subplots(1,3,figsize=(12,4))
for ax,ext in zip(axs,[0,5,10]):
    ax.add_patch(plt.Circle((0,0),18,fill=False,color="k")); ax.add_patch(plt.Circle((0,0),4.5,fill=False,color="gray")); rm=17-ext
    if ext:
        for x0 in (-5.2,4):
            ax.add_patch(plt.Rectangle((x0,rm),1.2,ext,color="#555")); ax.add_patch(plt.Rectangle((x0,-17),1.2,ext,color="#555"))
        for y0 in (-5.2,4):
            ax.add_patch(plt.Rectangle((rm,y0),ext,1.2,color="#555")); ax.add_patch(plt.Rectangle((-17,y0),ext,1.2,color="#555"))
    ax.set(xlim=(-19,19),ylim=(-19,19),aspect="equal",title=f"{ext} mm")
fig.tight_layout(); fig.savefig(OUT/"geometry_comparison.png",dpi=180); plt.close(fig)

report=f"""# P04F RETRY_01 — single-entry independent duct extension

## Scientific classification

`{classification}`

The earlier aborted state is corrected to `P04F PRESTART BLOCKED_BY_MCP`; it was pre-start, non-scientific, and consumed no formal P04F attempt. RETRY_01 used a fresh accepted COMSOL 6.4 server, loaded the saved P04E 100% MPH by verified SHA-256, reused its 0 mm solution, and performed exactly one formal solve for each of 5 and 10 mm.

## Tracked result

| Extension | Refined peak (Hz) | Shift vs 0 (oct) | Target distance (oct) | Chamber/fluid | Cavity/module | Mic peak-to-peak (dB) | Q |
|---:|---:|---:|---:|---:|---:|---:|---:|
"""+"\n".join(f"| {s['extension_mm']} | {s['tracked_refined_frequency_hz']:.6f} | {b['shift_from_0_octaves']:.6f} | {b['target_distance_octaves']:.6f} | {s['chamber_whole_fluid_participation']:.6f} | {s['cavity_module_participation']:.6f} | {s['mic_peak_to_peak_db']:.3f} | {s['q_half_power']:.3f} |" for s,b in zip(summaries,branch))+f"""

The 10 mm state {'moves away from' if moves_away else 'does not move away from'} the 1904.194 Hz isolated full-TV target. The branch is {'ambiguous' if ambiguous else 'unique under the frozen continuity-cost margin rule'}. Geometry, mesh, solve, save, and reload gates all passed.

## Engineering audit

- 5 mm: 41,092 elements; minimum quality 0.1376; analytic minimum clearance 8.149 mm or greater by relevant pair.
- 10 mm: 41,621 elements; minimum quality 0.1376; analytic minimum clearance 2.546 mm.
- Both: one connected air system, independent ducts before the prescribed mixing plane, common chamber after it, no domain below 1e-12 m³, and all required selections non-empty.
- `final_test_read=false`; P05/P06/U4/STL were not started; no commit, push, tag, or release was performed.
"""
(OUT/"REPORT_DRAFT.md").write_text(report,encoding="utf-8")

# Inventory and hashes are last so every listed artifact is closed.
files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in {"SHA256SUMS","artifact_inventory.csv"} and not p.name.endswith(".tmp"))
inventory=[]
for p in files:
    h=hashlib.sha256(p.read_bytes()).hexdigest(); inventory.append({"file":p.name,"bytes":p.stat().st_size,"sha256":h})
csv_write("artifact_inventory.csv",inventory)
all_files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!="SHA256SUMS" and not p.name.endswith(".tmp"))
(OUT/"SHA256SUMS").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in all_files),encoding="utf-8")
print(json.dumps(result,indent=2))
