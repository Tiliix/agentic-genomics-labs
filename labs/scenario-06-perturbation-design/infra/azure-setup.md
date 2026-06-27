# Azure setup — Perturbation Experiment Design lab

Provision the Azure backing services for the agent. All commands use the Azure
CLI (`az`). Run `az login` first and set a default subscription with
`az account set --subscription <SUB_ID>`.

> You only need **Azure OpenAI** to run the full agent loop. Azure ML and Azure
> AI Search are optional (predictor + literature grounding). The lab also runs
> fully offline with the heuristic proposer and no Azure resources.

```bash
# ---- 0. Variables -----------------------------------------------------------
export RG=rg-perturb-lab
export LOC=eastus
export PREFIX=perturb$RANDOM
```

## 1. Resource group

```bash
az group create --name $RG --location $LOC
```

## 2. Azure OpenAI (proposer + critic)

```bash
# Create the Azure OpenAI account
az cognitiveservices account create \
  --name ${PREFIX}-aoai \
  --resource-group $RG \
  --location $LOC \
  --kind OpenAI \
  --sku S0 \
  --yes

# Deploy a chat model (deployment name is what goes in AZURE_OPENAI_DEPLOYMENT)
az cognitiveservices account deployment create \
  --name ${PREFIX}-aoai \
  --resource-group $RG \
  --deployment-name gpt-4o \
  --model-name gpt-4o \
  --model-version "2024-08-06" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard

# Grab endpoint + key for your .env
az cognitiveservices account show \
  --name ${PREFIX}-aoai --resource-group $RG \
  --query properties.endpoint -o tsv
az cognitiveservices account keys list \
  --name ${PREFIX}-aoai --resource-group $RG \
  --query key1 -o tsv
```

Set in `.env`:
```
AZURE_OPENAI_ENDPOINT=<endpoint>
AZURE_OPENAI_API_KEY=<key1>
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview
```

## 3. Azure AI Search (literature / prior-knowledge grounding — optional)

```bash
az search service create \
  --name ${PREFIX}-search \
  --resource-group $RG \
  --sku basic \
  --location $LOC

# Admin key for ingestion / querying
az search admin-key show \
  --service-name ${PREFIX}-search --resource-group $RG \
  --query primaryKey -o tsv
```

Create an index named `perturbation-literature` with at least a `content` field,
then ingest abstracts / curated pathway notes. The agent's `retrieve_literature()`
queries it automatically when these vars are set:
```
AZURE_SEARCH_ENDPOINT=https://${PREFIX}-search.search.windows.net
AZURE_SEARCH_API_KEY=<primaryKey>
AZURE_SEARCH_INDEX=perturbation-literature
```

## 4. Azure ML (perturbation-outcome predictor — optional, GEARS-style)

```bash
# Install the ML extension once
az extension add -n ml

# Create the workspace
az ml workspace create \
  --name ${PREFIX}-mlw \
  --resource-group $RG \
  --location $LOC
```

Train/register a perturbation-outcome predictor (e.g. a GEARS surrogate or a
scikit-learn model over screen features) and deploy it as a managed online
endpoint. Point `measure()` (or a pre-screen filter in `propose()`) at it via:
```
AZURE_ML_PREDICTOR_ENDPOINT=https://<endpoint>.<region>.inference.ml.azure.com/score
AZURE_ML_PREDICTOR_KEY=<endpoint-key>
```

## 5. Azure Blob Storage (results + ground-truth tables — optional)

```bash
az storage account create \
  --name ${PREFIX}store \
  --resource-group $RG \
  --location $LOC \
  --sku Standard_LRS

az storage container create \
  --account-name ${PREFIX}store \
  --name screen-results
```

Persist each round's measurements and the ground-truth table here so runs are
reproducible and auditable.

## 6. Clean up

```bash
az group delete --name $RG --yes --no-wait
```

---

**Reminder:** this stack designs experiments *in silico*. Genes the agent
prioritizes are hypotheses; confirm with orthogonal guides and wet-lab assays
before acting on them.
