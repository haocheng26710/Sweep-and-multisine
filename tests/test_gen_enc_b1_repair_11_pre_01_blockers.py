from __future__ import annotations
import json,subprocess,time
from pathlib import Path
import jsonschema,pytest
from tests.helpers.gen_enc_b1_repair_11_pre_01_fixture import argv,make_case,reseal_controls,sha,write

SCHEMAS=Path("schemas/gen_enc/b1_repair_11_pre_01")
def run(c,command,module=None):
    args=argv(c,command)
    if module:args[2]=module
    return subprocess.run(args,text=True,capture_output=True)
def tree(c):
    base=c["roots"]["staging"].parent
    return {p.relative_to(base).as_posix():p.read_bytes() for p in base.rglob("*") if p.is_file()}
def prepare_driver(c):assert run(c,"shape-preflight").returncode==0;assert run(c,"extract-shape").returncode==0
def prepare_verifier(c):prepare_driver(c);assert run(c,"verify-shape").returncode==0

@pytest.mark.parametrize("field,value",[("state","FORGED"),("dispatch_sha256","0"*64),("authority_manifest_sha256","0"*64),("commands_exact",["shape-preflight"]),("final_test_read",True),("roots",{})])
def test_b01_consumed_each_binding_mutation_rejected_before_read_or_write(field,value):
    c=make_case();assert run(c,"shape-preflight").returncode==0;p=c["roots"]["side_records"]/"SHAPE_DISPATCH_CONSUMED.json";v=json.loads(p.read_text());v[field]=value;write(p,v);before=tree(c);r=run(c,"extract-shape");assert r.returncode==2;assert tree(c)==before;assert not c["roots"]["driver_receipts"].exists()

def test_b01_noncanonical_consumed_rejected_zero_mutation():
    c=make_case();assert run(c,"shape-preflight").returncode==0;p=c["roots"]["side_records"]/"SHAPE_DISPATCH_CONSUMED.json";p.write_bytes(p.read_bytes()+b" ");before=tree(c);assert run(c,"extract-shape").returncode==2;assert tree(c)==before

@pytest.mark.parametrize("attack",["forged","dispatch","purpose","path","cumulative","missing","extra","reorder","noncanonical"])
def test_b02_prior_driver_receipt_attacks_rejected_before_snapshot_access(attack):
    c=make_case();prepare_driver(c);d=c["roots"]["driver_receipts"];p=d/"0001.json"
    if attack=="forged":write(p,{"forged":True})
    elif attack=="missing":p.rename(d/"MISSING.json")
    elif attack=="extra":write(d/"0014.json",json.loads(p.read_text()))
    elif attack=="reorder":
        q=d/"0002.json";a=p.read_bytes();b=q.read_bytes();p.write_bytes(b);q.write_bytes(a)
    elif attack=="noncanonical":p.write_bytes(p.read_bytes()+b" ")
    else:
        v=json.loads(p.read_text());key={"dispatch":"dispatch_sha256","purpose":"purpose","path":"source_path","cumulative":"cumulative_ordinal"}[attack];v[key]="0"*64 if attack=="dispatch" else "FORGED" if attack!="cumulative" else 99;write(p,v)
    before=tree(c);r=run(c,"verify-shape");assert r.returncode==2;assert tree(c)==before;assert not c["roots"]["verifier_receipts"].exists();assert not (c["roots"]["staging"]/"independent_shape_report.json").exists()

@pytest.mark.parametrize("where",["side_records","driver_receipts","verifier_receipts","staging","package"])
def test_b03_whole_run_unlisted_rejected_without_mutation(where):
    c=make_case();prepare_verifier(c);target=c["roots"][where]/"UNLISTED.json";write(target,{"unlisted":True});before=tree(c);assert run(c,"package-shape").returncode==2;assert tree(c)==before;assert not (c["roots"]["terminal"]/"TERMINAL.json").exists()

def test_b03_missing_or_replaced_required_output_rejected():
    c=make_case();prepare_verifier(c);p=c["roots"]["side_records"]/"DRIVER_DONE.json";p.rename(p.with_name("DRIVER_DONE.missing"));before=tree(c);assert run(c,"package-shape").returncode==2;assert tree(c)==before
    c=make_case();prepare_verifier(c);p=c["roots"]["staging"]/"independent_shape_report.json";v=json.loads(p.read_text());v["structural_snapshot_digest"]="0"*64;write(p,v);before=tree(c);assert run(c,"package-shape").returncode==2;assert tree(c)==before

