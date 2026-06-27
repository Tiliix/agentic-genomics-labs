"""BioDiscoveryAgent-style iterative perturbation designer.

The loop (one round):
  1. PROPOSE  -- the agent picks the next batch of genes to knock out, given the
                 search space, what's already been tested, the running hit list,
                 and (optionally) retrieved literature. Known-essential genes are
                 excluded on request.
  2. MEASURE  -- each proposed gene is "screened" via screen_env.measure()
                 (a noisy phenotype readout; replace with a real assay / GEARS
                 prediction in production).
  3. UPDATE   -- the running hit list is updated from the measured scores.
  4. CRITIQUE -- a critic step (also LLM) revises the working hypothesis about
                 which pathways look promising, steering the next PROPOSE.

The agent is benchmarked against a random-selection baseline on *cumulative
true hits discovered* per round.

Two proposers are provided:
  * AzureOpenAIProposer -- uses Azure OpenAI chat completions (proposer + critic).
  * HeuristicProposer   -- a deterministic offline fallback that exploits
                           measured signal (so the lab runs with no credentials).

NOTE: This designs experiments *in silico*. Prioritized genes are hypotheses
that require wet-lab validation.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
from dataclasses import dataclass, field

import numpy as np

# Support both "python src/discovery_agent.py" and "python -m src.discovery_agent"
try:
    from screen_env import HIT_THRESHOLD, ScreenEnv, load_ground_truth
except ImportError:  # pragma: no cover
    from src.screen_env import HIT_THRESHOLD, ScreenEnv, load_ground_truth


# ---------------------------------------------------------------------------
# Optional literature retrieval (Azure AI Search). Returns short context
# strings the proposer can use for grounding. Safe no-op if not configured.
# ---------------------------------------------------------------------------
def retrieve_literature(query: str, top: int = 3) -> list[str]:
    """Query an Azure AI Search index for prior knowledge about ``query``.

    Returns a list of snippet strings. If Azure AI Search isn't configured,
    returns an empty list so the loop still runs.
    """
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_SEARCH_API_KEY")
    index = os.getenv("AZURE_SEARCH_INDEX")
    if not (endpoint and api_key and index):
        return []
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient

        client = SearchClient(endpoint, index, AzureKeyCredential(api_key))
        results = client.search(search_text=query, top=top)
        return [str(doc.get("content", ""))[:300] for doc in results]
    except Exception as exc:  # noqa: BLE001 - retrieval is best-effort
        print(f"[retrieve_literature] skipped ({exc})")
        return []


# ---------------------------------------------------------------------------
# Shared state carried across rounds
# ---------------------------------------------------------------------------
@dataclass
class LoopState:
    tested: set[str] = field(default_factory=set)
    # gene -> best observed (max) phenotype score so far
    observed: dict[str, float] = field(default_factory=dict)
    hits: set[str] = field(default_factory=set)
    hypothesis: str = "No prior signal yet. Explore diverse pathways first."

    def record(self, gene: str, score: float) -> None:
        self.tested.add(gene)
        if score > self.observed.get(gene, float("-inf")):
            self.observed[gene] = score
        if score >= HIT_THRESHOLD:
            self.hits.add(gene)

    def top_observed(self, n: int = 10) -> list[tuple[str, float]]:
        return sorted(self.observed.items(), key=lambda kv: kv[1], reverse=True)[:n]


# ---------------------------------------------------------------------------
# Proposers
# ---------------------------------------------------------------------------
class HeuristicProposer:
    """Offline proposer: greedy exploit + epsilon explore, pathway-aware.

    With no LLM, this still demonstrates active learning: it favors genes whose
    *measured* neighbors (same pathway) scored well, mixing in random
    exploration. It mirrors what the LLM is asked to do, just deterministically.
    """

    name = "agent(heuristic)"

    def __init__(self, env: ScreenEnv, rng: random.Random, epsilon: float = 0.3):
        self.env = env
        self.rng = rng
        self.epsilon = epsilon

    def propose(
        self, state: LoopState, batch_size: int, avoid_essential: bool
    ) -> list[str]:
        candidates = [
            g
            for g in self.env.genes
            if g not in state.tested
            and not (avoid_essential and g in self.env.essential)
        ]
        if not candidates:
            return []

        # Score each candidate by the best observed effect among already-tested
        # genes in the same pathway (exploit pathway structure).
        pathway_signal: dict[str, float] = {}
        for gene, score in state.observed.items():
            pw = self.env.pathway.get(gene, "?")
            pathway_signal[pw] = max(pathway_signal.get(pw, 0.0), score)

        def candidate_score(g: str) -> float:
            return pathway_signal.get(self.env.pathway.get(g, "?"), 0.0)

        ranked = sorted(candidates, key=candidate_score, reverse=True)

        chosen: list[str] = []
        for _ in range(min(batch_size, len(candidates))):
            if self.rng.random() < self.epsilon and candidates:
                pick = self.rng.choice(candidates)  # explore
            else:
                pick = next((g for g in ranked if g not in chosen), None)
                if pick is None:
                    pick = self.rng.choice(candidates)
            chosen.append(pick)
            candidates = [c for c in candidates if c != pick]
            ranked = [c for c in ranked if c != pick]
        return chosen

    def critique(self, state: LoopState) -> str:
        top = state.top_observed(5)
        if not top:
            return "No signal yet; keep exploring diverse pathways."
        best_pw = self.env.pathway.get(top[0][0], "?")
        return (
            f"Strongest signal in pathway '{best_pw}' "
            f"(top gene {top[0][0]} = {top[0][1]:+.2f}). "
            f"Prioritize untested members of '{best_pw}' next round."
        )


class AzureOpenAIProposer:
    """LLM proposer + critic backed by Azure OpenAI chat completions."""

    name = "agent(azure-openai)"

    def __init__(self, env: ScreenEnv):
        from openai import AzureOpenAI

        self.env = env
        self.deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        self.client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ.get(
                "AZURE_OPENAI_API_VERSION", "2024-08-01-preview"
            ),
        )

    def _chat(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.deployment,
            temperature=0.4,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    def propose(
        self, state: LoopState, batch_size: int, avoid_essential: bool
    ) -> list[str]:
        candidates = [
            g
            for g in self.env.genes
            if g not in state.tested
            and not (avoid_essential and g in self.env.essential)
        ]
        if not candidates:
            return []

        lit = retrieve_literature("CRISPR knockout proliferation phenotype hits")
        lit_block = (
            "\nRelevant literature snippets:\n- " + "\n- ".join(lit) if lit else ""
        )
        top = ", ".join(f"{g}={s:+.2f}" for g, s in state.top_observed(8)) or "none"

        system = (
            "You are a genetic-perturbation experiment designer running an "
            "active-learning CRISPR knockout screen. You pick the next batch of "
            "genes to knock out to MAXIMIZE discovery of strong phenotype hits, "
            "balancing exploitation of promising pathways against exploration. "
            "You design experiments in silico; outputs are hypotheses requiring "
            "wet-lab validation. Respond ONLY with a JSON array of gene symbols."
        )
        user = (
            f"Current hypothesis: {state.hypothesis}\n"
            f"Top observed effects so far: {top}\n"
            f"Genes already tested ({len(state.tested)}): "
            f"{sorted(state.tested)}\n"
            f"{'Avoid known-essential genes.' if avoid_essential else ''}"
            f"{lit_block}\n\n"
            f"Choose exactly {batch_size} UNTESTED gene symbols from this "
            f"candidate pool:\n{candidates}\n\n"
            f'Return JSON only, e.g. ["KRAS","BRAF"].'
        )
        raw = self._chat(system, user)
        genes = _parse_gene_list(raw, valid=set(candidates))
        # Top up if the model returned too few / invalid symbols.
        for g in candidates:
            if len(genes) >= batch_size:
                break
            if g not in genes:
                genes.append(g)
        return genes[:batch_size]

    def critique(self, state: LoopState) -> str:
        top = ", ".join(f"{g}={s:+.2f}" for g, s in state.top_observed(8)) or "none"
        system = (
            "You are the critic in an active-learning loop. In 2-3 sentences, "
            "revise the working hypothesis about which pathways/genes are most "
            "promising and what to prioritize next round. Be concrete."
        )
        user = (
            f"Previous hypothesis: {state.hypothesis}\n"
            f"Top observed effects: {top}\n"
            f"Hits found so far: {sorted(state.hits)}"
        )
        return self._chat(system, user).strip() or state.hypothesis


def _parse_gene_list(raw: str, valid: set[str]) -> list[str]:
    """Extract gene symbols from a possibly-messy LLM response."""
    out: list[str] = []
    try:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            for item in json.loads(match.group(0)):
                g = str(item).strip().upper()
                if g in valid and g not in out:
                    out.append(g)
    except (json.JSONDecodeError, TypeError):
        pass
    if not out:  # fallback: token scan
        for token in re.findall(r"[A-Z0-9]+", raw.upper()):
            if token in valid and token not in out:
                out.append(token)
    return out


# ---------------------------------------------------------------------------
# Random baseline
# ---------------------------------------------------------------------------
class RandomBaseline:
    name = "random-baseline"

    def __init__(self, env: ScreenEnv, rng: random.Random):
        self.env = env
        self.rng = rng

    def propose(
        self, state: LoopState, batch_size: int, avoid_essential: bool
    ) -> list[str]:
        candidates = [
            g
            for g in self.env.genes
            if g not in state.tested
            and not (avoid_essential and g in self.env.essential)
        ]
        self.rng.shuffle(candidates)
        return candidates[:batch_size]

    def critique(self, state: LoopState) -> str:
        return "Random baseline: no hypothesis."


# ---------------------------------------------------------------------------
# The active-learning driver
# ---------------------------------------------------------------------------
def run_loop(
    proposer,
    env: ScreenEnv,
    rounds: int,
    batch_size: int,
    avoid_essential: bool,
    verbose: bool = True,
) -> list[int]:
    """Run the propose -> measure -> update -> critique loop.

    Returns the cumulative-hit count after each round.
    """
    state = LoopState()
    cumulative: list[int] = []

    for r in range(1, rounds + 1):
        batch = proposer.propose(state, batch_size, avoid_essential)
        if not batch:
            cumulative.append(len(state.hits))
            continue

        scores = env.measure_batch(batch)
        for gene, score in scores.items():
            state.record(gene, score)

        # Critic revises the hypothesis to steer the next round.
        state.hypothesis = proposer.critique(state)
        cumulative.append(len(state.hits))

        if verbose:
            new_hits = sorted(g for g in batch if g in state.hits)
            print(
                f"[{proposer.name}] round {r:>2}: "
                f"tested {len(state.tested):>3} | "
                f"cumulative hits {len(state.hits):>2} | "
                f"new hits this round: {new_hits or '-'}"
            )
            print(f"    hypothesis: {state.hypothesis}")

    return cumulative


def build_proposer(env: ScreenEnv, use_llm: bool, rng: random.Random):
    """Pick the Azure OpenAI proposer if configured, else the heuristic one."""
    configured = bool(
        os.getenv("AZURE_OPENAI_ENDPOINT")
        and os.getenv("AZURE_OPENAI_API_KEY")
        and os.getenv("AZURE_OPENAI_DEPLOYMENT")
    )
    if use_llm and configured:
        try:
            print("Using Azure OpenAI proposer + critic.")
            return AzureOpenAIProposer(env)
        except Exception as exc:  # noqa: BLE001
            print(f"Azure OpenAI unavailable ({exc}); using heuristic proposer.")
    else:
        print("Using offline heuristic proposer (no Azure OpenAI credentials).")
    return HeuristicProposer(env, rng)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Force the offline heuristic proposer even if Azure is configured.",
    )
    parser.add_argument(
        "--allow-essential",
        action="store_true",
        help="Do NOT exclude known-essential genes from proposals.",
    )
    args = parser.parse_args()

    # Load environment variables from .env if present.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    env = load_ground_truth()
    total_true_hits = len(env.true_hits())
    avoid_essential = not args.allow_essential

    print("=" * 70)
    print("Perturbation experiment design — active-learning loop")
    print(f"Search space: {len(env.genes)} genes | "
          f"true hits (hidden): {total_true_hits} | "
          f"avoid_essential={avoid_essential}")
    print("IN-SILICO DESIGN ONLY — prioritized genes require wet-lab validation.")
    print("=" * 70)

    # Agent run.
    agent = build_proposer(env, use_llm=not args.no_llm, rng=random.Random(args.seed))
    print("\n--- AGENT ---")
    agent_curve = run_loop(
        agent, env, args.rounds, args.batch_size, avoid_essential
    )

    # Random baseline on a *fresh* environment instance (same ground truth).
    base_env = load_ground_truth()
    baseline = RandomBaseline(base_env, random.Random(args.seed + 100))
    print("\n--- RANDOM BASELINE ---")
    base_curve = run_loop(
        baseline, base_env, args.rounds, args.batch_size, avoid_essential,
        verbose=False,
    )

    # Report.
    print("\n" + "=" * 70)
    print("RESULTS — cumulative true hits discovered per round")
    print(f"{'round':>6} | {'agent':>6} | {'random':>6}")
    print("-" * 26)
    for i, (a, b) in enumerate(zip(agent_curve, base_curve), start=1):
        print(f"{i:>6} | {a:>6} | {b:>6}")
    print("-" * 26)
    final_a = agent_curve[-1] if agent_curve else 0
    final_b = base_curve[-1] if base_curve else 0
    print(f"final  | {final_a:>6} | {final_b:>6}   "
          f"(of {total_true_hits} true hits)")
    lift = final_a - final_b
    print(
        f"\nAgent discovered {final_a}/{total_true_hits} hits vs "
        f"{final_b}/{total_true_hits} for random "
        f"({'+' if lift >= 0 else ''}{lift} hit advantage)."
    )
    print("Reminder: these are in-silico hypotheses — validate in the wet lab.")


if __name__ == "__main__":
    main()
