# COMSOL Scheme 3A — P04C single-entry topology/mode diagnostic

## Status

`P04C TOPOLOGY HYBRIDIZATION SUPPORTED`

Secondary flags:

- `metric_mismatch_supported=false`;
- `reduced_model_suspected=false`;
- broad-band branch results are exploratory, not replacement centre estimates.

The accepted phase states remain unchanged: P03 local `as_designed_close`, P04A `INADEQUATE`, and P04B-N `MODEL NOT CREDIBLE FOR U4`. No P05, P06, U4, full array, external field or classifier work was started. `final_test_read=false`.

## Frozen contract and authority

Before any new compartment-resolved value was read, `diagnostic_contract.json` was written and frozen at SHA-256 `1be500f1dad6de4a1b14cf97ce772113d5b50408e2f2eca4dfc12efd6fe5bdc0`. It fixes the source models and `dset1/sol1`, named selections, pressure/kinetic-energy formulas, all-peak logic, branch cost, classifications, and the no-solve rule.

The P03, P04A and P04B-N authority manifests were recomputed as 37/37, 124/124 and 94/94 matches. All eight production MPH hashes and the HR04/HR07 mesh-2 hashes match `model_manifest.csv`. Existing geometry, connectivity and selection gates remain valid. The ten P04B-N MPH files were loaded only to evaluate their saved 256-frequency solutions. Temporary Results `IntVolume`, `AvVolume` and `AvSurface` nodes existed only in memory; no study, mesh or geometry was run and no model was saved.

The stable volume selections were available for HR inner neck, HR cavity, HR outer neck, whole HR module, fixed inner passage, central chamber, fixed outer passage and whole fluid. `sel_mic_nominal` is a stable 2-D sampling boundary, so its complex average is valid. No stable 3-D microphone-neighbourhood selection exists; its volume energy is explicitly unavailable and was not guessed. This does not block the present distinction because the chamber/microphone complex relation and all other required compartment energies were evaluable.

Some frozen box selections overlap where the integrated HR geometry partitions the original fixed passage. The overlap is enumerated in `region_selection_audit.csv`; participation vectors are therefore descriptive signatures, not additive causal percentages.

## HR03 controlled differential

P03's isolated centres remain 1890.62 Hz (reduced fine) and 1904.19 Hz (full Thermoviscous fine), with accepted two-mesh evidence. In integrated S1, the full-band HR03 energy candidates refine to approximately 1430.01, 1650.40, 3087.33, 3300.23 and 4070.20 Hz. There is no discrete cavity-energy local maximum between 1900 and 2000 Hz.

At the sampled 1646.88 Hz landmark:

- HR cavity total energy is 59.37% of whole-module total and is the largest leaf-region contribution;
- whole-module kinetic fraction is 44.08%;
- combined inner/outer-neck kinetic energy is 36.15% of whole-module total;
- cavity energy is pressure dominated (`Ek/Etotal=0.134`), while inner and outer necks are individually kinetic dominated;
- cavity–chamber phase is 174.21°, so the cavity and chamber are nearly antiphase.

Thus the P04B target-window boundary behaviour is not caused by neck kinetic energy overwhelming a still-present 1900–2000 Hz cavity peak. The local cavity branch itself has shifted downward: the 1904.19-to-1646.88 displacement is −0.209 octave (−13.51% in frequency). The refined integrated peak is 1650.40 Hz. Existing evidence supports topology loading/reorganization; it does not uniquely identify one geometric subcomponent as causal.

At 1986.97 Hz there is no internal-energy maximum. Chamber and microphone are almost phase locked (chamber-minus-microphone 0.021°), while cavity is nearly antiphase to both (cavity-minus-chamber 178.08°). The previously reported 1986.97 Hz microphone-relative feature is therefore an observation/transfer-interference feature tied to the chamber/microphone field, not an internal cavity-energy centre.

## Exploratory HR01–HR08 branch audit

