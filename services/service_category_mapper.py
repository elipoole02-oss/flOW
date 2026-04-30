from __future__ import annotations

from typing import Dict


SERVICE_CATEGORIES: list[Dict[str, str]] = [
    {
        "service_category_key": "artificial_lift",
        "label": "Artificial Lift",
        "description": "Lift optimization, pump issues, and lift-related field work.",
    },
    {
        "service_category_key": "workover",
        "label": "Workover / Well Service",
        "description": "Mechanical remediation, tubing, and intervention-style work.",
    },
    {
        "service_category_key": "production_optimization",
        "label": "Production Optimization",
        "description": "Optimization reviews, tuning, and performance improvement work.",
    },
    {
        "service_category_key": "inspection_maintenance",
        "label": "Inspection / Maintenance",
        "description": "Field inspection, maintenance, and downtime investigation.",
    },
    {
        "service_category_key": "water_handling",
        "label": "Water Handling",
        "description": "Water logistics, disposal, and water-driven operating issues.",
    },
    {
        "service_category_key": "compression",
        "label": "Compression",
        "description": "Gas handling, compression, and flow assurance support.",
    },
]


def classify_service_category(opportunity_type: str, metric: str | None, downtime_hours: float, water_bbl: float | None = None) -> str:
    opportunity_type = (opportunity_type or "").strip().lower()
    metric = (metric or "").strip().lower()
    water_bbl = float(water_bbl or 0.0)

    if opportunity_type == "downtime_risk":
        return "inspection_maintenance"
    if opportunity_type == "underperformance":
        return "workover"
    if opportunity_type == "rapid_decline":
        return "workover"
    if opportunity_type == "optimization_candidate":
        if metric == "gas_mcf":
            return "compression"
        return "production_optimization"
    if water_bbl > 0:
        return "water_handling"
    if downtime_hours >= 6:
        return "inspection_maintenance"
    return "production_optimization"
