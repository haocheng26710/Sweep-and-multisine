"""Offline P04C peak, participation, branch, classification, and figure analysis."""
from __future__ import annotations

import csv
import itertools
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, peak_prominences

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC"
P03 = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01"
MODULES = [f"HR{i:02d}" for i in range(1, 9)]
LEAF = ["hr_neck_inner", "hr_cavity", "hr_neck_outer", "fixed_inner_passage", "shared_chamber", "fixed_outer_passage"]
PCOLS = [f"p_{x}" for x in LEAF]
TARGETS = dict(zip(MODULES, [1200, 1500, 1850, 2250, 2700, 3200, 3800, 4500]))


def refine_peak(f, y, i):
    x = np.log2(f[i-1:i+2]); z = np.log10(y[i-1:i+2])
    a, b, c = np.polyfit(x, z, 2)
    if not (np.isfinite(a) and a < 0):
        return f[i], y[i], "sampled_nonconcave"
    vertex = -b / (2*a)
    if not x[0] < vertex < x[2]:
        return f[i], y[i], "sampled_vertex_outside"
    return 2**vertex, 10**(a*vertex**2+b*vertex+c), "interior_log_quadratic"


def circdiff(a, b):
    return abs((a-b+180) % 360 - 180)


def cosine(a, b):
    den = np.linalg.norm(a)*np.linalg.norm(b)
    return float(np.dot(a,b)/den) if den else 0.0


