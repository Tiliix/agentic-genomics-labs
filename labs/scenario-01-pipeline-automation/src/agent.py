"""
agent.py
========

Autonomous bioinformatics pipeline assistant.

An Azure OpenAI chat model drives the RNA-seq differential-expression pipeline
using the real **tool-calling** loop: the model plans, requests tool calls, we
execute the corresponding Python functions from ``pipeline.py``, feed the JSON
results back, and let the model decide the next step. When the model is done it
writes a final markdown report.

The model never fabricates numbers — every figure it reports comes from a tool
result that we computed deterministically.

Run:

    python src/agent.py

Requires a populated ``.env`` (see ``.env.example``) with a tool-calling-capable
Azure OpenAI deployment.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from src import pipeline

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")

MAX_TURNS = 12  # safety cap on the tool-calling loop


# --------------------------------------------------------------------------- #
# Tool registry — maps tool names the model can call to real Python functions
# --------------------------------------------------------------------------- #
TOOL_IMPLEMENTATIONS: dict[str, Callable[..., dict[str, Any]]] = {
    "run_qc": pipeline.run_qc,
    "quantify": pipeline.quantify,
    "differential_expression": pipeline.differential_expression,
    "pathway_enrichment": pipeline.pathway_enrichment,
}

# JSON-schema tool specs in the OpenAI "tools" format. The descriptions are what
# the model reasons over when planning the pipeline.
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_qc",
            "description": (
                "Quality-control summary of the raw counts matrix: library "
                "sizes, number of genes/samples, condition balance, and how many "
                "genes fall below a minimum count. Call this first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "min_count": {
                        "type": "integer",
                        "description": "Total-count threshold below which a gene is flagged as low-count.",
                        "default": 10,
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quantify",
            "description": (
                "Produce the analysis-ready counts matrix by filtering out "
                "low-count genes (where Salmon quant output would be imported in "
                "a full pipeline). Call after run_qc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "min_count": {
                        "type": "integer",
                        "description": "Minimum total count across samples to keep a gene.",
                        "default": 10,
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "differential_expression",
            "description": (
                "Run a DESeq2 differential-expression analysis with pydeseq2 on "
                "the filtered counts. Returns the number of significant genes and "
                "the top hits by adjusted p-value. Call after quantify."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "condition_column": {
                        "type": "string",
                        "description": "Metadata column defining the comparison groups.",
                        "default": "condition",
                    },
                    "reference_level": {
                        "type": "string",
                        "description": "Optional reference (control) level of the condition column.",
                    },
                    "alpha": {
                        "type": "number",
                        "description": "Adjusted p-value significance threshold.",
                        "default": 0.05,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pathway_enrichment",
            "description": (
                "Run Enrichr pathway enrichment via the Enrichr REST API. Splits "
                "the significant genes into up- and down-regulated sets and tests "
                "each against BOTH GO Biological Process and KEGG. Drosophila "
                "(FlyBase FBgn) genes are auto-mapped to symbols and routed to "
                "FlyEnrichr. Requires internet; degrades gracefully if Enrichr is "
                "unreachable. Call last, after differential_expression."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_set": {
                        "type": "string",
                        "description": "Enrichr gene-set library name.",
                        "default": "KEGG_2021_Human",
                    },
                    "alpha": {
                        "type": "number",
                        "description": "Adjusted p-value threshold for selecting input genes.",
                        "default": 0.05,
                    },
                },
            },
        },
    },
]


SYSTEM_PROMPT = """\
You are an autonomous bioinformatics pipeline assistant. Your job is to run an
RNA-seq differential-expression analysis end to end and explain every decision.

You have four tools that each perform a real analysis step:
  1. run_qc                  — inspect the counts matrix
  2. quantify                — build the analysis-ready (filtered) matrix
  3. differential_expression — pydeseq2 DESeq2 analysis
  4. pathway_enrichment      — Enrichr (REST) on the up- and down-regulated genes,
                               each tested against GO Biological Process AND KEGG

Plan the run, then call the tools in a sensible order (normally 1 → 2 → 3 → 4).
Before each tool call, briefly state your reasoning in one or two sentences.
Base every claim strictly on the JSON the tools return — never invent numbers.
If pathway enrichment is skipped because Enrichr is unreachable, say so plainly.

When all steps are complete, produce a FINAL markdown report titled
"# RNA-seq Differential Expression Report" with these sections:
  - Dataset & QC
  - Differential Expression (mention the count of significant genes and a few top genes)
  - Pathway Enrichment (report the up- and down-regulated results for BOTH
    databases — GO Biological Process and KEGG — with the top terms and whether any
    term passes FDR < 0.05; or note if skipped)
  - Interpretation & Recommended Next Steps
