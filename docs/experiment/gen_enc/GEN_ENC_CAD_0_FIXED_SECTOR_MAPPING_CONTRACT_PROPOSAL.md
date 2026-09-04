# GEN-ENC-CAD-0 fixed-sector CAD-mapping contract proposal

Version: `GEN-ENC-CAD-0-PHASE-A-PROPOSAL-v1`

Date: 2026-08-28

Terminal state: `READY_FOR_GUARDIAN_AND_USER_REVIEW`

Evidence label: `E0_CAD_MAPPING_CONTRACT_PROPOSAL`

`scientific_evidence_level=NOT_ESTABLISHED`; `scientific_hypothesis_status=NOT_TESTED`; `overrides=false`; `execution_authorized=false`; `phase_b_authorized=false`; `scientific_identity_generation_authorized=false`; `static_eligibility_authorized=false`; `preflight_authorized=false`; `gen_enc_2_authorized=false`; `final_test=sealed`; `final_test_read=false`.

## Addendum metadata and authority boundary

- **New content:** a finite, falsifiable proposal for the missing common U4 fixed-sector geometry, volume/overlap accounting, family parameter-to-primitive mapping, connectivity semantics, static audits, matched-cost rules, technical fixtures and future implementation structure.
- **Relates to:** the explicit user selection `AUTHOR_NEW_E0_CAD_MAPPING`; the GEN-ENC-2C Phase A and correction packages; sealed GEN-ENC-2A REV01 numeric identities; sealed GEN-ENC-2B source bundle and its two guardian reviews; the active-question ledger and guardian charter.
- **Unchanged:** every existing GEN-ENC, FORMAL, SUP, V2.5, Scheme 3A, TRANS and INFO-TOP report/package; the rejected 2C REV01 scripts/schemas; all sealed family values, parameter order, DOF, seeds, member slots, matched-volume interval, interface identity and later endpoints.
- **Provenance only:** P01/P02 nominal P05 and TRANS/INFO-TOP reports are not promoted to new four-family authority or new results.
- **Proposal rule:** every new dimension, bound, primitive, placement and family mapping below is `PROPOSED_REQUIRES_USER_APPROVAL`. Nothing here is a frozen geometry, eligible identity, CAD result, manufacturability result, response, ranking or scientific finding.

## 1. Inherited versus proposed quantities

Inherited sealed quantities are: target connected volume `V*=3.014899604922098e-5 m3`; closed matched interval `[2.984750608872877e-5,3.0450486009713192e-5] m3`; central/local shares `0.40/0.60`; `s_i=0.60 exp(q_i)/sum_j exp(q_j)` with `q270=-(q0+q90+q180)/3`; four cardinal ports, four states, one central sensor, interface identity `U4_CARDINAL_4PORT_CENTRAL_M1_v1`; outer interface width/height `0.016/0.0092 m`; sensor bore/disk `0.009/0.0088 m`; envelope caps `0.227302/0.227302/0.0122 m`; tolerance `0.0002 m`; minimum feature/load path thresholds `0.002/0.0016 m`; `DOF<=16`; aperture formula `w(a)=0.002+0.006a m`; lower-on-exact-tie bisection, 80-iteration cap and `1e-12 m3` residual.

Proposed T1 geometry uses SI internally. Global origin is the head centre, `+x=90 deg`, `+y=0 deg`, `+z` upward. Sector order is `0,90,180,270 deg`, with local orthonormal frames `e_u=(sin theta,cos theta,0)`, `e_v=(cos theta,-sin theta,0)`, `e_z=(0,0,1)`; `u` is outward radial and `v` is clockwise tangential when viewed from `+z`. Half-open solids define volume; closed faces define adjacency.

The inherited U4 planes are `u=0.105 m`, the z interval `[0.003,0.0122] m`, the four cardinal directions and outer port rectangles. The proposed items are a square central plenum, sector passages, stepped outer taper, cavity and connector placement, all length bounds, connector lane placements and the solid audit construction.

The proposed solid-audit body is the regular-octagonal prism `abs(x)<=0.105`, `abs(y)<=0.105`, `abs(x)+abs(y)<=0.105sqrt(2)`, `z in [0,0.0122] m`, minus the fluid union with the four outer ports and sensor declared as intentional interfaces. Its `0.105 m` apothem and z scale come from nominal P01 provenance but their use as a four-family body is new and requires approval. Exact half-plane/box arrangement cells, not voxel samples, define its solid audit.

## 2. Recommended T1 fixed-sector candidate

