"""Validate P04C artifacts, write inventory, and freeze SHA256SUMS."""
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path

ROOT=Path(r"D:\Bristol course\dissertation\program work")
OUT=ROOT/"outputs/simulation/COMSOL_SCHEME_3A/P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC"
REPORT=ROOT/"docs/progress/COMSOL_3A_P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC.md"

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

required=[
"diagnostic_contract.json","input_authority_manifest.csv","region_selection_audit.csv",
"compartment_energy_long.csv","compartment_participation.csv","cavity_chamber_mic_complex.csv",
"hr03_isolated_vs_integrated.csv","full_band_local_peaks.csv","mode_branch_tracking.csv",
"mechanism_classification.json","extract_existing_solutions.py","analyze_p04c_diagnostic.py",
"finalize_p04c_artifacts.py","figures/energy_participation_heatmap.png",
"figures/pressure_kinetic_fraction.png","figures/hr03_isolated_vs_integrated.png",
"figures/branch_frequency_vs_module.png","figures/cavity_chamber_mic_comparison.png",
"figures/phase_participation_exchange.png"]
missing=[x for x in required if not (OUT/x).is_file() or (OUT/x).stat().st_size==0]
if missing: raise RuntimeError(f"Missing/empty required artifacts: {missing}")
if not REPORT.is_file(): raise RuntimeError("Missing progress report")
contract=json.loads((OUT/"diagnostic_contract.json").read_text(encoding="utf-8"))
classification=json.loads((OUT/"mechanism_classification.json").read_text(encoding="utf-8"))
if contract["final_test_read"] or classification["final_test_read"]: raise RuntimeError("final-test boundary violated")
if classification["study_run_calls"] or classification["model_save_calls"]: raise RuntimeError("no-solve/no-save boundary violated")
if classification["primary_status"]!="P04C TOPOLOGY HYBRIDIZATION SUPPORTED": raise RuntimeError("unexpected terminal state")
with (OUT/"compartment_energy_long.csv").open(newline="",encoding="utf-8") as f: energy=list(csv.DictReader(f))
with (OUT/"compartment_participation.csv").open(newline="",encoding="utf-8") as f: participation=list(csv.DictReader(f))
with (OUT/"cavity_chamber_mic_complex.csv").open(newline="",encoding="utf-8") as f: complex_rows=list(csv.DictReader(f))
with (OUT/"full_band_local_peaks.csv").open(newline="",encoding="utf-8") as f: peaks=list(csv.DictReader(f))
if (len(energy),len(participation),len(complex_rows),len(peaks))!=(20480,2560,2560,44):
    raise RuntimeError("unexpected artifact row counts")

inventory=[]
for path in sorted(OUT.rglob("*")):
    if path.is_file() and path.name not in {"SHA256SUMS","artifact_inventory.csv"}:
        inventory.append({"relative_path":path.relative_to(ROOT).as_posix(),"size_bytes":path.stat().st_size,"sha256":sha(path)})
with (OUT/"artifact_inventory.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["relative_path","size_bytes","sha256"]);w.writeheader();w.writerows(inventory)

hash_paths=[p for p in sorted(OUT.rglob("*")) if p.is_file() and p.name!="SHA256SUMS"]+[REPORT]
lines=[f"{sha(path)}  {path.relative_to(ROOT).as_posix()}" for path in hash_paths]
(OUT/"SHA256SUMS").write_text("\n".join(lines)+"\n",encoding="utf-8")
print(json.dumps({"status":classification["primary_status"],"inventory_entries":len(inventory),"sha256_entries":len(lines),"row_counts":{"energy":len(energy),"participation":len(participation),"complex":len(complex_rows),"peaks":len(peaks)},"final_test_read":False}))
