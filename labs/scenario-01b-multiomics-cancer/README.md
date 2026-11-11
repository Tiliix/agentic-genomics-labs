# Lab 1B — Agentic Multi-Omics Tumor Board (Human Breast Cancer)

> ⚠️ **RESEARCH / EDUCATION ONLY — NOT FOR CLINICAL USE.** This lab runs on
> synthetic or public *research* data with deliberately simplified heuristics. It
> must never be used to diagnose, treat, or inform any medical decision. Real
> molecular tumor boards require board-certified clinicians and accredited
> (CAP/CLIA) laboratories.

This is the **harder sequel** to a simple RNA-seq agent lab. The whole point is a
**complex pipeline of many tools where the agent CHOOSES which to run based on the
data** — not a fixed `1 → 2 → 3` sequence. An LLM orchestrator is given **12
analysis "skills"** and must conditionally route through them for each tumor case,
ending with a **Molecular Tumor Board Summary**.

**Stack:** Azure OpenAI (keyless / Azure AD) · GitHub · VS Code dev container ·
Python 3.11.

**Biology background:** [Understand the biology — Cancer Biology 101](Cancer_Biology_101.md).

---

## Why this lab is "agentic" and not a fixed pipeline

A fixed pipeline runs the same steps every time. Here, three different tumors take
three different paths through the toolset because **the agent reasons over each
tool's result before deciding the next call**:

- HER2 looks high → *then* confirm `ERBB2` copy-number; otherwise don't bother.
- High TMB or a BRCA mutation → *then* assess HRD and immune phenotype; otherwise skip.
- Methylation layer missing for this case → *detect that and skip gracefully*.

Two implementations encode the **same** logic so the behaviour is verifiable with
or without Azure:

| Component | File | Needs Azure? | Purpose |
|---|---|---|---|
| LLM agent | `src/agent.py` | yes | Tool-calling loop; the model decides the route. |
| Deterministic router | `src/router.py` | no | Plain if/else twin; pinned by tests. |

---

## Decision-flow diagram

```mermaid
flowchart TD
    A[inspect_case<br/>which layers exist?] --> B[expression_qc]
    B --> C[receptor_status<br/>ER / PR / HER2]
    C -->|HER2 high| D[cna_analysis ERBB2]
    C -->|HER2 low| D2[skip cna_analysis]
    D --> E[mutation_analysis<br/>drivers + TMB]
    D2 --> E
    E -->|TMB-high OR BRCA1/2| F[hrd_status]
    F --> G[immune_infiltration]
    E -->|low TMB & no BRCA| FG[skip hrd + immune]
    G --> H{methylation<br/>layer present?}
    FG --> H
    H -->|yes| I[methylation_analysis]
    H -->|no| I2[skip methylation]
    I --> J[pathway_enrichment]
    I2 --> J
    J --> K[survival_association]
    K --> L[therapy_hint<br/>biomarker → therapy class]
    L --> M[[Molecular Tumor Board Summary<br/>research-only]]
```

---

## The 12 tools (`src/omics.py`)

Each takes the loaded case dict and returns a JSON-serialisable dict. No randomness,
no network — fully reproducible.

| # | Tool | What it does | Conditional? |
|---|---|---|---|
| 1 | `inspect_case` | Lists which omics layers exist + metadata. | Always (first). |
| 2 | `expression_qc` | QC flags on the expression layer (housekeeping, range). | If expression present. |
| 3 | `receptor_status` | ER/PR/HER2 from ESR1/PGR/ERBB2 → HR±, HER2 high/low. | Always. |
| 4 | `differential_expression` | Tumor-vs-normal top up/down genes. | Optional context. |
| 5 | `cna_analysis(gene)` | GISTIC copy-number state; ERBB2 focal amp. | **Only if HER2 high.** |
| 6 | `mutation_analysis` | Driver mutations (TP53/PIK3CA/BRCA1/2) + TMB (mut/Mb). | Always. |
| 7 | `hrd_status` | HRD call from BRCA1/2 + genomic-scar score. | **Only if TMB-high or BRCA.** |
| 8 | `immune_infiltration` | Cytolytic/IFN-γ signature → hot/cold tumor. | **Only if TMB-high or BRCA.** |
| 9 | `methylation_analysis(gene)` | Promoter methylation. **Layer may be ABSENT.** | **Only if layer present.** |
| 10 | `pathway_enrichment` | Descriptive directional gene-to-pathway membership lookup over changed genes (not statistical enrichment). | Optional context. |
| 11 | `survival_association(marker)` | Hazard direction for a marker. | Optional context. |
| 12 | `therapy_hint` | Accumulated findings → actionable biomarker → therapy class. | Always (last). |

