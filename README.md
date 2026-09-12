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
  -> SVG/HTML exact-text rendering
  -> Medical QA + Visual QA
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
- No secrets are committed to the repository.
- Alembic migrations are versioned and CI validates the migration chain.

## Phase 4 medical intelligence

- PubMed E-utilities is the primary literature provider.
- Evidence records carry source IDs, PMID, title, abstract, publication year, provenance URL, and a bounded evidence score.
- Research results are deduplicated and missing-evidence conditions are surfaced as warnings.
- Synthesized medical claims must reference known evidence IDs; unknown or missing citations are rejected before visual planning.
- AI synthesis is provider-neutral, with an OpenAI Responses adapter using `httpx`.
- Visual architecture is selected deterministically from the medical topic and synthesized content.
- Illustration generation and exact text rendering are explicitly separated: the future image model receives an illustration-only prompt while exact labels/text remain a renderer responsibility.
- All visual plans are 9:16 and include the GQMRMed watermark metadata.

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
- Medical synthesis: provider abstraction + OpenAI Responses adapter
- AI/image pipeline: provider abstraction, with ComfyUI/FLUX planned for the visual layer
- Exact layout: SVG/HTML renderer
- Storage: S3-compatible abstraction
- Deployment: Docker + managed application hosting
- Quality: Ruff, MyPy, Pytest, migration validation

## Build stages

1. Project foundation — complete
2. Core system foundation — complete
3. Telegram bot + user onboarding + usage enforcement — implemented
4. Research, verification, synthesis, and visual architecture — implemented
5. Image generation + exact-text renderer
6. Queue, live progress, medical QA, visual QA, and failure recovery
7. Subscriptions, activation, payments, and private admin panel
8. End-to-end testing, deployment, hardening, monitoring, and release

## Current status

Phase 2 passed the full CI quality gate. Phase 3 Telegram intake/onboarding/usage and durable dispatch are implemented. Phase 4 medical research, evidence-linked synthesis, and visual architecture are implemented with automated tests. The final image pipeline is intentionally not claimed complete until image generation, exact rendering, QA, and Telegram result delivery are wired in the following phases.
