from __future__ import annotations

import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from scripts.gen_enc_b1_repair_01 import cad_adapter_driver as da
from scripts.gen_enc_b1_repair_01 import cad_adapter_verifier as va
from scripts.gen_enc_b1_repair_01 import formal_driver as driver
from scripts.gen_enc_b1_repair_01 import independent_verifier as verifier

REPO = Path(__file__).resolve().parents[1]
SCHEMAS = REPO / "schemas/gen_enc/b1_repair_01"
PROJECTION = REPO / "outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_01/cad_projection_contract.json"
BINDING = REPO / "outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_freeze/authority_binding.json"
OLD_FREEZE = REPO / "outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_freeze"


def authority_entries() -> list[dict]:
    return json.loads(BINDING.read_text(encoding="utf-8"))["triples"]


def projection() -> dict:
    return json.loads(PROJECTION.read_text(encoding="utf-8"))


def fixture_objects() -> dict:
    hand, near = [], []
    for i in range(1, 21):
        q0 = (i - 10.5) / 200; q90 = -q0 / 2; q180 = q0 / 4
        common = {"volume_logit_0": q0, "volume_logit_90": q90, "volume_logit_180": q180, "derived_volume_logit_270": -(q0 + q90 + q180) / 3, "external_aperture_fraction_0": .41+i/1000, "external_aperture_fraction_90": .42+i/1000, "external_aperture_fraction_180": .43+i/1000, "external_aperture_fraction_270": .44+i/1000, "loss_fraction_0": .03+i/10000, "loss_fraction_90": .035+i/10000, "loss_fraction_180": .04+i/10000, "loss_fraction_270": .045+i/10000}
        hand.append({"member_id": f"HAND_{i:02d}", **common, "central_mix_aperture_fraction": .2+i/1000})
        near.append({"member_id": f"NEAR_{i:02d}", **common, "shared_coupling_alpha": .03+(i-1)*.04/19})
    random_axes = list(da.RANDOM_AXES); physics_axes = list(da.PHYSICS_AXES)
    random = {"family_id": driver.FAMILIES[2], "version": "TECHNICAL_FIXTURE_ONLY", "member_count": 20, "stochastic": True, "seeds_ref": "TECHNICAL_FIXTURE_ONLY", "parameter_order": random_axes, "parameters": [{"group":"VOLUME_LOGIT","axes":random_axes[:3],"bounds":[-.12,.12]}, {"group":"RECIPROCAL_EDGE_POSITIVE","axes":random_axes[3:9],"bounds":[.2,.8]}, {"group":"LOSS","axes":random_axes[9:],"bounds":[.02,.08]}], "dof": 13, "uniform_algorithm": {"interval":"OPEN_0_1_BINARY64","word_to_uniform":"((word>>11)+0.5)/2^53","one_guard":"nextafter(1.0,0.0)"}, "splitmix64": {"gamma_hex":"9e3779b97f4a7c15","mix":"SPLITMIX64_FROZEN","address":"seed+gamma*(axis+1) mod 2^64"}, "reciprocity": True, "canonical_generator": {"draw_count":13,"redraw_count":0,"edge_zero_atom_probability":.5,"edge_positive":"0.2+0.6*(2*u-1)"}}
    physics = {"family_id": driver.FAMILIES[3], "version": "TECHNICAL_FIXTURE_ONLY", "member_count": 20, "stochastic": True, "lhs_master_seed": 2026090200, "member_identity_seeds_ref": "TECHNICAL_FIXTURE_ONLY", "parameter_order": physics_axes, "parameters": [{"group":"VOLUME_LOGIT","axes":physics_axes[:3],"bounds":[-.12,.12]}, {"group":"EXTERNAL_APERTURE","axes":physics_axes[3:7],"bounds":[.2,.8]}, {"group":"RING_COUPLING","axes":physics_axes[7:11],"bounds":[.2,.8]}, {"group":"LOSS","axes":physics_axes[11:],"bounds":[.02,.08]}], "dof": 15, "lhs_algorithm": ["STRATA=20","SAMPLE=(PERMUTATION[row]+0.5)/20","JITTER=false","FISHER_YATES_SPLITMIX64=i19_TO_1"], "physics_identity": ["TECHNICAL_FIXTURE_ONLY"]*4, "unstructured_random_matrix_substitution": False}
    result = {"HAND_ROWS":hand, "NEAR_ROWS":near, "RANDOM_FAMILY_SPEC":random, "RANDOM_FIXED_SEEDS":[1000+i*7919 for i in range(20)], "PHYSICS_FAMILY_SPEC_PARAMETERS_LHS":physics, "PHYSICS_MASTER_SEED":2026090200, "PHYSICS_MEMBER_IDENTITY_SEEDS":[2000+i*6151 for i in range(20)]}
    for index, entry in enumerate((x for x in authority_entries() if x["purpose"].startswith("CAD")), 1):
        shape = entry["object_shape"]
        value = {}
        for field in shape["field_names"]:
            count = shape.get("array_counts", {}).get(field)
            value[field] = [{"technical_leaf": f"{index}:{field}:{i}"} for i in range(count)] if count is not None else {"technical_leaf": f"{index}:{field}"}
        if index == 13:
            value["selections"] = {"U1":{"technical_leaf":1}, "U2":{"technical_leaf":2}, "U3":{"technical_leaf":3}}
        result[entry["purpose"]] = value
    return result


