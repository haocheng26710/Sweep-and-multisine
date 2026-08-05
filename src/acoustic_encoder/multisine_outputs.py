"""Structured P8 QC views and software-validation diagnostic plots."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .multisine_qc import MultisineQCAnalysis
from .schemas import save_spectrum


def _write_rows(
    path: Path,
    fieldnames: Iterable[str],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def _clock_drift_row(metrics: str | Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(metrics, Mapping):
        return {
            "availability": "unavailable",
            "estimated_signed_drift_ppm": None,
            "pre_correction_decision": None,
            "correction_mode": None,
            "correction_applied": None,
            "correction_method": None,
            "correction_ratio": None,
            "residual_signed_drift_ppm": None,
            "post_correction_decision": None,
            "magnitude_change_max_abs_db": None,
            "magnitude_change_rms_db": None,
            "final_decision": None,
            "phase_status": None,
        }
    pre = metrics["pre_correction"]
    correction = metrics["correction"]
    post = metrics.get("post_correction") or {}
    return {
        "availability": "available",
        "estimated_signed_drift_ppm": pre["signed_drift_ppm"],
        "pre_correction_decision": pre["decision"],
        "correction_mode": correction["mode"],
        "correction_applied": correction["applied"],
        "correction_method": correction["method"],
        "correction_ratio": correction["ratio"],
        "residual_signed_drift_ppm": post.get("signed_residual_drift_ppm"),
        "post_correction_decision": post.get("decision"),
        "magnitude_change_max_abs_db": post.get("magnitude_change_max_abs_db"),
        "magnitude_change_rms_db": post.get("magnitude_change_rms_db"),
        "final_decision": metrics["final_decision"],
        "phase_status": metrics["phase_status"],
    }


def write_multisine_qc_outputs(
    analysis: MultisineQCAnalysis,
    output_directory: str | Path,
    *,
    refuse_existing: bool = True,
    measurement_summary_filename: str = "measurement_qc.csv",
) -> dict[str, Path]:
    """Write authoritative spectrum plus CSV/PNG audit views without filtering."""
    summary_component = Path(measurement_summary_filename)
    if (
        not measurement_summary_filename.strip()
        or summary_component.name != measurement_summary_filename
        or summary_component.suffix.lower() != ".csv"
    ):
        raise ValueError("measurement_summary_filename must be one CSV filename")
    output = Path(output_directory)
    paths = {
        "transfer_tones_csv": output / "transfer_tones.csv",
        "tone_quality_csv": output / "tone_quality.csv",
        "clock_drift_qc_csv": output / "clock_drift_qc.csv",
        "measurement_qc_csv": output / measurement_summary_filename,
        "spectrum_npz": output / "spectrum_data.npz",
        "spectrum_json": output / "spectrum_data.json",
        "synchronization_diagnostic_png": output
        / "synchronization_diagnostic.png",
        "period_consistency_png": output / "period_consistency.png",
    }
    existing = [path for path in paths.values() if path.exists()]
    if refuse_existing and existing:
        raise FileExistsError(f"P8 QC output already exists: {existing[0]}")
    output.mkdir(parents=True, exist_ok=True)

    spectrum = analysis.spectrum
    transfer_rows = []
    for index, frequency in enumerate(spectrum.frequency_hz):
        transfer_rows.append(
            {
                "frequency_hz": float(frequency),
                "magnitude_db": float(spectrum.magnitude_db[index]),
                "magnitude_linear": (
                    None
                    if spectrum.magnitude_linear is None
                    else float(spectrum.magnitude_linear[index])
                ),
                "phase_rad": (
                    None
                    if spectrum.phase_rad is None
                    else float(spectrum.phase_rad[index])
                ),
                "phase_status": spectrum.phase_status.value,
                "valid_tone": bool(spectrum.valid_mask[index]),
            }
        )
    _write_rows(
        paths["transfer_tones_csv"],
        transfer_rows[0].keys(),
        transfer_rows,
    )

    tone_rows = []
    for record in analysis.tone_quality:
        row = record.to_dict()
        row["qc_reasons"] = ";".join(record.qc_reasons)
        tone_rows.append(row)
    _write_rows(paths["tone_quality_csv"], tone_rows[0].keys(), tone_rows)

    clock_row = _clock_drift_row(spectrum.quality_metrics["clock_drift"])
    _write_rows(
        paths["clock_drift_qc_csv"],
        clock_row.keys(),
        [clock_row],
    )
    non_excited = analysis.measurement_qc["non_excited_energy"]
    clipping = analysis.clipping_metrics
    measurement_row = {
        "sample_id": spectrum.meta.sample_id,
        "status": analysis.measurement_qc["status"],
        "clipping_status": clipping["status"],
        "clipping_sample_count": clipping["sample_count"],
        "clipping_fraction": clipping["fraction"],
        "clipping_channel": clipping["channel"],
        "clipping_longest_run_samples": clipping["longest_run_samples"],
        "missing_tone_count": analysis.measurement_qc["missing_tone_count"],
        "missing_tone_unavailable_count": analysis.measurement_qc[
            "missing_tone_unavailable_count"
        ],
        "non_excited_energy_status": non_excited["status"],
        "non_excited_energy_ratio": non_excited["energy_ratio"],
        "non_excited_bin_count": non_excited["bin_count"],
        "unavailable_items": ";".join(
            analysis.measurement_qc["unavailable_items"]
        ),
        "measurement_meta_valid": spectrum.meta.valid,
        "data_origin": spectrum.meta.data_origin.value,
        "dataset_role": spectrum.meta.dataset_role.value,
        "eligible_for_scientific_analysis": (
            spectrum.meta.eligible_for_scientific_analysis
        ),
    }
    _write_rows(
        paths["measurement_qc_csv"],
        measurement_row.keys(),
        [measurement_row],
    )
    save_spectrum(spectrum, output / "spectrum_data")

    estimate = analysis.estimate
    figure, axis = plt.subplots(figsize=(9, 3.8), constrained_layout=True)
    axis.plot(
        np.arange(estimate.normalized_correlation.size),
        estimate.normalized_correlation,
        color="#285f9e",
        linewidth=0.8,
    )
    axis.axvline(
        estimate.preamble_start_sample,
        color="#b33b33",
        linestyle="--",
        label="preamble start",
    )
    axis.axvline(
        estimate.analysis_start_sample,
        color="#3a7d44",
        linestyle=":",
        label="stable analysis start",
    )
    axis.set(
        title="Preamble synchronization diagnostic (simulated validation)",
        xlabel="Recording sample",
        ylabel="Normalized |correlation|",
    )
    axis.legend(loc="upper right")
    figure.savefig(paths["synchronization_diagnostic_png"], dpi=160)
    plt.close(figure)

    period_magnitude_db = 20.0 * np.log10(
        np.maximum(np.abs(estimate.transfer_by_period), np.finfo(float).tiny)
    )
    figure, axis = plt.subplots(figsize=(9, 4.5), constrained_layout=True)
    for period_index, values in enumerate(period_magnitude_db):
        axis.plot(
            estimate.frequency_hz,
            values,
            linewidth=0.7,
            alpha=0.6,
            label=f"period {period_index + 1}",
        )
    axis.set(
        title="Stable-period transfer consistency (simulated validation)",
        xlabel="Frequency (Hz)",
        ylabel="Transfer magnitude (dB)",
    )
    axis.grid(alpha=0.2)
    axis.legend(ncol=4, fontsize=7)
    figure.savefig(paths["period_consistency_png"], dpi=160)
    plt.close(figure)
    return paths
