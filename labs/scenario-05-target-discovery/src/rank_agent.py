"""Azure OpenAI tool-calling agent that ranks drug targets for a disease.

The agent is given ONE tool: `get_target_evidence`, which pulls Open Targets
association scores, tractability, and safety for a disease's top targets. The model
calls the tool, then writes a transparent target-prioritization memo scoring each
candidate across four axes:

  1. Human genetic support   (Open Targets genetic_association datatype score)
  2. Tissue / mechanism specificity (eQTL / RNA-expression / pathway evidence)
  3. Tractability            (is the target druggable, and by what modality?)
  4. Safety                  (known liabilities that raise risk)

Crucially the memo must state that *genetic support is supporting evidence, not a
guarantee of clinical efficacy*.

Run:
    python -m src.rank_agent --efo EFO_0001360 --top 10 --out memo.md

Requires Azure OpenAI env vars (see .env.example). The Open Targets tool itself
needs no key and will fall back to the cached snapshot in data/ if the API is down.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from dotenv import load_dotenv

# Repo root on path for `from src...` when run as a script.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.opentargets import (  # noqa: E402
    associated_targets,
    target_safety,
    target_tractability,
)

DATA_DIR = os.path.join(_REPO_ROOT, "data")


# ---------------------------------------------------------------------------
# Tool implementation: assemble an evidence bundle the model can reason over
# ---------------------------------------------------------------------------
def _load_cached(efo_id: str) -> dict[str, Any] | None:
    """Return a previously downloaded snapshot for the disease, if present."""
    path = os.path.join(DATA_DIR, f"associations_{efo_id}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def get_target_evidence(efo_id: str, top: int = 10) -> dict[str, Any]:
    """Tool body. Return disease + top-N targets enriched with tractability/safety.

    Strategy: prefer the cached snapshot (fast, offline-safe). If absent, query the
    live Open Targets API. Then enrich each top target with tractability + safety.
    """
    base = _load_cached(efo_id)
    source = "cache"
    if base is None:
        base = associated_targets(efo_id, size=max(top, 25))
        source = "live"

    targets = base["targets"][:top]
    enriched: list[dict[str, Any]] = []
    for t in targets:
        ens = t["ensemblId"]
        # If we loaded from cache the tractability/safety may be missing; fetch live
        # when possible, but tolerate failure so the agent still gets the scores.
        tract: list = t.get("tractability", [])
        safety: list = t.get("safety", [])
        if not tract or not safety:
            try:
                tract = tract or target_tractability(ens)
                safety = safety or target_safety(ens)
            except Exception:  # offline / API issue — proceed with what we have
                pass
        enriched.append(
            {
                "symbol": t["symbol"],
                "ensemblId": ens,
                "name": t.get("name"),
                "overallScore": t["overallScore"],
                "datatypeScores": t["datatypeScores"],
                "tractability": tract,
                "safetyLiabilities": safety,
            }
        )

    return {
        "disease": base["disease"],
        "source": source,
        "targets": enriched,
    }


# JSON schema describing the tool to Azure OpenAI.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_target_evidence",
            "description": (
                "Fetch Open Targets evidence for a disease's top associated drug "
                "targets: overall association score, per-datatype scores "
                "(genetic_association, known_drug, affected_pathway, rna_expression, "
                "literature, animal_model, somatic_mutation), tractability buckets, "
                "and curated safety liabilities."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "efo_id": {
                        "type": "string",
                        "description": "EFO disease identifier, e.g. EFO_0001360.",
                    },
                    "top": {
                        "type": "integer",
                        "description": "How many top targets to retrieve.",
                        "default": 10,
                    },
                },
                "required": ["efo_id"],
            },
        },
    }
]

SYSTEM_PROMPT = """\
You are a computational drug-discovery analyst. You prioritize drug targets for a \
disease using ONLY the evidence returned by the get_target_evidence tool (Open Targets \
Platform). You must:

1. Call get_target_evidence exactly once for the requested disease.
2. Score every returned target across four axes, each cited to its evidence type:
   - Human genetic support  -> datatypeScores.genetic_association
   - Tissue / mechanism specificity -> datatypeScores.rna_expression and
     affected_pathway (eQTL/colocalization-derived); note tissue if present.
   - Tractability -> the tractability buckets (which modality is druggable?).
   - Safety -> safetyLiabilities (more/severe liabilities => lower score).
3. Produce a ranked, transparent target-prioritization memo in MARKDOWN with:
   - A one-paragraph summary.
   - A ranked table: Rank | Symbol | Overall | Genetic | Tractability | Safety flags.
   - For the top 3 targets, a short rationale paragraph citing the specific evidence
     types and scores that drove the ranking.
   - A clearly labelled "Caveats" section.
4. CRITICAL caveat you must state explicitly: human genetic association is SUPPORTING
   evidence and does NOT guarantee clinical efficacy. Genetic support improves the prior
   that modulating the target affects disease, but tractability, safety, biology, and
   trial execution all still gate success. Recommend the memo be used to triage
   hypotheses for literature/wet-lab follow-up, not for go/no-go decisions.

Be concrete and quantitative. Never invent evidence not present in the tool output.
"""


def build_client():
    """Construct an AzureOpenAI client from environment variables."""
    from openai import AzureOpenAI  # imported lazily so tests can import this module

    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    api_key = os.environ["AZURE_OPENAI_API_KEY"]
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )


def run_agent(efo_id: str, top: int) -> str:
    """Drive the tool-calling loop and return the final markdown memo."""
    client = build_client()
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Prioritize the top {top} drug targets for disease {efo_id}. "
                "Call the tool, then write the markdown memo."
            ),
        },
    ]

    # First turn: the model decides to call the tool.
    first = client.chat.completions.create(
        model=deployment,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=0.2,
    )
    msg = first.choices[0].message
    messages.append(msg.model_dump(exclude_none=True))

    # Execute any tool calls the model requested.
    if msg.tool_calls:
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            result = get_target_evidence(
                efo_id=args.get("efo_id", efo_id),
                top=int(args.get("top", top)),
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.function.name,
                    "content": json.dumps(result),
                }
            )

    # Second turn: the model writes the memo from the tool output.
    final = client.chat.completions.create(
        model=deployment,
        messages=messages,
        temperature=0.2,
    )
    return final.choices[0].message.content or ""


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Rank drug targets for a disease.")
    parser.add_argument("--efo", default="EFO_0001360", help="EFO disease id.")
    parser.add_argument("--top", type=int, default=10, help="Targets to rank.")
    parser.add_argument("--out", default=None, help="Write memo to this markdown file.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip Azure OpenAI; just print the evidence bundle the agent would use.",
    )
    args = parser.parse_args()

    if args.dry_run:
        bundle = get_target_evidence(args.efo, args.top)
        print(json.dumps(bundle, indent=2))
        return 0

    memo = run_agent(args.efo, args.top)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(memo)
        print(f"Wrote memo -> {args.out}")
    else:
        print(memo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