def binding(run_id: str = "a"*64) -> dict:
    return {"run_id":run_id, "release_sha256":"b"*64, "attestation_sha256":"9"*64, "authority_allowlist_sha256":driver.frozen.FAST0_ALLOWLIST_SHA256, "source_manifest_sha256":"c"*64, "schema_manifest_sha256":"d"*64, "command_manifest_sha256":"e"*64, "authority_read_count":0}


def tx_context(base: Path, run_id: str = "f"*64) -> dict:
    roots={name:base/name for name in ("staging","run","pointer","journal","success","failure","side_records")}
    return {**binding(run_id),"task_id":driver.TASK_ID,"batch_id":"B1","roots_resolved":roots,"roots_relative":{k:str(v.relative_to(REPO)).replace("\\","/") if v.is_relative_to(REPO) else k for k,v in roots.items()},"schemas":driver.load_schemas(SCHEMAS)}


def make_tx_stage(path: Path) -> None:
    for index,rel in enumerate(driver.exact_artifact_paths()):
        target=path/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(f"repair-technical-{index}\n")


def leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items(): yield from leaves(child, path+(key,))
    elif isinstance(value, list):
        for index, child in enumerate(value): yield from leaves(child, path+(index,))
    else: yield path


def mutate_at(value, path):
    node = value
    for part in path[:-1]: node = node[part]
    old = node[path[-1]]
    node[path[-1]] = not old if isinstance(old, bool) else old+1 if isinstance(old, (int,float)) else old+"_MUTATED"


def test_review_hash_task_binding_and_old_freeze_immutable() -> None:
    review = REPO / "outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_FAST_B1_PRE_RELEASE_EXECUTABLE_FREEZE_CONFORMANCE_REVIEW.json"
    assert hashlib.sha256(review.read_bytes()).hexdigest() == "38544ae737c07f6bde05c510592b388f6a49006a392db1aa7d69cbf394ef2bb2"
    assert driver.TASK_ID == verifier.TASK_ID == "01a049a7-15ca-79e1-92a2-d3822ba8609d"
    assert hashlib.sha256((OLD_FREEZE/"SHA256SUMS.txt").read_bytes()).hexdigest() == "a7daa2013d4f84e9f2b8d355f47498634edfd35ec1a4fbbd6551daced6b6c369"


def test_schemas_are_strict_and_valid() -> None:
    assert len(list(SCHEMAS.glob("*.schema.json"))) == 15
    for path in SCHEMAS.glob("*.schema.json"):
        schema=json.loads(path.read_text()); jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False


def test_driver_and_verifier_mechanically_bind_all_13_sources_and_every_leaf() -> None:
    objects=fixture_objects(); entries=authority_entries(); contract=projection()
    left=da.parse_cad(objects,entries,contract); right=va.model(objects,entries,contract)
    assert left == right and left["source_count"] == 13 and left["leaf_count"] > 100
    original=left["model_sha256"]
    for purpose in da.CAD_PURPOSES:
        for leaf in list(leaves(objects[purpose])):
            changed=copy.deepcopy(objects); mutate_at(changed[purpose],leaf)
            try: new=da.parse_cad(changed,entries,contract)["model_sha256"]
            except Exception: continue
            assert new != original, (purpose,leaf)


def test_replacing_all_13_cad_objects_changes_every_member_hash() -> None:
    objects=fixture_objects(); entries=authority_entries(); contract=projection()
    before=driver.members_from_authority(objects,entries,contract)
    changed=copy.deepcopy(objects)
    for purpose in da.CAD_PURPOSES:
        for leaf in list(leaves(changed[purpose])): mutate_at(changed[purpose],leaf)
    after=driver.members_from_authority(changed,entries,contract)
    assert all(hashlib.sha256(driver.canonical(a)).digest()!=hashlib.sha256(driver.canonical(b)).digest() for a,b in zip(before,after))


