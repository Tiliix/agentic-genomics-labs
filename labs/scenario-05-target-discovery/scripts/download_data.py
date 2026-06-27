"""Snapshot Open Targets associations for a disease into data/ as JSON.

Live path:
    python scripts/download_data.py --efo EFO_0001360 --size 25

If the API is unreachable (e.g. no internet in this container), the script falls
back to a small bundled snapshot so downstream steps still run. The bundled data
is illustrative only — re-run with internet for real, current numbers.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Allow running as a plain script (python scripts/download_data.py) by putting the
# repo root on sys.path so `from src...` resolves.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.opentargets import associated_targets  # noqa: E402

DATA_DIR = os.path.join(_REPO_ROOT, "data")

# Small offline fallback for the worked example (type 2 diabetes, EFO_0001360).
# Numbers are representative, not authoritative — they let the lab run with no network.
FALLBACK: dict[str, dict] = {
    "EFO_0001360": {
        "disease": {"id": "EFO_0001360", "name": "type 2 diabetes mellitus"},
        "count": 5,
        "_note": "BUNDLED FALLBACK — illustrative scores, re-run online for real data.",
        "targets": [
            {
                "ensemblId": "ENSG00000132170",
                "symbol": "PPARG",
                "name": "peroxisome proliferator activated receptor gamma",
                "biotype": "protein_coding",
                "overallScore": 0.91,
                "datatypeScores": {
                    "genetic_association": 0.88,
                    "known_drug": 0.95,
                    "affected_pathway": 0.70,
                    "rna_expression": 0.40,
                    "literature": 0.80,
                },
            },
            {
                "ensemblId": "ENSG00000254647",
                "symbol": "INS",
                "name": "insulin",
                "biotype": "protein_coding",
                "overallScore": 0.86,
                "datatypeScores": {
                    "genetic_association": 0.75,
                    "known_drug": 0.90,
                    "literature": 0.85,
                    "rna_expression": 0.50,
                },
            },
            {
                "ensemblId": "ENSG00000186951",
                "symbol": "PPARA",
                "name": "peroxisome proliferator activated receptor alpha",
                "biotype": "protein_coding",
                "overallScore": 0.62,
                "datatypeScores": {
                    "genetic_association": 0.55,
                    "known_drug": 0.60,
                    "affected_pathway": 0.45,
                },
            },
            {
                "ensemblId": "ENSG00000174697",
                "symbol": "LEP",
                "name": "leptin",
                "biotype": "protein_coding",
                "overallScore": 0.58,
                "datatypeScores": {
                    "genetic_association": 0.62,
                    "literature": 0.70,
                    "rna_expression": 0.30,
                },
            },
            {
                "ensemblId": "ENSG00000169174",
                "symbol": "PCSK9",
                "name": "proprotein convertase subtilisin/kexin type 9",
                "biotype": "protein_coding",
                "overallScore": 0.41,
                "datatypeScores": {
                    "genetic_association": 0.66,
                    "known_drug": 0.30,
                    "literature": 0.40,
                },
            },
        ],
    }
}


def snapshot(efo_id: str, size: int) -> dict:
    """Try the live API; on any failure return the bundled fallback if available."""
    try:
        print(f"Fetching live associations for {efo_id} (size={size}) ...")
        result = associated_targets(efo_id, size=size)
        result["_source"] = "live"
        return result
    except Exception as exc:  # network down, DNS blocked, API change, etc.
        print(f"Live fetch failed ({type(exc).__name__}: {exc}).", file=sys.stderr)
        if efo_id in FALLBACK:
            print("Using bundled fallback snapshot.", file=sys.stderr)
            data = dict(FALLBACK[efo_id])
            data["_source"] = "fallback"
            return data
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot Open Targets associations.")
    parser.add_argument("--efo", default="EFO_0001360", help="EFO disease id.")
    parser.add_argument("--size", type=int, default=25, help="Number of targets.")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    data = snapshot(args.efo, args.size)

    out_path = os.path.join(DATA_DIR, f"associations_{args.efo}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    print(
        f"Wrote {len(data['targets'])} targets "
        f"(source={data.get('_source')}) -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
