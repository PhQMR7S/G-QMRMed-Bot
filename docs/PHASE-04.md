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
- OpenAI-compatible and local-provider adapters through the configured provider abstraction.
- Strict JSON validation of synthesized content through Pydantic contracts.
- Deterministic visual architecture selector covering emergency, laboratory, ECG, drug, anatomy, pathophysiology, comparison, procedure and general disease-card paths.
- Visual plan explicitly separates illustration generation from exact text rendering.
- Canonical **2:3 output contract (1024×1536)** and GQMRMed watermark metadata.
- Natural-language design preferences are passed into the deterministic design specification without requiring preset menus.
- Unit tests for provenance, parsing, architecture selection and end-to-end Phase 4 planning.

## Medical safety boundary

The synthesis stage is instructed to use supplied evidence only, link factual claims to evidence, lower confidence when evidence is incomplete, and never invent doses, laboratory ranges, measurements or patient-specific treatment instructions.

Phase 4 does not itself generate or send the final image. Image generation, deterministic exact-text rendering, QA, progress updates and Telegram delivery remain downstream worker stages.
