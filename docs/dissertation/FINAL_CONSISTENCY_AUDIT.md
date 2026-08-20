# Final Consistency Audit

## Audit scope

This audit covers `EXPERIMENTAL_CHAPTERS_FINAL.md`, its citation register, the frozen WRITE-2 assets and the FORMAL-3/4/5 claim boundary. No statistic was recalculated and no figure was regenerated.

## Authority checks

| Check | Result | Evidence |
|---|---|---|
| FORMAL-3 selection | pass | 72 ACTIVE, 19 EXCLUDED; selection unchanged |
| Outlier policy | pass | 10 ACTIVE flags retained; sensitivity only |
| FORMAL-4 synthesis gate | pass | `ready_for_formal_synthesis=true` in the frozen authority |
| FORMAL-5 disposition | pass | `supported_with_limits` |
| Hypotheses | pass | `H0=not_rejected`; `H1=not_confirmed` |
| Scientific eligibility | pass | `scientifically_eligible=false` |
| Final-test | pass | sealed; `final_test_read=false` |
| Analysis/selection changes | pass | none during WRITE-4 |

## Authoritative number checks

| Quantity | Required value | Final chapter | Result |
|---|---:|---:|---|
| ACTIVE / EXCLUDED | 72 / 19 | 72 / 19 | pass |
| Repeatability median | 0.3783 dB | 0.3783 dB | pass |
| Repeatability IQR | 0.2191 dB | 0.2191 dB | pass |
| Repeatability p95 | 0.8793 dB | 0.8793 dB | pass |
| U4ENC G / 95% CI | 1.2805 / 0.8297–1.7667 | exact | pass |
| U4SYM G / 95% CI | 0.6824 / 0.6105–1.2699 | exact | pass |
| Delta G / 95% CI | 0.5982 / -0.1131–1.0843 | exact | pass |
| Stable direction pairs | 6/6; 3/6 | exact | pass |
| AS01 effect/floor | 1.5688 | 1.5688 | pass |
| U4SYM BA / macro-F1 | 0.375 / 0.250 | exact | pass |
| U4ENC BA / macro-F1 | 0.250 / 0.183 | exact | pass |
| BA practical target | 0.50 | 0.50 | pass |

## Preprocessing consistency

The final Methods section records the 200–8000 Hz range, 48 points per octave, 1/12-octave dB smoothing and the 200–4000/4000–8000 Hz primary/secondary bands.

It also records that the 200 Hz boundary stayed invalid and that no interpolation or smoothing crossed an invalid or missing-frequency gap.

## Figure and table audit

The final chapter references Figure 1 through Figure 7 and Table 1 through Table 4. Every relative target exists.

The WRITE-2 manifest verifies seven figure groups as 14 PNG/SVG files and four table groups as eight CSV/Markdown files. All stored SHA-256 values match, and every PNG is at least 300 dpi.

The final chapter preserves the established numbering: Figure 6 remains outlier sensitivity and Figure 7 remains grouped classification. No figure or table was recreated in WRITE-4.

## Claim-boundary audit

The text distinguishes observation, comparison with the repeatability floor, unmet confirmatory gates and exploratory AS02 evidence.

It does not claim confirmation of H1, established U4ENC superiority, reliable four-direction classification, causal AS01/AS02 effects, absolute SPL traceability or anechoic conditions.

The conclusion state remains `supported_with_limits`; low scientific eligibility is explained as a claim boundary rather than a software failure.

## Citation audit

The final chapter contains 13 explicit citation-needed markers, C01–C13. Each has one matching row in `FINAL_CITATION_REQUIREMENTS.md` and a search topic rather than a fabricated reference.

No unmarked external literature claim was intentionally introduced in WRITE-4. Sources must later be verified before replacing any marker.

## Link and delivery audit

All relative Markdown figure and table links resolve. The delivery manifest lists every WRITE-4 final document and the progress/index records, with a SHA-256 for each listed file.

The delivery manifest excludes only its own self-hash, because embedding that value would be self-referential. Its file hash is verified externally during delivery checks.

## Validation result

- WRITE-4 focused checks: 5 passed.
- FORMAL-3/4/5 and WRITE-1/2/3 related regression: 30 passed.
- Full pytest: 918 passed.
- `python -m compileall -q src scripts`: passed.
- `git diff --check`: passed.

No final-test content, simulated output, temporary analysis output or data-selection change is part of this delivery.
