# Azure setup (az CLI)

Provision the three Azure services this lab uses: **Azure Machine Learning**
(MOFA+ training), **Azure OpenAI** (reasoning agent), and **Azure AI Search**
(PubMed-abstract evidence index). Run these from a shell with the `az` CLI
logged in (`az login`).

> Replace the placeholder names/regions. Names for OpenAI and Search must be
> globally unique. Azure OpenAI requires an approved subscription.

## 0. Variables and resource group

```bash
export LOCATION="eastus2"
export RG="rg-multiomics-lab"
export AOAI_NAME="aoai-multiomics-$RANDOM"
export SEARCH_NAME="search-multiomics-$RANDOM"
export AML_WS="aml-multiomics-lab"
export STORAGE="stmultiomics$RANDOM"

az group create --name "$RG" --location "$LOCATION"
```

## 1. Azure OpenAI + chat deployment

```bash
# Create the Azure OpenAI account.
az cognitiveservices account create \
  --name "$AOAI_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --kind OpenAI \
  --sku S0 \
  --yes

# Deploy a chat model (deployment name = what you put in AZURE_OPENAI_DEPLOYMENT).
az cognitiveservices account deployment create \
  --name "$AOAI_NAME" \
  --resource-group "$RG" \
  --deployment-name "gpt-4o" \
  --model-name "gpt-4o" \
  --model-version "2024-08-06" \
  --model-format OpenAI \
  --sku-name "Standard" \
  --sku-capacity 10

# Fetch endpoint + key for your .env
az cognitiveservices account show \
  --name "$AOAI_NAME" --resource-group "$RG" \
  --query "properties.endpoint" -o tsv
az cognitiveservices account keys list \
  --name "$AOAI_NAME" --resource-group "$RG" \
  --query "key1" -o tsv
```

> Prefer **keyless** auth in production: grant your identity the
> `Cognitive Services OpenAI User` role and leave `AZURE_OPENAI_API_KEY` blank;
> the agent uses `DefaultAzureCredential`.
>
> ```bash
> az role assignment create \
>   --assignee "<your-object-id>" \
>   --role "Cognitive Services OpenAI User" \
>   --scope "$(az cognitiveservices account show -n "$AOAI_NAME" -g "$RG" --query id -o tsv)"
> ```

## 2. Azure AI Search (PubMed abstracts index)

```bash
az search service create \
  --name "$SEARCH_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Basic

# Admin key for ingestion; query key for the agent.
az search admin-key show --service-name "$SEARCH_NAME" --resource-group "$RG"
az search query-key list   --service-name "$SEARCH_NAME" --resource-group "$RG"
```

Create an index named `pubmed-abstracts` (matching `.env` `AZURE_SEARCH_INDEX`)
with at least these fields, then push abstracts you have rights to use:

| field    | type            | notes                |
|----------|-----------------|----------------------|
| `id`     | Edm.String      | key                  |
| `pmid`   | Edm.String      | filterable           |
| `title`  | Edm.String      | searchable           |
| `abstract` | Edm.String    | searchable           |

You can ingest abstracts harvested from PubMed E-utilities (`efetch`) via the
Search REST API or the `azure-search-documents` SDK. If you skip this step the
agent automatically falls back to live PubMed queries.

## 3. Azure Machine Learning workspace (run MOFA+ as a job)

```bash
# Storage + AML workspace.
az storage account create --name "$STORAGE" --resource-group "$RG" --location "$LOCATION" --sku Standard_LRS
az extension add -n ml -y
az ml workspace create --name "$AML_WS" --resource-group "$RG" --location "$LOCATION"

# A small CPU compute target for training.
az ml compute create \
  --name cpu-cluster \
  --resource-group "$RG" --workspace-name "$AML_WS" \
  --type AmlCompute --min-instances 0 --max-instances 1 --size Standard_DS3_v2
```

Submit `src/integrate.py` as a command job (example `job.yml`):

```yaml
$schema: https://azuremlschemas.azureedge.net/latest/commandJob.schema.json
command: >-
  python scripts/download_data.py --synthetic &&
  python src/integrate.py --n-factors 10 --top-k 15
environment:
  image: mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04
  conda_file: conda.yml          # mirror requirements.txt
compute: azureml:cpu-cluster
code: .
outputs:
  factors:
    type: uri_folder
```

```bash
az ml job create --file job.yml --resource-group "$RG" --workspace-name "$AML_WS"
```

The job's `data/` outputs (factors + `top_features_per_factor.json`) can be
written to **Blob Storage**, then consumed by the agent step.

## 4. Wire up `.env`

Copy the endpoint/keys printed above into your local `.env` (see `.env.example`).
For CI / production, store them as GitHub Actions secrets or in Azure Key Vault
rather than committing them.

## 5. Clean up

```bash
az group delete --name "$RG" --yes --no-wait
```
