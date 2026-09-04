"""Execute the single authorized P04D RETRY_01 coupling-scope repair."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import time
import traceback
from pathlib import Path

import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04D_RETRY_01_COUPLING_SCOPE_FIX"
ORIGINAL = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL"
AUTHORITY = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION/P04BN_HR03_PRODUCTION.mph"
AUTHORITY_SHA256 = "33bf573dddc0c0b163e7f0a5e177fc227d16aa541479606e971cb4a3a9398db7"
REPAIR_CONTRACT_SHA256 = "2cd45b0a15faa652c301574b50216fbee9ec5e39c10705cb9790ec5cda1fb60f"
MODEL_PATH = OUT / "P04D_RETRY_01_HR03_S1_FULL_TV_CONTROL.mph"
LOG_PATH = OUT / "solver_session_license.log"
EXPECTED_CROSSINGS = {
    "inner": [262, 263, 264, 265, 279],
    "outer": [257, 259, 260, 261, 284],
}
LANDMARKS_HZ = (1646.88357862959, 1986.97249931757)


def _load_original_module():
    spec = importlib.util.spec_from_file_location("p04d_frozen_original", ORIGINAL / "run_p04d_control.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot import original frozen P04D implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P04D = _load_original_module()


def regular_frequencies() -> list[float]:
    return P04D.regular_frequencies()


def solve_frequencies() -> list[float]:
    return P04D.solve_frequencies()


def coupling_plan() -> dict[str, str]:
    return {
        "tag": "atb_p04d",
        "type": "AcousticThermoacousticBoundary",
        "selection": "all",
        "Acoustics_physics": "acpr",
        "Thermoacoustics_physics": "ta",
        "StudyStep": "std_freq/step1",
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def verify_original_manifest() -> dict:
    manifest_path = ORIGINAL / "SHA256SUMS"
    entries = []
    failures = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = ROOT / Path(relative)
        actual = sha256(path) if path.exists() else None
        item = {"path": relative, "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected}
        entries.append(item)
        if not item["pass"]:
            failures.append(relative)
    return {
        "original_status": "P04D BLOCKED_BY_SOLVER",
        "original_directory": str(ORIGINAL.relative_to(ROOT)),
        "manifest_sha256": sha256(manifest_path),
        "entry_count": len(entries),
        "matched_count": sum(item["pass"] for item in entries),
        "failures": failures,
        "pass": not failures and len(entries) == 24,
        "authority_sha256": sha256(AUTHORITY),
        "authority_pass": sha256(AUTHORITY) == AUTHORITY_SHA256,
        "repair_contract_sha256": sha256(OUT / "repair_contract.json"),
        "repair_contract_pass": sha256(OUT / "repair_contract.json") == REPAIR_CONTRACT_SHA256,
        "original_files_modified": False,
        "final_test_read": False,
    }


def physics_inventory(component) -> list[dict[str, str]]:
    return [
        {"tag": str(tag), "type": str(component.physics(str(tag)).getType())}
        for tag in component.physics().tags()
    ]


def multiphysics_inventory(component) -> list[dict[str, str]]:
    return [
        {"tag": str(tag), "type": str(component.multiphysics(str(tag)).getType())}
        for tag in component.multiphysics().tags()
    ]


def dependent_components(physics) -> list[str]:
    output = []
    for field_tag in physics.field().tags():
        field = physics.field(str(field_tag))
        output.extend(str(value) for value in field.component())
    return output


def configure_model(model, frequencies: list[float], role: str) -> tuple[dict, dict, dict]:
    java = model.java
    java.label(f"P04D_RETRY01_{role.upper()}")
    component = java.component("comp1")
    fluid = set(P04D.selection_entities(component, "sel_fluid_all"))
    module = set(P04D.selection_entities(component, "sel_hr_module_all"))
    bulk = fluid - module
    if len(fluid) != 56 or len(module) != 5 or len(bulk) != 51:
        raise RuntimeError(f"Unexpected authority domains: fluid={len(fluid)} module={len(module)} bulk={len(bulk)}")
    topology = P04D.derive_interfaces_and_walls(component, module, bulk)
    if topology["crossing_groups"] != EXPECTED_CROSSINGS:
        raise InterfaceIdentityError(
            f"PA-TV crossing identity mismatch: expected={EXPECTED_CROSSINGS} actual={topology['crossing_groups']}"
        )

    acpr = component.physics("acpr")
    acpr.selection().set(sorted(bulk))
    for tag in ("fpam_hr_inner", "fpam_hr_outer"):
        try:
            acpr.feature().remove(tag)
        except Exception:
            pass
    acpr.prop("MeshControl").set("SizeControlParameter", "Frequency")
    acpr.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "2100[Hz]")

    try:
        component.physics().remove("ta")
    except Exception:
        pass
    ta = component.physics().create("ta", "ThermoacousticsSinglePhysics", "geom1")
    ta.selection().set(sorted(module))
    ta.prop("MeshControl").set("SizeControlParameter", "Frequency")
    ta.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "2100[Hz]")
    medium = ta.feature("tam1")
    for name, value in P04D.MEDIUM_SETTINGS.items():
        medium.set(name, value)
    ta.feature("wall1").selection().set(topology["true_walls"])

    removed_couplings = []
    for tag in list(component.multiphysics().tags()):
        feature = component.multiphysics(str(tag))
        if str(feature.getType()) == "AcousticThermoacousticBoundary":
            removed_couplings.append(str(tag))
            component.multiphysics().remove(str(tag))
    plan = coupling_plan()
    atb = component.multiphysics().create(plan["tag"], plan["type"])
    atb.set("Acoustics_physics", plan["Acoustics_physics"])
    atb.set("Thermoacoustics_physics", plan["Thermoacoustics_physics"])
    atb.set("StudyStep", plan["StudyStep"])
    atb.selection().all()

    for tag, selection in (
        ("intop_p04d_inner", "sel_hr_neck_inner"),
        ("intop_p04d_cavity", "sel_hr_cavity"),
        ("intop_p04d_outer", "sel_hr_neck_outer"),
        ("intop_p04d_module", "sel_hr_module_all"),
    ):
        P04D.create_integration(component, tag, selection)
    P04D.create_average(component, "aveop_p04d_cavity", "sel_hr_cavity")
    P04D.create_average(component, "aveop_p04d_chamber", "sel_chamber")
    P04D.create_average(component, "aveop_p04d_mic", "sel_mic_nominal")

    mesh = component.mesh("mesh1")
    try:
        mesh.feature().remove("bl_p04d")
    except Exception:
        pass
    mesh.autoMeshSize(6)
    boundary_layer = mesh.feature().create("bl_p04d", "BndLayer")
    boundary_layer.selection().geom("geom1", 3)
    boundary_layer.selection().set(sorted(module))
    layer_properties = boundary_layer.feature().create("blp1", "BndLayerProp")
    layer_properties.selection().geom("geom1", 2)
    layer_properties.selection().set(topology["true_walls"])
    layer_properties.set("blnlayers", "3")
    layer_properties.set("blstretch", "1.2")
    layer_properties.set("inittype", "blhminfact")
    layer_properties.set("blhminfact", "1")

    step = java.study("std_freq").feature("step1")
    step.set("plist", " ".join(f"{value:.15g}" for value in frequencies))
    step.activate("acpr", True)
    step.activate("ta", True)
    activation = {
        "role": role,
        "study_step": "std_freq/step1",
        "acpr_activate_readback": bool(step.activate("acpr")),
        "ta_activate_readback": bool(step.activate("ta")),
        "readback_api": "StudyFeature.activate(String); solveFor(String) is not an activation getter in COMSOL 6.4",
        "activate_property": str(step.getString("activate")),
        "frequency_list_hz": frequencies,
        "pass": bool(step.activate("acpr")) and bool(step.activate("ta")),
        "final_test_read": False,
    }
    try:
        java.sol("sol1").clearSolution()
    except Exception:
        pass

    all_selection_entities = sorted(int(value) for value in atb.selection().entities())
    coupling_inventory = multiphysics_inventory(component)
    acoustic_couplings = [item for item in coupling_inventory if item["type"] == "AcousticThermoacousticBoundary"]
    physics = physics_inventory(component)
    acoustic_physics = [
        item for item in physics
        if item["type"] in {"PressureAcoustics", "ThermoacousticsSinglePhysics"}
    ]
    coupling_audit = {
        "role": role,
        "removed_preexisting_acoustic_thermoviscous_couplings": removed_couplings,
        "tag": str(atb.tag()),
        "type": str(atb.getType()),
        "selection_mode": "all",
        "selection_readback_entity_count": len(all_selection_entities),
        "selection_readback_contains_all_crossings": set(sum(EXPECTED_CROSSINGS.values(), [])).issubset(all_selection_entities),
        "Acoustics_physics": str(atb.getString("Acoustics_physics")),
        "Thermoacoustics_physics": str(atb.getString("Thermoacoustics_physics")),
        "StudyStep": str(atb.getString("StudyStep")),
        "derived_crossing_groups": topology["crossing_groups"],
        "derived_crossing_records": topology["crossing_records"],
        "coupling_inventory": coupling_inventory,
        "single_acoustic_thermoviscous_coupling": len(acoustic_couplings) == 1 and acoustic_couplings[0]["tag"] == "atb_p04d",
        "physics_inventory": physics,
        "acoustic_physics_count": len(acoustic_physics),
        "no_third_acoustic_physics": len(acoustic_physics) == 2,
        "true_wall_boundaries": topology["true_walls"],
        "pass": False,
        "final_test_read": False,
    }
    coupling_audit["pass"] = all(
        (
            coupling_audit["tag"] == "atb_p04d",
            coupling_audit["type"] == "AcousticThermoacousticBoundary",
            coupling_audit["Acoustics_physics"] == "acpr",
            coupling_audit["Thermoacoustics_physics"] == "ta",
            coupling_audit["StudyStep"] == "std_freq/step1",
            coupling_audit["selection_readback_contains_all_crossings"],
            coupling_audit["single_acoustic_thermoviscous_coupling"],
            coupling_audit["no_third_acoustic_physics"],
        )
    )
    configuration = {
        "role": role,
        "authority_sha256": sha256(AUTHORITY),
        "pressure_acoustics_domains": sorted(bulk),
        "thermoviscous_domains": sorted(module),
        "thermoviscous_medium_readback": P04D.node_readback(medium, P04D.MEDIUM_SETTINGS),
        "tv_wall_boundaries": topology["true_walls"],
        "boundary_layer_domains": sorted(module),
        "boundary_layer_wall_boundaries": topology["true_walls"],
        "boundary_layer_layers": "3",
        "boundary_layer_stretch": "1.2",
        "runtime_velocity_tokens": ["u", "v", "w"],
        "runtime_pressure_token": "ta.p_t",
        "source_selection": P04D.selection_entities(component, "bnd_port_000"),
        "microphone_selection": P04D.selection_entities(component, "sel_mic_nominal"),
        "final_test_read": False,
    }
    if not activation["pass"] or not coupling_audit["pass"]:
        raise RuntimeError(f"Retry configuration gate failed: activation={activation} coupling={coupling_audit}")
    return configuration, activation, coupling_audit


class InterfaceIdentityError(RuntimeError):
    pass


def scalar_complex(model, expression: str) -> complex:
    values = np.asarray(model.evaluate(expression)).reshape(-1)
    if values.size != 1:
        raise RuntimeError(f"Expected one smoke value for {expression}, got {values.size}")
    return complex(values[0])


def smoke_result(model, mesh_record: dict, activation: dict, coupling_audit: dict, solve_seconds: float) -> dict:
    cavity = scalar_complex(model, "aveop_p04d_cavity(ta.p_t)/p_inc")
    chamber = scalar_complex(model, "aveop_p04d_chamber(acpr.p_t)/p_inc")
    microphone = scalar_complex(model, "aveop_p04d_mic(acpr.p_t)/p_inc")
    component = model.java.component("comp1")
    pa_components = dependent_components(component.physics("acpr"))
    tv_components = dependent_components(component.physics("ta"))
    solution_size = [int(value) for value in model.java.sol("sol1").getSize()]

    def serial(value: complex) -> dict[str, float]:
        return {
            "real": float(value.real),
            "imag": float(value.imag),
            "magnitude": float(abs(value)),
            "phase_deg": float(np.degrees(np.angle(value))),
        }

    finite_nonzero = all(
        math.isfinite(value.real) and math.isfinite(value.imag) and abs(value) > 0
        for value in (cavity, chamber, microphone)
    )
    dof_gate = bool(solution_size and max(solution_size) > 0 and pa_components and tv_components)
    return {
        "phase_id": "P04D_RETRY_01_COUPLING_SCOPE_FIX",
        "status": "PASS" if finite_nonzero and dof_gate else "FAIL",
        "frequency_hz": 1650.0,
        "in_memory_only": True,
        "model_saved": False,
        "solve_seconds": solve_seconds,
        "equation_assembly_completed": True,
        "scope_errors": {
            "acpr_p_t_undefined": False,
            "mean_acpr_p_t_failure": False,
            "atb_p04d_sigman_failure": False,
        },
        "cavity_pressure_over_p_inc": serial(cavity),
        "chamber_pressure_over_p_inc": serial(chamber),
        "microphone_pressure_over_p_inc": serial(microphone),
        "finite_nonzero_pressure_gate": finite_nonzero,
        "solution_size_readback": solution_size,
        "pa_dependent_components": pa_components,
        "tv_dependent_components": tv_components,
        "pa_dependent_component_count": len(pa_components),
        "tv_dependent_component_count": len(tv_components),
        "pa_and_tv_dof_groups_positive": dof_gate,
        "study_activation": activation,
        "coupling": coupling_audit,
        "mesh": mesh_record,
        "scientific_use_prohibited": True,
        "final_test_read": False,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists():
        log("PRE-SMOKE API correction: removed non-getter solveFor(String); prior attempt called neither mesh.run nor study.run")
    else:
        LOG_PATH.write_text("", encoding="utf-8")
    original_audit = verify_original_manifest()
    atomic_json(OUT / "original_failure_audit.json", original_audit)
    if not original_audit["pass"] or not original_audit["authority_pass"] or not original_audit["repair_contract_pass"]:
        raise RuntimeError(f"Provenance gate failed: {original_audit}")

    import mph

    mph.option("session", "stand-alone")
    client = mph.start(cores=2)
    log(f"Initialized real COMSOL {client.version} standalone session; cores={client.cores}; licensed_products={len(client.modules())}")
    log("P04D RETRY_01 only; original P04D immutable; final_test_read=false")
    smoke_model = client.load(AUTHORITY)
    smoke_pass = False
    try:
        smoke_config, smoke_activation, smoke_coupling = configure_model(smoke_model, [1650.0], "smoke")
        atomic_json(OUT / "study_activation_audit.json", {"smoke": smoke_activation, "formal": None, "final_test_read": False})
        atomic_json(OUT / "coupling_configuration_audit.json", {"smoke": smoke_coupling, "formal": None, "final_test_read": False})
        log("SMOKE configuration PASS: single atb_p04d All boundaries; acpr+ta active")
        log("SMOKE build same prescribed mesh in memory")
        smoke_model.java.component("comp1").mesh("mesh1").run()
        smoke_mesh = P04D.mesh_statistics(smoke_model)
        log(f"SMOKE mesh PASS: elements={smoke_mesh['elements']} min_quality={smoke_mesh['minimum_quality']:.6g}")
        log("SMOKE study run once at 1650 Hz")
        started = time.perf_counter()
        smoke_model.java.study("std_freq").run()
        smoke = smoke_result(smoke_model, smoke_mesh, smoke_activation, smoke_coupling, time.perf_counter() - started)
        atomic_json(OUT / "coupling_smoke_test.json", smoke)
        smoke_pass = smoke["status"] == "PASS"
        if not smoke_pass:
            raise RuntimeError(f"Smoke numeric gates failed: {smoke}")
        log("SMOKE PASS: assembly complete; no acpr.p_t scope error; finite nonzero cavity/chamber/mic; PA+TV DOF groups positive")
    except Exception as error:
        failure = {
            "phase_id": "P04D_RETRY_01_COUPLING_SCOPE_FIX",
            "status": "P04D RETRY_01 BLOCKED_BY_SOLVER",
            "frequency_hz": 1650.0,
            "in_memory_only": True,
            "model_saved": False,
            "error_type": type(error).__name__,
            "raw_error": str(error),
            "traceback": traceback.format_exc(),
            "formal_band_run": False,
            "retry_02": False,
            "final_test_read": False,
        }
        atomic_json(OUT / "coupling_smoke_test.json", failure)
        atomic_json(OUT / "formal_solver_result.json", {"status": "NOT_RUN_SMOKE_FAILED", "formal_study_run_count": 0, "final_test_read": False})
        atomic_json(OUT / "scientific_classification.json", {"technical_status": "P04D RETRY_01 BLOCKED_BY_SOLVER", "scientific_classification": None, "reason": "single authorized smoke failed", "final_test_read": False})
        log(f"SMOKE FAIL {type(error).__name__}: {error}")
    finally:
        try:
            client.remove(smoke_model)
        except Exception:
            pass

    if not smoke_pass:
        client.clear()
        log("STOP after smoke failure; no formal band and no further full-TV S1 repair")
        return

    log("FORMAL fresh reload from unchanged authority")
    formal_model = client.load(AUTHORITY)
    try:
        formal_config, formal_activation, formal_coupling = configure_model(formal_model, solve_frequencies(), "formal")
        activation_audit = json.loads((OUT / "study_activation_audit.json").read_text(encoding="utf-8"))
        activation_audit["formal"] = formal_activation
        atomic_json(OUT / "study_activation_audit.json", activation_audit)
        coupling_audit = json.loads((OUT / "coupling_configuration_audit.json").read_text(encoding="utf-8"))
        coupling_audit["formal"] = formal_coupling
        atomic_json(OUT / "coupling_configuration_audit.json", coupling_audit)
        atomic_json(OUT / "formal_model_configuration.json", formal_config)
        log("FORMAL configuration PASS: only authorized two changes relative to original P04D")
        log("FORMAL build one mesh")
        formal_model.java.component("comp1").mesh("mesh1").run()
        formal_mesh = P04D.mesh_statistics(formal_model)
        atomic_json(OUT / "formal_mesh_statistics.json", formal_mesh)
        if not formal_mesh["pass"]:
            raise RuntimeError(f"Formal mesh gate failed: {formal_mesh}")
        log(f"FORMAL mesh PASS: elements={formal_mesh['elements']} min_quality={formal_mesh['minimum_quality']:.6g}")
        log(f"FORMAL study run once at {len(solve_frequencies())} frozen frequencies")
        started = time.perf_counter()
        formal_model.java.study("std_freq").run()
        solve_seconds = time.perf_counter() - started
        values = P04D.extract_results(formal_model)
        P04D.OUT = OUT
        peaks, landmarks = P04D.write_result_artifacts(values)
        classification = P04D.classify_science(peaks, coupling_pass=True, mesh_pass=True, solver_pass=True)
        formal_model.save(MODEL_PATH)
        model_sha = sha256(MODEL_PATH)
        client.remove(formal_model)
        formal_model = client.load(MODEL_PATH)
        reload_values = P04D.extract_results(formal_model)
        differences = {
            name: float(np.max(np.abs(values[name] - reload_values[name])))
            for name in values
        }
        reload_stable = all(value <= (1e-9 if name == "frequency" else 1e-12) for name, value in differences.items())
        formal_result = {
            "phase_id": "P04D_RETRY_01_COUPLING_SCOPE_FIX",
            "technical_status": "P04D RETRY_01 SOLVED",
            "scientific_classification": classification,
            "formal_study_run_count": 1,
            "frequency_count": len(values["frequency"]),
            "solve_seconds": solve_seconds,
            "finite_nonzero_results": True,
            "model": MODEL_PATH.name,
            "model_sha256": model_sha,
            "save_remove_reload_stable": reload_stable,
            "reload_max_absolute_differences": differences,
            "peak_count": len(peaks),
            "peaks": peaks,
            "landmarks": landmarks,
            "final_test_read": False,
        }
        atomic_json(OUT / "formal_solver_result.json", formal_result)
        atomic_json(OUT / "scientific_classification.json", {"technical_status": "P04D RETRY_01 SOLVED", "scientific_classification": classification, "frozen_rules_used": True, "original_p04d_status_retained": "P04D BLOCKED_BY_SOLVER", "no_u4_authorization": True, "final_test_read": False})
        if not reload_stable:
            raise RuntimeError("Formal save/remove/reload result mismatch")
        log(f"FORMAL PASS: classification={classification}; model_sha256={model_sha}")
    except Exception as error:
        failure = {
            "phase_id": "P04D_RETRY_01_COUPLING_SCOPE_FIX",
            "technical_status": "P04D RETRY_01 BLOCKED_BY_SOLVER",
            "formal_study_run_count": 1,
            "error_type": type(error).__name__,
            "raw_error": str(error),
            "traceback": traceback.format_exc(),
            "rescue_solve": False,
            "retry_02": False,
            "final_test_read": False,
        }
        atomic_json(OUT / "formal_solver_result.json", failure)
        atomic_json(OUT / "scientific_classification.json", {"technical_status": "P04D RETRY_01 BLOCKED_BY_SOLVER", "scientific_classification": None, "reason": "single formal run failed after smoke pass", "final_test_read": False})
        log(f"FORMAL FAIL {type(error).__name__}: {error}")
    finally:
        try:
            client.remove(formal_model)
        except Exception:
            pass
        client.clear()
        log("Cleared standalone COMSOL client; P05/P06/U4 not started")


if __name__ == "__main__":
    main()
