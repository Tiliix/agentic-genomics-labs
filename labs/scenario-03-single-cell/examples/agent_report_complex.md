# Single-Cell Agent Report

**Dataset:** Kang 2018 IFN-beta PBMC (ctrl vs stim, ambiguity-prone)  
**Mode:** 1  **Selected resolution:** 1.0

## Cell-type annotations

| Cluster | Cell type | Confidence | Ambiguous | Notes |
|---|---|---|---|---|
| 0 | CD14+ Monocytes | 0.7 | True | S100A8/S100A10/IL8 and lack of clear CD14/LYZ/CTSS suggest an activated inflammatory myeloid or neutrophil-like population rather than canonical CD14+ monocytes. |
| 1 | T cells | 0.3 | True | Markers are mostly housekeeping and RNA-processing genes without T-cell–specific markers (CD3D/E, TRAC, LST1, MS4A1, etc.), so the T-cell label is not well supported. | cross-readout conflict: IFN_response (prevalence-only); Cell_cycle (prevalence-only) |
| 2 | Cytotoxic T cells | 0.6 | True | GZMB suggests cytotoxic lymphocytes, but CD74 and HLA-DRA are strong APC/B-cell/DC markers; absence of clear CD3 or NK receptor markers makes the cytotoxic T-cell label uncertain. | cross-readout conflict: Cell_cycle (prevalence-only) |
| 3 | T cells | 0.3 | True | Ribosomal genes dominate and no lineage-defining T-cell markers are listed, so this may represent a high-translation state rather than a specific T-cell subset. |
| 4 | CD4+ T cells | 0.6 | True | GIMAP7 is T-cell–associated but no CD4, CCR7, IL7R, or other clear CD4-naive/memory markers are shown; cannot confidently distinguish CD4+ from CD8+ or other T-cell states. |
| 5 | NK cells | 0.9 | True | Strong cytotoxic/NK signature (GNLY, NKG7, GZMB, PRF1, CCL5, CST7) with no B/T markers supports NK-cell identity. | cross-readout conflict: Cell_cycle (prevalence-only) |
| 6 | NK cells | 0.9 | False | Similar to cluster 5 with NKG7, CCL5, GZMB, CST7 and MHC-I; consistent with NK cells. |
| 7 | B cells | 0.9 | True | CD74, CD79A, CD37 and strong HLA-II expression are characteristic of B cells. | cross-readout conflict: Cell_cycle (prevalence-only) |
| 8 | Naive/central memory B cells | 0.8 | True | B-cell markers (CD74, CD79A) plus interferon-stimulated genes (ISG20, IFIT3, PSMB9); CCR7 alone is insufficient to define naive/central memory B cells, so the specific state is uncertain. |
| 9 | Megakaryocytes | 1.0 | True | PPBP, PF4, TUBB1, GNG11, SDPR are canonical megakaryocyte/platelet markers. | cross-readout conflict: Cell_cycle (intensity-only) |
| 10 | Activated dendritic cells | 0.7 | True | CD83 and HLA-DQA1/DRA suggest activated APCs, but lack of clear DC-specific markers (e.g., FCER1A, CLEC9A) vs. B-cell markers (MS4A1, CD79A) makes precise DC vs. B distinction unclear. |
| 11 | FCGR3A+ Monocytes | 0.9 | True | FCGR3A, MS4A7, LST1, AIF1 are typical of non-classical/FCGR3A+ monocytes. | cross-readout conflict: Stress_response (intensity-only) |
| 12 | Dendritic cells | 0.8 | True | Strong HLA-II and CD74 with CST3 and LYZ indicate professional APCs; could be classical DCs or B cells/monocyte-derived DCs, but no clear lineage-specific markers to resolve. | cross-readout conflict: IFN_response (prevalence-only) |
| 13 | FCGR3A+ Monocytes | 0.9 | False | FCGR3A, MS4A7, MS4A4A with interferon/inflammatory genes (IFITM3, CXCL10) fit activated FCGR3A+ monocytes. |
| 14 | Erythroid cells | 1.0 | True | Hemoglobin genes (HBB, HBA1/2, HBD) and ALAS2 clearly indicate erythroid cells. | cross-readout conflict: Cytotoxicity (intensity-only); Antigen_presentation (prevalence-only); Cell_cycle (intensity-only) |
| 15 | Inflammatory monocytes/dendritic cells | 0.6 | True | Strong interferon/inflammatory signature (APOBEC3A, ISG15, CXCL10, RSAD2) but no clear CD14, FCGR3A, or DC-defining markers; cannot confidently distinguish inflammatory monocytes from DCs. |