All constants in this section are `PROPOSED_REQUIRES_USER_APPROVAL`.

The central connected-fluid partition is a square prism `[-A,A] x [-A,A] x [z0,z1]`, where `H=z1-z0=0.0092 m`, `V_c=0.40V*`, and `A=sqrt(V_c/(4H))=0.0181026649639184 m`. The sensor bore and observation disk are measurement/interface subsets inside this plenum; because they are subsets rather than added volumes, they contribute zero incremental union volume.

Each sector owns a disjoint local accounting cell and the following radial pieces:

1. fixed inner passage: `u in [A,A+0.010]`, width `0.008`, height `H`;
2. variable root span: `u in [A+0.010,0.088]`, total length `S=0.0598973350360816`;
3. fixed outer stepped passage: lengths/widths `(0.008,0.008)`, `(0.005,0.012)`, `(0.004,0.016)`, all height `H`, ending at `u=0.105`;
4. root-span cavity: width `W_cav=0.017`, height `H_cav=0.0064`, radial length `L_i in [0.002,0.026]`, centred in the root span;
5. inner fixed-spine and outer connector unions filling the two equal remaining radial lengths `(S-L_i)/2`. The inner cross-section is the common `0.002 x 0.002 m` spine; the outer cross-section is family-derived. Scientific central/edge/ring windows are separate `0.002 m`-long neck boxes at the inner end and enter `V_extra_union_i`; they do not run along the full connector length.

The fixed per-sector volume is

`V_fixed = (0.010*0.008*H) + H*(0.008*0.008 + 0.005*0.012 + 0.004*0.016) = 2.4656e-6 m3`.

Let `A_in=4e-6 m2`, let `A_out(p_i)` be the exact two-dimensional union of the outer connector rectangles, and let `A_cav=W_cav*H_cav=1.088e-4 m2`. With all family-specific fixed-length neck boxes included through the same union ledger,

`V_i(L_i,p_i)=V_fixed + A_in(p_i)(S-L_i)/2 + A_cav L_i + A_out(p_i)(S-L_i)/2 + V_extra_union_i(p_i)`.

`V_extra_union_i` is zero for a primitive already included in a connector union. Any genuinely separate fixed-volume primitive is assigned once to one sector; an inter-sector primitive is clipped at the ownership plane and each clip is counted once. There is no global post-hoc addition.

Target `T_i=s_iV*`. Root existence requires finite inputs, legal bounds, positive union areas, `V_i(L_lo)<=T_i<=V_i(L_hi)` and strict monotonicity `dV_i/dL=A_cav-(A_in+A_out)/2>0`. Failure of any condition is `CAD_ROOT_NOT_BRACKETED` or `CAD_VOLUME_FUNCTION_NOT_STRICTLY_MONOTONE` and closes the member as `COST_INELIGIBLE`; parameters are never modified.

Even when a closed-form root exists, a future implementation must use the sealed deterministic bisection: exact endpoints first; 80 iterations maximum; midpoint in binary64; exact residual tie selects the lower interval endpoint; success only if `abs(V_i-T_i)<=1e-12 m3`; otherwise `CAD_ROOT_RESIDUAL_EXCEEDED`. Impossible roots fail closed and retain the slot.

## 3. Exact volume, overlap and Boolean accounting

Central and local ownership interiors are disjoint. Shared faces have zero measure. Therefore the contractual total is

`V_connected = V_c + sum_i V_i = 0.40V* + sum_i s_iV* = V*`.

Every fluid primitive has an ID, owner, family applicability, local/global transform, extent, unit and parameter dependency. For rectilinear boxes, exact union measure is computed by coordinate compression: sort all unique x/y/z endpoints; inspect every elementary open cell at its midpoint; include its `dx*dy*dz` exactly once when covered by at least one primitive; sum in lexicographic cell order. A primitive crossing an ownership plane is clipped first. This deterministic inclusion algorithm replaces informal pairwise subtraction and prevents double counting of cavity/neck, spine/window and family-window overlaps.

For every primitive list the future audit must report raw volume sum, overlap deduction `raw_sum-union`, owned union, target and residual. Negative widths, inverted extents, positive-volume cross-owner overlap before clipping, unclassified overlap or non-finite measure are fail-closed technical reason codes.

## 4. Family mappings without new scientific DOF

The common fixed spine is one `0.002 m x 0.002 m` connector slot per sector and fills the inner connector length `(S-L_i)/2`. It is a disclosed common CAD control and contributes no family DOF. Each scientific central/edge/ring window is a fixed `0.002 m` radial neck; zero-edge slots are absent, not epsilon-repaired.

