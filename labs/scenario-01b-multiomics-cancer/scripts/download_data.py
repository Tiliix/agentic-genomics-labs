"""Restore or fetch Lab 1-b cases: synthetic teaching fixtures vs real TCGA-BRCA."""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CBIOPORTAL_BASE = "https://www.cbioportal.org/api"
TCGA_STUDY = "brca_tcga_pan_can_atlas_2018"

DATA_SOURCE_DIFFERENCE = (
    "Synthetic data (`synthetic`) uses hand-authored 24-gene teaching dicts with clean "
    "round numbers, zero background noise, and no network download required; "
    "Real study data (`real`) uses actual de-identified TCGA-BRCA PanCanAtlas tumors "
    "(TCGA-A2-A3XV-01, TCGA-AO-A0J4-01, TCGA-D8-A1XV-01) with continuous log2(RSEM+1) "
    "expression vs. TCGA solid-tissue normals, real co-occurring CNAs/mutations, "
    "realistic breast-cancer TMB (0.66-2.66 mut/Mb), and genuine HM450 methylation "
    "platform absence on TCGA-AO-A0J4-01."
)

EXPR_GENES = [
    "ESR1", "PGR", "ERBB2", "MKI67", "EGFR", "MYC", "GATA3", "FOXA1",
    "KRT5", "KRT14", "GZMA", "PRF1", "IFNG", "CD8A", "CXCL9", "BRCA1",
    "BRCA2", "TP53", "PIK3CA", "PTEN", "RB1", "CCND1", "ACTB", "GAPDH",
]
CNA_GENES = ["ERBB2", "MYC", "CCND1", "TP53", "PTEN", "RB1", "BRCA1"]
METH_GENES = ["BRCA1", "RB1", "CDKN2A", "MLH1"]
ALL_GENES = sorted(set(EXPR_GENES + CNA_GENES + METH_GENES + ["CDH1", "AKT1"]))
DRIVER_SET = {"TP53", "PIK3CA", "BRCA1", "BRCA2", "PTEN", "GATA3", "CDH1", "AKT1"}

TCGA_ARCHETYPE_SAMPLES = {
    "A": (
        "TCGA-A2-A3XV-01",
        "HER2_AMP",
        (
            "TCGA-A2-A3XV-01 (TCGA-BRCA HER2-enriched): real ERBB2 +2 amp "
            "(log2 RSEM 15.23) + ERBB2 S310F & TP53 C135F."
        ),
    ),
    "B": (
        "TCGA-AO-A0J4-01",
        "TNBC_BRCA",
        (
            "TCGA-AO-A0J4-01 (TCGA-BRCA Basal-like TNBC): real BRCA1 V83F + "
            "TP53 R282W, TBL scar 159.0, immune-hot (7.81), HM450 absent "
            "(assayed on HM27 only)."
        ),
    ),
    "C": (
        "TCGA-D8-A1XV-01",
        "LUMINAL_A",
        (
            "TCGA-D8-A1XV-01 (TCGA-BRCA Luminal A): real ER+/PR+ high "
            "(ESR1 15.50, PGR 13.31), ERBB2 neutral, low TMB (0.66), TBL scar 4.0."
        ),
    ),
}


def synthetic_cases() -> list[dict[str, Any]]:
    """Return the bundled synthetic teaching cases from fixtures/synthetic_cases.json."""
    fixture = ROOT / "fixtures" / "synthetic_cases.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


