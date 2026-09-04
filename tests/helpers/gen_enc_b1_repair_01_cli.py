"""Subprocess-only technical conformance CLI; never imported by formal modules."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from scripts.gen_enc_b1_repair_01 import formal_driver as driver
from scripts.gen_enc_b1_repair_01 import independent_verifier as verifier


def main()->int:
    p=argparse.ArgumentParser();p.add_argument("command",choices=["generate","verify"]);p.add_argument("--bundle",type=Path,required=True);p.add_argument("--stage",type=Path,required=True);p.add_argument("--schema-root",type=Path,required=True);p.add_argument("--fault")
    ns=p.parse_args();bundle=json.loads(ns.bundle.read_text());binding=bundle["binding"]
    if bundle.get("identity_class")!="TECHNICAL_CONFORMANCE_ONLY_NEVER_FORMAL_AUTHORITY" or binding.get("authority_read_count")!=0:raise SystemExit(9)
    try:
        if ns.command=="generate":result=driver.build_staging(ns.stage,bundle["objects"],bundle["authority_entries"],bundle["projection"],binding,ns.schema_root)
        else:result=verifier.verify_and_reseal(ns.stage,bundle["objects"],bundle["authority_entries"],bundle["projection"],binding,ns.schema_root,ns.fault)
        print(json.dumps(result,sort_keys=True));return 0
    except BaseException as exc:
        print(json.dumps({"status":"FAIL_CLOSED_TECHNICAL_CONFORMANCE","error":type(exc).__name__+":"+str(exc),"authority_read_count":0},sort_keys=True),file=sys.stderr);return 2


if __name__=="__main__":raise SystemExit(main())
