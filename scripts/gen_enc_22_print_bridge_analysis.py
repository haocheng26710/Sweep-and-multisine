"""Frozen representative-point gates for GEN-ENC-22 PRINT-BRIDGE-A."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/"outputs/gen_enc/GEN_ENC_22_PRINT_BRIDGE_A"
F=np.arange(820.,1080.1,2.); SPAN=201.; TEMPLATE_Q=12.; THRESHOLD=5.731630586148788

def read_case(label,size):
    rows=[]
    for source in range(4):
        path=ROOT/f"{label}_size{size}_src{source}.txt"
        lines=[x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("%")]
        if len(lines)!=1:raise RuntimeError(f"BAD_EXPORT:{path.name}")
        values=np.asarray([complex(x.replace("i","j")) for x in lines[0].split()[3:]])
        if len(values)!=len(F) or not np.isfinite(values).all():raise RuntimeError(f"BAD_VALUES:{path.name}")
        rows.append(values)
    return np.stack(rows)

def marker(values):
    db=np.mean(20*np.log10(np.maximum(np.abs(values),1e-30)),axis=0);best=(-1.,float("nan"))
    for center in np.arange(920.,980.01,2.):
        mask=np.abs(F-center)<=SPAN/2;ff=F[mask];yy=db[mask];x=(ff-center)/(SPAN/2)
        lorentz=1/(1+(2*TEMPLATE_Q*(ff-center)/center)**2)
        amp=float(np.linalg.lstsq(np.column_stack((np.ones_like(x),x,-lorentz)),yy,rcond=None)[0][-1])
        if amp>best[0]:best=(amp,center)
    return {"tracked_hz":best[1],"fitted_depth_db":max(0.,best[0])}

def representative():
    specs=[("EQ3D_A05",4),("TRUE3D_CONTROL",4),("PRINT3D_A05_BULK",4),("PRINT3D_A05_NRA",4)]
    cases={label:{**marker(read_case(label,size)),"mesh_size":size} for label,size in specs}
    for case in cases.values():case["at_search_boundary"]=bool(case["tracked_hz"] in (920.,980.))
    control=cases["TRUE3D_CONTROL"]["fitted_depth_db"]
    eq=cases["EQ3D_A05"];bulk=cases["PRINT3D_A05_BULK"];nra=cases["PRINT3D_A05_NRA"]
    gates={
      "equivalent_3d_frequency":abs(eq["tracked_hz"]-952)<=20,
      "equivalent_3d_visible":eq["fitted_depth_db"]>=THRESHOLD,
      "print_bulk_frequency":abs(bulk["tracked_hz"]-950)<=30 and not bulk["at_search_boundary"],
      "print_bulk_visible_over_control":bulk["fitted_depth_db"]>=THRESHOLD and bulk["fitted_depth_db"]-control>=2,
      "print_nra_frequency":abs(nra["tracked_hz"]-950)<=30 and not nra["at_search_boundary"],
      "print_nra_visible_over_control":nra["fitted_depth_db"]>=THRESHOLD and nra["fitted_depth_db"]-control>=2,
      "nra_shift_from_bulk":abs(nra["tracked_hz"]-bulk["tracked_hz"])<=20,
    }
    gates={key:bool(value) for key,value in gates.items()}
    passed=all(gates.values())
    result={"state":"PRINT_BRIDGE_FINE_AUTHORIZED" if passed else "PRINT_BRIDGE_REPRESENTATIVE_FAIL_STOP",
            "cases":cases,"control_depth_db":control,"gates":gates,"pass":bool(passed)}
    (ROOT/"representative_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))

def fine():
    coarse=read_case("PRINT3D_A05_NRA",4);fine_values=read_case("PRINT3D_A05_NRA_FINE",3)
    cm,fm=marker(coarse),marker(fine_values)
    mesh={"complex_relative_l2":float(np.linalg.norm(coarse-fine_values)/np.linalg.norm(coarse)),
          "frequency_shift_hz":fm["tracked_hz"]-cm["tracked_hz"],
          "depth_shift_db":fm["fitted_depth_db"]-cm["fitted_depth_db"],"coarse_marker":cm,"fine_marker":fm}
    passed=mesh["complex_relative_l2"]<=.03 and abs(mesh["frequency_shift_hz"])<=10 and abs(mesh["depth_shift_db"])<=1.5
    result={"state":"PRINT_BRIDGE_REPRESENTATIVE_PASS" if passed else "PRINT_BRIDGE_MESH_FAIL_STOP","mesh":mesh,"pass":bool(passed)}
    (ROOT/"fine_result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))

def diagnostic():
    control=read_case("TRUE3D_CONTROL",4)
    output={};curves={}
    for label in ("PRINT3D_A05_BULK","PRINT3D_A05_NRA"):
        values=read_case(label,4)
        relative=np.mean(20*np.log10(np.maximum(np.abs(values/control),1e-30)),axis=0)
        curves[label]=relative
        index=int(np.argmin(relative))
        output[label]={"raw_relative_min_hz":float(F[index]),"raw_relative_depth_db":float(-relative[index]),
                       "minimum_at_sweep_edge":bool(index in (0,len(F)-1)),
                       "relative_db_at_820":float(relative[0]),"relative_db_at_920":float(relative[np.where(F==920)[0][0]]),
                       "relative_db_at_950":float(relative[np.where(F==950)[0][0]])}
    result={"state":"POST_GATE_READ_ONLY_DIAGNOSTIC","no_gate_change":True,"cases":output}
    (ROOT/"post_gate_diagnostic.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7.4,4.2),constrained_layout=True)
    colors={"PRINT3D_A05_BULK":"#1565c0","PRINT3D_A05_NRA":"#d32f2f"}
    names={"PRINT3D_A05_BULK":"Printable 3D, bulk loss","PRINT3D_A05_NRA":"Printable 3D, neck boundary-layer loss"}
    for label,relative in curves.items():
        ax.plot(F,relative,color=colors[label],label=names[label])
        hz=output[label]["raw_relative_min_hz"];depth=output[label]["raw_relative_depth_db"]
        ax.scatter([hz],[-depth],color=colors[label],s=38,zorder=3)
        ax.annotate(f"{hz:.0f} Hz",(hz,-depth),xytext=(5,-14),textcoords="offset points",color=colors[label])
    ax.axvline(950,color="0.3",ls="--",lw=1,label="950 Hz target")
    ax.axhline(0,color="0.5",lw=.8)
    ax.set(xlabel="Frequency (Hz)",ylabel="Mean level relative to true-3D control (dB)",title="PRINT-BRIDGE-A representative-point diagnostic")
    ax.grid(alpha=.25);ax.legend(frameon=False,fontsize=8)
    fig.savefig(ROOT/"print_bridge_representative_diagnostic.png",dpi=220);plt.close(fig)
    print(json.dumps(result,indent=2))

def audit():
    specs=[("EQ3D_A05",4),("TRUE3D_CONTROL",4),("PRINT3D_A05_BULK",4),("PRINT3D_A05_NRA",4)]
    models=[]
    for label,size in specs:
        values=read_case(label,size);mph=ROOT/f"{label}_size{size}.mph"
        if not mph.is_file() or mph.stat().st_size==0:raise RuntimeError(f"BAD_MPH:{mph.name}")
        models.append({"label":label,"shape":list(values.shape),"finite":bool(np.isfinite(values).all()),"mph_bytes":mph.stat().st_size})
    logs=["representative_attempt01_comsol.log","nra_retry_comsol.log"]
    for name in logs:
        if not (ROOT/name).is_file() or (ROOT/name).stat().st_size==0:raise RuntimeError(f"BAD_LOG:{name}")
    result={"state":"PRINT_BRIDGE_ARTIFACT_AUDIT_PASS","model_count":4,"complex_spectrum_count":16,
            "frequency_points_each":len(F),"models":models,"logs":logs,"pass":True}
    (ROOT/"artifact_audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="models"},indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("phase",choices=("representative","fine","diagnostic","audit"));a=p.parse_args()
    {"representative":representative,"fine":fine,"diagnostic":diagnostic,"audit":audit}[a.phase]()
