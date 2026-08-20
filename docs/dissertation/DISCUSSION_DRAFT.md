# Discussion Draft

## 1. Interpretation within the frozen boundary

The final disposition is `supported_with_limits`. H0 remains `not_rejected`, H1 remains `not_confirmed`, `scientifically_eligible=false`, and `final_test_read=false`.

These states permit a bounded account of measured spectral differences. They do not support unrestricted inference about configuration superiority, four-direction identification, deployment, or unseen data.

## 2. Direction-related change relative to repeatability

Figure 1 and Table 1 establish the technical-repeat reference before any direction comparison. The primary-band CONT floor had median 0.3783 dB, IQR 0.2191 dB, and p95 0.8793 dB.

The p95 value was a conservative empirical boundary from all CONT pairs, not a universal psychoacoustic or physical threshold.

Figure 2 shows the block-specific direction spectra, while Figure 3 compares pairwise direction effects with the CONT p95 floor.

All six U4ENC direction pairs exceeded the floor in both AS01 REPOS blocks. Three of six U4SYM pairs met the same criterion.

This pattern indicates that direction changes produced spectral differences larger than ordinary consecutive-repeat variation in the retained AS01 data.

It does not show that every direction can be assigned correctly in unseen blocks. Floor exceedance is a physical-distance observation, whereas prediction is a separate validation task.

Ordinary-room reflections can contribute direction-dependent structure and interact with device geometry. That context limits attribution to the internal morphology alone.

[CITATION NEEDED: room–object interaction in directional responses]

## 3. U4ENC and U4SYM direction-effect gains

Figure 4 and Table 2 show the frozen gain estimates and intervals. U4ENC had `G_demeaned=1.2805`, compared with 0.6824 for U4SYM.

The U4ENC interval was 0.8297–1.7667, so its lower bound did not exceed the frozen reference of 1.

The point-estimate contrast was `ΔG=0.5982`, but its 95% interval was -0.1131–1.0843 and crossed zero.

The estimates therefore followed the proposed ordering, but the uncertainty did not meet the preregistered confirmatory rules.

This explains how a descriptive direction effect can coexist with `H0=not_rejected` and `H1=not_confirmed`.

H0 covered more than the existence of any spectral difference. It also required the encoded structure to outperform repeatability and comparison-structure boundaries with adequate uncertainty control.

H1 required the full set of frozen conditions. Direction-pair floor exceedance alone was insufficient when the U4ENC interval crossed 1 and the contrast interval crossed zero.

The contrast between a favourable point estimate and an interval crossing the null is central to the interpretation of finite repeated-measure data. [CITATION NEEDED: confidence intervals and bounded scientific claims]

## 4. Configuration differences and assembly-state observations

Figure 5 reports U4ENC–U4SYM frequency-response differences. In AS01, all four direction-specific configuration effects exceeded the CONT p95 floor.

The median AS01 effect/floor ratio was 1.5688. This supports a measurable configuration difference under the retained AS01 conditions.

That observation is not equivalent to stronger direction encoding. The `ΔG` interval and grouped classification address that more demanding claim and did not pass their frozen targets.

AS01 contained two REPOS blocks per configuration. AS02 contained only B05 for U4ENC and B07 for U4SYM.

Consequently, AS02 lacked a within-configuration cross-REPOS denominator. This created a block/time/assembly confound because session and acquisition time also changed.

AS01–AS02 differences can therefore be reported only as exploratory observations. They cannot be assigned uniquely to reassembly.

Future assembly comparisons need independent assembly states with repeated repositioning under a schedule that separates assembly, block, session, and time. [CITATION NEEDED: design of repeated-measure assembly experiments]

## 5. Grouped classification as a negative result

Figure 7 and Table 3 report leave-one-block-out classification. U4SYM balanced accuracy was 0.375 with macro-F1 0.250.

U4ENC balanced accuracy was 0.250 with macro-F1 0.183. The frozen practical target was 0.50 and the four-class chance level was 0.25.

Neither AS01 configuration reached the practical target. The U4ENC result equalled chance on balanced accuracy.

Each result used two folds and eight grouped predictions. This limited coverage makes the scores uncertain, but it does not justify replacing the grouped protocol with a random split.

The exploratory all-assembly U4ENC score reached 0.500. It mixed assembly and acquisition time across three blocks and cannot override the AS01 result.

Grouped validation is essential when technical repeats share a physical state, because random repeat-level splitting can leak state-specific information. [CITATION NEEDED: grouped cross-validation for repeated measurements]

The classification outcome is therefore a formal negative result: the measured differences did not translate into the prespecified level of four-direction prediction.

## 6. Outlier sensitivity and result stability

Figure 6 and Table 4 compare the primary analysis with a temporary sensitivity view that omitted 10 flagged curves.

All 72 ACTIVE curves remained in the primary analysis. The 19 EXCLUDED records remained outside every feature, statistic, training, and result artifact.

The temporary omission changed U4ENC `G_demeaned` from 1.2805 to 1.2790 and `ΔG` from 0.5982 to 0.5739.

U4SYM and U4ENC grouped balanced accuracy remained 0.375 and 0.250. No frozen threshold conclusion changed.

The sensitivity result reduces concern that the headline pattern was caused only by the flagged curves. It does not convert flags into invalid measurements or authorise post-hoc deletion.

## 7. Engineering significance for acoustic morphology encoding

The data show that passive morphology can coincide with direction-related spectral structure above the consecutive-repeat floor in an ordinary room.

This is useful engineering evidence because it identifies measurable response channels that may be shaped through geometry.

The encoded structure also had the higher direction-gain point estimate, but the uncertainty and classification outcomes show that the present encoding was not sufficiently stable for a stronger claim.

The result suggests that future morphology design should optimise both effect magnitude and invariance across repositioning, reassembly, session, and room conditions.

Frequency regions contributing to the effect should be selected only within a new preregistered development process. WRITE-3 does not reopen frequency selection or model search.

The relationship between passive acoustic shape and robust directional features requires external support and independent replication. [CITATION NEEDED: passive acoustic morphology for spatial encoding]

## 8. Implications for subsequent work

A future study should increase independent REPOS and REASM blocks rather than increasing only CONT sweeps.

The design should balance assembly, session, time, and direction order, and should preserve an untouched evaluation partition under a separately approved access procedure.

Measurement stability could be improved through better geometry fixtures, contemporaneous environmental logging, calibrated source monitoring, and replication across microphones and rooms.

Classification development should remain grouped by physical state. Model or frequency choices should be frozen before evaluation and assessed with more held-out blocks.

These changes would target the present weaknesses: broad gain intervals, incomplete AS02 replication, room dependence, and sub-target grouped prediction.

## 9. Integrated interpretation

Figures 1–3 support the presence of measurable direction-related spectral variation above the CONT floor.

Figures 4–5 show favourable U4ENC point estimates and measurable configuration differences, while retaining interval and assembly-confounding limits.

Figures 6–7 show that outlier sensitivity did not change the frozen conclusions and that grouped classification missed the 0.50 target.

Together, Tables 1–4 support a bounded engineering interpretation rather than a confirmatory superiority or prediction claim.

The approved summary is: the encoded structure produced direction-related spectral changes above the repeatability floor, but between-configuration uncertainty and classification performance missed the preregistered criteria.
