"""Real regression for extraction-only recovery of coarse chunk 0."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import mph
import numpy as np


HERE = Path(__file__).resolve().parent
PARTIAL_MPH = HERE / "chunks/coarse/.chunk_000.partial/model.mph"


def load_controller():
    spec = importlib.util.spec_from_file_location("r256_partial_regression", HERE / "run_resumable_256_gate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_existing_partial_reproduces_old_failure_and_extracts_authority_fields():
    controller = load_controller()
    contract = json.loads((HERE / "frozen_run_contract.json").read_text(encoding="utf-8"))
    expected = contract["chunks"]["coarse"][0]["frequencies_hz"]
    client = model = None
    try:
        client = mph.start(cores=4, version="6.4")
        model = client.load(PARTIAL_MPH)
        datasets = [node.tag() for node in list(model / "datasets")]
        assert datasets == ["dset1"]
        frequency = np.asarray(model.evaluate("freq", dataset=list(model / "datasets")[0])).real.reshape(-1)
        mic = np.asarray(model.evaluate("aveop_mic(acpr.p_t)/p_inc", dataset=list(model / "datasets")[0])).reshape(-1)
        assert np.array_equal(frequency, np.asarray(expected))
        assert frequency.size == mic.size == 64
        assert np.all(np.isfinite(mic)) and not np.allclose(mic, 0.0)

        old = "abs(acpr.p_t)^2/(4*rho0*c0^2)+rho0*(abs(acpr.u)^2+abs(acpr.v)^2+abs(acpr.w)^2)/4"
        try:
            model.evaluate(f"intop_all({old})", dataset=list(model / "datasets")[0])
        except Exception as exc:
            assert "rho0" in str(exc)
        else:
            raise AssertionError("Legacy bare rho0/c0 expression unexpectedly succeeded")

        values = controller.evaluate(model, expected)
        assert set(values) == set(controller.FIELDS)
        for key in controller.FIELDS:
            assert values[key].size == 64
            assert np.all(np.isfinite(values[key]))
        assert not np.allclose(values["mic"], 0.0)
    finally:
        if client is not None:
            if model is not None:
                try:
                    client.remove(model)
                except Exception:
                    pass
            client.disconnect()


def test_controller_energy_expression_is_parsed_from_authority_without_bare_material_symbols():
    controller = load_controller()
    expression = controller.authoritative_energy_expression()
    authority_source = controller.AUTHORITY_EXPRESSION_SOURCE.read_text(encoding="utf-8")
    assert "ENERGY_DENSITY" in authority_source
    assert "rho0_nom" in expression and "c0_nom" in expression
    assert "d(acpr.p_t" in expression
    assert "rho0*" not in expression
    assert "c0^" not in expression
