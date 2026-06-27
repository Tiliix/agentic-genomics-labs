"""Azure OpenAI cell-type annotation agent (GPTCelltype-style).

Idea (mirrors the GPTCelltype paper, Hou & Ji 2024): instead of manually
cross-referencing marker genes against the literature, hand the top marker
genes for each cluster to an LLM and ask it to name the cell type. Here we add
a second *self-critique* pass: the model re-reads its own annotations and flags
clusters whose markers are ambiguous (e.g. cycling vs. exhausted T cells, or
monocyte vs. dendritic overlap) so a human can review them.

Pipeline:
    markers_top.csv  ->  per-cluster marker lists
                     ->  Azure OpenAI chat completion (structured JSON)
                     ->  cell-type label + confidence + justification
                     ->  self-critique pass -> ambiguity flags
                     ->  results/cell_type_annotations.csv

Auth: API key OR Microsoft Entra ID (keyless), selected via .env.

Run (after src/pipeline.py):
    python src/annotate_agent.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import AzureOpenAI

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
MARKERS_CSV = RESULTS_DIR / "markers_top.csv"
ANNOTATIONS_CSV = RESULTS_DIR / "cell_type_annotations.csv"

# How many top markers per cluster to send to the model. GPTCelltype found that
# ~10 top genes is plenty; more tokens rarely improves the label.
N_MARKERS_FOR_LLM = 10

# Tissue context steers the model toward the right reference cell types.
TISSUE_CONTEXT = "human peripheral blood mononuclear cells (PBMC)"


def build_client() -> tuple[AzureOpenAI, str]:
    """Construct an AzureOpenAI client from environment variables.

    Returns (client, deployment_name).
    """
    load_dotenv()  # read .env into os.environ

    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
    use_ad = os.environ.get("USE_AZURE_AD_AUTH", "false").lower() == "true"

    if use_ad:
        # Keyless auth via Entra ID. Requires `az login` or a managed identity
        # with the "Cognitive Services OpenAI User" role.
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_version=api_version,
            azure_ad_token_provider=token_provider,
        )
    else:
        # API key auth.
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_version=api_version,
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
    return client, deployment


def load_marker_lists() -> dict[str, list[str]]:
    """Read markers_top.csv into {cluster: [gene, gene, ...]} (top N each)."""
    df = pd.read_csv(MARKERS_CSV, dtype={"cluster": str})
    markers: dict[str, list[str]] = {}
    for cluster, sub in df.groupby("cluster"):
        top = sub.sort_values("rank").head(N_MARKERS_FOR_LLM)["gene"].tolist()
        markers[str(cluster)] = top
    return markers


def annotate_clusters(
    client: AzureOpenAI, deployment: str, markers: dict[str, list[str]]
) -> list[dict]:
    """First pass: ask the model to label every cluster in one structured call."""
    # Compact, deterministic prompt. We request strict JSON so it parses cleanly.
    cluster_block = "\n".join(
        f"- Cluster {cid}: {', '.join(genes)}" for cid, genes in markers.items()
    )

    system_prompt = (
        "You are an expert single-cell genomics annotator. Given the top "
        "differentially expressed marker genes for each cluster, assign the most "
        "likely cell type. Be cautious: base labels strictly on canonical marker "
        "biology, and lower your confidence when markers are mixed or generic."
    )
    user_prompt = (
        f"Tissue context: {TISSUE_CONTEXT}.\n\n"
        f"Marker genes per cluster (ranked, most significant first):\n{cluster_block}\n\n"
        "For EACH cluster return a JSON object with this exact schema:\n"
        '{"annotations": [{"cluster": "<id>", "cell_type": "<label>", '
        '"confidence": <0.0-1.0>, "justification": "<one line citing the key '
        'markers>"}]}\n'
        "Use standard PBMC cell-type names (e.g. CD4+ T cells, CD8+ T cells, "
        "NK cells, B cells, CD14+ Monocytes, FCGR3A+ Monocytes, Dendritic cells, "
        "Megakaryocytes). Output JSON only."
    )

    resp = client.chat.completions.create(
        model=deployment,  # for AzureOpenAI, `model` is the deployment name
        temperature=0.0,    # deterministic labelling
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    payload = json.loads(resp.choices[0].message.content)
    return payload["annotations"]


def self_critique(
    client: AzureOpenAI,
    deployment: str,
    markers: dict[str, list[str]],
    annotations: list[dict],
) -> list[dict]:
    """Second pass: the model reviews its own labels and flags ambiguity.

    This guards against confident-but-wrong labels — the classic failure mode of
    LLM annotation. We explicitly prompt for hard-to-distinguish pairs such as
    cycling vs. exhausted T cells, or monocyte vs. dendritic overlap.
    """
    review_input = []
    for ann in annotations:
        cid = str(ann["cluster"])
        review_input.append(
            {
                "cluster": cid,
                "proposed_cell_type": ann.get("cell_type"),
                "confidence": ann.get("confidence"),
                "markers": markers.get(cid, []),
            }
        )

    system_prompt = (
        "You are a meticulous reviewer of single-cell annotations. Critically "
        "re-examine each proposed label against its markers and identify clusters "
        "that are genuinely ambiguous or potentially mislabelled."
    )
    user_prompt = (
        "Here are proposed annotations with their marker genes:\n"
        f"{json.dumps(review_input, indent=2)}\n\n"
        "For EACH cluster, decide whether the label is ambiguous. Pay special "
        "attention to commonly confused states, e.g.:\n"
        "  - cycling (MKI67, TOP2A) vs. exhausted (PDCD1, LAG3, HAVCR2) T cells\n"
        "  - CD14+ monocytes vs. dendritic cells (FCER1A, CST3)\n"
        "  - naive vs. memory T-cell subsets\n"
        "Return JSON with this schema:\n"
        '{"review": [{"cluster": "<id>", "ambiguous": <true|false>, '
        '"alternative": "<other plausible cell type or null>", '
        '"reason": "<short explanation>"}]}\n'
        "Output JSON only."
    )

    resp = client.chat.completions.create(
        model=deployment,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    payload = json.loads(resp.choices[0].message.content)
    return payload["review"]


def main() -> None:
    if not MARKERS_CSV.exists():
        raise SystemExit(
            f"{MARKERS_CSV} not found. Run `python src/pipeline.py` first."
        )

    client, deployment = build_client()
    markers = load_marker_lists()
    print(f"Loaded markers for {len(markers)} clusters.")

    print("Pass 1: annotating clusters ...")
    annotations = annotate_clusters(client, deployment, markers)

    print("Pass 2: self-critique for ambiguity ...")
    review = self_critique(client, deployment, markers, annotations)
    review_by_cluster = {str(r["cluster"]): r for r in review}

    # Merge the two passes into one tidy table.
    rows = []
    for ann in annotations:
        cid = str(ann["cluster"])
        rev = review_by_cluster.get(cid, {})
        rows.append(
            {
                "cluster": cid,
                "cell_type": ann.get("cell_type"),
                "confidence": ann.get("confidence"),
                "justification": ann.get("justification"),
                "ambiguous": rev.get("ambiguous", False),
                "alternative": rev.get("alternative"),
                "review_reason": rev.get("reason"),
                "markers": ", ".join(markers.get(cid, [])),
            }
        )

    out = pd.DataFrame(rows).sort_values("cluster", key=lambda s: s.astype(int))
    out.to_csv(ANNOTATIONS_CSV, index=False)
    print(f"Wrote {ANNOTATIONS_CSV}")

    # Console summary, surfacing flagged clusters for human review.
    print("\nCluster annotations:")
    for _, r in out.iterrows():
        flag = "  <-- REVIEW (ambiguous)" if r["ambiguous"] else ""
        print(
            f"  cluster {r['cluster']:>2}: {r['cell_type']:<22} "
            f"conf={r['confidence']}{flag}"
        )


if __name__ == "__main__":
    main()