- **HAND_DESIGNED (sealed DOF 12):** each `external_aperture_fraction_i` sets the outer connector clear width by sealed `w(a)`. The single `central_mix_aperture_fraction` sets one replicated inner shared-window width in every sector, unioned with the fixed spine. Loss coordinates alter no geometry. This replication adds no latent tunable coordinate.
- **NEAR_INDEPENDENT (sealed DOF 12):** external fractions map identically to outer connectors. `shared_coupling_alpha` first maps to `a_alpha=(alpha-0.03)/0.04`, then to one replicated inner shared-window width `w(a_alpha)`, unioned with the spine. It does not create four hidden alphas.
- **FIXED_SEED_RANDOM_DISORDERED (sealed DOF 13):** q and loss retain sealed roles. The six reciprocal edges map to paired endpoint inner-window slots; each sector has three fixed z lanes for its three incident edges. `edge=0` omits both paired windows; positive edge uses `w(edge)`. A disclosed fixed external fraction `a_ext=0.5` is common CAD control, not family DOF. The reduced edge graph and actual fluid-domain graph are separately audited under recommended decision D2-A.
- **PHYSICS_METAMATERIAL_INSPIRED (sealed DOF 15):** four external coordinates map to four outer connectors. Four reciprocal ring coordinates map to paired endpoint inner-window slots for `(0,90),(90,180),(180,270),(270,0)`. q and loss retain sealed roles. No diagonal ring edge or extra tunable coordinate is introduced.

The three proposed inner-window lane z intervals are `[0.003,0.005]`, `[0.0066,0.0086]`, and `[0.0102,0.0122] m`; the two separating solid gaps are each `0.0016 m`. Slot assignment is lexicographic by opposite sector angle. All these placements and the fixed `a_ext=0.5` are new proposal constants requiring approval.

## 5. Connectivity semantics and RANDOM zero edges

Fluid connectivity is derived, never copied as `connected_components=1`. Build one node per positive-volume elementary union cell. Add an undirected adjacency only when two cells share a face with strictly positive area; point/edge contact does not connect. Add interface nodes for each port and the central sensor subset, then run deterministic BFS in lexicographic node order. Report component membership, port reachability and central reachability.

Recommended D2-A separates two graphs. `G_reduced` contains the six RANDOM scientific edges whose value is positive. `G_fluid` contains the actual fixed spine, passages, cavities and positive family windows. Thus a zero or disconnected `G_reduced` is retained as a valid scientific numeric identity, while `G_fluid` must independently have one component to pass static cost. This does not pretend that reduced pairwise edges are identical to exclusive fluid ducts; it exposes the shared-plenum interpretation and its fairness risk.

D2-B makes reduced and fluid connectivity identical by removing the fixed spine for RANDOM; disconnected zero-edge members become `COST_INELIGIBLE`. D2-C retains the fixed spine but declares any disconnected reduced graph cost-ineligible. These are mutually exclusive and require user choice.

## 6. Derived static audits

Envelope is derived from transformed primitive extrema: `E_k=max_P max_vertex x_k - min_P min_vertex x_k`. Under T1 the fixed interfaces imply candidate values `E_x=E_y=0.210 m` and `E_z=0.0092 m`; these are derivations and are compared afterwards with, not copied from, the sealed caps.

Minimum designed feature is the minimum strictly positive primitive dimension, positive shared-face width/height, and coordinate-compressed cell thickness after excluding zero/absent slots. Minimum solid load path is derived from `S_solid=U4_candidate_body_closure(F_fluid)` as the minimum positive face-normal separation between non-intentional fluid boundaries or between fluid and exterior, excluding the four declared ports and sensor interface. A deterministic coordinate-compressed solid-cell adjacency audit must confirm a boundary-supported solid component and compute this minimum; no threshold value may be inserted as an observed result.

Fail codes include `CAD_ENVELOPE_X/Y/Z_EXCEEDED`, `CAD_MIN_FEATURE_BELOW_THRESHOLD`, `CAD_SOLID_LOAD_PATH_BELOW_THRESHOLD`, `CAD_SOLID_SUPPORT_DISCONNECTED`, `CAD_INTERFACE_MISMATCH`, `CAD_FLUID_COMPONENT_COUNT_NOT_ONE`, `CAD_DOF_CAP_EXCEEDED`, `CAD_BOUND_VIOLATION`, and the root/overlap codes above.

