from __future__ import annotations

from typing import Dict, List, Mapping


DEFAULT_VENDOR_LIBRARY: dict[str, list[dict[str, str]]] = {
    "artificial_lift": [
        {"vendor_account_id": "vendor-lift-01", "vendor_name": "Gulf Lift Services"},
        {"vendor_account_id": "vendor-lift-02", "vendor_name": "Pelican Pump & Lift"},
    ],
    "workover": [
        {"vendor_account_id": "vendor-workover-01", "vendor_name": "Bayou Well Service"},
        {"vendor_account_id": "vendor-workover-02", "vendor_name": "Delta Intervention Group"},
    ],
    "production_optimization": [
        {"vendor_account_id": "vendor-opt-01", "vendor_name": "FlowTune Optimization"},
        {"vendor_account_id": "vendor-opt-02", "vendor_name": "WellIQ Field Solutions"},
    ],
    "inspection_maintenance": [
        {"vendor_account_id": "vendor-maint-01", "vendor_name": "Southline Inspection"},
        {"vendor_account_id": "vendor-maint-02", "vendor_name": "Parish Field Maintenance"},
    ],
    "water_handling": [
        {"vendor_account_id": "vendor-water-01", "vendor_name": "Acadiana Water Logistics"},
        {"vendor_account_id": "vendor-water-02", "vendor_name": "Pelican Disposal Services"},
    ],
    "compression": [
        {"vendor_account_id": "vendor-comp-01", "vendor_name": "Cajun Compression"},
        {"vendor_account_id": "vendor-comp-02", "vendor_name": "Gulf Gas Systems"},
    ],
}


def suggest_vendor_matches(opportunity: Mapping[str, object]) -> List[Dict[str, object]]:
    category_key = str(opportunity.get("service_category_key") or "").strip()
    well_name = str(opportunity.get("well_name") or "this well")
    priority_score = float(opportunity.get("priority_score", 0.0) or 0.0)
    estimated_90_day_value = float(opportunity.get("estimated_90_day_value", 0.0) or 0.0)

    vendors = DEFAULT_VENDOR_LIBRARY.get(category_key, [])
    matches: list[dict[str, object]] = []
    for idx, vendor in enumerate(vendors, start=1):
        match_score = max(25.0, min(95.0, priority_score - (idx - 1) * 7.0))
        reason = (
            f"Suggested for {well_name} because the opportunity maps to {category_key.replace('_', ' ')} "
            f"and carries an estimated 90-day upside of ${estimated_90_day_value:,.0f}."
        )
        matches.append(
            {
                "vendor_account_id": vendor["vendor_account_id"],
                "vendor_name": vendor["vendor_name"],
                "service_category_key": category_key,
                "match_score": round(match_score, 2),
                "match_reason": reason,
                "access_status": "suggested",
            }
        )
    return matches
