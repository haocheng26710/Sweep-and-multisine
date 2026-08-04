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

## Deferred to DEV-B/DEV-C

- Real REW parser fixtures and P1 import tests.
- P8 synchronization, delay/drift detection, transfer recovery, missing tone and clipping QC.
- P3 matched FeatureSet construction, P4/P5 metrics/classification, P9 selection, and leakage tests.
- Complete T0–T3 dry-runs and S2 failure reports.

## Required real REW samples

Before freezing P1, provide 1–3 actual REW Frequency Response TXT exports. Prefer one with phase, one without phase, and any sample containing the real comment/header variation. The mock CSV-like TXT deliberately does not define the real parser format.
