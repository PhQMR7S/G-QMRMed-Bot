# GQMRMed AI Provider Layer

GQMRMed does not depend on a single AI vendor. The synthesis stage uses a provider-neutral contract and a deterministic fallback router.

## Provider order

`AI_PROVIDER_ORDER` is a comma-separated priority list. The reference configuration is:

```text
ollama,openai_compatible,openai
```

A provider failure at the transport/configuration boundary moves execution to the next provider. A medically invalid response is not silently accepted: the existing evidence-validation stage remains authoritative after synthesis.

## Providers

### 1. Ollama — local-first

Ollama runs a local model and therefore has no per-token hosted API subscription. Compute, RAM, and GPU resources are still required. The default example model is `qwen3:8b`; the model can be changed without changing application code.

Configure:

```env
AI_PROVIDER_ORDER=ollama,openai_compatible,openai
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen3:8b
```

### 2. OpenAI-compatible gateway

`OpenAICompatibleChatSynthesizer` supports providers exposing `/chat/completions`. This is intentionally vendor-neutral: a free-tier gateway can be selected when available, or a paid provider can be used without changing the medical pipeline.

Configure:

```env
AI_COMPATIBLE_API_KEY=
AI_COMPATIBLE_BASE_URL=
AI_COMPATIBLE_MODEL=
```

Do not hardcode a provider's supposedly free model into the application. Free quotas and model availability change; configuration is the correct boundary.

### 3. OpenAI Responses API

The existing `OpenAIResponsesSynthesizer` remains the high-quality hosted fallback. Its key is supplied only through an environment/secret store.

```env
AI_API_KEY=
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-5.6-luna
```

Never commit API keys to GitHub.

## Medical safety boundary

Provider selection is an infrastructure concern, not an evidence authority. Every provider must return the same `SynthesizedContent` contract. The pipeline then validates every claim against known evidence IDs before visual generation. Provider fallback must never be used to bypass that validation.

## Adding another provider

1. Implement `TextSynthesisProvider`.
2. Return validated `SynthesizedContent`.
3. Convert provider/network errors into a provider-boundary exception.
4. Register the provider with a `ProviderDescriptor`.
5. Add deterministic unit tests with mocked HTTP transport.
6. Keep secrets and model names in environment configuration.

This keeps model/vendor changes isolated from research, evidence validation, visual architecture, rendering, billing, and Telegram code.
