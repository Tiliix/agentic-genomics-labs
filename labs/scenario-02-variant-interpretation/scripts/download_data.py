#!/usr/bin/env python3
"""Fetch a small public VCF subset for the variant-interpretation lab.

The lab ships with a tiny bundled VCF at ``data/example.vcf`` (a handful of
well-known variants such as BRCA1) so it runs even offline. This script can
additionally pull a *small subset* of a real public callset:

  * Genome in a Bottle (GIAB) NA12878 / HG001 high-confidence small-variant VCF
  * 1000 Genomes Project phase-3 release

The full files are large, so by default we stream only the header + the first
chunk of records and write a truncated, valid VCF you can experiment with. Use
``--full`` to download the entire (large) file instead.

RESEARCH / EDUCATION ONLY -- not for clinical use.
"""
from __future__ import annotations

import argparse
import gzip
import io
import sys
from pathlib import Path

import requests

# Real, public, stable URLs (GRCh38 / hg38).
SOURCES = {
    # GIAB NA12878 (HG001) high-confidence small variants, GRCh38.
    "giab": (
        "https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/"
        "NA12878_HG001/latest/GRCh38/"
        "HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz"
    ),
    # 1000 Genomes phase-3, chromosome 22 (smallest autosome), GRCh38 liftover.
    "1000g_chr22": (
        "http://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/"
        "1000_genomes_project/release/20190312_biallelic_SNV_and_INDEL/"
        "ALL.chr22.shapeit2_integrated_snvindels_v2a_27022019.GRCh38.phased.vcf.gz"
    ),
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_MAX_RECORDS = 200


def list_sources() -> None:
    print("Available public VCF sources:\n")
    for name, url in SOURCES.items():
        print(f"  {name:14s} {url}")
    print(
        "\nThe bundled tiny example is already at data/example.vcf "
        "(works offline)."
    )


def download_subset(source: str, max_records: int, out: Path) -> None:
    """Stream a gzip VCF and keep header + first ``max_records`` data lines."""
    url = SOURCES[source]
    print(f"Streaming {source} from:\n  {url}")
    out.parent.mkdir(parents=True, exist_ok=True)

    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()

    # Decompress on the fly; stop once we have enough records.
    raw = io.BufferedReader(resp.raw)  # type: ignore[arg-type]
    gz = gzip.GzipFile(fileobj=raw)
    kept = 0
    with open(out, "w", encoding="utf-8") as fh:
        for bline in gz:
            line = bline.decode("utf-8", errors="replace")
            if line.startswith("#"):
                fh.write(line)
                continue
            if kept >= max_records:
                break
            fh.write(line)
            kept += 1
    print(f"Wrote {kept} records (+ header) -> {out}")


def download_full(source: str, out: Path) -> None:
    """Download the entire (large) gzip VCF to disk."""
    url = SOURCES[source]
    out = out.with_suffix(out.suffix + ".gz") if out.suffix != ".gz" else out
    print(f"Downloading FULL file (large!) from:\n  {url}")
    out.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, stream=True, timeout=600)
    resp.raise_for_status()
    with open(out, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            fh.write(chunk)
    print(f"Wrote {out} -- gunzip before annotating.")


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--source",
        choices=sorted(SOURCES),
        default="giab",
        help="which public callset to subset (default: %(default)s)",
    )
    ap.add_argument(
        "--max-records",
        type=int,
        default=DEFAULT_MAX_RECORDS,
        help="number of data lines to keep when subsetting (default: %(default)s)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DATA_DIR / "giab_subset.vcf",
        help="output VCF path (default: %(default)s)",
    )
    ap.add_argument(
        "--full", action="store_true", help="download the entire large file"
    )
    ap.add_argument(
        "--list", action="store_true", help="just print the source URLs and exit"
    )
    args = ap.parse_args(argv)

    if args.list:
        list_sources()
        return 0

    try:
        if args.full:
            download_full(args.source, args.out)
        else:
            download_subset(args.source, args.max_records, args.out)
    except requests.RequestException as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        print(
            "No internet? The bundled data/example.vcf works offline.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
