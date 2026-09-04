from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "outputs/gen_enc/GEN_ENC_4_CAD_TO_EDGE_ROUTE_AUDIT"


def test_route_audit_rejects_unphysical_direct_edges_and_freezes_m2b() -> None:
    run = subprocess.run([sys.executable, str(REPO / "scripts/gen_enc_4_cad_to_edge_route_audit.py")], cwd=REPO, capture_output=True, text=True, check=True)
    assert "M2_DIRECT_EDGE_PHYSICAL_MAPPING_REJECTED__M2B_CONTRACT_FROZEN" in run.stdout
    audit = json.loads((ROOT / "route_mapping_audit.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "m2b_preexecution_contract.json").read_text(encoding="utf-8"))
    assert audit["terminal_state"] == "M2_DIRECT_EDGE_PHYSICAL_MAPPING_REJECTED"
    assert audit["sealed_actual_fluid_topology"]["direct_sector_to_sector_positive_area_edges"] == []
    assert all(item["status"] == "REJECTED" for item in audit["route_candidate_audit"])
    assert contract["status"] == "CONTRACT_FROZEN_EXECUTION_NOT_AUTHORIZED"
    assert contract["full_m2_or_m3_authorized"] is False
    assert contract["validation_reads"] == 0 and contract["final_test_read"] is False
