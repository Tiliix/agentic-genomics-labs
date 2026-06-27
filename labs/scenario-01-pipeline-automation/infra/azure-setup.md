# Azure setup — provisioning the pipeline assistant

These `az` CLI commands stand up everything the lab needs in Azure: a resource
group, an Azure OpenAI resource + tool-calling model deployment, a storage
account for staging data/results, and a compute option (Azure ML job **or**
Azure Container Instance) to run the pipeline at scale.

> Prerequisites: [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli),
> `az login`, and a subscription with access to Azure OpenAI
> (request access at https://aka.ms/oai/access if needed).

Set some shared variables first:

```bash
export LOCATION="eastus"
export RG="rg-rnaseq-agent"
export AOAI_NAME="aoai-rnaseq-$RANDOM"
export STORAGE_NAME="strnaseq$RANDOM"          # 3-24 lowercase chars, globally unique
export DEPLOYMENT_NAME="gpt-4o"
```

## 1. Resource group

```bash
az group create --name "$RG" --location "$LOCATION"
```

## 2. Azure OpenAI resource + model deployment

```bash
# Create the Azure OpenAI (Cognitive Services) account.
az cognitiveservices account create \
  --name "$AOAI_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --kind OpenAI \
  --sku S0 \
  --yes

# Deploy a tool-calling-capable chat model. Adjust model/version to what's
# available in your region (check: az cognitiveservices account list-models ...).
az cognitiveservices account deployment create \
  --name "$AOAI_NAME" \
  --resource-group "$RG" \
  --deployment-name "$DEPLOYMENT_NAME" \
  --model-name "gpt-4o" \
  --model-version "2024-08-06" \
  --model-format OpenAI \
  --sku-name "Standard" \
  --sku-capacity 10

# Grab the endpoint and key for your .env
az cognitiveservices account show \
  --name "$AOAI_NAME" --resource-group "$RG" \
  --query "properties.endpoint" -o tsv

az cognitiveservices account keys list \
  --name "$AOAI_NAME" --resource-group "$RG" \
  --query "key1" -o tsv
```

Put those into `.env`:

```
AZURE_OPENAI_ENDPOINT=<endpoint from above>
AZURE_OPENAI_API_KEY=<key1 from above>
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

## 3. Storage account (stage FASTQs / counts / results)

```bash
az storage account create \
  --name "$STORAGE_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2

# Connection string for AZURE_STORAGE_CONNECTION_STRING in .env
az storage account show-connection-string \
  --name "$STORAGE_NAME" --resource-group "$RG" -o tsv

# A container to hold pipeline artifacts
az storage container create \
  --name "rnaseq" \
  --account-name "$STORAGE_NAME" \
  --auth-mode login
```

Upload local data / download results:

```bash
az storage blob upload-batch \
  --account-name "$STORAGE_NAME" \
  --destination rnaseq/data \
  --source ./data --auth-mode login

az storage blob download-batch \
  --account-name "$STORAGE_NAME" \
  --source rnaseq/data/results \
  --destination ./data/results --auth-mode login
```

## 4a. Run on Azure Container Instances (simplest)

Build and push the image to Azure Container Registry, then run it as a one-shot
container that executes the pipeline.

```bash
export ACR_NAME="acrrnaseq$RANDOM"

az acr create --resource-group "$RG" --name "$ACR_NAME" --sku Basic --admin-enabled true

# Build directly in ACR (needs a Dockerfile that pip-installs requirements.txt
# and copies the repo; see note below).
az acr build --registry "$ACR_NAME" --image rnaseq-agent:latest .

# Run the pipeline (no LLM) as a container job. Pass secrets as env vars.
az container create \
  --resource-group "$RG" \
  --name rnaseq-job \
  --image "$ACR_NAME.azurecr.io/rnaseq-agent:latest" \
  --registry-login-server "$ACR_NAME.azurecr.io" \
  --cpu 2 --memory 4 \
  --restart-policy Never \
  --environment-variables \
      AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
      AZURE_OPENAI_DEPLOYMENT="$DEPLOYMENT_NAME" \
  --secure-environment-variables \
      AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
  --command-line "python src/agent.py"
```

> A minimal `Dockerfile` for ACI:
> ```dockerfile
> FROM python:3.11-slim
> WORKDIR /app
> COPY requirements.txt .
> RUN pip install --no-cache-dir -r requirements.txt
> COPY . .
> CMD ["python", "src/agent.py"]
> ```

## 4b. Run as an Azure ML job (for scale / tracking)

```bash
export ML_WS="mlw-rnaseq"

# Install the ML extension once
az extension add -n ml -y

# Workspace
az ml workspace create --name "$ML_WS" --resource-group "$RG" --location "$LOCATION"

# Submit a command job (job.yml references the repo as the code asset and runs
# the pipeline). Example job.yml:
#
#   $schema: https://azuremlschemas.azureedge.net/latest/commandJob.schema.json
#   code: .
#   command: python src/pipeline.py
#   environment:
#     image: mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04
#     conda_file: ./conda.yml          # or pip install -r requirements.txt
#   compute: azureml:cpu-cluster
#
az ml job create --file ./job.yml --resource-group "$RG" --workspace-name "$ML_WS"
```

## 5. Clean up

```bash
az group delete --name "$RG" --yes --no-wait
```

Deleting the resource group removes the Azure OpenAI resource, storage account,
ACR/ACI, and ML workspace in one shot to avoid ongoing charges.
