from __future__ import annotations

from dataclasses import replace

import pytest

from acoustic_encoder.research_gate import (
    ResearchGateError,
    RunPurpose,
    enforce_research_gate,
)
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    SourceFormat,
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


def simulated_meta() -> MeasurementMeta:
    return MeasurementMeta(
        sample_id="simulated-sweep-001",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=90.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        acquisition_block_id="B01",
        experiment_step="MOCK_DEV_A",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path="data/mock/example.txt",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="0" * 64,
        provenance_uri="data/mock/mock_manifest.json",
        eligible_for_scientific_analysis=False,
    )


def real_meta() -> MeasurementMeta:
    return replace(
        simulated_meta(),
        sample_id="real-experiment-sweep-001",
        experiment_step="E8",
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_INPUT,
        source_format=SourceFormat.REW_TXT,
        source_path="data/exported_txt/measurement.txt",
        provenance_uri="experiment_logs/E8.json",
        eligible_for_scientific_analysis=True,
    )


def test_research_run_rejects_simulated_input() -> None:
    with pytest.raises(
        ResearchGateError,
        match="simulated-sweep-001.*simulated",
    ):
        enforce_research_gate(RunPurpose.RESEARCH_ANALYSIS, [simulated_meta()])


def test_research_run_rejects_empty_input() -> None:
    with pytest.raises(ResearchGateError, match="at least one"):
        enforce_research_gate(RunPurpose.RESEARCH_ANALYSIS, [])


def test_research_run_rejects_external_reference_fixture() -> None:
    reference = replace(
        simulated_meta(),
        sample_id="official-rew-reference-001",
        data_origin=DataOrigin.EXTERNAL_REFERENCE,
        dataset_role=DatasetRole.PARSER_FIXTURE,
        source_format=SourceFormat.REW_TXT,
        source_path="data/reference/official-rew.txt",
        provenance_uri="https://example.invalid/official-rew-sample",
    )
    with pytest.raises(
        ResearchGateError,
        match="official-rew-reference-001.*external_reference",
    ):
        enforce_research_gate(RunPurpose.RESEARCH_ANALYSIS, [reference])


def test_research_run_accepts_eligible_real_experiment_input() -> None:
    real = real_meta()
    assert enforce_research_gate(RunPurpose.RESEARCH_ANALYSIS, [real]) == (real,)


def test_research_run_rejects_real_input_not_explicitly_eligible() -> None:
    ineligible = replace(real_meta(), eligible_for_scientific_analysis=False)
    with pytest.raises(ResearchGateError, match="eligible=False"):
        enforce_research_gate(RunPurpose.RESEARCH_ANALYSIS, [ineligible])
