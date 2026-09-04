"""Frozen non-semantic primitives; contains no CAD, generation, or terminal logic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


class PrimitiveError(RuntimeError): pass


def canonical(value:Any)->bytes:
    def walk(x:Any)->None:
        if isinstance(x,float) and (not math.isfinite(x) or (x==0 and math.copysign(1,x)<0)):raise PrimitiveError("NON_CANONICAL_NUMBER")
        if isinstance(x,dict):
            if not all(isinstance(k,str) for k in x):raise PrimitiveError("NON_STRING_KEY")
            for child in x.values():walk(child)
        elif isinstance(x,list):
            for child in x:walk(child)
    walk(value)
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")+b"\n"


def sha_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha_value(value:Any)->str:return sha_bytes(canonical(value))


def sha_file(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1<<20),b""):digest.update(chunk)
    return digest.hexdigest()


def pointer(value:Any,address:str)->Any:
    node=value
    if address=="":return node
    if not address.startswith("/"):raise PrimitiveError("POINTER")
    for raw in address[1:].split("/"):
        token=raw.replace("~1","/").replace("~0","~")
        try:node=node[int(token)] if isinstance(node,list) else node[token]
        except (KeyError,IndexError,TypeError,ValueError) as exc:raise PrimitiveError("POINTER_MISSING:"+address) from exc
    return node


def atomic_bytes(path:Path,data:bytes)->None:
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+".a04")
    if temp.exists():raise PrimitiveError("TEMP_COLLISION")
    try:
        with temp.open("xb") as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    except BaseException:
        if temp.is_file():temp.unlink()
        raise


def atomic_json(path:Path,value:Any)->None:atomic_bytes(path,canonical(value))


def read_canonical(path:Path)->tuple[Any,bytes]:
    raw=path.read_bytes()
    try:value=json.loads(raw.decode("utf-8"))
    except Exception as exc:raise PrimitiveError("JSON_READ:"+path.name) from exc
    if raw!=canonical(value):raise PrimitiveError("NON_CANONICAL:"+path.name)
    return value,raw
