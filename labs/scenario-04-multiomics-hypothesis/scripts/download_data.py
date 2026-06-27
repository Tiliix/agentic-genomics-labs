#!/usr/bin/env python3
"""Fetch the MOFA+ CLL multi-omics tutorial dataset, or generate a synthetic
multi-omics fallback so the lab runs fully offline.

The real CLL dataset (mRNA, methylation, drug response, mutations) ships with
the MOFA2 / mofapy2 tutorials. We store it as a "long" data frame with columns
[sample, feature, view, value] — exactly the shape MOFA+ accepts.

Usage:
    python scripts/download_data.py             # try real download, else synthetic
    python scripts/download_data.py --synthetic # force synthetic fallback
    python scripts/download_data.py --real      # only try the real download
"""
from __future__ import annotations

import argparse
import io
import os
import sys

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Real dataset location.
#
# The MOFA+ CLL data is distributed as an RData/HDF5 bundle with the tutorials.
# A convenient long-format CSV/TSV mirror used by the muon/MOFA2 tutorials is
# the "getting started" CLL data. The canonical pointer is below; because this
# container has no internet, the download is best-effort and we fall back to the
# synthetic generator on any failure.
#
# Reference: https://muon-tutorials.readthedocs.io/en/latest/CLL.html
# Raw mirror (long-format TSV, ~loaded by load_dataset in the tutorials):
CLL_DATA_URL = "https://raw.githubusercontent.com/bioFAM/MOFA2_tutorials/master/data/CLL_data.txt.gz"

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LONG_PATH = os.path.join(DATA_DIR, "cll_long.csv")


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def download_real() -> bool:
    """Attempt to download the real CLL dataset into long format.

    Returns True on success, False on any failure (so the caller can fall back).
    """
    try:
        import gzip

        import requests  # imported lazily so --synthetic works without it
    except ImportError:
        print("requests not installed; cannot download real data.", file=sys.stderr)
        return False

    try:
        print(f"Downloading CLL dataset from {CLL_DATA_URL} ...")
        resp = requests.get(CLL_DATA_URL, timeout=60)
        resp.raise_for_status()
        # The tutorial file is a gzipped long-format table with a header row.
        raw = gzip.decompress(resp.content)
        df = pd.read_csv(io.BytesIO(raw), sep="\t")
        # Normalise column names to [sample, feature, view, value].
        rename = {
            "sample": "sample",
            "feature": "feature",
            "view": "view",
            "value": "value",
        }
        df = df.rename(columns={c: c.lower() for c in df.columns}).rename(columns=rename)
        df = df[["sample", "feature", "view", "value"]].dropna(subset=["value"])
        _ensure_data_dir()
        df.to_csv(LONG_PATH, index=False)
        print(f"Wrote real dataset -> {LONG_PATH} ({len(df):,} rows)")
        return True
    except Exception as exc:  # noqa: BLE001 - best effort, any failure -> fallback
        print(f"Real download failed ({exc}); will use synthetic fallback.", file=sys.stderr)
        return False


def generate_synthetic(
    n_samples: int = 200,
    seed: int = 0,
    n_features: dict[str, int] | None = None,
    n_factors: int = 4,
) -> pd.DataFrame:
    """Generate a small synthetic 4-view multi-omics dataset.

    The data is built from a shared low-rank latent structure (``n_factors``
    factors) so that MOFA+ can recover cross-view covariation — mirroring the
    real CLL views: mRNA, Methylation, Drugs, Mutations.
    """
    if n_features is None:
        # Deliberately small so the lab trains in seconds.
        n_features = {"mRNA": 120, "Methylation": 100, "Drugs": 40, "Mutations": 30}

    rng = np.random.default_rng(seed)
    # Shared latent factors: samples x factors.
    Z = rng.normal(size=(n_samples, n_factors))

    frames = []
    for view, n_feat in n_features.items():
        # Factor loadings for this view: factors x features (sparse-ish).
        W = rng.normal(size=(n_factors, n_feat))
        mask = rng.random(size=W.shape) < 0.4  # ~60% of loadings zeroed for sparsity
        W = W * mask
        signal = Z @ W
        noise = rng.normal(scale=0.5, size=signal.shape)
        X = signal + noise

        if view == "Mutations":
            # Binary view: threshold to 0/1, as real mutation calls are binary.
            X = (X > 0.7).astype(float)
        elif view == "Methylation":
            # Squash toward an M-value-like range.
            X = np.tanh(X)

        samples = [f"sample_{i:03d}" for i in range(n_samples)]
        features = [f"{view}_{j:03d}" for j in range(n_feat)]
        long = (
            pd.DataFrame(X, index=samples, columns=features)
            .reset_index(names="sample")
            .melt(id_vars="sample", var_name="feature", value_name="value")
        )
        long["view"] = view
        frames.append(long)

    df = pd.concat(frames, ignore_index=True)[["sample", "feature", "view", "value"]]
    return df


def write_synthetic(seed: int = 0) -> None:
    df = generate_synthetic(seed=seed)
    _ensure_data_dir()
    df.to_csv(LONG_PATH, index=False)
    print(f"Wrote synthetic dataset -> {LONG_PATH} ({len(df):,} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", help="force synthetic fallback")
    parser.add_argument("--real", action="store_true", help="only try the real download")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if args.synthetic:
        write_synthetic(seed=args.seed)
        return

    ok = download_real()
    if not ok and not args.real:
        write_synthetic(seed=args.seed)
    elif not ok and args.real:
        sys.exit("Real download failed and --real was requested.")


if __name__ == "__main__":
    main()
