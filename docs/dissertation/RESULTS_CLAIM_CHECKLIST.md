# Results Claim Checklist

Use this checklist when moving text, tables, captions, or abstract statements from WRITE-1 into the dissertation. A checked item records compliance with frozen evidence; it does not upgrade scientific eligibility.

## 1. Frozen state

- [x] Final disposition remains `supported_with_limits`.
- [x] H0 remains `not_rejected`.
- [x] H1 remains `not_confirmed`.
- [x] ACTIVE/EXCLUDED remains 72/19.
- [x] All 10 outlier flags remain ACTIVE in primary analysis.
- [x] `final_test_read=false`; final-test remains sealed.
- [x] `scientifically_eligible=false` is not rewritten as software failure.
- [x] No raw TXT re-import, sample reselection, threshold change, or model search occurred.

Authority: FORMAL-5 `final_claim_boundary.json` and `final_analysis_manifest.json`.

## 2. Numeric traceability

| Claim ID | Frozen value | Required authority | WRITE-1 location | Checked |
|---|---|---|---|---|
| N01 | Primary CONT median 0.3783 dB | F4 `repeatability_summary.csv` | Results §2 | [x] |
| N02 | Primary CONT IQR 0.2191 dB | F4 `repeatability_summary.csv` | Results §2 | [x] |
| N03 | Primary CONT p95 0.8793 dB | F4 `repeatability_summary.csv` | Results §§2–4 | [x] |
| N04 | U4ENC G_demeaned 1.2805, CI 0.8297–1.7667 | F4 `direction_gain_summary.csv` | Results §3 | [x] |
| N05 | U4SYM G_demeaned 0.6824, CI 0.6105–1.2699 | F4 `direction_gain_summary.csv` | Results §3 | [x] |
| N06 | ΔG 0.5982, CI -0.1131–1.0843 | F4 `direction_gain_contrasts.csv` | Results §3 | [x] |
| N07 | U4ENC 6/6; U4SYM 3/6 stable pairs | F4 `direction_pairwise_effects.csv` and summary | Results §3 | [x] |
| N08 | AS01 median configuration/floor ratio 1.5688 | F4 `configuration_effects.csv` | Results §4 | [x] |
| N09 | U4SYM BA 0.375; macro-F1 0.250 | F4 `grouped_validation_metrics.csv` | Results §6 | [x] |
| N10 | U4ENC BA 0.250; macro-F1 0.183 | F4 `grouped_validation_metrics.csv` | Results §6 | [x] |
| N11 | 10 outlier flags; no frozen conclusion changed | F4 `outlier_sensitivity.csv` | Results §7 | [x] |

Every rounded value must retain enough digits to preserve the frozen decision. Do not replace a confidence interval with a point estimate or omit a bound that crosses its threshold.

## 3. Claim classes

### A. Descriptive results

- [x] State that U4ENC had a higher `G_demeaned` point estimate than U4SYM.
- [x] Report raw, demeaned, and z-score point estimates without calling them proof.
- [x] Report secondary-band and full-band results as secondary/descriptive.
- [x] Describe AS01–AS02 magnitudes only with their confounding caveat.

Allowed wording: “The U4ENC point estimate was higher.”

Forbidden wording: “U4ENC was significantly or definitively more directional.”

### B. Results exceeding the repeatability floor

- [x] State that U4ENC 6/6 and U4SYM 3/6 direction pairs exceeded CONT p95 in both AS01 blocks.
- [x] State that all four AS01 configuration differences exceeded CONT p95.
- [x] Identify 0.8793 dB as a technical-repeat floor, not a universal physical threshold.

Allowed wording: “Direction-related spectral differences exceeded the measurement-repeatability floor.”

Forbidden wording: “All directions were independently identifiable.”

### C. Confirmatory criteria not passed

- [x] Retain the U4ENC CI lower bound of 0.8297, below 1.
- [x] Retain the ΔG CI lower bound of -0.1131, below 0.
- [x] State that both AS01 balanced accuracies were below 0.50.
- [x] Keep H0 `not_rejected` and H1 `not_confirmed`.

