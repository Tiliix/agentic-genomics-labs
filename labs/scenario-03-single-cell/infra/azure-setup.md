# Azure Setup — Single-Cell Annotation Lab

Provision the cloud resources this lab uses: an **Azure ML workspace + compute**
(to run the Scanpy pipeline at scale) and an **Azure OpenAI** deployment (for the
annotation agent). All commands use the [Azure CLI](https://learn.microsoft.com/cli/azure/).

> Run `az login` first. Replace the placeholder names/regions to suit your tenant.
> Azure OpenAI requires an approved subscription; region availability varies.

## 0. Variables

```bash
# Edit these, then paste the block into your shell.
export LOCATION="eastus"
export RG="rg-sc-lab"
export AML_WS="aml-sc-lab"
export AML_COMPUTE="cpu-cluster"
export AOAI_NAME="aoai-sc-lab-$RANDOM"   # must be globally unique
export AOAI_DEPLOYMENT="gpt-4o"
export AOAI_MODEL="gpt-4o"
export AOAI_MODEL_VERSION="2024-08-06"
```

## 1. Resource group

```bash
az group create --name "$RG" --location "$LOCATION"
```

## 2. Azure Machine Learning workspace

```bash
# Install the ML extension once (idempotent).
az extension add --name ml --upgrade

az ml workspace create \
  --name "$AML_WS" \
  --resource-group "$RG" \
  --location "$LOCATION"
```

This automatically provisions the associated Storage account (Blob), Key Vault,
Container Registry, and Application Insights. The default Blob container is where
you stage `data/` inputs and collect `results/` artifacts.

## 3. Compute cluster (auto-scales to zero when idle)

```bash
az ml compute create \
  --name "$AML_COMPUTE" \
  --resource-group "$RG" \
  --workspace-name "$AML_WS" \
  --type AmlCompute \
  --size Standard_DS3_v2 \
  --min-instances 0 \
  --max-instances 2 \
  --idle-time-before-scale-down 1800
```

`Standard_DS3_v2` (4 vCPU / 14 GB) comfortably handles PBMC3k. Bump the size for
larger datasets. `--min-instances 0` keeps cost near zero between runs.

## 4. Azure OpenAI resource + model deployment

```bash
# Create the Azure OpenAI (Cognitive Services) account.
az cognitiveservices account create \
  --name "$AOAI_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --kind OpenAI \
  --sku S0 \
  --yes

# Deploy a chat model (the deployment name is what the SDK calls `model`).
az cognitiveservices account deployment create \
  --name "$AOAI_NAME" \
  --resource-group "$RG" \
  --deployment-name "$AOAI_DEPLOYMENT" \
  --model-name "$AOAI_MODEL" \
  --model-version "$AOAI_MODEL_VERSION" \
  --model-format OpenAI \
  --sku-name Standard \
  --sku-capacity 10
```

## 5. Capture endpoint + credentials for `.env`

```bash
# Endpoint
az cognitiveservices account show \
  --name "$AOAI_NAME" --resource-group "$RG" \
  --query "properties.endpoint" -o tsv

# API key (Option A auth). Prefer Entra ID (Option B) in production.
az cognitiveservices account keys list \
  --name "$AOAI_NAME" --resource-group "$RG" \
  --query "key1" -o tsv
```

Paste these into your `.env` (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`,
`AZURE_OPENAI_DEPLOYMENT=$AOAI_DEPLOYMENT`).

### Optional — keyless (Entra ID) auth

```bash
# Grant your signed-in user the data-plane role on the Azure OpenAI resource.
AOAI_ID=$(az cognitiveservices account show -n "$AOAI_NAME" -g "$RG" --query id -o tsv)
ME=$(az ad signed-in-user show --query id -o tsv)

az role assignment create \
  --assignee "$ME" \
  --role "Cognitive Services OpenAI User" \
  --scope "$AOAI_ID"
```

Then set `USE_AZURE_AD_AUTH=true` in `.env` and leave `AZURE_OPENAI_API_KEY` blank.

## 6. Tear down (avoid surprise costs)

```bash
az group delete --name "$RG" --yes --no-wait
```

Deleting the resource group removes the workspace, compute, storage, and Azure
OpenAI resource together.