---

## The three test cases and their **expected divergent tool paths**

The synthetic generator plants ground truth so routing is reproducible. Case **B**
has **no methylation layer** on purpose, so the agent must detect and skip it.

| Case | Subtype (planted) | Key signals | Expected tool path |
|---|---|---|---|
| **A** `HER2_AMP` | HER2-enriched, HR− | ERBB2 amp+high, **low TMB**, methylation present | `inspect → expression_qc → receptor_status → ` **`cna_analysis`** ` → mutation_analysis → methylation_analysis → pathway_enrichment → survival_association → therapy_hint` |
| **B** `TNBC_BRCA` | Basal / triple-negative | **BRCA1 pathogenic**, **HIGH TMB**, immune-hot, **methylation ABSENT** | `inspect → expression_qc → receptor_status → mutation_analysis → ` **`hrd_status → immune_infiltration`** ` → pathway_enrichment → survival_association → therapy_hint` |
| **C** `LUMINAL_A` | Luminal A, HR+ | ESR1/PGR high, low TMB, no ERBB2 amp, methylation present | `inspect → expression_qc → receptor_status → mutation_analysis → methylation_analysis → pathway_enrichment → survival_association → therapy_hint` |

**Where they diverge (this is the whole point):**

| Step | Case A | Case B | Case C |
|---|---|---|---|
| `cna_analysis(ERBB2)` | ✅ run (HER2 high) | ⛔ skip | ⛔ skip |
| `hrd_status` + `immune_infiltration` | ⛔ skip (low TMB) | ✅ run (TMB-high + BRCA) | ⛔ skip |
| `methylation_analysis` | ✅ run (present) | ⛔ skip (layer absent) | ✅ run (present) |
| `therapy_hint` →  | anti-HER2 | PARP + immunotherapy | endocrine therapy |

`tests/test_router.py` asserts these three paths are pairwise distinct and match
the expected lists exactly.

---

## Data

- **Bundled synthetic source (`--source synthetic`):** `fixtures/synthetic_cases.json`
  preserves the three hand-authored 24-gene teaching cases (`Case A: HER2_AMP`,
  `Case B: TNBC_BRCA`, `Case C: LUMINAL_A`). Requires **no internet**.