def test_exact_random_nextafter_and_physics_fisher_yates_from_sealed_bounds(monkeypatch) -> None:
    objects=fixture_objects()
    assert da.parse_random_spec(objects["RANDOM_FAMILY_SPEC"])["bounds"]["q0"] == (-.12,.12)
    assert va.random_spec(objects["RANDOM_FAMILY_SPEC"])["bounds"]["q0"] == (-.12,.12)
    monkeypatch.setattr(da,"mix64",lambda _: (1<<64)-1); monkeypatch.setattr(va,"_mix",lambda _: (1<<64)-1)
    assert da.uniform(1,0) == va._uniform(1,0) == math.nextafter(1.0,0.0)
    monkeypatch.undo()
    for axis in range(15): assert da.permutation(2026090200,axis) == va._permutation(2026090200,axis)
    changed=copy.deepcopy(objects["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"]); changed["parameters"][0]["bounds"]=[-.05,.05]
    assert da.physics_parameters(changed,2026090200,1)["q0"] != da.physics_parameters(objects["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"],2026090200,1)["q0"]


@pytest.mark.parametrize("where", ["RANDOM_FAMILY_SPEC", "PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"])
def test_spec_leaf_mutation_rejected_or_changes_derived_values(where: str) -> None:
    objects=fixture_objects(); changed=copy.deepcopy(objects); spec=changed[where]
    spec["lhs_algorithm" if where.startswith("PHYSICS") else "uniform_algorithm"] = []
    with pytest.raises(Exception): driver.members_from_authority(changed,authority_entries(),projection())


def test_generate_verify_complete_graph_and_deep_cad(tmp_path: Path) -> None:
    stage=tmp_path/"stage"; objects=fixture_objects(); context=binding()
    assert driver.build_staging(stage,objects,authority_entries(),projection(),context,SCHEMAS)["artifact_count"] == 29
    result=verifier.verify_and_reseal(stage,objects,authority_entries(),projection(),context,SCHEMAS)
    assert result["artifact_count"] == 31
    actual={p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()}
    assert len(actual)==31 and len(list((stage/"members").glob("*.json")))==20 and len(list((stage/"partial_manifests").glob("*.json")))==4
    member=json.loads((stage/"members/RANDOM_01.json").read_text()); cad=member["cad_static_evidence"]
    assert all(len(x["trace"])==80 for x in cad["volume_root_witnesses"])
    assert all(x["participation"]=="U4_INTERFACE_EXCEPTION_ONLY" for x in cad["u4_exception_witnesses"])
    assert cad["actual_fluid_graph"]["component_count"]==1


@pytest.mark.parametrize("mutation", ["missing","extra","empty","threshold_copy","graph","trace","u4"])
def test_schema_and_independent_verifier_fail_closed_on_cad_mutations(mutation: str,tmp_path: Path) -> None:
    stage=tmp_path/mutation; objects=fixture_objects(); driver.build_staging(stage,objects,authority_entries(),projection(),binding(),SCHEMAS)
    path=stage/"members/HAND_01.json"; member=json.loads(path.read_text()); cad=member["cad_static_evidence"]
    if mutation=="missing": del cad["ownership_cells"]
    elif mutation=="extra": cad["unlisted"]={}
    elif mutation=="empty": cad["general_minima"]={}
    elif mutation=="threshold_copy": cad["thresholds_copied_as_measurements"]=True
    elif mutation=="graph": cad["actual_fluid_graph"]["edges"][0]["positive_area_m2"]=0
    elif mutation=="trace": cad["volume_root_witnesses"][0]["trace"][4]["mid_m"] += .001
    else: cad["u4_exception_witnesses"][0]["participation"]="GENERAL"
    path.write_bytes(driver.canonical(member))
    with pytest.raises(Exception): verifier.verify_and_reseal(stage,objects,authority_entries(),projection(),binding(),SCHEMAS)


@pytest.mark.parametrize("artifact", ["partial_manifests/HAND.json","static_audit.json","batch_index.json","SHA256SUMS.txt","generation_terminal.json"])
def test_artifact_graph_mutation_rejected(artifact: str,tmp_path: Path) -> None:
    stage=tmp_path/artifact.replace("/","_"); objects=fixture_objects(); driver.build_staging(stage,objects,authority_entries(),projection(),binding(),SCHEMAS)
    path=stage/artifact; path.write_bytes(path.read_bytes()+b"X")
    with pytest.raises(Exception): verifier.verify_and_reseal(stage,objects,authority_entries(),projection(),binding(),SCHEMAS)


