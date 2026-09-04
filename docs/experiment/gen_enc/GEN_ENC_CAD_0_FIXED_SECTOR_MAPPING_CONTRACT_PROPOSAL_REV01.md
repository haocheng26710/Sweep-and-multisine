# GEN-ENC-CAD-0 fixed-sector CAD-mapping contract proposal REV01

Version: `GEN-ENC-CAD-0-PHASE-A-PROPOSAL-REV01-v1`

Date: 2026-08-28

Terminal state: `READY_FOR_GUARDIAN_REVIEW_BEFORE_USER_CONFIRMATION`

Evidence label: `E0_CAD_MAPPING_CONTRACT_PROPOSAL`

`scientific_evidence_level=NOT_ESTABLISHED`; `scientific_hypothesis_status=NOT_TESTED`; `overrides=false`; all execution, Phase B, scientific-identity, static-eligibility, preflight and GEN-ENC-2 authorizations are false; `final_test=sealed`; `final_test_read=false`.

## Addendum metadata and disposition

- **New content:** an incremental correction of F-01..F-09 from `GEN_ENC_CAD_0_PHASE_A_CONTRACT_REVIEW.json`, including a closed body-z proposal, an executable solid-thickness metric, a full-domain family root proof, exact slot/ownership ledgers and a three-item future user matrix.
- **Relates to:** the unchanged initial CAD-0 proposal/package and its guardian review; the explicit earlier authorization to author an E0 mapping proposal; sealed GEN-ENC-2A REV01 and GEN-ENC-2B.
- **Unchanged:** all initial CAD-0 files, every GEN-ENC/FORMAL/SUP/V2.5/Scheme 3A/TRANS/INFO-TOP artifact, the rejected 2C REV01 scripts/schemas, formal identities, seeds, rows, DOF, endpoints and final-test.
- **Authority boundary:** every new dimension, interval, collar exception, primitive, placement, metric and mapping remains `PROPOSED_REQUIRES_USER_APPROVAL`. P01/P02 remain nominal P05 provenance only.
- **Current decision boundary:** no user confirmation is requested now. This revision must first receive a new guardian review.

## 1. F-01: corrected T1 z/body contract and compatibility proof

All quantities in this section are proposals requiring approval.

The sealed outer-port clear height is `h_port=0.0092 m`, the sealed device z cap is `H_device=0.0122 m`, the minimum designed feature is `0.002 m`, and the minimum solid load path threshold is `0.0016 m`. Without an interface exception or height conversion, top and bottom load paths would require

`h_port + 2*0.0016 = 0.0124 m > 0.0122 m`.

Therefore the literal full-height-through-device interpretation is mathematically incompatible by `0.0002 m`. REV01 does not report the original T1 as feasible. Corrected T1 adds one explicit scientific-semantic proposal inside future U1: a bounded side-interface collar plus an internal height transition. Rejecting that semantic rejects T1 and escalates; it is not inferred by code.

Corrected intervals are:

- device exterior/body: `z in [0,0.0122] m`;
- bottom supported solid: `[0,0.002] m`;
- internal fluid: `[0.002,0.0102] m`, height `H_int=0.0082 m`;
- top cover: `[0.0102,0.0122] m`, thickness `0.002 m`;
- exterior: `z<0` or `z>0.0122 m`;
- four side-interface collars only: local `u in [0.103,0.105]`, `v in [-0.008,0.008]`, `z in [0.0015,0.0107] m`, retaining the exact `0.016 x 0.0092 m` outer interface;
- collar-to-internal transition face: `u=0.103`, with positive shared rectangle `v in [-0.008,0.008]`, `z in [0.002,0.0102]`;
- the only top opening: the central sensor bore, radius `0.0045 m`, `z in [0.0102,0.0122]`.

The collar side face at `u=0.105` is a declared outer-port interface. The `0.0015 m` collar rim above/below it is an explicit interface-collar exception to the `0.0016 m` general load-path gate. No other fluid/exterior pair is exempt. This exception and internal height conversion are part of U1, not inherited authority.

The central fluid partition is the union of an internal square prism and the top sensor bore. With `V_s=pi*(0.0045)^2*0.002=1.2723450247038663e-7 m3`,

