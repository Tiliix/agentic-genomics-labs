#!/usr/bin/env python3
"""run_cases.py -- run the tumor-board agent on Case A, B, C and show the DIVERGENCE.

For each case it prints the ORDERED list of tools the agent actually called (the
"tool path"), so you can SEE the agent choose different analyses per case. It also
prints the deterministic router's expected path side-by-side.

Modes:
  * default: needs Azure OpenAI creds (.env). Runs the real LLM agent per case.
  * --router-only: NO Azure needed -- prints only the deterministic router paths
    (handy in CI or before you have credentials).

RESEARCH / EDUCATION ONLY.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import download_data  # noqa: E402

import router  # noqa: E402  (deterministic; no Azure needed)

DATA_DIR = ROOT / "data"
CASE_FILES = ["case_A.json", "case_B.json", "case_C.json"]

DATA_CHOICE_BANNER = """\
==============================================================================
DATA SOURCE SELECTION (Synthetic vs. Real Study Data)
==============================================================================
  [1] synthetic : Hand-authored 24-gene teaching cases (fixtures/synthetic_cases.json).
                  Faster, zero background noise, clean round numbers, no download.
  [2] real      : Actual TCGA-BRCA PanCanAtlas primary breast tumors from cBioPortal
                  (Case A: TCGA-A2-A3XV-01, Case B: TCGA-AO-A0J4-01,
                  Case C: TCGA-D8-A1XV-01). Continuous log2(RSEM+1) expression vs.
                  113 TCGA normals, real secondary CNAs/mutations, realistic TMB
                  (0.66-2.66 mut/Mb), and genuine HM450 methylation platform absence
                  on TCGA-AO-A0J4-01.
"""


def select_data_source(requested: str | None) -> str:
    """Resolve 'synthetic' vs 'real', prompting interactively when requested='ask'."""
    if requested in ("synthetic", "real"):
        return requested
    if not sys.stdin.isatty():
        return "synthetic"
    print(DATA_CHOICE_BANNER)
    try:
        prompt = "Choose data source [1=synthetic, 2=real] (default: 1): "
        ans = input(prompt).strip().lower()
    except EOFError:
        return "synthetic"
    if ans in ("2", "real", "r", "tcga"):
        return "real"
    return "synthetic"


def load_cases(data_source: str = "synthetic", live_download: bool = False) -> list[dict]:
    if data_source == "real":
        real_dir = DATA_DIR / "real"
        if live_download or not all((real_dir / f).exists() for f in CASE_FILES):
            cases = download_data.real_cases(live_fetch=live_download)
            note = (
                "Real TCGA-BRCA PanCanAtlas 2018 tumor profile via cBioPortal; "
                "research/education only."
            )
            download_data._write_case_set(cases, real_dir, note)
        return [
            json.loads((real_dir / f).read_text(encoding="utf-8")) for f in CASE_FILES
        ]

    if not all((DATA_DIR / f).exists() for f in CASE_FILES):
        syn_cases = download_data.synthetic_cases()
        download_data._write_case_set(
            syn_cases,
            DATA_DIR,
            "Bundled synthetic teaching case; not clinical evidence.",
        )
    return [json.loads((DATA_DIR / f).read_text(encoding="utf-8")) for f in CASE_FILES]


def print_router_paths(cases: list[dict], data_source: str = "synthetic") -> None:
    tag = "REAL TCGA-BRCA DATA" if data_source == "real" else "SYNTHETIC TEACHING DATA"
    print("=" * 78)
    print(f"DETERMINISTIC ROUTER (no LLM) -- expected tool paths [{tag}]")
    print("=" * 78)
    print(f"Note: {download_data.DATA_SOURCE_DIFFERENCE}\n")
    for case in cases:
        sample_id = case.get("tcga_sample_id")
        if sample_id:
            print(f"TCGA Sample: {sample_id}")
        print(router.format_plan(case))
        print()


def run_agent_paths(cases: list[dict]) -> None:
    import agent  # noqa: PLC0415  (import lazily so --router-only needs no Azure SDK)

    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    client = agent.build_client()

    print("=" * 78)
    print("LLM AGENT (Azure OpenAI) -- actual tool paths")
    print("=" * 78)
    summary = []
    for case in cases:
        print(f"\n--- Case {case['case_id']} ({case['label']}) ---", file=sys.stderr)
        out = agent.run_tumor_board(client, deployment, case)
        path = out["tool_path"]
        summary.append((case["case_id"], case["label"], path))
        print(f"Case {case['case_id']} ({case['label']}) tool path:")
        print("   " + " -> ".join(path))

    print("\n" + "=" * 78)
    print("DIVERGENCE SUMMARY (agent)")
    print("=" * 78)
    for cid, label, path in summary:
        print(f"  {cid} {label:12s}: {' -> '.join(path)}")


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--router-only", action="store_true",
                    help="only show deterministic router paths (no Azure needed)")
    ap.add_argument(
        "--data-source",
        choices=["synthetic", "real", "ask"],
        default="ask",
        help=(
            "choose 'synthetic' (fast, no download, clean round numbers), "
            "'real' (actual TCGA-BRCA PanCanAtlas patient tumors from cBioPortal), "
            "or 'ask' (interactive prompt in terminal; defaults to synthetic in CI)"
        ),
    )
    ap.add_argument(
        "--live-download",
        action="store_true",
        help="when --data-source=real, re-fetch live from https://www.cbioportal.org/api",
    )
    args = ap.parse_args(argv)

    chosen_source = select_data_source(args.data_source)
    cases = load_cases(data_source=chosen_source, live_download=args.live_download)
    print_router_paths(cases, data_source=chosen_source)

    if args.router_only:
        return 0

    try:
        run_agent_paths(cases)
    except KeyError as exc:
        print(f"\n[skipped LLM run] missing env var {exc}. "
              "Set AZURE_OPENAI_ENDPOINT/DEPLOYMENT in .env, or use --router-only.",
              file=sys.stderr)
        return 0
    except Exception as exc:  # network / auth problems shouldn't crash the demo
        print(f"\n[skipped LLM run] {type(exc).__name__}: {exc}\n"
              "Use --router-only to see the deterministic paths without Azure.",
              file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(_main())
