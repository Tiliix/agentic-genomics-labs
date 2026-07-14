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
# Stage 4: Pathway enrichment (Enrichr REST)
# --------------------------------------------------------------------------- #
ENRICHR_HUMAN = "https://maayanlab.cloud/Enrichr"
ENRICHR_FLY = "https://maayanlab.cloud/FlyEnrichr"  # modEnrichr, same REST API

# Every run tests GO Biological Process AND KEGG (organism-appropriate).
FLY_LIBRARIES = ["GO_Biological_Process_2018", "KEGG_2019"]
HUMAN_LIBRARIES = ["GO_Biological_Process_2021", "KEGG_2021_Human"]


def _fbgn_to_symbols(fbgn_ids: list[str]) -> list[str]:
    """Map FlyBase ``FBgn`` gene IDs to Drosophila gene symbols via the
    mygene.info batch REST API. Returns the symbols found (deduplicated); returns
    an empty list on any error so the caller can degrade gracefully."""
    import requests

    try:
        resp = requests.post(
            "https://mygene.info/v3/query",
            data={
                "q": ",".join(fbgn_ids),
                "scopes": "flybase,ensembl.gene",
                "fields": "symbol",
                "species": "7227",  # Drosophila melanogaster
            },
            timeout=30,
        )
        resp.raise_for_status()
        symbols = [
            hit["symbol"]
            for hit in resp.json()
            if isinstance(hit, dict) and hit.get("symbol")
        ]
        return list(dict.fromkeys(symbols))  # de-dupe, preserve order
    except Exception:  # noqa: BLE001 — mapping is best-effort
        return []


def _enrichr_rest(genes: list[str], library: str, base: str) -> pd.DataFrame:
    """Run Enrichr over ``genes`` against ``library`` via the REST API
    (POST /addList then GET /enrich). Returns a DataFrame with columns
    Term, P-value, Adjusted P-value, Combined Score, Overlap, Genes.
    Raises on any network/HTTP error."""
    import requests

    add = requests.post(
        f"{base}/addList",
        files={
            "list": (None, "\n".join(genes)),
            "description": (None, "scenario-01 DE genes"),
        },
        timeout=30,
    )
    add.raise_for_status()
    user_list_id = add.json()["userListId"]

    enr = requests.get(
        f"{base}/enrich",
        params={"userListId": user_list_id, "backgroundType": library},
        timeout=60,
    )
    enr.raise_for_status()

    # Enrichr row layout:
    # [rank, term, p_value, z_score, combined_score, [genes], adj_p_value, ...]
    entries = enr.json().get(library, [])
    cols = ["Term", "P-value", "Adjusted P-value", "Combined Score", "Overlap", "Genes"]
    if not entries:
        return pd.DataFrame(columns=cols)
    rows = [
        {
            "Term": e[1],
            "P-value": e[2],
            "Adjusted P-value": e[6],
            "Combined Score": e[4],
            "Overlap": len(e[5]),
            "Genes": ";".join(e[5]),
        }
        for e in entries
    ]
    return pd.DataFrame(rows).sort_values("Adjusted P-value").reset_index(drop=True)


def _enrichment_summary(table: pd.DataFrame) -> dict[str, Any]:
    """Compact summary of one Enrichr result table: total terms, count passing
    FDR < 0.05, and the top 5 terms by adjusted p-value."""
    if table.empty:
        return {"n_terms": 0, "n_sig_fdr05": 0, "top_terms": []}
    return {
        "n_terms": int(table.shape[0]),
        "n_sig_fdr05": int((table["Adjusted P-value"] < 0.05).sum()),
        "top_terms": table[["Term", "Adjusted P-value", "Overlap", "Genes"]]
        .head(5)
        .to_dict(orient="records"),
    }


