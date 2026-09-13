# Phase 8 — Long Text Engine

## Scope

Phase 8 converts long or structured medical text into a deterministic generation
plan before visual architecture.

Pipeline:

`Parser → semantic chunking → topic extraction → deduplication → prioritization → page decision`

## Guarantees

- Headings are preserved as section context.
- Text is chunked on sentence/paragraph boundaries near a configurable target size.
- Near-duplicate chunks are removed using token-set Jaccard similarity.
- Topics are extracted deterministically with medical-term weighting.
- Chunks receive a priority score so downstream architecture can surface high-value content.
- The engine chooses `single` for compact requests and `multi_page` for larger requests.
- Multi-page output preserves one `visual_identity` value for all pages.
- Every long request reports exactly one `usage_units` value; Phase 8 does not multiply usage by page count.
- Empty input is rejected rather than silently producing an empty design.

## Boundary

The engine does not render images, invent medical facts, or charge usage. It prepares
content structure for the existing research, architecture, rendering, and QA stages.
