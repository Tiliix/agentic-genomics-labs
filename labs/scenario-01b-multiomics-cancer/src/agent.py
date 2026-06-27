#!/usr/bin/env python3
"""agent.py -- the Agentic Multi-Omics Tumor Board (Azure OpenAI tool-calling loop).

The agent is given ALL 12 omics skills as tools and is instructed to choose WHICH
ones to run based on what each result reveals -- a CONDITIONAL, non-sequential
pipeline, not a fixed 1->2->3 chain. It ends with a "Molecular Tumor Board Summary".

Auth (keyless-first, exactly as required by the lab):
  * If AZURE_OPENAI_API_KEY is set -> use the API key.
  * ELSE -> keyless Azure AD via azure-identity DefaultAzureCredential +
    get_bearer_token_provider (managed-identity excluded for local `az login`).

RESEARCH / EDUCATION ONLY -- never for clinical use.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Make the local omics module importable whether run as a script or a module.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import omics  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv optional at runtime
    pass

API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")

DISCLAIMER = (
    "> **DISCLAIMER -- RESEARCH / EDUCATION ONLY. NOT FOR CLINICAL USE.** "
    "This molecular tumor board summary was produced by an automated teaching "
    "pipeline on synthetic / public research data using simplified heuristics. "
    "It must NOT be used to diagnose, treat, or make any medical decision. Real "
    "molecular tumor boards require board-certified clinicians and accredited "
    "(CAP/CLIA) laboratory testing."
)

SYSTEM_PROMPT = """\
You are the orchestrator of an Agentic Multi-Omics Tumor Board for a single human
breast-cancer case. You have 12 analysis tools. Your job is to run a CONDITIONAL,
data-driven workup -- NOT a fixed sequence. Do NOT call every tool; choose tools
based on what previous results reveal.

MANDATORY behaviour:
- FIRST call inspect_case to learn which omics layers exist.
- Before EACH tool call, state in one sentence WHY you are calling it (what prior
  result justifies it).
- When you decide to SKIP a tool, explicitly say which tool and WHY you skipped it.
- Base every claim ONLY on returned tool results. Never invent numbers or statuses.

CONDITIONAL ROUTING RULES (follow these):
- Always run expression_qc and receptor_status when an expression layer exists.
- Run cna_analysis('ERBB2') ONLY IF receptor_status shows HER2 is high.
- Always run mutation_analysis.
- Run hrd_status AND immune_infiltration ONLY IF mutation_analysis shows TMB-high
  OR a pathogenic BRCA1/2 mutation. Otherwise skip both and say why.
- Run methylation_analysis ONLY IF the methylation layer is present
  (inspect_case tells you). If it is absent, skip it and say so.
- differential_expression, pathway_enrichment and survival_association are optional
  context tools -- use them when they add value.
- ALWAYS finish with therapy_hint as the last tool call.

After the tools, write a final report titled "## Molecular Tumor Board Summary"
with these sections:
  - Case & subtype
  - Key molecular findings (cite the tool + value for each)
  - Tools you SKIPPED and why
  - Biomarker -> therapy-class hint (from therapy_hint), clearly labelled research-only
  - End with the exact disclaimer line provided in the user message.