def _post_json(path: str, payload: Any) -> Any:
    req = urllib.request.Request(
        CBIOPORTAL_BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(path: str) -> Any:
    req = urllib.request.Request(
        CBIOPORTAL_BASE + path, headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_tcga_cases_live() -> list[dict[str, Any]]:
    """Fetch the 3 real TCGA-BRCA tumor cases live from the cBioPortal public REST API."""
    genes_info = _post_json("/genes/fetch?geneIdType=HUGO_GENE_SYMBOL", ALL_GENES)
    hugo_to_entrez = {g["hugoGeneSymbol"]: g["entrezGeneId"] for g in genes_info}
    entrez_to_hugo = {g["entrezGeneId"]: g["hugoGeneSymbol"] for g in genes_info}
    sample_ids = [v[0] for v in TCGA_ARCHETYPE_SAMPLES.values()]
    expr_entrez = [hugo_to_entrez[g] for g in EXPR_GENES]

    rsem_rows = _post_json(
        f"/molecular-profiles/{TCGA_STUDY}_rna_seq_v2_mrna/molecular-data/fetch",
        {"sampleIds": sample_ids, "entrezGeneIds": expr_entrez},
    )
    z_profile = f"{TCGA_STUDY}_rna_seq_v2_mrna_median_all_sample_ref_normal_Zscores"
    z_rows = _post_json(
        f"/molecular-profiles/{z_profile}/molecular-data/fetch",
        {"sampleIds": sample_ids, "entrezGeneIds": expr_entrez},
    )
    rsem: dict[str, dict[str, float]] = {}
    for r in rsem_rows:
        sym = entrez_to_hugo[r["entrezGeneId"]]
        rsem.setdefault(r["sampleId"], {})[sym] = math.log2(float(r["value"]) + 1.0)
    z: dict[str, dict[str, float]] = {}
    for r in z_rows:
        sym = entrez_to_hugo[r["entrezGeneId"]]
        z.setdefault(r["sampleId"], {})[sym] = float(r["value"])

    normal_ref: dict[str, float] = {}
    for g in EXPR_GENES:
        s1, s2 = "TCGA-A2-A3XV-01", "TCGA-D8-A1XV-01"
        x1, x2 = rsem[s1][g], rsem[s2][g]
        z1, z2 = z[s1][g], z[s2][g]
        sigma = (x1 - x2) / (z1 - z2)
        normal_ref[g] = round(x1 - z1 * sigma, 2)

    cna_rows = _post_json(
        f"/molecular-profiles/{TCGA_STUDY}_gistic/molecular-data/fetch",
        {"sampleIds": sample_ids, "entrezGeneIds": [hugo_to_entrez[g] for g in CNA_GENES]},
    )
    cna: dict[str, dict[str, int]] = {}
    for r in cna_rows:
        sym = entrez_to_hugo[r["entrezGeneId"]]
        cna.setdefault(r["sampleId"], {})[sym] = int(r["value"])

    meth_rows = _post_json(
        "/molecular-profiles/brca_tcga_methylation_hm450/molecular-data/fetch",
        {
            "sampleIds": sample_ids,
            "entrezGeneIds": [hugo_to_entrez[g] for g in METH_GENES],
        },
    )
    meth: dict[str, dict[str, float]] = {}
    for r in meth_rows:
        sym = entrez_to_hugo[r["entrezGeneId"]]
        meth.setdefault(r["sampleId"], {})[sym] = round(float(r["value"]), 3)

    mut_url = (
        f"/molecular-profiles/{TCGA_STUDY}_mutations/mutations/fetch?projection=DETAILED"
    )
    mut_rows = _post_json(mut_url, {"sampleIds": sample_ids})
    muts: dict[str, list[dict[str, Any]]] = {}
    for r in mut_rows:
        sym = r.get("gene", {}).get("hugoGeneSymbol")
        if sym in ALL_GENES:
            raw_type = r.get("mutationType") or "missense"
            vtype = raw_type.lower().replace("_mutation", "")
            muts.setdefault(r["sampleId"], []).append({
                "gene": sym,
                "protein_change": r.get("proteinChange") or "unknown",
                "variant_type": vtype,
                "pathogenic": sym in DRIVER_SET,
            })

    clin_s_url = (
        f"/studies/{TCGA_STUDY}/clinical-data?clinicalDataType=SAMPLE&pageSize=100000"
    )
    clin_p_url = (
        f"/studies/{TCGA_STUDY}/clinical-data?clinicalDataType=PATIENT&pageSize=100000"
    )
    clin_sample = _get_json(clin_s_url)
    clin_patient = _get_json(clin_p_url)
    sample_meta: dict[str, dict[str, str]] = {}
    for row in clin_sample:
        if row["sampleId"] in sample_ids:
            attr = row["clinicalAttributeId"]
            sample_meta.setdefault(row["sampleId"], {})[attr] = row["value"]
    patient_meta: dict[str, dict[str, str]] = {}
    patient_ids = {s[:12] for s in sample_ids}
    for row in clin_patient:
        if row["patientId"] in patient_ids:
            attr = row["clinicalAttributeId"]
            patient_meta.setdefault(row["patientId"], {})[attr] = row["value"]

    cases: list[dict[str, Any]] = []
    for cid, (sid, label, hint) in TCGA_ARCHETYPE_SAMPLES.items():
        sm = sample_meta[sid]
        pm = patient_meta[sid[:12]]
        expr_dict = {g: round(rsem[sid][g], 2) for g in EXPR_GENES}
        cna_dict = {g: cna[sid][g] for g in CNA_GENES if g in cna.get(sid, {})}
        raw_stage = pm.get("AJCC_PATHOLOGIC_TUMOR_STAGE") or ""
        case_obj: dict[str, Any] = {
            "case_id": cid,
            "label": label,
            "tcga_sample_id": sid,
            "data_source": "real_tcga_brca",
            "provenance": {
                "study_id": TCGA_STUDY,
                "methylation_study_id": "brca_tcga",
                "tcga_sample_id": sid,
                "tcga_patient_id": sid[:12],
                "citation": "TCGA Pan-Cancer Atlas (Cell 2018) via cBioPortal public API",
                "expression_unit": (
                    "log2(RSEM_batch_normalized + 1); normal baseline derived from "
                    "TCGA solid-tissue normal reference Z-scores"
                ),
                "cna_unit": "GISTIC2 discrete copy-number state (-2..+2)",
                "hrd_score_source": (
                    "TCGA PanCanAtlas Tumor Break Load "
                    "(TBL_SCORE; Lakbir et al., Eur J Cancer 2022)"
                ),
            },
            "sample_type": sm.get("SAMPLE_TYPE", "Primary").lower(),
            "hint": hint,
            "expression": expr_dict,
            "expression_normal": normal_ref,
            "mutations": muts.get(sid, []),
            "mutation_burden_count": int(float(sm["MUTATION_COUNT"])),
            "cna": cna_dict,
            "hrd_score": float(sm["TBL_SCORE"]),
            "clinical": {
                "subtype": {
                    "BRCA_Her2": "HER2-enriched",
                    "BRCA_Basal": "Basal-like",
                    "BRCA_LumA": "Luminal A",
                }.get(pm.get("SUBTYPE"), pm.get("SUBTYPE")),
                "er_status": "Positive" if expr_dict["ESR1"] >= 8.0 else "Negative",
                "pr_status": "Positive" if expr_dict["PGR"] >= 7.0 else "Negative",
                "her2_status": "Positive" if expr_dict["ERBB2"] >= 12.0 else "Negative",
                "stage": raw_stage.replace("STAGE ", ""),
            },
        }
        if sid in meth:
            case_obj["methylation"] = {
                g: meth[sid][g] for g in METH_GENES if g in meth[sid]
            }
        cases.append(case_obj)
    return cases


def real_cases(live_fetch: bool = False) -> list[dict[str, Any]]:
    """Return real TCGA-BRCA cases (live from cBioPortal or cached snapshot)."""
    snapshot = ROOT / "fixtures" / "tcga_brca_cases.json"
    if live_fetch:
        try:
            print("Fetching real TCGA-BRCA cases live from cBioPortal API ...")
            cases = fetch_tcga_cases_live()
            snapshot.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
            return cases
        except Exception as exc:  # pragma: no cover - fallback when offline
            print(
                f"Live cBioPortal fetch failed ({exc}); "
                f"using verified snapshot {snapshot.name}.",
                file=sys.stderr,
            )
    return json.loads(snapshot.read_text(encoding="utf-8"))


def _write_case_set(
    cases: list[dict[str, Any]], out_dir: Path, provenance_note: str
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for case in cases:
        filename = f"case_{case['case_id']}.json"
        out_path = out_dir / filename
        out_path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
        entry: dict[str, Any] = {
            "case_id": case["case_id"],
            "label": case["label"],
            "file": filename,
            "provenance": case.get("provenance") or provenance_note,
        }
        if "tcga_sample_id" in case:
            entry["tcga_sample_id"] = case["tcga_sample_id"]
        manifest.append(entry)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["synthetic", "real", "both"],
        default="both",
        help=(
            "materialize 'synthetic' (data/), 'real' TCGA-BRCA (data/real/), "
            "or 'both' (default)."
        ),
    )
    parser.add_argument(
        "--live-download",
        action="store_true",
        help="re-fetch real TCGA-BRCA cases live from https://www.cbioportal.org/api",
    )
    parser.add_argument("--out", type=Path, default=ROOT / "data")
    args = parser.parse_args()

    print("Data source comparison:")
    print("  " + DATA_SOURCE_DIFFERENCE)
    print()

    if args.source in ("synthetic", "both"):
        syn = synthetic_cases()
        _write_case_set(
            syn,
            args.out,
            "Bundled synthetic teaching case; not clinical evidence.",
        )
        print(f"Restored {len(syn)} synthetic teaching cases to {args.out}")

    if args.source in ("real", "both"):
        real_out = args.out / "real" if args.source == "both" else args.out
        real = real_cases(live_fetch=args.live_download)
        note = (
            "Real TCGA-BRCA PanCanAtlas 2018 tumor profile via cBioPortal; "
            "research/education only."
        )
        _write_case_set(real, real_out, note)
        print(f"Restored {len(real)} real TCGA-BRCA cases to {real_out}")


if __name__ == "__main__":
    main()
