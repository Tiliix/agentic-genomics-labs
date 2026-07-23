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
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

import requests

try:  # dotenv is optional at import time
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv missing is non-fatal
    pass

# Public, keyless endpoints. These are REAL services.
MYVARIANT_URL = "https://myvariant.info/v1/variant"  # GET /{id}; POST for batches
MYVARIANT_QUERY_URL = "https://myvariant.info/v1/query"  # POST scored batch (rsIDs)
VEP_URL = "https://rest.ensembl.org/vep/human/hgvs"  # GET /{hgvs}; POST for batches
VEP_ID_URL = "https://rest.ensembl.org/vep/human/id"  # GET /{rsid}; POST for batches

ASSEMBLY = os.getenv("MYVARIANT_ASSEMBLY", "hg38")
RATE_LIMIT_S = float(os.getenv("ANNOTATE_RATE_LIMIT_SECONDS", "0.34"))

# Per-request id caps for the POST (batch) endpoints -- public-service maximums.
MYVARIANT_BATCH = 1000  # MyVariant.info accepts up to 1000 ids per POST
VEP_BATCH = 200  # Ensembl VEP accepts up to 200 ids per POST


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


def _compact(value: Any) -> Any:
    """Collapse a repeated per-transcript list to unique values.

    dbNSFP returns one entry per transcript, so ``genename`` / ``sift.pred`` etc.
    often look like ``["HBB", "HBB", ...]``. Returns the single value when they
    all agree, else the list of distinct values -- keeps memos tidy.
    """
    if not isinstance(value, list):
        return value
    seen: list[Any] = []
    for v in value:
        if v not in seen:
            seen.append(v)
    return seen[0] if len(seen) == 1 else seen


def _chunks(seq: list[Any], n: int):
    """Yield successive ``n``-sized chunks from ``seq``."""
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _post_json(url: str, payload: dict[str, Any], timeout: int = 120) -> Any | None:
    """POST ``payload`` as JSON; return the decoded body or ``None`` on error.

    Batch endpoints can be slow for large id lists, hence the generous timeout.
    """
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def _richness(hit: dict[str, Any]) -> int:
    """Rank a MyVariant hit so we can keep the most annotation-rich one.

    An rsID can map to several docs (a bare dbSNP stub next to a fully-curated
    ClinVar record); prefer whichever carries ClinVar and/or gnomAD.
    """
    score = 0
    if hit.get("clinvar"):
        score += 4
    if hit.get("gnomad_exome") or hit.get("gnomad_genome"):
        score += 2
    if hit.get("dbnsfp"):
        score += 1
    return score