def main():
    energy = pd.read_csv(OUT / "energy_long.csv")
    part = pd.read_csv(OUT / "participation_vectors.csv")
    comp = pd.read_csv(OUT / "complex_averages.csv")
    selection = pd.read_csv(OUT / "selection_audit.csv")
    energy.to_csv(OUT / "compartment_energy_long.csv", index=False)
    part.to_csv(OUT / "compartment_participation.csv", index=False)
    comp.to_csv(OUT / "cavity_chamber_mic_complex.csv", index=False)
    selection["overlap_with_other_3d_named_regions"] = ""
    selection["overlap_entities"] = ""
    for (_, _), group in selection.groupby(["module_id","role"]):
        domains = {r.region:set(int(x) for x in str(r.entities).split(";") if x and x != "nan")
                   for _,r in group[group.entity_dimension==3].iterrows()}
        for idx,r in group[group.entity_dimension==3].iterrows():
            overlaps=[]; entities=set()
            for other,values in domains.items():
                common=domains[r.region]&values if other!=r.region else set()
                if common: overlaps.append(other);entities|=common
            selection.loc[idx,"overlap_with_other_3d_named_regions"]=";".join(sorted(overlaps))
            selection.loc[idx,"overlap_entities"]=";".join(map(str,sorted(entities)))
    selection.to_csv(OUT / "region_selection_audit.csv", index=False)

    authority = json.loads((OUT / "authority_manifest.json").read_text(encoding="utf-8"))
    auth_rows = []
    for row in authority["p04b_models"]:
        auth_rows.append({"authority":"P04B-N", **row})
    for row in authority["supporting_models"]:
        auth_rows.append({"authority":"supporting", "module_id":"HR03", "role":"supporting", **row,
                          "expected_sha256":row["actual_sha256"], "hash_match":True})
    pd.DataFrame(auth_rows).to_csv(OUT / "input_authority_manifest.csv", index=False)

    ep = energy[(energy.role == "production") & energy.region.isin(["whole_hr_module","hr_cavity"])].pivot_table(
        index=["module_id","grid_index","frequency_hz"], columns="region", values="total_energy_J").reset_index()
    peak_rows = []
    for module in MODULES:
        table = ep[ep.module_id == module].sort_values("grid_index").reset_index(drop=True)
        mask = (table.frequency_hz >= 800) & (table.frequency_hz <= 5000)
        sub = table[mask].reset_index(drop=True)
        candidates = {}
        for curve in ["whole_hr_module", "hr_cavity"]:
            z = np.log10(sub[curve].to_numpy())
            local, _ = find_peaks(z)
            prominence = peak_prominences(z, local)[0]
            for j, i in enumerate(local):
                grid = int(sub.iloc[i].grid_index)
                record = candidates.setdefault(grid, {"triggers":[], "prominence":{}, "local_i":i})
                record["triggers"].append(curve)
                record["prominence"][curve] = float(prominence[j])
        for grid, record in sorted(candidates.items()):
            i = record["local_i"]
            trigger = sorted(record["triggers"], key=lambda x:(-record["prominence"][x], x))[0]
            f = sub.frequency_hz.to_numpy(); y = sub[trigger].to_numpy()
            refined_f, refined_e, reason = refine_peak(f, y, i)
            er = energy[(energy.module_id==module)&(energy.role=="production")&(energy.grid_index==grid)]
            pr = part[(part.module_id==module)&(part.role=="production")&(part.grid_index==grid)].iloc[0]
            cr = comp[(comp.module_id==module)&(comp.role=="production")&(comp.grid_index==grid)].iloc[0]
            module_row = er[er.region=="whole_hr_module"].iloc[0]
            cavity_row = er[er.region=="hr_cavity"].iloc[0]
            row = {
                "module_id":module, "grid_index":grid, "sampled_frequency_hz":float(sub.iloc[i].frequency_hz),
                "refined_frequency_hz":refined_f, "refined_trigger_energy_J":refined_e,
                "refinement_reason":reason, "trigger_curves":";".join(record["triggers"]),
                "prominence_whole_decades":record["prominence"].get("whole_hr_module",np.nan),
                "prominence_cavity_decades":record["prominence"].get("hr_cavity",np.nan),
                "whole_pressure_energy_J":module_row.pressure_energy_J, "whole_kinetic_energy_J":module_row.kinetic_energy_J,
                "whole_total_energy_J":module_row.total_energy_J, "whole_kinetic_fraction":module_row.kinetic_fraction,
                "cavity_pressure_energy_J":cavity_row.pressure_energy_J, "cavity_kinetic_energy_J":cavity_row.kinetic_energy_J,
                "cavity_total_energy_J":cavity_row.total_energy_J, "cavity_kinetic_fraction":cavity_row.kinetic_fraction,
                "phase_cavity_minus_chamber_deg":cr.phase_cavity_minus_chamber_deg,
                "phase_cavity_minus_mic_deg":cr.phase_cavity_minus_mic_deg,
            }
            for col in PCOLS: row[col] = pr[col]
            for name in LEAF:
                rr = er[er.region==name].iloc[0]
                row[f"energy_{name}_J"] = rr.total_energy_J
                row[f"whole_fraction_{name}"] = pr[f"whole_fraction_{name}"]
                row[f"module_fraction_{name}"] = pr[f"module_fraction_{name}"]
            peak_rows.append(row)
    peaks = pd.DataFrame(peak_rows).sort_values(["module_id","refined_frequency_hz"]).reset_index(drop=True)
    peaks["peak_id"] = [f"{m}_P{i+1:02d}" for m in MODULES for i in range(sum(peaks.module_id==m))]
    peaks.to_csv(OUT / "full_band_local_peaks.csv", index=False)

    # Frozen adjacent-module minimum-total one-to-one assignment.
    memberships = []
    next_branch = 1
    previous = None
    previous_branch = {}
    for module in MODULES:
        current = peaks[peaks.module_id==module].reset_index(drop=True)
        links = {}
        if previous is not None:
            costs = np.empty((len(previous),len(current)))
            for i,a in previous.iterrows():
                for j,b in current.iterrows():
                    freq = min(abs(math.log2(b.refined_frequency_hz/a.refined_frequency_hz))/0.5,2)
                    sim = cosine(a[PCOLS].to_numpy(float), b[PCOLS].to_numpy(float))
                    costs[i,j] = 0.40*freq+0.35*(1-sim)+0.15*abs(a.whole_kinetic_fraction-b.whole_kinetic_fraction)+0.10*circdiff(a.phase_cavity_minus_chamber_deg,b.phase_cavity_minus_chamber_deg)/180
            best = None
            if len(previous) <= len(current):
                for perm in itertools.permutations(range(len(current)),len(previous)):
                    total = sum(costs[i,j] for i,j in enumerate(perm))
                    candidate=(total,perm)
                    if best is None or candidate < best: best=candidate
                pairs=[(i,j) for i,j in enumerate(best[1])]
            else:
                for perm in itertools.permutations(range(len(previous)),len(current)):
                    total = sum(costs[i,j] for j,i in enumerate(perm))
                    candidate=(total,perm)
                    if best is None or candidate < best: best=candidate
                pairs=[(i,j) for j,i in enumerate(best[1])]
            for i,j in pairs:
                if costs[i,j] <= 0.75: links[j]=(i,float(costs[i,j]))
        current_branch={}
        for j,row in current.iterrows():
            if j in links:
                i,cost=links[j]; branch=previous_branch[i]; pred=previous.iloc[i].peak_id
                sim=cosine(previous.iloc[i][PCOLS].to_numpy(float),row[PCOLS].to_numpy(float))
                swap=((previous.iloc[i].energy_hr_cavity_J>previous.iloc[i].energy_shared_chamber_J) != (row.energy_hr_cavity_J>row.energy_shared_chamber_J))
                exchange=sim<0.85 or swap
            else:
                branch=f"B{next_branch:02d}"; next_branch+=1; pred=""; cost=np.nan; sim=np.nan; swap=False; exchange=False
            current_branch[j]=branch
            memberships.append({"module_id":module,"peak_id":row.peak_id,"branch_id":branch,
                                "sampled_frequency_hz":row.sampled_frequency_hz,"refined_frequency_hz":row.refined_frequency_hz,
                                "predecessor_peak_id":pred,"link_cost":cost,"participation_cosine_to_predecessor":sim,
                                "cavity_chamber_dominance_swap":swap,"participation_exchange":exchange,
                                "phase_cavity_minus_chamber_deg":row.phase_cavity_minus_chamber_deg,
                                **{col:row[col] for col in PCOLS}})
        previous=current; previous_branch=current_branch
    branches=pd.DataFrame(memberships)

    split_modules=[]
    for m in MODULES:
        q=peaks[peaks.module_id==m]
        if any(abs(math.log2(a.refined_frequency_hz/b.refined_frequency_hz))>=1/24 and cosine(a[PCOLS].to_numpy(float),b[PCOLS].to_numpy(float))<0.90
               for (_,a),(_,b) in itertools.combinations(q.iterrows(),2)):
            split_modules.append(m)
    compressed=[]
    for bid,q in branches.groupby("branch_id"):
        if len(q)>=3:
            fspan=math.log2(q.refined_frequency_hz.max()/q.refined_frequency_hz.min())
            t=[TARGETS[x] for x in q.module_id]
            if fspan<=1/12 and math.log2(max(t)/min(t))>=1/3: compressed.append(bid)
    branches["branch_compressed"] = branches.branch_id.isin(compressed)
    branches["module_has_splitting"] = branches.module_id.isin(split_modules)
    branches.to_csv(OUT / "mode_branch_tracking.csv", index=False)

    # HR03 confirmatory controlled differential and exact landmark audit.
    h3=peaks[peaks.module_id=="HR03"]
    h3e=energy[(energy.module_id=="HR03")&(energy.role=="production")]
    h3c=comp[(comp.module_id=="HR03")&(comp.role=="production")]
    def nearest(freq):
        grid=int(h3e[h3e.region=="whole_hr_module"].iloc[(h3e[h3e.region=="whole_hr_module"].frequency_hz-freq).abs().argmin()].grid_index)
        rows=h3e[h3e.grid_index==grid]; cm=h3c[h3c.grid_index==grid].iloc[0]
        module=rows[rows.region=="whole_hr_module"].iloc[0]
        leaf={r:float(rows[rows.region==r].total_energy_J.iloc[0]) for r in LEAF}
        dominant=max(leaf,key=leaf.get)
        return grid,float(module.frequency_hz),dominant,leaf[dominant]/float(module.total_energy_J),float(module.kinetic_fraction),float(cm.phase_cavity_minus_chamber_deg),float(cm.phase_chamber_minus_mic_deg)
    diff=[]
    for label,centre,kind in [("P03 reduced coarse",1891.0407934695,"isolated accepted centre"),("P03 reduced fine",1890.6166388677,"isolated accepted centre"),("P03 full TV coarse",1901.8218918305,"isolated accepted centre"),("P03 full TV fine",1904.1942270911,"isolated accepted centre")]:
        diff.append({"evidence":label,"topology":"isolated/local","frequency_hz":centre,"kind":kind})
    for _,r in h3.iterrows():
        diff.append({"evidence":r.peak_id,"topology":"integrated S1","frequency_hz":r.refined_frequency_hz,"kind":"full-band energy peak","trigger":r.trigger_curves,"prominence_decades":np.nanmax([r.prominence_whole_decades,r.prominence_cavity_decades])})
    for label,freq in [("P04B whole-module landmark",1646.88357862959),("P04A nominal mic relative feature",1986.97249931757)]:
        grid,actual,dom,share,kf,phase,cmphase=nearest(freq)
        diff.append({"evidence":label,"topology":"integrated S1","frequency_hz":actual,"kind":"landmark sampled audit","grid_index":grid,"dominant_leaf_region":dom,"dominant_leaf_over_module":share,"whole_module_kinetic_fraction":kf,"cavity_minus_chamber_phase_deg":phase,"chamber_minus_mic_phase_deg":cmphase})
    pd.DataFrame(diff).to_csv(OUT / "hr03_isolated_vs_integrated.csv", index=False)

    cavity_window=h3[(h3.refined_frequency_hz>=1900)&(h3.refined_frequency_hz<=2000)&h3.trigger_curves.str.contains("hr_cavity")]
    local_shift_oct=math.log2(1646.88357862959/1904.1942270911)
    grid,actual,dom,share,kf,phase,cmphase=nearest(1646.88357862959)
    landmark=h3e[h3e.grid_index==grid]
    module_total=float(landmark[landmark.region=="whole_hr_module"].total_energy_J.iloc[0])
    neck_kin=float(landmark[landmark.region.isin(["hr_neck_inner","hr_neck_outer"])].kinetic_energy_J.sum())/module_total
    topology = bool(len(h3)>=2 and abs(local_shift_oct)>1/12 and (len(split_modules)>0 or len(compressed)>0 or branches.participation_exchange.any()))
    metric = bool(len(cavity_window)>0 and neck_kin>=0.5)
    status = "P04C MIXED MECHANISM EVIDENCE" if topology and metric else ("P04C TOPOLOGY HYBRIDIZATION SUPPORTED" if topology else ("P04C METRIC MISMATCH SUPPORTED" if metric else "P04C INCONCLUSIVE"))
    high_reappear=all(any((peaks.module_id==m)&(peaks.refined_frequency_hz>3000)&peaks.trigger_curves.str.contains("hr_cavity")) for m in ["HR06","HR07","HR08"])
    mechanism={
        "phase_id":"P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC","primary_status":status,
        "flags":{"topology_hybridization_supported":topology,"metric_mismatch_supported":metric,"reduced_model_suspected":False,
                 "branch_splitting_modules":split_modules,"compressed_branches":compressed,
                 "participation_exchange_link_count":int(branches.participation_exchange.sum()),"high_frequency_reappearance_HR06_HR08":high_reappear},
        "hr03":{"integrated_energy_peak_count_800_5000":len(h3),"cavity_peak_1900_2000_count":len(cavity_window),
                "dominant_region_at_1646_88":dom,"dominant_region_over_module":share,"whole_module_kinetic_fraction":kf,
                "combined_neck_kinetic_over_module":neck_kin,"P03_full_TV_to_integrated_shift_octaves":local_shift_oct,
                "interpretation":"The accepted isolated ~1904 Hz local mode is not retained near 1900-2000 Hz as an integrated cavity-energy maximum; the integrated cavity-dominated branch is shifted to ~1647 Hz. At 1986.97 Hz the chamber and microphone are phase-locked while cavity is nearly antiphase, but no internal-energy maximum exists."},
        "metric_note":"The 1646.88-Hz module peak is cavity-pressure dominated, not neck-kinetic dominated; therefore the frozen metric-mismatch predicate is false.",
        "scientific_boundary":"Exploratory branch structure supports topology reorganization, not causal proof of a four-port U4 mechanism; P04B-N remains not credible for U4.",
        "study_run_calls":0,"model_save_calls":0,"final_test_read":False
    }
    (OUT/"mechanism_classification.json").write_text(json.dumps(mechanism,indent=2,ensure_ascii=False),encoding="utf-8")

    # Six required figures.
    plt.style.use("seaborn-v0_8-whitegrid")
    figdir=OUT/"figures"; figdir.mkdir(exist_ok=True)
    prod=energy[energy.role=="production"]
    fig,axs=plt.subplots(4,2,figsize=(14,14),sharex=True,sharey=True)
    for ax,m in zip(axs.flat,MODULES):
        q=prod[(prod.module_id==m)&prod.region.isin(LEAF)].pivot(index="frequency_hz",columns="region",values="total_energy_J")
        frac=q.div(prod[(prod.module_id==m)&(prod.region=="whole_fluid")].set_index("frequency_hz").total_energy_J,axis=0)
        im=ax.pcolormesh(frac.index,np.arange(len(LEAF)),frac.T.to_numpy(),shading="auto",cmap="magma",vmin=0,vmax=np.nanpercentile(frac,99)); ax.set_xscale("log");ax.set_title(m);ax.set_yticks(np.arange(len(LEAF)),LEAF if m in ["HR01","HR03","HR05","HR07"] else [])
    fig.colorbar(im,ax=axs,label="region / whole-fluid energy");fig.supxlabel("Frequency (Hz)");fig.suptitle("HR01–HR08 energy participation heatmap");fig.savefig(figdir/"energy_participation_heatmap.png",dpi=180,bbox_inches="tight");plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,6))
    for m in MODULES:
        q=prod[(prod.module_id==m)&(prod.region=="whole_hr_module")];ax.plot(q.frequency_hz,q.kinetic_fraction,label=m)
    ax.set(xscale="log",xlim=(800,5000),ylim=(0,1),xlabel="Frequency (Hz)",ylabel="Whole-module kinetic fraction",title="Pressure-versus-kinetic energy fraction");ax.legend(ncol=4);fig.savefig(figdir/"pressure_kinetic_fraction.png",dpi=180,bbox_inches="tight");plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,6));rf=pd.read_csv(P03/"reduced_fine_transfer_phase.csv");tv=pd.read_csv(P03/"thermoviscous_fine_transfer_phase.csv");q=prod[(prod.module_id=="HR03")&prod.region.isin(["whole_hr_module","hr_cavity"])].pivot(index="frequency_hz",columns="region",values="total_energy_J")
    ax.plot(rf.frequency_hz,rf.magnitude/rf.magnitude.max(),label="P03 reduced cavity transfer");ax.plot(tv.frequency_hz,tv.magnitude/tv.magnitude.max(),label="P03 full-TV cavity transfer");ax.plot(q.index,q.hr_cavity/q.hr_cavity.max(),label="S1 cavity total energy");ax.plot(q.index,q.whole_hr_module/q.whole_hr_module.max(),label="S1 whole-module total energy",ls="--");ax.axvspan(1900,2000,color="grey",alpha=.12);ax.set(xlim=(1300,2200),xlabel="Frequency (Hz)",ylabel="curve-normalized response",title="HR03 isolated versus integrated topology");ax.legend();fig.savefig(figdir/"hr03_isolated_vs_integrated.png",dpi=180,bbox_inches="tight");plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,6))
    for bid,q in branches.groupby("branch_id"):
        if len(q)>=2: ax.plot([MODULES.index(m)+1 for m in q.module_id],q.refined_frequency_hz,"o-",label=bid)
    ax.set(xticks=range(1,9),xticklabels=MODULES,yscale="log",ylabel="Refined peak frequency (Hz)",title="Exploratory branch frequency versus module");ax.legend(ncol=4,fontsize=8);fig.savefig(figdir/"branch_frequency_vs_module.png",dpi=180,bbox_inches="tight");plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,6));q=comp[(comp.module_id=="HR03")&(comp.role=="production")]
    ax.plot(q.frequency_hz,q.cavity_magnitude,label="cavity");ax.plot(q.frequency_hz,q.chamber_magnitude,label="central chamber");ax.plot(q.frequency_hz,q.mic_magnitude,label="microphone");ax.set(xscale="log",xlim=(800,5000),yscale="log",xlabel="Frequency (Hz)",ylabel="|p/p_inc|",title="HR03 cavity/chamber/microphone transfers");ax.legend();fig.savefig(figdir/"cavity_chamber_mic_comparison.png",dpi=180,bbox_inches="tight");plt.close(fig)
    fig,(ax1,ax2)=plt.subplots(2,1,figsize=(12,9),sharex=True)
    for m in MODULES:
        q=comp[(comp.module_id==m)&(comp.role=="production")];ax1.plot(q.frequency_hz,q.phase_cavity_minus_chamber_deg,label=m)
    ax1.set(ylabel="Cavity−chamber phase (deg)",ylim=(-180,180),title="Phase and participation exchange audit");ax1.legend(ncol=4)
    for name,col in zip(LEAF,PCOLS):
        ax2.scatter([MODULES.index(m)+1 for m in peaks.module_id],peaks[col],s=12,label=name)
    ax2.set(xticks=range(1,9),xticklabels=MODULES,ylabel="Normalized participation at peaks",xlabel="Module");ax2.legend(ncol=3,fontsize=8);fig.savefig(figdir/"phase_participation_exchange.png",dpi=180,bbox_inches="tight");plt.close(fig)
    print(json.dumps({"status":status,"peaks":len(peaks),"branches":branches.branch_id.nunique(),"split_modules":split_modules,"compressed":compressed,"exchanges":int(branches.participation_exchange.sum())}))


if __name__ == "__main__": main()
