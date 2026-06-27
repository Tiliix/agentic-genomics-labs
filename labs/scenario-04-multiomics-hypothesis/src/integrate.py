#!/usr/bin/env python3
"""Train a MOFA+ model on multi-omics views and extract latent factors plus the
top-weighted features per factor.

Pipeline:
  1. Load the long-format multi-omics table (data/cll_long.csv). If it is
     missing, generate the synthetic fallback in-process so the lab still runs.
  2. Train MOFA+ (mofapy2) across the views.
  3. Extract:
       - factors  : samples x factors  -> data/factors.csv
       - weights  : per view, features x factors -> data/weights/<view>.csv
       - a tidy "top features per factor" JSON the LLM agent consumes:
         data/top_features_per_factor.json

MOFA+ (Multi-Omics Factor Analysis) is real: https://biofam.github.io/MOFA2/

Run:
    python src/integrate.py [--n-factors 10] [--top-k 15]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

# Resolve repo-relative paths regardless of where the script is invoked from.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_DIR = os.path.join(ROOT, "data")
LONG_PATH = os.path.join(DATA_DIR, "cll_long.csv")
WEIGHTS_DIR = os.path.join(DATA_DIR, "weights")
FACTORS_PATH = os.path.join(DATA_DIR, "factors.csv")
TOPFEAT_PATH = os.path.join(DATA_DIR, "top_features_per_factor.json")
MODEL_PATH = os.path.join(DATA_DIR, "mofa_model.hdf5")


def load_long_data() -> pd.DataFrame:
    """Load the long-format multi-omics table, generating synthetic data if absent."""
    if not os.path.exists(LONG_PATH):
        print(f"{LONG_PATH} not found; generating synthetic data in-process.")
        # Import the generator from the sibling scripts/ package.
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from download_data import generate_synthetic  # type: ignore

        os.makedirs(DATA_DIR, exist_ok=True)
        df = generate_synthetic()
        df.to_csv(LONG_PATH, index=False)
    df = pd.read_csv(LONG_PATH)
    expected = {"sample", "feature", "view", "value"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Long data missing columns: {missing}")
    return df


def train_mofa(long_df: pd.DataFrame, n_factors: int) -> "object":
    """Train a MOFA+ model from a long-format data frame.

    Returns the trained mofapy2 entry-point object. Raises ImportError if
    mofapy2 is not installed (the caller can choose to fall back).
    """
    from mofapy2.run.entry_point import entry_point  # type: ignore

    ent = entry_point()
    # MOFA+ accepts the long data frame directly (columns: sample, feature, view, value).
    ent.set_data_options(scale_views=True)
    ent.set_data_df(long_df, likelihoods=None)  # likelihoods auto-inferred per view
    ent.set_model_options(factors=n_factors, spikeslab_weights=True, ard_weights=True)
    ent.set_train_options(
        iter=200,
        convergence_mode="fast",
        seed=1,
        verbose=False,
        gpu_mode=False,
    )
    ent.build()
    ent.run()
    return ent


def _factors_from_model(ent) -> pd.DataFrame:
    """Extract the samples x factors matrix as a tidy DataFrame."""
    # expectations["Z"] is the latent factor matrix; concatenate across groups.
    Z = ent.model.getExpectations()["Z"]["E"]
    samples = ent.data_opts["samples_names"][0]
    cols = [f"Factor{i + 1}" for i in range(Z.shape[1])]
    return pd.DataFrame(Z, index=samples, columns=cols)


def _weights_from_model(ent) -> dict[str, pd.DataFrame]:
    """Extract per-view features x factors weight matrices."""
    W = ent.model.getExpectations()["W"]  # list, one per view
    views = ent.data_opts["views_names"]
    feature_names = ent.data_opts["features_names"]
    out: dict[str, pd.DataFrame] = {}
    for vi, view in enumerate(views):
        Wv = W[vi]["E"]
        cols = [f"Factor{i + 1}" for i in range(Wv.shape[1])]
        out[view] = pd.DataFrame(Wv, index=feature_names[vi], columns=cols)
    return out


def top_features_per_factor(
    weights: dict[str, pd.DataFrame], top_k: int
) -> dict[str, list[dict]]:
    """Build the tidy structure the LLM agent consumes.

    For each factor, list the top-|weight| features across all views, keeping the
    signed weight and the view of origin so every downstream hypothesis can cite
    (factor, feature, weight, view).
    """
    # Determine the factor columns from any view.
    any_view = next(iter(weights.values()))
    factor_cols = list(any_view.columns)

    result: dict[str, list[dict]] = {}
    for factor in factor_cols:
        rows = []
        for view, W in weights.items():
            for feature, w in W[factor].items():
                rows.append({"feature": feature, "view": view, "weight": float(w)})
        # Rank by absolute weight, keep top_k.
        rows.sort(key=lambda r: abs(r["weight"]), reverse=True)
        result[factor] = rows[:top_k]
    return result


# ---------------------------------------------------------------------------
# Lightweight fallback when mofapy2 is unavailable (keeps the lab runnable).
# Uses sparse PCA-like SVD on the concatenated, scaled views. This is NOT MOFA+,
# but it produces the same factor/weight artefacts so the agent step works.
# ---------------------------------------------------------------------------
def train_fallback(long_df: pd.DataFrame, n_factors: int):
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import StandardScaler

    print("mofapy2 unavailable -> using SVD fallback (not true MOFA+).")
    # Pivot each view to samples x features, scale, then concatenate.
    views = sorted(long_df["view"].unique())
    samples = sorted(long_df["sample"].unique())
    blocks, feature_index = [], []
    for view in views:
        wide = (
            long_df[long_df["view"] == view]
            .pivot_table(index="sample", columns="feature", values="value")
            .reindex(samples)
            .fillna(0.0)
        )
        scaled = StandardScaler().fit_transform(wide.values)
        blocks.append(scaled)
        feature_index.extend((view, f) for f in wide.columns)

    X = np.hstack(blocks)
    svd = TruncatedSVD(n_components=n_factors, random_state=1)
    Z = svd.fit_transform(X)  # samples x factors
    Wt = svd.components_.T  # features x factors

    factor_cols = [f"Factor{i + 1}" for i in range(n_factors)]
    factors = pd.DataFrame(Z, index=samples, columns=factor_cols)

    weights: dict[str, pd.DataFrame] = {}
    for view in views:
        idx = [i for i, (v, _) in enumerate(feature_index) if v == view]
        feats = [feature_index[i][1] for i in idx]
        weights[view] = pd.DataFrame(Wt[idx, :], index=feats, columns=factor_cols)
    return factors, weights


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-factors", type=int, default=10)
    parser.add_argument("--top-k", type=int, default=15)
    args = parser.parse_args()

    long_df = load_long_data()
    print(
        f"Loaded {len(long_df):,} rows across views: "
        f"{sorted(long_df['view'].unique())}"
    )

    try:
        ent = train_mofa(long_df, n_factors=args.n_factors)
        factors = _factors_from_model(ent)
        weights = _weights_from_model(ent)
        try:
            ent.save(MODEL_PATH)  # persist the trained model for Azure ML output
            print(f"Saved MOFA+ model -> {MODEL_PATH}")
        except Exception as exc:  # noqa: BLE001
            print(f"(model save skipped: {exc})")
    except ImportError:
        factors, weights = train_fallback(long_df, n_factors=args.n_factors)

    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    factors.to_csv(FACTORS_PATH)
    print(f"Wrote factors -> {FACTORS_PATH} ({factors.shape[0]}x{factors.shape[1]})")

    for view, W in weights.items():
        path = os.path.join(WEIGHTS_DIR, f"{view}.csv")
        W.to_csv(path)
        print(f"Wrote weights[{view}] -> {path} ({W.shape[0]}x{W.shape[1]})")

    top = top_features_per_factor(weights, top_k=args.top_k)
    with open(TOPFEAT_PATH, "w") as fh:
        json.dump(top, fh, indent=2)
    print(f"Wrote top features per factor -> {TOPFEAT_PATH}")
    print("Done. Next: python src/hypothesis_agent.py")


if __name__ == "__main__":
    main()
