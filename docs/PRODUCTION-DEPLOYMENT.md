# Production deployment contract

GQMRMed Bot is a long-running Telegram + queue + worker system. The production runtime is intentionally split into three roles:

- `api` — FastAPI health/admin surface.
- `bot` — Telegram polling/ingestion process.
- `worker` — durable generation worker and dispatch recovery.

PostgreSQL is the source of truth for jobs and usage. Redis is the queue/transport layer. Generated results must live on a persistent volume or S3-compatible object storage.

## Required external dependencies

Before production start, provide:

- PostgreSQL with the database URL in `DATABASE_URL`.
- Redis with `REDIS_URL`.
- A real Telegram bot token in `TELEGRAM_BOT_TOKEN`.
- `ADMIN_SECRET` with at least 32 characters.
- A reachable ComfyUI API in `COMFYUI_BASE_URL` and a concrete API-format workflow in `COMFYUI_WORKFLOW_JSON`.
- At least one configured AI provider according to `AI_PROVIDER_ORDER`.
- Persistent result storage. For a single host, the production compose volume is sufficient; for multiple hosts, configure S3-compatible storage.

## Release order

1. Build the application image from the exact Git commit being released.
2. Run `alembic upgrade head` once as the release migration step.
3. Start `api`, `bot`, and `worker` from the same image/commit.
4. Verify `/health/live` on the API process.
5. Verify `/health/ready` reports both PostgreSQL and Redis as `ok`.
6. Send a controlled Telegram generation request and verify the complete durable path: job creation → queue → worker → research → synthesis → rendering → stored result → Telegram delivery.
7. Verify a failed Telegram delivery can be retried without regenerating the image.

## Compose

`compose.production.yml` provides the three application roles and a one-shot migration container. It deliberately does **not** bundle PostgreSQL, Redis, Ollama, or ComfyUI: those components are infrastructure dependencies and should be supplied by the production environment rather than recreated on every application deployment.

Create a production `.env` from `.env.example`; never commit real credentials or workflow secrets.

Start the release with:

```bash
docker compose --env-file .env -f compose.production.yml up -d --build
```

Inspect the rollout with:

```bash
docker compose --env-file .env -f compose.production.yml ps
docker compose --env-file .env -f compose.production.yml logs --tail=200 api bot worker
```

## Health semantics

- `/health` and `/health/live` are liveness-only and do not require external dependencies.
- `/health/ready` checks PostgreSQL and Redis and returns HTTP 503 until both are reachable.
- Readiness is therefore suitable for load balancers/orchestrators; liveness is safe for restart checks.

## Telegram mode

The production compose uses the dedicated `bot` role, which is compatible with Telegram polling. If webhook delivery is introduced later, it must be wired as a separate ingress contract and must not cause two consumers to process the same Telegram updates.

## Migration safety

Do not run `alembic upgrade head` from every API/worker replica. The migration container is intentionally one-shot so schema changes happen before application replicas start.

## Multi-host storage

When more than one application host can execute workers, local `/data/results` is not sufficient for cross-host result retrieval. Configure `S3_ENDPOINT`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`, and `S3_REGION`, and use the S3-compatible result store. Keep PostgreSQL and Redis reachable from every role.

## Final external gate

The repository can validate code, packaging, migrations, and deterministic tests without production credentials. A real end-to-end generation cannot be truthfully marked complete until the external Telegram, PostgreSQL, Redis, AI, ComfyUI, and persistent-storage endpoints are supplied and exercised.
