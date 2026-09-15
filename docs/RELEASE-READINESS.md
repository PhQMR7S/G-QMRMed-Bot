# Release readiness

The application path is ready for staging integration testing after CI validation.

## Automated gates

- Python compilation
- Alembic migration-chain validation
- Ruff linting
- MyPy typing
- Pytest suite
- Production release gate
- Production Compose contract
- Production container build
- Production import smoke test

## Required staging configuration

Before the first real Telegram generation test, configure:

- `TELEGRAM_BOT_TOKEN`
- PostgreSQL `DATABASE_URL`
- Redis `REDIS_URL`
- `AI_API_KEY` for the OpenAI text/image path, unless an explicitly configured alternative synthesis/image path is used
- persistent result storage (`S3_*` or the production results volume)
- external PubMed/network access

The first staging test should cover `/start`, `/plans`, `/terms`, `/paysupport`, text generation, a natural-language design instruction, a media input, quota exhaustion, successful Telegram delivery, and a forced generation failure to verify quota release.

Payment readiness: Telegram requires a clear `/terms` path and explicit user agreement before purchase; digital goods/services sold inside Telegram use Stars (`XTR`).