`A=sqrt((0.40V*-V_s)/(4H_int))=0.019073321232601637 m`,

so `4A^2H_int+V_s=0.40V*` up to the stated algebraic representation. The sensor cylinder overlaps the square plenum only on its shared face at `z=0.0102`, hence no positive-volume double count.

Derived fluid envelope is obtained from primitive extrema, not copied from caps: `0.210 x 0.210 x 0.0107 m`, including the sensor bore from `z=0.0015` to `0.0122`. Derived device/solid envelope from the proposed body vertices is `0.210 x 0.210 x 0.0122 m`. The z equality is a consequence of the proposed body interval constrained by the sealed cap, not a measured thickness. Internal top/bottom covers derive as `0.002 m`; the load-path threshold remains a separate comparison value.

## 2. Corrected common radial template and exact volume function

The corrected central half-side is `A` above. Each sector has:

1. inner aperture wall/neck region `u in [A,A+0.002]`;
2. inner collector `u in [A+0.002,A+0.010]`, `v in [-0.015,0.015]`, `z in [0.0051,0.0071]`;
3. root span `u in [A+0.010,0.088]`, length `S=0.058926678767398356 m`;
4. cavity width/height `0.017/0.0062 m`, radial `L in [0.002,0.030]`, centred in the root span, z interval `[0.003,0.0092]`;
5. inner spine and outer connector filling equal lengths `(S-L)/2`, both z `[0.0051,0.0071]`; spine width `0.002`, outer width `w(a)=0.002+0.006a`;
6. internal outer steps over `u=[0.088,0.103]`: `(length,width)=(0.006,0.008),(0.005,0.012),(0.004,0.016)`, z `[0.002,0.0102]`;
7. outer collar above.

Fixed local volume, excluding the variable connectors, cavity and aperture-wall slots, is

`V_fixed=(0.008*0.030*0.002)+(0.006*0.008+0.005*0.012+0.004*0.016)*0.0082+(0.002*0.016*0.0092)=2.1848e-6 m3`.

Let `A_in=0.002*0.002=4e-6 m2`, `A_out=0.002*w(a)`, `A_cav=0.017*0.0062=1.054e-4 m2`, and let `V_window` be the exact union of `SPINE` and active `WINDOW_1..3` within the fixed `0.002 m` aperture-wall length. The wall region is disjoint in positive volume from the L-dependent root span, so `V_window` is independent of `L`. The exact local function is

`V_i(L,p)=V_fixed + (A_in+A_out(p))(S-L)/2 + A_cav*L + V_window(p)`.

Its derivative is `A_cav-(A_in+A_out)/2` and is strictly positive over every family domain.

## 3. F-05: family-by-family full-domain root proof

No formal seed or row was evaluated. Bounds come only from sealed parameter domains and finite extrema.

The conservative local-target enclosure follows `q_i in [-0.12,0.12]` and `q270 in [-0.12,0.12]`:

`T_i in [3.7578617934992e-6,5.38393583634402e-6] m3`.

This enclosure is wider than the admissible derived-q image, so proving it is sufficient.

Exact interval results are:

| Family | `A_out` m2 | `V_window` m3 | `V(Llo)` m3 | `V(Lhi)` m3 | `dV/dL` m2 |
|---|---:|---:|---:|---:|---:|
| HAND | `[6.4e-6,1.36e-5]` | `[1.04e-8,1.52e-8]` | `[2.70201872959047e-6,2.91175477315311e-6]` | `[5.50761872959047e-6,5.61655477315311e-6]` | `[9.66e-5,1.002e-4]` |
| NEAR | `[6.4e-6,1.36e-5]` | `[8e-9,3.2e-8]` | `[2.69961872959047e-6,2.92855477315311e-6]` | `[5.50521872959047e-6,5.63335477315311e-6]` | `[9.66e-5,1.002e-4]` |
| RANDOM | `[1e-5,1e-5]` | `[8e-9,8.16e-8]` | `[2.80208675137179e-6,2.87568675137179e-6]` | `[5.55728675137179e-6,5.63088675137179e-6]` | `[9.84e-5,9.84e-5]` |
| PHYSICS | `[6.4e-6,1.36e-5]` | `[2.56e-8,5.44e-8]` | `[2.71721872959047e-6,2.95095477315311e-6]` | `[5.52281872959047e-6,5.65575477315311e-6]` | `[9.66e-5,1.002e-4]` |

