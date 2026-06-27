#!/usr/bin/env python3
"""omics.py -- the 12 deterministic "skills" of the Agentic Multi-Omics Tumor Board.

Every function takes a *loaded case dict* (see ``scripts/download_data.py`` for the
schema) and returns a **plain, JSON-serialisable dict**. They contain NO randomness
and NO network calls, so the agent's tool results are fully reproducible -- which is
exactly what makes the conditional routing in ``src/agent.py`` / ``src/router.py``
verifiable.

Case dict schema (one JSON file per case under ``data/``)::

    {
      "case_id": "A",
      "label": "HER2_AMP",
      "sample_type": "primary tumor",
      "hint": "...",
      "expression":        {gene: log2_normalised_tumor_value, ...},
      "expression_normal": {gene: log2_normalised_matched_normal_value, ...},
      "mutations":         [{"gene","protein_change","variant_type","pathogenic"}, ...],
      "mutation_burden_count": int,   # genome/exome-wide nonsynonymous count (for TMB)
      "cna":               {gene: gistic_state(-2..2), ...},
      "hrd_score":         float,     # genomic-scar / HRD signature score (0-100)
      "clinical":          {"subtype","er_status","pr_status","her2_status","stage"},
      "methylation":       {gene: beta_value(0-1), ...}    # OPTIONAL -- may be absent!
    }

RESEARCH / EDUCATION ONLY -- never for clinical use.
"""
from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- #
# Tunable thresholds (kept in one place so omics.py and router.py agree).
# --------------------------------------------------------------------------- #
# Receptor calls from log2-normalised expression.
ESR1_POS_THRESHOLD = 8.0     # ER+  if ESR1 expression >= this
PGR_POS_THRESHOLD = 7.0      # PR+  if PGR  expression >= this
ERBB2_HIGH_THRESHOLD = 12.0  # HER2 "high" if ERBB2 expression >= this

# Copy-number (GISTIC-style discrete states): +2 amp, +1 gain, 0 neutral, -1/-2 loss.
CNA_AMPLIFICATION = 2
CNA_DEEP_DELETION = -2

# Tumour mutational burden.
TMB_PANEL_MB = 38.0          # ~exome footprint used for TCGA-style TMB (mut / Mb)
TMB_HIGH_THRESHOLD = 10.0    # mut/Mb >= 10 is the common "TMB-high" cut-off

# Homologous-recombination deficiency (genomic-scar score, Myriad-style cut-off 42).
HRD_SCORE_THRESHOLD = 42.0

# Immune "hot vs cold": mean log2 expression of a cytolytic / IFN-gamma panel.
IMMUNE_GENES = ("GZMA", "PRF1", "IFNG", "CD8A", "CXCL9")
IMMUNE_HOT_THRESHOLD = 7.0

# Methylation promoter-hypermethylation call.
METH_HYPER_THRESHOLD = 0.6   # beta >= 0.6 => hypermethylated (silenced)

# Canonical breast-cancer driver genes we score in mutation_analysis.
DRIVER_GENES = ("TP53", "PIK3CA", "BRCA1", "BRCA2", "PTEN", "GATA3", "CDH1", "AKT1")

# Tiny static gene -> pathway lookup for pathway_enrichment (illustrative only).
GENE_PATHWAYS: dict[str, list[str]] = {
    "ERBB2": ["ERBB / HER2 signalling", "PI3K-AKT"],
    "EGFR": ["ERBB / HER2 signalling", "RTK-RAS"],
    "PIK3CA": ["PI3K-AKT", "mTOR"],
    "AKT1": ["PI3K-AKT", "mTOR"],
    "PTEN": ["PI3K-AKT"],
    "TP53": ["p53 / DNA-damage response", "Cell cycle"],
    "RB1": ["Cell cycle"],
    "CCND1": ["Cell cycle", "Estrogen response"],
    "BRCA1": ["Homologous recombination repair", "p53 / DNA-damage response"],
    "BRCA2": ["Homologous recombination repair"],
    "MKI67": ["Proliferation"],
    "ESR1": ["Estrogen response"],
    "PGR": ["Estrogen response"],
    "GATA3": ["Luminal differentiation"],
    "FOXA1": ["Luminal differentiation"],
    "KRT5": ["Basal differentiation"],
    "KRT14": ["Basal differentiation"],
    "MYC": ["MYC targets", "Proliferation"],
    "GZMA": ["Immune cytolytic"],
    "PRF1": ["Immune cytolytic"],
    "IFNG": ["IFN-gamma response"],
    "CD8A": ["T-cell infiltration"],
    "CXCL9": ["IFN-gamma response"],
}

