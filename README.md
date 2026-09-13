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
- Quota reservations are atomic at the PostgreSQL level and are released on failed/cancelled work.
- Telegram IDs use PostgreSQL BIGINT.
- Activation codes are stored only as SHA-256 hashes and are single-use.
- Provider transaction IDs are protected against duplicates per provider.
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
- AI synthesis is provider-neutral, with local Ollama first, OpenAI-compatible gateways second, and OpenAI Responses as a configurable fallback.
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

| Plan | Price | Duration | Daily limit |
| --- | ---: | ---: | ---: |
| FREE | $0 | ongoing | 3 |
| PLUS | $5 | 30 days | unlimited |
| PRO | $20 | 365 days | unlimited |

Payment approval is transactional: an approved paid payment creates the corresponding subscription, while invalid plan/amount transitions are rejected. `/buy PLUS` and `/buy PRO` currently create manual pending payment requests; provider-specific payment gateways are not claimed as integrated until their APIs and credentials are configured.

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
7. Subscriptions, activation, payments, and private admin panel — implemented
8. End-to-end testing, deployment, hardening, monitoring, and release — in progress

## Current status

The application-level generation path is implemented and CI-verified: Telegram jobs are durably queued, media is normalized when necessary, medical research is performed against PubMed, content is synthesized through the configured provider router, a visual architecture is selected, a ComfyUI illustration is generated, exact SVG text is composed, the final artwork is rasterized to PNG, persisted, and delivered to Telegram with durable retry support. Worker heartbeats prevent false recovery of legitimate long-running jobs.

Subscriptions and activation codes are implemented, and the private admin API/panel can issue codes and approve/reject/refund payments. Approving a valid paid payment now grants the purchased subscription transactionally. Result storage can use an S3-compatible object store so worker restarts or ephemeral application filesystems do not discard completed images.

The remaining release dependencies are external infrastructure/configuration: a real Telegram token, production PostgreSQL/Redis endpoints, an AI provider credential or reachable Ollama instance, persistent result storage credentials or a persistent volume, and a ComfyUI deployment with a concrete FLUX.2 Klein API-format workflow/model. These external credentials and model weights are intentionally not committed to the repository.

CI is the source of truth for static typing, linting, migrations, package resolution, automated tests, and production container buildability after each push. Passing CI does not replace an end-to-end staging smoke test against the real external services.
