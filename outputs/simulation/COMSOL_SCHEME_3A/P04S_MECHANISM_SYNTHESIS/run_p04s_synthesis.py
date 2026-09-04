"""P04S evidence-only synthesis. Never imports or calls COMSOL."""

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

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04S_MECHANISM_SYNTHESIS"
sys.path.insert(0, str(OUT))
import p04s_synthesis as calc

F = {
    "HR03 CAD target": 1850.0,
    "HR03 measured S1 centre": 1848.564314995637,
    "isolated reduced fine": 1890.6166388677,
    "isolated full-TV fine": 1904.1942270911,
    "integrated cavity branch": 1650.4014917042427,
    "P04E 75%": 1684.6941903782695,
    "P04E 50%": 1749.3994360554204,
    "P04F 10 mm": 1652.6581442358677,
    "experimental exploratory clue": 1623.272535900038,
    "microphone transfer feature": 1986.97249931757,
}
CAD, MEAS, TV, BASE = F["HR03 CAD target"], F["HR03 measured S1 centre"], F["isolated full-TV fine"], F["integrated cavity branch"]


def write_csv(name: str, data: list[dict]) -> None:
    if not data: raise ValueError(name)
    temp = OUT / (name + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(data[0]), extrasaction="ignore"); w.writeheader(); w.writerows(data)
    os.replace(temp, OUT/name)


def write_json(name: str, value: object) -> None:
    temp=OUT/(name+".tmp"); temp.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8"); os.replace(temp,OUT/name)


def sha(path: Path) -> str:
    d=hashlib.sha256()
    with path.open("rb") as h:
        for b in iter(lambda:h.read(1024*1024),b""): d.update(b)
    return d.hexdigest()


def manifest_audit() -> dict:
    phases={
        "P03":"P03_HR03_RETRY_01", "P04A":"P04A_GLOBAL_CALIBRATION", "P04B":"P04B_NOMINAL_CROSS_MODULE_VALIDATION",
        "P04C":"P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC", "P04D":"P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL",
        "P04D_RETRY_01":"P04D_RETRY_01_COUPLING_SCOPE_FIX", "P04E":"P04E_SINGLE_ENTRY_CHAMBER_ABLATION",
        "P04F":"P04F_SINGLE_ENTRY_INDEPENDENT_DUCT_EXTENSION"}
    result={}
    for phase,directory in phases.items():
        folder=ROOT/"outputs/simulation/COMSOL_SCHEME_3A"/directory; failures=[]; count=0
        for line in (folder/"SHA256SUMS").read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            expected,name=line.split("  ",1); path=ROOT/name if (ROOT/name).exists() else folder/name; count+=1
            if not path.exists() or sha(path)!=expected: failures.append(name)
        result[phase]={"manifest_entries":count,"failures":failures,"passed":not failures}
    return result