Do not call any more tools once you start the final report.
"""


def _make_client():
    """Construct the AzureOpenAI client. Imported lazily so the module imports
    cleanly even when the openai package or credentials are absent (CI smoke).

    Auth: if AZURE_OPENAI_API_KEY is set, use key auth. Otherwise fall back to
    keyless Microsoft Entra ID auth (DefaultAzureCredential) — required when the
    resource has key authentication disabled by policy. Keyless picks up your
    `az login` session locally, or the managed identity on Azure ML compute."""
    from openai import AzureOpenAI

    if not ENDPOINT:
        raise RuntimeError(
            "Azure OpenAI endpoint missing. Copy .env.example to .env and set "
            "AZURE_OPENAI_ENDPOINT (and AZURE_OPENAI_DEPLOYMENT)."
        )

    # Two endpoint styles are supported and selected automatically:
    #   * classic data plane -> https://<res>.openai.azure.com/  (azure_endpoint)
    #   * OpenAI v1 surface   -> https://<res>.services.ai.azure.com/openai/v1/
    #     (base_url) — required for the newest models such as gpt-5.1.
    _endpoint = ENDPOINT.rstrip("/")
    if _endpoint.endswith("/openai/v1"):
        route_kwargs: dict[str, Any] = {"base_url": _endpoint + "/"}
    else:
        route_kwargs = {"azure_endpoint": _endpoint}

    if API_KEY:
        return AzureOpenAI(api_key=API_KEY, api_version=API_VERSION, **route_kwargs)

    # Keyless / Entra ID auth (no API key required).
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_ad_token_provider=token_provider,
        api_version=API_VERSION,
        **route_kwargs,
    )


def _dispatch_tool(name: str, arguments: str) -> dict[str, Any]:
    """Execute a tool call requested by the model and return its JSON result."""
    impl = TOOL_IMPLEMENTATIONS.get(name)
    if impl is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        kwargs = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as exc:
        return {"error": f"Could not parse arguments for {name}: {exc}"}
    try:
        return impl(**kwargs)
    except Exception as exc:  # noqa: BLE001 — return errors to the model as data
        return {"error": f"{name} failed: {exc}"}


def run_agent(goal: str | None = None) -> str:
    """
    Drive the pipeline with the Azure OpenAI tool-calling loop.

    Returns the model's final markdown report (also written to
    ``data/results/report.md``).
    """
    client = _make_client()

    user_goal = goal or (
        "Run the full RNA-seq differential-expression pipeline on the dataset in "
        "data/ comparing the experimental condition against the control, then "
        "summarise the biology in a clear report."
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_goal},
    ]

    # gpt-5 / o-series reasoning models only allow the default sampling
    # temperature (1); sending temperature=0.2 returns a 400. Only pass it for
    # models that accept a custom value.
    supports_temperature = not any(
        tag in DEPLOYMENT.lower() for tag in ("gpt-5", "o1", "o3", "o4")
    )

    final_report = ""
    for turn in range(MAX_TURNS):
        create_kwargs: dict[str, Any] = {
            "model": DEPLOYMENT,  # Azure: this is the *deployment* name
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
        }
        if supports_temperature:
            create_kwargs["temperature"] = 0.2
        response = client.chat.completions.create(**create_kwargs)
        msg = response.choices[0].message

        # Print the model's reasoning / narration for this turn.
        if msg.content:
            print(f"\n--- Agent (turn {turn + 1}) ---\n{msg.content}\n")

        # Append the assistant message (must be echoed back verbatim).
        messages.append(msg.model_dump(exclude_none=True))

        # No tool calls => the model has produced its final answer.
        if not msg.tool_calls:
            final_report = msg.content or ""
            break

        # Execute each requested tool call and feed results back.
        for call in msg.tool_calls:
            name = call.function.name
            args = call.function.arguments or "{}"
            print(f">> tool call: {name}({args})")
            result = _dispatch_tool(name, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": json.dumps(result, default=str),
                }
            )
    else:
        print("Reached MAX_TURNS without a final report.")

    if final_report:
        pipeline.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = pipeline.RESULTS_DIR / "report.md"
        report_path.write_text(final_report, encoding="utf-8")
        print(f"\nFinal report written to {report_path}")

    return final_report


if __name__ == "__main__":
    # On Windows, stdout/stderr default to cp1252 when redirected, which raises
    # UnicodeEncodeError on unicode in the model's narration/report (e.g. α).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    os.chdir(REPO_ROOT)
    report = run_agent()
    print("\n" + "=" * 70)
    print(report)
