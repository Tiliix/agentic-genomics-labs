"""
pipeline.py
===========

Deterministic RNA-seq differential-expression pipeline. These functions do the
real analysis; the LLM agent in ``agent.py`` only decides *when* to call them and
narrates the results — it never invents numbers.

Stages
------
1. ``run_qc``                 — summarise the counts matrix (library sizes, etc.)
2. ``quantify``               — pass-through for a provided counts matrix
                                (or where Salmon output would be imported)
3. ``differential_expression`` — pydeseq2 DESeq2 analysis (pure Python, no R)
4. ``pathway_enrichment``      — gseapy / Enrichr over the top DE genes

All stages read from ``data/`` and write artifacts to ``data/results/``.

Run standalone for an offline smoke test (no LLM required):

    python src/pipeline.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
# Resolve relative to the repo root (parent of this file's directory) so the
# pipeline works no matter the current working directory.
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
RESULTS_DIR = DATA_DIR / "results"

COUNTS_CSV = DATA_DIR / "counts.csv"
COLDATA_CSV = DATA_DIR / "coldata.csv"


def _ensure_results_dir() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def load_counts() -> pd.DataFrame:
    """Load the genes-x-samples counts matrix (genes as the index)."""
    if not COUNTS_CSV.exists():
        raise FileNotFoundError(
            f"Counts matrix not found at {COUNTS_CSV}. "
            "Run `python scripts/download_data.py` first."
        )
    return pd.read_csv(COUNTS_CSV, index_col=0)


def load_coldata() -> pd.DataFrame:
    """Load sample metadata (samples as the index, must contain a 'condition' column)."""
    if not COLDATA_CSV.exists():
        raise FileNotFoundError(
            f"Sample metadata not found at {COLDATA_CSV}. "
            "Run `python scripts/download_data.py` first."
        )
    return pd.read_csv(COLDATA_CSV, index_col=0)


# --------------------------------------------------------------------------- #
# Stage 1: QC
# --------------------------------------------------------------------------- #
def run_qc(min_count: int = 10) -> dict[str, Any]:
    """
    Summarise the raw counts matrix.

    Returns a JSON-serialisable dict with library sizes, sample/gene counts and a
    list of low-count genes (total across samples < ``min_count``). Also writes
    ``data/results/qc_summary.json``.
    """
    _ensure_results_dir()
    counts = load_counts()
    coldata = load_coldata()

    library_sizes = counts.sum(axis=0)
    gene_totals = counts.sum(axis=1)
    low_count_genes = gene_totals[gene_totals < min_count].index.tolist()

    summary: dict[str, Any] = {
        "n_genes": int(counts.shape[0]),
        "n_samples": int(counts.shape[1]),
        "samples": list(counts.columns),
        "conditions": coldata["condition"].value_counts().to_dict(),
        "library_sizes": {s: int(v) for s, v in library_sizes.items()},
        "median_library_size": int(library_sizes.median()),
        "n_low_count_genes": len(low_count_genes),
        "min_count_threshold": min_count,
    }

    out = RESULTS_DIR / "qc_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    summary["_artifact"] = str(out)
    return summary


# --------------------------------------------------------------------------- #
# Stage 2: Quantification
# --------------------------------------------------------------------------- #
def quantify(min_count: int = 10) -> dict[str, Any]:
    """
    Produce the analysis-ready counts matrix.

    In a full pipeline this is where Salmon ``quant.sf`` files would be imported
    (e.g. via ``tximport``/``pyroe``) into a gene-level counts matrix. For this
    lab we already have a counts matrix, so this stage filters out genes whose
    total count across all samples falls below ``min_count`` and writes the
    filtered matrix for downstream DE.
    """
    _ensure_results_dir()
    counts = load_counts()

    gene_totals = counts.sum(axis=1)
    kept = counts.loc[gene_totals >= min_count]

    out = RESULTS_DIR / "counts_filtered.csv"
    kept.to_csv(out)

    return {
        "n_genes_in": int(counts.shape[0]),
        "n_genes_kept": int(kept.shape[0]),
        "n_genes_dropped": int(counts.shape[0] - kept.shape[0]),
        "min_count_threshold": min_count,
        "_artifact": str(out),
    }


# --------------------------------------------------------------------------- #
# Stage 3: Differential expression (pydeseq2)
# --------------------------------------------------------------------------- #
def differential_expression(
    condition_column: str = "condition",
    reference_level: str | None = None,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """
    Run a DESeq2 differential-expression analysis using pydeseq2 (pure Python).

    Reads the filtered matrix from ``quantify`` if present, otherwise the raw
    counts. Writes the full results table to ``data/results/de_results.csv`` and
    returns a summary plus the top genes by adjusted p-value.
    """
    _ensure_results_dir()

    # Prefer the filtered matrix produced by quantify(); fall back to raw counts.
    filtered = RESULTS_DIR / "counts_filtered.csv"
    counts = (
        pd.read_csv(filtered, index_col=0) if filtered.exists() else load_counts()
    )
    coldata = load_coldata()

    # pydeseq2 expects samples as rows, genes as columns.
    counts_t = counts.T
    counts_t = counts_t.loc[coldata.index]  # align sample order

    # Imported lazily so the module still imports if pydeseq2 is missing
    # (e.g. during a lint-only CI smoke import).
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats

    # Put the reference (control) level first so results read as "treated vs control".
    if reference_level and reference_level in list(coldata[condition_column]):
        ordered = [reference_level] + [
            lv for lv in dict.fromkeys(coldata[condition_column])
            if lv != reference_level
        ]
        coldata[condition_column] = pd.Categorical(
            coldata[condition_column], categories=ordered
        )

    # pydeseq2 changed its API across versions: newer releases use a formula
    # design ("~factor"); older ones use design_factors=. Try new, fall back to old.
    try:
        dds = DeseqDataSet(
            counts=counts_t,
            metadata=coldata,
            design="~" + condition_column,
        )
    except TypeError:
        dds = DeseqDataSet(
            counts=counts_t,
            metadata=coldata,
            design_factors=condition_column,
        )

    dds.deseq2()

    # Newer pydeseq2 requires an explicit contrast: [factor, tested_level, reference_level].
    levels = list(dict.fromkeys(str(v) for v in coldata[condition_column]))
    ref = reference_level if (reference_level and reference_level in levels) else levels[0]
    test = next((lv for lv in levels if lv != ref), ref)
    stats = DeseqStats(dds, contrast=[condition_column, test, ref], alpha=alpha)
        
    stats.summary()
    res: pd.DataFrame = stats.results_df.sort_values("padj")

    out = RESULTS_DIR / "de_results.csv"
    res.to_csv(out)

    n_sig = int((res["padj"] < alpha).sum())
    top = (
        res.dropna(subset=["padj"])
        .head(15)
        .reset_index()
        .rename(columns={"index": "gene"})
    )

    return {
        "n_genes_tested": int(res.shape[0]),
        "n_significant": n_sig,
        "alpha": alpha,
        "design_factor": condition_column,
        "top_genes": top.to_dict(orient="records"),
        "_artifact": str(out),
    }


# --------------------------------------------------------------------------- #
# Stage 4: Pathway enrichment (gseapy / Enrichr)
# --------------------------------------------------------------------------- #
def pathway_enrichment(
    gene_set: str = "KEGG_2021_Human",
    alpha: float = 0.05,
    top_n: int = 200,
) -> dict[str, Any]:
    """
    Run Enrichr pathway enrichment (via gseapy) on the significant DE genes.

    Requires internet to reach the Enrichr service. If Enrichr is unreachable the
    function degrades gracefully and reports that enrichment was skipped, so the
    rest of the lab still completes offline.
    """
    _ensure_results_dir()

    de_path = RESULTS_DIR / "de_results.csv"
    if not de_path.exists():
        raise FileNotFoundError(
            "de_results.csv not found — run differential_expression() first."
        )
    res = pd.read_csv(de_path, index_col=0)

    sig = res[res["padj"] < alpha].sort_values("padj")
    gene_list = sig.head(top_n).index.astype(str).tolist()

    if not gene_list:
        return {
            "status": "skipped",
            "reason": "No significant genes at the chosen alpha.",
            "n_input_genes": 0,
        }

    try:
        import gseapy as gp

        enr = gp.enrichr(
            gene_list=gene_list,
            gene_sets=[gene_set],
            organism="human",
            outdir=None,  # don't litter the filesystem
        )
        table: pd.DataFrame = enr.results.sort_values("Adjusted P-value")
        out = RESULTS_DIR / "enrichment.csv"
        table.to_csv(out, index=False)

        top_terms = (
            table[["Term", "Adjusted P-value", "Overlap", "Genes"]]
            .head(10)
            .to_dict(orient="records")
        )
        return {
            "status": "ok",
            "gene_set": gene_set,
            "n_input_genes": len(gene_list),
            "n_terms": int(table.shape[0]),
            "top_terms": top_terms,
            "_artifact": str(out),
        }
    except Exception as exc:  # noqa: BLE001 — surface any network/library error
        return {
            "status": "skipped",
            "reason": f"Enrichr unreachable or gseapy error: {exc}",
            "n_input_genes": len(gene_list),
        }


# --------------------------------------------------------------------------- #
# Offline smoke test
# --------------------------------------------------------------------------- #
def _smoke() -> None:
    """Run all stages in order with default parameters and print a short summary."""
    print("== QC ==")
    print(json.dumps(run_qc(), indent=2))
    print("\n== Quantify ==")
    print(json.dumps(quantify(), indent=2))
    print("\n== Differential expression ==")
    de = differential_expression()
    print(f"tested={de['n_genes_tested']} significant={de['n_significant']}")
    print("\n== Pathway enrichment ==")
    print(json.dumps(pathway_enrichment(), indent=2))
    print(f"\nArtifacts written to {RESULTS_DIR}")


if __name__ == "__main__":
    # Allow `python src/pipeline.py` from the repo root.
    os.chdir(REPO_ROOT)
    _smoke()