Allowed wording: “The point estimates followed the predicted direction, but the confirmatory criteria were not fully met.”

Forbidden wording: “H1 was supported” without the qualifier `not_confirmed`.

### D. Exploratory results

- [x] Label AS02 and AS01–AS02 comparisons exploratory.
- [x] State that assembly, acquisition block, and time were confounded.
- [x] Label all-assembly classification exploratory.
- [x] Prevent exploratory BA=0.500 from replacing the AS01 negative result.

Allowed wording: “An exploratory all-assembly analysis showed…”

Forbidden wording: “Independent assembly replication confirmed…”

## 4. Independence and validation language

- [x] Do not count three CONT repeats as three independent scientific samples.
- [x] Describe the classification protocol as leave-one-block-out grouped validation.
- [x] Do not mention ordinary random train/test splitting as a valid result.
- [x] Report the 25% chance level and 50% practical target together.
- [x] Keep the limited number of blocks and grouped predictions visible.

## 5. Outlier language

- [x] Say “outlier flag,” not “invalid measurement,” unless referring to a structural QC failure.
- [x] State that primary analysis retained all 72 ACTIVE curves.
- [x] State that sensitivity omission did not edit ACTIVE/EXCLUDED.
- [x] Do not recommend post-hoc deletion to improve G, CI, or classification.

## 6. Figure and caption checks

- [x] Figure 1 appears before direction-effect interpretation.
- [x] Primary and secondary bands are clearly distinguished.
- [x] Figure 2 preserves block and REPOS identity.
- [x] Figures 3–4 do not equate floor exceedance with confirmatory success.
- [x] Figure 5 marks AS02 as exploratory.
- [x] Figure 6 states that no sample selection changed.
- [x] Figure 7 states that both AS01 BA values missed the 0.50 target.
- [x] No figure is duplicated under a different title.

## 7. Thesis-level boundaries

The following statement is approved:

> Under ordinary-room and limited-repeat conditions, the encoded structure produced direction-related spectral changes above the measurement-repeatability floor. Its direction-effect point estimate exceeded that of the symmetric structure, but between-configuration uncertainty and direction-classification performance did not meet the preregistered confirmatory criteria.

The following statements are prohibited:

- “U4ENC was proved superior to U4SYM.”
- “The system reliably classified all four directions.”
- “AS02 independently replicated the AS01 result.”
- “The result generalizes to final-test, deployment, or real Multisine/P8.”
- “The 10 flagged curves were invalid and removed.”
- “`scientifically_eligible=false` means the software analysis failed.”

## 8. Final pre-submission check

- [ ] Recheck every transcribed number against the evidence keys in `RESULTS_DRAFT.md` after typesetting.
- [ ] Recheck final figure files against their SHA-256 values in `FIGURE_PLAN.md`.
- [ ] Confirm that editing has not changed `supported_with_limits`, H0, H1, or exploratory labels.
- [ ] Confirm that final-test remains sealed and unread.
- [ ] Confirm that no abstract or conclusion sentence exceeds the approved claim boundary.

## 9. WRITE-2 generated-asset verification

- [x] Seven planned figure groups exist as PNG and SVG; no additional result figure was introduced.
- [x] Four planned table groups exist as CSV and Markdown.
- [x] PNG metadata reports at least 300 dpi and every PNG is at least 1200 × 900 pixels.
- [x] Every generated file matches the SHA-256 recorded in `FIGURE_AND_TABLE_MANIFEST.json`.
- [x] Every figure/table entry records its frozen FORMAL-4 source artifact and reproduction script.
- [x] The generated tables reproduce the frozen rounded values for CONT floor, G, ΔG, AS01 configuration/floor ratio and grouped classification.
- [x] Figure captions preserve `supported_with_limits`, H0 `not_rejected`, H1 `not_confirmed`, exploratory labels and the 0.50 classification target.
- [x] WRITE-2 did not change ACTIVE/EXCLUDED, run a new estimator, or read final-test.

These checks validate the generated WRITE-2 assets. The unchecked pre-submission items above remain manual gates after final dissertation typesetting.
