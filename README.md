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
  -> Telegram final image
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
- Stale RUNNING jobs are recovered conservatively and their reservations released.
- No secrets are committed to the repository.
- Alembic migrations are versioned and CI validates the migration chain.

## Medical intelligence

- PubMed E-utilities is the primary literature provider.
- Evidence records carry source IDs, PMID, title, abstract, publication year, provenance URL, and a bounded evidence score.
- Research results are deduplicated and missing-evidence conditions are surfaced as warnings.
- Synthesized medical claims must reference known evidence IDs; unknown or missing citations are rejected before visual planning.
- AI synthesis is provider-neutral, with local Ollama first, OpenAI-compatible gateways second, and OpenAI Responses as a configurable fallback.
- Visual architecture is selected deterministically from the medical topic and synthesized content.
- Illustration generation and exact text rendering are explicitly separated: the image model receives an illustration-only prompt while exact labels/text remain a renderer responsibility.
- Final artwork is rasterized to a deterministic 1080×1920 PNG for Telegram delivery.

## Subscription plans

| Plan | Price | Duration | Daily limit |
| --- | ---: | ---: | ---: |
| FREE | $0 | ongoing | 3 |
| PLUS | $5 | 30 days | unlimited |
| PRO | $20 | 365 days | unlimited |

## Stack

- Telegram: aiogram
- API: FastAPI
- Database: PostgreSQL + SQLAlchemy + Alembic
- Queue: Redis
- Medical research: NCBI PubMed E-utilities
- Medical synthesis: provider abstraction + Ollama/OpenAI-compatible/OpenAI adapters
- AI/image pipeline: ComfyUI API adapter, ready for a configured FLUX.2 Klein workflow
- Exact layout: SVG renderer + CairoSVG rasterization
- Storage: filesystem result adapter now, S3-compatible abstraction retained for production storage
- Deployment: Docker + managed application hosting
- Quality: Ruff, MyPy, Pytest, migration validation

## Build stages

1. Project foundation — complete
2. Core system foundation — complete
3. Telegram bot + user onboarding + usage enforcement — implemented
4. Research, verification, synthesis, and visual architecture — implemented
5. Image generation + exact-text renderer — wired
6. Queue, live progress, failure recovery, and Telegram delivery — wired
7. Subscriptions, activation, payments, and private admin panel — next
8. End-to-end testing, deployment, hardening, monitoring, and release — next

## Current status

The repository now contains the complete application-level text-to-infographic execution path: a Telegram job is durably queued, researched against PubMed, synthesized through the configured provider router, assigned a visual architecture, rendered with a real ComfyUI illustration provider, composed with exact SVG text, rasterized to PNG, persisted, and delivered back to Telegram. The remaining deployment dependency is external infrastructure/configuration: a real Telegram token, database/Redis endpoints, an AI provider credential or reachable Ollama instance, and a ComfyUI deployment with a concrete API-format workflow/model.