All strict interior maxima from both whole-module and cavity-total energy were retained over 800–5000 Hz. The union contains 44 peaks; no target-nearest filter or prominence cutoff was used. Three-point log-frequency refinement was applied only to interior candidates.

The frozen frequency/participation/kinetic-fraction/phase cost yields nine branch identifiers. Seven span more than one module. In particular:

- B01 and B02 are moving low-frequency branches, spanning about 1109–1465 Hz and 1520–2480 Hz;
- B03 is compressed to about 3087–3120 Hz across all eight modules;
- B05 is compressed to about 3300–3361 Hz across all eight modules;
- B07 is a high branch spanning about 3964–4205 Hz across all eight modules;
- five accepted adjacent links meet the frozen participation-exchange rule;
- the frozen split predicate is met in every module because multiple separated peaks have participation cosine below 0.90;
- HR06–HR08 each retain cavity-triggered peaks above 3 kHz, satisfying the predeclared high-frequency reappearance descriptor.

The repeated compressed branches and participation exchanges are incompatible with a picture in which each installed HR behaves as one independently translated local resonance. They support a shared-topology modal family. These descriptors remain exploratory and do not turn P04B-N boundary maxima into valid centres.

## Answers to the nine required questions

1. **What mainly caused P04B-N to fail?** The evidence supports topology-associated reorganization of the isolated HR modes after connection to the fixed passages and shared chamber. Several compressed shared branches coexist with moving module/cavity branches, so the target-window single-centre assumption fails for HR02–HR05.
2. **Was whole-module energy dominated by neck kinetic energy?** No at the critical HR03 landmark. At 1646.88 Hz the cavity supplies 59.37% of module energy, whole-module kinetic fraction is 44.08%, and combined neck kinetic energy is 36.15%.
3. **Does a cavity mode still exist?** Yes, but not near 1900–2000 Hz in integrated S1. The cavity-dominated integrated branch is at about 1647–1650 Hz, with additional cavity-bearing branches elsewhere in the band.
4. **What happened to P03's approximately 1900 Hz mode after S1 connection?** Its best-supported integrated correspondence is a substantial downward drift/reorganization to the approximately 1650 Hz cavity-dominated branch, not a hidden 1900–2000 Hz cavity-energy peak. The present data cannot label that correspondence as a unique causal mode continuation.
5. **Are branch compression, splitting or participation exchange present?** Yes, exploratorily: B03/B05 meet the frozen compression rule, all modules meet the broad split predicate, and five adjacent links meet the participation-exchange rule.
6. **Why does the microphone feature differ from the internal-energy centre?** At 1986.97 Hz the microphone tracks the chamber phase while the cavity is nearly antiphase, and no compartment-energy maximum occurs. The relative microphone feature is an observation/transfer-interference feature, not stored-energy resonance identity.
7. **Can the evidence support a thesis-level mechanism conclusion?** It supports the bounded statement that connecting the nominal module to the S1 receiving topology is associated with modal reorganization and shared branches. It does not prove a causal four-port U4 mechanism, direction recognition, or U4HR superiority.
8. **What is the next step?** Stop here under the current authority. If the mechanism must be strengthened, the next separately authorized simulation should be exactly one nominal full-Thermoviscous HR03 S1 control on one accepted mesh. Do not enter topology-isolated design simulation yet.
9. **Why can P05/U4 still not begin?** P04B-N's formal stable-module interior-centre and mesh gates remain failed; P04A provides no identifiable calibration; P04C is diagnostic and does not repair those gates. The U4 entry authority is therefore still absent.

## Classification boundary

The frozen metric-mismatch predicate is false because no 1900–2000 Hz cavity peak exists and the 1646.88 Hz whole-module peak is cavity-pressure dominated rather than neck-kinetic dominated. The reduced model is not singled out because the compartment and cross-module evidence already explains the discrepancy through topology. A future full-Thermoviscous S1 control would test robustness, not rescue P04B-N or authorize U4.

No frequency-domain study was run, no authority model was modified or saved, no calibration bound or parameter was changed, and no git write, commit, push, tag or release occurred. Work stops at P04C pending user acceptance.
