#!/usr/bin/env python3
"""test_router.py -- prove the conditional routing diverges per case WITHOUT Azure.

These tests pin the deterministic router (src/router.py), which encodes the same
conditional logic the LLM agent is instructed to follow. They assert that Case A,
B and C take three DIFFERENT, expected tool paths -- so the "agent chooses tools
based on the data" behaviour is verifiable with zero credentials and zero network.

Run::

    python -m pytest tests/test_router.py -v
    # or, without pytest installed:
    python tests/test_router.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import omics  # noqa: E402
import router  # noqa: E402

# Build the three planted cases directly from the generator -- no files/network.
sys.path.insert(0, str(ROOT / "scripts"))
import download_data  # noqa: E402

CASES = {c["case_id"]: c for c in download_data.synthetic_cases()}

# Expected, hand-verified divergent tool paths (must match router + agent rules).
EXPECTED = {
    "A": [  # HER2_AMP: HER2 high -> cna; low TMB/no BRCA -> no hrd/immune; meth present
        "inspect_case", "expression_qc", "receptor_status", "cna_analysis",
        "mutation_analysis", "methylation_analysis", "pathway_enrichment",
        "survival_association", "therapy_hint",
    ],
    "B": [  # TNBC_BRCA: HER2 low -> no cna; high TMB + BRCA -> hrd+immune; meth ABSENT
        "inspect_case", "expression_qc", "receptor_status", "mutation_analysis",
        "hrd_status", "immune_infiltration", "pathway_enrichment",
        "survival_association", "therapy_hint",
    ],
    "C": [  # LUMINAL_A: HER2 low -> no cna; low TMB/no BRCA -> no hrd/immune; meth present
        "inspect_case", "expression_qc", "receptor_status", "mutation_analysis",
        "methylation_analysis", "pathway_enrichment",
        "survival_association", "therapy_hint",
    ],
}


def _path(case_id: str) -> list[str]:
    return router.route(CASES[case_id])["path"]


def test_exact_paths_match_expected():
    for cid, expected in EXPECTED.items():
        assert _path(cid) == expected, f"case {cid} path mismatch: {_path(cid)}"


def test_three_paths_are_distinct():
    paths = [tuple(_path(c)) for c in ("A", "B", "C")]
    assert len(set(paths)) == 3, "expected three DIFFERENT tool paths"


def test_cna_only_when_her2_high():
    # Only Case A (HER2 high) should run the ERBB2 copy-number tool.
    assert "cna_analysis" in _path("A")
    assert "cna_analysis" not in _path("B")
    assert "cna_analysis" not in _path("C")


def test_hrd_and_immune_only_when_tmb_high_or_brca():
    # Only Case B (high TMB + BRCA1) should run HRD + immune profiling.
    for tool in ("hrd_status", "immune_infiltration"):
        assert tool in _path("B")
        assert tool not in _path("A")
        assert tool not in _path("C")


def test_methylation_skipped_when_layer_absent():
    # Case B has NO methylation layer -> tool must be skipped.
    assert "methylation_analysis" not in _path("B")
    assert "methylation_analysis" in _path("A")
    assert "methylation_analysis" in _path("C")
    # And calling the skill directly returns a graceful 'layer_absent' result.
    res = omics.methylation_analysis(CASES["B"], "BRCA1")
    assert res["status"] == "layer_absent" and res["skipped"] is True


def test_every_path_ends_with_therapy_hint():
    for cid in ("A", "B", "C"):
        assert _path(cid)[-1] == "therapy_hint"
        assert _path(cid)[0] == "inspect_case"


def test_underlying_tool_calls_are_consistent():
    # Sanity-check that the thresholds the router branches on are real.
    a = omics.receptor_status(CASES["A"])
    assert a["her2_high"] is True and a["hr_status"] == "HR-negative"
    b = omics.mutation_analysis(CASES["B"])
    assert b["tmb_high"] is True and b["brca_mutated"] is True
    c = omics.receptor_status(CASES["C"])
    assert c["hr_status"] == "HR-positive" and c["her2_high"] is False


def _run_standalone() -> int:
    """Allow `python tests/test_router.py` without pytest installed."""
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_standalone())
