# GQMRMed Bot

GQMRMed is an independent Telegram medical infographic generation system.

## Project boundaries

- Fully independent from QMRMed and QMRMed-Bot.
- No Telegram Mini App.
- Separate backend, database, queue, AI/image pipeline, storage, subscriptions, payments, and admin panel.
- The Telegram bot accepts medical topics, text, images, and supported files and produces original 9:16 medical infographics.

## Core architecture

```text
Telegram User
  -> GQMRMed Bot
  -> API / Orchestrator
  -> User / Subscription / Usage checks
  -> Durable DB Job
  -> Redis Queue
  -> Medical Research
  -> Evidence Validation
  -> Content Synthesis
  -> Visual Architect
  -> Image Generation
  -> SVG exact-text rendering
  -> PNG rasterization
  -> Medical/Visual QA boundary
  -> Durable Result Storage
  -> Telegram delivery + retry
```

## Foundation guarantees

- FREE entitlement is exactly 3 designs per UTC calendar day.
- PLUS entitlement is exactly 8 designs per UTC calendar day while an active 30-day subscription exists.
- PRO entitlement is exactly 15 designs per UTC calendar day while an active 90-day subscription exists.
- Quota reservations are atomic at the PostgreSQL level and are idempotent by generation job, so Telegram retries cannot consume the same slot twice.
- Telegram IDs use PostgreSQL BIGINT.
- Activation codes are stored only as SHA-256 hashes and are single-use.
- Provider transaction IDs and Telegram Stars invoice payloads are protected against duplicates.
- Billing events are recorded in an append-only ledger protected against update/delete mutation.
- Subscription resolution is server-authoritative and UTC-based; expired/cancelled entitlements never remain active because of a missing cron job.
- Same-plan purchases extend from the current expiry; stronger-plan upgrades start immediately and preserve remaining paid value; weaker-plan purchases are queued after the current entitlement.
- Generation jobs support text, image, document, audio, video, and mixed input through validated contracts and references.
- Job progress is bounded to 0..100 and lifecycle transitions are guarded.
- Queued jobs have durable dispatch state; PostgreSQL remains the source of truth and Redis delivery is at-least-once.
- RUNNING jobs use a heartbeat lease, preventing long-running valid generations from being mistaken for dead workers.
- Successful results have durable Telegram delivery state in job metadata and are retried after transient delivery/process failures.
- Failed generation releases its reserved usage; successful generation commits usage before delivery retry begins.
- No secrets are committed to the repository.
- Alembic migrations are versioned and CI validates the migration chain.
- `/health` and `/health/live` provide liveness checks; `/health/ready` verifies PostgreSQL and Redis before the service is considered ready.

## Medical intelligence

- PubMed E-utilities is the primary literature provider.
- Evidence records carry source IDs, PMID, title, abstract, publication year, provenance URL, and a bounded evidence score.
- Research results are deduplicated and missing-evidence conditions are surfaced as warnings.
- Synthesized medical claims must reference known evidence IDs; unknown or missing citations are rejected before visual planning.
- AI synthesis is provider-neutral, with local Ollama first and configured free external providers next. Paid providers remain disabled unless explicitly enabled.
- Visual architecture is selected deterministically from the medical topic and synthesized content.
- Illustration generation and exact text rendering are explicitly separated: the image model receives an illustration-only prompt while exact labels/text remain a renderer responsibility.
- Final artwork is rasterized to a deterministic 1080×1920 PNG for Telegram delivery.

## Media ingestion

- Telegram media is downloaded through a provider-neutral source adapter.
- Inputs are size-checked, MIME-normalized, hashed, and stored only temporarily during processing.
- PDF/TXT/Markdown/CSV extraction is local where possible.
- Images can use the configured multimodal AI extractor for OCR and medical diagram interpretation.
- Audio and video can use the configured transcription path; video audio extraction uses FFmpeg.
- Media is converted into synthesis-ready text before medical research, preserving user captions/context for mixed inputs.

## Subscription plans

| Plan | Price | Duration | Daily limit | Telegram Stars |
| --- | ---: | ---: | ---: | ---: |
| FREE | $0 | ongoing | 3 | — |
| PLUS | $5 | 30 days | 8 | 400 ⭐ |
| PRO | $20 | 90 days | 15 | 1,600 ⭐ |

