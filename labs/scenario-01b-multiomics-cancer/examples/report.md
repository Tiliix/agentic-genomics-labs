# Example Output — Multi-Omics Tumor Board Conditional Routing (`Cases A, B, and C`)

> **DISCLAIMER — RESEARCH / EDUCATION ONLY. NOT FOR CLINICAL USE.**
> This molecular tumor board summary was produced by an automated teaching pipeline on synthetic and public TCGA-BRCA research data using simplified heuristics. It must NOT be used to diagnose, treat, or make any medical decision.

---

## 1. Divergent Tool Paths Across the Three Breast-Cancer Archetypes

When you run `python scripts/run_cases.py --router-only` (or the live Azure OpenAI agent via `python scripts/run_cases.py`), the three cases take **three distinct, evidence-triggered paths** through the 12 deterministic omics skills in `src/omics.py`:

```text
==============================================================================
DETERMINISTIC ROUTER (no LLM) -- expected tool paths [SYNTHETIC & REAL TCGA-BRCA]
==============================================================================

Case A (HER2_AMP / TCGA-A2-A3XV-01) deterministic plan:
   1. [RUN ] inspect_case  -- Always start by discovering which omics layers are present.
   2. [RUN ] expression_qc  -- Expression layer present -> QC it before interpreting.
   3. [RUN ] receptor_status  -- Derive ER/PR/HER2 from ESR1/PGR/ERBB2 to anchor the subtype.
   4. [RUN ] cna_analysis {'gene': 'ERBB2'}  -- HER2 expression is high -> confirm ERBB2 amplification.
   5. [RUN ] mutation_analysis  -- Catalogue driver mutations and compute TMB.
   6. [SKIP] hrd_status  -- TMB low and no BRCA mutation -> HRD assessment not warranted.
   7. [SKIP] immune_infiltration  -- TMB low and no BRCA mutation -> immune profiling not warranted.
   8. [RUN ] methylation_analysis {'gene': 'BRCA1'}  -- Methylation layer present -> check BRCA1 promoter.
   9. [RUN ] pathway_enrichment  -- Summarise affected pathways from DE + drivers.
  10. [RUN ] survival_association {'marker': 'ERBB2'}  -- Prognostic context for the key marker (ERBB2).
  11. [RUN ] therapy_hint  -- Always finish by mapping findings to an actionable hint.
  PATH: inspect_case -> expression_qc -> receptor_status -> cna_analysis -> mutation_analysis -> methylation_analysis -> pathway_enrichment -> survival_association -> therapy_hint

Case B (TNBC_BRCA / TCGA-AO-A0J4-01) deterministic plan:
   1. [RUN ] inspect_case  -- Always start by discovering which omics layers are present.
   2. [RUN ] expression_qc  -- Expression layer present -> QC it before interpreting.
   3. [RUN ] receptor_status  -- Derive ER/PR/HER2 from ESR1/PGR/ERBB2 to anchor the subtype.
   4. [SKIP] cna_analysis  -- HER2 is not high -> ERBB2 amplification check not warranted.
   5. [RUN ] mutation_analysis  -- Catalogue driver mutations and compute TMB.
   6. [RUN ] hrd_status  -- TMB-high or BRCA1/2 mutation -> assess homologous-recombination deficiency.
   7. [RUN ] immune_infiltration  -- TMB-high or BRCA1/2 mutation -> assess immune hot/cold (immunotherapy relevance).
   8. [SKIP] methylation_analysis  -- Methylation layer ABSENT for this case -> skip gracefully.
   9. [RUN ] pathway_enrichment  -- Summarise affected pathways from DE + drivers.
  10. [RUN ] survival_association {'marker': 'TMB'}  -- Prognostic context for the key marker.
  11. [RUN ] therapy_hint  -- Always finish by mapping findings to an actionable hint.
  PATH: inspect_case -> expression_qc -> receptor_status -> mutation_analysis -> hrd_status -> immune_infiltration -> pathway_enrichment -> survival_association -> therapy_hint

Case C (LUMINAL_A / TCGA-D8-A1XV-01) deterministic plan:
   1. [RUN ] inspect_case  -- Always start by discovering which omics layers are present.
   2. [RUN ] expression_qc  -- Expression layer present -> QC it before interpreting.
   3. [RUN ] receptor_status  -- Derive ER/PR/HER2 from ESR1/PGR/ERBB2 to anchor the subtype.
   4. [SKIP] cna_analysis  -- HER2 is not high -> ERBB2 amplification check not warranted.
   5. [RUN ] mutation_analysis  -- Catalogue driver mutations and compute TMB.
   6. [SKIP] hrd_status  -- TMB low and no BRCA mutation -> HRD assessment not warranted.
   7. [SKIP] immune_infiltration  -- TMB low and no BRCA mutation -> immune profiling not warranted.
   8. [RUN ] methylation_analysis {'gene': 'BRCA1'}  -- Methylation layer present -> check BRCA1 promoter.
   9. [RUN ] pathway_enrichment  -- Summarise affected pathways from DE + drivers.
  10. [RUN ] survival_association {'marker': 'ESR1'}  -- Prognostic context for the key marker (ESR1).
  11. [RUN ] therapy_hint  -- Always finish by mapping findings to an actionable hint.
  PATH: inspect_case -> expression_qc -> receptor_status -> mutation_analysis -> methylation_analysis -> pathway_enrichment -> survival_association -> therapy_hint
```