# Direction of survival association for common markers (teaching simplification).
# +1 => higher marker associates with WORSE outcome (hazard up); -1 => better.
SURVIVAL_DIRECTION: dict[str, dict[str, Any]] = {
    "ERBB2": {"direction": +1, "note": "ERBB2/HER2 amplification: worse if untreated; "
              "strongly modified by anti-HER2 therapy."},
    "MKI67": {"direction": +1, "note": "High Ki-67 (proliferation): worse prognosis."},
    "TP53": {"direction": +1, "note": "TP53 mutation: generally worse prognosis."},
    "ESR1": {"direction": -1, "note": "ER-positive disease: better baseline prognosis, "
             "endocrine-responsive."},
    "PGR": {"direction": -1, "note": "PR-positive: favourable, endocrine-responsive."},
    "TMB": {"direction": -1, "note": "High TMB: associated with better response to "
            "immune-checkpoint blockade."},
    "BRCA1": {"direction": -1, "note": "BRCA1-mutant/HRD: sensitive to PARP inhibition "
              "and platinum."},
}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _expr(case: dict[str, Any], gene: str, default: float = 0.0) -> float:
    return float(case.get("expression", {}).get(gene, default))


def _has_layer(case: dict[str, Any], layer: str) -> bool:
    """A layer is 'present' if the key exists AND is non-empty."""
    return bool(case.get(layer))


def _round(x: float, n: int = 3) -> float:
    return round(float(x), n)


# --------------------------------------------------------------------------- #
# 1. inspect_case
# --------------------------------------------------------------------------- #
def inspect_case(case: dict[str, Any]) -> dict[str, Any]:
    """Report which omics layers are present plus basic case metadata.

    This is the agent's FIRST call: it tells the model what evidence is even
    available, so it can skip tools whose data layer is missing (e.g. methylation).
    """
    candidate_layers = ["expression", "mutations", "cna", "methylation", "clinical"]
    present = [layer for layer in candidate_layers if _has_layer(case, layer)]
    absent = [layer for layer in candidate_layers if layer not in present]
    return {
        "tool": "inspect_case",
        "case_id": case.get("case_id"),
        "label": case.get("label"),
        "sample_type": case.get("sample_type"),
        "hint": case.get("hint"),
        "layers_present": present,
        "layers_absent": absent,
        "n_expression_genes": len(case.get("expression", {})),
        "n_mutations_listed": len(case.get("mutations", [])),
    }


# --------------------------------------------------------------------------- #
# 2. expression_qc
# --------------------------------------------------------------------------- #
def expression_qc(case: dict[str, Any]) -> dict[str, Any]:
    """Basic QC on the expression layer: housekeeping genes, range, missing values."""
    expr = case.get("expression", {})
    flags: list[str] = []
    if not expr:
        return {"tool": "expression_qc", "status": "no_expression_layer", "pass": False,
                "flags": ["expression layer absent"]}

    housekeeping = ["ACTB", "GAPDH"]
    hk_present = [g for g in housekeeping if g in expr]
    if len(hk_present) < len(housekeeping):
        flags.append("missing housekeeping gene(s): "
                     + ",".join(g for g in housekeeping if g not in expr))
    # Housekeeping genes should be robustly expressed in a real library.
    for g in hk_present:
        if expr[g] < 8.0:
            flags.append(f"low housekeeping signal {g}={expr[g]} (library quality?)")

    values = [float(v) for v in expr.values()]
    n_negative = sum(1 for v in values if v < 0)
    if n_negative:
        flags.append(f"{n_negative} negative expression value(s)")

    return {
        "tool": "expression_qc",
        "pass": len(flags) == 0,
        "n_genes": len(expr),
        "housekeeping_present": hk_present,
        "value_min": _round(min(values)),
        "value_max": _round(max(values)),
        "value_mean": _round(sum(values) / len(values)),
        "flags": flags or ["none"],
    }


