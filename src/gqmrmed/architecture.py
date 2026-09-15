"""Canonical GQMRMed system boundaries and module map."""

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

# Public defaults. Database migrations are authoritative for live billing records.
PLANS = {
    "FREE": {"daily_limit": 1, "price": 0, "currency": "USD"},
    "PLUS": {"daily_limit": 2, "price": 15, "currency": "USD", "duration_days": 30},
    "PRO": {"daily_limit": 3, "price": 50, "currency": "USD", "duration_days": 90},
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
CANVAS_WIDTH = 1024
CANVAS_HEIGHT = 1536
CANVAS_ASPECT_RATIO = "2:3"
