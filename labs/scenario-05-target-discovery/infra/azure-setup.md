# Azure setup (az CLI)

Provision the backing services for the target-discovery lab: **Azure OpenAI** (rank
agent), **Azure AI Search** (literature RAG), and a **Function or Container** for the
ingestion job. Run these from a shell with the Azure CLI installed and `az login` done.

> Names must be globally unique where noted. Replace the placeholder values.

## 0. Variables

```bash
export RG=rg-target-discovery
export LOC=eastus
export AOAI=aoai-targetdisc-$RANDOM        # Azure OpenAI account (unique)
export SEARCH=srch-targetdisc-$RANDOM      # Azure AI Search service (unique)
export STORAGE=sttargetdisc$RANDOM         # Blob storage (unique, lowercase)
export FUNCAPP=func-targetdisc-$RANDOM     # Function app (unique)
export PLAN=plan-targetdisc
```

## 1. Resource group

```bash
az group create --name "$RG" --location "$LOC"
```

## 2. Azure OpenAI + chat deployment

```bash
# Create the account (Cognitive Services kind=OpenAI).
az cognitiveservices account create \
  --name "$AOAI" --resource-group "$RG" --location "$LOC" \
  --kind OpenAI --sku S0 --yes

# Deploy a tool-calling-capable chat model.
az cognitiveservices account deployment create \
  --name "$AOAI" --resource-group "$RG" \
  --deployment-name gpt-4o \
  --model-name gpt-4o --model-version "2024-08-06" \
  --model-format OpenAI \
  --sku-name Standard --sku-capacity 10

# Grab endpoint + key for your .env
az cognitiveservices account show --name "$AOAI" --resource-group "$RG" \
  --query properties.endpoint -o tsv
az cognitiveservices account keys list --name "$AOAI" --resource-group "$RG" \
  --query key1 -o tsv
```

Put these into `.env` as `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and
`AZURE_OPENAI_DEPLOYMENT=gpt-4o`.

## 3. Azure AI Search (literature RAG index)

```bash
az search service create \
  --name "$SEARCH" --resource-group "$RG" --location "$LOC" \
  --sku basic --partition-count 1 --replica-count 1

# Admin key + endpoint for .env (AZURE_SEARCH_*)
az search admin-key show --service-name "$SEARCH" --resource-group "$RG" \
  --query primaryKey -o tsv
echo "https://$SEARCH.search.windows.net"
```

Create an index named `literature-rag` (via portal, REST, or
`azure-search-documents`) with at least: `id` (key), `title`, `abstract` (searchable),
`pmid`, and a `contentVector` field if you enable vector search. Populate it with
PubMed abstracts for your targets; the rank agent can then cite literature context
alongside Open Targets evidence.

## 4. Storage (raw JSON snapshots)

```bash
az storage account create \
  --name "$STORAGE" --resource-group "$RG" --location "$LOC" \
  --sku Standard_LRS

az storage container create \
  --account-name "$STORAGE" --name associations --auth-mode login
```

The ingestion job writes the output of `scripts/download_data.py` here; Azure AI Search
can index from this container.

## 5. Ingestion as an Azure Function (Python)

```bash
az functionapp create \
  --name "$FUNCAPP" --resource-group "$RG" \
  --consumption-plan-location "$LOC" \
  --runtime python --runtime-version 3.11 --functions-version 4 \
  --storage-account "$STORAGE" --os-type Linux

# Wire the Open Targets endpoint + storage into app settings.
az functionapp config appsettings set --name "$FUNCAPP" --resource-group "$RG" \
  --settings OPENTARGETS_GRAPHQL_URL="https://api.platform.opentargets.org/api/v4/graphql"
```

Deploy a timer-triggered function that calls `associated_targets()` and uploads JSON to
the `associations` container with `func azure functionapp publish "$FUNCAPP"`.

### Alternative: Container job

If you prefer a container over Functions, build the repo into an image and run it on
Azure Container Apps Jobs:

```bash
az containerapp job create \
  --name job-targetdisc --resource-group "$RG" \
  --environment cae-targetdisc \
  --trigger-type Schedule --cron-expression "0 6 * * *" \
  --image <your-registry>/target-discovery:latest \
  --cpu 0.5 --memory 1Gi \
  --env-vars OPENTARGETS_GRAPHQL_URL="https://api.platform.opentargets.org/api/v4/graphql"
```

## 6. (Optional) Cosmos DB for normalized associations

```bash
az cosmosdb create --name cosmos-targetdisc-$RANDOM --resource-group "$RG" \
  --kind GlobalDocumentDB --default-consistency-level Session
```

Store one document per (disease, target) with the flattened datatype scores so the agent
can query without re-hitting the API.

## Cleanup

```bash
az group delete --name "$RG" --yes --no-wait
```
