# DEV-A mock and test plan

Mock data exist only to test software. They cannot support any claim about the acoustic structure.

## Implemented in DEV-A

- Schema invariants and NPZ/JSON hash-checked round trips.
- Legacy config migration without rewriting the original YAML.
- Explicit smoothing definitions and rejection of ambiguous smoothing.
- P7 deterministic WAV generation, integer DFT bins, exact period count, crest factor, target peak, and stable hash.
- A single known synthetic `H(f)` used to produce matching dense sweep TXT and time-domain multisine recordings.
- Direction-dependent U4SYM/U4ENC mock responses, fixed random state, truth CSV, sidecars, and `mock_only` markers.

## Implemented in the provenance guard slice

- Required, hash-backed provenance in `MeasurementMeta`, with hard separation between `external_reference`, `simulated`, and `real_experiment`.
- Safe `software_validation` run-purpose default and strict validation of the two allowed run purposes.
- A research hard gate that rejects empty runs, official reference fixtures, simulated inputs, and real inputs not explicitly eligible for scientific analysis.
- Mock TXT/WAV metadata carrying the actual source SHA-256 and structured `simulated` / `software_validation` declarations in addition to the legacy `mock_only` marker.

## Implemented in the P1 REW import slice

- Flexible `*`/`#` comments and whitespace, TAB, comma, or semicolon numeric delimiters without a frozen literal header string.
- Two-column magnitude-only and three-column magnitude/phase imports returning dense `SpectrumData`.
- Explicit rejection of empty, malformed, mixed-column, non-finite, duplicate/decreasing, too-short, impedance, hash-mismatched, and unresolved-manual-review inputs.
- REW headroom, noise floor, and raw waveform QC recorded as `unavailable` rather than inferred.
- Synthetic format/error fixtures plus byte-immutable regressions for `Artist 3 + Q2070Si`, `REL Sub, No EQ`, and `BW M1`.
- External references with no fabricated experiment identity and enforced `software_validation`-only use.

## Implemented in the P8-A multisine slice

- Configurable S3 leading recording delay, including non-period-aligned capture starts.
- Known-preamble normalized cross-correlation, manifest-driven transient-period discard, and exact stable-period extraction.
- Per-period FFT and `Y/X` transfer calculation at the P7 stimulus tones.
- Explicit complex-spectrum or power period averaging and sparse-tone `SpectrumData` output.
- Hash, stimulus, tone-set, nominal sample-rate, period, and manifest-layout consistency gates.
- `relative_unreliable` phase without a proven shared clock and explicit `unavailable` status for deferred P8-B QC.
- Known-`H(f)` magnitude recovery regression with a provisional synthetic-only tolerance of 0.05 dB.

## Deferred to DEV-B/DEV-C

- Project-specific `real_experiment` REW fixtures and complete pipeline routing beyond the P1 adapter.
- P8-B clock drift correction, missing-tone detection, clipping/leakage/SNR QC, and final phase policy.
- P3 matched FeatureSet construction, P4/P5 metrics/classification, P9 selection, and leakage tests.
- Complete T0–T3 dry-runs and S2 failure reports.

## Remaining real-experiment gate

The three official sample exports validate format only and remain `external_reference`. Before scientific analysis, provide unedited REW Frequency Response TXT exports from this project together with explicit experiment metadata and provenance. A real two-column no-phase export should be retained as an immutable regression if that form occurs in the project workflow.
