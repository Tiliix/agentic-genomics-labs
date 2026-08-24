# Single-Cell RNA-seq Analysis Report: PBMC 3k

**Date:** August 21, 2026  
**Dataset:** 10x Genomics Peripheral Blood Mononuclear Cells (PBMC), 3k Healthy Donor  
**Pipeline:** Agentic Scanpy automated workflow (Leiden clustering, optimal resolution algorithm)

---

## 1. Executive Summary
This report details the tertiary analysis of ~2,700 single cells from a healthy human donor peripheral blood sample. An AI-driven iterative clustering pipeline was utilized to optimize the Leiden community detection resolution. The algorithm evaluated 10 distinct resolutions (from 0.20 to 1.80) and identified **Resolution 0.91** as the mathematically and biologically optimal threshold, yielding **9 distinct cell populations**. This granularity perfectly captures the expected major immune lineages without over-fragmenting functionally identical cell states.

## 2. Quality Control & Preprocessing
- **Cell Filtering:** Cells expressing < 200 genes or > 2,500 genes (probable doublets) were removed.
- **Mitochondrial Threshold:** Cells with > 5.0% mitochondrial read fraction were filtered out to eliminate dead, dying, or lysed cells.
- **Dimensionality Reduction:** Data was library-size normalized (1e4), log-transformed, and subset to the top 2,000 highly variable genes. Principal Component Analysis (PCA) and a 15-nearest neighbor (kNN) graph were used to map the topological space.

## 3. Biological Insights: Identified Populations
At the optimal resolution of 0.91, the 9 clusters correspond tightly to the canonical PBMC compartments. Based on the top differentially expressed marker genes (Wilcoxon rank-sum test), the populations are characterized as follows:

### The Lymphoid Lineage
* **CD4+ T Cells (IL7R, CD3D):** The most abundant population in the sample. Shows high expression of canonical T-cell receptor genes and IL7R, indicative of resting/naive and memory CD4+ states.
* **CD8+ T Cells (CD8A, CD8B):** Distinct from the CD4+ compartment, these cells show baseline expression of cytotoxic markers.
* **Natural Killer (NK) Cells (NKG7, GNLY):** A highly distinct cluster defined by robust expression of granzymes and granulysin, confirming a strong innate cytotoxic footprint.
* **B Cells (MS4A1, CD79A):** Cleanly separated cluster expressing canonical CD20 (MS4A1) and B-cell receptor complex proteins.

### The Myeloid Lineage
* **CD14+ Monocytes (CD14, LYZ):** A large, transcriptionally active cluster representing classical monocytes, marked by intense lysozyme (LYZ) and CD14 expression.
* **FCGR3A+ (CD16+) Monocytes (FCGR3A, MS4A7):** A smaller, distinct non-classical monocyte population. The clear separation of these two monocyte states validates the choice of the 0.91 resolution, as lower resolutions (e.g., 0.38) merged these functionally distinct populations.
* **Dendritic Cells (FCER1A, CST3):** Professional antigen-presenting cells cleanly isolated from the broader monocyte cluster.

### Rare Populations
* **Megakaryocytes / Platelet precursors (PPBP):** A very small but highly distinct cluster characterized by platelet basic protein (PPBP), demonstrating the pipeline's sensitivity to rare (< 2%) cell types.

## 4. Significant Findings & Next Steps

### Significant Results
1. **Successful Myeloid Resolution:** The pipeline successfully captured the bifurcation of the monocyte lineage (Classical CD14+ vs. Non-classical FCGR3A+). This is a critical QC hallmark of a well-calibrated PBMC analysis.
2. **Optimal Granularity:** The automated resolution iteration proved that resolutions below 0.70 fail to resolve NK cells from CD8+ T cells, while resolutions above 1.20 begin to artificially slice the CD4+ T cell cluster into arbitrary mathematical fragments with no distinct biological markers.

### Suggested Follow-up Analysis (Next Steps)
To build upon this baseline reference, the following computational and wet-lab experiments are recommended:

1. **Sub-clustering of the T-Cell Compartment:**
   * *Rationale:* The current CD4+ and CD8+ clusters likely contain a mixture of Naive, Central Memory, and Effector Memory states. 
   * *Action:* Isolate the T-cell clusters and run a targeted, high-resolution re-clustering (with specialized markers like *CCR7*, *SELL*, *CD45RA*) to map the immune memory landscape.
2. **Trajectory Inference (Pseudotime):**
   * *Rationale:* Monocytes exist on a differentiation continuum from CD14+ classical to FCGR3A+ non-classical states.
   * *Action:* Apply algorithms like *Monocle3* or *PAGA* to model this transition and identify the transient gene regulatory networks driving monocyte maturation.
3. **Comparative Differential Expression (Disease vs. Healthy):**
   * *Rationale:* This dataset serves as a healthy baseline. 
   * *Action:* Integrate this AnnData object (using *Harmony* or *scVI*) with a disease cohort (e.g., autoimmune or infectious disease) to perform cell-type-specific differential abundance and expression analysis.
4. **Wet-Lab Validation (FACS):**
   * *Rationale:* Confirm the computationally derived proportions.
   * *Action:* Design a multi-color flow cytometry panel targeting CD3, CD4, CD8, CD14, CD16, and CD20 to physically validate the relative abundance of these 9 populations in the original donor blood.
