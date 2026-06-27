# Azure setup — keyless Azure OpenAI for the Multi-Omics Tumor Board lab

> **RESEARCH / EDUCATION ONLY.** Nothing here is for clinical use.

This lab uses **keyless** authentication by default: your agent gets a short-lived
Azure AD token via `DefaultAzureCredential` instead of a long-lived API key. You
sign in once with `az login` and grant your identity the **Cognitive Services
OpenAI User** role on the Azure OpenAI resource.

## 0. Prerequisites

- An Azure subscription with access to **Azure OpenAI**.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (`az`).
- The model you want deployed (e.g. `gpt-4o`).

## 1. Sign in and pick the subscription

```bash
az login
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"
```

## 2. Create a resource group + Azure OpenAI resource

```bash
RG=rg-omics-tumorboard
LOC=eastus
AOAI=aoai-omics-$RANDOM            # must be globally unique

az group create --name "$RG" --location "$LOC"

az cognitiveservices account create \
  --name "$AOAI" \
  --resource-group "$RG" \
  --location "$LOC" \
  --kind OpenAI \
  --sku S0 \
  --custom-domain "$AOAI"          # custom domain is required for AAD token auth
```

## 3. Deploy a chat model (tool-calling capable)

```bash
az cognitiveservices account deployment create \
  --name "$AOAI" \
  --resource-group "$RG" \
  --deployment-name gpt-4o \
  --model-name gpt-4o \
  --model-version "2024-08-06" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard
```

> The **deployment name** (`gpt-4o` above) is what goes in `AZURE_OPENAI_DEPLOYMENT`,
> not the base model name.

## 4. Grant yourself the keyless role

```bash
# Your signed-in identity:
ME=$(az ad signed-in-user show --query id -o tsv)

# Scope = the Azure OpenAI resource:
SCOPE=$(az cognitiveservices account show \
  --name "$AOAI" --resource-group "$RG" --query id -o tsv)

az role assignment create \
  --assignee "$ME" \
  --role "Cognitive Services OpenAI User" \
  --scope "$SCOPE"
```

Role propagation can take a minute or two.

## 5. Get the endpoint and fill in `.env`

```bash
az cognitiveservices account show \
  --name "$AOAI" --resource-group "$RG" \
  --query properties.endpoint -o tsv
```

Copy `.env.example` to `.env` and set:

```ini
AZURE_OPENAI_ENDPOINT=https://<AOAI>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_API_KEY=            # leave BLANK for keyless AAD
```

Because the key is blank, `src/agent.py` builds the client with:

```python
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(exclude_managed_identity_credential=True),
    "https://cognitiveservices.azure.com/.default",
)
AzureOpenAI(azure_endpoint=ENDPOINT, azure_ad_token_provider=token_provider,
            api_version=API_VERSION)
```

## 6. Run it

```bash
python scripts/download_data.py            # writes data/case_A|B|C.json
python scripts/run_cases.py                # LLM agent: see the divergent tool paths
```

## Cost & cleanup

A few runs cost cents. Delete everything when done:

```bash
az group delete --name "$RG" --yes --no-wait
```

## Troubleshooting

- **401 / token errors** → re-run `az login`; confirm the role assignment landed
  (`az role assignment list --assignee "$ME" --scope "$SCOPE" -o table`).
- **`DeploymentNotFound`** → `AZURE_OPENAI_DEPLOYMENT` must equal the deployment
  name from step 3, not the model name.
- **Keyless fails locally but key works** → your custom domain (step 2) is required
  for AAD tokens; recreate with `--custom-domain` if you skipped it.
- **No Azure yet?** Everything except `src/agent.py` runs offline. Use
  `python scripts/run_cases.py --router-only` and `pytest tests/test_router.py`.
