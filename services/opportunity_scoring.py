from __future__ import annotations

from typing import Mapping


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, float(value)))


def score_priority(candidate: Mapping[str, object]) -> float:
    estimated_90_day_value = float(candidate.get("estimated_90_day_value", 0.0) or 0.0)
    drop_pct = float(candidate.get("drop_pct", 0.0) or 0.0)
    decline_pct = float(candidate.get("decline_pct_per_month", 0.0) or 0.0)
    downtime_hours = float(candidate.get("downtime_hours", 0.0) or 0.0)
    permit_signal = 10.0 if candidate.get("permit_signal") else 0.0
    underperf_gap_pct = float(candidate.get("underperf_gap_pct", 0.0) or 0.0)

    value_component = clamp(estimated_90_day_value / 2500.0, maximum=45.0)
    drop_component = clamp(drop_pct * 0.8, maximum=20.0)
    decline_component = clamp(decline_pct * 0.8, maximum=15.0)
    downtime_component = clamp(downtime_hours * 1.5, maximum=10.0)
    underperf_component = clamp(underperf_gap_pct * 0.4, maximum=10.0)

    return round(
        value_component + drop_component + decline_component + downtime_component + underperf_component + permit_signal,
        2,
    )


def score_confidence(candidate: Mapping[str, object]) -> float:
    evidence_count = int(candidate.get("evidence_count", 0) or 0)
    latest_value = float(candidate.get("latest_value", 0.0) or 0.0)
    baseline_value = float(candidate.get("baseline_value", 0.0) or 0.0)
    permit_signal = 8.0 if candidate.get("permit_signal") else 0.0

    evidence_component = clamp(evidence_count * 12.0, maximum=60.0)
    production_component = 20.0 if baseline_value > 0 or latest_value > 0 else 0.0

    return round(clamp(evidence_component + production_component + permit_signal), 2)
