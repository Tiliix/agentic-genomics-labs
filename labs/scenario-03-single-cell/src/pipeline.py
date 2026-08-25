"""Scanpy scRNA-seq pipeline for PBMC datasets.

Stages:
    1. Load counts / expression matrix
    2. QC filtering (dataset-aware)
    3. Normalization / feature selection
    4. Scale + PCA + neighbors + UMAP
    5. Leiden clustering
    6. rank_genes_groups marker extraction
    7. Program contrast analysis (intensity vs prevalence)

Outputs (written to ./results):
    - pbmc3k_processed.h5ad
    - markers_top.csv
    - umap_leiden.png
    - resolution_iteration_report.csv (Mode 2)
    - mode2_UMAPs.png (Mode 2)
    - program_contrasts.csv
    - run_metadata.json
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scanpy as sc
from scipy.stats import fisher_exact, mannwhitneyu

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
RAW_H5AD = DATA_DIR / "pbmc3k_raw.h5ad"
KANG_H5AD = DATA_DIR / "kang2018_raw.h5ad"
PROCESSED_H5AD = RESULTS_DIR / "pbmc3k_processed.h5ad"
MARKERS_CSV = RESULTS_DIR / "markers_top.csv"
UMAP_PNG = RESULTS_DIR / "umap_leiden.png"
ITERATION_REPORT_CSV = RESULTS_DIR / "resolution_iteration_report.csv"
MODE2_UMAPS_PNG = RESULTS_DIR / "mode2_UMAPs.png"
PROGRAM_CONTRASTS_CSV = RESULTS_DIR / "program_contrasts.csv"
RUN_METADATA_JSON = RESULTS_DIR / "run_metadata.json"

# ---------------------------------------------------------------------------
# Dataset selection
# ---------------------------------------------------------------------------
DATASET_SIMPLE = "simple"
DATASET_COMPLEX = "complex"
DATASET_LABELS = {
    DATASET_SIMPLE: "PBMC 3k (classic, cleaner baseline)",
    DATASET_COMPLEX: "Kang 2018 IFN-beta PBMC (ctrl vs stim, ambiguity-prone)",
}

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
ALPHA = 0.05
MIN_GROUP_SIZE = 20

# Programs used for cross-readout ambiguity tests. These are canonical PBMC
# signatures and intentionally include both identity-like and state-like sets.
PROGRAM_SETS: dict[str, list[str]] = {
    "IFN_response": [
        "ISG15", "IFIT1", "IFIT3", "MX1", "OAS1",
        "OASL", "RSAD2", "IFI44L", "STAT1", "IRF7",
    ],
    "Cytotoxicity": ["NKG7", "GNLY", "PRF1", "GZMB", "CTSW", "KLRD1", "TRBC1", "TRAC"],
    "Antigen_presentation": [
        "HLA-DRA", "HLA-DRB1", "HLA-DPA1", "HLA-DPB1", "FCER1A", "CD74", "CST3",
    ],
    "Cell_cycle": ["MKI67", "TOP2A", "TYMS", "PCNA", "STMN1", "HMGB2", "UBE2C", "BIRC5"],
    "Stress_response": ["JUN", "FOS", "DUSP1", "HSPA1A", "HSPA1B", "DNAJB1", "ATF3", "EGR1"],
}


def benjamini_hochberg(pvals: pd.Series) -> pd.Series:
    """Return BH-adjusted p-values for a p-value series."""
    if pvals.empty:
        return pvals.copy()

    values = pvals.astype(float).to_numpy()
    order = np.argsort(values)
    ranked = values[order]
    n = len(values)
    adjusted_ranked = np.empty(n, dtype=float)
    running_min = 1.0
    for idx in range(n - 1, -1, -1):
        rank = idx + 1
        candidate = ranked[idx] * n / rank
        running_min = min(running_min, candidate)
        adjusted_ranked[idx] = running_min
    adjusted = np.empty(n, dtype=float)
    adjusted[order] = np.clip(adjusted_ranked, 0.0, 1.0)
    return pd.Series(adjusted, index=pvals.index)


def load_counts(dataset_mode: str) -> sc.AnnData:
    """Load the requested dataset."""
    if dataset_mode == DATASET_SIMPLE:
        if RAW_H5AD.exists():
            adata = sc.read_h5ad(RAW_H5AD)
        else:
            adata = sc.datasets.pbmc3k()
            adata.var_names_make_unique()
        adata.uns["dataset_name"] = "pbmc3k"
        return adata

    if dataset_mode == DATASET_COMPLEX:
        if not KANG_H5AD.exists():
            raise SystemExit(
                f"{KANG_H5AD} not found. Download it first with:\n"
                "  python scripts/download_data.py --dataset complex"
            )
        adata = sc.read_h5ad(KANG_H5AD)
        adata.var_names_make_unique()
        adata.uns["dataset_name"] = "kang2018_ifnb"
        return adata

    raise ValueError(f"Unsupported dataset_mode='{dataset_mode}'")


def quality_control(adata: sc.AnnData, dataset_mode: str) -> sc.AnnData:
    """Apply QC with dataset-aware behavior."""
    if dataset_mode == DATASET_COMPLEX:
        # Kang 2018 is raw counts but has larger, stimulated cells; use standard
        # QC with a data-driven upper gene bound instead of the PBMC3k-specific
        # fixed 2500 cutoff (which would discard many genuine activated cells).
        print("[QC] Standard QC for Kang 2018 (data-driven upper gene bound).")
        sc.pp.filter_cells(adata, min_genes=MIN_GENES_PER_CELL)
        sc.pp.filter_genes(adata, min_cells=MIN_CELLS_PER_GENE)
        adata.var["mt"] = adata.var_names.str.startswith("MT-")
        sc.pp.calculate_qc_metrics(
            adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True
        )
        upper = float(np.quantile(adata.obs["n_genes_by_counts"], 0.98))
        adata = adata[adata.obs["n_genes_by_counts"] < upper, :].copy()
        if float(adata.obs["pct_counts_mt"].max()) > 0.0:
            adata = adata[adata.obs["pct_counts_mt"] < MAX_PCT_MITO, :].copy()
        return adata

    sc.pp.filter_cells(adata, min_genes=MIN_GENES_PER_CELL)
    sc.pp.filter_genes(adata, min_cells=MIN_CELLS_PER_GENE)
    adata.var["mt"] = adata.var_names.str.startswith("MT-")
    sc.pp.calculate_qc_metrics(
        adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True
    )
    adata = adata[adata.obs["n_genes_by_counts"] < MAX_GENES_PER_CELL, :].copy()
    adata = adata[adata.obs["pct_counts_mt"] < MAX_PCT_MITO, :].copy()
    return adata


def normalize(adata: sc.AnnData, dataset_mode: str) -> sc.AnnData:
    """Normalize and choose informative genes."""
    adata.layers["counts"] = adata.X.copy()
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    adata.raw = adata
    sc.pp.highly_variable_genes(adata, n_top_genes=N_TOP_HVG, flavor="seurat")
    adata = adata[:, adata.var["highly_variable"]].copy()
    return adata

def pre_cluster(adata: sc.AnnData) -> sc.AnnData:
    """Run scale, PCA, neighbors, and UMAP with safe dimensions."""
    if adata.n_obs < 3:
        raise ValueError("Need at least 3 cells after QC to run clustering.")

    sc.pp.scale(adata, max_value=10)
    n_pcs = max(2, min(N_PCS, adata.n_vars - 1, adata.n_obs - 1))
    n_neighbors = max(2, min(N_NEIGHBORS, adata.n_obs - 1))
    sc.tl.pca(adata, svd_solver="arpack", n_comps=n_pcs)
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs)
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


def _program_gene_source(adata: sc.AnnData) -> tuple[list[str], bool]:
    """Return (var_names, use_raw), preferring the full raw gene set for scoring.

    Program genes (e.g. IFN, stress) are often dropped by HVG selection, so we
    score against ``adata.raw`` (the pre-HVG, normalized matrix) when available.
    """
    if adata.raw is not None:
        return list(adata.raw.var_names), True
    return list(adata.var_names), False


def _case_insensitive_genes(var_names: list[str], genes: list[str]) -> list[str]:
    lookup = {str(g).upper(): str(g) for g in var_names}
    return [lookup[g.upper()] for g in genes if g.upper() in lookup]


def add_program_scores(adata: sc.AnnData) -> dict[str, str]:
    """Add score columns to adata.obs and return {program_name: obs_col_name}."""
    var_names, use_raw = _program_gene_source(adata)
    mapping: dict[str, str] = {}
    for program_name, genes in PROGRAM_SETS.items():
        present = _case_insensitive_genes(var_names, genes)
        if len(present) < 3:
            print(
                f"[Program score] Skipping {program_name}: only {len(present)} genes present."
            )
            continue
        col = f"program__{program_name}"
        sc.tl.score_genes(adata, gene_list=present, score_name=col, use_raw=use_raw)
        mapping[program_name] = col
    return mapping

def analyze_program_contrasts(adata: sc.AnnData, groupby: str = "leiden") -> pd.DataFrame:
    """Compare intensity and prevalence for each (cluster, program) against shared null."""
    program_cols = add_program_scores(adata)
    if not program_cols:
        raise ValueError(
            "No program scores were computed. Check that program genes exist in the dataset."
        )

    clusters = adata.obs[groupby].astype(str)
    rows: list[dict] = []
    for program_name, score_col in program_cols.items():
        for cluster in sorted(clusters.unique(), key=lambda x: int(x) if x.isdigit() else x):
            mask = clusters == cluster
            n_cluster = int(mask.sum())
            n_null = int((~mask).sum())
            if n_cluster < MIN_GROUP_SIZE or n_null < MIN_GROUP_SIZE:
                continue

            score_cluster = adata.obs.loc[mask, score_col].astype(float)
            score_null = adata.obs.loc[~mask, score_col].astype(float)

            if score_cluster.nunique() <= 1 and score_null.nunique() <= 1:
                p_intensity = 1.0
            else:
                _, p_intensity = mannwhitneyu(
                    score_cluster, score_null, alternative="two-sided"
                )

            threshold = float(np.quantile(score_null, 0.9))
            on_cluster = int((score_cluster >= threshold).sum())
            off_cluster = n_cluster - on_cluster
            on_null = int((score_null >= threshold).sum())
            off_null = n_null - on_null
            table = np.array([[on_cluster, off_cluster], [on_null, off_null]], dtype=int)
            _, p_prevalence = fisher_exact(table, alternative="two-sided")

            mean_cluster = float(score_cluster.mean())
            mean_null = float(score_null.mean())
            frac_on_cluster = float(on_cluster / n_cluster)
            frac_on_null = float(on_null / n_null)

            rows.append(
                {
                    "cluster": cluster,
                    "program": program_name,
                    "n_cluster": n_cluster,
                    "n_null": n_null,
                    "mean_score_cluster": mean_cluster,
                    "mean_score_null": mean_null,
                    "delta_mean": mean_cluster - mean_null,
                    "p_intensity": float(p_intensity),
                    "frac_on_cluster": frac_on_cluster,
                    "frac_on_null": frac_on_null,
                    "delta_frac_on": frac_on_cluster - frac_on_null,
                    "prevalence_threshold_q90": threshold,
                    "p_prevalence": float(p_prevalence),
                }
            )

    contrasts = pd.DataFrame(rows)
    if contrasts.empty:
        raise ValueError("Program contrast table is empty; no valid contrasts were generated.")

    contrasts["p_intensity_adj"] = benjamini_hochberg(contrasts["p_intensity"])
    contrasts["p_prevalence_adj"] = benjamini_hochberg(contrasts["p_prevalence"])
    contrasts["sig_intensity"] = contrasts["p_intensity_adj"] < ALPHA
    contrasts["sig_prevalence"] = contrasts["p_prevalence_adj"] < ALPHA
    contrasts["sig_both"] = contrasts["sig_intensity"] & contrasts["sig_prevalence"]
    contrasts["discordant"] = contrasts["sig_intensity"] ^ contrasts["sig_prevalence"]
    return contrasts


def summarize_program_contrasts(contrasts: pd.DataFrame) -> dict[str, int]:
    sig_intensity = int(contrasts["sig_intensity"].sum())
    sig_prevalence = int(contrasts["sig_prevalence"].sum())
    sig_both = int(contrasts["sig_both"].sum())
    return {
        "total_contrasts": len(contrasts),
        "significant_intensity": sig_intensity,
        "significant_prevalence": sig_prevalence,
        "significant_both": sig_both,
        "intensity_only": sig_intensity - sig_both,
        "prevalence_only": sig_prevalence - sig_both,
    }


def save_run_metadata(
    dataset_mode: str,
    mode: int,
    iterations: int | None = None,
    selected_resolution: float | None = None,
) -> None:
    metadata = {
        "dataset_mode": dataset_mode,
        "dataset_label": DATASET_LABELS[dataset_mode],
        "mode": mode,
        "iterations": iterations,
        "selected_resolution": selected_resolution,
    }
    RUN_METADATA_JSON.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

def save_dataset_umap(dataset_mode: str) -> None:
    """Copy the generic umap_leiden.png to a dataset-specific filename.

    The generic name is kept for backward compatibility, and a suffixed copy
    (e.g. umap_leiden_complex.png) is written so simple and complex runs do not
    overwrite each other's clustering UMAP.
    """
    src = UMAP_PNG
    if src.exists():
        dst = RESULTS_DIR / f"umap_leiden_{dataset_mode}.png"
        shutil.copyfile(src, dst)
        print(f"Saved dataset UMAP copy: {dst}")

def run_mode_1(dataset_mode: str) -> None:
    print(f"\n--- MODE 1: Fixed Resolution ({LEIDEN_RESOLUTION}) ---")
    adata = load_counts(dataset_mode)
    adata = quality_control(adata, dataset_mode)
    adata = normalize(adata, dataset_mode)
    adata = pre_cluster(adata)

    print(f"[4/7] Leiden clustering at resolution {LEIDEN_RESOLUTION} ...")
    adata = do_leiden(adata, LEIDEN_RESOLUTION)
    n_clusters = adata.obs["leiden"].nunique()
    print(f"      found {n_clusters} Leiden clusters")

    print("[5/7] Ranking marker genes ...")
    markers = rank_markers(adata)
    markers.to_csv(MARKERS_CSV, index=False)

    print("[6/7] Program contrast analysis (intensity vs prevalence) ...")
    contrasts = analyze_program_contrasts(adata, groupby="leiden")
    contrasts.to_csv(PROGRAM_CONTRASTS_CSV, index=False)
    summary = summarize_program_contrasts(contrasts)
    print("      contrast summary:", summary)

    print("[7/7] Saving processed AnnData + UMAP plot ...")
    sc.pl.umap(adata, color="leiden", show=False, save="_leiden.png")
    adata.write_h5ad(PROCESSED_H5AD)
    save_run_metadata(
        dataset_mode=dataset_mode, mode=1, iterations=None, selected_resolution=LEIDEN_RESOLUTION
    )
    save_dataset_umap(dataset_mode)
    print(f"Saved program contrasts to {PROGRAM_CONTRASTS_CSV}")
    print("Done. Next: python src/annotate_agent.py")


def run_mode_2(iterations: int, dataset_mode: str) -> None:
    print(f"\n--- MODE 2: Iterative Resolution Search ({iterations} iterations) ---")
    adata = load_counts(dataset_mode)
    adata = quality_control(adata, dataset_mode)
    adata = normalize(adata, dataset_mode)
    adata = pre_cluster(adata)

    resolutions = np.linspace(0.2, 1.8, iterations)
    print(f"Agent proposes the following {iterations} resolution values:")
    print(f"[{', '.join([f'{r:.2f}' for r in resolutions])}]")

    reports = []
    for i, res in enumerate(resolutions):
        print(f"\n--> Iteration {i + 1}/{iterations}: Resolution = {res:.2f}")
        obs_key = f"leiden_{res:.2f}"
        adata = do_leiden(adata, res, key_added=obs_key)
        n_clusters = adata.obs[obs_key].nunique()
        print(f"    Found {n_clusters} clusters.")
        reports.append(
            {
                "iteration": i + 1,
                "resolution": round(float(res), 2),
                "num_clusters": int(n_clusters),
                "obs_key": obs_key,
            }
        )

    report_df = pd.DataFrame(reports)
    report_df["distance_to_expected"] = abs(report_df["num_clusters"] - 9)
    best_idx = int(report_df["distance_to_expected"].idxmin())
    best_res = float(report_df.loc[best_idx, "resolution"])
    best_key = str(report_df.loc[best_idx, "obs_key"])

    print("\n--- Iteration Summary ---")
    report_df["is_best"] = False
    report_df.loc[best_idx, "is_best"] = True
    print(report_df.drop(columns=["distance_to_expected", "obs_key"]))
    print(
        f"\nAgent selected best resolution: {best_res:.2f} "
        "(closest to 9 expected broad cell types in PBMC)"
    )

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
        is_best = bool(row["is_best"])
        sc.pl.umap(adata, color=c_key, ax=ax, show=False, legend_loc="on data", legend_fontsize=8)
        ax.set_title(f"Res: {c_res:.2f} | Clusters: {c_num}")
        if is_best:
            for spine in ax.spines.values():
                spine.set_edgecolor("red")
                spine.set_linewidth(4)

    for j in range(iterations, len(axes_flat)):
        axes_flat[j].axis("off")

    plt.tight_layout()
    fig.savefig(MODE2_UMAPS_PNG, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved UMAP matrix to {MODE2_UMAPS_PNG}")

    print("\nSaving optimal pipeline outputs ...")
    adata.obs["leiden"] = adata.obs[best_key]
    markers = rank_markers(adata, groupby="leiden")
    markers.to_csv(MARKERS_CSV, index=False)
    sc.pl.umap(adata, color="leiden", show=False, save="_leiden.png")
    adata.write_h5ad(PROCESSED_H5AD)

    contrasts = analyze_program_contrasts(adata, groupby="leiden")
    contrasts.to_csv(PROGRAM_CONTRASTS_CSV, index=False)
    summary = summarize_program_contrasts(contrasts)
    print("Program contrast summary:", summary)

    report_df.drop(columns=["distance_to_expected", "obs_key"]).to_csv(
        ITERATION_REPORT_CSV, index=False
    )
    print(f"Saved iteration report to {ITERATION_REPORT_CSV}")
    print(f"Saved program contrasts to {PROGRAM_CONTRASTS_CSV}")

    save_run_metadata(
        dataset_mode=dataset_mode,
        mode=2,
        iterations=iterations,
        selected_resolution=best_res,
    )
    save_dataset_umap(dataset_mode)
    print("Done. Next: python src/annotate_agent.py")

def choose_dataset_interactive() -> str:
    print("Please choose a dataset profile:")
    print("  1) Simple PBMC 3k (clean baseline, quick run)")
    print("  2) Complex PBMC 68k reduced (higher heterogeneity/ambiguity)")
    choice = input("Enter dataset profile (1 or 2): ").strip()
    if choice == "2":
        return DATASET_COMPLEX
    return DATASET_SIMPLE


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    sc.settings.verbosity = 1
    sc.settings.figdir = str(RESULTS_DIR)
    sc.settings.n_jobs = 1

    parser = argparse.ArgumentParser(description="Scanpy pipeline for PBMC datasets")
    parser.add_argument(
        "--mode",
        type=int,
        choices=[1, 2],
        help="1: Fixed resolution, 2: Iterative resolution",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations for mode 2",
    )
    parser.add_argument(
        "--dataset",
        choices=[DATASET_SIMPLE, DATASET_COMPLEX],
        help="Dataset profile: simple=PBMC3k, complex=PBMC68k reduced",
    )
    args = parser.parse_args()

    if args.dataset is None:
        args.dataset = choose_dataset_interactive()

    print(f"Selected dataset: {DATASET_LABELS[args.dataset]}")

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

    if args.mode == 2 and args.iterations < 2:
        raise SystemExit("--iterations must be >= 2 for mode 2.")

    if args.mode == 1:
        run_mode_1(args.dataset)
    else:
        run_mode_2(args.iterations, args.dataset)


if __name__ == "__main__":
    main()






