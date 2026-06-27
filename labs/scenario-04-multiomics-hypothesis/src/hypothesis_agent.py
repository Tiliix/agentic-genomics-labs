#!/usr/bin/env python3
"""Azure OpenAI hypothesis agent.

Ingests the per-factor top features produced by ``src/integrate.py``, optionally
pulls supporting / contradicting literature (Azure AI Search index, or the
public PubMed E-utilities API as a fallback), and emits a *ranked* list of
candidate-driver hypotheses. Each hypothesis:

  * is explicitly labelled a HYPOTHESIS with caveats,
  * never asserts mechanism from correlation,
  * carries an evidence-strength score (0-1),
  * cites the exact data it rests on (factor, feature, signed weight, view).

Outputs:
  output/hypotheses.json   (machine-readable, schema-checked)
  output/hypotheses.md     (human-readable summary)

Run:
    python src/hypothesis_agent.py [--factor Factor1] [--top-factors 5]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
TOPFEAT_PATH = os.path.join(ROOT, "data", "top_features_per_factor.json")
OUT_DIR = os.path.join(ROOT, "output")

load_dotenv(os.path.join(ROOT, ".env"))

OFFLINE = os.getenv("OFFLINE", "0") == "1"


# ---------------------------------------------------------------------------
# Evidence retrieval
# ---------------------------------------------------------------------------
def search_pubmed(query: str, retmax: int = 3) -> list[dict[str, str]]:
    """Query PubMed via the public E-utilities API (esearch + esummary).

    Returns a list of {pmid, title, source} dicts. Returns [] on any failure or
    when OFFLINE=1. PubMed E-utilities is a real, free NCBI API:
    https://www.ncbi.nlm.nih.gov/books/NBK25501/
    """
    if OFFLINE:
        return []
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    common = {
        "tool": os.getenv("PUBMED_TOOL", "multiomics-hypothesis-lab"),
        "email": os.getenv("PUBMED_EMAIL", ""),
        "api_key": os.getenv("PUBMED_API_KEY", ""),
    }
    common = {k: v for k, v in common.items() if v}
    try:
        es = requests.get(
            f"{base}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": retmax, "retmode": "json", **common},
            timeout=20,
        )
        es.raise_for_status()
        ids = es.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        # Be polite to NCBI (max ~3 req/s without an API key).
        time.sleep(0.34)
        su = requests.get(
            f"{base}/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json", **common},
            timeout=20,
        )
        su.raise_for_status()
        result = su.json().get("result", {})
        out = []
        for pmid in ids:
            doc = result.get(pmid, {})
            out.append(
                {
                    "pmid": pmid,
                    "title": doc.get("title", ""),
                    "source": doc.get("source", ""),
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001 - evidence is best-effort
        print(f"PubMed query failed for {query!r}: {exc}", file=sys.stderr)
        return []


def search_azure_ai_search(query: str, top: int = 3) -> list[dict[str, str]]:
    """Query an Azure AI Search index of PubMed abstracts, if configured.

    Returns [] when Search is not configured or on failure (caller falls back
    to PubMed).
    """
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    index = os.getenv("AZURE_SEARCH_INDEX")
    key = os.getenv("AZURE_SEARCH_API_KEY")
    if OFFLINE or not (endpoint and index and key):
        return []
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient

        client = SearchClient(endpoint, index, AzureKeyCredential(key))
        results = client.search(search_text=query, top=top)
        out = []
        for doc in results:
            out.append(
                {
                    "pmid": str(doc.get("pmid", "")),
                    "title": str(doc.get("title", "")),
                    "source": "azure-ai-search",
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001
        print(f"Azure AI Search query failed for {query!r}: {exc}", file=sys.stderr)
        return []


def gather_evidence(factor: str, features: list[dict]) -> list[dict[str, str]]:
    """Build a query from the top features of a factor and gather evidence.

    Prefers Azure AI Search (in-tenant) and falls back to PubMed E-utilities.
    """
    # Use the top 3 feature stems as keywords (strip the view prefix).
    keywords = []
    for f in features[:3]:
        stem = f["feature"].split("_", 1)[-1]
        keywords.append(stem)
    query = " ".join(keywords) + " chronic lymphocytic leukemia"
    evidence = search_azure_ai_search(query)
    if not evidence:
        evidence = search_pubmed(query)
    for e in evidence:
        e["query"] = query
        e["factor"] = factor
    return evidence


# ---------------------------------------------------------------------------
# Azure OpenAI agent
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a cautious computational-biology research assistant. You are given the
top-weighted features of latent factors learned by MOFA+ (Multi-Omics Factor
Analysis) across several omics views (mRNA, methylation, drug response,
mutations) for a chronic lymphocytic leukaemia cohort, plus optional literature
evidence.

Your job: propose RANKED candidate-driver HYPOTHESES that could explain each
factor's covariation pattern.

HARD RULES — follow exactly:
1. MOFA+ factors capture COVARIATION, not causation. NEVER assert mechanism or
   causality from correlation. Every item is a HYPOTHESIS, phrased tentatively
   ("may", "could", "is consistent with"), with explicit caveats.
2. Every hypothesis MUST cite its data basis: the factor name, the specific
   feature(s), their signed weight(s), and the view(s). Do not invent features
   or weights — use only those provided.
3. Assign an evidence_strength score in [0,1]:
   - weight magnitude / how many views co-vary (data support), AND
   - whether literature evidence supports, contradicts, or is silent.
   State briefly how you arrived at the score.
4. If literature is absent, say so; do not fabricate citations or PMIDs.
5. Clearly separate supporting vs contradicting evidence when both exist.

Return STRICT JSON only, matching this schema:
{
  "factor": "<factor name>",
  "hypotheses": [
    {
      "rank": 1,
      "statement": "<tentative hypothesis text>",
      "caveats": "<why this is correlational / could be confounded>",
      "data_citations": [
        {"factor": "...", "feature": "...", "view": "...", "weight": 0.0}
      ],
      "evidence_strength": 0.0,
      "evidence_rationale": "<how the score was derived>",
      "supporting_evidence": [{"pmid": "...", "title": "..."}],
      "contradicting_evidence": [{"pmid": "...", "title": "..."}]
    }
  ]
}
"""


