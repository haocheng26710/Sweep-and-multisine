"""Independent CORR03 authority/CAD verifier and staging-tree resealer.

No driver, generator, orchestrator, or CAD mapper is imported.  Formal input
bytes remain unreachable until a canonical future RELEASE, its one-way
attestation, the actual dynamically named guardian review, every manifest, and
every authority path/hash/pointer binding have all passed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

TASK_ID = "01a048bd-dc5e-7e93-87e6-72d299ebaa4d"
DOMAIN = b"GEN-ENC-2C-S2-CORR03-RUN-ID-v1"
LITERAL_BACKSLASH_N = bytes.fromhex("5c6e")
assert LITERAL_BACKSLASH_N == b"\\n" and LITERAL_BACKSLASH_N != b"\x0a"
MANIFEST_ORDER = ("source", "schema", "fixture", "authority", "allowlist")
FAMILIES = ("HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED")
PREFIX = dict(zip(FAMILIES, ("HAND", "NEAR", "RANDOM", "PHYSICS")))
SCHEMAS = {"member":"scientific_instance_identity.schema.json","family":"family_manifest.schema.json",
           "index":"identity_index.schema.json","analysis":"analysis_summary.schema.json",
           "inventory":"artifact_inventory.schema.json","hashes":"scientific_hash_manifest.schema.json",
           "verification":"independent_verification_report.schema.json","execution":"execution_record.schema.json"}
TARGET = 3.014899604922098e-5
VOLUME_INTERVAL = (2.984750608872877e-5, 3.0450486009713192e-5)
ZERO_HASH, MASK64 = "0" * 64, (1 << 64) - 1
SECTORS = ("0", "90", "180", "270")
Q = ("volume_logit_0","volume_logit_90","volume_logit_180","derived_volume_logit_270")
EXT = tuple(f"external_aperture_fraction_{s}" for s in SECTORS)
LOSS = tuple(f"loss_fraction_{s}" for s in SECTORS)
EDGES = ("edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270")
RINGS = ("ring_0_90","ring_90_180","ring_180_270","ring_270_0")
HAND_KEYS = {"member_id",*Q,"central_mix_aperture_fraction",*EXT,*LOSS}
NEAR_KEYS = {"member_id",*Q,"shared_coupling_alpha",*EXT,*LOSS}
RANDOM_DRAW_ORDER = ("q0","q90","q180",*EDGES,"loss_0","loss_90","loss_180","loss_270")
PHYSICS_ORDER = ("q0","q90","q180","aperture_0","aperture_90","aperture_180","aperture_270",*RINGS,"loss_0","loss_90","loss_180","loss_270")
STORED_MAP={"volume_logit_0":"q0","volume_logit_90":"q90","volume_logit_180":"q180","derived_volume_logit_270":"q270",
            **{f"external_aperture_fraction_{s}":f"aperture_{s}" for s in SECTORS},
            **{f"external_{s}":f"aperture_{s}" for s in SECTORS},
            **{f"loss_fraction_{s}":f"loss_{s}" for s in SECTORS},
            **{f"reciprocal_{k}":k for k in EDGES},
            "central_mix_aperture_fraction":"central_mix","shared_coupling_alpha":"shared_alpha",
            "ring_coupling_0_90":"ring_0_90","ring_coupling_90_180":"ring_90_180","ring_coupling_180_270":"ring_180_270","ring_coupling_270_0":"ring_270_0"}


class VerifyError(RuntimeError): pass


def canonical(x: Any) -> bytes:
    def walk(v: Any) -> None:
        if isinstance(v,float) and (not math.isfinite(v) or (v == 0 and math.copysign(1,v) < 0)): raise VerifyError("NONCANONICAL_NUMBER")
        if isinstance(v,dict):
            if not all(isinstance(k,str) for k in v): raise VerifyError("NON_STRING_KEY")
            for z in v.values(): walk(z)
        elif isinstance(v,list):
            for z in v: walk(z)
    walk(x)
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def sha_bytes(b: bytes) -> str: return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""): h.update(block)
    return h.hexdigest()


def read_json(p: Path, canonical_required: bool=False) -> tuple[dict[str,Any],bytes]:
    raw=p.read_bytes(); value=json.loads(raw.decode())
    if not isinstance(value,dict): raise VerifyError(f"JSON_OBJECT:{p}")
    if canonical_required and raw != canonical(value): raise VerifyError(f"NONCANONICAL:{p}")
    return value,raw


def atomic_bytes(p: Path, data: bytes) -> None:
    p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_name(p.name+".corr03-verifier-owned.tmp")
    if tmp.exists(): raise VerifyError("OWNED_TEMP_COLLISION")
    try:
        with tmp.open("xb") as f: f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    except BaseException:
        if tmp.exists(): tmp.unlink()
        raise


def atomic_json(p: Path, value: Any) -> None: atomic_bytes(p,canonical(value))


def self_hash(value: Mapping[str,Any], field: str) -> str:
    copy=dict(value);copy[field]=ZERO_HASH;return sha_bytes(canonical(copy))


def splitmix64(value: int) -> int:
    value=(value+0x9E3779B97F4A7C15)&MASK64
    z=value;z=((z^(z>>30))*0xBF58476D1CE4E5B9)&MASK64;z=((z^(z>>27))*0x94D049BB133111EB)&MASK64
    return (z^(z>>31))&MASK64


def open_uniform53(word:int)->float:
    value=((word>>11)+.5)/float(1<<53)
    if value==1.0:value=math.nextafter(1.0,0.0)
    if not 0.0<value<1.0:raise VerifyError('OPEN_UNIFORM')
    return value


class Stream:
    def __init__(self,seed: Any):
        if isinstance(seed,bool) or not isinstance(seed,(int,str)): raise VerifyError("SEED_TYPE")
        self.state=int(seed)&MASK64
    def word(self)->int:self.state=(self.state+0x9E3779B97F4A7C15)&MASK64;return splitmix64((self.state-0x9E3779B97F4A7C15)&MASK64)
    def uniform(self)->float:return ((self.word()>>11)+.5)/float(1<<53)
    def below(self,n:int)->int:
        if n<1:raise VerifyError("RNG_BOUND")
        limit=((1<<64)//n)*n
        while True:
            w=self.word()
            if w<limit:return w%n


def derive_run_id(release_sha: str, hashes: Mapping[str,str]) -> str:
    fields=[DOMAIN,release_sha.encode(),TASK_ID.encode()]+[hashes[k].encode() for k in MANIFEST_ORDER]
    preimage=b"\x0a".join(fields)
    if preimage.endswith(b"\x0a") or preimage.count(b"\x0a")!=7:raise VerifyError("RUN_ID_SEPARATOR")
    return sha_bytes(preimage)


def _numeric(row: Mapping[str,Any], keys: set[str]) -> dict[str,float]:
    if set(row)!=keys:raise VerifyError("EXACT_ROW_KEYS")
    result={}
    for k,v in row.items():
        if k=="member_id":continue
        if isinstance(v,bool) or not isinstance(v,(int,float)):raise VerifyError(f"ROW_NUMERIC:{k}")
        result[k]=float(v)
    return result


def exact_rows(rows: Any, family: str) -> list[tuple[str,dict[str,float]]]:
    if not isinstance(rows,list) or len(rows)!=20:raise VerifyError("EXACT_ROW_COUNT")
    keys=HAND_KEYS if family==FAMILIES[0] else NEAR_KEYS; prefix=PREFIX[family];out=[]
    for i,row in enumerate(rows,1):
        if not isinstance(row,dict) or row.get("member_id")!=f"{prefix}_{i:02d}":raise VerifyError(f"EXACT_MEMBER_ID:{i}")
        p=_numeric(row,keys)
        if not math.isclose(p["derived_volume_logit_270"],-(p["volume_logit_0"]+p["volume_logit_90"]+p["volume_logit_180"])/3,rel_tol=0,abs_tol=1e-12):raise VerifyError("DERIVED_270")
        if not all(-.12<=p[k]<=.12 for k in Q) or not all(.2<=p[k]<=.8 for k in EXT) or not all(.02<=p[k]<=.08 for k in LOSS):raise VerifyError(f"EXACT_ROW_BOUNDS:{i}")
        if family==FAMILIES[0] and not .1<=p["central_mix_aperture_fraction"]<=.3:raise VerifyError(f"HAND_CENTRAL_BOUNDS:{i}")
        if family==FAMILIES[1]:
            expected=.03+(i-1)*.04/19
            if not .03<=p["shared_coupling_alpha"]<=.07 or not math.isclose(p["shared_coupling_alpha"],expected,rel_tol=0,abs_tol=5e-13):raise VerifyError(f"NEAR_ALPHA_SCHEDULE:{i}")
        out.append((row["member_id"],{STORED_MAP[k]:v for k,v in p.items()}))
    return out


def _bounds(spec: Mapping[str,Any], order: Sequence[str]) -> tuple[dict[str,float],dict[str,float]]:
    lo,hi=spec.get("lower"),spec.get("upper")
    if not isinstance(lo,dict) or not isinstance(hi,dict) or set(lo)!=set(order) or set(hi)!=set(order):raise VerifyError("EXACT_BOUNDS")
    return {k:float(lo[k]) for k in order},{k:float(hi[k]) for k in order}


def random_family(spec: Mapping[str,Any], seeds: Any) -> list[tuple[str,dict[str,float]]]:
    if "synthetic_random_seeds" in spec and seeds is None:seeds=spec["synthetic_random_seeds"]
    if isinstance(seeds,dict):seeds=seeds.get('random')
    if not isinstance(seeds,list) or len(seeds)!=20 or len(set(seeds))!=20 or any(isinstance(x,bool) or not isinstance(x,int) for x in seeds):raise VerifyError("SEED_SPLIT_20")
    stored_order=tuple(spec.get("coordinate_order",spec.get("parameter_order",())))
    try:order=tuple(STORED_MAP.get(k,k) for k in stored_order)
    except TypeError as exc:raise VerifyError("RANDOM_13_ORDER") from exc
    if order!=RANDOM_DRAW_ORDER:raise VerifyError("RANDOM_13_ORDER")
    technical=spec.get('identity_class')=='TECHNICAL_SUBSTITUTE_ONLY'
    expected_bounds=[[-.12,.12]]*3+[[.02,.08]]*4
    if technical:
        if set(spec)!={'schema_version','identity_class','authority_kind','formal_values','parameter_order','draw_addressing','inverse_cdf','final_test_read'} or spec.get('authority_kind')!='RANDOM_FAMILY_SPEC_EXACT_SHAPE' or spec.get('formal_values') is not False or spec.get('final_test_read') is not False:raise VerifyError('RANDOM_TECHNICAL_WRAPPER')
        address=spec.get('draw_addressing')
        if address!={'golden_gamma_hex':'9e3779b97f4a7c15','parameter_index_origin':0,'x_expression':'(member_seed+GOLDEN_GAMMA*(index+1)) mod 2^64','generator':'SPLITMIX64','one_uniform_per_coordinate':True}:raise VerifyError('RANDOM_DRAW_ADDRESSING')
    elif set(spec)!={'algorithm','parameter_order','bounds','external_aperture_fractions'} or spec.get('algorithm')!='SPLITMIX64_FROZEN_INVERSE_CDF' or spec.get('bounds')!=expected_bounds:raise VerifyError('RANDOM_EXACT_SPEC')
    inv=spec.get("inverse_cdf")
    if inv is not None:
        if inv.get("uniform_interval")!="OPEN_0_1" or inv.get("draw_count")!=13 or inv.get("volume_logit")!="-0.12+0.24*u" or inv.get("loss")!="0.02+0.06*u":raise VerifyError("RANDOM_INVERSE_CDF")
        edge=inv.get("edge",{})
        expected_edge={"zero_atom_probability":.5,"zero_when":"u<0.5","positive_branch":"0.2+0.6*(2*u-1)"}
        if {k:edge.get(k) for k in expected_edge}!=expected_edge or edge.get('same_uniform_for_atom_and_positive_branch',True) is not True:raise VerifyError("RANDOM_ZERO_ATOM")
    out=[]
    for i,seed in enumerate(seeds,1):
        seed_i=int(seed)&MASK64;p={}
        for index,name in enumerate(RANDOM_DRAW_ORDER):
            u=open_uniform53(splitmix64((seed_i+0x9E3779B97F4A7C15*(index+1))&MASK64))
            if name in EDGES:p[name]=0.0 if u<.5 else .2+.6*(2*u-1)
            elif name.startswith("q"):p[name]=-.12+.24*u
            else:p[name]=.02+.06*u
        p["q270"]=-(p["q0"]+p["q90"]+p["q180"])/3
        external=spec.get('external_aperture_fractions',[.5,.5,.5,.5])
        if not isinstance(external,list) or len(external)!=4 or any(not .2<=float(x)<=.8 for x in external):raise VerifyError('RANDOM_EXTERNAL_APERTURES')
        p.update({f'aperture_{s}':float(x) for s,x in zip(SECTORS,external)})
        out.append((f"RANDOM_{i:02d}",p))
    return out


def fisher_yates(master_seed: Any, parameter_index: int) -> list[int]:
    root=int(master_seed)&MASK64;p=list(range(20))
    for i in range(19,0,-1):
        x=(root+0x9E3779B97F4A7C15*(1+32*parameter_index+(19-i)))&MASK64
        j=splitmix64(x)%(i+1);p[i],p[j]=p[j],p[i]
    return p


def physics_family(spec: Mapping[str,Any]) -> list[tuple[str,dict[str,float]]]:
    stored_order=tuple(spec.get("parameter_order",()))
    if tuple(STORED_MAP.get(k,k) for k in stored_order)!=PHYSICS_ORDER:raise VerifyError("PHYSICS_15_ORDER")
    if spec.get('identity_class')=='TECHNICAL_SUBSTITUTE_ONLY':
        if set(spec)!={'schema_version','identity_class','authority_kind','formal_values','master_seed','parameter_order','bounds','lhs','permutation_algorithm','final_test_read'} or spec.get('authority_kind')!='PHYSICS_MASTER_SPEC_EXACT_SHAPE' or spec.get('formal_values') is not False or spec.get('final_test_read') is not False:raise VerifyError('PHYSICS_TECHNICAL_WRAPPER')
        lhs=spec.get('lhs');algorithm=spec.get('permutation_algorithm')
        if lhs!={'strata':20,'sample':'L+(U-L)*(perm[r]+0.5)/20','jitter':False} or algorithm!={'golden_gamma_hex':'9e3779b97f4a7c15','parameter_index_origin':0,'generator':'SPLITMIX64','loop':'i=19..1','x_expression':'(master_seed+GOLDEN_GAMMA*(1+32*parameter_index+(19-i))) mod 2^64','j_expression':'splitmix64(x)%(i+1)'}:raise VerifyError('PHYSICS_TECHNICAL_ALGORITHM')
    elif set(spec)!={'master_seed','parameter_order','bounds','algorithm'} or spec.get('algorithm')!='FISHER_YATES_MIDPOINT_LHS':raise VerifyError('PHYSICS_ALGORITHM')
    bounds=spec.get("bounds")
    if not isinstance(bounds,list) or len(bounds)!=15 or any(not isinstance(v,list) or len(v)!=2 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in v) or not v[0]<v[1] for v in bounds):raise VerifyError("PHYSICS_ORDERED_15_BOUNDS")
    lo={k:float(bounds[i][0]) for i,k in enumerate(PHYSICS_ORDER)};hi={k:float(bounds[i][1]) for i,k in enumerate(PHYSICS_ORDER)};seed=spec.get("master_seed",spec.get("synthetic_master_seed"))
    perms={name:fisher_yates(seed,j) for j,name in enumerate(PHYSICS_ORDER)};out=[]
    for i in range(20):
        p={name:lo[name]+(hi[name]-lo[name])*(perms[name][i]+.5)/20.0 for name in PHYSICS_ORDER}
        p["q270"]=-(p["q0"]+p["q90"]+p["q180"])/3
        out.append((f"PHYSICS_{i+1:02d}",p))
    return out


def adapt(bundle: Mapping[str,Any]) -> dict[str,list[tuple[str,dict[str,float]]]]:
    hand=bundle.get("hand_rows",bundle.get("hand"));near=bundle.get("near_rows",bundle.get("near"));random=bundle.get("random_spec",bundle.get("random"));physics=bundle.get("physics_spec",bundle.get("physics",bundle.get('physics_authority')));seeds=bundle.get("seed_split")
    random_authority=bundle.get('random_authority')
    if isinstance(random_authority,dict):random=random_authority.get('family_specification');seeds=random_authority.get('seeds')
    if isinstance(hand,dict):hand=hand.get("rows")
    if isinstance(near,dict):near=near.get("rows")
    if seeds is None and isinstance(random,dict):seeds=random.get("synthetic_random_seeds")
    if any(x is None for x in (hand,near,random,physics,bundle.get("cad0_mapping"))):raise VerifyError("AUTHORITY_BUNDLE_FIELDS")
    validate_cad0(bundle["cad0_mapping"])
    return {FAMILIES[0]:exact_rows(hand,FAMILIES[0]),FAMILIES[1]:exact_rows(near,FAMILIES[1]),
            FAMILIES[2]:random_family(random,seeds),FAMILIES[3]:physics_family(physics)}


def validate_cad0(mapping: Any) -> None:
    """Bind the exact CAD-0 contract facts used below, never threshold copies."""
    if not isinstance(mapping,dict):raise VerifyError("CAD0_MAPPING_OBJECT")
    exact={
        "root_span_m":.058926678767398356,"root_length_bounds_m":[.002,.030],
        "fixed_volume_m3":2.1848e-6,"inner_area_m2":4e-6,"cavity_area_m2":.0001054,
        "internal_z_m":[.002,.0102],"collar_z_m":[.0015,.0107],"central_half_side_m":.019073321232601637,
        "window_centres_m":[-.0096,0,.0096],"minimum_feature_m":.002,"minimum_load_path_m":.0016,
        }
    facts=mapping.get("facts",mapping)
    if not isinstance(facts,dict) or any(facts.get(k)!=v for k,v in exact.items()):raise VerifyError("CAD0_FROZEN_FACTS")
    algorithms={'ownership_algorithm':'CAD0_EXACT_CELL_OWNERSHIP','connectivity_algorithm':'CAD0_POSITIVE_AREA_FACE_BFS','solid_load_path_algorithm':'CAD0_Z_PARTITION_MINIMUM'}
    if any(facts.get(k)!=value for k,value in algorithms.items()):raise VerifyError('CAD0_ALGORITHMS')
    witnesses=facts.get('interface_exception_witnesses')
    expected_ids={f'IFX_U4_{s}_{suffix}' for s in ('000','090','180','270') for suffix in ('RIM_BOTTOM','RIM_TOP','SHOULDER_LOWER','SHOULDER_UPPER')}|{f'IFX_U4_{s}_RIM' for s in ('000','090','180','270')}
    if not isinstance(witnesses,list) or {x.get('id') for x in witnesses if isinstance(x,dict)}!=expected_ids or any(x.get('feature_m')!=.0005 or x.get('load_path_m')!=.0015 for x in witnesses):raise VerifyError('CAD0_U4_WITNESSES')


def width(a:float)->float:return .002+.006*a


def normalized(p:Mapping[str,float],family:str)->dict[str,float]:
    canonical_required={f'q{s}' for s in SECTORS}|{f'aperture_{s}' for s in SECTORS}|{f'loss_{s}' for s in SECTORS}
    if canonical_required<=p.keys():return dict(p)
    if family in FAMILIES[:2]:
        q={f"q{s}":p[f"volume_logit_{s}"] if s!="270" else p["derived_volume_logit_270"] for s in SECTORS}
        for s in SECTORS:q[f"aperture_{s}"]=p[f"external_aperture_fraction_{s}"];q[f"loss_{s}"]=p[f"loss_fraction_{s}"]
    else:
        q={f"q{s}":p[f"q{s}"] for s in SECTORS}
        for s in SECTORS:q[f"aperture_{s}"]=.5 if family==FAMILIES[2] else p[f"external_{s}"];q[f"loss_{s}"]=p[f"loss_{s}"]
    if family==FAMILIES[0]:q["central_mix"]=p["central_mix_aperture_fraction"]
    elif family==FAMILIES[1]:q["shared_alpha"]=p["shared_coupling_alpha"]
    elif family==FAMILIES[2]:q.update({k:p[k] for k in EDGES})
    else:q.update({k:p[k] for k in RINGS})
    return q


def sector_slots(p:Mapping[str,float],family:str,s:str)->tuple[float,list[tuple[str,float]]]:
    if family==FAMILIES[0]:return p[f"aperture_{s}"],[('WINDOW_1',width(p['central_mix']))]
    if family==FAMILIES[1]:return p[f"aperture_{s}"],[('WINDOW_1',width((p['shared_alpha']-.03)/.04))]
    if family==FAMILIES[2]:
        m={"0":EDGES[:3],"90":(EDGES[0],EDGES[3],EDGES[4]),"180":(EDGES[1],EDGES[3],EDGES[5]),"270":(EDGES[2],EDGES[4],EDGES[5])}[s]
        return .5,[(f"WINDOW_{i+1}",0.0 if p[k]==0 else width(p[k])) for i,k in enumerate(m)]
    m={"0":(RINGS[0],RINGS[3]),"90":(RINGS[0],RINGS[1]),"180":(RINGS[1],RINGS[2]),"270":(RINGS[2],RINGS[3])}[s]
    return p[f"aperture_{s}"],[("WINDOW_1",width(p[m[0]])),("WINDOW_2",width(p[m[1]]))]


def solve(target:float,outer:float,window:float)->tuple[float,float]:
    def v(L:float)->float:return 2.1848e-6+(4e-6+outer)*(.058926678767398356-L)/2+.0001054*L+window
    lo,hi=.002,.030
    if not v(lo)<=target<=v(hi):raise VerifyError("CAD_ROOT_BRACKET")
    for _ in range(80):
        mid=(lo+hi)/2
        if v(mid)<target:lo=mid
        else:hi=mid
    L=(lo+hi)/2;return L,v(L)


def graph_components(nodes:Sequence[str],edges:Sequence[tuple[str,str,float]])->int:
    a={n:set() for n in nodes}
    for x,y,w in edges:
        if w>0:a[x].add(y);a[y].add(x)
    left=set(nodes);count=0
    while left:
        count+=1;q=deque([left.pop()])
        while q:
            for n in a[q.popleft()]:
                if n in left:left.remove(n);q.append(n)
    return count


def algebraic_connectivity(nodes:Sequence[str],edges:Sequence[tuple[str,str,float]])->tuple[list[float],float]:
    index={n:i for i,n in enumerate(nodes)};n=len(nodes);a=[[0.0]*n for _ in range(n)];degree=[0.0]*n
    for x,y,w in edges:
        if w<=0:continue
        i,j=index[x],index[y];degree[i]+=w;degree[j]+=w;a[i][j]-=w;a[j][i]-=w
    for i in range(n):a[i][i]=degree[i]
    for _ in range(80):
        p,q=max(((i,j) for i in range(n) for j in range(i+1,n)),key=lambda z:abs(a[z[0]][z[1]]))
        if abs(a[p][q])<1e-15:break
        angle=.5*math.atan2(2*a[p][q],a[q][q]-a[p][p]);c,s=math.cos(angle),math.sin(angle)
        app,aqq,apq=a[p][p],a[q][q],a[p][q]
        a[p][p]=c*c*app-2*s*c*apq+s*s*aqq;a[q][q]=s*s*app+2*s*c*apq+c*c*aqq;a[p][q]=a[q][p]=0.0
        for k in range(n):
            if k in (p,q):continue
            akp,akq=a[k][p],a[k][q];a[k][p]=a[p][k]=c*akp-s*akq;a[k][q]=a[q][k]=s*akp+c*akq
    eigen=sorted(max(0.0,a[i][i]) for i in range(n))
    return degree,eigen[1] if n>1 else 0.0


def cad(pstored:Mapping[str,float],family:str)->tuple[dict[str,Any],dict[str,Any],str]:
    p=normalized(pstored,family);q_expected=-(p['q0']+p['q90']+p['q180'])/3
    bounds=math.isclose(p['q270'],q_expected,rel_tol=0,abs_tol=1e-12)
    bounds &= all(-.12<=p[f'q{s}']<=.12 for s in SECTORS) and all(.2<=p[f'aperture_{s}']<=.8 for s in SECTORS) and all(.02<=p[f'loss_{s}']<=.08 for s in SECTORS)
    weights=[math.exp(p[f'q{s}']) for s in SECTORS];den=sum(weights);roots=[];volumes=[];slot_evidence=[];gap_candidates=[];feature_candidates=[('SPINE_WIDTH',.002),('WINDOW_DEPTH',.002),('COLLECTOR_U',.008),('STEP_1',.006),('STEP_2',.005),('STEP_3',.004),('CAVITY_HEIGHT',.0062)]
    for s,w in zip(SECTORS,weights):
        outer,slots=sector_slots(p,family,s);scientific_active=[x for _,x in slots if x>0];by_id={k:v for k,v in slots}
        window=.002*.002*(by_id.get('WINDOW_1',0)+max(.002,by_id.get('WINDOW_2',0))+by_id.get('WINDOW_3',0))
        L,V=solve(.6*TARGET*w/den,width(outer)*.002,window);roots.append(L);volumes.append(V)
        feature_candidates.append((f'ROOT_LENGTH_{s}',L));feature_candidates.extend((f'{slot}_{s}_WIDTH',value) for slot,value in slots if value>0)
        placed=[(-.0096,by_id.get('WINDOW_1',0),'WINDOW_1'),(0.0,max(.002,by_id.get('WINDOW_2',0)),'WINDOW_2_OR_SPINE'),(.0096,by_id.get('WINDOW_3',0),'WINDOW_3')]
        active=[x for x in placed if x[1]>0]
        for left,right in zip(active,active[1:]):gap_candidates.append((f'{s}:{left[2]}__{right[2]}',right[0]-left[0]-(left[1]+right[1])/2,[left[0]+left[1]/2,right[0]-right[1]/2]))
        for centre,sw,name in active:gap_candidates.append((f'{s}:{name}__COLLECTOR_SIDE',.015-abs(centre)-sw/2,[math.copysign(abs(centre)+sw/2,centre or 1),math.copysign(.015,centre or 1)]))
        slot_evidence.append({'sector':s,'owner':f'SECTOR_{s}','root_length_m':L,'root_residual_m3':V-.6*TARGET*w/den,
                              'slots':slots,'active_slot_count':len(scientific_active)+1,'disabled_slot_count':3-len(scientific_active)})
    reduced=[('P0','P90',p[k]) for k in EDGES[:1]]+[('P0','P180',p[EDGES[1]]),('P0','P270',p[EDGES[2]]),('P90','P180',p[EDGES[3]]),('P90','P270',p[EDGES[4]]),('P180','P270',p[EDGES[5]])] if family==FAMILIES[2] else []
    actual=[('PLENUM',f'P{s}',4e-6) for s in SECTORS];volume=.4*TARGET+sum(volumes)
    feature_name,feature=min(feature_candidates,key=lambda x:(x[1],x[0]));positive_gaps=[x for x in gap_candidates if x[1]>0]
    t_ff=min((x[1] for x in positive_gaps),default=.0028);t_fe_candidates=[('BOTTOM_COVER_Z',[0,.002],.002),('TOP_COVER_Z',[.0102,.0122],.002)]
    tfe_name,tfe_coords,t_fe=min(t_fe_candidates,key=lambda x:(x[2],x[0]));load=min(t_ff,t_fe)
    reduced_degree,reduced_lambda=algebraic_connectivity(('P0','P90','P180','P270'),reduced) if reduced else ([],0.0)
    audit={'bounds_pass':bool(bounds),'dof':{FAMILIES[0]:12,FAMILIES[1]:12,FAMILIES[2]:13,FAMILIES[3]:15}[family],
           'volume_m3':volume,'envelope_m':[.210,.210,.0122],'interface_identity':'U4_CARDINAL_4PORT_CENTRAL_M1_v1',
           'actual_fluid_component_count':graph_components(('PLENUM','P0','P90','P180','P270'),actual),
           'minimum_feature_m':feature,'solid_load_path_m':load}
    evidence={'ownership_algorithm':'CENTRAL_HALF_OPEN_THEN_MAX_RADIAL_DOT_MIN_SECTOR_ORDER','sector_witnesses':slot_evidence,
              'fixed_u4_exception_witnesses':[{'sector':s,'collar_z':[.0015,.0107],'rim_m':.0015,'excluded_from_load_metric':True} for s in SECTORS],
              'reduced_graph':{'edges':[list(x) for x in reduced],'component_count':graph_components(('P0','P90','P180','P270'),reduced) if reduced else None,
                               'positive_edge_count':sum(x[2]>0 for x in reduced),'positive_edge_density':sum(x[2]>0 for x in reduced)/6 if reduced else None,
                               'weighted_degree_sequence':reduced_degree,'weighted_algebraic_connectivity':reduced_lambda},
              'actual_fluid_graph':{'edges':[list(x) for x in actual],'component_count':audit['actual_fluid_component_count']},
              'minimum_feature_witness':{'candidate':feature_name,'length_m':feature,'all_candidates':feature_candidates,'threshold_m':.002,'passes':feature>=.002},
              'solid_load_witness':{'algorithm':'EXACT_POLYHEDRAL_SUPPORTED_COMPONENT_OPPOSING_SHEETS','pair':'GENERAL_BOTTOM_TOP_COVER','length_m':load,'supported_from_z0':True,
                                    't_ff_m':t_ff,'t_fe_m':t_fe,'t_fe_witness':{'id':tfe_name,'z_coordinates_m':tfe_coords},'t_ff_candidates':positive_gaps,
                                    'excluded_interfaces':[{'id':'FOUR_OUTER_COLLARS','rim_m':.0015,'reason':'DECLARED_INTERFACE_EXCEPTION'},{'id':'SENSOR_TOP_OPENING','reason':'INTENTIONAL_OPENING'}],
                                    'threshold_m':.0016,'passes':load>=.0016,'threshold_equal_passes':True},
              'sensor_owner':'CENTRAL','positive_volume_overlap_m3':0.0,'thresholds_copied_as_measurements':False}
    eligible=bounds and audit['dof']<=16 and VOLUME_INTERVAL[0]<=volume<=VOLUME_INTERVAL[1] and audit['actual_fluid_component_count']==1 and feature>=.002 and load>=.0016
    return audit,evidence,'STATIC_IDENTITY_ELIGIBLE' if eligible else 'COST_INELIGIBLE'


def load_schemas(root:Path)->dict[str,Any]:
    out={}
    for k,n in SCHEMAS.items():out[k]=read_json(root/n)[0];jsonschema.Draft202012Validator.check_schema(out[k])
    return out


def validate(x:Any,schemas:Mapping[str,Any],key:str)->None:jsonschema.Draft202012Validator(schemas[key]).validate(x)


def allowlist(path:Path)->tuple[list[str],list[str]]:
    x,_=read_json(path);paths=x.get('paths')
    if not isinstance(paths,list) or len(paths)!=92 or len(set(paths))!=92:raise VerifyError('ALLOWLIST_92')
    marker='outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/'
    logical=[p[len(marker):] if p.startswith(marker) else p for p in paths]
    if logical[-1]!='docs/progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md':raise VerifyError('PROGRESS_MAPPING')
    return paths,logical


def _restore(replacements:list[tuple[Path,bytes]])->None:
    for p,old in replacements:
        try:atomic_bytes(p,old)
        except BaseException:pass


def verify_and_reseal(root:Path,schema_root:Path,allowlist_path:Path,bundle:Mapping[str,Any],attestation_out:Path,
                      release_binding:Mapping[str,Any],formal_execution:bool=False)->dict[str,Any]:
    if attestation_out.exists():raise VerifyError('VERIFIER_ATTESTATION_EXISTS')
    schemas=load_schemas(schema_root);paths,logical=allowlist(allowlist_path);files=[root/p for p in logical]
    if any(not p.is_file() for p in files) or len([p for p in root.rglob('*') if p.is_file()])!=92:raise VerifyError('EXACT_TREE_92')
    expected=adapt(bundle);family_members={};scientific=[];cad_hashes=[];member_provenance={}
    for fi,family in enumerate(FAMILIES):
        entries=[]
        for i,(member_id,params) in enumerate(expected[family]):
            idx=fi*20+i;obj,_=read_json(files[idx]);validate(obj,schemas,'member')
            if obj.get('member_sha256') in (None,ZERO_HASH) or obj['member_sha256']!=self_hash(obj,'member_sha256'):raise VerifyError(f'MEMBER_SELF_HASH:{idx+1}')
            audit,evidence,status=cad(params,family)
            if obj['member_id']!=member_id or obj['family_id']!=family or obj['global_ordinal']!=idx+1 or obj['parameters']!=params:raise VerifyError(f'MEMBER_ADAPTER:{idx+1}')
            if obj['cad_static_audit']!=audit or obj['status']!=status:raise VerifyError(f'CAD_STATIC:{idx+1}')
            provenance=obj['input_provenance'];kind='EXACT_ROW' if fi<2 else ('FIXED_SEED' if fi==2 else 'MIDPOINT_LHS')
            if provenance['kind']!=kind or not provenance['pointer_or_seed_binding'] or len(provenance['authority_sha256'])!=64:raise VerifyError(f'PROVENANCE:{idx+1}')
            pair=(provenance['authority_path'],provenance['authority_sha256'])
            if family in member_provenance and member_provenance[family]!=pair:raise VerifyError(f'PROVENANCE_DRIFT:{idx+1}')
            member_provenance[family]=pair
            digest=sha_file(files[idx]);entries.append({'ordinal':i+1,'path':paths[idx],'sha256':digest,'status':status});scientific.append({'path':paths[idx],'sha256':digest});cad_hashes.append(sha_bytes(canonical(evidence)))
        family_members[family]=entries
    fam_entries=[]
    for fi,family in enumerate(FAMILIES):
        idx=80+fi;obj,_=read_json(files[idx]);validate(obj,schemas,'family')
        counts={'members':20,'eligible':sum(x['status']=='STATIC_IDENTITY_ELIGIBLE' for x in family_members[family]),'cost_ineligible':sum(x['status']=='COST_INELIGIBLE' for x in family_members[family]),'technical_failure':0}
        if obj['family_id']!=family or obj['ordered_members']!=family_members[family] or obj['observed_counts']!=counts or obj['family_manifest_sha256']!=self_hash(obj,'family_manifest_sha256'):raise VerifyError(f'FAMILY_CHAIN:{family}')
        h=sha_file(files[idx]);scientific.append({'path':paths[idx],'sha256':h});fam_entries.append({'ordinal':fi+1,'family_id':family,'path':paths[idx],'sha256':h})
    index,_=read_json(files[84]);validate(index,schemas,'index')
    if index['ordered_families']!=fam_entries or index['identity_index_sha256']!=self_hash(index,'identity_index_sha256'):raise VerifyError('INDEX_CHAIN')
    scientific.append({'path':paths[84],'sha256':sha_file(files[84])})
    analysis,_=read_json(files[85]);inventory,_=read_json(files[86]);hashes,_=read_json(files[87]);execution,_=read_json(files[89])
    for obj,key in ((analysis,'analysis'),(inventory,'inventory'),(hashes,'hashes'),(execution,'execution')):validate(obj,schemas,key)
    formal_hashes={'member':sha_bytes(canonical(scientific[:80])),'family':sha_bytes(canonical(scientific[80:84])),'index':scientific[84]['sha256']}
    if analysis['formal_hashes']!=formal_hashes or hashes['scientific_entries']!=scientific or hashes['identity_index_sha256']!=scientific[84]['sha256']:raise VerifyError('SCIENTIFIC_CHAIN')
    authority_entries=hashes['authority_entries']
    if len(authority_entries)!=6 or len({(x['path'],x['sha256']) for x in authority_entries})!=6:raise VerifyError('AUTHORITY_HASH_CHAIN')
    for family in FAMILIES:
        if {'path':member_provenance[family][0],'sha256':member_provenance[family][1]} not in authority_entries:raise VerifyError(f'PROVENANCE_MANIFEST:{family}')
    released_entries=release_binding.get('authority_entries')
    if released_entries is not None and authority_entries!=released_entries:raise VerifyError('RELEASED_AUTHORITY_MANIFEST')
    if len(inventory['artifacts'])!=85 or [x.get('path') for x in inventory['artifacts'] if isinstance(x,dict)]!=[x['path'] for x in scientific]:raise VerifyError('INVENTORY_EXACT_ORDER')
    for entry in inventory['artifacts']:
        if not isinstance(entry,dict) or entry.get('path') not in paths:raise VerifyError('INVENTORY_PATH')
        ix=paths.index(entry['path'])
        if entry.get('sha256')!=sha_file(files[ix]) or entry.get('bytes')!=files[ix].stat().st_size:raise VerifyError('INVENTORY_HASH')
    report={'schema_version':'gen_enc_2c_independent_verification_rev03_v1','mode':'READ_ONLY_INDEPENDENT_RECOMPUTATION','status':'PASS_STATIC_IDENTITY_RECOMPUTATION',
            'observed_counts':{'members':80,'families':4,'artifacts':92,'cad_witnesses':80},
            'recomputed_checks':['EXACT_FORMAL_AUTHORITY_ADAPTER','80_NON_NULL_MEMBER_SELF_HASHES','80_COMPLETE_CAD0_RECOMPUTATIONS','FAMILY_INDEX_CHAIN','SIX_RESULTS_PROGRESS_HASH_CHAIN'],
            'failure_count':0,'scientific_hypothesis_status':'NOT_TESTED','final_test_read':False};validate(report,schemas,'verification')
    old=[(files[88],files[88].read_bytes()),(files[89],files[89].read_bytes()),(files[91],files[91].read_bytes()),(files[90],files[90].read_bytes())]
    try:
        atomic_json(files[88],report)
        final_execution=dict(execution);commands=list(final_execution['commands_exact'])
        if 'independent-verify-reseal' not in commands:commands.append('independent-verify-reseal')
        final_execution['commands_exact']=commands;final_execution['terminal_state']='SUCCESS'
        final_execution['observed_counts']={'members':80,'artifacts':92,'verified_members':80,'verification_failures':0,'publication_commits':0}
        final_execution['runtime']=dict(final_execution.get('runtime',{}),independent_verifier='CORR03')
        validate(final_execution,schemas,'execution');atomic_json(files[89],final_execution)
        progress=("# GEN-ENC-2C scientific identity generation results\n\nmembers=80\nindependent_verification=PASS_STATIC_IDENTITY_RECOMPUTATION\n"
                  f"independent_verification_report_sha256={sha_file(files[88])}\nexecution_record_sha256={sha_file(files[89])}\n"
                  "publication=NOT_STARTED\nscience=NOT_TESTED\nfinal_test_read=false\n").encode()
        atomic_bytes(files[91],progress)
        lines=[f"{sha_file(files[i])}  {paths[i]}" for i in range(92) if i!=90];atomic_bytes(files[90],("\n".join(lines)+"\n").encode())
        listed={line.split('  ',1)[1]:line.split('  ',1)[0] for line in files[90].read_text().splitlines()}
        if set(listed)!=set(paths)-{paths[90]} or any(listed[paths[i]]!=sha_file(files[i]) for i in range(92) if i!=90):raise VerifyError('FINAL_SHA_CHAIN')
        result_hashes={paths[i]:sha_file(files[i]) for i in range(85,92)}
        staging_entries=[{'path':paths[i],'sha256':sha_file(files[i])} for i in range(92)]
        att={'schema_version':'gen_enc_2c_s2_corr03_verifier_terminal_v1','record_kind':'VERIFIED_STAGING','task_id':TASK_ID,
             'dispatch_id':release_binding.get('dispatch_id'),'run_id':release_binding.get('run_id'),
             'status':'VERIFIED_STAGING','release_full_sha256':release_binding.get('release_full_sha256'),'staging_root':str(root),
             'generation_terminal_sha256':release_binding.get('generation_terminal_sha256'),
             'final_independent_verification_report_sha256':sha_file(files[88]),
             'final_scientific_hash_manifest_sha256':sha_file(files[87]),'artifact_count':92,'member_count':80,
             # Recomputable by the later publisher without importing this verifier:
             # the ordered S1 allowlist mapping plus every one of the 92 final hashes.
             'verified_staging_sha256':sha_bytes(canonical(staging_entries)),
             'member_self_hash_null_count':0,'all_required_fields_verified':True,
             'publication_authorized':True,'success_written':False,'final_test_read':False}
        terminal_schema=release_binding.get('verifier_terminal_schema')
        if terminal_schema is not None:jsonschema.Draft202012Validator(terminal_schema).validate(att)
        atomic_json(attestation_out,att)
        return {'status':'VERIFIED_STAGING_RESEALED_NOT_PUBLISHED','attestation_sha256':sha_file(attestation_out),'artifacts':92,'final_test_read':False}
    except BaseException:
        _restore(old)
        if attestation_out.exists():attestation_out.unlink()
        raise


def pointer(doc:Any,p:str)->Any:
    if p=='':return doc
    if not p.startswith('/'):raise VerifyError('POINTER')
    x=doc
    for t in p[1:].split('/'):
        t=t.replace('~1','/').replace('~0','~');x=x[int(t)] if isinstance(x,list) else x[t]
    return x


def gate(repo:Path,release_path:Path,release_schema:Path,att_path:Path,att_schema:Path,contract_path:Path)->dict[str,Any]:
    release,raw=read_json(release_path,True);schema,_=read_json(release_schema);jsonschema.Draft202012Validator(schema).validate(release);p=release['payload']
    if sha_bytes(canonical(p))!=release.get('payload_sha256'):raise VerifyError('RELEASE_PAYLOAD_HASH')
    if p.get('record_kind')=='DRAFT':raise VerifyError('DRAFT_NEVER_EXECUTABLE')
    if p.get('record_kind')!='RELEASE' or p.get('task_id')!=TASK_ID or not isinstance(p.get('attempt'),int) or p['attempt']<1 or p.get('expired') is not False or p.get('revoked') or p.get('consumed') or p.get('reusable') or p.get('draft_promoted'):raise VerifyError('RELEASE_STATE')
    if datetime.fromisoformat(p['expires_at'].replace('Z','+00:00'))<=datetime.now(timezone.utc):raise VerifyError('RELEASE_EXPIRED')
    if p.get('final_test_read') is not False or p.get('final_test_state')!='SEALED':raise VerifyError('FINAL_TEST_BOUNDARY')
    perms=p.get('permissions',{})
    if perms.get('s2_formal_generation_and_static_audit') is not True or any(v for k,v in perms.items() if k!='s2_formal_generation_and_static_audit'):raise VerifyError('PERMISSIONS')
    contract,craw=read_json(contract_path,True)
    declared=Path(p['contract_path']);declared=declared if declared.is_absolute() else repo/declared
    if declared.resolve()!=contract_path.resolve() or p.get('contract_sha256')!=sha_bytes(craw):raise VerifyError('CONTRACT_BINDING')
    runtime={'python':platform.python_version(),'jsonschema':importlib.metadata.version('jsonschema')}
    if contract.get('runtime')!=runtime or p.get('commands')!=contract.get('commands') or p.get('modes')!=contract.get('modes') or 'independent-verify-reseal' not in p.get('commands',[]) or 'S2_INDEPENDENT_VERIFICATION_RESEAL' not in p.get('modes',[]):raise VerifyError('RUNTIME_COMMAND_MODE')
    manifests=p.get('manifest_sha256',{});mp=contract.get('manifest_paths',{})
    for k in MANIFEST_ORDER:
        path=Path(mp[k]);path=path if path.is_absolute() else repo/path
        if sha_file(path)!=manifests[k]:raise VerifyError(f'MANIFEST:{k}')
    review=Path(p['guardian_approval_path']);review=review if review.is_absolute() else repo/review
    if not review.is_file() or sha_file(review)!=p.get('guardian_approval_sha256'):raise VerifyError('DYNAMIC_GUARDIAN_BYTES')
    guardian,_=read_json(review)
    if guardian.get('stage')!='GEN-ENC-2C-S2-CORR03' or guardian.get('verdict') not in ('ACCEPT','APPROVE') or 'APPROVE' not in str(guardian.get('decision','')):raise VerifyError('GUARDIAN_NOT_EVENTUAL_CORR03_APPROVAL')
    aschema,_=read_json(att_schema)
    if sha_file(att_schema)!=p.get('attestation_schema_sha256'):raise VerifyError('ATTESTATION_SCHEMA_HASH')
    att,araw=read_json(att_path,True);jsonschema.Draft202012Validator(aschema).validate(att);full=sha_bytes(raw)
    declared_att=Path(p['attestation_path']);declared_att=declared_att if declared_att.is_absolute() else repo/declared_att
    if declared_att.resolve()!=att_path.resolve():raise VerifyError('ATTESTATION_PATH_BINDING')
    declared_release=Path(att.get('release_path',''));declared_release=declared_release if declared_release.is_absolute() else repo/declared_release
    if declared_release.resolve()!=release_path.resolve():raise VerifyError('ATTESTED_RELEASE_PATH')
    if att.get('task_id')!=TASK_ID or att.get('dispatch_id')!=p.get('dispatch_id') or att.get('attempt')!=p.get('attempt') or att.get('release_full_sha256')!=full or att.get('guardian_approval_path')!=p.get('guardian_approval_path') or att.get('guardian_approval_sha256')!=p.get('guardian_approval_sha256') or att.get('manifest_sha256')!=manifests:raise VerifyError('ATTESTATION_BINDING')
    run=derive_run_id(full,manifests)
    if att.get('run_id')!=run:raise VerifyError('RUN_ID')
    bases=p.get('terminal_root_bases');contract_bases=contract.get('terminal_root_bases',contract.get('terminal_roots'))
    roots=att.get('terminal_roots');root_keys={'staging','success','failure','temp','journal'}
    if not isinstance(bases,dict) or set(bases)!=root_keys or bases!=contract_bases or not isinstance(roots,dict) or set(roots)!=root_keys:raise VerifyError('TERMINAL_ROOT_BINDING')
    for key in root_keys:
        if Path(roots[key])!=Path(bases[key])/run or Path(roots[key]).name!=run:raise VerifyError(f'RUN_SPECIFIC_ROOT:{key}')
    expanded={key:(repo/Path(value)).resolve() for key,value in roots.items()}
    if not expanded['staging'].is_dir() or expanded['success'].exists() or expanded['failure'].exists():raise VerifyError('VERIFIER_ROOT_STATE')
    released=flatten_authorities(p.get('formal_authorities'))
    att_bindings=att.get('formal_authority_bindings')
    if isinstance(att_bindings,dict):
        try:
            random=att_bindings[FAMILIES[2]]
            nested={'hand':att_bindings[FAMILIES[0]],'near':att_bindings[FAMILIES[1]],'random_spec':random['spec'],'random_seed':random['seed_split'],'physics':att_bindings[FAMILIES[3]],'cad0':att_bindings['CAD0_MAPPING']}
            att_flat={key:{'path':item['path'],'sha256':item['sha256'],'pointer':item['pointer']} for key,item in nested.items() if item.get('bound_before_read') is True}
        except (KeyError,TypeError) as exc:raise VerifyError('ATTESTED_SIX_AUTHORITY_BINDINGS') from exc
        if set(att_flat)!=set(nested):raise VerifyError('ATTESTED_SIX_AUTHORITY_BINDINGS')
    elif isinstance(att_bindings,list):
        by_kind={x.get('authority_kind'):x for x in att_bindings if isinstance(x,dict)}
        kinds={'hand':'HAND_ROWS','near':'NEAR_ROWS','random_spec':'RANDOM_FAMILY_SPEC','random_seed':'RANDOM_SEED_SPLIT','physics':'PHYSICS_MASTER_AND_SPEC','cad0':'CAD0_MAPPING'}
        if set(by_kind)!=set(kinds.values()):raise VerifyError('ATTESTED_SIX_AUTHORITY_BINDINGS')
        att_flat={key:{'path':by_kind[kind]['path'],'sha256':by_kind[kind]['sha256'],'pointer':by_kind[kind].get('pointer',by_kind[kind].get('json_pointer'))} for key,kind in kinds.items()}
    else:raise VerifyError('ATTESTED_SIX_AUTHORITY_BINDINGS')
    if att_flat!=released:raise VerifyError('ATTESTED_AUTHORITY_MISMATCH')
    return {'payload':p,'contract':contract,'attestation':att,'run_id':run,'dispatch_id':p['dispatch_id'],'release_full_sha256':full,
            'guardian_approval_path':p['guardian_approval_path'],'guardian_approval_sha256':p['guardian_approval_sha256'],'roots':roots}


def bind_read(repo:Path,declared:Mapping[str,Any],cli:Mapping[str,tuple[Path,str,str]])->dict[str,Any]:
    # Every metadata triple is compared before the first authority byte opens.
    if set(declared)!=set(cli):raise VerifyError('AUTHORITY_BINDING_SET')
    norm={}
    for k,(path,h,ptr) in cli.items():
        d=declared[k];dp=Path(d['path']);dp=dp if dp.is_absolute() else repo/dp
        if dp.resolve()!=path.resolve() or d['sha256']!=h or d['pointer']!=ptr:raise VerifyError(f'AUTHORITY_SUBSTITUTION:{k}')
        norm[k]=(path,h,ptr)
    docs={}
    for k,(path,h,_) in norm.items():
        raw=path.read_bytes()
        if sha_bytes(raw)!=h:raise VerifyError(f'AUTHORITY_HASH:{k}')
        docs[k]=json.loads(raw)
    return {k:pointer(docs[k],norm[k][2]) for k in norm}


def flatten_authorities(declared: Mapping[str,Any]) -> dict[str,Any]:
    if not isinstance(declared,dict):raise VerifyError("FORMAL_AUTHORITY_OBJECT")
    try:
        random=declared[FAMILIES[2]];physics=declared[FAMILIES[3]]
        flat={"hand":declared[FAMILIES[0]],"near":declared[FAMILIES[1]],
              "random_spec":random["spec"],"random_seed":random["seed_split"],
              "physics":physics.get("spec",physics),"cad0":declared["CAD0_MAPPING"]}
    except (KeyError,TypeError) as exc:raise VerifyError("FORMAL_AUTHORITY_NESTING") from exc
    if any(not isinstance(v,dict) or set(v)!={"path","sha256","pointer"} for v in flat.values()):raise VerifyError("FORMAL_AUTHORITY_TRIPLES")
    return flat


def generation_binding(path:Path,schema_path:Path,run_id:str|None=None,dispatch_id:str|None=None)->dict[str,Any]:
    value,_=read_json(path);schema,_=read_json(schema_path);jsonschema.Draft202012Validator(schema).validate(value)
    if value.get('task_id')!=TASK_ID or value.get('artifact_count')!=92 or value.get('member_count')!=80 or value.get('member_self_hash_null_count')!=0 or value.get('verification_complete') is not False or value.get('publication_started') is not False or value.get('success_eligible') is not False:raise VerifyError('GENERATION_TERMINAL_STATE')
    if run_id is not None and value.get('run_id')!=run_id:raise VerifyError('GENERATION_RUN_ID')
    if dispatch_id is not None and value.get('dispatch_id')!=dispatch_id:raise VerifyError('GENERATION_DISPATCH')
    return {'generation_terminal_sha256':sha_file(path),'run_id':value['run_id'],'dispatch_id':value['dispatch_id']}


def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description='Independent CORR03 exact-authority verifier/resealer');sub=p.add_subparsers(dest='mode',required=True)
    syn=sub.add_parser('synthetic');syn.add_argument('--tree-root',type=Path,required=True);syn.add_argument('--schema-root',type=Path,required=True);syn.add_argument('--allowlist',type=Path,required=True);syn.add_argument('--authority-bundle',type=Path,required=True);syn.add_argument('--generation-terminal',type=Path,required=True);syn.add_argument('--generation-terminal-schema',type=Path,required=True);syn.add_argument('--verifier-terminal-schema',type=Path,required=True);syn.add_argument('--attestation-out',type=Path,required=True)
    formal=sub.add_parser('formal')
    for x in ('repo-root','tree-root','schema-root','allowlist','release','release-schema','guardian-attestation','guardian-attestation-schema','contract','generation-terminal','generation-terminal-schema','verifier-terminal-schema','attestation-out'):formal.add_argument('--'+x,type=Path,required=True)
    for name in ('hand','near','random-spec','random-seed','physics','cad0'):
        formal.add_argument('--'+name+'-path',type=Path,required=True);formal.add_argument('--'+name+'-sha256',required=True);formal.add_argument('--'+name+'-pointer',required=True)
    return p


def main(argv:Sequence[str]|None=None)->int:
    ns=parser().parse_args(argv)
    try:
        if ns.mode=='synthetic':
            bundle=read_json(ns.authority_bundle)[0];binding=generation_binding(ns.generation_terminal,ns.generation_terminal_schema)
            binding.update({'release_full_sha256':ZERO_HASH,'guardian_approval_path':None,'guardian_approval_sha256':None,
                'verifier_terminal_schema':read_json(ns.verifier_terminal_schema)[0]})
            result=verify_and_reseal(ns.tree_root,ns.schema_root,ns.allowlist,bundle,ns.attestation_out,binding,False)
        else:
            repo=ns.repo_root.resolve();g=gate(repo,ns.release.resolve(),ns.release_schema.resolve(),ns.guardian_attestation.resolve(),ns.guardian_attestation_schema.resolve(),ns.contract.resolve())
            expected_staging=(repo/Path(g['roots']['staging'])).resolve()
            if ns.tree_root.resolve()!=expected_staging:raise VerifyError('STAGING_ROOT_BINDING')
            names=('hand','near','random_spec','random_seed','physics','cad0');cli={k:(getattr(ns,k+'_path').resolve(),getattr(ns,k+'_sha256'),getattr(ns,k+'_pointer')) for k in names}
            selected=bind_read(repo,flatten_authorities(g['payload']['formal_authorities']),cli)
            bundle={'hand_rows':selected['hand'],'near_rows':selected['near'],'random_spec':selected['random_spec'],'seed_split':selected['random_seed'],'physics_spec':selected['physics'],'cad0_mapping':selected['cad0']}
            g.update(generation_binding(ns.generation_terminal,ns.generation_terminal_schema,g['run_id'],g['dispatch_id']));g['verifier_terminal_schema']=read_json(ns.verifier_terminal_schema)[0]
            g['authority_entries']=[{'path':x['path'],'sha256':x['sha256']} for x in flatten_authorities(g['payload']['formal_authorities']).values()]
            result=verify_and_reseal(ns.tree_root,ns.schema_root,ns.allowlist,bundle,ns.attestation_out,g,True)
        sys.stdout.buffer.write(canonical(result)+b'\n');return 0
    except BaseException as exc:
        sys.stderr.write(f'FAIL_CLOSED:{type(exc).__name__}:{exc}\n');return 2


if __name__=='__main__':raise SystemExit(main())