# --------------------------------------------------------------------------- #
# 3. receptor_status
# --------------------------------------------------------------------------- #
def receptor_status(case: dict[str, Any]) -> dict[str, Any]:
    """Derive ER / PR / HER2 status from ESR1 / PGR / ERBB2 expression.

    Returns the combined hormone-receptor (HR) call and a HER2 high/low flag.
    The agent uses ``her2_high`` to decide whether cna_analysis('ERBB2') is warranted.
    """
    esr1 = _expr(case, "ESR1")
    pgr = _expr(case, "PGR")
    erbb2 = _expr(case, "ERBB2")

    er_pos = esr1 >= ESR1_POS_THRESHOLD
    pr_pos = pgr >= PGR_POS_THRESHOLD
    her2_high = erbb2 >= ERBB2_HIGH_THRESHOLD

    hr_status = "HR-positive" if (er_pos or pr_pos) else "HR-negative"
    triple_negative = (not er_pos) and (not pr_pos) and (not her2_high)

    return {
        "tool": "receptor_status",
        "ESR1_expression": _round(esr1),
        "PGR_expression": _round(pgr),
        "ERBB2_expression": _round(erbb2),
        "ER": "positive" if er_pos else "negative",
        "PR": "positive" if pr_pos else "negative",
        "HER2": "high" if her2_high else "low",
        "her2_high": her2_high,
        "hr_status": hr_status,
        "triple_negative_by_expression": triple_negative,
    }


# --------------------------------------------------------------------------- #
# 4. differential_expression
# --------------------------------------------------------------------------- #
def differential_expression(case: dict[str, Any], top_n: int = 8) -> dict[str, Any]:
    """Tumour-vs-normal log2 fold-changes; return the strongest up/down genes."""
    tumor = case.get("expression", {})
    normal = case.get("expression_normal", {})
    if not tumor or not normal:
        return {"tool": "differential_expression", "status": "missing_tumor_or_normal",
                "top_up": [], "top_down": []}

    fcs = []
    for gene, t in tumor.items():
        if gene in normal:
            log2fc = float(t) - float(normal[gene])
            fcs.append({"gene": gene, "log2fc": _round(log2fc), "tumor": _round(float(t)),
                        "normal": _round(float(normal[gene]))})
    up = sorted(fcs, key=lambda d: d["log2fc"], reverse=True)[:top_n]
    down = sorted(fcs, key=lambda d: d["log2fc"])[:top_n]
    return {
        "tool": "differential_expression",
        "n_tested": len(fcs),
        "top_up": up,
        "top_down": down,
    }


# --------------------------------------------------------------------------- #
# 5. cna_analysis(gene)
# --------------------------------------------------------------------------- #
def cna_analysis(case: dict[str, Any], gene: str = "ERBB2") -> dict[str, Any]:
    """Copy-number state for a single gene (GISTIC-style -2..+2)."""
    cna = case.get("cna", {})
    if gene not in cna:
        return {"tool": "cna_analysis", "gene": gene, "status": "gene_not_in_cna_layer",
                "state": None}
    state = int(cna[gene])
    call_map = {
        2: "high-level amplification",
        1: "low-level gain",
        0: "copy-neutral",
        -1: "shallow deletion",
        -2: "deep (homozygous) deletion",
    }
    return {
        "tool": "cna_analysis",
        "gene": gene,
        "state": state,
        "call": call_map.get(state, "unknown"),
        "amplified": state >= CNA_AMPLIFICATION,
        "deep_deletion": state <= CNA_DEEP_DELETION,
    }


# --------------------------------------------------------------------------- #
# 6. mutation_analysis
# --------------------------------------------------------------------------- #
def mutation_analysis(case: dict[str, Any]) -> dict[str, Any]:
    """Driver mutations + tumour mutational burden (TMB).

    TMB = genome/exome-wide nonsynonymous mutation count / panel size (Mb).
    The agent uses ``tmb_high`` and ``brca_mutated`` to decide whether to run
    hrd_status and immune_infiltration.
    """
    mutations = case.get("mutations", [])
    drivers = [m for m in mutations if m.get("gene") in DRIVER_GENES]
    pathogenic_drivers = [m for m in drivers if m.get("pathogenic")]
    brca_mutated = any(
        m.get("gene") in ("BRCA1", "BRCA2") and m.get("pathogenic") for m in mutations
    )

    burden = int(case.get("mutation_burden_count", len(mutations)))
    tmb = burden / TMB_PANEL_MB
    return {
        "tool": "mutation_analysis",
        "n_mutations_genomewide": burden,
        "tmb_mut_per_mb": _round(tmb, 2),
        "tmb_high": tmb >= TMB_HIGH_THRESHOLD,
        "tmb_threshold": TMB_HIGH_THRESHOLD,
        "driver_mutations": [
            {"gene": m.get("gene"), "protein_change": m.get("protein_change"),
             "variant_type": m.get("variant_type"), "pathogenic": bool(m.get("pathogenic"))}
            for m in drivers
        ],
        "n_pathogenic_drivers": len(pathogenic_drivers),
        "brca_mutated": brca_mutated,
    }


