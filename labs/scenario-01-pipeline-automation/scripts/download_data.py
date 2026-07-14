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

Interactive by default
----------------------
Run with no arguments and the script **prompts for the URL of an RNA-seq counts
file** to analyse. Press Enter (no input) to use the built-in **pasilla** dataset.
Pass ``--url`` to supply a link non-interactively, or ``--synthetic-only`` for an
offline synthetic set (used by CI). A custom file must be a gene-level counts table
(TSV or CSV) with the gene id in column 1 and one integer-count column per sample;
condition is inferred from column names by stripping the trailing replicate number
(``treated1``/``treated2`` -> ``treated``).

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
    python scripts/download_data.py                 # interactive prompt (default: pasilla)
    python scripts/download_data.py --url <URL>     # analyse a specific counts file
    python scripts/download_data.py --synthetic-only
"""

from __future__ import annotations

import argparse
import io
import re
import sys
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

# One-line description of the default dataset, shown at the interactive prompt.
PASILLA_DESC = (
    "the pasilla dataset — a classic Drosophila melanogaster RNA-seq experiment "
    "(~14,599 genes; 7 samples: 3 pasilla splicing-factor knockdown 'treated' vs "
    "4 'untreated' controls)."
)


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


def _derive_conditions(columns: list[str]) -> list[str]:
    """Infer a condition label per sample by stripping the trailing replicate
    number (and any separator) from each column name, e.g. ``treated1`` ->
    ``treated``, ``ctrl_02`` -> ``ctrl``. Generalises the pasilla convention."""
    labels = []
    for col in columns:
        label = re.sub(r"[ _.\-]*\d+$", "", str(col)).strip(" _.-")
        labels.append(label or str(col))
    return labels


def _download_counts(url: str) -> None:
    """Download a user-supplied RNA-seq counts table (TSV or CSV) and write
    ``data/counts.csv`` + ``data/coldata.csv``. Raises on any download/parse error
    so the caller can fall back to the default dataset."""
    import requests

    print(f"Downloading RNA-seq counts from:\n  {url}")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    # Auto-detect the delimiter (tab vs comma) from the header line.
    header = resp.text.split("\n", 1)[0]
    sep = "\t" if header.count("\t") >= header.count(",") else ","
    counts = pd.read_csv(io.StringIO(resp.text), sep=sep, index_col=0)

    # Keep only numeric (count) columns; drop any annotation columns.
    counts = counts.select_dtypes(include="number")
    if counts.shape[1] < 2:
        raise ValueError(
            "need at least 2 numeric sample columns for differential expression"
        )

    conditions = _derive_conditions(list(counts.columns))
    coldata = pd.DataFrame({"condition": conditions}, index=counts.columns)
    coldata.index.name = "sample"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    counts.to_csv(COUNTS_CSV)
    coldata.to_csv(COLDATA_CSV)

    groups = sorted(set(conditions))
    print(
        f"Wrote {COUNTS_CSV} ({counts.shape[0]} genes x {counts.shape[1]} samples) "
        f"and {COLDATA_CSV}."
    )
    print(f"Derived condition group(s) from column names: {groups}")
    if len(groups) < 2:
        print(
            "WARNING: fewer than 2 condition groups were derived — differential "
            "expression needs two. Name sample columns '<group><replicate>' "
            "(e.g. treated1, control2)."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch RNA-seq counts for the lab (interactive by default)."
    )
    parser.add_argument(
        "--url",
        default=None,
        help="URL of an RNA-seq counts file (TSV/CSV) to analyse; skips the prompt.",
    )
    parser.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Skip any download and always generate the synthetic dataset (CI).",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="Never prompt; use --url if given, otherwise the default pasilla set.",
    )
    args = parser.parse_args()

    if args.synthetic_only:
        _generate_synthetic()
        return

    url = args.url

    # Interactive prompt — only when attached to a terminal and no URL/flag given.
    if url is None and not args.no_input and sys.stdin.isatty():
        print(f"By default this lab runs on {PASILLA_DESC}")
        entered = input(
            "\nEnter the URL of an RNA-seq counts file to analyse (TSV/CSV, gene id "
            "in column 1),\nor press Enter to use the default pasilla dataset: "
        ).strip()
        url = entered or None

    if url:
        try:
            _download_counts(url)
            return
        except Exception as exc:  # noqa: BLE001 — bad URL -> fall back to default
            print(f"Could not use '{url}' ({exc}).")
            print("Falling back to the default pasilla dataset.")

    # Default: pasilla, with a synthetic offline fallback.
    try:
        _download_pasilla()
    except Exception as exc:  # noqa: BLE001 — any failure -> offline fallback
        print(f"Download failed ({exc}). Falling back to synthetic dataset.")
        _generate_synthetic()


if __name__ == "__main__":
    main()
