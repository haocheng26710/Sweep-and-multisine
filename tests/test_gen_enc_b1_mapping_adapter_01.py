from __future__ import annotations
import copy,hashlib,json
from pathlib import Path
import jsonschema,pytest
from scripts.gen_enc_b1_mapping_adapter_01.build_freeze_package import build,PACKAGE,ROOT
from scripts.gen_enc_b1_mapping_adapter_01.driver_adapter import AdapterError,build as driver_build
from scripts.gen_enc_b1_mapping_adapter_01.verifier_adapter import verify as verifier_build

def read_raw_bound(path:Path,want:str):
    raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==want;return json.loads(raw.decode("utf-8"))
def members():return [f"{f}_{i:02d}" for f in ("HAND","NEAR","RANDOM","PHYSICS") for i in range(1,6)]
def real_documents():
    build();table=json.loads((PACKAGE/"dependency_table.json").read_text());return {row["source_id"]:read_raw_bound(ROOT/row["path"],row["sha256"]) for row in table["sources"]}

def test_real_read_only_adapter_driver_and_verifier_agree():
    left=driver_build(real_documents(),members());right=verifier_build(real_documents(),members());assert left==right
    assert left["type_corrections"]=={"ROOT_BRACKET":"object","SLOT_ROWS":"object","U4_PARTICIPATION":"object","ZERO_EDGE_RULE":"string"}
    z=left["geometry_slot_z_interval_m"];assert len(z["runtime_primary_interval"])==2 and all(len(v)==2 for v in z["runtime_slot_intervals"].values());assert z["static_rules"]["midpoint_lower_upper_for_identity_eligibility_metrics"] is False
    ownership=left["ownership_derivation"]["members"];assert len(ownership)==20 and all(len(x["witnesses"])==5 for x in ownership)
    assert left["future_outputs"]==["OWNERSHIP_CELLS","OWNERSHIP_RULE"] and left["final_test_read"] is False

def test_interval_must_remain_two_finite_ordered_endpoints():
    docs=real_documents();bad=copy.deepcopy(docs);bad["CAD0_MULTI_SOURCE_02"]["sector"]["collector"]["z_m"]=[0.1,0.1]
    with pytest.raises(AdapterError,match="INTERVAL"):driver_build(bad,members())

def test_frozen_contract_exact20_schema_and_zero_state():
    build();contract=json.loads((PACKAGE/"adapter_contract.json").read_text());schema=json.loads((ROOT/"schemas/gen_enc/b1_mapping_adapter_01/adapter_contract.schema.json").read_text());jsonschema.Draft202012Validator(schema).validate(contract)
    assert contract["members"]==members() and contract["member_count"]==20 and contract["ownership"]["witness_count_b1"]==100
    assert contract["geometry_slot_z"]["type"]=="array" and contract["geometry_slot_z"]["min_items"]==contract["geometry_slot_z"]["max_items"]==2
    assert contract["threshold_metric_evidence_change"] is False and contract["identity_or_static_execution"] is False and contract["final_test_read"] is False
    assert "driver_adapter" not in (ROOT/"scripts/gen_enc_b1_mapping_adapter_01/verifier_adapter.py").read_text()