---

## 2. Example Agent Report (`Case B — TNBC_BRCA`)

### Molecular Tumor Board Summary

- **Case & Subtype:**
  - **Case ID:** `B` (`TNBC_BRCA`, Synthetic Teaching / Real TCGA-BRCA counterpart `TCGA-AO-A0J4-01`)
  - **Subtype:** Basal-like / Triple-Negative Breast Cancer (`HR-negative`, `HER2-low` by `receptor_status`: `ESR1 = 2.3`, `PGR = 1.1`, `ERBB2 = 9.2` $\log_2$ units).

- **Key Molecular Findings:**
  - **Quality Control (`expression_qc`):** Passed (`pass = True`, 24 genes assayed, housekeeping `ACTB = 12.0`, `GAPDH = 11.9`).
  - **Somatic Mutations & TMB (`mutation_analysis`):** Pathogenic `BRCA1 c.68_69delAG` frameshift (`brca_mutated = True`), `TP53 R175H` missense, and `PTEN R130*` nonsense; elevated Tumor Mutational Burden (`TMB = 13.68 mut/Mb >= 10.0`, `tmb_high = True`).
  - **Homologous Recombination Deficiency (`hrd_status`):** `hrd_positive = True`, driven by pathogenic `BRCA1` loss and genomic-scar score `68.0 >= 42.0`.
  - **Tumor Microenvironment (`immune_infiltration`):** `phenotype = "hot (inflamed)"` (`immune_score = 9.0 >= 7.0` across `GZMA`, `PRF1`, `IFNG`, `CD8A`, `CXCL9`).
  - **Pathway Context (`pathway_enrichment` & `survival_association`):** Strong activation of proliferation (`MKI67`), basal keratins (`KRT5`, `KRT14`), and cytolytic T-cell/IFN-$\gamma$ signaling, alongside mutated `BRCA1`, `TP53`, and `PTEN` in DNA-damage and PI3K-AKT pathways.

- **Tools Skipped and Rationale:**
  - **`cna_analysis('ERBB2')` — Skipped:** `receptor_status` returned `her2_high = False` (`ERBB2 = 9.2 < 12.0`), so confirmatory `ERBB2` focal amplification testing was not warranted.
  - **`methylation_analysis('BRCA1')` — Skipped:** `inspect_case` reported `methylation` in `layers_absent` (`status = 'layer_absent'`), preventing ungrounded inference on an unmeasured assay.

- **Biomarker $\rightarrow$ Therapy-Class Hint (`therapy_hint`, Research-Only):**
  1. `BRCA1/2 mutation or HRD-positive genomic scar` $\rightarrow$ **PARP inhibitor / platinum chemotherapy** (primary hint via synthetic lethality).
  2. `TMB-high (13.68 mut/Mb)` with inflamed (`hot`) immune signature $\rightarrow$ **immune-checkpoint blockade (immunotherapy)**.

> **DISCLAIMER -- RESEARCH / EDUCATION ONLY. NOT FOR CLINICAL USE.** This molecular tumor board summary was produced by an automated teaching pipeline on synthetic / public research data using simplified heuristics. It must NOT be used to diagnose, treat, or make any medical decision. Real molecular tumor boards require board-certified clinicians and accredited (CAP/CLIA) laboratory testing.