def test_zero_unlisted_and_verifier_exception(tmp_path: Path) -> None:
    objects=fixture_objects(); stage=tmp_path/"extra"; driver.build_staging(stage,objects,authority_entries(),projection(),binding(),SCHEMAS); (stage/"extra.json").write_text("{}")
    with pytest.raises(verifier.RepairVerifyError,match="ZERO_UNLISTED"): verifier.verify_and_reseal(stage,objects,authority_entries(),projection(),binding(),SCHEMAS)
    stage2=tmp_path/"fault"; driver.build_staging(stage2,objects,authority_entries(),projection(),binding(),SCHEMAS)
    with pytest.raises(verifier.RepairVerifyError,match="INJECT"): verifier.verify_and_reseal(stage2,objects,authority_entries(),projection(),binding(),SCHEMAS,"member:7")


def test_failure_terminal_exclusive_honest_and_success_prevents_failure(tmp_path: Path) -> None:
    roots={k:tmp_path/k for k in ("success","failure")}; context={**binding(),"roots_resolved":roots,"schemas":driver.load_schemas(SCHEMAS)}
    marker=driver.write_failure(context,"TECHNICAL_NEGATIVE",{"authority_reads":0,"members":7,"artifacts":12,"published":0})
    assert json.loads(marker.read_text())["honest_counts"]["members"]==7
    assert driver.write_failure(context,"OTHER",{"authority_reads":0,"members":0,"artifacts":0,"published":0})==marker
    marker.unlink(); roots["success"].mkdir(); (roots["success"]/"VERIFIED_SUCCESS.json").write_text("{}")
    with pytest.raises(driver.RepairError,match="SUCCESS_FORBIDS_FAILURE"): driver.write_failure(context,"NO",{"authority_reads":0,"members":0,"artifacts":0,"published":0})


def test_marker_first_write_failure_is_retried_not_swallowed(tmp_path:Path)->None:
    context={**binding(),"roots_resolved":{k:tmp_path/k for k in ("success","failure")},"schemas":driver.load_schemas(SCHEMAS)}
    path=driver.write_failure_resilient(context,"INJECTED",{"authority_reads":0,"members":3,"artifacts":5,"published":0},True)
    value=json.loads(path.read_text());assert value["package_terminal_count"]==1 and value["honest_counts"]["members"]==3 and value["reason"].startswith("TERMINAL_RETRY_AFTER")


def test_formal_cli_is_exact_and_pre_release_refuses_before_authority_read() -> None:
    expected=driver.expected_argv("preflight")
    assert expected[0:3]==["-m","scripts.gen_enc_b1_repair_01.formal_driver","preflight"]
    completed=subprocess.run([sys.executable,*expected],cwd=REPO,text=True,capture_output=True,check=False)
    assert completed.returncode==2 and '"authority_read_count": 0' in completed.stderr
    assert "technical" not in {a.dest for a in driver.parser()._actions}


def test_full_subprocess_technical_cli_positive_and_fault(tmp_path:Path)->None:
    bundle=tmp_path/"bundle.json";stage=tmp_path/"stage"
    bundle.write_text(json.dumps({"identity_class":"TECHNICAL_CONFORMANCE_ONLY_NEVER_FORMAL_AUTHORITY","binding":binding(),"objects":fixture_objects(),"authority_entries":authority_entries(),"projection":projection()}))
    base=[sys.executable,"tests/helpers/gen_enc_b1_repair_01_cli.py"]
    generated=subprocess.run([*base,"generate","--bundle",str(bundle),"--stage",str(stage),"--schema-root",str(SCHEMAS)],cwd=REPO,text=True,capture_output=True)
    assert generated.returncode==0 and '"artifact_count": 29' in generated.stdout
    verified=subprocess.run([*base,"verify","--bundle",str(bundle),"--stage",str(stage),"--schema-root",str(SCHEMAS)],cwd=REPO,text=True,capture_output=True)
    assert verified.returncode==0 and '"artifact_count": 31' in verified.stdout
    stage2=tmp_path/"fault";subprocess.run([*base,"generate","--bundle",str(bundle),"--stage",str(stage2),"--schema-root",str(SCHEMAS)],cwd=REPO,check=True)
    fault=subprocess.run([*base,"verify","--bundle",str(bundle),"--stage",str(stage2),"--schema-root",str(SCHEMAS),"--fault","member:8"],cwd=REPO,text=True,capture_output=True)
    assert fault.returncode==2 and '"authority_read_count": 0' in fault.stderr


