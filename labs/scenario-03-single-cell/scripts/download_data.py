"""Download the 10x Genomics PBMC 3k dataset for the lab.

PBMC 3k is the classic Scanpy clustering tutorial dataset: ~2,700 peripheral
blood mononuclear cells from a healthy donor, sequenced on the 10x Genomics
platform (Cell Ranger 1.1.0).

Primary path:  scanpy.datasets.pbmc3k() — Scanpy ships a loader that fetches
the filtered gene-barcode matrix and returns a ready-to-use AnnData object.

Fallback path: if the Scanpy loader cannot reach the internet (e.g. corporate
proxy), download the raw 10x .tar.gz directly from the public 10x URL and read
it with scanpy.read_10x_mtx().

Run:
    python scripts/download_data.py
"""

from __future__ import annotations

import tarfile
import urllib.request
from pathlib import Path

import scanpy as sc

# Where we cache the data for the rest of the pipeline.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
H5AD_RAW = DATA_DIR / "pbmc3k_raw.h5ad"

# Public 10x Genomics URL for the PBMC 3k filtered matrices (Cell Ranger 1.1.0).
TENX_URL = (
    "https://cf.10xgenomics.com/samples/cell-exp/1.1.0/pbmc3k/"
    "pbmc3k_filtered_gene_bc_matrices.tar.gz"
)


def via_scanpy() -> sc.AnnData:
    """Preferred: let Scanpy fetch and cache PBMC3k."""
    # scanpy.datasets.pbmc3k() returns the raw counts AnnData (n_obs x n_vars).
    adata = sc.datasets.pbmc3k()
    return adata


def via_manual_download() -> sc.AnnData:
    """Fallback: pull the .tar.gz from 10x and parse the MTX triplet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tar_path = DATA_DIR / "pbmc3k_filtered_gene_bc_matrices.tar.gz"

    if not tar_path.exists():
        print(f"Downloading PBMC3k from {TENX_URL} ...")
        urllib.request.urlretrieve(TENX_URL, tar_path)  # noqa: S310 (trusted host)

    # Extract the matrix/barcodes/genes triplet.
    print(f"Extracting {tar_path} ...")
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(DATA_DIR)  # noqa: S202 (trusted archive)

    # Cell Ranger 1.1.0 lays files out under filtered_gene_bc_matrices/hg19/.
    mtx_dir = DATA_DIR / "filtered_gene_bc_matrices" / "hg19"
    # read_10x_mtx reads matrix.mtx + genes.tsv + barcodes.tsv into AnnData.
    adata = sc.read_10x_mtx(mtx_dir, var_names="gene_symbols", cache=True)
    return adata


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        adata = via_scanpy()
        print("Loaded PBMC3k via scanpy.datasets.pbmc3k().")
    except Exception as exc:  # network / SSL / proxy issues
        print(f"scanpy.datasets.pbmc3k() failed ({exc!r}); using manual fallback.")
        adata = via_manual_download()

    # Make gene names unique (some symbols repeat) before saving.
    adata.var_names_make_unique()
    adata.write_h5ad(H5AD_RAW)
    print(f"Saved raw AnnData: {H5AD_RAW}  (shape={adata.shape})")


if __name__ == "__main__":
    main()
