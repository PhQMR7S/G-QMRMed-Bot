# GQMRMed Engine Configuration

This document defines the configuration boundary for the medical generation engine before and during the Telegram Bot phase.

## Providers

### Medical synthesis

- Provider: configured provider abstraction
- Base URL/model: environment configuration
- Secret: `AI_API_KEY` or the selected provider credential

The model is used for structured medical content synthesis only. Evidence retrieval and validation remain separate stages.

### Illustration

- Default provider: OpenAI GPT-Image-2
- Default order: `IMAGE_PROVIDER_ORDER=openai,procedural`
- Model: `OPENAI_IMAGE_MODEL` (default `gpt-image-2`)
- Quality: `OPENAI_IMAGE_QUALITY` (default `medium`)
- Timeout: `OPENAI_IMAGE_TIMEOUT_SECONDS`
- Canonical output: **1024×1536, 2:3**

OpenAI receives an illustration-only prompt. The deterministic QMRMed compositor owns exact medical text, labels, numbers, cards, branding and disclaimer. ComfyUI and other image providers remain optional fallbacks and are not required by the default production path.

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
