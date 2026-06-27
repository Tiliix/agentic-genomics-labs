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

import router  # noqa: E402  (deterministic; no Azure needed)

DATA_DIR = ROOT / "data"
CASE_FILES = ["case_A.json", "case_B.json", "case_C.json"]


def load_cases() -> list[dict]:
    cases = []
    for fname in CASE_FILES:
        path = DATA_DIR / fname
        if not path.exists():
            sys.exit(f"Missing {path}. Run: python scripts/download_data.py")
        cases.append(json.loads(path.read_text(encoding="utf-8")))
    return cases


def print_router_paths(cases: list[dict]) -> None:
    print("=" * 78)
    print("DETERMINISTIC ROUTER (no LLM) -- expected tool paths")
    print("=" * 78)
    for case in cases:
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
    args = ap.parse_args(argv)

    cases = load_cases()
    print_router_paths(cases)

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
