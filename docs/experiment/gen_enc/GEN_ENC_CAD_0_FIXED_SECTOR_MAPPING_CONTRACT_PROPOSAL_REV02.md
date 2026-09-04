# GEN-ENC-CAD-0 fixed-sector CAD-mapping contract proposal REV02

Version: `GEN-ENC-CAD-0-PHASE-A-PROPOSAL-REV02-v1`

Date: 2026-08-28

Terminal state: `READY_FOR_GUARDIAN_REVIEW_BEFORE_USER_CONFIRMATION`

Evidence label: `E0_CAD_MAPPING_CONTRACT_PROPOSAL`

`scientific_evidence_level=NOT_ESTABLISHED`; `scientific_hypothesis_status=NOT_TESTED`; `overrides=false`; `phase_b_started=false`; `formal_generator_invoked=false`; `formal_seed_consumed=false`; `formal_instance_count=0`; all execution/static-eligibility/preflight/GEN-ENC-2 authorizations are false; `final_test_read=false`.

## Addendum metadata

- **New content:** documentation-only closure of guardian RC-01..RC-06: exact fixed-interface exception enumeration and scope, separate general/exception measurements and witnesses, literal spillover fixtures, and a corrected constrained-domain root proof.
- **Relates to:** unchanged initial CAD-0, REV01 and `GEN_ENC_CAD_0_REV01_CONTRACT_REVIEW.json`.
- **Unchanged:** F-03, F-04 and F-06..F-09 resolutions; every existing report/package; sealed numeric families, rows, seeds, DOF, status rules and final-test.
- **Proposal boundary:** all REV01/REV02 geometry semantics remain `PROPOSED_REQUIRES_USER_APPROVAL`; P05 remains provenance only. This revision is not user-decision ready until a new guardian review says so.

## 1. RC-01/RC-02: exact fixed U4 interface transition exception

Corrected T1 retains the four identical, common, non-tunable collars. Each collar is classified `FIXED_U4_INTERFACE_TRANSITION_EXCEPTION`; this classification is part of future U1 and applies only to the stable IDs below.

For sector `sss` in `000,090,180,270`, local coordinates use the frozen sector frame. The collar fluid box is `u=[0.103,0.105]`, `v=[-0.008,0.008]`, `z=[0.0015,0.0107] m`. Its internal shared opening is only `z=[0.002,0.0102]`. Exact exception objects are:

- `IFX_U4_sss_RIM`: one composite rim per collar, count four. It contains `BOTTOM`, body solid `z=[0,0.0015]`, and `TOP`, body solid `z=[0.0107,0.0122]`, both over the collar plan and each with derived thickness `0.0015 m`.
- `IFX_U4_sss_SHOULDER_LOWER`: one lower transition shoulder per collar, count four, collar fluid/boundary feature `u=[0.103,0.105]`, `v=[-0.008,0.008]`, `z=[0.0015,0.002]`, derived z feature `0.0005 m`.
- `IFX_U4_sss_SHOULDER_UPPER`: one upper transition shoulder per collar, count four, same u/v and `z=[0.0102,0.0107]`, derived z feature `0.0005 m`.

Thus the exception inventory is four composite 1.5 mm rims with eight rim component sheets and eight 0.5 mm shoulders.

Participation is frozen, not implicit:

- each rim is excluded from `general_minimum_feature_m`, excluded from general `t_ff`, and excluded from general `t_fe`; it participates in `interface_exception_min_feature_m` with 1.5 mm component witnesses and in `interface_exception_min_load_path_m` as a direct fluid-to-exterior cover witness of 1.5 mm;
- each shoulder is excluded from the general minimum-feature aggregate and recorded in `interface_exception_min_feature_m` with a 0.5 mm witness; it is excluded from both `t_ff` and `t_fe` because its 0.5 mm is a boundary-feature height, not an eligible opposing-sheet clearance. Its faces remain in the arrangement and may not suppress unrelated general witnesses;
- every exception exclusion is by exact stable ID only. Classification by size, family, overlap or proximity is forbidden.

The contract fields are separate:

- `general_minimum_feature_m=0.002`, with proposed analytic witnesses `GEN_TOP_COVER_Z`, `GEN_BOTTOM_FLOOR_Z`, `GEN_INNER_NECK_U`, `GEN_WINDOW_HEIGHT` and `GEN_WINDOW_COLLECTOR_MARGIN`;
- `general_minimum_load_path_m=0.002`, with witnesses `GEN_TOP_COVER_TFE` and `GEN_BOTTOM_FLOOR_TFE`; the independent general gate remains `0.0016 m`;
- `interface_exception_min_feature_m=0.0005`, witnessed by all eight shoulder IDs;
- `interface_exception_min_load_path_m=0.0015`, witnessed by the four rim IDs and their top/bottom component sheets.

These values are derived from frozen coordinate differences, not copied from thresholds. A later exact arrangement that finds a smaller nonexception general witness fails closed; proposal values are not manufacturability results.

