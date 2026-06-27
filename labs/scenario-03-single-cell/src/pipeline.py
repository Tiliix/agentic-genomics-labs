"""Scanpy scRNA-seq pipeline for PBMC 3k.

Stages:
    1. Load raw counts (from scripts/download_data.py output, or fetch on the fly)
    2. QC filtering            — drop low-quality cells/genes (n_genes, pct mito)
    3. Normalization + log1p   — library-size normalize to 1e4, natural log
    4. Highly variable genes   — keep the informative genes for clustering
    5. Scale + PCA             — linear dimensionality reduction
    6. Neighbors + Leiden      — graph-based community clustering
    7. rank_genes_groups       — top differentially-expressed markers per cluster

Outputs (written to ./results):
    - pbmc3k_processed.h5ad    — full processed AnnData (embeddings, clusters)
    - markers_top.csv          — top-N marker genes per Leiden cluster
    - umap_leiden.png          — UMAP coloured by cluster (sanity-check plot)

The markers table is the hand-off artifact consumed by src/annotate_agent.py.

Run:
    python src/pipeline.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import scanpy as sc

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
RAW_H5AD = DATA_DIR / "pbmc3k_raw.h5ad"
PROCESSED_H5AD = RESULTS_DIR / "pbmc3k_processed.h5ad"
MARKERS_CSV = RESULTS_DIR / "markers_top.csv"
UMAP_PNG = RESULTS_DIR / "umap_leiden.png"

# ---------------------------------------------------------------------------
# Tunable parameters — in the "agent-driven" variant of this lab, an LLM can
# propose these values from the QC plots. Defaults follow the Scanpy PBMC3k
# tutorial and are sensible starting points.
# ---------------------------------------------------------------------------
MIN_GENES_PER_CELL = 200     # filter cells expressing fewer than this many genes
MIN_CELLS_PER_GENE = 3       # filter genes seen in fewer than this many cells
MAX_GENES_PER_CELL = 2500    # upper bound — likely doublets above this
MAX_PCT_MITO = 5.0           # cells with >5% mitochondrial counts = dying/stressed
N_TOP_HVG = 2000             # number of highly variable genes to keep
N_PCS = 40                   # principal components for the neighbor graph
N_NEIGHBORS = 15             # kNN graph connectivity
LEIDEN_RESOLUTION = 1.0      # higher -> more, finer clusters
N_TOP_MARKERS = 25           # markers per cluster handed to the annotation agent


def load_counts() -> sc.AnnData:
    """Load raw PBMC3k counts, fetching via Scanpy if the cache is missing."""
    if RAW_H5AD.exists():
        adata = sc.read_h5ad(RAW_H5AD)
    else:
        # Fall back to the Scanpy loader so the pipeline runs standalone.
        adata = sc.datasets.pbmc3k()
        adata.var_names_make_unique()
    return adata


def quality_control(adata: sc.AnnData) -> sc.AnnData:
    """Apply standard scRNA-seq QC filtering."""
    # Basic count-based filtering of empty/low-complexity cells and rare genes.
    sc.pp.filter_cells(adata, min_genes=MIN_GENES_PER_CELL)
    sc.pp.filter_genes(adata, min_cells=MIN_CELLS_PER_GENE)

    # Flag mitochondrial genes (human symbols start with "MT-").
    adata.var["mt"] = adata.var_names.str.startswith("MT-")

    # Compute per-cell QC metrics: total counts, n_genes, pct_counts_mt, etc.
    sc.pp.calculate_qc_metrics(
        adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True
    )

    # Remove probable doublets (very high gene counts) and dying cells (high mito).
    adata = adata[adata.obs["n_genes_by_counts"] < MAX_GENES_PER_CELL, :].copy()
    adata = adata[adata.obs["pct_counts_mt"] < MAX_PCT_MITO, :].copy()
    return adata


def normalize(adata: sc.AnnData) -> sc.AnnData:
    """Library-size normalize, log-transform, and select HVGs."""
    # Keep a copy of raw (post-QC) counts for later marker visualization.
    adata.layers["counts"] = adata.X.copy()

    # Normalize each cell to 10,000 total counts, then natural-log(1+x).
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)

    # Stash the log-normalized matrix in .raw so DE uses all genes, not just HVGs.
    adata.raw = adata

    # Select highly variable genes for the downstream embedding.
    sc.pp.highly_variable_genes(adata, n_top_genes=N_TOP_HVG, flavor="seurat")
    adata = adata[:, adata.var["highly_variable"]].copy()
    return adata


def embed_and_cluster(adata: sc.AnnData) -> sc.AnnData:
    """Scale, PCA, neighbor graph, UMAP, and Leiden clustering."""
    # Regress out and scale (clip to max 10 to limit outlier influence).
    sc.pp.scale(adata, max_value=10)

    # PCA for linear dimensionality reduction.
    sc.tl.pca(adata, svd_solver="arpack", n_comps=N_PCS)

    # Build the kNN graph in PCA space.
    sc.pp.neighbors(adata, n_neighbors=N_NEIGHBORS, n_pcs=N_PCS)

    # UMAP embedding (for visualization only).
    sc.tl.umap(adata)

    # Leiden community detection. Use the modern igraph flavor explicitly to
    # avoid the deprecation warning in newer Scanpy/leidenalg.
    sc.tl.leiden(
        adata,
        resolution=LEIDEN_RESOLUTION,
        flavor="igraph",
        n_iterations=2,
        directed=False,
    )
    return adata


def rank_markers(adata: sc.AnnData) -> pd.DataFrame:
    """Differential expression per cluster -> tidy top-marker table."""
    # Wilcoxon rank-sum test is the recommended default for scRNA-seq DE.
    sc.tl.rank_genes_groups(adata, groupby="leiden", method="wilcoxon")

    # Flatten Scanpy's structured result into a long DataFrame.
    result = adata.uns["rank_genes_groups"]
    groups = result["names"].dtype.names  # cluster labels
    rows = []
    for cluster in groups:
        for rank in range(N_TOP_MARKERS):
            rows.append(
                {
                    "cluster": cluster,
                    "rank": rank + 1,
                    "gene": result["names"][cluster][rank],
                    "log2fc": float(result["logfoldchanges"][cluster][rank]),
                    "pval_adj": float(result["pvals_adj"][cluster][rank]),
                    "score": float(result["scores"][cluster][rank]),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    sc.settings.verbosity = 1
    sc.settings.figdir = str(RESULTS_DIR)

    print("[1/6] Loading raw counts ...")
    adata = load_counts()
    print(f"      raw shape: {adata.shape}")

    print("[2/6] Quality control ...")
    adata = quality_control(adata)
    print(f"      post-QC shape: {adata.shape}")

    print("[3/6] Normalization + HVG ...")
    adata = normalize(adata)

    print("[4/6] PCA + neighbors + UMAP + Leiden ...")
    adata = embed_and_cluster(adata)
    n_clusters = adata.obs["leiden"].nunique()
    print(f"      found {n_clusters} Leiden clusters")

    print("[5/6] Ranking marker genes ...")
    markers = rank_markers(adata)
    markers.to_csv(MARKERS_CSV, index=False)
    print(f"      wrote {MARKERS_CSV}")

    print("[6/6] Saving processed AnnData + UMAP plot ...")
    # save=... appends to figdir; produces results/umap_leiden.png
    sc.pl.umap(adata, color="leiden", show=False, save="_leiden.png")
    adata.write_h5ad(PROCESSED_H5AD)
    print(f"      wrote {PROCESSED_H5AD}")
    print("Done. Next: python src/annotate_agent.py")


if __name__ == "__main__":
    main()