## Cross-readout disagreement (intensity vs prevalence)

70 survive on intensity, 73 on prevalence, 66 on both (11 discordant).

These contrasts are significant by exactly one readout. Both are defensible; the agent flags them for review rather than resolving them.

| Cluster | Program | Significant by | delta_mean | delta_frac_on |
|---|---|---|---|---|
| 1 | IFN_response | prevalence | -0.0271 | -0.0434 |
| 12 | IFN_response | prevalence | 0.1957 | 0.1009 |
| 14 | Cytotoxicity | intensity | -0.1273 | -0.0621 |
| 14 | Antigen_presentation | prevalence | -0.2198 | -0.1000 |
| 1 | Cell_cycle | prevalence | 0.0481 | 0.1100 |
| 2 | Cell_cycle | prevalence | 0.0704 | 0.0839 |
| 5 | Cell_cycle | prevalence | 0.0075 | 0.0427 |
| 7 | Cell_cycle | prevalence | 0.0141 | 0.0323 |
| 9 | Cell_cycle | intensity | 0.0073 | -0.0022 |
| 14 | Cell_cycle | intensity | -0.0036 | -0.0367 |
| 11 | Stress_response | intensity | 0.1122 | 0.0166 |

### Agent weigh-in (per discordant contrast)

- **Cluster 1 / IFN_response** - prevalence-driven: a modestly smaller fraction of cells are above the IFN-response threshold, but among IFN-on cells the per-cell program level is similar between conditions, suggesting a shift in how many cells participate rather than how strongly each responding cell is activated. _Next:_ Plot the full score distribution (e.g., violin/density) and on-fraction for IFN_response in cluster 1, and cross-check with canonical IFN genes; if the effect is subtle and mostly a change in fraction near the threshold, consider sensitivity analyses with alternative thresholds or a continuous model (e.g., logistic regression on score) before interpreting this as a robust biological difference.
- **Cluster 12 / IFN_response** - prevalence-driven: many more cells cross the IFN-response on-threshold in one condition (delta_frac_on > 0), but the average score among all cells does not change significantly, implying a broad recruitment of additional cells into a low-to-moderate IFN state rather than a strong upregulation in a small subset. _Next:_ Inspect per-cell score distributions and the location of the null threshold; verify that newly IFN-on cells show coherent upregulation of key IFN genes and are not driven by a few noisy genes, and, if consistent, treat this as a condition-level shift in the proportion of IFN-primed cells rather than a change in IFN intensity per cell.
- **Cluster 14 / Cytotoxicity** - intensity-driven: among cytotoxicity-positive cells, the program score is substantially lower in one condition (delta_mean negative and highly significant), but the fraction of cytotoxic cells does not change convincingly, indicating that cytotoxic cells remain present but are functionally dampened rather than lost. _Next:_ Stratify cluster 14 by cytotoxicity on/off and compare score distributions only within the on-cells; validate with key effector genes (e.g., GZMB, PRF1) and, if possible, orthogonal functional readouts (e.g., degranulation markers or killing assays) to confirm that cytotoxic potential is reduced per cell rather than a change in cell abundance.
- **Cluster 14 / Antigen_presentation** - prevalence-driven: a smaller fraction of cells are above the antigen-presentation threshold, but the mean score across all cells is not significantly different, suggesting that fewer cells engage this program while those that remain on do so at similar intensity. _Next:_ Examine the distribution of antigen-presentation scores and expression of core genes (e.g., HLA class I/II, B2M) to confirm a discrete on/off shift; if supported, interpret this as a reduction in the proportion of antigen-presenting cells within cluster 14 and consider re-annotating or subclustering to see whether a specific subpopulation is being lost or reprogrammed.
- **Cluster 1 / Cell_cycle** - prevalence-driven: a markedly larger fraction of cells are cell-cycle positive (very significant delta_frac_on), but the average program score changes only modestly, indicating that more cells are entering a similar, relatively mild proliferative state rather than a few cells becoming highly proliferative. _Next:_ Quantify the fraction of S/G2M-phase cells using canonical markers and compare to the program-based on-fraction; if consistent, treat this as a shift in cycling fraction and consider whether this reflects biological proliferation versus technical confounders (e.g., cell doublets or sampling bias), possibly regressing out cell-cycle effects in downstream analyses if they obscure other biology.
- **Cluster 2 / Cell_cycle** - prevalence-driven: a modest but significant increase in the proportion of cycling cells with only a small change in mean score, consistent with more cells entering a low-to-moderate cycling state rather than a strong proliferative burst in a subset. _Next:_ Check phase assignments (G1/S/G2M) and the distribution of cell-cycle scores to confirm that the added cycling cells are bona fide; if validated, interpret as a mild expansion of proliferating cells and consider whether this aligns with known biology of cluster 2 (e.g., progenitor vs mature state) before overemphasizing the effect.
- **Cluster 5 / Cell_cycle** - prevalence-driven: a clear increase in the fraction of cells above the cell-cycle threshold despite a negligible change in mean score, implying that many cells are just crossing into a weakly cycling state rather than a few cells becoming strongly proliferative. _Next:_ Re-express the data as the proportion of cells in active cell-cycle phases and visualize score distributions around the threshold; if the effect is driven by cells just above the cutoff, perform robustness checks with alternative thresholds or a continuous regression model to ensure this is not an artifact of the chosen null cutoff.
- **Cluster 7 / Cell_cycle** - prevalence-driven: a small but statistically robust increase in the fraction of cycling cells with minimal change in mean intensity, suggesting a subtle recruitment of additional cells into a mild cycling state rather than a major proliferative shift. _Next:_ Overlay cell-cycle scores on the UMAP/embedding for cluster 7 and verify that the additional cycling cells form a coherent sub-region; if they cluster spatially or transcriptionally, consider subclustering to determine whether a distinct proliferative subpopulation is emerging.
- **Cluster 9 / Cell_cycle** - intensity-driven: the mean cell-cycle score is slightly but significantly higher in one condition while the fraction of cells above the on-threshold is unchanged, indicating that already cycling cells are modestly more active rather than more cells entering the cell cycle. _Next:_ Restrict analysis to cell-cycle–positive cells and compare their score distributions and phase composition (S vs G2M) between conditions; if the shift is consistent across many cells rather than driven by outliers, interpret as a mild increase in proliferative intensity per cycling cell and consider whether this has functional relevance for cluster 9.
- **Cluster 14 / Cell_cycle** - intensity-driven: the mean cell-cycle score is slightly but significantly lower while the fraction of cycling cells does not change convincingly, suggesting that cycling cells in cluster 14 are present at similar frequency but are less strongly engaged in the program (e.g., slower cycling or partial exit from cycle). _Next:_ Within cluster 14, compare S/G2M-phase scores and key cell-cycle gene expression among cycling cells between conditions; if consistent with a global dampening, consider whether this reflects differentiation, exhaustion, or treatment effects, and validate against independent proliferation markers (e.g., Ki-67 if available).
- **Cluster 11 / Stress_response** - intensity-driven: stress-response–positive cells show a strong increase in program score (very significant delta_mean) with only a minor, non-significant change in the fraction of on-cells, indicating that the same subset of cells is experiencing a much stronger stress response rather than more cells becoming stressed. _Next:_ Focus on stress-response–positive cells in cluster 11 and examine expression of core stress genes (e.g., heat-shock, unfolded protein response, oxidative stress markers); if the pattern is coherent, treat this as a robust per-cell stress amplification and assess whether it correlates with technical factors (e.g., mitochondrial content, dissociation time) versus a biologically meaningful stress state.

### Agent recommendation

For contrasts where only one readout is significant, interpret prevalence-driven hits as changes in how many cells participate in a program (on/off recruitment) and intensity-driven hits as changes in how strongly already-participating cells engage the program. In each case, inspect full score distributions, key marker genes, and sensitivity to threshold choice or alternative continuous models to rule out artifacts. Treat these discordant results as hypothesis-generating and decide, based on your biological question (cell-state abundance vs per-cell activity), whether to prioritize prevalence or intensity for interpretation; the final choice of which signal to emphasize should rest with you, informed by these checks and the broader experimental context.

---
> **Final call:** This report is advisory. The researcher makes the final decision on every ambiguous or discordant result above.