def _extract_myvariant_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize the fields the lab uses from a MyVariant.info record."""
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
        "myvariant_id": data.get("_id") if isinstance(data, dict) else None,
        "clinvar_significance": clnsig,
        "clinvar_review_status": _safe_get(data, "clinvar", "rcv", "review_status"),
        "gnomad_af": af,
        # dbNSFP in-silico scores (consumed by the PP3 heuristic in acmg.py).
        "cadd_phred": _safe_get(data, "cadd", "phred"),
        "sift_pred": _compact(_safe_get(data, "dbnsfp", "sift", "pred")),
        "polyphen_pred": _compact(
            _safe_get(data, "dbnsfp", "polyphen2", "hdiv", "pred")
        ),
        "gene": _compact(
            _safe_get(data, "dbnsfp", "genename")
            or _safe_get(data, "clinvar", "gene", "symbol")
        ),
        "_raw_keys": sorted(data.keys()) if isinstance(data, dict) else [],
    }


def _myvariant_by_rsid(rsid: str, assembly: str) -> dict[str, Any] | None:
    """Resolve the best MyVariant.info record via dbSNP rsID.

    An rsID can map to several documents (different ALT alleles, or a bare dbSNP
    stub alongside a fully-curated ClinVar record). We fetch the top hits and
    pick the richest one -- preferring a record that carries ClinVar and/or
    gnomAD -- so we never return an annotation-less stub. Works for indels/dups,
    not just SNVs. Returns None if nothing matched / the call failed.
    """
    try:
        resp = requests.get(
            "https://myvariant.info/v1/query",
            params={
                "q": f"dbsnp.rsid:{rsid}",
                "assembly": assembly,
                "fields": "all",
                "size": 10,
            },
            timeout=30,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
    except (requests.RequestException, ValueError):
        return None
    if not hits:
        return None
    # max() keeps the first (highest dbSNP score) among equally-rich hits.
    return max(hits, key=_richness)


def _myvariant_by_hgvs(hgvs_id: str, assembly: str) -> dict[str, Any] | None:
    """Resolve a MyVariant.info record via genomic HGVS id (SNVs)."""
    try:
        resp = requests.get(
            f"{MYVARIANT_URL}/{hgvs_id}", params={"assembly": assembly}, timeout=30
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def query_myvariant(variant: Variant, assembly: str = ASSEMBLY) -> dict[str, Any]:
    """Query MyVariant.info for one variant and normalize key fields.

    Prefers a dbSNP rsID lookup when the VCF supplies one (reliable, and it works
    for indels/dups, not just SNVs); falls back to the genomic HGVS id otherwise.
    """
    data: dict[str, Any] | None = None
    if variant.rsid and variant.rsid.startswith("rs"):
        data = _myvariant_by_rsid(variant.rsid, assembly)
    if data is None:
        data = _myvariant_by_hgvs(variant.hgvs_id, assembly)
    if not isinstance(data, dict):
        return {"found": False}
    return _extract_myvariant_fields(data)


def _vep_hgvs(variant: Variant) -> str:
    """Ensembl VEP HGVS notation for a SNV, e.g. ``17:g.43045712C>T`` (no 'chr')."""
    chrom = variant.chrom[3:] if variant.chrom.startswith("chr") else variant.chrom
    return f"{chrom}:g.{variant.pos}{variant.ref}>{variant.alt}"


def _vep_fields(rec: dict[str, Any]) -> dict[str, Any]:
    """Pull the most-severe consequence + gene symbol from one VEP record."""
    return {
        "most_severe_consequence": rec.get("most_severe_consequence"),
        "vep_gene_symbol": _safe_get(rec, "transcript_consequences", "gene_symbol"),
    }


def query_vep(variant: Variant) -> dict[str, Any]:
    """Query Ensembl VEP REST for the most-severe consequence term.

    Uses the dbSNP rsID endpoint when the VCF supplies one (robust for indels),
    otherwise the genomic HGVS endpoint. Errors degrade gracefully to ``{}`` so
    the lab still runs if VEP is unreachable.
    """
    if variant.rsid and variant.rsid.startswith("rs"):
        endpoint = f"{VEP_ID_URL}/{variant.rsid}"
    else:
        endpoint = f"{VEP_URL}/{_vep_hgvs(variant)}"
    try:
        resp = requests.get(
            endpoint,
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
    return _vep_fields(data[0])


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


# --------------------------------------------------------------------------- #
# Batch annotation -- scales to large VCFs (thousands of variants)
# --------------------------------------------------------------------------- #
def batch_myvariant(
    variants: list[Variant], assembly: str = ASSEMBLY
) -> list[dict[str, Any]]:
    """Annotate many variants with MyVariant.info via batched POST requests.

    Two passes keep the request count tiny for large VCFs:

      1. Variants carrying a dbSNP rsID are resolved in bulk through the scored
         ``/query`` endpoint (``scopes=dbsnp.rsid``), up to
         :data:`MYVARIANT_BATCH` ids per call. When an rsID maps to several docs
         we keep the richest (ClinVar/gnomAD-bearing) hit -- same rule as the
         single-variant path.
      2. Anything still unresolved (no rsID, or an rsID that missed) falls back
         to the genomic-HGVS ``/variant`` batch endpoint.

    Returns a list aligned 1:1 with ``variants`` (``{"found": False}`` on miss).
    """
    results: list[dict[str, Any] | None] = [None] * len(variants)

    # Pass 1 -- rsID bulk lookup via the scored /query endpoint.
    rs_idx = [i for i, v in enumerate(variants) if v.rsid.startswith("rs")]
    for chunk in _chunks(rs_idx, MYVARIANT_BATCH):
        payload = {
            "q": [variants[i].rsid for i in chunk],
            "scopes": "dbsnp.rsid",
            "fields": "all",
            "assembly": assembly,
            "size": 10,
        }
        data = _post_json(MYVARIANT_QUERY_URL, payload)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if isinstance(data, list):
            for rec in data:
                q = rec.get("query")
                if q and not rec.get("notfound"):
                    grouped[q].append(rec)
        for i in chunk:
            hits = grouped.get(variants[i].rsid)
            if hits:
                results[i] = _extract_myvariant_fields(max(hits, key=_richness))

    # Pass 2 -- genomic-HGVS fallback via the /variant endpoint.
    id_to_idx: dict[str, list[int]] = defaultdict(list)
    for i, v in enumerate(variants):
        if results[i] is None:
            id_to_idx[v.hgvs_id].append(i)
    for chunk_ids in _chunks(list(id_to_idx), MYVARIANT_BATCH):
        data = _post_json(MYVARIANT_URL, {"ids": chunk_ids, "assembly": assembly})
        if isinstance(data, list):
            for rec in data:
                if rec.get("notfound"):
                    continue
                for i in id_to_idx.get(rec.get("query"), []):
                    results[i] = _extract_myvariant_fields(rec)

    return [r if r is not None else {"found": False} for r in results]


def batch_vep(variants: list[Variant]) -> list[dict[str, Any]]:
    """Annotate many variants with Ensembl VEP via batched POST requests.

    rsID-bearing variants go to ``POST /vep/human/id``; the rest to
    ``POST /vep/human/hgvs`` (:data:`VEP_BATCH` ids per call). VEP echoes each
    query in the record's ``input`` field, which we use to realign the response
    to the input order. Returns a list aligned 1:1 with ``variants`` (``{}`` on
    miss or if the service is unreachable).
    """
    results: list[dict[str, Any]] = [{} for _ in variants]

    # Pass 1 -- rsIDs via /vep/human/id.
    rs_idx = [i for i, v in enumerate(variants) if v.rsid.startswith("rs")]
    for chunk in _chunks(rs_idx, VEP_BATCH):
        data = _post_json(VEP_ID_URL, {"ids": [variants[i].rsid for i in chunk]})
        by_input = {
            rec["input"]: rec
            for rec in (data or [])
            if isinstance(rec, dict) and rec.get("input")
        }
        for i in chunk:
            rec = by_input.get(variants[i].rsid)
            if rec:
                results[i] = _vep_fields(rec)

    # Pass 2 -- HGVS notations via /vep/human/hgvs for anything still empty.
    id_to_idx: dict[str, list[int]] = defaultdict(list)
    for i, v in enumerate(variants):
        if not results[i]:
            id_to_idx[_vep_hgvs(v)].append(i)
    for chunk_ids in _chunks(list(id_to_idx), VEP_BATCH):
        data = _post_json(VEP_URL, {"hgvs_notations": chunk_ids})
        if isinstance(data, list):
            for rec in data:
                if isinstance(rec, dict) and rec.get("input"):
                    for i in id_to_idx.get(rec["input"], []):
                        results[i] = _vep_fields(rec)

    return results


def annotate_vcf(
    path: str, use_vep: bool = True, assembly: str = ASSEMBLY
) -> list[dict[str, Any]]:
    """Annotate every variant in a VCF using batched POST requests.

    Scales to large VCFs: rather than two GET calls per variant, the whole file
    is resolved in a handful of POSTs (MyVariant up to :data:`MYVARIANT_BATCH`,
    VEP up to :data:`VEP_BATCH` ids each). A 50k-variant VCF becomes ~50
    MyVariant + ~250 VEP requests instead of ~100k. The per-variant
    :func:`annotate_variant` path is retained for the agent's single-variant
    tool.
    """
    variants = parse_vcf(path)
    if not variants:
        return []

    myvariant = batch_myvariant(variants, assembly=assembly)
    if use_vep:
        time.sleep(RATE_LIMIT_S)  # small pause between the two public services
        vep = batch_vep(variants)
    else:
        vep = [{} for _ in variants]

    out: list[dict[str, Any]] = []
    for v, mv, ann in zip(variants, myvariant, vep):
        record: dict[str, Any] = {
            "variant": asdict(v),
            "hgvs_id": v.hgvs_id,
            "sources": ["MyVariant.info (ClinVar, gnomAD, dbNSFP)"],
        }
        record.update(mv)
        if use_vep and ann:
            record.update(ann)
            record["sources"].append("Ensembl VEP REST")
        out.append(record)
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
