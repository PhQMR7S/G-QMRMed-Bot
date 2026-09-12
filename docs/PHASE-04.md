# Phase 4 — Medical Research, Evidence Validation, Synthesis & Visual Architecture

Phase 4 establishes the medical-intelligence boundary before any image is generated.

## Pipeline

```text
User input
  ↓
ResearchRequest
  ↓
PubMed / evidence provider
  ↓
Provenance + deduplication validation
  ↓
Evidence-linked medical synthesis
  ↓
Claim/evidence validation
  ↓
Deterministic visual architecture selection
  ↓
MedicalPlan
```

## Implemented

- Bounded research contracts with explicit source provenance.
- PubMed E-utilities provider using ESearch + EFetch.
- Configurable NCBI API key/email identity.
- Evidence deduplication and warnings for missing evidence/abstracts.
- Structured medical claims where every claim must reference known evidence IDs.
- Provider-neutral synthesis boundary.
- OpenAI Responses API adapter using `httpx`; no provider SDK is required by the core package.
- Strict JSON validation of synthesized content through Pydantic contracts.
- Deterministic visual architecture selector covering emergency, laboratory, ECG, drug, anatomy, pathophysiology, comparison, procedure and general disease-card paths.
- Visual plan explicitly separates illustration generation from exact text rendering.
- Fixed 9:16 output requirement and GQMRMed watermark metadata.
- Unit tests for provenance, parsing, architecture selection and end-to-end Phase 4 planning.

## Medical safety boundary

The synthesis stage is instructed to use supplied evidence only, link factual claims to evidence, lower confidence when evidence is incomplete, and never invent doses, laboratory ranges, measurements or patient-specific treatment instructions.

Phase 4 does not yet generate or send the final image. Image generation, SVG/HTML exact-text rendering, QA, progress updates and Telegram delivery remain downstream worker stages.
