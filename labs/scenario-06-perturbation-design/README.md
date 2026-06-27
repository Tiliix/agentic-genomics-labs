# Scenario 06 — Genetic Perturbation Experiment Design (BioDiscoveryAgent-style)

An iterative, LLM-driven **active-learning loop** that designs the next batch of
CRISPR gene knockouts to test in a pooled genetic screen. Inspired by the
[BioDiscoveryAgent](https://github.com/snap-stanford/BioDiscoveryAgent) pattern,
this lab wires an **Azure OpenAI** agent that proposes genes, "measures" their
phenotype against a bundled ground-truth simulator (so the loop runs **fully
offline**), critiques its own hypothesis, and proposes the next round — beating a
random-selection baseline on cumulative hits.

> **This is in-silico experiment DESIGN, not biological discovery.** Every gene
> the agent prioritizes is a *hypothesis*. Nothing here substitutes for wet-lab
> validation: arrayed/pooled re-screening, orthogonal guides, and functional
> follow-up are required before any biological claim. The bundled phenotype
> table is **synthetic**; the real public datasets referenced below are for when
> you wire up an actual readout.

---

## Architecture

```mermaid
flowchart TD
    subgraph Dev["Dev environment (VS Code + GitHub)"]
        VSC[VS Code Dev Container\nPython 3.11]
        GH[GitHub repo\nCI: ruff + smoke import]
    end

    subgraph Azure["Azure"]
        AOAI[Azure OpenAI\nchat completion — proposer + critic]
        AML[Azure ML\nperturbation-outcome predictor\n(optional: GEARS surrogate)]
        SRCH[Azure AI Search\nliterature / prior-knowledge index]
        BLOB[Azure Blob Storage\nscreen results + ground-truth tables]
    end

    subgraph Loop["Active-learning loop (src/discovery_agent.py)"]
        PROP[Propose next batch] --> MEAS[measure() screen readout\nsrc/screen_env.py]
        MEAS --> UPD[Update running hit list]
        UPD --> CRIT[Critic revises hypothesis]
        CRIT --> PROP
    end

    VSC --> Loop
    AOAI --> PROP
    AOAI --> CRIT
    SRCH -. retrieved evidence .-> PROP
    AML -. predicted effect .-> PROP
    MEAS <--> BLOB
    GH --> VSC
```

The proposer and critic both run on Azure OpenAI. Azure AI Search supplies
literature/prior-knowledge grounding, Azure ML hosts an optional
perturbation-outcome predictor (a GEARS-style surrogate), and Blob Storage holds
the ground-truth tables and accumulated screen results. In this offline lab the
**screen readout is simulated** by `src/screen_env.py`; swap `measure()` for a
real assay or a GEARS prediction when you go live.

---

## Prerequisites

- Docker + VS Code with the **Dev Containers** extension (or any Python 3.11).
- An **Azure OpenAI** resource with a deployed chat model (e.g. `gpt-4o`).
- (Optional) Azure ML workspace + Azure AI Search service for the full stack.
- Azure CLI (`az`) for provisioning — see [`infra/azure-setup.md`](infra/azure-setup.md).

The loop runs **without any Azure credentials** using a deterministic offline
heuristic proposer, so you can try it before provisioning anything.

---

## Step-by-step run guide

1. **Open in the dev container.** `code .` → "Reopen in Container". This builds
   Python 3.11 and installs `requirements.txt`.

2. **Install dependencies** (already done by the container; otherwise):
   ```bash
   pip install -r requirements.txt
   ```

3. **Generate the synthetic ground-truth table.**
   ```bash
   python scripts/download_data.py
   ```
   This writes `data/ground_truth.csv` (pathway-clustered phenotype scores) and
   prints URLs for the real Norman/Adamson Perturb-seq datasets.

4. **(Optional) Configure Azure OpenAI.** Copy `.env.example` to `.env` and fill
   in your endpoint, deployment name, and key. Skip this to run the offline
   heuristic proposer.
   ```bash
   cp .env.example .env
   ```

5. **Run the discovery loop.**
   ```bash
   python src/discovery_agent.py --rounds 8 --batch-size 8
   ```
   Each round: propose genes → `measure()` → update hits → critic revises the
   hypothesis. Add `--no-llm` to force the offline proposer.

6. **Read the report.** The agent prints cumulative hits per round for the
   **agent** vs a **random baseline**, plus the final hypothesis. Cumulative-hit
   curves above the baseline indicate effective active learning.

7. **Go from in-silico to real.** Replace `screen_env.measure()` with a real
   readout (or an Azure ML / GEARS prediction), point the retrieval step at your
   Azure AI Search index, and persist results to Blob. **Then validate in the
   wet lab.**

---

## Files

| Path | Purpose |
|------|---------|
| `src/screen_env.py` | Synthetic perturbation environment + noisy `measure()` |
| `src/discovery_agent.py` | Iterative propose → measure → critique loop |
| `scripts/download_data.py` | Real dataset URLs + synthetic ground-truth generator |
| `infra/azure-setup.md` | `az` CLI for Azure OpenAI + Azure ML + AI Search |
| `.devcontainer/devcontainer.json` | Python 3.11 dev container |
| `.github/workflows/ci.yml` | ruff lint + smoke import |

---

## Responsible-use note

Phenotype scores here are simulated and biologically illustrative only. Use this
lab to learn the active-learning *workflow*, not to draw biological conclusions.
Any prioritized gene must be confirmed with independent guides and orthogonal
assays before it informs real experiments.