def test_b04_eight_process_extract_single_transition_no_mixed_failure():
    c=make_case(read_delay_ms=30);assert run(c,"shape-preflight").returncode==0;ps=[subprocess.Popen(argv(c,"extract-shape"),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)];results=[p.communicate()+(p.returncode,) for p in ps]
    assert all(code in (0,2) for _,_,code in results);assert len(list(c["roots"]["driver_receipts"].glob("*.json")))==13;assert (c["roots"]["staging"]/"driver_shape_snapshot.json").exists();assert (c["roots"]["side_records"]/"DRIVER_DONE.json").exists();assert not (c["roots"]["terminal"]/"TERMINAL.json").exists()

def test_b04_eight_process_verify_and_package_are_single_idempotent_transitions():
    c=make_case(read_delay_ms=20);prepare_driver(c);ps=[subprocess.Popen(argv(c,"verify-shape"),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)];results=[p.communicate()+(p.returncode,) for p in ps];assert all(x[2] in (0,2) for x in results);assert len(list(c["roots"]["verifier_receipts"].glob("*.json")))==13;assert not (c["roots"]["terminal"]/"TERMINAL.json").exists()
    ps=[subprocess.Popen(argv(c,"package-shape"),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)];results=[p.communicate()+(p.returncode,) for p in ps];assert all(x[2] in (0,2) for x in results);assert len(list(c["roots"]["package"].glob("SHAPE_PACKAGE.json")))==1;assert len(list(c["roots"]["terminal"].glob("TERMINAL.json")))==1;assert json.loads((c["roots"]["terminal"]/"TERMINAL.json").read_text())["status"]=="TECHNICAL_SUCCESS_NEVER_FORMAL"

def test_b04_verifier_real_kill_partial_receipts_recover_to_single_failure():
    c=make_case(read_delay_ms=100);prepare_driver(c);p=subprocess.Popen(argv(c,"verify-shape"),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);deadline=time.time()+5
    while time.time()<deadline and len(list(c["roots"]["verifier_receipts"].glob("*.json")))<3:time.sleep(.01)
    p.kill();p.communicate(timeout=5);n=len(list(c["roots"]["verifier_receipts"].glob("*.json")));assert 1<=n<13;assert run(c,"verify-shape").returncode==2;t=json.loads((c["roots"]["terminal"]/"TERMINAL.json").read_text());assert t["authority_read_count"]==13+n and t["status"]=="FAIL_CLOSED";assert not (c["roots"]["staging"]/"independent_shape_report.json").exists()

@pytest.mark.parametrize("manifest",["authority_manifest","selector_contract","command_manifest","output_manifest","negative_capability_manifest"])
def test_b05_coordinated_manifest_reanchor_rejected_pre_read(manifest):
    c=make_case();fake=c["base"]/(manifest+".json");fake.write_bytes((Path("outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_11_shape_only_preexecution_corr01")/(manifest+".json")).read_bytes());release=json.loads(c["release"].read_text());release[manifest+"_path"]=fake.as_posix();release[manifest+"_sha256"]=sha(fake.read_bytes());write(c["release"],release);reseal_controls(c);assert run(c,"shape-preflight").returncode==2;assert not c["roots"]["side_records"].exists()

def test_b05_guardian_contract_and_exact13_are_independently_enforced():
    c=make_case();release=json.loads(c["release"].read_text());release["guardian_contract_path"]=(c["base"]/"contract.json").as_posix();Path(release["guardian_contract_path"]).write_bytes(Path("outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/contracts/GEN_ENC_FAST_B1_REPAIR_11_AUTHORITY_SHAPE_ONLY_CONFORMANCE_CONTRACT.json").read_bytes());release["guardian_contract_sha256"]=sha(Path(release["guardian_contract_path"]).read_bytes());write(c["release"],release);reseal_controls(c);assert run(c,"shape-preflight").returncode==2

def test_b06_formal_entrypoints_reject_technical_controls_pre_read():
    c=make_case();assert run(c,"shape-preflight","scripts.gen_enc_b1_repair_11_pre_01.formal_driver").returncode==2;assert not c["roots"]["side_records"].exists()
    prepare_driver(c);assert run(c,"verify-shape","scripts.gen_enc_b1_repair_11_pre_01.independent_verifier").returncode==2;assert not c["roots"]["verifier_receipts"].exists()

def test_b06_technical_outputs_fail_formal_schemas_and_are_nonpromotable():
    c=make_case();prepare_verifier(c);assert run(c,"package-shape").returncode==0;terminal=json.loads((c["roots"]["terminal"]/"TERMINAL.json").read_text());package=json.loads((c["roots"]["package"]/"SHAPE_PACKAGE.json").read_text());assert terminal["record_kind"].startswith("TECHNICAL_") and package["record_kind"].startswith("TECHNICAL_")
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(terminal,json.loads((SCHEMAS/"terminal.schema.json").read_text()))
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(package,json.loads((SCHEMAS/"shape_package.schema.json").read_text()))