- **Bundled & live TCGA-BRCA source (`--source real`):** `fixtures/tcga_brca_cases.json`
  ships three verified, de-identified primary breast tumors from **The Cancer Genome
  Atlas Pan-Cancer Atlas** (`brca_tcga_pan_can_atlas_2018` / `brca_tcga` via the
  [cBioPortal public REST API](https://www.cbioportal.org/api)):
  `TCGA-A2-A3XV-01` (Case A), `TCGA-AO-A0J4-01` (Case B), and `TCGA-D8-A1XV-01` (Case C).
  Pass `--live-download` to re-fetch them live from cBioPortal.

```bash
python scripts/download_data.py                               # materialize both synthetic (data/) and real (data/real/)
python scripts/download_data.py --source synthetic            # synthetic only
python scripts/download_data.py --source real --live-download # re-fetch live from cBioPortal API
```

Output: `data/case_A.json` .. `data/case_C.json`, `data/manifest.json`, and
`data/real/case_A.json` .. `data/real/case_C.json`, `data/real/manifest.json`.

---

## Run guide (Azure + GitHub + VS Code)

### A. Open in VS Code

1. `git clone` your fork, then **Reopen in Container** (uses `.devcontainer/`,
   Python 3.11, installs `requirements.txt`).

### B. Provision keyless Azure OpenAI

Follow **[`infra/azure-setup.md`](infra/azure-setup.md)**: create the resource,
deploy a tool-calling model (e.g. `gpt-4o`), and grant your identity the
**Cognitive Services OpenAI User** role. Then `az login`.

### C. Configure `.env`

```bash
cp .env.example .env
# set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT; leave AZURE_OPENAI_API_KEY blank
```

Leaving the key blank triggers keyless Azure AD auth in `src/agent.py`:

```python
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(exclude_managed_identity_credential=True),
    "https://cognitiveservices.azure.com/.default",
)
AzureOpenAI(azure_endpoint=ENDPOINT, azure_ad_token_provider=token_provider,
            api_version=API_VERSION)
```

### D. Choose Synthetic vs. Real TCGA-BRCA Study Data and Run

When running the lab, you can select between **Synthetic Teaching Data (`synthetic`)** and **Actual Study Data (`real`)** from **The Cancer Genome Atlas Pan-Cancer Atlas (`brca_tcga_pan_can_atlas_2018` / `brca_tcga` via cBioPortal)**:

> **Difference between Synthetic and Real Study Data:**
> - **Synthetic Data (`--data-source synthetic`):** Hand-authored 24-gene teaching dicts (`fixtures/synthetic_cases.json`) with clean round numbers (`ESR1: 2.0`, `ERBB2: 13.6`, `TMB: 13.68 mut/Mb`), zero background passenger noise, and no network download required.
> - **Real Study Data (`--data-source real`):** Actual de-identified TCGA-BRCA primary breast tumors (`Case A: TCGA-A2-A3XV-01`, `Case B: TCGA-AO-A0J4-01`, `Case C: TCGA-D8-A1XV-01`) with continuous `log2(RSEM + 1)` expression measured against 113 TCGA solid-tissue normals, real co-occurring somatic CNAs/mutations (e.g., `ERBB2 S310F` alongside `+2` amplification in `TCGA-A2-A3XV-01`), realistic breast-cancer TMB (`0.66–2.66 mut/Mb`, so Case B routes to HRD/immune via its `BRCA1 V83F` mutation rather than extreme hypermutation), and genuine platform absence of HM450 methylation on `TCGA-AO-A0J4-01` (which was assayed only on the legacy HM27 array).

```bash
python scripts/download_data.py                              # materializes both synthetic (data/) and real (data/real/)
python scripts/download_data.py --source real --live-download # optional: re-fetch live from cBioPortal API

python scripts/run_cases.py                                  # prompts interactively: [1] synthetic or [2] real
python scripts/run_cases.py --data-source synthetic          # run on synthetic teaching cases
python scripts/run_cases.py --data-source real               # run on real TCGA-BRCA patient tumors

python src/agent.py --case B --data-source real              # single case → output/reports/summary_case_B.md
```

### E. Verify the conditional behaviour WITHOUT Azure

```bash
python scripts/run_cases.py --router-only --data-source synthetic
python scripts/run_cases.py --router-only --data-source real
python -m pytest tests/test_router.py -v    # asserts both synthetic & real TCGA paths diverge as expected
```

---

## Repository layout

```
scenario-01b-multiomics-cancer/
├── README.md
├── Cancer_Biology_101.md         # biology background and reference diagrams
├── requirements.txt
├── pyproject.toml                # ruff + pytest config
├── .env.example                  # keyless-first config
├── .gitignore
├── .devcontainer/devcontainer.json
├── .github/workflows/ci.yml      # ruff + smoke import + router tests (no secrets)
├── examples/report.md            # sample divergent tool paths + tumor board report
├── infra/azure-setup.md          # az CLI: resource, deployment, role assignment
├── fixtures/
│   ├── synthetic_cases.json      # hand-authored 24-gene teaching cases
│   └── tcga_brca_cases.json      # real TCGA-BRCA PanCanAtlas tumors (cBioPortal)
├── data/                         # generated case_A|B|C.json + data/real/case_A|B|C.json
├── scripts/
│   ├── download_data.py          # materialize synthetic and/or real TCGA-BRCA cases
│   └── run_cases.py              # run agent/router on A/B/C (--data-source synthetic|real|ask)
├── src/
│   ├── __init__.py
│   ├── omics.py                  # the 12 deterministic skills
│   ├── router.py                 # non-LLM if/else twin of the agent's routing
│   └── agent.py                  # Azure OpenAI tool-calling loop (keyless)
└── tests/
    └── test_router.py            # proves A/B/C take different paths on both synthetic & real data
```

---

## Disclaimer (again, on purpose)

This material is for **research and education only**. The biomarker→therapy-class
associations emitted by `therapy_hint` are illustrative teaching mappings, **not**
treatment recommendations. Do not use any output of this lab for clinical care.