def test_concurrent_process_consumption_has_exactly_one_winner(tmp_path: Path) -> None:
    context=tx_context(tmp_path);side=context["roots_resolved"]["side_records"];side.mkdir(parents=True)
    issued={"schema_version":"gen_enc_fast_b1_repair_01_side_record_v1","state":"ISSUED","repair_id":driver.REPAIR,"task_id":driver.TASK_ID,"batch_id":"B1","run_id":context["run_id"],"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"],"authority_allowlist_sha256":context["authority_allowlist_sha256"],"source_manifest_sha256":context["source_manifest_sha256"],"schema_manifest_sha256":context["schema_manifest_sha256"],"command_manifest_sha256":context["command_manifest_sha256"],"commands_exact":["preflight","generate-staging","verify","publish","recover","package-results"],"mode":"FORMAL_B1_EXACT_20","roots":{k:k for k in ("staging","run","pointer","journal","success","failure","side_records")},"one_use":True,"revoked":False,"final_test_read":False}
    driver.exclusive_json(side/"ISSUED.json",issued)
    code="""import json,sys\nfrom pathlib import Path\nfrom scripts.gen_enc_b1_repair_01 import formal_driver as d\nbase=Path(sys.argv[1]);schemas=d.load_schemas(Path(sys.argv[2]));roots={n:base/n for n in ('staging','run','pointer','journal','success','failure','side_records')};issued=json.loads((roots['side_records']/ 'ISSUED.json').read_text());c={**issued,'roots_resolved':roots,'schemas':schemas};\ntry:d.consume_once(c);print('WON')\nexcept Exception:print('LOST');raise SystemExit(3)\n"""
    procs=[subprocess.Popen([sys.executable,"-c",code,str(tmp_path),str(SCHEMAS)],cwd=REPO,text=True,stdout=subprocess.PIPE) for _ in range(8)]
    results=[p.communicate()[0].strip() for p in procs]
    assert results.count("WON")==1 and results.count("LOST")==7


@pytest.mark.parametrize("index",range(20))
def test_real_kill_after_replace_before_journal_recovers_20_targets(index:int,tmp_path:Path)->None:
    context=tx_context(tmp_path);stage=context["roots_resolved"]["staging"];make_tx_stage(stage)
    code="""import sys\nfrom pathlib import Path\nfrom scripts.gen_enc_b1_repair_01 import formal_driver as d\nbase=Path(sys.argv[1]);schemas=d.load_schemas(Path(sys.argv[2]));roots={n:base/n for n in ('staging','run','pointer','journal','success','failure','side_records')};c={**%r,'roots_resolved':roots,'roots_relative':{n:n for n in roots},'schemas':schemas};d.transaction_publish(roots['staging'],roots['run'],roots['journal']/ 'publication.json',roots['pointer']/ 'B1.json',c,'kill:%d')\n"""%(binding("f"*64),index)
    result=subprocess.run([sys.executable,"-c",code,str(tmp_path),str(SCHEMAS)],cwd=REPO,check=False)
    assert result.returncode==86
    journal=context["roots_resolved"]["journal"]/"publication.json";pointer=context["roots_resolved"]["pointer"]/"B1.json"
    assert driver.rollback(journal,context["roots_resolved"]["run"],pointer,context["schemas"])>=1
    assert not any(p.is_file() for p in context["roots_resolved"]["run"].rglob("*"))


@pytest.mark.parametrize("fault",["copy:0","fsync:0","replace:0","journal:0","pointer"])
def test_publication_faults_recover_to_zero_partial(fault:str,tmp_path:Path)->None:
    context=tx_context(tmp_path);stage=context["roots_resolved"]["staging"];make_tx_stage(stage);journal=context["roots_resolved"]["journal"]/"publication.json";pointer=context["roots_resolved"]["pointer"]/"B1.json"
    with pytest.raises(driver.RepairError):driver.transaction_publish(stage,context["roots_resolved"]["run"],journal,pointer,context,fault)
    driver.rollback(journal,context["roots_resolved"]["run"],pointer,context["schemas"])
    assert not pointer.exists() and not any(p.is_file() for p in context["roots_resolved"]["run"].rglob("*"))
