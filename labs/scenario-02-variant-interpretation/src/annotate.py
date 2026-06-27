#!/usr/bin/env python3
"""Annotate a VCF against public knowledgebases.

For each variant in a (small) VCF this module:

  1. Parses the VCF with a tiny dependency-free plain-text parser. We avoid
     pysam/cyvcf2 so the lab needs no C build step. This handles uncompressed
     ``.vcf`` text; for ``.vcf.gz`` just gunzip first.
  2. Queries **MyVariant.info** (https://myvariant.info, no API key) which
     aggregates ClinVar and gnomAD, pulling out:
       - ClinVar clinical significance + review status
       - gnomAD exome/genome allele frequency
       - dbNSFP in-silico predictions (used later by the ACMG PP3 heuristic)
  3. (Optionally) queries the **Ensembl VEP REST API**
     (https://rest.ensembl.org) for the most-severe consequence term, which the
     ACMG PVS1 heuristic uses to spot likely loss-of-function variants.

The output is a list of normalized dicts (also writable as JSON) consumed by
``acmg.py`` and ``agent.py``.

RESEARCH / EDUCATION ONLY -- not for clinical use.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import requests

try:  # dotenv is optional at import time
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv missing is non-fatal
    pass

# Public, keyless endpoints. These are REAL services.
MYVARIANT_URL = "https://myvariant.info/v1/variant"
VEP_URL = "https://rest.ensembl.org/vep/human/hgvs"

ASSEMBLY = os.getenv("MYVARIANT_ASSEMBLY", "hg38")
RATE_LIMIT_S = float(os.getenv("ANNOTATE_RATE_LIMIT_SECONDS", "0.34"))


# --------------------------------------------------------------------------- #
# VCF parsing
# --------------------------------------------------------------------------- #
@dataclass
class Variant:
    """A minimal representation of one VCF record (first ALT allele)."""

    chrom: str
    pos: int
    ref: str
    alt: str
    rsid: str = "."
    info: dict[str, str] = field(default_factory=dict)

    @property
    def hgvs_id(self) -> str:
        """MyVariant.info chrom-based id, e.g. ``chr17:g.43045712C>T``.

        MyVariant accepts this "g." HGVS-style genomic key for SNVs. The chrom
        is normalized to include the ``chr`` prefix.
        """
        chrom = self.chrom if self.chrom.startswith("chr") else f"chr{self.chrom}"
        return f"{chrom}:g.{self.pos}{self.ref}>{self.alt}"


def parse_vcf(path: str) -> list[Variant]:
    """Parse an uncompressed VCF into a list of :class:`Variant`.

    Only the first ALT allele of each record is kept (sufficient for the lab).
    Header/comment lines (starting with ``#``) are skipped.
    """
    variants: list[Variant] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 5:
                # Tolerate space-delimited toy files too.
                cols = line.split()
            if len(cols) < 5:
                continue
            chrom, pos, vid, ref, alt = cols[0], cols[1], cols[2], cols[3], cols[4]
            info: dict[str, str] = {}
            if len(cols) >= 8 and cols[7] not in (".", ""):
                for kv in cols[7].split(";"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        info[k] = v
                    else:
                        info[kv] = "True"
            variants.append(
                Variant(
                    chrom=chrom,
                    pos=int(pos),
                    ref=ref,
                    alt=alt.split(",")[0],  # first ALT only
                    rsid=vid,
                    info=info,
                )
            )
    return variants


# --------------------------------------------------------------------------- #
# Annotation
# --------------------------------------------------------------------------- #
def _safe_get(d: Any, *keys: str, default: Any = None) -> Any:
    """Walk nested dict keys, returning ``default`` if any are missing."""
    cur = d
    for k in keys:
        if isinstance(cur, list):  # MyVariant sometimes returns lists
            cur = cur[0] if cur else None
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def query_myvariant(variant: Variant, assembly: str = ASSEMBLY) -> dict[str, Any]:
    """Query MyVariant.info for one variant and normalize key fields."""
    url = f"{MYVARIANT_URL}/{variant.hgvs_id}"
    params = {"assembly": assembly}
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 404:
            return {"found": False}
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:  # network/HTTP error -> degrade
        return {"found": False, "error": str(exc)}

    # ClinVar significance can be a str or list depending on submissions.
    clnsig = _safe_get(data, "clinvar", "rcv", "clinical_significance")
    if isinstance(clnsig, list):
        clnsig = ", ".join(sorted({str(x) for x in clnsig}))

    # gnomAD allele frequency: prefer exome, fall back to genome.
    af = _safe_get(data, "gnomad_exome", "af", "af")
    if af is None:
        af = _safe_get(data, "gnomad_genome", "af", "af")

    return {
        "found": True,
        "clinvar_significance": clnsig,
        "clinvar_review_status": _safe_get(data, "clinvar", "rcv", "review_status"),
        "gnomad_af": af,
        # dbNSFP in-silico scores (consumed by the PP3 heuristic in acmg.py).
        "cadd_phred": _safe_get(data, "cadd", "phred"),
        "sift_pred": _safe_get(data, "dbnsfp", "sift", "pred"),
        "polyphen_pred": _safe_get(data, "dbnsfp", "polyphen2", "hdiv", "pred"),
        "gene": _safe_get(data, "dbnsfp", "genename")
        or _safe_get(data, "clinvar", "gene", "symbol"),
        "_raw_keys": sorted(data.keys()) if isinstance(data, dict) else [],
    }


def query_vep(variant: Variant) -> dict[str, Any]:
    """Query Ensembl VEP REST for the most-severe consequence term.

    Uses the genomic HGVS endpoint. Errors degrade gracefully to ``{}`` so the
    lab still runs if VEP is unreachable.
    """
    # Ensembl VEP HGVS endpoint expects e.g. 17:g.43045712C>T (no 'chr').
    chrom = variant.chrom[3:] if variant.chrom.startswith("chr") else variant.chrom
    hgvs = f"{chrom}:g.{variant.pos}{variant.ref}>{variant.alt}"
    try:
        resp = requests.get(
            f"{VEP_URL}/{hgvs}",
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
    except requests.RequestException:
        return {}
    if not isinstance(data, list) or not data:
        return {}
    rec = data[0]
    return {
        "most_severe_consequence": rec.get("most_severe_consequence"),
        "vep_gene_symbol": _safe_get(
            rec, "transcript_consequences", "gene_symbol"
        ),
    }


def annotate_variant(
    variant: Variant, use_vep: bool = True, assembly: str = ASSEMBLY
) -> dict[str, Any]:
    """Combine MyVariant + (optional) VEP annotations for one variant."""
    record: dict[str, Any] = {
        "variant": asdict(variant),
        "hgvs_id": variant.hgvs_id,
        "sources": ["MyVariant.info (ClinVar, gnomAD, dbNSFP)"],
    }
    record.update(query_myvariant(variant, assembly=assembly))
    if use_vep:
        vep = query_vep(variant)
        if vep:
            record.update(vep)
            record["sources"].append("Ensembl VEP REST")
    return record


def annotate_vcf(
    path: str, use_vep: bool = True, assembly: str = ASSEMBLY
) -> list[dict[str, Any]]:
    """Annotate every variant in a VCF, rate-limiting public API calls."""
    variants = parse_vcf(path)
    out: list[dict[str, Any]] = []
    for i, v in enumerate(variants):
        if i:
            time.sleep(RATE_LIMIT_S)  # be polite to public endpoints
        out.append(annotate_variant(v, use_vep=use_vep, assembly=assembly))
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("vcf", help="path to an (uncompressed) VCF file")
    ap.add_argument("--out", help="write annotations as JSON to this path")
    ap.add_argument(
        "--no-vep", action="store_true", help="skip the Ensembl VEP REST call"
    )
    ap.add_argument(
        "--assembly", default=ASSEMBLY, help="hg19 or hg38 (default: %(default)s)"
    )
    args = ap.parse_args(argv)

    records = annotate_vcf(
        args.vcf, use_vep=not args.no_vep, assembly=args.assembly
    )
    text = json.dumps(records, indent=2, default=str)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Wrote {len(records)} annotated variants -> {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
