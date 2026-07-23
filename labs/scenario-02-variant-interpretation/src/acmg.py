#!/usr/bin/env python3
"""A transparent, SIMPLIFIED ACMG/AMP-style variant classification engine.

==============================  IMPORTANT  ==================================
This is an EDUCATIONAL SUBSET, not the full ACMG/AMP 2015 framework.

The real framework (Richards et al., 2015, Genet Med) defines 28 criteria
(PVS1, PS1-4, PM1-6, PP1-5 for pathogenic; BA1, BS1-4, BP1-7 for benign) and a
combining rule table. Proper application requires curated evidence, segregation
data, functional studies, and expert judgment -- typically by a clinical lab.

Here we implement only a handful of *heuristic* criteria that can be derived
from the automated annotations in annotate.py:

    PVS1  (very strong, pathogenic) -- null variant in a gene where LoF is a
            known disease mechanism. HEURISTIC: most-severe consequence is a
            stop-gain / frameshift / splice-donor/acceptor term.
    PM2   (moderate, pathogenic)    -- absent / extremely rare in gnomAD.
            HEURISTIC: gnomAD AF is None or < 0.0001.
    PP3   (supporting, pathogenic)  -- multiple in-silico tools predict damage.
            HEURISTIC: CADD phred >= 20, or SIFT "D", or PolyPhen "D"/"P".
    PP5   (supporting, pathogenic)  -- reputable source (ClinVar) reports it
            pathogenic. (NOTE: PP5/BP6 were deprecated by later guidance; kept
            here only as a teaching signal.)
    BA1   (stand-alone, benign)     -- gnomAD AF > 0.05.
    BS1   (strong, benign)          -- gnomAD AF > 0.01 (greater than expected
            for the disorder). HEURISTIC threshold only.
    BP6   (supporting, benign)      -- ClinVar reports it benign. (deprecated;
            teaching signal only.)

Classification combining below is a SIMPLIFIED reading of the ACMG rules.

RESEARCH / EDUCATION ONLY -- not for clinical use.
============================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any

# Consequence terms (Sequence Ontology) treated as putative loss-of-function.
LOF_TERMS = {
    "transcript_ablation",
    "splice_acceptor_variant",
    "splice_donor_variant",
    "stop_gained",
    "frameshift_variant",
    "start_lost",
    "stop_lost",
}

# Allele-frequency thresholds (illustrative, NOT disease-calibrated).
PM2_MAX_AF = 1e-4
BS1_MIN_AF = 1e-2
BA1_MIN_AF = 5e-2
PP3_CADD_MIN = 20.0


@dataclass
class CriterionHit:
    """One ACMG criterion that fired, with the evidence behind it."""

    code: str          # e.g. "PM2"
    direction: str     # "pathogenic" or "benign"
    strength: str      # very_strong | strong | moderate | supporting | stand_alone
    rationale: str


@dataclass
class Classification:
    """Result of running the rule engine on a single annotated variant."""

    hgvs_id: str
    classification: str
    criteria: list[CriterionHit] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "hgvs_id": self.hgvs_id,
            "classification": self.classification,
            "criteria": [c.__dict__ for c in self.criteria],
            "rationale": self.rationale,
        }


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pred_codes(value: Any) -> list[str]:
    """Normalize a SIFT/PolyPhen prediction to upper-case codes.

    MyVariant.info returns these as a single string OR a per-transcript list, so
    we coerce both into a list of codes (e.g. ["D"], ["D", "T"]).
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).upper() for v in value if v not in (None, "")]
    return [str(value).upper()]


