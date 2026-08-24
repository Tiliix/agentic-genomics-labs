"""Scanpy scRNA-seq pipeline for PBMC 3k.

Stages:
    1. Load raw counts (from scripts/download_data.py output, or fetch on the fly)
    2. QC filtering            ? drop low-quality cells/genes (n_genes, pct mito)
    3. Normalization + log1p   ? library-size normalize to 1e4, natural log
    4. Highly variable genes   ? keep the informative genes for clustering
    5. Scale + PCA             ? linear dimensionality reduction
    6. Neighbors + Leiden      ? graph-based community clustering
    7. rank_genes_groups       ? top differentially-expressed markers per cluster

Outputs (written to ./results):
    - pbmc3k_processed.h5ad    ? full processed AnnData (embeddings, clusters)
    - markers_top.csv          ? top-N marker genes per Leiden cluster
    - umap_leiden.png          ? UMAP coloured by cluster (sanity-check plot)
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
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
ITERATION_REPORT_CSV = RESULTS_DIR / "resolution_iteration_report.csv"
MODE2_UMAPS_PNG = RESULTS_DIR / "mode2_UMAPs.png"

# ---------------------------------------------------------------------------
# Tunable parameters
# ---------------------------------------------------------------------------
MIN_GENES_PER_CELL = 200     
MIN_CELLS_PER_GENE = 3       
MAX_GENES_PER_CELL = 2500    
MAX_PCT_MITO = 5.0           
N_TOP_HVG = 2000             
N_PCS = 40                   
N_NEIGHBORS = 15             
LEIDEN_RESOLUTION = 1.0      
N_TOP_MARKERS = 25           


def load_counts() -> sc.AnnData:
    if RAW_H5AD.exists():
        adata = sc.read_h5ad(RAW_H5AD)
    else:
        adata = sc.datasets.pbmc3k()
        adata.var_names_make_unique()
    return adata


def quality_control(adata: sc.AnnData) -> sc.AnnData:
    sc.pp.filter_cells(adata, min_genes=MIN_GENES_PER_CELL)
    sc.pp.filter_genes(adata, min_cells=MIN_CELLS_PER_GENE)
    adata.var["mt"] = adata.var_names.str.startswith("MT-")
    sc.pp.calculate_qc_metrics(
        adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True
    )
    adata = adata[adata.obs["n_genes_by_counts"] < MAX_GENES_PER_CELL, :].copy()
    adata = adata[adata.obs["pct_counts_mt"] < MAX_PCT_MITO, :].copy()
    return adata


def normalize(adata: sc.AnnData) -> sc.AnnData:
    adata.layers["counts"] = adata.X.copy()
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    adata.raw = adata
    sc.pp.highly_variable_genes(adata, n_top_genes=N_TOP_HVG, flavor="seurat")
    adata = adata[:, adata.var["highly_variable"]].copy()
    return adata

def pre_cluster(adata: sc.AnnData) -> sc.AnnData:
    """Run steps up to neighbors (scale, pca, neighbors, umap)"""
    sc.pp.scale(adata, max_value=10)
    sc.tl.pca(adata, svd_solver="arpack", n_comps=N_PCS)
    sc.pp.neighbors(adata, n_neighbors=N_NEIGHBORS, n_pcs=N_PCS)
    sc.tl.umap(adata)
    return adata


def do_leiden(adata: sc.AnnData, resolution: float, key_added: str = "leiden") -> sc.AnnData:
    sc.tl.leiden(
        adata,
        resolution=resolution,
        flavor="igraph",
        n_iterations=2,
        directed=False,
        key_added=key_added,
    )
    return adata


def rank_markers(adata: sc.AnnData, groupby: str = "leiden") -> pd.DataFrame:
    sc.tl.rank_genes_groups(adata, groupby=groupby, method="wilcoxon")
    result = adata.uns["rank_genes_groups"]
    groups = result["names"].dtype.names
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


def run_mode_1():
    print(f"\n--- MODE 1: Fixed Resolution ({LEIDEN_RESOLUTION}) ---")
    adata = load_counts()
    adata = quality_control(adata)
    adata = normalize(adata)
    adata = pre_cluster(adata)
    
    print(f"[4/6] Leiden clustering at resolution {LEIDEN_RESOLUTION} ...")
    adata = do_leiden(adata, LEIDEN_RESOLUTION)
    n_clusters = adata.obs["leiden"].nunique()
    print(f"      found {n_clusters} Leiden clusters")
    
    print("[5/6] Ranking marker genes ...")
    markers = rank_markers(adata)
    markers.to_csv(MARKERS_CSV, index=False)
    
    print("[6/6] Saving processed AnnData + UMAP plot ...")
    sc.pl.umap(adata, color="leiden", show=False, save="_leiden.png")
    adata.write_h5ad(PROCESSED_H5AD)
    print("Done. Next: python src/annotate_agent.py (in Mode 1)")


def run_mode_2(iterations: int):
    print(f"\n--- MODE 2: Iterative Resolution Search ({iterations} iterations) ---")
    adata = load_counts()
    adata = quality_control(adata)
    adata = normalize(adata)
    adata = pre_cluster(adata)
    
    # Generate well-spaced resolutions. Commonly between 0.2 and 1.8 for PBMC.
    resolutions = np.linspace(0.2, 1.8, iterations)
    print(f"Agent proposes the following {iterations} resolution values:")
    print(f"[{', '.join([f'{r:.2f}' for r in resolutions])}]")
    
    reports = []
    
    for i, res in enumerate(resolutions):
        print(f"\n--> Iteration {i+1}/{iterations}: Resolution = {res:.2f}")
        
        # We save each iteration to a separate obs column to plot them later
        obs_key = f"leiden_{res:.2f}"
        adata = do_leiden(adata, res, key_added=obs_key)
        n_clusters = adata.obs[obs_key].nunique()
        print(f"    Found {n_clusters} clusters.")
        
        reports.append({
            "iteration": i + 1,
            "resolution": round(res, 2),
            "num_clusters": n_clusters,
            "obs_key": obs_key,
        })
    
    report_df = pd.DataFrame(reports)
    
    # Heuristic for PBMC3k (usually ~8-10 cell types expected)
    report_df["distance_to_expected"] = abs(report_df["num_clusters"] - 9)
    best_idx = report_df["distance_to_expected"].idxmin()
    best_res = report_df.loc[best_idx, "resolution"]
    best_key = report_df.loc[best_idx, "obs_key"]
    
    print("\n--- Iteration Summary ---")
    report_df["is_best"] = False
    report_df.loc[best_idx, "is_best"] = True
    
    print(report_df.drop(columns=["distance_to_expected", "obs_key"]))
    print(f"\nAgent selected best resolution: {best_res:.2f} (closest to 9 expected broad cell types in PBMC3k)")
    
    print("\nPlotting UMAP grid (Matrix) ...")
    ncols = min(iterations, 3)
    nrows = math.ceil(iterations / ncols)
    
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 5, nrows * 4))
    axes_flat = axes.flatten() if isinstance(axes, np.ndarray) else [axes]
    
    for i, row in report_df.iterrows():
        ax = axes_flat[i]
        c_key = row["obs_key"]
        c_res = row["resolution"]
        c_num = row["num_clusters"]
        is_best = row["is_best"]
        
        # We put the legend on data to keep the plots cleaner
        sc.pl.umap(adata, color=c_key, ax=ax, show=False, legend_loc='on data', legend_fontsize=8)
        ax.set_title(f"Res: {c_res:.2f} | Clusters: {c_num}")
        
        # Highlight the best one with a red border
        if is_best:
            for spine in ax.spines.values():
                spine.set_edgecolor('red')
                spine.set_linewidth(4)
                
    # Turn off axes for any empty subplots
    for j in range(iterations, len(axes_flat)):
        axes_flat[j].axis('off')
        
    plt.tight_layout()
    fig.savefig(MODE2_UMAPS_PNG, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved UMAP matrix to {MODE2_UMAPS_PNG}")
    
    print("\nSaving optimal pipeline outputs ...")
    # Set the "leiden" column to the best run so the downstream agent scripts work out-of-the-box
    adata.obs['leiden'] = adata.obs[best_key]
    
    markers = rank_markers(adata, groupby='leiden')
    markers.to_csv(MARKERS_CSV, index=False)
    sc.pl.umap(adata, color="leiden", show=False, save="_leiden.png")
    adata.write_h5ad(PROCESSED_H5AD)
    
    # Save the report without internal keys
    report_df.drop(columns=["distance_to_expected", "obs_key"]).to_csv(ITERATION_REPORT_CSV, index=False)
    print(f"Saved iteration report to {ITERATION_REPORT_CSV}")
    print("Done. Next: python src/annotate_agent.py")


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    sc.settings.verbosity = 1
    sc.settings.figdir = str(RESULTS_DIR)
    sc.settings.n_jobs = 1

    parser = argparse.ArgumentParser(description="Scanpy pipeline for PBMC3k")
    parser.add_argument("--mode", type=int, choices=[1, 2], help="1: Fixed resolution, 2: Iterative resolution")
    parser.add_argument("--iterations", type=int, default=10, help="Number of iterations for mode 2")
    args = parser.parse_args()
    
    if args.mode is None:
        print("Please choose a run mode:")
        print(f"  Mode 1: Use the fixed default resolution ({LEIDEN_RESOLUTION})")
        print("  Mode 2: Let the agent iterate over multiple resolutions to find the best fit")
        choice = input("Enter mode (1 or 2): ").strip()
        if choice == "2":
            args.mode = 2
            iters = input("Enter number of iterations (default 10): ").strip()
            if iters:
                args.iterations = int(iters)
        else:
            args.mode = 1
            
    if args.mode == 1:
        run_mode_1()
    else:
        run_mode_2(args.iterations)

if __name__ == "__main__":
    main()
