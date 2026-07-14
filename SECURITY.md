# Security Policy

## Secrets & credentials

This repository contains **no credentials**. Every lab reads its Azure (or GCP)
configuration from environment variables at runtime.

- **Never commit a real `.env`.** Each scenario ships a `.env.example` template —
  copy it locally and fill in your own values:

  ```bash
  cp labs/<scenario>/.env.example labs/<scenario>/.env
  ```

  `.env`, `.env.*` (except `*.example`) and private keys (`*.pem`, `*.key`,
  `*.pfx`) are git-ignored repo-wide — see [.gitignore](.gitignore).
- **Prefer keyless auth.** The Azure labs support Microsoft Entra ID
  (`DefaultAzureCredential` / `az login`), so no API key is required — leave
  `AZURE_OPENAI_API_KEY` unset to use it.
- **Do not paste** resource endpoints, tenant/subscription IDs, or account names
  into code, comments, or committed documents.

## Automated secret scanning

A [gitleaks](https://github.com/gitleaks/gitleaks) pre-commit hook blocks commits
that contain secrets. Enable it once per clone:

```bash
pip install pre-commit
pre-commit install
```

Scan on demand (including full history):

```bash
pre-commit run gitleaks --all-files
# or, with gitleaks installed directly:
gitleaks detect --source .
```

We also recommend enabling **GitHub Secret Scanning + Push Protection**
(repo → *Settings → Code security*).

## If a secret is ever committed

1. **Rotate/revoke it immediately** (regenerate the key, or switch to keyless auth).
2. Purge it from history (`git filter-repo` or the BFG) and force-push.
3. Treat the exposed value as compromised regardless of removal.

## Reporting a vulnerability

Please use the repository's **Security → Report a vulnerability** tab
(private disclosure) rather than opening a public issue.