def evaluate(annotation: dict[str, Any]) -> Classification:
    """Apply the simplified criteria to one annotation dict from annotate.py."""
    hits: list[CriterionHit] = []

    af = _as_float(annotation.get("gnomad_af"))
    consequence = (annotation.get("most_severe_consequence") or "").lower()
    clnsig = (annotation.get("clinvar_significance") or "").lower()

    # --- Pathogenic-direction criteria ------------------------------------ #
    if consequence in LOF_TERMS:
        hits.append(
            CriterionHit(
                "PVS1",
                "pathogenic",
                "very_strong",
                f"Predicted loss-of-function: most-severe consequence is "
                f"'{consequence}'.",
            )
        )

    if af is None or af < PM2_MAX_AF:
        rare = "absent from gnomAD" if af is None else f"gnomAD AF={af:.2e}"
        hits.append(
            CriterionHit(
                "PM2",
                "pathogenic",
                "moderate",
                f"Rare/absent in population databases ({rare} < {PM2_MAX_AF:.0e}).",
            )
        )

    cadd = _as_float(annotation.get("cadd_phred"))
    sift_codes = _pred_codes(annotation.get("sift_pred"))
    polyphen_codes = _pred_codes(annotation.get("polyphen_pred"))
    sift_damaging = any(c.startswith("D") for c in sift_codes)
    polyphen_damaging = any(c.startswith(("D", "P")) for c in polyphen_codes)
    insilico_damaging = (
        (cadd is not None and cadd >= PP3_CADD_MIN)
        or sift_damaging
        or polyphen_damaging
    )
    if insilico_damaging:
        details = []
        if cadd is not None:
            details.append(f"CADD={cadd:.1f}")
        if sift_codes:
            details.append("SIFT=" + ",".join(sorted(set(sift_codes))))
        if polyphen_codes:
            details.append("PolyPhen=" + ",".join(sorted(set(polyphen_codes))))
        hits.append(
            CriterionHit(
                "PP3",
                "pathogenic",
                "supporting",
                "Multiple in-silico predictors suggest a deleterious effect ("
                + ", ".join(details)
                + ").",
            )
        )

    if "pathogenic" in clnsig and "conflicting" not in clnsig:
        hits.append(
            CriterionHit(
                "PP5",
                "pathogenic",
                "supporting",
                f"ClinVar reports '{annotation.get('clinvar_significance')}' "
                "(PP5 is deprecated; teaching signal only).",
            )
        )

    # --- Benign-direction criteria ---------------------------------------- #
    if af is not None and af > BA1_MIN_AF:
        hits.append(
            CriterionHit(
                "BA1",
                "benign",
                "stand_alone",
                f"Common in gnomAD (AF={af:.3f} > {BA1_MIN_AF}); stand-alone "
                "benign evidence.",
            )
        )
    elif af is not None and af > BS1_MIN_AF:
        hits.append(
            CriterionHit(
                "BS1",
                "benign",
                "strong",
                f"gnomAD AF={af:.3f} greater than expected for a rare disorder "
                f"(> {BS1_MIN_AF}).",
            )
        )

    if "benign" in clnsig and "conflicting" not in clnsig:
        hits.append(
            CriterionHit(
                "BP6",
                "benign",
                "supporting",
                f"ClinVar reports '{annotation.get('clinvar_significance')}' "
                "(BP6 is deprecated; teaching signal only).",
            )
        )

    classification, rationale = _combine(hits)
    return Classification(
        hgvs_id=annotation.get("hgvs_id", "?"),
        classification=classification,
        criteria=hits,
        rationale=rationale,
    )


def _combine(hits: list[CriterionHit]) -> tuple[str, str]:
    """Combine fired criteria into a single category.

    This is a SIMPLIFIED reading of the ACMG/AMP combining rules. We weight by
    strength per direction and resolve conflicts conservatively to VUS.
    """
    weights = {
        "stand_alone": 8,
        "very_strong": 8,
        "strong": 4,
        "moderate": 2,
        "supporting": 1,
    }
    path_score = sum(weights[h.strength] for h in hits if h.direction == "pathogenic")
    benign_score = sum(weights[h.strength] for h in hits if h.direction == "benign")

    codes = ", ".join(h.code for h in hits) or "none"

    # Stand-alone / very-strong benign (BA1) dominates per ACMG.
    if any(h.code == "BA1" for h in hits):
        return "Benign", f"BA1 stand-alone benign evidence present. Criteria: {codes}."

    # Conflicting strong evidence on both sides -> VUS.
    if path_score >= 4 and benign_score >= 4:
        return (
            "Uncertain significance (VUS)",
            f"Conflicting strong evidence (path={path_score}, benign={benign_score}). "
            f"Criteria: {codes}.",
        )

    if path_score >= 8:
        cat = "Pathogenic"
    elif path_score >= 4:
        cat = "Likely pathogenic"
    elif benign_score >= 4:
        cat = "Likely benign"
    elif path_score == 0 and benign_score == 0:
        cat = "Uncertain significance (VUS)"
    elif benign_score > path_score:
        cat = "Likely benign"
    else:
        cat = "Uncertain significance (VUS)"

    return (
        cat,
        f"Simplified combine: pathogenic weight={path_score}, benign weight="
        f"{benign_score}. Criteria fired: {codes}.",
    )


def classify_all(annotations: list[dict[str, Any]]) -> list[Classification]:
    return [evaluate(a) for a in annotations]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Simplified ACMG/AMP rule engine.")
    ap.add_argument(
        "annotations", help="JSON file produced by annotate.py (a list of dicts)"
    )
    args = ap.parse_args(argv)

    with open(args.annotations, encoding="utf-8") as fh:
        annotations = json.load(fh)
    if isinstance(annotations, dict):
        annotations = [annotations]

    results = [c.to_dict() for c in classify_all(annotations)]
    print(json.dumps(results, indent=2))
    print(
        "\n[NOTE] Simplified educational subset of ACMG/AMP -- NOT for clinical use.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_main())
