from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Mapping


def build_opportunity_summary(candidate: Mapping[str, object]) -> str:
    well_name = str(candidate.get("well_name") or "This well")
    drop_pct = float(candidate.get("drop_pct", 0.0) or 0.0)
    decline_pct = float(candidate.get("decline_pct_per_month", 0.0) or 0.0)
    downtime_hours = float(candidate.get("downtime_hours", 0.0) or 0.0)
    estimated_90_day_value = float(candidate.get("estimated_90_day_value", 0.0) or 0.0)
    permit_signal = bool(candidate.get("permit_signal"))

    parts = [
        f"{well_name} is flagged for review because recent production fell {drop_pct:.1f}% versus its local baseline.",
        f"The current decline trend is {decline_pct:.1f}% per month.",
    ]
    if downtime_hours > 0:
        parts.append(f"Recent downtime reached {downtime_hours:.1f} hours.")
    if permit_signal:
        parts.append("Recent permit activity suggests related field work may already be underway.")
    if estimated_90_day_value > 0:
        parts.append(f"Estimated 90-day recoverable value is about ${estimated_90_day_value:,.0f}.")
    return " ".join(parts)


def build_evidence_items(candidate: Mapping[str, object]) -> List[Dict[str, object]]:
    created_at = datetime.utcnow()
    items: list[dict[str, object]] = []
    evidence_specs = [
        ("production", "Latest production", candidate.get("latest_value"), None, candidate.get("primary_metric")),
        ("production", "Baseline production", candidate.get("baseline_value"), None, candidate.get("primary_metric")),
        ("production", "Production drop", candidate.get("drop_pct"), None, "%"),
        ("decline", "Decline rate", candidate.get("decline_pct_per_month"), None, "%/month"),
        ("downtime", "Downtime", candidate.get("downtime_hours"), None, "hours"),
        ("economics", "Estimated monthly value", candidate.get("estimated_monthly_value"), None, "USD"),
        ("economics", "Estimated 90-day value", candidate.get("estimated_90_day_value"), None, "USD"),
    ]
    if candidate.get("permit_signal"):
        evidence_specs.append(("permit", "Recent permit signal", None, "Recent permit activity found", None))
    if candidate.get("underperf_gap_pct") is not None:
        evidence_specs.append(("forecast", "Percent below forecast", candidate.get("underperf_gap_pct"), None, "%"))

    for sort_order, (evidence_type, label, value_number, value_text, unit) in enumerate(evidence_specs, start=1):
        if value_number is None and not value_text:
            continue
        items.append(
            {
                "evidence_type": evidence_type,
                "label": label,
                "value_number": float(value_number) if value_number is not None else None,
                "value_text": value_text,
                "unit": unit,
                "sort_order": sort_order,
                "created_at": created_at,
            }
        )
    return items