## 7. Matched-cost fairness and complexity

All families use the same target/interval, central share, sector frame, interface, envelope caps, feature/load-path thresholds, cavity/root bounds, bisection, Boolean accounting, connector length, fixed spine, outer passage and failure policy. Family-specific rules are limited to the sealed scientific coordinates that must differ by family.

Recommended D3-A reserves four inner connector slots and one outer connector slot per sector for every family. Unused slots remain explicit `DISABLED_FIXED_SLOT` entries; template capacity and all scientific latent coordinates are counted, while disabled slots add no fluid volume. Report the complexity vector `(active_box_count, reserved_slot_count, scientific_DOF, fixed_CAD_constants, replicated_mapping_count)`. Caps apply identically; no family receives an unreported primitive or latent coordinate.

D3-B requires equal active primitive count by solid padding; D3-C uses a common Pareto cap without reserved slots. Both remain possible but have greater risk of artificial padding or family-dependent template capacity.

## 8. Status, set blocking and no repair

Member statuses remain exactly `STATIC_IDENTITY_ELIGIBLE`, `COST_INELIGIBLE`, `GENERATION_TECHNICAL_FAILURE`. This proposal emits none of them. Static scientific mismatch gives `COST_INELIGIBLE`; implementation/schema/hash/non-finite/unclassified failures give `GENERATION_TECHNICAL_FAILURE`.

Future set states are `SCIENTIFIC_IDENTITY_AND_STATIC_ELIGIBILITY_COMPLETE` for 80/80 eligible, `IDENTITY_SET_STATIC_ELIGIBILITY_BLOCKED` for any cost-ineligible slot and no technical failure, and `IDENTITY_SET_TECHNICAL_FAILURE_BLOCKED` for any technical failure, missing/duplicate slot or provenance failure. Failures preserve family/member/seed/row and slot. No repair, redraw, replacement, drop, threshold change, re-sampling or scope shrink is allowed.

## 9. Nonformal falsification fixtures only

Fixtures are contracts with literal logic and object class `TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY`: SI dimensional consistency; central/local volume conservation; `a=0/1` aperture limits; exact root endpoints/ties; impossible root; RANDOM all-zero and disconnected reduced graphs; fluid disconnection by removed spine; deliberate overlaps; feature/load-path/cap boundaries; and 90-degree rotation/symmetry invariance. This stage does not execute them and creates no geometry/generator output.

## 10. Four user decisions

1. **D1 template:** T1 square exact-volume template (**recommended**); T2 nominal-circular/P05-derived template with analytic circular-overlap rules; or reject both and return `ESCALATE`. T1 has the cleanest accounting but is the largest new semantic departure; T2 has stronger provenance resemblance but risks silently privileging P05 and is harder to falsify.
2. **D2 RANDOM zero edge:** separate reduced and fluid graphs (**recommended D2-A**); make them identical; or keep a common fluid spine but fail disconnected reduced graphs. D2-A retains frozen random identities and makes the distinction auditable; the others change which numeric members can be cost eligible.
3. **D3 complexity:** common reserved slot capacity with a disclosed complexity vector (**recommended D3-A**); equal active count by inert padding; or common Pareto caps without slot reservation. D3-A most directly exposes hidden template capacity.
4. **D4 geometry-volume conflict:** retain the member as `COST_INELIGIBLE` and statically block the set (**recommended D4-A**); block the whole family at first conflict; or reject the common template before any identity execution. All three fail closed and prohibit changing scientific parameters.

No additional scientific semantic choice is delegated to code. If the user rejects both D1 templates or asks for a topology not expressible without a new research family, terminal state becomes `ESCALATE`.

## 11. Future implementation structure and stop rule

Only after guardian review and explicit user confirmation may a new, separately reviewed implementation delta be authored. Proposed future paths, schemas, commands, required fields and null hashes are frozen in `dependency_and_stop_rules.json`. The rejected `scripts/gen_enc_2c_*` and REV01 schemas remain untouched and forbidden as execution paths.

This phase performed only read-only provenance review and deterministic algebra. Formal seed, generator, CAD kernel, solver, COMSOL, full-wave, response, timing, endpoint, ranking, development, validation and final-test counts remain zero; all identity hashes remain null; `active_questions_closed=0`; `bidirectional_discovery_established=false`. Stop at `READY_FOR_GUARDIAN_AND_USER_REVIEW`; do not contact guardian, commit, push, tag or release.