def get_client():
    """Construct an Azure OpenAI client.

    Uses an API key if provided, else azure-identity (Managed Identity / az login)
    via a bearer-token provider.
    """
    from openai import AzureOpenAI

    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if api_key:
        return AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)

    # Keyless auth via Entra ID.
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version,
    )


def reason_over_factor(client, factor: str, features: list[dict], evidence: list[dict]) -> dict[str, Any]:
    """Call Azure OpenAI to produce ranked hypotheses for one factor."""
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    user_payload = {
        "factor": factor,
        "top_features": features,
        "literature_evidence": evidence,
    }
    resp = client.chat.completions.create(
        model=deployment,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Here is the data for one MOFA+ factor. Produce ranked "
                    "candidate-driver hypotheses as strict JSON.\n\n"
                    + json.dumps(user_payload, indent=2)
                ),
            },
        ],
    )
    content = resp.choices[0].message.content or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"factor": factor, "hypotheses": [], "_raw": content}


def select_factors(top: dict[str, list[dict]], only: str | None, n: int) -> list[str]:
    """Pick which factors to reason over: a single named factor, or the top-N
    factors ranked by the max absolute feature weight they carry."""
    if only:
        if only not in top:
            sys.exit(f"Factor {only!r} not found. Available: {list(top)}")
        return [only]
    ranked = sorted(
        top.keys(),
        key=lambda f: max((abs(x["weight"]) for x in top[f]), default=0.0),
        reverse=True,
    )
    return ranked[:n]


def write_markdown(all_results: list[dict], path: str) -> None:
    lines = ["# Candidate-driver hypotheses (MOFA+ + Azure OpenAI)", ""]
    lines.append(
        "> Generated by `src/hypothesis_agent.py`. Each item is a **hypothesis** "
        "derived from covariation, not a causal claim.\n"
    )
    for res in all_results:
        lines.append(f"## {res.get('factor', '?')}")
        for h in res.get("hypotheses", []):
            lines.append(f"### #{h.get('rank', '?')} (evidence {h.get('evidence_strength', '?')})")
            lines.append(h.get("statement", ""))
            lines.append("")
            lines.append(f"*Caveats:* {h.get('caveats', '')}")
            cites = h.get("data_citations", [])
            if cites:
                lines.append("")
                lines.append("Data citations:")
                for c in cites:
                    lines.append(
                        f"- `{c.get('factor')}` / `{c.get('feature')}` "
                        f"({c.get('view')}) weight={c.get('weight')}"
                    )
            lines.append("")
    with open(path, "w") as fh:
        fh.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factor", default=None, help="reason over a single named factor")
    parser.add_argument("--top-factors", type=int, default=5, help="how many factors to process")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="skip Azure OpenAI; only assemble features+evidence (dry run)",
    )
    args = parser.parse_args()

    if not os.path.exists(TOPFEAT_PATH):
        sys.exit(f"{TOPFEAT_PATH} not found. Run src/integrate.py first.")
    with open(TOPFEAT_PATH) as fh:
        top = json.load(fh)

    factors = select_factors(top, args.factor, args.top_factors)
    print(f"Reasoning over factors: {factors}")

    client = None
    if not args.no_llm:
        client = get_client()

    all_results = []
    for factor in factors:
        features = top[factor]
        evidence = gather_evidence(factor, features)
        print(f"{factor}: {len(features)} features, {len(evidence)} evidence hits")
        if args.no_llm:
            all_results.append(
                {"factor": factor, "top_features": features, "evidence": evidence}
            )
            continue
        result = reason_over_factor(client, factor, features, evidence)
        all_results.append(result)

    os.makedirs(OUT_DIR, exist_ok=True)
    json_path = os.path.join(OUT_DIR, "hypotheses.json")
    with open(json_path, "w") as fh:
        json.dump(all_results, fh, indent=2)
    print(f"Wrote -> {json_path}")

    if not args.no_llm:
        md_path = os.path.join(OUT_DIR, "hypotheses.md")
        write_markdown(all_results, md_path)
        print(f"Wrote -> {md_path}")


if __name__ == "__main__":
    main()