# --------------------------------------------------------------------------- #
# 7. hrd_status
# --------------------------------------------------------------------------- #
def hrd_status(case: dict[str, Any]) -> dict[str, Any]:
    """Homologous-recombination-deficiency call from BRCA1/2 + genomic-scar score."""
    score = float(case.get("hrd_score", 0.0))
    brca_mutated = any(
        m.get("gene") in ("BRCA1", "BRCA2") and m.get("pathogenic")
        for m in case.get("mutations", [])
    )
    hrd_positive = brca_mutated or score >= HRD_SCORE_THRESHOLD
    drivers = []
    if brca_mutated:
        drivers.append("pathogenic BRCA1/2 mutation")
    if score >= HRD_SCORE_THRESHOLD:
        drivers.append(f"genomic-scar score {score} >= {HRD_SCORE_THRESHOLD}")
    return {
        "tool": "hrd_status",
        "hrd_score": _round(score),
        "hrd_threshold": HRD_SCORE_THRESHOLD,
        "brca_mutated": brca_mutated,
        "hrd_positive": hrd_positive,
        "evidence": drivers or ["no HRD evidence"],
    }


# --------------------------------------------------------------------------- #
# 8. immune_infiltration
# --------------------------------------------------------------------------- #
def immune_infiltration(case: dict[str, Any]) -> dict[str, Any]:
    """Cytolytic / IFN-gamma signature -> 'hot' vs 'cold' tumour."""
    expr = case.get("expression", {})
    used = {g: float(expr[g]) for g in IMMUNE_GENES if g in expr}
    if not used:
        return {"tool": "immune_infiltration", "status": "no_immune_genes_in_layer",
                "phenotype": "unknown"}
    score = sum(used.values()) / len(used)
    hot = score >= IMMUNE_HOT_THRESHOLD
    return {
        "tool": "immune_infiltration",
        "signature_genes": list(used.keys()),
        "immune_score": _round(score),
        "immune_threshold": IMMUNE_HOT_THRESHOLD,
        "phenotype": "hot (inflamed)" if hot else "cold (immune-desert)",
        "hot": hot,
    }


# --------------------------------------------------------------------------- #
# 9. methylation_analysis(gene)  -- LAYER MAY BE ABSENT
# --------------------------------------------------------------------------- #
def methylation_analysis(case: dict[str, Any], gene: str = "BRCA1") -> dict[str, Any]:
    """Promoter methylation for a gene.

    The methylation layer is INTENTIONALLY absent for some cases. The function
    detects this and returns ``status='layer_absent'`` so the agent can skip it
    gracefully rather than hallucinate a value.
    """
    if not _has_layer(case, "methylation"):
        return {
            "tool": "methylation_analysis",
            "gene": gene,
            "status": "layer_absent",
            "skipped": True,
            "message": "No methylation layer for this case -- cannot assess; skip.",
        }
    meth = case["methylation"]
    if gene not in meth:
        return {"tool": "methylation_analysis", "gene": gene,
                "status": "gene_not_measured", "beta": None}
    beta = float(meth[gene])
    return {
        "tool": "methylation_analysis",
        "gene": gene,
        "status": "ok",
        "beta": _round(beta),
        "hypermethylated": beta >= METH_HYPER_THRESHOLD,
        "interpretation": ("promoter hypermethylation -> likely epigenetic silencing"
                           if beta >= METH_HYPER_THRESHOLD
                           else "unmethylated / low -> gene not epigenetically silenced"),
    }