Telegram's official documentation states that the amount a user pays to acquire Stars can vary by user/region due to VAT and other fees, and Telegram currently assigns a $0.013 reward value per Star to developers. The launch Star amounts therefore target approximately $5.20 and $20.80 of current reward value; they are not a promise that every user will pay exactly $5/$20 when acquiring Stars. citeturn3search0

Inside Telegram, GQMRMed sells a digital service. Telegram requires digital goods/services in bots to be sold exclusively using Telegram Stars (`XTR`), so the bot does not expose Mastercard, Zain Cash, bank-transfer, or other alternative payment instructions as an in-Telegram purchase path. citeturn6search0turn3search0

The bot requires explicit purchase-terms confirmation before creating a Stars invoice, validates the exact server-side order during `pre_checkout_query`, and grants access only after a verified `successful_payment`. Telegram also requires `/terms` and payment support for live digital-service sales; GQMRMed exposes `/terms` and `/paysupport`. citeturn6search0turn4search0

All successful Stars transactions persist the Telegram charge ID for audit/refund handling. Telegram documents `telegram_payment_charge_id` as the identifier needed for refunds. citeturn4search0

## Activation codes and admin operations

Activation codes are intended for operator-controlled grants and other approved administrative workflows. The admin panel generates single-use hashed codes and returns the plaintext code only at issuance time. The user activates a code with `/activate CODE`; the server validates the code, resolves the plan, applies the subscription lifecycle rules, and marks the code consumed in the same transaction.

## Payment and audit model

- Payment provider + transaction ID is unique.
- Telegram Stars invoice payload is unique and maps one invoice to one server-side pending order.
- Successful Stars payment must match user, currency, amount, plan, and pending order before activation.
- Replayed successful-payment updates are idempotent.
- Manual approval cannot be used to bypass the Telegram Stars settlement path for a Stars order.
- Refund transitions are locked and auditable.
- Billing ledger records creation, approval, rejection, and refund events and is append-only at the database trigger level.

## Stack

- Telegram: aiogram
- API: FastAPI
- Database: PostgreSQL + SQLAlchemy + Alembic
- Queue: Redis
- Medical research: NCBI PubMed E-utilities
- Medical synthesis: provider abstraction + Ollama/OpenAI-compatible/OpenAI adapters
- AI/image pipeline: ComfyUI API adapter, ready for a configured FLUX.2 Klein workflow
- Exact layout: SVG renderer + CairoSVG rasterization
- Storage: filesystem result adapter for local/dev operation; S3-compatible object storage adapter for durable production results
- Media: Telegram download + local document extraction + optional AI OCR/transcription + FFmpeg
- Deployment: Docker + managed application hosting
- Quality: Ruff, MyPy, Pytest, migration validation, production container build validation

## Build stages

1. Project foundation — complete
2. Core system foundation — complete
3. Telegram bot + user onboarding + usage enforcement — implemented
4. Research, verification, synthesis, and visual architecture — implemented
5. Image generation + exact-text renderer — wired
6. Queue, live progress, heartbeat recovery, media ingestion, and durable Telegram delivery — implemented
7. Subscriptions, activation, Telegram Stars payments, immutable billing audit, and private admin panel — implemented
8. End-to-end testing, deployment, hardening, monitoring, and release — in progress

## Current status

The application-level generation path is implemented: Telegram jobs are durably queued, media is normalized when necessary, medical research is performed against PubMed, content is synthesized through the configured provider router, a visual architecture is selected, a ComfyUI illustration is generated, exact SVG text is composed, the final artwork is rasterized to PNG, persisted, and delivered to Telegram with durable retry support. Worker heartbeats prevent false recovery of legitimate long-running jobs.

Subscription entitlements, activation codes, Telegram Stars checkout, payment replay protection, idempotent usage reservations, immutable billing audit, and the private admin API/panel are implemented. The launch pricing and daily limits are enforced from the database plan records: FREE 3/day, PLUS 8/day for 30 days, and PRO 15/day for 90 days.

The remaining release dependencies are external infrastructure/configuration: a real Telegram token, production PostgreSQL/Redis endpoints, an AI provider credential or reachable Ollama instance, persistent result storage credentials or a persistent volume, and a ComfyUI deployment with a concrete FLUX.2 Klein API-format workflow/model. These external credentials and model weights are intentionally not committed to the repository.

CI is the source of truth for static typing, linting, migrations, package resolution, automated tests, and production container buildability after each push. Passing CI does not replace an end-to-end staging smoke test against the real external services.
