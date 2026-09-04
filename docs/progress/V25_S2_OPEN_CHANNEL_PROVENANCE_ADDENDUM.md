# V2.5 S2 four-open-channel provenance addendum

Date: 2026-08-25  
Status: authoritative human-readable provenance clarification

## Clarification

The user explicitly confirmed on 2026-08-25 that the physical S2 `U4SYM` assembly used four open P05 straight-through modules at `0°`, `90°`, `180°`, and `270°`. The diagonal positions `45°`, `135°`, `225°`, and `315°` used P09 solid dummy modules.

The `1 acoustic channels open` text present in all 16 S2 TXT notes is stale note-template metadata. It does not describe the physical S2 assembly and must not be used to reclassify S2 as a one-open-port experiment.

## Authority and scope

This addendum supersedes only the earlier conditional wording that treated the S2 physical four-open identity as awaiting user confirmation. It does not alter measured spectra, sample identities, repeat-selection decisions, statistical results, or scientific eligibility.

The frozen machine-readable analysis file `outputs/supplemental/V25-S1_S2_S3_JOINT_ANALYSIS/analysis_summary.json` is intentionally unchanged. Its fields `qc.physical_four_open_assembly_requires_user_confirmation=true` and `qc.S2_all_notes_declare_one_open_channel=true` remain historical records of the state at analysis time; downstream human-readable interpretation must apply this addendum.

The S3 physical mapping remains `0°→HR01`, `90°→HR03`, `180°→HR05`, `270°→HR07`, with P09 solid dummies at the four diagonal positions. The single stale one-open-channel note in S3 remains a preserved metadata mismatch.

## Preservation statement

- No original S2 or S3 TXT/MDAT file was edited.
- No original note field was rewritten.
- No frozen analysis JSON, artifact manifest, or existing SHA-256 record was modified.
- P01 recorded byte-level SHA-256 identities for all 16 S2 raw TXT files in `outputs/simulation/COMSOL_SCHEME_3A/P01_CONTRACT/input_manifest.csv`.

This clarification is provenance-only and is not new experimental evidence.
