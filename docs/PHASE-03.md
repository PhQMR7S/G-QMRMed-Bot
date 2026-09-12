# Phase 03 — Telegram bot + onboarding + usage enforcement

## Implemented

- Independent aiogram Telegram bot runtime; no Mini App.
- `/start`, `/help`, `/plans`, and `/activate CODE` commands.
- Telegram identity provisioning without reactivating blocked users.
- Text, image, document, audio, voice, video, and mixed-input intake.
- Generation requests are validated through the shared Pydantic contract.
- Job creation and usage reservation occur in one PostgreSQL transaction.
- FREE quota remains exactly 3 generations per UTC calendar day.
- Paid plans with unlimited daily quota are supported by the same reservation ledger.
- Durable DB-to-Redis dispatch state protects queued jobs across process restarts.
- Dispatcher is at-least-once and the database remains the source of truth.
- Bot and API can run from the same image using `SERVICE_ROLE=bot` or `SERVICE_ROLE=api`.

## Important boundary

Phase 03 only accepts and queues work. Medical research, image generation, exact-text rendering, live progress, QA, and result delivery remain later pipeline phases. No placeholder image is returned and no web image is treated as a generated result.

## Runtime

For the bot service set:

```text
SERVICE_ROLE=bot
TELEGRAM_BOT_TOKEN=<secret>
DATABASE_URL=<postgres>
REDIS_URL=<redis>
```

For the API service set `SERVICE_ROLE=api`.
