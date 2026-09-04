"""Independent S2-CORR02 verifier.

This module deliberately does not import the formal driver, a generator, an
orchestrator, or either CAD mapper.  Formal authority bytes are not opened
until a new canonical RELEASE and its one-way attestation have been checked
and all four path/hash/pointer bindings have been compared.
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
from typing import Any, Iterable, Mapping, Sequence

import jsonschema

TASK_ID = "01a048bd-dc5e-7e93-87e6-72d299ebaa4d"
DOMAIN = b"GEN-ENC-2C-S2-CORR02-RUN-ID-v1"
LITERAL_BACKSLASH_N = bytes.fromhex("5c6e")
if LITERAL_BACKSLASH_N in DOMAIN or b"\x0a" in DOMAIN:
    raise RuntimeError("RUN_ID_DOMAIN_SEPARATOR_CONTAMINATION")
FAMILIES = (
    "HAND_DESIGNED", "NEAR_INDEPENDENT",
    "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED",
)
PREFIX = dict(zip(FAMILIES, ("HAND", "NEAR", "RANDOM", "PHYSICS")))
SCHEMAS = {
    "member": "scientific_instance_identity.schema.json",
    "family": "family_manifest.schema.json", "index": "identity_index.schema.json",
    "analysis": "analysis_summary.schema.json", "inventory": "artifact_inventory.schema.json",
    "hashes": "scientific_hash_manifest.schema.json",
    "verification": "independent_verification_report.schema.json",
    "execution": "execution_record.schema.json", "failure": "fail_closed_record.schema.json",
}
TARGET = 3.014899604922098e-5
VOLUME_INTERVAL = (2.984750608872877e-5, 3.0450486009713192e-5)
CAPS = (0.227302, 0.227302, 0.0122)
INTERFACE = "U4_CARDINAL_4PORT_CENTRAL_M1_v1"
ROOT_SPAN, ROOT_BOUNDS = 0.058926678767398356, (0.002, 0.030)
FIXED_VOLUME, INNER_AREA, CAVITY_AREA = 2.1848e-6, 4e-6, 0.0001054
ZERO_HASH = "0" * 64


class VerificationError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    def walk(x: Any) -> None:
        if isinstance(x, float) and not math.isfinite(x):
            raise VerificationError("NONFINITE_JSON")
        if isinstance(x, dict):
            if not all(isinstance(k, str) for k in x):
                raise VerificationError("NON_STRING_JSON_KEY")
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path, *, canonical_required: bool = False) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict): raise VerificationError(f"JSON_OBJECT_REQUIRED:{path}")
    if canonical_required and raw != canonical(value): raise VerificationError(f"NONCANONICAL:{path}")
    return value, raw


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".corr02-verifier-owned.tmp")
    if temp.exists(): raise VerificationError("OWNED_TEMP_COLLISION")
    try:
        with temp.open("xb") as stream:
            stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
    except BaseException:
        if temp.exists(): temp.unlink()
        raise


def load_schemas(root: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for key, name in SCHEMAS.items():
        value, _ = read_json(root / name)
        jsonschema.Draft202012Validator.check_schema(value)
        result[key] = value
    return result


def validate(value: Any, schemas: Mapping[str, dict[str, Any]], key: str) -> None:
    jsonschema.Draft202012Validator(schemas[key]).validate(value)


def self_hash(value: Mapping[str, Any], field: str) -> str:
    copy = dict(value); copy[field] = ZERO_HASH
    return sha_bytes(canonical(copy))


def derive_run_id(release_full_sha256: str, manifest_hashes: Mapping[str, str]) -> str:
    ordered = ("source", "schema", "fixture", "authority", "allowlist")
    fields = [DOMAIN, release_full_sha256.encode("ascii"), TASK_ID.encode("ascii")]
    fields.extend(str(manifest_hashes[k]).encode("ascii") for k in ordered)
    encoded = b"\x0a".join(fields)  # separator only; deliberately no final newline
    if encoded.endswith(b"\x0a") or encoded.count(b"\x0a") != 7:
        raise VerificationError("RUN_ID_SEPARATOR_CONTRACT")
    return sha_bytes(encoded)


def _runtime() -> dict[str, str]:
    return {"python": platform.python_version(),
            "jsonschema": importlib.metadata.version("jsonschema")}


def _iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None: raise VerificationError("AUTH_TIMEZONE_REQUIRED")
    return parsed


def _resolve(repo_root: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else repo_root / candidate


def _path_hash_bindings(payload: Mapping[str, Any], contract: Mapping[str, Any], repo_root: Path) -> None:
    manifests = payload.get("manifest_sha256")
    if not isinstance(manifests, dict) or set(manifests) != {"source", "schema", "fixture", "authority", "allowlist"}:
        raise VerificationError("MANIFEST_HASH_ORDER_OR_FIELDS")
    paths = contract.get("manifest_paths")
    if not isinstance(paths, dict) or set(paths) != set(manifests):
        raise VerificationError("MANIFEST_PATH_FIELDS")
    for name in manifests:
        if sha_file(_resolve(repo_root, str(paths[name]))) != manifests[name]:
            raise VerificationError(f"MANIFEST_HASH:{name}")


def authorize(release_path: Path, authorization_schema: Path, attestation_path: Path,
              attestation_schema: Path, contract_path: Path, command: str, mode: str,
              repo_root: Path
              ) -> dict[str, Any]:
    """Validate gate without touching any authority input path."""
    record, raw = read_json(release_path, canonical_required=True)
    schema, _ = read_json(authorization_schema)
    jsonschema.Draft202012Validator(schema).validate(record)
    payload = record.get("payload")
    if not isinstance(payload, dict) or sha_bytes(canonical(payload)) != record.get("payload_sha256"):
        raise VerificationError("AUTH_PAYLOAD_HASH")
    permissions = payload.get("permissions")
    if not isinstance(permissions, dict): raise VerificationError("AUTH_PERMISSIONS_REQUIRED")
    if payload.get("record_kind") == "DRAFT":
        if any(value is not False for value in permissions.values()):
            raise VerificationError("DRAFT_PERMISSION_NOT_FALSE")
        raise VerificationError("DRAFT_NEVER_EXECUTABLE")
    if payload.get("record_kind") != "RELEASE": raise VerificationError("NEW_RELEASE_REQUIRED")
    if payload.get("task_id") != TASK_ID or payload.get("revoked") is not False:
        raise VerificationError("AUTH_TASK_OR_REVOKED")
    if payload.get("consumed") is not False or payload.get("reusable") is not False or payload.get("draft_promoted") is not False:
        raise VerificationError("CONSUMED_REUSABLE_OR_DRAFT_PROMOTION")
    if payload.get("final_test_read") is not False or payload.get("final_test_state") != "SEALED":
        raise VerificationError("FINAL_TEST_BOUNDARY")
    if _iso(str(payload.get("expires_at"))) <= datetime.now(timezone.utc):
        raise VerificationError("EXPIRED_RELEASE_NEVER_REUSED")
    allowed = payload.get("commands")
    modes = payload.get("modes")
    if command not in (allowed or []) or mode not in (modes or []):
        raise VerificationError("AUTH_COMMAND_MODE")
    if payload.get("runtime") != _runtime(): raise VerificationError("AUTH_RUNTIME")
    if permissions.get("s2_formal_generation_and_static_audit") is not True:
        raise VerificationError("S2_PERMISSION_FALSE")
    if any(v is not False for k, v in permissions.items()
           if k != "s2_formal_generation_and_static_audit"):
        raise VerificationError("OUT_OF_SCOPE_PERMISSION")
    # Contract exact bytes are bound by RELEASE SHA-256; canonical exact-byte
    # enforcement is reserved for the RELEASE and one-way attestation.  This
    # intentionally matches the driver's contract semantics.
    contract, contract_raw = read_json(contract_path)
    declared_contract = payload.get("contract_path")
    if _resolve(repo_root, str(declared_contract)).resolve() != contract_path.resolve() or payload.get("contract_sha256") != sha_bytes(contract_raw):
        raise VerificationError("CONTRACT_BINDING")
    _path_hash_bindings(payload, contract, repo_root)
    full_sha = sha_bytes(raw)
    att_schema_hash = sha_file(attestation_schema)
    expected_schema_hash = contract.get("attestation_schema_sha256", payload.get("attestation_schema_sha256"))
    expected_schema_path = contract.get("attestation_schema_path", payload.get("attestation_schema_path"))
    if _resolve(repo_root, str(expected_schema_path)).resolve() != attestation_schema.resolve() or expected_schema_hash != att_schema_hash:
        raise VerificationError("ATTESTATION_SCHEMA_BINDING")
    att, att_raw = read_json(attestation_path, canonical_required=True)
    att_schema, _ = read_json(attestation_schema)
    jsonschema.Draft202012Validator(att_schema).validate(att)
    expected_att_path = contract.get("attestation_path", payload.get("attestation_path"))
    if _resolve(repo_root, str(expected_att_path)).resolve() != attestation_path.resolve():
        raise VerificationError("ATTESTATION_FILE_BINDING")
    if att.get("release_full_sha256") != full_sha or att.get("task_id") != TASK_ID:
        raise VerificationError("ATTESTATION_RELEASE_BINDING")
    review_path = _resolve(repo_root, str(payload.get("guardian_review_path")))
    review_hash = payload.get("guardian_review_sha256")
    if not review_hash or sha_file(review_path) != review_hash:
        raise VerificationError("ACTUAL_GUARDIAN_REVIEW_HASH")
    att_review = att.get("guardian_review_path", payload.get("guardian_review_path"))
    if _resolve(repo_root, str(att_review)).resolve() != review_path.resolve() or att.get("guardian_review_sha256") != review_hash:
        raise VerificationError("ATTESTATION_GUARDIAN_BINDING")
    run_id = derive_run_id(full_sha, payload["manifest_sha256"])
    attempt = payload.get("attempt")
    if not isinstance(attempt, int) or attempt < 1: raise VerificationError("RELEASE_ATTEMPT_REQUIRED")
    if payload.get("run_id") is not None or att.get("run_id") != run_id or att.get("dispatch_id") != payload.get("dispatch_id"):
        raise VerificationError("ATTESTATION_RUN_OR_DISPATCH")
    if att.get("attempt") != attempt or att.get("manifest_sha256") != payload["manifest_sha256"]:
        raise VerificationError("ATTESTATION_ATTEMPT_OR_MANIFEST")
    formal = payload.get("formal_authorities")
    if isinstance(formal, dict):
        kinds = ("HAND_ROWS", "NEAR_ROWS", "RANDOM_SEEDS", "PHYSICS_SEEDS")
        expected_bindings = []
        for family, kind in zip(FAMILIES, kinds):
            binding = formal.get(family)
            if not isinstance(binding, dict): raise VerificationError("ATTESTATION_FORMAL_BINDINGS")
            expected_bindings.append({"authority_kind": kind, "path": binding["path"],
                                      "sha256": binding["sha256"], "json_pointer": binding["pointer"],
                                      "bound_before_read": True})
        if att.get("formal_authority_bindings") != expected_bindings:
            raise VerificationError("ATTESTATION_FORMAL_BINDINGS")
    expanded_roots = att.get("terminal_roots")
    if not isinstance(expanded_roots, dict) or set(expanded_roots) != {"staging", "success", "failure", "temp", "journal"}:
        raise VerificationError("ATTESTATION_EXPANDED_ROOTS")
    for value in expanded_roots.values():
        if run_id not in Path(str(value)).parts:
            raise VerificationError("ATTESTATION_ROOT_RUN_BINDING")
    return {"record": record, "payload": payload, "contract": contract,
            "release_full_sha256": full_sha, "run_id": run_id, "attempt": attempt,
            "expanded_terminal_roots": expanded_roots}


def _pointer(document: Any, pointer: str) -> Any:
    if pointer == "": return document
    if not pointer.startswith("/"): raise VerificationError("JSON_POINTER")
    value = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def bind_then_read_formal(bindings: Mapping[str, tuple[Path, str, str]],
                          payload: Mapping[str, Any], opened: list[str] | None = None,
                          repo_root: Path | None = None) -> dict[str, Any]:
    """Compare all four metadata triples before the first authority byte read."""
    declared_raw = payload.get("formal_authorities")
    aliases = dict(zip(("hand", "near", "random", "physics"), FAMILIES))
    if not isinstance(declared_raw, dict):
        raise VerificationError("FOUR_FORMAL_AUTHORITY_BINDINGS_REQUIRED")
    if set(declared_raw) == set(aliases): declared = declared_raw
    elif set(declared_raw) == set(FAMILIES): declared = {short: declared_raw[full] for short, full in aliases.items()}
    else: raise VerificationError("FOUR_FORMAL_AUTHORITY_BINDINGS_REQUIRED")
    normalized = {}
    for name in ("hand", "near", "random", "physics"):
        path, digest, pointer = bindings[name]
        expected = declared[name]
        expected_path = _resolve(repo_root or Path.cwd(), str(expected.get("path"))) if isinstance(expected, dict) else None
        if not isinstance(expected, dict) or expected_path.resolve() != path.resolve() or expected.get("sha256") != digest or expected.get("pointer") != pointer:
            raise VerificationError(f"FORMAL_BINDING:{name}")
        normalized[name] = (path, digest, pointer)
    # Metadata equality is now complete. Only from this point are authority files opened.
    documents = {}
    for name, (path, digest, _) in normalized.items():
        raw = path.read_bytes()
        if opened is not None: opened.append(name)
        if sha_bytes(raw) != digest: raise VerificationError(f"FORMAL_AUTHORITY_HASH:{name}")
        documents[name] = json.loads(raw.decode("utf-8"))
    return {name: _pointer(documents[name], pointer)
            for name, (_, _, pointer) in normalized.items()}


MASK64 = (1 << 64) - 1


class SplitMix64:
    def __init__(self, seed: int): self.state = int(seed) & MASK64
    def word(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return (z ^ (z >> 31)) & MASK64
    def open_uniform(self) -> float:
        return ((self.word() >> 11) + 0.5) / float(1 << 53)


def splitmix_word(value: int) -> int:
    state = (int(value) + 0x9E3779B97F4A7C15) & MASK64
    z = ((state ^ (state >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


def indexed_open_uniform(seed: int, channel: int) -> float:
    word = splitmix_word((seed + channel * 0x9E3779B97F4A7C15) & MASK64)
    return ((word >> 11) + 0.5) / float(1 << 53)


def _row_parameters(row: Any) -> dict[str, float]:
    if isinstance(row, dict) and isinstance(row.get("parameters"), dict): row = row["parameters"]
    if not isinstance(row, dict) or not row: raise VerificationError("EXACT_ROW_PARAMETERS")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in row.values()):
        raise VerificationError("EXACT_ROW_NUMERIC")
    return {str(k): float(v) for k, v in row.items()}


def _base_parameters(ordinal: int) -> dict[str, float]:
    phase = (ordinal - 10.5) / 100.0
    q0, q90, q180 = phase, -0.6 * phase, 0.2 * phase
    return {"q0": q0, "q90": q90, "q180": q180,
            "q270": -(q0 + q90 + q180) / 3.0,
            "aperture_0": .42 + ordinal / 1000.0,
            "aperture_90": .45 + ordinal / 1200.0,
            "aperture_180": .48 - ordinal / 1500.0,
            "aperture_270": .44 + ordinal / 1800.0,
            "loss_0": .03 + ordinal / 10000.0,
            "loss_90": .035 + ordinal / 11000.0,
            "loss_180": .04 + ordinal / 12000.0,
            "loss_270": .045 + ordinal / 13000.0}


def _bounds(bundle: Mapping[str, Any], section: Mapping[str, Any] | None = None) -> tuple[list[str], dict[str, float], dict[str, float]]:
    section = section or {}
    lower = section.get("lower", bundle.get("lower"))
    upper = section.get("upper", bundle.get("upper"))
    order = section.get("parameter_order", bundle.get("parameter_order"))
    if isinstance(lower, list) and isinstance(upper, list) and isinstance(order, list):
        lower, upper = dict(zip(order, lower)), dict(zip(order, upper))
    if not isinstance(lower, dict) or not isinstance(upper, dict): raise VerificationError("PARAMETER_BOUNDS")
    if order is None: order = list(lower)
    if not isinstance(order, list) or set(order) != set(lower) or set(lower) != set(upper):
        raise VerificationError("PARAMETER_ORDER")
    return [str(x) for x in order], {k: float(v) for k, v in lower.items()}, {k: float(v) for k, v in upper.items()}


def regenerate_random(seed_item: Any, bundle: Mapping[str, Any], ordinal: int) -> dict[str, float]:
    section = bundle.get("random_spec", {})
    seed = seed_item.get("seed") if isinstance(seed_item, dict) else seed_item
    if isinstance(seed, bool) or not isinstance(seed, (int, str)): raise VerificationError("RANDOM_SEED")
    seed = int(seed) & MASK64
    rng = SplitMix64(seed); result = {}
    if not section and "lower" not in bundle:
        result = _base_parameters(ordinal)
        # Independent implementation of the frozen exact-zero atom and the
        # open-uniform nonzero channel; neither endpoint is reachable.
        for channel, name in enumerate(("edge_0_90", "edge_0_180", "edge_0_270",
                                        "edge_90_180", "edge_90_270", "edge_180_270")):
            draw = indexed_open_uniform(seed, channel)
            result[name] = 0.0 if splitmix_word(seed + channel) % 5 == 0 else .2 + .55 * draw
        return result
    order, lower, upper = _bounds(bundle, section)
    zero = section.get("zero_rule", bundle.get("random_zero_rule", {}))
    zero_names = set(zero.get("parameters", ())) if isinstance(zero, dict) else set()
    probability = float(zero.get("probability", 0.0)) if isinstance(zero, dict) else 0.0
    for name in order:
        draw = rng.open_uniform()
        if name in zero_names and draw < probability:
            result[name] = 0.0
        else:
            result[name] = lower[name] + (upper[name] - lower[name]) * draw
    if {"q0", "q90", "q180"} <= result.keys():
        result["q270"] = -(result["q0"] + result["q90"] + result["q180"]) / 3.0
    return result


def regenerate_physics(index: int, lhs: Mapping[str, Any], bundle: Mapping[str, Any]) -> dict[str, float]:
    order, lower, upper = _bounds(bundle, lhs)
    permutations = lhs.get("permutations")
    if not isinstance(permutations, dict) or set(permutations) != set(order):
        raise VerificationError("LHS_PERMUTATIONS")
    result = {}
    for name in order:
        permutation = permutations[name]
        if not isinstance(permutation, list) or len(permutation) != 20 or sorted(permutation) not in (list(range(20)), list(range(1, 21))):
            raise VerificationError(f"LHS_PERMUTATION:{name}")
        cell = int(permutation[index]) - (1 if min(permutation) == 1 else 0)
        u = (cell + 0.5) / 20.0
        result[name] = lower[name] + (upper[name] - lower[name]) * u
    if {"q0", "q90", "q180"} <= result.keys():
        result["q270"] = -(result["q0"] + result["q90"] + result["q180"]) / 3.0
    return result


def regenerate(authorities: Mapping[str, Any]) -> dict[str, list[dict[str, float]]]:
    if authorities.get("schema_version") != "gen_enc_2c_s2_corr02_synthetic_authorities_v1" and "hand" not in authorities:
        raise VerificationError("AUTHORITY_BUNDLE_SCHEMA")
    hand = authorities.get("hand_rows", authorities.get("hand"))
    near = authorities.get("near_rows", authorities.get("near"))
    seeds = authorities.get("random_seeds", authorities.get("random"))
    lhs = authorities.get("physics_lhs", authorities.get("physics"))
    if not all(isinstance(x, list) and len(x) == 20 for x in (hand, near, seeds)) or not isinstance(lhs, dict):
        raise VerificationError("AUTHORITY_4X20_SHAPE")
    return {
        FAMILIES[0]: [_row_parameters(x) for x in hand],
        FAMILIES[1]: [_row_parameters(x) for x in near],
        FAMILIES[2]: [regenerate_random(x, authorities, i + 1) for i, x in enumerate(seeds)],
        FAMILIES[3]: [regenerate_physics(i, lhs, authorities) for i in range(20)],
    }


def synthetic_authorities() -> dict[str, Any]:
    hand, near = [], []
    for ordinal in range(1, 21):
        h = _base_parameters(ordinal); h["central_mix"] = .18 + ordinal / 10000.0; hand.append(h)
        n = _base_parameters(ordinal); n["shared_alpha"] = .03 + (ordinal - 1) * .04 / 19.0; near.append(n)
    names = ("q0", "q90", "q180", "q270", "aperture_0", "aperture_90", "aperture_180",
             "aperture_270", "loss_0", "loss_90", "loss_180", "loss_270",
             "ring_0_90", "ring_90_180", "ring_180_270", "ring_270_0")
    lower = {n: (-.08 if n.startswith("q") else .25 if n.startswith("ring") else
                 .3 if n.startswith("aperture") else .025) for n in names}
    upper = {n: (.08 if n.startswith("q") else .75 if n.startswith("ring") else
                 .7 if n.startswith("aperture") else .065) for n in names}
    permutations = {n: list(range(20)) if i % 2 == 0 else list(reversed(range(20)))
                    for i, n in enumerate(names)}
    return {"schema_version": "gen_enc_2c_s2_corr02_synthetic_authorities_v1",
            "hand_rows": hand, "near_rows": near, "random_seeds": list(range(2201, 2221)),
            "physics_lhs": {"lower": lower, "upper": upper, "permutations": permutations}}


def load_technical_substitute(path: Path | None, repo_root: Path) -> dict[str, Any]:
    if path is None: return synthetic_authorities()
    value, _ = read_json(path)
    if value.get("schema_version") == "gen_enc_2c_s2_corr02_synthetic_authorities_v1": return value
    if value.get("schema_version") != "gen_enc_2c_s2_corr02_technical_substitute_bundle_v1":
        raise VerificationError("TECHNICAL_BUNDLE_SCHEMA")
    entries = value.get("authorities")
    if not isinstance(entries, list) or len(entries) != 4:
        raise VerificationError("TECHNICAL_BUNDLE_FOUR_AUTHORITIES")
    expected_kinds = ("HAND_ROWS_SUBSTITUTE", "NEAR_ROWS_SUBSTITUTE",
                      "RANDOM_SEEDS_SUBSTITUTE", "PHYSICS_SEEDS_SUBSTITUTE")
    for entry, kind in zip(entries, expected_kinds):
        if not isinstance(entry, dict) or entry.get("authority_kind") != kind:
            raise VerificationError("TECHNICAL_BUNDLE_ORDER")
        authority_path = _resolve(repo_root, str(entry.get("path")))
        if sha_file(authority_path) != entry.get("sha256"):
            raise VerificationError(f"TECHNICAL_AUTHORITY_HASH:{kind}")
        authority, _ = read_json(authority_path)
        if authority.get("authority_kind") != kind or authority.get("authorized_for_formal_use") is not False or authority.get("contains_formal_rows") is not False or authority.get("contains_formal_seeds") is not False:
            raise VerificationError(f"TECHNICAL_AUTHORITY_BOUNDARY:{kind}")
    return synthetic_authorities()


def components(nodes: Iterable[str], edges: Iterable[tuple[str, str, float]]) -> int:
    graph = {n: set() for n in nodes}
    for a, b, area in edges:
        if area > 0: graph[a].add(b); graph[b].add(a)
    left, count = set(graph), 0
    while left:
        count += 1; queue = deque([left.pop()])
        while queue:
            for item in graph[queue.popleft()]:
                if item in left: left.remove(item); queue.append(item)
    return count


def _width(x: float) -> float: return 0.002 + 0.006 * x


def _controls(p: Mapping[str, float], family: str, sector: str) -> tuple[float, list[float]]:
    if family == FAMILIES[0]: return p[f"aperture_{sector}"], [_width(p["central_mix"])]
    if family == FAMILIES[1]: return p[f"aperture_{sector}"], [_width((p["shared_alpha"] - .03) / .04)]
    if family == FAMILIES[2]:
        names = {"0": ("edge_0_90", "edge_0_180", "edge_0_270"),
                 "90": ("edge_0_90", "edge_90_180", "edge_90_270"),
                 "180": ("edge_0_180", "edge_90_180", "edge_180_270"),
                 "270": ("edge_0_270", "edge_90_270", "edge_180_270")}[sector]
        return .5, [0.0 if p[n] == 0.0 else _width(p[n]) for n in names]
    names = {"0": ("ring_0_90", "ring_270_0"), "90": ("ring_0_90", "ring_90_180"),
             "180": ("ring_90_180", "ring_180_270"), "270": ("ring_180_270", "ring_270_0")}[sector]
    return p[f"aperture_{sector}"], [_width(p[n]) for n in names]


def _root(target: float, outer: float, extra: float) -> tuple[float, float]:
    def volume(length: float) -> float:
        return FIXED_VOLUME + (INNER_AREA + outer) * (ROOT_SPAN - length) / 2 + CAVITY_AREA * length + extra
    lo, hi = ROOT_BOUNDS
    if not volume(lo) <= target <= volume(hi): raise VerificationError("CAD_ROOT_NOT_BRACKETED")
    for _ in range(80):
        mid = (lo + hi) / 2
        if volume(mid) < target: lo = mid
        else: hi = mid
    length = (lo + hi) / 2
    return length, volume(length)


def recompute_static(p: Mapping[str, float], family: str) -> tuple[dict[str, Any], str]:
    base = {f"q{sector}" for sector in ("0", "90", "180", "270")}
    base |= {f"{stem}_{sector}" for stem in ("aperture", "loss") for sector in ("0", "90", "180", "270")}
    if not base <= p.keys(): raise VerificationError("CAD_REQUIRED_PARAMETER_MISSING")
    q270 = -(p["q0"] + p["q90"] + p["q180"]) / 3
    bounds = math.isclose(p["q270"], q270, rel_tol=0, abs_tol=1e-15)
    bounds &= all(-.12 <= p[n] <= .12 for n in ("q0", "q90", "q180", "q270"))
    bounds &= all(.2 <= p[f"aperture_{s}"] <= .8 for s in ("0", "90", "180", "270"))
    bounds &= all(.02 <= p[f"loss_{s}"] <= .08 for s in ("0", "90", "180", "270"))
    weights = [math.exp(p[f"q{s}"]) for s in ("0", "90", "180", "270")]
    denominator = sum(weights); lengths, volumes = [], []
    for sector, weight in zip(("0", "90", "180", "270"), weights):
        aperture, slots = _controls(p, family, sector)
        slots = (slots + [0.0, 0.0, 0.0])[:3]
        extra = .002 * .002 * (slots[0] + max(.002, slots[1]) + slots[2])
        length, volume = _root(.60 * TARGET * weight / denominator, _width(aperture) * .002, extra)
        lengths.append(length); volumes.append(volume)
    audit = {"bounds_pass": bool(bounds),
             "dof": {FAMILIES[0]: 12, FAMILIES[1]: 12, FAMILIES[2]: 13, FAMILIES[3]: 16}[family],
             "volume_m3": .40 * TARGET + sum(volumes), "envelope_m": [.210, .210, .0122],
             "interface_identity": INTERFACE,
             "actual_fluid_component_count": components(("PLENUM", "P0", "P90", "P180", "P270"),
                                                        (("PLENUM", f"P{s}", INNER_AREA) for s in ("0", "90", "180", "270"))),
             "minimum_feature_m": min(.008, .030, .002, .006, .005, .004, .002, .0062, min(lengths)),
             "solid_load_path_m": .002}
    eligible = bounds and audit["dof"] <= 16 and VOLUME_INTERVAL[0] <= audit["volume_m3"] <= VOLUME_INTERVAL[1]
    eligible &= all(v <= cap for v, cap in zip(audit["envelope_m"], CAPS))
    eligible &= audit["actual_fluid_component_count"] == 1 and audit["minimum_feature_m"] >= .002 and audit["solid_load_path_m"] >= .0016
    return audit, "STATIC_IDENTITY_ELIGIBLE" if eligible else "COST_INELIGIBLE"


def load_allowlist(path: Path) -> list[str]:
    value, _ = read_json(path)
    paths = value.get("paths")
    if not isinstance(paths, list) or len(paths) != 92 or len(set(paths)) != 92:
        raise VerificationError("EXACT_ALLOWLIST_92")
    if value.get("counts") != {"scientific": 85, "result": 6, "progress": 1, "total": 92}:
        raise VerificationError("ALLOWLIST_COUNTS")
    return paths


def _tree_file(root: Path, logical: str) -> Path:
    exact = root / Path(logical)
    marker = "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/"
    relative = root / Path(logical[len(marker):]) if logical.startswith(marker) else root / Path(logical)
    matches = [p for p in (exact, relative) if p.is_file()]
    unique = list(dict.fromkeys(p.resolve() for p in matches))
    if len(unique) != 1: raise VerificationError(f"TREE_PATH_EXACTLY_ONE:{logical}")
    return unique[0]


def _required(obj: Mapping[str, Any], fields: Sequence[str], where: str) -> None:
    missing = [name for name in fields if name not in obj]
    if missing: raise VerificationError(f"MISSING_FIELDS:{where}:{','.join(missing)}")


def verify_tree(root: Path, schema_root: Path, allowlist_path: Path,
                expected: Mapping[str, list[dict[str, float]]]) -> dict[str, Any]:
    schemas = load_schemas(schema_root); paths = load_allowlist(allowlist_path)
    files = [_tree_file(root, p) for p in paths]
    if len({p.resolve() for p in files}) != 92: raise VerificationError("TREE_FILE_ALIAS")
    if len([p for p in root.rglob("*") if p.is_file()]) != 92:
        raise VerificationError("TREE_EXACT_FILE_COUNT_92")
    if any("TECHNICAL_FIXTURE" in p.read_text(encoding="utf-8", errors="strict") for p in files[:91]):
        raise VerificationError("TECHNICAL_WRAPPER_OR_LABEL")
    member_entries, family_slices, provenance_bindings = [], {}, {}
    for fi, family in enumerate(FAMILIES):
        slice_entries = []
        for i in range(20):
            logical = paths[fi * 20 + i]; path = files[fi * 20 + i]
            member, _ = read_json(path)
            _required(member, ("schema_version", "member_id", "family_id", "global_ordinal", "status",
                               "input_provenance", "parameters", "cad_static_audit", "member_sha256"), logical)
            validate(member, schemas, "member")
            params = expected[family][i]; audit, status = recompute_static(params, family)
            if member["family_id"] != family or member["member_id"] != f"{PREFIX[family]}_{i+1:02d}" or member["global_ordinal"] != fi * 20 + i + 1:
                raise VerificationError(f"MEMBER_IDENTITY:{logical}")
            if member["parameters"] != params: raise VerificationError(f"PARAMETER_DISAGREEMENT:{logical}")
            if member["cad_static_audit"] != audit: raise VerificationError(f"CAD_STATIC_DISAGREEMENT:{logical}")
            if member["status"] != status: raise VerificationError(f"STATIC_STATUS_DISAGREEMENT:{logical}")
            provenance = member["input_provenance"]
            expected_kind = "EXACT_ROW" if fi < 2 else ("FIXED_SEED" if fi == 2 else "MIDPOINT_LHS")
            if provenance["kind"] != expected_kind or not provenance["pointer_or_seed_binding"]:
                raise VerificationError(f"PROVENANCE_KIND_OR_POINTER:{logical}")
            binding = (provenance["authority_path"], provenance["authority_sha256"])
            if family in provenance_bindings and provenance_bindings[family] != binding:
                raise VerificationError(f"PROVENANCE_FAMILY_DRIFT:{logical}")
            provenance_bindings[family] = binding
            if member["member_sha256"] not in (None, self_hash(member, "member_sha256")):
                raise VerificationError(f"MEMBER_SELF_HASH:{logical}")
            entry = {"ordinal": i + 1, "path": logical, "sha256": sha_file(path), "status": status}
            member_entries.append({"path": logical, "sha256": entry["sha256"]}); slice_entries.append(entry)
        family_slices[family] = slice_entries
    family_entries = []
    for fi, family in enumerate(FAMILIES):
        logical, path = paths[80 + fi], files[80 + fi]; manifest, _ = read_json(path)
        validate(manifest, schemas, "family")
        if manifest["family_id"] != family or manifest["ordered_members"] != family_slices[family]:
            raise VerificationError(f"FAMILY_CHAIN:{logical}")
        counts = {"members": 20,
                  "eligible": sum(x["status"] == "STATIC_IDENTITY_ELIGIBLE" for x in family_slices[family]),
                  "cost_ineligible": sum(x["status"] == "COST_INELIGIBLE" for x in family_slices[family]),
                  "technical_failure": 0}
        if manifest["observed_counts"] != counts or manifest["family_manifest_sha256"] != self_hash(manifest, "family_manifest_sha256"):
            raise VerificationError(f"FAMILY_FIELDS:{logical}")
        family_entries.append({"ordinal": fi + 1, "family_id": family, "path": logical, "sha256": sha_file(path)})
    index_path = files[84]; index, _ = read_json(index_path); validate(index, schemas, "index")
    if index["ordered_families"] != family_entries or index["observed_counts"] != {"families": 4, "members": 80} or index["identity_index_sha256"] != self_hash(index, "identity_index_sha256"):
        raise VerificationError("INDEX_CHAIN")
    scientific = member_entries + [{"path": x["path"], "sha256": x["sha256"]} for x in family_entries] + [{"path": paths[84], "sha256": sha_file(index_path)}]
    result_keys = ("analysis", "inventory", "hashes", "verification", "execution")
    results = {}
    for offset, key in enumerate(result_keys, 85):
        value, _ = read_json(files[offset]); validate(value, schemas, key); results[key] = value
    expected_formal_hashes = {"member": sha_bytes(canonical(scientific[:80])),
                              "family": sha_bytes(canonical(scientific[80:84])), "index": scientific[84]["sha256"]}
    if results["analysis"]["formal_hashes"] != expected_formal_hashes:
        raise VerificationError("ANALYSIS_HASH_CHAIN")
    inventory = results["inventory"]["artifacts"]
    for entry in inventory:
        actual = _tree_file(root, entry["path"])
        if entry["sha256"] != sha_file(actual) or entry["bytes"] != actual.stat().st_size:
            raise VerificationError(f"INVENTORY_HASH:{entry['path']}")
    hashes = results["hashes"]
    if hashes["scientific_entries"] != scientific or hashes["identity_index_sha256"] != scientific[84]["sha256"]:
        raise VerificationError("SCIENTIFIC_HASH_MANIFEST_CHAIN")
    expected_authorities = [{"path": provenance_bindings[f][0], "sha256": provenance_bindings[f][1]}
                            for f in FAMILIES]
    if hashes["authority_entries"] != expected_authorities:
        raise VerificationError("AUTHORITY_PROVENANCE_HASH_CHAIN")
    sha_lines = files[90].read_text(encoding="utf-8").splitlines()
    listed = {}
    for line in sha_lines:
        if not line or line.startswith("#"): continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or parts[1] in listed: raise VerificationError("SHA256SUMS_FORMAT")
        listed[parts[1]] = parts[0]
    for logical, actual in zip(paths, files):
        if logical == paths[90]: continue
        if listed.get(logical) != sha_file(actual): raise VerificationError(f"SHA256SUMS:{logical}")
    if set(listed) != set(paths) - {paths[90]}: raise VerificationError("SHA256SUMS_PATH_SET")
    progress_hash = sha_file(files[91])
    if listed.get(paths[91]) != progress_hash: raise VerificationError("PROGRESS_EXACT_MAPPING_HASH")
    return {"members": 80, "families": 4, "artifacts": 92, "failures": 0,
            "formal_hashes": expected_formal_hashes, "progress_sha256": progress_hash,
            "result_sha256": {paths[i]: sha_file(files[i]) for i in range(85, 92)}}


def _terminal(control_root: Path, success: bool, counts: Mapping[str, int], schemas: Mapping[str, Any] | None,
              error: str | None, run_id: str | None, attempt: int,
              terminal_schema: Mapping[str, Any] | None = None,
              dispatch_id: str | None = None) -> Path:
    success_path, failure_path = control_root / "VERIFIED_SUCCESS.json", control_root / "FAIL_CLOSED.json"
    if success_path.exists() or failure_path.exists(): raise VerificationError("TERMINAL_ALREADY_EXISTS")
    if success:
        value = {"schema_version": "gen_enc_2c_s2_corr02_terminal_v1", "terminal_state": "VERIFIED_SUCCESS",
                 "task_id": TASK_ID, "run_id": run_id, "attempt": attempt, "observed_counts": dict(counts),
                 "formal_instance_count": counts.get("members", 0), "scientific_hypothesis_status": "NOT_TESTED",
                 "final_test_read": False}
        target = success_path
    else:
        detail = str(error or "UNKNOWN")[:2048]
        if terminal_schema is not None:
            value = {"schema_version": "gen_enc_2c_s2_corr02_fail_closed_terminal_v1",
                     "terminal_kind": "FAIL_CLOSED", "terminal_status": "FAIL_CLOSED_S2_CORR02_INCOMPLETE",
                     "task_id": TASK_ID, "dispatch_id": dispatch_id, "attempt": attempt, "run_id": run_id,
                     "fatal_stage": detail.split(":", 1)[0], "error_code": detail,
                     "error_sha256": sha_bytes(detail.encode("utf-8")),
                     "observed_counts": {
                         "formal_authority_files_read": counts.get("formal_authorities_opened", 0),
                         "formal_rows_read": counts.get("formal_rows_read", 0),
                         "formal_seeds_read": counts.get("formal_seeds_read", 0),
                         "formal_members_created": counts.get("members", 0),
                         "formal_paths_existing": min(92, counts.get("artifacts", 0)),
                         "published_paths": counts.get("published_paths", 0),
                         "static_eligibility_runs": counts.get("static_eligibility_runs", 0),
                         "final_test_reads": 0},
                     "formal_hashes": {"member": None, "family": None, "index": None,
                                       "results": None, "progress": None},
                     "package_terminal_count": 1, "atomic_write": True,
                     "evidence_level": "E1_TECHNICAL_PREEXECUTION_CORRECTION_ONLY",
                     "scientific_hypothesis_status": "NOT_TESTED", "final_test_read": False}
            jsonschema.Draft202012Validator(terminal_schema).validate(value)
        else:
            value = {"schema_version": "gen_enc_2c_fail_closed_record_rev03_s1_v1", "record_kind": "TECHNICAL_FAIL_CLOSED",
                     "task_id": TASK_ID, "error_code": detail,
                     "observed_counts": {k: max(0, int(v)) for k, v in counts.items()},
                     "evidence_level": "E1_TECHNICAL_IMPLEMENTATION_CONFORMANCE_ONLY",
                     "scientific_hypothesis_status": "NOT_TESTED", "formal_instance_count": 0,
                     "static_eligibility_run_count": 0,
                     "formal_hashes": {"member": None, "family": None, "index": None}, "final_test_read": False}
            if schemas is not None: validate(value, schemas, "failure")
        target = failure_path
    atomic_json(target, value)
    if success_path.exists() == failure_path.exists(): raise VerificationError("TERMINAL_EXACTLY_ONE")
    return target


def _root_has_run_id(root: Path, run_id: str) -> None:
    if run_id not in root.parts: raise VerificationError("RUN_SPECIFIC_ROOT_REQUIRED")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    counts = {"members": 0, "families": 0, "artifacts": 0, "failures": 1}
    run_id = None; attempt = 0; schemas = None; formal_opened: list[str] = []; auth = None
    control = Path(args.control_root)
    try:
        repo_root = Path(args.repo_root).resolve()
        release_mode = "TECHNICAL_SUBSTITUTE" if args.mode == "technical-substitute" else "S2_GENERATE_STATIC"
        auth = authorize(Path(args.release), Path(args.authorization_schema), Path(args.attestation),
                         Path(args.attestation_schema), Path(args.contract), "independent-verify", release_mode,
                         repo_root)
        run_id, attempt = auth["run_id"], auth["attempt"]
        _root_has_run_id(Path(args.tree_root), run_id); _root_has_run_id(control, run_id)
        roots = auth["expanded_terminal_roots"]
        resolved_roots = {k: _resolve(repo_root, str(v)).resolve() for k, v in roots.items()}
        if Path(args.tree_root).resolve() != resolved_roots["staging"]:
            raise VerificationError("STAGING_ROOT_ATTESTATION_BINDING")
        if control.resolve() not in (resolved_roots["success"], resolved_roots["failure"]):
            raise VerificationError("CONTROL_ROOT_ATTESTATION_BINDING")
        if args.mode == "technical-substitute":
            technical = Path(args.technical_authority).resolve() if args.technical_authority else None
            fixture_default = technical.parent if technical else repo_root / "tests/fixtures/gen_enc_2c_s2_corr02"
            fixture_root = _resolve(repo_root, str(auth["contract"].get("technical_fixture_root", fixture_default))).resolve()
            if technical is not None and fixture_root not in technical.parents:
                raise VerificationError("TECHNICAL_AUTHORITY_BOUNDARY")
            if auth["payload"].get("authority_mode") not in (None, "SYNTHETIC_SUBSTITUTE"):
                raise VerificationError("TECHNICAL_AUTHORITY_MODE")
            expected = regenerate(load_technical_substitute(technical, repo_root))
        else:
            bindings = {name: (Path(getattr(args, f"{name}_path")).resolve(), getattr(args, f"{name}_sha"),
                               getattr(args, f"{name}_pointer"))
                        for name in ("hand", "near", "random", "physics")}
            authorities = bind_then_read_formal(bindings, auth["payload"], formal_opened, repo_root)
            # Normalize four formal pointer values to the exact regeneration bundle shape.
            bundle = {"schema_version": "gen_enc_2c_s2_corr02_synthetic_authorities_v1",
                      "hand_rows": authorities["hand"], "near_rows": authorities["near"],
                      "random_seeds": authorities["random"]["seeds"] if isinstance(authorities["random"], dict) else authorities["random"],
                      "physics_lhs": authorities["physics"]}
            for key in ("parameter_order", "lower", "upper", "random_spec"):
                for source in authorities.values():
                    if isinstance(source, dict) and key in source: bundle[key] = source[key]
            expected = regenerate(bundle)
        result = verify_tree(Path(args.tree_root), Path(args.schema_root), Path(args.allowlist), expected)
        counts = {"members": 80, "families": 4, "artifacts": 92, "failures": 0}
        _terminal(control, True, counts, schemas, None, run_id, attempt,
                  dispatch_id=auth["payload"].get("dispatch_id"))
        return {"status": "VERIFIED_SUCCESS", "run_id": run_id, "attempt": attempt,
                "observed_counts": counts, "hash_chain": result, "final_test_read": False}
    except BaseException as exc:
        try:
            tree = Path(args.tree_root)
            observed_files = [p for p in tree.rglob("*") if p.is_file()] if tree.exists() else []
            counts = {"members": sum(p.name.endswith(".identity.json") for p in observed_files),
                      "families": sum(p.name.endswith(".manifest.json") for p in observed_files),
                      "artifacts": len(observed_files), "formal_authorities_opened": len(formal_opened),
                      "failures": 1}
        except BaseException:
            counts = {"members": 0, "families": 0, "artifacts": 0,
                      "formal_authorities_opened": len(formal_opened), "failures": 1}
        try:
            if schemas is None and getattr(args, "schema_root", None):
                try: schemas = load_schemas(Path(args.schema_root))
                except BaseException: schemas = None
            terminal_schema = None
            candidate = Path(args.repo_root) / "schemas/gen_enc/gen_enc_2c_s2_corr02/fail_closed_terminal.schema.json"
            if candidate.is_file(): terminal_schema = read_json(candidate)[0]
            _terminal(control, False, counts, schemas, f"{type(exc).__name__}:{exc}", run_id, attempt,
                      terminal_schema, auth["payload"].get("dispatch_id") if auth else None)
        except BaseException as marker_exc:
            raise VerificationError(f"FATAL_AND_MARKER_FAILURE:{exc};{marker_exc}") from exc
        return {"status": "FAIL_CLOSED", "run_id": run_id, "attempt": attempt,
                "error": f"{type(exc).__name__}:{exc}", "observed_counts": counts,
                "formal_input_read_count": len(formal_opened), "final_test_read": False}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Independent release-gated CORR02 verifier")
    sub = result.add_subparsers(dest="mode", required=True)
    common = argparse.ArgumentParser(add_help=False)
    for flag in ("repo-root", "tree-root", "control-root", "schema-root", "allowlist", "release", "attestation",
                 "contract", "authorization-schema", "attestation-schema"):
        common.add_argument("--" + flag, required=True)
    synthetic = sub.add_parser("technical-substitute", aliases=["synthetic"], parents=[common])
    synthetic.add_argument("--technical-authority")
    formal = sub.add_parser("formal", parents=[common])
    for name in ("hand", "near", "random", "physics"):
        formal.add_argument(f"--{name}-path", required=True)
        formal.add_argument(f"--{name}-sha256", f"--{name}-sha", dest=f"{name}_sha", required=True)
        formal.add_argument(f"--{name}-pointer", required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.mode == "synthetic": args.mode = "technical-substitute"
    outcome = execute(args)
    sys.stdout.buffer.write(canonical(outcome) + b"\n")
    return 0 if outcome["status"] == "VERIFIED_SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
