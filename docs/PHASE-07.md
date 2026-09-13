# Phase 7 — Live Telegram progress

Phase 7 exposes the worker's real generation stages to the user through **one Telegram message that is edited in place**.

## Guarantees

- Progress is derived from the existing `GenerationStage` contract; no fake percentage loop is introduced.
- The first worker update creates a progress message when one does not already exist.
- Subsequent updates edit the same Telegram message instead of sending a message per stage.
- Updates are throttled by the existing 4-second reporter and meaningful stage/progress changes can pass immediately.
- Progress payloads are validated to `0..100` and include elapsed time.
- Telegram delivery is observability only: a Telegram API failure cannot mark a healthy generation job as `FAILED`.
- The progress message ID is persisted in the existing job metadata so it can be recovered after a worker restart.
- PostgreSQL remains the source of truth; Redis remains transport only.

## User-visible flow

`Job accepted → ⏳ queued → 🔎 research → 🧠 synthesis → 📐 architecture → 🎨 generation → 🖼 rendering → ✅ quality control`

The final generated image/result delivery remains provider/storage-boundary work; Phase 7 specifically establishes the reliable live progress UX around the already-defined worker pipeline.