"""


# --------------------------------------------------------------------------- #
# Azure OpenAI client (keyless-first)
# --------------------------------------------------------------------------- #
def build_client():
    """Create an AzureOpenAI client: API key if present, else keyless Azure AD."""
    from openai import AzureOpenAI

    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()

    if api_key:
        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_version=API_VERSION,
            api_key=api_key,
        )

    # Keyless: requires `az login` and the "Cognitive Services OpenAI User" role.
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(exclude_managed_identity_credential=True),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=API_VERSION,
    )


# --------------------------------------------------------------------------- #
# OpenAI tool schema for all 12 skills
# --------------------------------------------------------------------------- #
def _fn(name: str, description: str, properties: dict | None = None,
        required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


TOOLS: list[dict[str, Any]] = [
    _fn("inspect_case",
        "List which omics layers (expression, mutations, cna, methylation, clinical) "
        "are present, plus case metadata. Call this FIRST."),
    _fn("expression_qc",
        "QC the expression layer: housekeeping genes, value range, missing values."),
    _fn("receptor_status",
        "Derive ER/PR/HER2 status from ESR1/PGR/ERBB2 expression. Returns her2_high "
        "and the hormone-receptor (HR) call."),
    _fn("differential_expression",
        "Tumour-vs-normal log2 fold-changes; returns the top up/down genes.",
        {"top_n": {"type": "integer", "description": "How many genes per direction."}}),
    _fn("cna_analysis",
        "Copy-number state (GISTIC -2..+2) for one gene; flags amplification/deletion. "
        "Use gene='ERBB2' to confirm HER2 amplification.",
        {"gene": {"type": "string", "description": "HUGO gene symbol, e.g. ERBB2."}},
        ["gene"]),
    _fn("mutation_analysis",
        "Driver mutations (TP53/PIK3CA/BRCA1/2/...) and TMB (mut/Mb); returns tmb_high "
        "and brca_mutated."),
    _fn("hrd_status",
        "Homologous-recombination-deficiency call from BRCA1/2 status + genomic-scar "
        "score."),
    _fn("immune_infiltration",
        "Cytolytic / IFN-gamma signature -> hot vs cold tumour phenotype."),
    _fn("methylation_analysis",
        "Promoter methylation beta for a gene. The methylation LAYER MAY BE ABSENT -- "
        "in that case it returns status='layer_absent' and you should skip it.",
        {"gene": {"type": "string", "description": "HUGO gene symbol, e.g. BRCA1."}},
        ["gene"]),
    _fn("pathway_enrichment",
        "Aggregate affected pathways over the case's top DE genes + driver mutations."),
    _fn("survival_association",
        "Direction of prognostic association for a marker (ERBB2, ESR1, TMB, BRCA1...).",
        {"marker": {"type": "string", "description": "Marker symbol or 'TMB'."}},
        ["marker"]),
    _fn("therapy_hint",
        "Map accumulated findings to actionable biomarker -> therapy class. "
        "Call this LAST. Research-only."),
]

assert len(TOOLS) == 12, "expected exactly 12 registered tools"


# --------------------------------------------------------------------------- #
# Dispatch: tool name -> python call against the loaded case.
# --------------------------------------------------------------------------- #
def build_dispatch(case: dict[str, Any]) -> dict[str, Any]:
    """Bind the loaded case into a name->callable(args)->dict dispatch table."""
    return {name: (lambda fn: (lambda args: fn(case, **args)))(fn)
            for name, fn in omics.TOOL_FUNCTIONS.items()}


# --------------------------------------------------------------------------- #
# Agent loop
# --------------------------------------------------------------------------- #
def run_tumor_board(client, deployment: str, case: dict[str, Any],
                    max_steps: int = 16, verbose: bool = True) -> dict[str, Any]:
    """Run the conditional tool-calling loop on one case.

    Returns {"report": str, "tool_path": [tool names in call order],
             "messages": [...]} so callers can inspect the divergent tool path.
    """
    dispatch = build_dispatch(case)
    user_msg = (
        f"Work up this breast-cancer case (case_id={case.get('case_id')}). "
        "Decide which analyses are warranted -- do not run every tool. "
        "End your final summary with EXACTLY this disclaimer line:\n" + DISCLAIMER
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    tool_path: list[str] = []

    for _ in range(max_steps):
        resp = client.chat.completions.create(
            model=deployment,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.1,
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            report = msg.content or ""
            if "NOT FOR CLINICAL USE" not in report.upper():
                report = report.rstrip() + "\n\n" + DISCLAIMER
            return {"report": report, "tool_path": tool_path, "messages": messages}

        for call in msg.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
                if name not in dispatch:
                    raise KeyError(f"unknown tool {name}")
                result = dispatch[name](args)
            except Exception as exc:  # surface tool errors back to the model
                result = {"error": f"{type(exc).__name__}: {exc}"}
            tool_path.append(name)
            if verbose:
                print(f"    -> tool: {name}({args if args else ''})", file=sys.stderr)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "name": name,
                "content": json.dumps(result, default=str),
            })

    return {"report": "Agent did not converge within the step budget.\n\n" + DISCLAIMER,
            "tool_path": tool_path, "messages": messages}


def load_case(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("case_json", help="path to a case JSON file (data/case_A.json)")
    ap.add_argument("--out-dir", default="output/reports",
                    help="directory for the markdown summary")
    args = ap.parse_args(argv)

    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    case = load_case(args.case_json)
    client = build_client()

    print(f"Running tumor board on case {case.get('case_id')} "
          f"({case.get('label')}) ...", file=sys.stderr)
    out = run_tumor_board(client, deployment, case)

    print("\nTOOL PATH:", " -> ".join(out["tool_path"]))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"summary_case_{case.get('case_id')}.md"
    report_path.write_text(out["report"], encoding="utf-8")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