# --------------------------------------------------------------------------- #
# 10. pathway_enrichment
# --------------------------------------------------------------------------- #
def pathway_enrichment(case: dict[str, Any]) -> dict[str, Any]:
    """Aggregate pathways over the case's top DE genes + driver mutations."""
    de = differential_expression(case, top_n=8)
    de_genes = [d["gene"] for d in de.get("top_up", [])] + \
               [d["gene"] for d in de.get("top_down", [])]
    driver_genes = [m.get("gene") for m in case.get("mutations", [])]
    genes = list(dict.fromkeys(de_genes + driver_genes))  # de-dup, keep order

    counts: dict[str, int] = {}
    contributors: dict[str, list[str]] = {}
    for g in genes:
        for pw in GENE_PATHWAYS.get(g, []):
            counts[pw] = counts.get(pw, 0) + 1
            contributors.setdefault(pw, []).append(g)

    enriched = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "tool": "pathway_enrichment",
        "n_input_genes": len(genes),
        "enriched_pathways": [
            {"pathway": pw, "n_genes": n, "genes": contributors[pw]}
            for pw, n in enriched
        ],
    }


# --------------------------------------------------------------------------- #
# 11. survival_association(marker)
# --------------------------------------------------------------------------- #
def survival_association(case: dict[str, Any], marker: str = "MKI67") -> dict[str, Any]:
    """Direction of prognostic association for a marker (teaching simplification)."""
    info = SURVIVAL_DIRECTION.get(marker)
    if info is None:
        return {"tool": "survival_association", "marker": marker,
                "status": "no_reference_for_marker", "hazard_direction": "unknown"}
    direction = info["direction"]
    return {
        "tool": "survival_association",
        "marker": marker,
        "hazard_direction": "worse-outcome" if direction > 0 else "better-outcome",
        "hazard_ratio_sign": "+" if direction > 0 else "-",
        "note": info["note"],
    }


# --------------------------------------------------------------------------- #
# 12. therapy_hint
# --------------------------------------------------------------------------- #
def therapy_hint(case: dict[str, Any]) -> dict[str, Any]:
    """Map ACCUMULATED findings to actionable biomarker(s) -> therapy class.

    Re-derives the key findings deterministically so it can serve as the agent's
    final 'decision' tool. RESEARCH-ONLY: these are illustrative biomarker->class
    associations, NOT treatment recommendations.
    """
    rec = receptor_status(case)
    mut = mutation_analysis(case)
    hrd = hrd_status(case)
    erbb2_cna = cna_analysis(case, "ERBB2")

    hints: list[dict[str, str]] = []

    # Anti-HER2: HER2 high AND/OR ERBB2 amplified.
    if rec["her2_high"] or erbb2_cna.get("amplified"):
        hints.append({
            "biomarker": "ERBB2 amplification / HER2 overexpression",
            "therapy_class": "anti-HER2 (e.g. trastuzumab-class agents)",
        })
    # PARP / platinum: BRCA mutation or HRD-positive.
    if hrd["hrd_positive"]:
        hints.append({
            "biomarker": "BRCA1/2 mutation or HRD-positive genomic scar",
            "therapy_class": "PARP inhibitor / platinum chemotherapy",
        })
    # Immunotherapy: TMB-high.
    if mut["tmb_high"]:
        hints.append({
            "biomarker": f"TMB-high ({mut['tmb_mut_per_mb']} mut/Mb)",
            "therapy_class": "immune-checkpoint blockade (immunotherapy)",
        })
    # Endocrine: HR-positive.
    if rec["hr_status"] == "HR-positive":
        hints.append({
            "biomarker": "ER/PR-positive (hormone-receptor positive)",
            "therapy_class": "endocrine therapy (e.g. aromatase inhibitor / SERM)",
        })

    if not hints:
        hints.append({
            "biomarker": "no dominant actionable biomarker detected",
            "therapy_class": "no targeted hint -- standard-of-care evaluation",
        })

    return {
        "tool": "therapy_hint",
        "actionable_hints": hints,
        "primary_hint": hints[0],
        "disclaimer": ("RESEARCH / EDUCATION ONLY. These biomarker-to-therapy-class "
                       "associations are illustrative and MUST NOT be used for any "
                       "clinical or treatment decision."),
    }


# Public registry of the 12 skills (used by agent.py & router.py to stay in sync).
TOOL_FUNCTIONS = {
    "inspect_case": inspect_case,
    "expression_qc": expression_qc,
    "receptor_status": receptor_status,
    "differential_expression": differential_expression,
    "cna_analysis": cna_analysis,
    "mutation_analysis": mutation_analysis,
    "hrd_status": hrd_status,
    "immune_infiltration": immune_infiltration,
    "methylation_analysis": methylation_analysis,
    "pathway_enrichment": pathway_enrichment,
    "survival_association": survival_association,
    "therapy_hint": therapy_hint,
}

assert len(TOOL_FUNCTIONS) == 12, "expected exactly 12 omics skills"