def pathway_enrichment(
    gene_set: str = "KEGG_2021_Human",
    alpha: float = 0.05,
    top_n: int = 200,
) -> dict[str, Any]:
    """
    Enrichr pathway enrichment on the significant DE genes via the Enrichr REST
    API (POST /addList + GET /enrich) — no gseapy dependency.

    The significant genes are split into **up-** and **down-regulated** sets (by
    log2 fold change) and each set is tested against **two** libraries — GO
    Biological Process **and** KEGG — so every run reports both databases for both
    directions.

    Drosophila datasets (FlyBase ``FBgn`` IDs) are auto-detected: IDs are mapped to
    Drosophila symbols (mygene.info) and queried against FlyEnrichr with fly
    libraries; other IDs use the standard (human) Enrichr. ``gene_set`` is retained
    for backward compatibility but no longer selects the library (both GO-BP and
    KEGG are always tested).

    Requires internet. Degrades gracefully (status "skipped") on any network error.
    """
    _ensure_results_dir()

    de_path = RESULTS_DIR / "de_results.csv"
    if not de_path.exists():
        raise FileNotFoundError(
            "de_results.csv not found — run differential_expression() first."
        )
    res = pd.read_csv(de_path, index_col=0)

    sig = res[res["padj"] < alpha].sort_values("padj")
    if sig.empty:
        return {
            "status": "skipped",
            "reason": "No significant genes at the chosen alpha.",
            "n_significant": 0,
        }

    # Split significant genes by direction of change (top_n each, by padj).
    up_ids = sig[sig["log2FoldChange"] > 0].head(top_n).index.astype(str).tolist()
    down_ids = sig[sig["log2FoldChange"] < 0].head(top_n).index.astype(str).tolist()

    # Organism detection over all significant IDs -> Enrichr instance + libraries.
    all_ids = up_ids + down_ids
    n_fbgn = sum(g.startswith("FBgn") for g in all_ids)
    is_fly = n_fbgn > 0.5 * max(len(all_ids), 1)
    base = ENRICHR_FLY if is_fly else ENRICHR_HUMAN
    libraries = FLY_LIBRARIES if is_fly else HUMAN_LIBRARIES

    # Map FlyBase IDs to symbols per direction (best effort).
    note: str | None = None
    genes_by_dir: dict[str, list[str]] = {"up": up_ids, "down": down_ids}
    if is_fly:
        genes_by_dir = {
            d: (_fbgn_to_symbols(ids) if ids else []) for d, ids in genes_by_dir.items()
        }
        note = (
            "Detected FlyBase IDs; mapped to Drosophila symbols (mygene.info) and "
            "queried FlyEnrichr (GO-BP + KEGG)."
        )

    # Run every (direction x library) combination.
    frames: list[pd.DataFrame] = []
    results: dict[str, Any] = {}
    try:
        for direction, genes in genes_by_dir.items():
            results[direction] = {}
            for lib in libraries:
                table = (
                    _enrichr_rest(genes, lib, base)
                    if genes
                    else pd.DataFrame(
                        columns=["Term", "P-value", "Adjusted P-value", "Combined Score", "Overlap", "Genes"]
                    )
                )
                if not table.empty:
                    tagged = table.copy()
                    tagged.insert(0, "Database", lib)
                    tagged.insert(0, "Direction", direction)
                    frames.append(tagged)
                results[direction][lib] = _enrichment_summary(table)
    except Exception as exc:  # noqa: BLE001 — surface any network error to the model
        return {
            "status": "skipped",
            "reason": f"Enrichr REST error: {exc}",
            "n_significant": int(sig.shape[0]),
        }

    out = RESULTS_DIR / "enrichment.csv"
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(out, index=False)
    else:
        pd.DataFrame(
            columns=["Direction", "Database", "Term", "P-value", "Adjusted P-value", "Combined Score", "Overlap", "Genes"]
        ).to_csv(out, index=False)

    result: dict[str, Any] = {
        "status": "ok",
        "enrichr": "FlyEnrichr" if is_fly else "Enrichr",
        "organism": "drosophila" if is_fly else "human/other",
        "alpha": alpha,
        "n_significant": int(sig.shape[0]),
        "n_up": len(up_ids),
        "n_down": len(down_ids),
        "n_up_queried": len(genes_by_dir["up"]),
        "n_down_queried": len(genes_by_dir["down"]),
        "libraries": libraries,
        "results": results,
        "_artifact": str(out),
    }
    if note:
        result["note"] = note
    return result


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