The exception does not apply to cavities, spines, scientific windows, outer connectors, family primitives, overlap fragments, disabled/active slots, parameter-dependent geometry or future topology freedom. A 1.5 mm or 0.5 mm topology primitive therefore fails the general 2.0 mm minimum-feature gate. The exception is identical for all four families, always active, adds no DOF, and is reported in matched-cost burden fields. It does not establish manufacturability and does not reduce the 2.0 mm general feature or 1.6 mm general load-path gates elsewhere.

## 2. RC-03: literal exception and threshold fixtures

Nonformal fixtures enumerate all four rim IDs and all eight shoulder IDs. Each rim must return exception feature/load-path `0.0015 m`; each shoulder must return exception feature `0.0005 m` and `NOT_APPLICABLE` for `t_ff/t_fe`. A topology-dependent primitive at either 1.5 mm or 0.5 mm must fail `GENERAL_MINIMUM_FEATURE_BELOW_THRESHOLD`, even if it touches a collar.

For both general thresholds, binary64 literal cases are frozen: one representable step below fails, exact equality passes, and one step above passes. Exception values never substitute for the general fields or gates.

## 3. RC-04: exact constrained local-target extrema

Let `a=0.12`, the provenance-bound `V=3.014899604922098e-5 m3`, independent variables `(x,y,z) in [-a,a]^3`, `q270=-(x+y+z)/3`, and

`T_k=0.60V* exp(q_k)/(exp(x)+exp(y)+exp(z)+exp(q270))`.

For the derived sector,

`d log(T_270)/dx = -(1-p_270)/3-p_x < 0`,

and identically for y and z, where every softmax probability is positive. Therefore `T_270` is strictly decreasing in each independent variable. Its exact extrema are:

- minimum witness `Q270_MIN_WITNESS=(a,a,a)`, giving `q270=-a` and `T=3.7578617934992e-6 m3`;
- maximum witness `Q270_MAX_WITNESS=(-a,-a,-a)`, giving `q270=a` and `T=5.38393583634402e-6 m3`.

For an independent sector, take x as its coordinate. `d log(T_x)/dx=1-p_x+p_270/3>0`, so its minimum uses `x=-a` and maximum uses `x=a`. At `x=-a`, maximizing the remaining convex denominator over `(y,z)` occurs at a square corner; the four corners are finitely compared and `(a,a)` is the maximum-denominator witness. At `x=a`, the unconstrained symmetric stationary point for denominator minimization is `y=z=-(3 ln 3+a)/5<-a`, so the constrained minimum is `y=z=-a`. Hence independent-sector extrema are the narrower interval:

- `3.91055705987307e-6 m3` at `(-a,a,a)`;
- `5.17376219550658e-6 m3` at `(a,-a,-a)`.

By permutation symmetry the same holds for the other two independent sectors. Consequently the exact global four-sector constrained interval is the derived-sector interval `[3.7578617934992e-6,5.38393583634402e-6] m3`. It is not an independent-extrema superset.

## 4. RC-05: root bracket restatement

The exact constrained target range is numerically unchanged, so the REV01 family endpoint/derivative proof remains valid:

- maximum lower-end volume across all family bound corners: `2.95095477315311e-6 m3 < 3.7578617934992e-6 m3`;
- minimum upper-end volume: `5.50521872959047e-6 m3 > 5.38393583634402e-6 m3`;
- minimum derivative: `9.66e-5 m2 > 0`.

Therefore corrected T1 brackets the full sealed parameter domain for HAND, NEAR, RANDOM and PHYSICS. No admissible region is unbracketed, and no family parameter, threshold, seed or identity is changed. No formal row/seed/identity was evaluated.

## 5. RC-06 and future user text

F-03, F-04 and F-06..F-09 remain byte-semantically carried forward: no T2; D4 remains binding status behavior rather than a choice; RANDOM is shared-plenum descriptive-only; exact slot/ownership algorithms remain; all new semantics stay proposed.

After a new guardian approval only, U1 must say:

> Approve the corrected T1 fixed-sector mapping, including the exact 0.0082 m internal-fluid height, sensor-only top opening, four fixed U4 side collars, and the explicitly enumerated common non-tunable collar rim/transition exceptions recorded separately from the general 2.0 mm minimum-feature and 1.6 mm load-path gates; these exceptions apply to no topology-dependent primitive, do not establish manufacturability, and authorize no execution. Otherwise reject T1 and escalate.

U2 and U3 use the guardian-recommended exact semantics frozen in `user_decision_matrix.json`. Current user confirmation remains unauthorized.

No formal seed, row, identity, generator, mapping compiler, verifier, geometry, CAD kernel, COMSOL, full-wave, response, timing, eligibility, search, development, validation or final-test operation occurred. Stop at `READY_FOR_GUARDIAN_REVIEW_BEFORE_USER_CONFIRMATION`; do not contact guardian or commit/push/tag/release.
