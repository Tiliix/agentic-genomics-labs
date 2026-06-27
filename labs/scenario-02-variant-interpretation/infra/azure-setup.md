# Azure provisioning (`az` CLI)

Provision the Azure resources the lab uses: **Azure OpenAI** (required),
**Azure AI Search** (optional literature RAG), and a **Storage account** (VCFs +
memo archive). Run these once. Requires the
[Azure CLI](https://learn.microsoft.com/cli/azure/) and `az login`.

> Azure OpenAI requires approved access on your subscription. Region
> availability for models (e.g. `gpt-4o`) varies — check the
> [model availability table](https://learn.microsoft.com/azure/ai-services/openai/concepts/models).

```bash
# ---------------------------------------------------------------------------
# 0. Variables (edit these)
# ---------------------------------------------------------------------------
RG=rg-variant-lab
LOCATION=eastus2
AOAI=aoai-variant-lab-$RANDOM         # must be globally unique
SEARCH=search-variant-lab-$RANDOM     # must be globally unique
STORAGE=stvariantlab$RANDOM           # 3-24 lowercase alphanumeric, unique
DEPLOYMENT=gpt-4o
MODEL=gpt-4o
MODEL_VERSION=2024-08-06              # check current availability

# ---------------------------------------------------------------------------
# 1. Resource group
# ---------------------------------------------------------------------------
az group create --name "$RG" --location "$LOCATION"

# ---------------------------------------------------------------------------
# 2. Azure OpenAI account + chat deployment
# ---------------------------------------------------------------------------
az cognitiveservices account create \
  --name "$AOAI" --resource-group "$RG" --location "$LOCATION" \
  --kind OpenAI --sku S0 --yes

az cognitiveservices account deployment create \
  --name "$AOAI" --resource-group "$RG" \
  --deployment-name "$DEPLOYMENT" \
  --model-name "$MODEL" --model-version "$MODEL_VERSION" \
  --model-format OpenAI \
  --sku-capacity 10 --sku-name Standard

# Endpoint + key for your .env
az cognitiveservices account show \
  --name "$AOAI" --resource-group "$RG" \
  --query "properties.endpoint" -o tsv
az cognitiveservices account keys list \
  --name "$AOAI" --resource-group "$RG" \
  --query "key1" -o tsv

# Keyless (recommended): grant yourself the data-plane role instead of a key.
ME=$(az ad signed-in-user show --query id -o tsv)
AOAI_ID=$(az cognitiveservices account show --name "$AOAI" \
  --resource-group "$RG" --query id -o tsv)
az role assignment create --assignee "$ME" \
  --role "Cognitive Services OpenAI User" --scope "$AOAI_ID"
# Then set AZURE_OPENAI_USE_AAD=true in .env (no key needed).

# ---------------------------------------------------------------------------
# 3. Azure AI Search  (OPTIONAL -- literature RAG citations)
# ---------------------------------------------------------------------------
az search service create \
  --name "$SEARCH" --resource-group "$RG" \
  --sku basic --location "$LOCATION"

az search admin-key show \
  --service-name "$SEARCH" --resource-group "$RG" \
  --query "primaryKey" -o tsv
echo "Search endpoint: https://$SEARCH.search.windows.net"
# Create the 'variant-literature' index in the portal or via the REST API,
# then point AZURE_SEARCH_* in .env at it.

# ---------------------------------------------------------------------------
# 4. Storage account  (VCF inputs + memo outputs)
# ---------------------------------------------------------------------------
az storage account create \
  --name "$STORAGE" --resource-group "$RG" \
  --location "$LOCATION" --sku Standard_LRS

az storage container create --account-name "$STORAGE" --name vcfs --auth-mode login
az storage container create --account-name "$STORAGE" --name memos --auth-mode login

# ---------------------------------------------------------------------------
# 5. Populate .env
# ---------------------------------------------------------------------------
# AZURE_OPENAI_ENDPOINT   <- step 2 endpoint
# AZURE_OPENAI_DEPLOYMENT <- $DEPLOYMENT
# AZURE_OPENAI_API_KEY    <- step 2 key  (or AZURE_OPENAI_USE_AAD=true)
# AZURE_SEARCH_ENDPOINT / _API_KEY / _INDEX  <- step 3 (optional)
```

## Cleanup

```bash
az group delete --name "$RG" --yes --no-wait
```

> ⚠️ Research/education only. Do not load real patient data into these
> resources without appropriate compliance review (HIPAA/GDPR, BAA, etc.).
