"""Canonical GQMRMed system boundaries and module map.

This file is intentionally dependency-light. It documents the production
architecture so implementation can proceed without changing the foundation.
"""

PROJECT_NAME = "GQMRMed"
INDEPENDENT_FROM = ("QMRMed", "QMRMed-Bot")
TELEGRAM_MINI_APP = False

MODULES = (
    "bot",
    "backend",
    "workers",
    "ai",
    "research",
    "vision",
    "rendering",
    "qa",
    "subscriptions",
    "usage",
    "admin",
    "database",
    "storage",
    "tests",
)

VISUAL_ARCHITECTURES = (
    "anatomy_explorer",
    "pathophysiology_flow",
    "disease_master_card",
    "drug_profile",
    "mechanism_of_action",
    "clinical_emergency_algorithm",
    "laboratory_interpretation",
    "ecg_analysis",
    "radiology_annotation",
    "comparison_matrix",
    "timeline",
    "step_by_step_procedure",
    "clinical_case",
    "concept_map",
    "revision_exam_card",
    "hybrid_anatomy_algorithm",
    "custom",
)

PLANS = {
    "FREE": {"daily_limit": 3, "price": 0, "currency": "USD"},
    "PLUS": {"daily_limit": None, "price": 5, "currency": "USD", "duration_days": 30},
    "PRO": {"daily_limit": None, "price": 20, "currency": "USD", "duration_days": 365},
}

GENERATION_STAGES = (
    "researching",
    "synthesizing",
    "architecture",
    "generating",
    "rendering",
    "quality_control",
)

WATERMARK = "GQMRMed"
CANVAS_ASPECT_RATIO = "4:5"