For every family, the maximum lower-end volume is below the conservative target lower bound and the minimum upper-end volume is above the conservative target upper bound. Thus the entire sealed parameter domain is bracketed by corrected T1. Extrema witnesses are bound corners: maximum `V(Llo)` uses maximum outer width and maximum active-window union; minimum `V(Lhi)` uses minimum outer width and minimum window union. RANDOM uses fixed outer `a=0.5`, all-zero edges for its minimum and all six positive endpoint maxima for the relevant sector maximum. No admissible region is predeclared cost-ineligible from root bracketing.

Future bisection remains lower-on-exact-tie, 80 iterations, residual `<=1e-12 m3`, impossible-root fail closed. Any discrepancy between implementation and this proof triggers `TEMPLATE_VALIDITY_REJECTED` before formal identity generation.

## 4. F-02: executable solid clearance/thickness metric

Fluid and solid boundary faces are first consolidated into maximal coplanar connected polygonal sheets with stable IDs. Zero-area fragments are rejected. Two sheets are adjacent when their closures share positive-length edge or positive-area subset; adjacent faces of the same sheet, coplanar fragments of the same sheet, and faces belonging to declared port/sensor interfaces are excluded from opposing-pair enumeration.

For each remaining pair, compute exact convex-polygon closest points. A pair is eligible only when: endpoints lie in relative interiors; the open segment between them lies entirely in the relative interior of the same boundary-supported solid component; the segment intersects no other boundary sheet; and either (a) sheet normals are antiparallel within exact construction identity and the segment is normal to both, or (b) the pair gives the exact nonparallel polyhedral clearance minimum. Corner-only and edge-only contacts are ineligible. A T-junction's incident sheets are adjacency-excluded, but a separate opposing sheet across its stem remains eligible.

`t_ff` is the minimum eligible fluid-boundary to fluid-boundary segment; `t_fe` is the minimum eligible fluid-boundary to exterior-body segment. General load path is `min(t_ff,t_fe)`. The side collar exception and sensor/port openings are reported separately and never silently omitted. Empty eligible sets return `UNAVAILABLE`, not infinity or pass. Equal minima tie by `(distance,first_sheet_id,second_sheet_id,endpoint_lexicographic)`; calculations use exact proposal expressions where possible and binary64 only at serialization. Equality to `0.0016 m` passes; one `nextafter` below fails.

The solid arrangement is a separate exact polyhedral half-space arrangement, not the rectilinear fluid midpoint algorithm. Supported solid components are face-flooded from the bottom support sheet before pair testing.

## 5. F-06: permanent shared-plenum interpretation

Corrected D2-A defines RANDOM reduced edges as additional reciprocal throttling windows into a shared collector/plenum, not exclusive pairwise ducts. The fixed spine is a common connectivity floor. Reduced-graph disconnection is therefore not actual fluid disconnection.

Descriptive-only, non-eligibility, non-performance outputs are frozen: reduced component count; positive edge count/density; weighted degree sequence; weighted algebraic connectivity; actual fluid component count; each port and sensor reachability; spine/window raw and union volumes; wetted/interface areas. Later summaries may be stratified by reduced sparsity only descriptively. Any causal edge claim requires a separate future spine/window ablation contract.

## 6. F-07: exact reserved slot ledger

Every sector reserves `SPINE`, `WINDOW_1`, `WINDOW_2`, `WINDOW_3`, `OUTER_1`.

- all inner slots occupy `u=[A,A+0.002]`, `z=[0.0051,0.0071]`;
- `SPINE` has `v=[-0.001,0.001]`;
- window centres are `v=-0.0096,0,+0.0096`; active width is `w(a)` and absent width is zero. At maximum width `0.0068 m`, adjacent clear gaps are `0.0028 m` and the outer window-to-collector-side margin is exactly `0.002 m`;
- `OUTER_1` occupies the outer connector length, is centred at `v=0`, z `[0.0051,0.0071]` and uses its mapped width.

