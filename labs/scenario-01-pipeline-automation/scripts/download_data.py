"""
download_data.py
================

Fetch a small public RNA-seq counts matrix into ``data/`` so the lab can run.

Primary source
--------------
The pasilla dataset is a classic, small Drosophila RNA-seq DE dataset (7 samples,
treated vs untreated) that ships as a gene-level count table — perfect for a fast
DESeq2 lab. We pull the count table and the sample annotation from the
Bioconductor ``pasilla`` package data mirrored on GitHub.

Fallback
--------
If there is no internet (this container, an air-gapped CI runner, etc.) the script
generates a tiny **synthetic** counts matrix with a known set of differentially
expressed genes so the pipeline still runs end to end. Use ``--synthetic-only`` to
force this path (used by CI).

Outputs
-------
    data/counts.csv    genes x samples integer counts (genes as the index)
    data/coldata.csv   samples x metadata, with a 'condition' column

Usage
-----
    python scripts/download_data.py                 # try download, else synthetic
    python scripts/download_data.py --synthetic-only
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

COUNTS_CSV = DATA_DIR / "counts.csv"
COLDATA_CSV = DATA_DIR / "coldata.csv"

# Public mirrors of the Bioconductor `pasilla` gene-count table (Drosophila,
# treated vs untreated; tab-separated, first column = gene id). The original
# bioc_docker mirror was retired, so we try a list of current mirrors in order
# and use the first that responds. Add more URLs here if any go offline.
PASILLA_COUNTS_URLS = [
    "https://raw.githubusercontent.com/Scavetta/DAwR-CS/master/pasilla_gene_counts.tsv",
]


def _download_pasilla() -> bool:
    """Try each mirror of the pasilla counts in turn; return True on the first
    that succeeds. Raises if every mirror fails (caller falls back to synthetic)."""
    import requests

    last_err: Exception | None = None
    for url in PASILLA_COUNTS_URLS:
        try:
            print(f"Downloading pasilla counts from:\n  {url}")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()

            counts = pd.read_csv(io.StringIO(resp.text), sep="\t", index_col=0)
            # Sample names look like 'untreated1', 'treated1', ... — derive the
            # condition from the column name prefix.
            conditions = [
                "treated" if c.startswith("treated") else "untreated"
                for c in counts.columns
            ]
            coldata = pd.DataFrame({"condition": conditions}, index=counts.columns)
            coldata.index.name = "sample"

            DATA_DIR.mkdir(parents=True, exist_ok=True)
            counts.to_csv(COUNTS_CSV)
            coldata.to_csv(COLDATA_CSV)
            print(
                f"Wrote {COUNTS_CSV} ({counts.shape[0]} genes x "
                f"{counts.shape[1]} samples) and {COLDATA_CSV}."
            )
            return True
        except Exception as exc:  # noqa: BLE001 — try the next mirror
            last_err = exc
            print(f"  mirror failed: {exc}")

    raise RuntimeError(f"all pasilla mirrors failed (last error: {last_err})")


def _generate_synthetic(
    n_genes: int = 2000,
    n_per_group: int = 4,
    n_de: int = 100,
    seed: int = 7,
) -> None:
    """
    Generate a small synthetic counts matrix with a known DE signal.

    ``n_de`` genes are up-regulated in the 'treated' group; the rest are noise.
    Counts are drawn from a negative-binomial so DESeq2 has realistic dispersion.
    """
    rng = np.random.default_rng(seed)
    samples = [f"untreated{i + 1}" for i in range(n_per_group)] + [
        f"treated{i + 1}" for i in range(n_per_group)
    ]
    conditions = ["untreated"] * n_per_group + ["treated"] * n_per_group

    # Baseline mean expression per gene (log-normal spread of magnitudes).
    base_mean = rng.lognormal(mean=3.0, sigma=1.0, size=n_genes)

    # Per-gene, per-group fold change: first n_de genes up in 'treated'.
    fc = np.ones(n_genes)
    fc[:n_de] = rng.uniform(3.0, 8.0, size=n_de)

    def nb_counts(mean_vec: np.ndarray) -> np.ndarray:
        # Negative binomial via gamma-poisson mixture; dispersion ~0.2.
        dispersion = 0.2
        shape = 1.0 / dispersion
        gamma = rng.gamma(shape, mean_vec / shape)
        return rng.poisson(gamma)

    cols = {}
    for sample, cond in zip(samples, conditions):
        mean_vec = base_mean * (fc if cond == "treated" else 1.0)
        cols[sample] = nb_counts(mean_vec)

    gene_ids = [f"GENE{i:05d}" for i in range(n_genes)]
    counts = pd.DataFrame(cols, index=gene_ids)
    counts.index.name = "gene"

    coldata = pd.DataFrame({"condition": conditions}, index=samples)
    coldata.index.name = "sample"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    counts.to_csv(COUNTS_CSV)
    coldata.to_csv(COLDATA_CSV)
    print(
        f"Wrote SYNTHETIC {COUNTS_CSV} ({n_genes} genes x {len(samples)} samples) "
        f"with {n_de} truly-DE genes, and {COLDATA_CSV}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download or synthesise RNA-seq counts.")
    parser.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Skip the download and always generate the synthetic dataset.",
    )
    args = parser.parse_args()

    if args.synthetic_only:
        _generate_synthetic()
        return

    try:
        _download_pasilla()
    except Exception as exc:  # noqa: BLE001 — any failure -> offline fallback
        print(f"Download failed ({exc}). Falling back to synthetic dataset.")
        _generate_synthetic()


if __name__ == "__main__":
    main()
