# Agentic Engineering for Bioinformatics & Genomics — Hands-on Labs

A growing series of six self-contained training labs that let you test agentic-AI bioinformatics scenarios end-to-end on the **Azure + GitHub + VS Code** stack using **publicly available data**. Each lab pairs a classic bioinformatics workflow with an LLM agent (Azure OpenAI) that plans, runs tools, and explains its reasoning.

> **How to use:** Push this folder to your own GitHub account (e.g. `github.com/<your-username>/agentic-genomics-labs`), then open any scenario folder in VS Code and "Reopen in Container". Each `README.md` has a numbered, step-by-step run guide. All labs run **offline with a synthetic fallback** and **at full scale once you add an Azure OpenAI resource + internet**.

> **Availability:** Only **Challenge 01 — Pipeline automation** ships in this repo today. The rows below are the roadmap — each lab lands here as its newsletter issue goes live.

| # | Scenario | Classic stack | Agent does | Public dataset |
|---|----------|---------------|------------|----------------|
| 01 | Pipeline automation | Salmon · pyDESeq2 · gseapy | Orchestrates QC → DE → pathway enrichment | nf-core / pasilla RNA-seq |
| 02 | Variant interpretation | VCF · MyVariant.info · Ensembl VEP · ACMG | Writes cited interpretation memo | GIAB NA12878 / bundled VCF |
| 03 | Single-cell analysis | Scanpy · Leiden · CellTypist | Annotates cell types + self-critique | 10x PBMC 3k |
| 04 | Multi-omics hypothesis | MOFA+ · scikit-learn | Ranks candidate-driver hypotheses | MOFA+ CLL multi-omics |
| 05 | Target discovery | Open Targets GraphQL API | Prioritizes drug targets from human genetics | Open Targets Platform |
| 06 | Perturbation design | Active-learning loop · scikit-learn | Proposes next CRISPR knockouts (BioDiscoveryAgent-style) | Norman/Adamson Perturb-seq |

## Prerequisites (all labs)
- An Azure subscription with an **Azure OpenAI** resource + a chat deployment (e.g. `gpt-4o`)
- **VS Code** + Dev Containers extension + Docker
- **GitHub** account (to host this repo and run the included GitHub Actions CI)
- Python 3.11 (provided by the devcontainer)

## Safety & scope
These labs are for **education and research only**. The variant-interpretation and perturbation-design labs are explicitly **not for clinical or wet-lab decisions** without qualified review and validation.

## Repository layout (per scenario)
```
scenario-XX-name/
├── README.md                 # step-by-step run guide + architecture
├── .devcontainer/            # VS Code dev container (Python 3.11)
├── .github/workflows/ci.yml  # lint + smoke tests
├── requirements.txt
├── .env.example              # copy to .env and fill Azure OpenAI values
├── infra/azure-setup.md      # az CLI to provision Azure resources
├── scripts/download_data.py  # fetch public data (with offline fallback)
└── src/                      # pipeline + agent code
```

_Generated as a training companion to the "Agentic Engineering in Bioinformatics & Genomics" strategy deck._
