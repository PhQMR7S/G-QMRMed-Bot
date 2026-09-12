# Phase 6 — Worker, progress, delivery boundary

Phase 6 turns the durable DB/Redis queue into an executable worker boundary.

## Guarantees

- Redis is only the transport; PostgreSQL remains the source of truth.
- A worker claims only a `QUEUED` job under a row lock, so duplicate delivery is harmless.
- Progress stages remain monotonic and Telegram-facing updates are throttled to a safe cadence (default 4 seconds).
- Successful jobs persist `GenerationResult`, commit the reserved usage slot, and finish as `SUCCEEDED`.
- Failed jobs release the reservation and finish as `FAILED` with a bounded error message.
- Result storage is provider-neutral through `ResultStore`; this keeps S3/local/object storage replaceable.
- The pipeline is provider-neutral through `GenerationPipeline`; Phase 5 rendering/image generation plugs into this boundary.

## Execution boundary

`Telegram → PostgreSQL job → Redis → GenerationWorker → GenerationPipeline → ResultStore → PostgreSQL result → Telegram delivery`

The worker deliberately does not contain medical research or image-model business logic. Those remain injectable pipeline components, keeping retries, quota settlement, and delivery state independent from the AI providers.
