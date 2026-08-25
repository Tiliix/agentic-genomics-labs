"""Download datasets for the single-cell lab.

Two dataset profiles are available:

  1) simple  -- 10x Genomics PBMC 3k
     ~2,700 peripheral blood mononuclear cells from a single healthy donor
     (10x Cell Ranger 1.1.0). One condition, cleaner structure, ~9 broad cell
     types. This is the classic Scanpy tutorial dataset: fast to run and easy to
     interpret, ideal as a baseline.

  2) complex -- Kang et al. 2018 IFN-beta PBMC (two conditions)
     ~24,700 PBMCs from lupus patients, split into control ("ctrl") and
     interferon-beta stimulated ("stim") cells, with 8 annotated cell types.
     Interferon stimulation drives a strong, cell-type-specific response, so the
     same gene program can change in strength per cell (intensity) or in the
     fraction of responding cells (prevalence). That makes this dataset far more
     prone to the "both readouts are defensible but disagree" case the agent's
     cross-readout disagreement check is designed to catch.

Run:
    python scripts/download_data.py                 # interactive prompt
    python scripts/download_data.py --dataset simple
    python scripts/download_data.py --dataset complex
"""

from __future__ import annotations

import argparse
import tarfile
import urllib.request
from pathlib import Path

import scanpy as sc

# Where we cache the data for the rest of the pipeline.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
H5AD_RAW = DATA_DIR / "pbmc3k_raw.h5ad"
KANG_H5AD = DATA_DIR / "kang2018_raw.h5ad"

# Public 10x Genomics URL for the PBMC 3k filtered matrices (Cell Ranger 1.1.0).
TENX_URL = (
    "https://cf.10xgenomics.com/samples/cell-exp/1.1.0/pbmc3k/"
    "pbmc3k_filtered_gene_bc_matrices.tar.gz"
)

# Processed Kang et al. 2018 IFN-beta PBMC dataset (raw counts, ctrl/stim labels),
# hosted by the scverse project. A User-Agent header is required by the host.
KANG_URL = "https://exampledata.scverse.org/pertpy/kang_2018.h5ad"

DATASET_SIMPLE = "simple"
DATASET_COMPLEX = "complex"

DATASET_DESCRIPTIONS = {
    DATASET_SIMPLE: (
        "PBMC 3k (~2,700 cells, one healthy donor, single condition). "
        "Clean baseline, fast, classic Scanpy tutorial dataset."
    ),
    DATASET_COMPLEX: (
        "Kang 2018 IFN-beta PBMC (~24,700 cells, ctrl vs stim, 8 cell types). "
        "Interferon response makes intensity-vs-prevalence disagreements common."
    ),
}


def via_scanpy() -> sc.AnnData:
    """Preferred: let Scanpy fetch and cache PBMC3k."""
    adata = sc.datasets.pbmc3k()
    return adata


def via_manual_download() -> sc.AnnData:
    """Fallback: pull the .tar.gz from 10x and parse the MTX triplet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tar_path = DATA_DIR / "pbmc3k_filtered_gene_bc_matrices.tar.gz"

    if not tar_path.exists():
        print(f"Downloading PBMC3k from {TENX_URL} ...")
        urllib.request.urlretrieve(TENX_URL, tar_path)

    print(f"Extracting {tar_path} ...")
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(DATA_DIR)

    mtx_dir = DATA_DIR / "filtered_gene_bc_matrices" / "hg19"
    adata = sc.read_10x_mtx(mtx_dir, var_names="gene_symbols", cache=True)
    return adata


def download_pbmc3k() -> None:
    """Download the simple PBMC3k dataset and cache it as raw AnnData."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if H5AD_RAW.exists():
        print(f"PBMC3k already present: {H5AD_RAW}")
        return
    try:
        adata = via_scanpy()
        print("Loaded PBMC3k via scanpy.datasets.pbmc3k().")
    except Exception as exc:  # noqa: BLE001 - any network/SSL/proxy error -> fallback
        print(f"scanpy.datasets.pbmc3k() failed ({exc!r}); using manual fallback.")
        adata = via_manual_download()

    adata.var_names_make_unique()
    adata.write_h5ad(H5AD_RAW)
    print(f"Saved raw AnnData: {H5AD_RAW}  (shape={adata.shape})")


def download_kang() -> None:
    """Download the complex Kang 2018 IFN-beta dataset (raw counts, ctrl/stim)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if KANG_H5AD.exists():
        print(f"Kang 2018 already present: {KANG_H5AD}")
        return

    print(f"Downloading Kang 2018 IFN-beta PBMC from {KANG_URL} ...")
    print("(~38 MB; this can take a minute.)")
    # The host rejects requests without a browser-like User-Agent header.
    req = urllib.request.Request(KANG_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(KANG_H5AD, "wb") as fh:
        fh.write(resp.read())

    adata = sc.read_h5ad(KANG_H5AD)
    print(f"Saved raw AnnData: {KANG_H5AD}  (shape={adata.shape})")
    if "label" in adata.obs:
        counts = adata.obs["label"].value_counts().to_dict()
        print(f"Conditions: {counts}")


def choose_dataset_interactive() -> str:
    """Prompt the user to pick a dataset profile, showing a short description."""
    print("Which dataset do you want to download?\n")
    print(f"  1) simple  -- {DATASET_DESCRIPTIONS[DATASET_SIMPLE]}\n")
    print(f"  2) complex -- {DATASET_DESCRIPTIONS[DATASET_COMPLEX]}\n")
    choice = input("Enter dataset (1 or 2): ").strip()
    if choice == "2":
        return DATASET_COMPLEX
    return DATASET_SIMPLE


def main() -> None:
    parser = argparse.ArgumentParser(description="Download lab datasets")
    parser.add_argument(
        "--dataset",
        choices=[DATASET_SIMPLE, DATASET_COMPLEX],
        help="Dataset profile to download (skips the interactive prompt).",
    )
    args = parser.parse_args()

    dataset = args.dataset or choose_dataset_interactive()
    print(f"\nSelected dataset: {dataset} -- {DATASET_DESCRIPTIONS[dataset]}\n")

    if dataset == DATASET_SIMPLE:
        download_pbmc3k()
    else:
        download_kang()

    print("\nDone. Next: python src/pipeline.py")


if __name__ == "__main__":
    main()
