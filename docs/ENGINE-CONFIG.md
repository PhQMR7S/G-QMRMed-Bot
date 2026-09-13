# GQMRMed Engine Configuration

This document defines the configuration boundary for the medical generation engine before the Telegram Bot phase.

## Providers

### Medical synthesis

- Provider: OpenAI Responses API
- Base URL: `https://api.openai.com/v1`
- Default model: `gpt-5.6-luna`
- Secret: `AI_API_KEY`

The model is used for structured medical content synthesis only. Evidence retrieval and validation remain separate stages.

### Illustration

- Provider: ComfyUI HTTP API
- Model: `FLUX.2 Klein 4B`
- Endpoint: `COMFYUI_BASE_URL`
- Workflow identifier: `COMFYUI_WORKFLOW_ID`
- Output: 1080×1920, 9:16

The image model is an illustration layer. It must not be trusted for exact readable medical text, numeric facts, doses, labels, or clinical claims.

## Infrastructure

- PostgreSQL: Supabase
- Queue: Render Key Value / Redis
- Object storage: S3-compatible storage abstraction
- Telegram credentials: intentionally deferred until the Bot phase
- Payment credentials: intentionally deferred until the Payments phase
- Admin credentials: intentionally deferred until the Admin phase

## Secrets policy

No real API keys, database passwords, bot tokens, ComfyUI credentials, or payment secrets belong in GitHub. `.env.example` contains names and safe placeholders only. Production secrets are injected by the deployment environment.

## Model registry principle

Model IDs are configuration, not business logic. Changing the synthesis model or illustration model must not require rewriting the medical pipeline.

## Current deployment preparation

Render Key Value `gqmrmed-redis` has been provisioned in Frankfurt on the free tier with persistence disabled. This is appropriate for the queue boundary during initial development; PostgreSQL remains in Supabase.

The Telegram Bot is deliberately not deployed or wired at this stage.
