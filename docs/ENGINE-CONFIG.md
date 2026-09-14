# GQMRMed Engine Configuration

This document defines the configuration boundary for the medical generation engine before and during the Telegram Bot phase.

## Providers

### Medical synthesis

- Provider: configured provider abstraction
- Base URL/model: environment configuration
- Secret: `AI_API_KEY` or the selected provider credential

The model is used for structured medical content synthesis only. Evidence retrieval and validation remain separate stages.

### Illustration

- Provider: ComfyUI HTTP API or the deterministic procedural fallback
- Model: configured by the ComfyUI workflow
- Endpoint: `COMFYUI_BASE_URL`
- Workflow: `COMFYUI_WORKFLOW_JSON`
- Canonical output: 1080×1350, 4:5

The image model is an illustration layer. It must not be trusted for exact readable medical text, numeric facts, doses, labels, or clinical claims.

## Infrastructure

- PostgreSQL: configured relational database
- Queue: Redis-compatible queue
- Object storage: S3-compatible storage abstraction
- Telegram credentials: supplied only through deployment secrets
- Payment credentials: supplied only through deployment secrets
- Admin credentials: supplied only through deployment secrets

## Secrets policy

No real API keys, database passwords, bot tokens, ComfyUI credentials, or payment secrets belong in GitHub. `.env.example` contains names and safe placeholders only. Production secrets are injected by the deployment environment.

## Model registry principle

Model IDs are configuration, not business logic. Changing the synthesis model or illustration model must not require rewriting the medical pipeline.

## Current deployment preparation

External infrastructure is intentionally separated from the repository contract. CI validates the application, migrations, production Compose contract, and container build without fabricating external model credentials or model weights.