HAND and NEAR replicate their single shared parameter into `WINDOW_2`; RANDOM maps the three incident edges sorted by opposite-sector angle into `WINDOW_1..3`; PHYSICS maps its two incident ring edges in sorted opposite-angle order into `WINDOW_1..2`; remaining windows are explicitly disabled. `SPINE` is always active. RANDOM `OUTER_1` uses fixed `a=0.5`; other outer slots use their sealed external coordinate.

Per member and family, future static disclosure must report active/disabled slots, active primitive count, raw and union volume, wetted/interface area, boundary-face count, replication count and supported-solid burden. Reserved capacity is a disclosure control only; it does not prove equal physical complexity and is not a response/performance gate.

## 7. F-08: exact ownership, clipping and two geometry algorithms

Central volume ownership is half-open `C=[-A,A) x [-A,A)` in plan, plus the sensor cylinder owned by central. Outside `C`, sector ownership is the minimum sector order among maximizers of `dot((x,y),e_u(theta))`; this is an exact tie rule for the diagonal planes. Local-to-global is `(x,y,z)=u e_u+v e_v+z e_z`; global-to-local uses dot products with `e_u,e_v`.

Clip order is: central ownership first; then sector half-planes in order `0,90,180,270`; then primitive extent; then declared-interface tagging. Corrected T1 requires every local box to remain strictly within its sector wedge except its zero-volume shared central face. A positive-volume diagonal crossing is `OWNERSHIP_NONRECTILINEAR_CROSSING` and rejects the template before formal execution. Cross-owner adjacency exists only when clipped closures share a face of strictly positive area; point and line contact do not connect.

The fluid algorithm handles cardinally transformed axis-aligned boxes: ownership validation, endpoint coordinate compression, open-cell membership and lexicographic volume sum. Its schema reports raw/union/overlap volumes, cells, faces, ownership and adjacency. The solid algorithm constructs exact convex polyhedra from octagonal-body half-planes, fluid box planes and z planes, subtracts fluid cells, consolidates boundary sheets, floods supported components and applies the thickness algorithm. Its schema reports polyhedral cells, sheet IDs/normals/areas, supported components, eligible/excluded pairs, witness segments and `t_ff/t_fe`.

## 8. F-03/F-04: decision and status correction

Incomplete T2 is removed. Future U1 is only `APPROVE_CORRECTED_T1_WITH_COLLAR_AND_INTERNAL_HEIGHT_SEMANTICS` versus `REJECT_T1_AND_ESCALATE`.

D4 is removed as a choice. Binding carry-forward remains: any formal member conflict is `COST_INELIGIBLE`; all 80 slots are retained; no repair, redraw, replacement, drop, threshold change or parameter change is permitted. Early family audit termination is prohibited. Before formal identity generation only, proof or nonformal-fixture failure may set `TEMPLATE_VALIDITY_REJECTED`; this is not a member status or scientific result.

## 9. Nonformal fixtures and future three-decision matrix

All fixtures remain `TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY` and unexecuted. Added literal cases cover top closure, collar exception, sensor-only top opening, parallel walls, corners, T-junctions, coplanar fragments, octagonal diagonal exterior, intentional openings, threshold/nextafter, family root corners, slot overlap, ownership-plane conservation and 90-degree rotation.

After a new guardian approval only, the user matrix has three binary decisions:

1. U1 corrected T1 approve versus reject/escalate;
2. U2 D2-A approve with permanent shared-plenum disclosure versus reject/require a new complete connectivity proposal;
3. U3 corrected D3-A disclosure control approve versus reject/require a new complete fairness proposal.

No current user confirmation, formal identity calculation, seed execution, geometry generation, implementation code, CAD kernel, solver, COMSOL, full-wave, response, timing, endpoint, ranking, development, validation or final-test access occurred. All counts remain zero, identity hashes null, RQ closures zero and `bidirectional_discovery_established=false`. Stop after `READY_FOR_GUARDIAN_REVIEW_BEFORE_USER_CONFIRMATION`; do not contact guardian or commit/push/tag/release.