def main() -> None:
    audit=manifest_audit(); provenance_complete=all(v["passed"] for v in audit.values())
    if not provenance_complete:
        write_json("scheme_3a_terminal_decision.json",{"classification":"P04S INSUFFICIENT_PROVENANCE","manifest_audit":audit,"final_test_read":False}); return

    evidence=[
        {"phase":"P03","question":"Does isolated HR03 retain its designed local centre with bounded full-TV reference?","execution_status":"PASS; reduced and full-TV solved on two meshes","scientific_classification":"P03 RETRY_01 PASS / as_designed_close","authoritative_inputs":"P02 nominal geometry; measured HR03 centre; P03 RETRY_01 manifest","principal_metric":"full-TV 1904.194 Hz; +3.009% vs measured 1848.564 Hz","supported_inference":"bounded isolated HR03 local centre is close as designed","unsupported_inference":"complete head, U4, amplitude/phase or direction-code validation","authorizes_u4":False,"contributes_scientific_evidence":True,"evidence_type":"local-model validation","provenance_caveat":"single isolated module; uncalibrated; first P03 attempt was technical BLOCKED"},
        {"phase":"P04A","question":"Can one global effective length/loss pair be identified from S1?","execution_status":"SUCCESSFUL NUMERICAL SEARCH","scientific_classification":"P04A INADEQUATE","authoritative_inputs":"P04A0 contract; P05/HR03 selected repeats","principal_metric":"best at +0.2 mm and 2.0, both upper bounds; bootstrap boundary mass 1.0","supported_inference":"the frozen two-parameter calibration is non-identifiable","unsupported_inference":"simulation calibrated to experiment or transferable fitted parameters","authorizes_u4":False,"contributes_scientific_evidence":True,"evidence_type":"credibility/identifiability negative result","provenance_caveat":"descriptive best models are not frozen authorities"},
        {"phase":"P04B","question":"Is the nominal cross-module S1 model credible enough to enter U4?","execution_status":"ALL REQUIRED MODELS SOLVED","scientific_classification":"P04B-N MODEL NOT CREDIBLE FOR U4","authoritative_inputs":"nominal as-designed authority; no P04A fitted parameters","principal_metric":"HR02–HR05 maxima at target-window boundaries; stable-module and mesh gates fail","supported_inference":"nominal model lacks frozen centre-level U4 credibility","unsupported_inference":"complete U4 prediction or promotion of boundary maxima to centres","authorizes_u4":False,"contributes_scientific_evidence":True,"evidence_type":"model-credibility negative result","provenance_caveat":"solver success is distinct from model credibility"},
        {"phase":"P04C","question":"Why does integrated HR03 differ from isolated HR03?","execution_status":"SUCCESSFUL SAVED-SOLUTION DIAGNOSTIC; no solve","scientific_classification":"P04C TOPOLOGY HYBRIDIZATION SUPPORTED","authoritative_inputs":"P03/P04A/P04B saved formal results","principal_metric":"1904.194→1650.401 Hz; −0.209 octave; cavity/module ≈59.37%; near-antiphase","supported_inference":"shared receiving topology reorganizes local modes into hybrid branches","unsupported_inference":"unique component causal percentage or full-U4 direction mechanism","authorizes_u4":False,"contributes_scientific_evidence":True,"evidence_type":"mechanism evidence","provenance_caveat":"overlapping selections are descriptive; broad branches exploratory"},
        {"phase":"P04D","question":"Does a full-TV HR03-in-S1 control confirm the P04C mechanism?","execution_status":"P04D and RETRY_01 equation assembly failed; no formal band solution","scientific_classification":"NO SCIENTIFIC CLASSIFICATION — technical BLOCKED_BY_SOLVER","authoritative_inputs":"P04B HR03 authority; frozen original/repair contracts","principal_metric":"0 completed formal frequency points","supported_inference":"current PA–TV coupling toolchain cannot execute this control","unsupported_inference":"any acoustic confirmation or refutation of P04C","authorizes_u4":False,"contributes_scientific_evidence":False,"evidence_type":"technical failure provenance","provenance_caveat":"must not be treated as an acoustic negative result"},
        {"phase":"P04E","question":"Does central-chamber volume control the reorganized branch?","execution_status":"VALID GEOMETRY/MESH/SOLVE/RELOAD FOR 100/75/50%","scientific_classification":"P04E PARTIAL RESTORATION","authoritative_inputs":"P04B HR03 nominal authority; frozen P04E contract","principal_metric":"1651.415→1684.694→1749.399 Hz; +0.083157 octave at 50%","supported_inference":"within the nominal model, chamber-volume intervention systematically shifts the hybrid branch","unsupported_inference":"direction-code restoration, physical insert validation or complete decoupling","authorizes_u4":False,"contributes_scientific_evidence":True,"evidence_type":"virtual causal intervention","provenance_caveat":"single screening mesh/state; 50% has 0.0317 mm gap and 731,519 elements"},
        {"phase":"P04F","question":"Do 5–10 mm independent short ducts recover module independence?","execution_status":"VALID GEOMETRY/MESH/SOLVE/RELOAD; one solve per 5/10 mm","scientific_classification":"P04F NO_USEFUL_IMPROVEMENT","authoritative_inputs":"saved P04E 100% MPH/results; P04F frozen contract","principal_metric":"10 mm shift +0.001085 octave; chamber participation 0.064232→0.080409","supported_inference":"5–10 mm inward extension is ineffective for modal recovery in this model","unsupported_inference":"all longer ducts or all impedance-isolation concepts are ineffective","authorizes_u4":False,"contributes_scientific_evidence":True,"evidence_type":"virtual design-intervention negative result","provenance_caveat":"earlier P04F was PRESTART BLOCKED_BY_MCP and is non-scientific"},
    ]
    write_csv("phase_evidence_matrix.csv",evidence)

    uncertainty={
        "HR03 CAD target":"design nominal, not measured", "HR03 measured S1 centre":"single campaign; fixed 48-PPo grid and repeat bootstrap",
        "isolated reduced fine":"reduced BLI approximation; mesh-converged centre", "isolated full-TV fine":"bounded isolated geometry and one material model",
        "integrated cavity branch":"nominal reduced model; internal-energy observable; branch continuity assumption", "P04E 75%":"nominal virtual intervention; one screening mesh",
        "P04E 50%":"0.0317 mm clearance and 731,519-element sensitivity", "P04F 10 mm":"nominal virtual intervention; one screening mesh",
        "experimental exploratory clue":"post-hoc, non-independent frequency bins, not confirmatory", "microphone transfer feature":"microphone observable, not an internal-energy peak"}
    corr=[]
    for name,hz in F.items():
        corr.append({"feature":name,"frequency_hz":hz,"delta_vs_cad_hz":hz-CAD,"delta_vs_cad_percent":calc.signed_percent(hz,CAD),"delta_vs_cad_octaves":calc.octave_delta(hz,CAD),
                     "delta_vs_measured_hz":hz-MEAS,"delta_vs_measured_percent":calc.signed_percent(hz,MEAS),"delta_vs_measured_octaves":calc.octave_delta(hz,MEAS),
                     "delta_vs_full_tv_hz":hz-TV,"delta_vs_full_tv_percent":calc.signed_percent(hz,TV),"delta_vs_full_tv_octaves":calc.octave_delta(hz,TV),
                     "delta_vs_common_0mm_hz":hz-BASE,"delta_vs_common_0mm_percent":calc.signed_percent(hz,BASE),"delta_vs_common_0mm_octaves":calc.octave_delta(hz,BASE),
                     "observable":"experiment microphone spectrum" if "measured" in name or "experimental" in name else "simulation microphone transfer" if "transfer" in name else "simulation internal energy" if name not in {"HR03 CAD target"} else "design nominal",
                     "uncertainty_source":uncertainty[name]})
    write_csv("frequency_correspondence.csv",corr)

    p04e_shift=0.0831567706074453; p04f_shift=0.0010853677679508425; ratio=calc.effect_ratio(p04e_shift,p04f_shift)
    interventions=[
        {"intervention":"P04E 75% chamber","changed_variable":"retained common-chamber air volume 100%→75%","frequency_restoration_hz":1684.6941903782695-1651.4152846806917,"frequency_restoration_octaves":0.028783770539598883,"chamber_participation":"0.064232→0.094929 (increases)","mic_transfer":"fixed 1646.884 Hz: −2.931 dB magnitude; fixed 1986.972 Hz: +3.027 dB magnitude","q_change":"not frozen as a primary P04E output","engineering_sensitivity":"31,457 elements; minimum quality 0.1376; 5.423 mm lateral clearance","interpretation":"systematic but partial branch motion; compliance/volume-sensitive hybridization, not decoupling"},
        {"intervention":"P04E 50% chamber","changed_variable":"retained common-chamber air volume 100%→50%","frequency_restoration_hz":1749.3994360554204-1651.4152846806917,"frequency_restoration_octaves":p04e_shift,"chamber_participation":"0.064232→0.105034 (increases)","mic_transfer":"tracked-peak magnitude 5.072→6.671; strong frequency redistribution","q_change":"not frozen as a primary P04E output","engineering_sensitivity":"731,519 elements; 0.0317 mm clearance; unsuitable print candidate","interpretation":"near-threshold partial restoration with extreme geometric/numerical sensitivity"},
        {"intervention":"P04F 5 mm ducts","changed_variable":"independent sidewall extension 0→5 mm; mixing radius 17→12 mm","frequency_restoration_hz":1651.2216289964852-1651.4152846806917,"frequency_restoration_octaves":-0.00016918971286731431,"chamber_participation":"0.064232→0.071767 (increases)","mic_transfer":"tracked-peak +0.206 dB","q_change":"38.204→37.639","engineering_sensitivity":"41,092 elements; minimum clearance 8.149 mm","interpretation":"no useful recovery"},
        {"intervention":"P04F 10 mm ducts","changed_variable":"independent sidewall extension 0→10 mm; mixing radius 17→7 mm","frequency_restoration_hz":1652.6581442358677-1651.4152846806917,"frequency_restoration_octaves":p04f_shift,"chamber_participation":"0.064232→0.080409 (+25.18%)","mic_transfer":"tracked-peak +0.304 dB","q_change":"38.204→35.069 (−8.21%)","engineering_sensitivity":"41,621 elements; minimum clearance 2.546 mm","interpretation":"short separation does not supply effective modal/impedance isolation"},
    ]
    write_csv("intervention_comparison.csv",interventions)

    claims=[
        (1,"HR module local frequency centres can be controlled morphologically","supported","S1 preserves design order; maximum absolute centre error ≈3.08%"),
        (2,"All HR modules form stable orthogonal spectral barcodes","not_supported","only HR03/HR04/HR07 pass the stable-signature gate; correlations remain broad"),
        (3,"The complete device exhibits direction-related spectral change above same-run repeat error","supported_with_limits","U4SYM 1.049 dB and U4HR 1.697 dB exceed technical floors; single campaign only"),
        (4,"The HR array increases overall direction-spectrum difference in this campaign","supported_with_limits","U4HR−U4SYM ≈0.648 dB; no independent reassembly and configuration-order confounding remains"),
        (5,"The HR array achieved the planned four-direction frequency decoding","not_supported","U4HR diagonal score −0.239 dB; expected top-1 0/4 and top-2 1/4"),
        (6,"Shared topology reorganizes the local HR mode","supported_with_limits","P04C nominal internal-energy evidence supports hybridization; P04D full-TV control was technically blocked"),
        (7,"Common-chamber volume is an important control variable for the reorganized branch","supported_with_limits","P04E virtual intervention moves the tracked branch monotonically; no physical insert validation"),
        (8,"A 5–10 mm independent short duct is sufficient to isolate four modules","not_supported","P04F shift only 0.001085 octave and is not monotonic"),
        (9,"P04E restored direction encoding","not_supported","P04E is single-entry nominal mechanism screening, not a direction-code test"),
        (10,"The current model can predict complete U4","not_supported","P04B-N explicitly fails U4 credibility gates"),
        (11,"The 1623 Hz experimental clue is mechanism-consistent with the ≈1650 Hz simulated branch","exploratory","distance 27.129 Hz / 1.671% / 0.02391 octave; not independent validation or causal naming"),
        (12,"A single module's causal contribution to a direction can be identified","not_supported","correlation and overlapping/shared responses do not identify causal contribution rates"),
        (13,"The study supports an experimental-diagnosis + simulation-mechanism + design-rule contribution","supported_with_limits","experimental frequency control/code failure plus nominal interventions support a bounded thesis contribution"),
    ]
    claim_rows=[{"claim_id":i,"candidate_claim":c,"eligibility":s,"evidence":e,"required_wording_boundary":"Do not upgrade association/nominal intervention to full-U4 or physical validation"} for i,c,s,e in claims]
    write_csv("claim_eligibility_matrix.csv",claim_rows)

    # Print decision: the existing 75% state supplies fixed microphone observables.
    # A later one-piece CAD must use a carrier outside the modeled acoustic height;
    # this is a concept constraint, not a geometry generated in P04S.
    gates=[
        (1,True,"75% has 31,457 elements, quality 0.1376 and 5.423 mm clearance; unlike 50%, no mesh explosion or extreme slit"),
        (2,True,"conceptually one removable carrier-backed insert can occupy the frozen diagonal complements without reprinting body/HR03/mic support; detailed CAD remains separately authorized"),
        (3,True,"frozen cross retains every 8×9.2 mm channel and the Ø9 mm microphone well"),
        (4,True,"fixed microphone predictions exist at 1646.8836 and 1986.9725 Hz, in addition to the internal branch"),
        (5,True,"predicted fixed-frequency magnitude changes are about 2.93 and 3.03 dB, above HR03 same-campaign local p95 ≈1.396 dB; 33.28 Hz branch motion exceeds one 48-PPo bin near 1.65 kHz"),
        (6,True,"freeze primary 1646.8836-Hz baseline/insert mic magnitude and secondary 1986.9725-Hz magnitude before measurement; do not re-pick peaks"),
        (7,True,"requires only original baseline, one 75% insert, HR03 single entry and one paired/interleaved repeat block"),
        (8,True,"tests whether the chamber modification produces the predicted spectrum change; it is not a direction-identification experiment"),
    ]
    decision=calc.print_decision([g[1] for g in gates],provenance_complete)
    write_csv("print_candidate_gate.csv",[{"gate":i,"passed":p,"evidence":e,"scope":"concept decision only; no STL or acquisition matrix"} for i,p,e in gates])

    contribution={
        "phase_id":"P04S_MECHANISM_SYNTHESIS", "strongest_conclusion":"Single-entry module centres are morphologically controllable, but shared receiving topology reorganizes local modes; common-chamber volume shifts the hybrid branch whereas <0.05-wavelength short duct extensions do not restore independence.",
        "evidence_layers":{"experiment":"frequency control, direction-spectrum change, and planned diagonal-code failure","nominal_simulation":"topology hybridization and controlled P04E/P04F virtual interventions","not_yet_validated":"new insert, complete U4 prediction, direction decoding, single-module causal rates"},
        "key_derived":{"p04e_50_shift_over_p04f_10_shift_ratio":ratio,"p04f_10_chamber_participation_relative_change_percent":calc.signed_percent(0.08040936174302188,0.0642321726917877),"p04f_10_q_relative_change_percent":calc.signed_percent(35.06912471557195,38.203922987330834),"p04f_5_length_over_wavelength_at_1650":calc.length_over_wavelength(5,1650),"p04f_10_length_over_wavelength_at_1650":calc.length_over_wavelength(10,1650),"exploratory_1623_vs_simulated_1650":{"hz":BASE-F["experimental exploratory clue"],"percent":calc.signed_percent(BASE,F["experimental exploratory clue"]),"octaves":calc.octave_delta(BASE,F["experimental exploratory clue"]) }},
        "design_rule":"Future designs should control shared-chamber acoustic compliance or introduce materially stronger impedance isolation; independent local tuning or 5–10 mm geometric separation alone is insufficient.",
        "print_decision":decision,"manifest_audit":audit,"final_test_read":False}
    write_json("paper_contribution_summary.json",contribution)
    terminal={"classification":f"P04S COMPLETE — {decision}","scheme_3a_search_status":"CLOSED_PENDING_USER_ACCEPTANCE","print_scope":"one P04E 75% mechanism insert concept only; no STL and no acquisition matrix","new_comsol_required_for_decision":False,"p04d_treatment":"technical failure provenance only","p04f_prestart_status":"P04F PRESTART BLOCKED_BY_MCP; non-scientific and no attempt consumed","p04f_formal_status":"P04F NO_USEFUL_IMPROVEMENT","manifest_audit":audit,"final_test_read":False,"prohibitions_observed":["no COMSOL call","no MPH read/write","no new geometry parameter","no STL","no data collection","no P05/P06/U4/external field","no commit/push/tag/release"]}
    write_json("scheme_3a_terminal_decision.json",terminal)

    outline=f"""# P04S paper-ready results outline

## 1. Research question

Whether frequency-tuned HR modules preserve interpretable, direction-linked signatures after connection to a shared receiver topology, and which minimal geometric variable governs any loss of independence.

## 2. V2.5 single-entry frequency control

HR01–HR08 measured centres preserve design order with a maximum absolute error of about 3.08%. Only HR03, HR04 and HR07 satisfy the current stable-signature gate, so centre control is supported but eight orthogonal spectral barcodes are not.

## 3. Complete-device direction spectra and code failure

Within this campaign, U4SYM and U4HR direction effects are 1.049 and 1.697 dB. U4HR adds about 0.648 dB, but the planned U4HR diagonal code fails (−0.239 dB; top-1 0/4; top-2 1/4). This is direction-related spectral structure, not validated four-direction decoding.

## 4. Isolated HR03 model

The isolated full-TV centre is 1904.194 Hz, +3.009% from the measured 1848.564 Hz centre. This supports bounded local frequency behaviour only.

## 5. Assembled nominal credibility boundary

P04A yields no identifiable calibration. P04B executes numerically but is not credible for U4 because HR02–HR05 centres are boundary maxima. No global calibration or complete-U4 prediction is claimed.

## 6. Shared-topology hybridization

P04C locates the integrated cavity-dominated branch near 1650.401 Hz, about −0.209 octave from isolated full-TV HR03. Cavity/module energy is about 59.37%, combined neck kinetic participation about 36.15%, and cavity/chamber phase is near antiphase. The 1986.972-Hz microphone feature is an observation-transfer feature, not the internal-energy peak. P04D/P04D RETRY_01 are technical solver failures and supply no acoustic result.

## 7. Controlled interventions

P04E chamber reduction moves the branch 1651.415→1684.694→1749.399 Hz; 100→50% gives 0.083157 octave. P04F 0→10 mm gives only 0.001085 octave, about {ratio:.2f} times smaller, and chamber participation rises. At 1650 Hz, 5/10 mm are only {calc.length_over_wavelength(5,1650):.4f}/{calc.length_over_wavelength(10,1650):.4f} wavelength. The contrast supports common-chamber compliance as an important model-internal control and rejects these short extensions as sufficient isolation.

## 8. Design rule

Control shared-chamber acoustic compliance or introduce stronger impedance isolation. Do not rely only on isolated-module tuning or <0.05-wavelength geometric separation.

## 9. Unresolved direction encoding

The model does not authorize U4 prediction, P04E/P04F have no physical validation, and neither correlations nor compartment signatures identify single-module directional causal rates. The 1623.273-Hz experimental clue is only an exploratory mechanism correspondence to the ≈1650-Hz branch.

## 10. Print decision

`{decision}`. The later experiment, if separately authorized, tests a fixed-frequency microphone response to one 75% central-chamber insert; it is not a direction-identification validation. No STL or acquisition matrix is produced in P04S.

## 11. Minimal future action

Fabricate only the frozen 75% mechanism insert concept, pre-register 1646.8836 Hz as the primary microphone comparison and 1986.9725 Hz as secondary, and use a paired/interleaved baseline-versus-insert repeat block. No new COMSOL solve is required before that decision.

## Thesis-ready synthesis statement

Single-entry module frequency centres can be controlled morphologically, but after connection to the shared receiving topology the local mode hybridizes with the central chamber and fixed passages. Central-chamber volume intervention systematically moves this hybrid branch, whereas short duct extensions below about 0.05 wavelength do not restore module independence. This combines experiment-supported frequency control and encoding failure with nominal-simulation mechanism interpretation and unvalidated design guidance.
"""
    (OUT/"paper_ready_results_outline.md").write_text(outline,encoding="utf-8")

    # Figures: schematic evidence graphics only, never COMSOL fields.
    plt.rcParams.update({"font.size":9})
    fig,ax=plt.subplots(figsize=(11,3.4)); ax.axis("off")
    nodes=[("S1","centre control"),("S2/S3","direction change\ncode failure"),("P03","isolated HR03"),("P04B/C","credibility limit\nhybridization"),("P04E/F","virtual interventions"),("Rule","compliance or\nstrong isolation")]
    xs=np.linspace(.07,.93,len(nodes))
    for i,((title,sub),x) in enumerate(zip(nodes,xs)):
        ax.text(x,.55,f"{title}\n{sub}",ha="center",va="center",bbox=dict(boxstyle="round,pad=.5",fc="#e8f1f8" if i<2 else "#f6eadf",ec="#345"),transform=ax.transAxes)
        if i<len(nodes)-1: ax.annotate("",xy=(xs[i+1]-.07,.55),xytext=(x+.07,.55),xycoords=ax.transAxes,arrowprops=dict(arrowstyle="->",lw=1.5))
    ax.text(.5,.12,"Experimental evidence → bounded nominal mechanism → design rule (no full-U4 validation)",ha="center",transform=ax.transAxes)
    fig.tight_layout(); fig.savefig(OUT/"evidence_chain.png",dpi=220); fig.savefig(OUT/"evidence_chain.svg"); plt.close(fig)

    fig,ax=plt.subplots(figsize=(10,5)); names=list(F); vals=[F[n] for n in names]; y=np.arange(len(names)); colors=["#555" if i<4 else "#4c78a8" if "P04E" in n else "#f58518" if "P04F" in n else "#999" for i,n in enumerate(names)]
    ax.scatter(vals,y,c=colors,s=55); ax.axvline(TV,ls="--",color="#333",label="isolated full-TV"); ax.axvline(BASE,ls=":",color="#4c78a8",label="integrated branch"); ax.set_yticks(y,names); ax.set_xlabel("Frequency (Hz)"); ax.invert_yaxis(); ax.legend(); fig.tight_layout(); fig.savefig(OUT/"frequency_evolution.png",dpi=220); fig.savefig(OUT/"frequency_evolution.svg"); plt.close(fig)

    fig,ax=plt.subplots(figsize=(8,4.8)); labels=["E75","E50","F5","F10"]; shifts=[.02878377,.08315677,-.00016919,.00108537]; parts=[.094929,.105034,.071767,.080409]; x=np.arange(4); bars=ax.bar(x,shifts,color=["#4c78a8","#4c78a8","#f58518","#f58518"]); ax.axhline(1/12,ls="--",color="#333",label="1/12 octave"); ax.set_xticks(x,labels); ax.set_ylabel("Shift from common 0 mm baseline (octave)"); ax2=ax.twinx(); ax2.plot(x,parts,color="#54a24b",marker="o",label="chamber participation"); ax2.set_ylabel("Chamber / whole-fluid participation"); ax.legend(loc="upper left"); ax2.legend(loc="upper right"); fig.tight_layout(); fig.savefig(OUT/"p04e_vs_p04f_intervention.png",dpi=220); fig.savefig(OUT/"p04e_vs_p04f_intervention.svg"); plt.close(fig)

    status_order=["supported","supported_with_limits","exploratory","not_supported"]; counts=[sum(s==k for _,_,s,_ in claims) for k in status_order]
    fig,ax=plt.subplots(figsize=(8,4)); ax.bar(status_order,counts,color=["#54a24b","#4c78a8","#f2cf5b","#e45756"]); ax.set_ylabel("Candidate claims"); ax.set_title("Thesis claim eligibility boundary"); fig.tight_layout(); fig.savefig(OUT/"claim_boundary.png",dpi=220); fig.savefig(OUT/"claim_boundary.svg"); plt.close(fig)

    fig,axs=plt.subplots(1,2,figsize=(10,4.5))
    for ax,title in zip(axs,["Central-chamber intervention","Short-duct intervention"]):
        ax.add_patch(plt.Circle((0,0),18,fill=False,lw=2,color="#333")); ax.add_patch(plt.Circle((0,0),4.5,fill=False,color="#777")); ax.set(xlim=(-20,20),ylim=(-20,20),aspect="equal",title=title); ax.axis("off")
    for ax in axs:
        ax.plot([-18,18],[0,0],color="#4c78a8",lw=5); ax.plot([0,0],[-18,18],color="#4c78a8",lw=5)
    for angle in (45,135,225,315):
        t=np.deg2rad(angle); axs[0].text(12*np.cos(t),12*np.sin(t),"reduced\nair",ha="center",va="center",color="#e45756",fontsize=8)
    for s in (-1,1):
        axs[1].plot([7,17],[s*4.6,s*4.6],color="#e45756",lw=2)
        axs[1].plot([-17,-7],[s*4.6,s*4.6],color="#e45756",lw=2)
        axs[1].plot([s*4.6,s*4.6],[7,17],color="#e45756",lw=2)
        axs[1].plot([s*4.6,s*4.6],[-17,-7],color="#e45756",lw=2)
    fig.text(.5,.02,"Conceptual mechanism schematic — geometry roles only; not a COMSOL pressure field",ha="center"); fig.tight_layout(rect=(0,.05,1,1)); fig.savefig(OUT/"mechanism_intervention_schematic.png",dpi=220); fig.savefig(OUT/"mechanism_intervention_schematic.svg"); plt.close(fig)

    report=f"""# P04S — Scheme 3A mechanism synthesis and minimum print decision

## Terminal classification

`P04S COMPLETE — {decision}`

All required P03–P04F manifests passed. P04D and RETRY_01 remain technical solver failures, not acoustic negative results. The earlier P04F connection failure remains `P04F PRESTART BLOCKED_BY_MCP`; the formal result remains `P04F NO_USEFUL_IMPROVEMENT`.

## Strongest thesis conclusion

Single-entry HR centre frequencies are morphologically controllable, but the shared receiving topology reorganizes local modes. In the nominal model, common-chamber volume systematically moves the hybrid branch, while 5–10 mm (<0.05 wavelength near 1650 Hz) duct extensions do not restore independence. This supports an “experimental diagnosis + nominal-simulation mechanism + bounded design rule” contribution, not complete-U4 validation.

## Experimental–simulation continuity

The exploratory 1623.273-Hz experimental clue is 27.129 Hz (1.671%, 0.02391 octave) below the simulated 1650.401-Hz internal branch. This is mechanism-consistent proximity only. It is not independent validation and does not rename 1623 Hz as an HR03 causal contribution. Internal-energy branches and microphone features are different observables.

## P04E versus P04F

P04E 100→50% shifts the tracked branch 0.083157 octave, {ratio:.2f} times the P04F 0→10 mm effect. P04F chamber participation rises 25.18%, Q falls 8.21%, and mic transfer rises 0.304 dB without useful frequency recovery. The controlled contrast implicates common-chamber compliance/volume as important within the nominal model; it does not prove physical causality before insert testing.

## Print decision

The 75% state avoids the 50% state's extreme slit and mesh explosion, retains the four fixed channels and microphone well, and predicts fixed microphone changes of about 2.93 dB at 1646.8836 Hz and 3.03 dB at 1986.9725 Hz. These exceed the HR03 same-campaign local p95 of about 1.396 dB. A later single removable carrier-backed insert is therefore worth one minimal paired mechanism test, subject to separate CAD authorization. It must test central-chamber spectral change, not direction recognition.

No new COMSOL solve is needed for this decision. P04S generated no geometry, MPH, STL or acquisition matrix.

## Boundaries

P04A is not a calibration; P04B does not authorize U4; P04E/P04F are not physically validated; H1 and reliable four-direction classification remain unconfirmed; single-module directional causal fractions remain unidentified. `final_test_read=false`.
"""
    (OUT/"REPORT_DRAFT.md").write_text(report,encoding="utf-8")

    files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in {"SHA256SUMS","artifact_inventory.csv"} and not p.name.endswith(".tmp"))
    inventory=[{"file":p.name,"bytes":p.stat().st_size,"sha256":sha(p)} for p in files]
    report_path=ROOT/"docs/progress/COMSOL_3A_P04S_MECHANISM_SYNTHESIS_AND_PRINT_DECISION.md"
    if report_path.exists():
        inventory.append({"file":"docs/progress/COMSOL_3A_P04S_MECHANISM_SYNTHESIS_AND_PRINT_DECISION.md","bytes":report_path.stat().st_size,"sha256":sha(report_path)})
    write_csv("artifact_inventory.csv",inventory)
    files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name!="SHA256SUMS" and not p.name.endswith(".tmp"))
    manifest="".join(f"{sha(p)}  {p.name}\n" for p in files)
    if report_path.exists(): manifest += f"{sha(report_path)}  docs/progress/COMSOL_3A_P04S_MECHANISM_SYNTHESIS_AND_PRINT_DECISION.md\n"
    (OUT/"SHA256SUMS").write_text(manifest,encoding="utf-8")
    print(json.dumps(terminal,indent=2,ensure_ascii=False))


if __name__=="__main__": main()
