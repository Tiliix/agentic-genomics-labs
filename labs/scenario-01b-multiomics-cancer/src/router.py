#!/usr/bin/env python3
"""router.py -- the NON-LLM, deterministic twin of the agent's reasoning.

This is a plain if/else encoding of the SAME conditional, data-driven routing the
LLM agent is asked to perform in ``src/agent.py``. It exists so the conditional
behaviour is verifiable WITHOUT any Azure credentials -- ``tests/test_router.py``
asserts that Case A, B and C take three different, expected tool paths.

The router calls the real omics skills to make its branching decisions, so it can
never silently drift from the thresholds the tools actually use.

Decision logic (mirrors SYSTEM_PROMPT in agent.py)::

    1. inspect_case                         (always)
    2. expression_qc                        (if expression layer present)
    3. receptor_status                      (always; expression present)
    4. cna_analysis('ERBB2')                ONLY IF HER2 is high
    5. mutation_analysis                    (always)
    6. hrd_status + immune_infiltration     ONLY IF TMB-high OR BRCA1/2 mutated
    7. methylation_analysis('BRCA1')        ONLY IF methylation layer present
    8. pathway_enrichment                   (always)
    9. survival_association(<marker>)       (always; marker chosen from findings)
   10. therapy_hint                         (always, last)
"""
from __future__ import annotations

from typing import Any

# Import the omics skills whether router.py is loaded as part of the ``src``
# package (``from src import router``) or with ``src`` on sys.path (``import router``).
try:
    from . import omics  # type: ignore  # noqa: TID252
except ImportError:  # pragma: no cover - standalone / sys.path import
    import omics  # type: ignore


def _pick_survival_marker(case: dict[str, Any], rec: dict[str, Any],
                          mut: dict[str, Any]) -> str:
    """Choose the most informative prognostic marker from what we found."""
    if rec["her2_high"]:
        return "ERBB2"
    if mut["tmb_high"]:
        return "TMB"
    if rec["hr_status"] == "HR-positive":
        return "ESR1"
    if mut["brca_mutated"]:
        return "BRCA1"
    return "MKI67"


def route(case: dict[str, Any]) -> dict[str, Any]:
    """Return the deterministic tool plan for one case.

    Returns a dict with:
      * ``path``    -- ordered list of executed tool names (the 'tool path')
      * ``steps``   -- ordered [{tool, args, reason, ran}] including SKIPS
    """
    steps: list[dict[str, Any]] = []

    def run(tool: str, reason: str, args: dict[str, Any] | None = None) -> None:
        steps.append({"tool": tool, "args": args or {}, "reason": reason, "ran": True})

    def skip(tool: str, reason: str) -> None:
        steps.append({"tool": tool, "args": {}, "reason": reason, "ran": False})

    # 1. Always inspect first to learn which layers exist.
    insp = omics.inspect_case(case)
    run("inspect_case", "Always start by discovering which omics layers are present.")
    layers = set(insp["layers_present"])

    # 2/3. Expression QC + receptor status (need the expression layer).
    if "expression" in layers:
        run("expression_qc", "Expression layer present -> QC it before interpreting.")
        rec = omics.receptor_status(case)
        run("receptor_status",
            "Derive ER/PR/HER2 from ESR1/PGR/ERBB2 to anchor the subtype.")
    else:  # pragma: no cover - all lab cases have expression
        rec = {"her2_high": False, "hr_status": "unknown"}
        skip("expression_qc", "No expression layer.")
        skip("receptor_status", "No expression layer.")

    # 4. ERBB2 copy-number ONLY if HER2 looked high (conditional!).
    if rec["her2_high"]:
        run("cna_analysis", "HER2 expression is high -> confirm ERBB2 amplification.",
            {"gene": "ERBB2"})
    else:
        skip("cna_analysis", "HER2 is not high -> ERBB2 amplification check not warranted.")

    # 5. Mutation analysis (always; gives TMB + driver/BRCA status).
    mut = omics.mutation_analysis(case)
    run("mutation_analysis", "Catalogue driver mutations and compute TMB.")

    # 6. HRD + immune ONLY if TMB-high OR BRCA mutated (conditional!).
    if mut["tmb_high"] or mut["brca_mutated"]:
        trigger = "TMB-high" if mut["tmb_high"] else "BRCA1/2 mutation"
        run("hrd_status", f"{trigger} -> assess homologous-recombination deficiency.")
        run("immune_infiltration",
            f"{trigger} -> assess immune hot/cold (immunotherapy relevance).")
    else:
        skip("hrd_status", "TMB low and no BRCA mutation -> HRD assessment not warranted.")
        skip("immune_infiltration",
             "TMB low and no BRCA mutation -> immune profiling not warranted.")

    # 7. Methylation ONLY if the layer exists (graceful skip otherwise).
    if "methylation" in layers:
        run("methylation_analysis", "Methylation layer present -> check BRCA1 promoter.",
            {"gene": "BRCA1"})
    else:
        skip("methylation_analysis",
             "Methylation layer ABSENT for this case -> skip gracefully.")

    # 8. Pathway enrichment (always).
    run("pathway_enrichment", "Summarise affected pathways from DE + drivers.")

    # 9. Survival association on the most informative marker (always).
    marker = _pick_survival_marker(case, rec, mut)
    run("survival_association", f"Prognostic context for the key marker ({marker}).",
        {"marker": marker})

    # 10. Therapy hint LAST -- maps everything accumulated to a biomarker->class hint.
    run("therapy_hint", "Always finish by mapping findings to an actionable hint.")

    path = [s["tool"] for s in steps if s["ran"]]
    return {"case_id": case.get("case_id"), "label": case.get("label"),
            "path": path, "steps": steps}


def format_plan(case: dict[str, Any]) -> str:
    """Human-readable plan (executed + skipped) for printing in run_cases.py."""
    plan = route(case)
    lines = [f"Case {plan['case_id']} ({plan['label']}) deterministic plan:"]
    for i, s in enumerate(plan["steps"], 1):
        mark = "RUN " if s["ran"] else "SKIP"
        arg = f" {s['args']}" if s["args"] else ""
        lines.append(f"  {i:>2}. [{mark}] {s['tool']}{arg}  -- {s['reason']}")
    lines.append(f"  PATH: {' -> '.join(plan['path'])}")
    return "\n".join(lines)
