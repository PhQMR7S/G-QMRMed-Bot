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
- AI/image pipeline: provider abstraction, with ComfyUI/FLUX planned for the visual layer
- Exact layout: SVG/HTML renderer
- Storage: S3-compatible abstraction
- Deployment: Docker + managed application hosting
- Quality: Ruff, MyPy, Pytest, migration validation

## Build stages

1. Project foundation — complete
2. Core system foundation — complete
3. Telegram bot + user onboarding + usage enforcement — implemented
4. Research, verification, synthesis, and visual architecture
5. Image generation + exact-text renderer
6. Queue, live progress, medical QA, visual QA, and failure recovery
7. Subscriptions, activation, payments, and private admin panel
8. End-to-end testing, deployment, hardening, monitoring, and release

## Current status

Phase 2 passed the full CI quality gate. Phase 3 Telegram intake and onboarding are implemented. The bot does not yet generate a placeholder image: generation/research/rendering are intentionally isolated for the following phases.
