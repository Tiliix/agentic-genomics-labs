"""Generate the synthetic ground-truth table and document the real datasets.

Offline-safe: this script does NOT download anything by default. It WRITES the
synthetic ground-truth CSV that the screen simulator reads, and prints the URLs
for the real public Perturb-seq / CRISPR screen datasets you can wire in later.

Usage:
    python scripts/download_data.py            # write synthetic table
    python scripts/download_data.py --urls     # just print dataset URLs
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

# Make src importable when run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from screen_env import GROUND_TRUTH_CSV, synthetic_rows  # noqa: E402


# Real public datasets for when you replace the simulator with a real readout.
REAL_DATASETS = {
    "Norman et al. 2019 (Perturb-seq, GI map, K562)": [
        "Paper: https://www.science.org/doi/10.1126/science.aax4438",
        "GEO: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE133344",
        "Processed (scPerturb): https://scperturb.org/",
    ],
    "Adamson et al. 2016 (Perturb-seq, UPR, K562)": [
        "Paper: https://doi.org/10.1016/j.cell.2016.11.048",
        "GEO: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE90546",
    ],
    "Replogle et al. 2022 (genome-wide Perturb-seq)": [
        "Paper: https://doi.org/10.1016/j.cell.2022.05.013",
        "Data: https://gwps.wi.mit.edu/",
    ],
    "GEARS (perturbation-outcome prediction model)": [
        "Code: https://github.com/snap-stanford/GEARS",
        "Paper: https://www.nature.com/articles/s41587-023-01905-6",
    ],
    "BioDiscoveryAgent (reference agent pattern)": [
        "Code: https://github.com/snap-stanford/BioDiscoveryAgent",
        "Paper: https://arxiv.org/abs/2405.17631",
    ],
}


def print_urls() -> None:
    print("Real public datasets / references (download separately, needs internet):\n")
    for name, links in REAL_DATASETS.items():
        print(f"  {name}")
        for link in links:
            print(f"      - {link}")
        print()
    print(
        "To use real data: parse a screen hit list into a CSV with columns\n"
        "  gene,pathway,true_effect,essential\n"
        "and point screen_env.GROUND_TRUTH_CSV at it. The agent loop is\n"
        "data-source agnostic."
    )


def write_synthetic(path: str = GROUND_TRUTH_CSV, seed: int = 7) -> str:
    """Write the pathway-clustered synthetic ground-truth table to ``path``."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = synthetic_rows(seed=seed)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["gene", "pathway", "true_effect", "essential"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--urls", action="store_true", help="Only print real dataset URLs."
    )
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    if args.urls:
        print_urls()
        return

    path = write_synthetic(seed=args.seed)
    n = len(synthetic_rows(seed=args.seed))
    print(f"Wrote synthetic ground-truth table: {path} ({n} genes)")
    print("Columns: gene, pathway, true_effect, essential\n")
    print_urls()


if __name__ == "__main__":
    main()
