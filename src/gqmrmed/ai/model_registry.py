"""Cost-aware model registry and task routing primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CostTier(StrEnum):
    FREE = "free"
    LOCAL = "local"
    PAID = "paid"


class ModelTask(StrEnum):
    SYNTHESIS = "synthesis"
    REASONING = "reasoning"
    VISION = "vision"
    RESEARCH = "research"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    provider: str
    model: str
    cost_tier: CostTier
    tasks: frozenset[ModelTask]
    priority: int
    enabled: bool = True

    @property
    def is_free(self) -> bool:
        return self.cost_tier in {CostTier.FREE, CostTier.LOCAL}


class ModelRegistry:
    """Deterministic registry used to build task-specific provider routes."""

    def __init__(self, models: list[ModelSpec]) -> None:
        enabled = [model for model in models if model.enabled]
        if not enabled:
            raise ValueError("model_registry_requires_enabled_model")
        self._models = tuple(sorted(enabled, key=lambda item: item.priority))

    def for_task(self, task: ModelTask, *, allow_paid: bool = False) -> tuple[ModelSpec, ...]:
        return tuple(
            model
            for model in self._models
            if task in model.tasks and (allow_paid or model.is_free)
        )

    def providers_for_task(
        self, task: ModelTask, *, allow_paid: bool = False
    ) -> tuple[tuple[str, str], ...]:
        return tuple(
            (model.provider, model.model)
            for model in self.for_task(task, allow_paid=allow_paid)
        )


OPENROUTER_FREE = ModelSpec(
    provider="openrouter_free",
    model="openrouter/free",
    cost_tier=CostTier.FREE,
    tasks=frozenset({ModelTask.SYNTHESIS, ModelTask.REASONING, ModelTask.VISION}),
    priority=20,
)

GROQ_FREE = ModelSpec(
    provider="groq_free",
    model="openai/gpt-oss-20b",
    cost_tier=CostTier.FREE,
    tasks=frozenset({ModelTask.SYNTHESIS, ModelTask.REASONING}),
    priority=30,
)

OLLAMA_LOCAL = ModelSpec(
    provider="ollama",
    model="qwen3:8b",
    cost_tier=CostTier.LOCAL,
    tasks=frozenset({ModelTask.SYNTHESIS, ModelTask.REASONING}),
    priority=10,
)

OPENAI_PAID = ModelSpec(
    provider="openai",
    model="configured",
    cost_tier=CostTier.PAID,
    tasks=frozenset({ModelTask.SYNTHESIS, ModelTask.REASONING, ModelTask.VISION}),
    priority=100,
)


def default_registry() -> ModelRegistry:
    """Launch registry: local/free first; paid remains explicitly opt-in."""
    return ModelRegistry([OLLAMA_LOCAL, OPENROUTER_FREE, GROQ_FREE, OPENAI_PAID])


__all__ = [
    "CostTier",
    "GROQ_FREE",
    "ModelRegistry",
    "ModelSpec",
    "ModelTask",
    "OPENAI_PAID",
    "OPENROUTER_FREE",
    "OLLAMA_LOCAL",
    "default_registry",
]
