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

Never put real credentials, Telegram tokens, API keys, S3 secrets, or ComfyUI workflow credentials in Git.

## Pre-release gate

Run the configuration gate from the release host with the real `.env` loaded, without printing the environment:

```bash
set -a
source .env
set +a
bash scripts/release-gate.sh
```

The gate verifies production mode, required dependencies, minimum admin-secret length, valid non-empty ComfyUI workflow JSON, at least one usable AI provider, and all-or-none S3 configuration. It does not print credential values.

Then validate the exact Compose contract:

```bash
docker compose --env-file .env -f compose.production.yml config --quiet
```

Build from the exact Git commit being released and record the image digest:

```bash
git rev-parse HEAD
docker compose --env-file .env -f compose.production.yml build
```

Do not mix images built from different commits in the same release.

## Release order

1. Check out the exact release commit and verify `git rev-parse HEAD`.
2. Run `bash scripts/release-gate.sh` with the production environment loaded.
3. Validate `docker compose ... config --quiet`.
4. Build the application image from that exact commit.
5. Run `alembic upgrade head` once through the one-shot `migrate` service.
6. Start `api`, `bot`, and `worker` from the same image/commit.
7. Verify `/health/live` on the API process.
8. Verify `/health/ready` reports both PostgreSQL and Redis as `ok`.
9. Verify the bot is connected to Telegram and only one polling consumer is active.
10. Send one controlled Telegram generation request and verify the complete durable path: job creation → quota reservation → queue → worker lease → research → synthesis → evidence validation → architecture → illustration → SVG QA → PNG QA → persistent result → Telegram delivery.
11. Verify a failed Telegram delivery can be retried without regenerating the image or consuming another usage unit.
12. Verify duplicate worker delivery/retry is idempotent.
13. Verify the free quota is exactly three successful reservations per UTC calendar day and paid-plan limits match the active entitlement.
14. Verify a real Telegram Stars purchase only settles after `successful_payment`, and that the stored Telegram charge ID is present for refund handling.

## Rollback

If the application image must be rolled back, keep the database at the newest compatible schema unless the release explicitly contains a tested reversible migration. Do not blindly downgrade production migrations.

For an application-only rollback:

```bash
git checkout <known-good-commit>
docker compose --env-file .env -f compose.production.yml build
docker compose --env-file .env -f compose.production.yml up -d api bot worker
```

Run the live and readiness checks again before accepting traffic. If a migration is not backward-compatible, stop and use the release-specific rollback procedure rather than forcing `alembic downgrade`.

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

The repository can validate code, packaging, migrations, deterministic rendering, and production configuration without production credentials. A real end-to-end generation cannot be truthfully marked complete until the external Telegram, PostgreSQL, Redis, AI, ComfyUI, and persistent-storage endpoints are supplied and exercised using the acceptance sequence above.

The release is considered **production-ready** only when the repository CI is green **and** the external acceptance sequence passes. A green CI run alone does not prove that external services are reachable or that a real Telegram generation was delivered.
