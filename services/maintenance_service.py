from __future__ import annotations

import pandas as pd

from services.inspection_context import InspectionContext
from services.production_service import get_context_production


def calculate_maintenance_risk(ctx: InspectionContext) -> pd.DataFrame:
    df = get_context_production(ctx)
    if df.empty:
        return pd.DataFrame(columns=["well_name", "field_name", "latest_value", "avg_value", "downtime_hours", "production_drop_pct", "risk_score", "risk_level", "metric"])

    rows = []
    for (well_name, field_name), well_df in df.groupby(["well_name", "field_name"]):
        well_df = well_df.sort_values("production_date").copy()
        metric = "oil_bbl" if float(well_df["oil_bbl"].sum()) > 0 else "gas_mcf"
        latest_row = well_df.iloc[-1]
        latest_value = float(latest_row[metric])
        avg_value = float(well_df[metric].mean()) if len(well_df) else 0.0
        latest_downtime = float(latest_row["downtime_hours"])
        production_drop_pct = max(0.0, ((avg_value - latest_value) / avg_value) * 100.0) if avg_value > 0 else 0.0
        recent_rows = well_df.tail(3)
        volatility = float(recent_rows[metric].std()) if len(recent_rows) > 1 else 0.0
        risk_score = min(latest_downtime * 5.0, 40.0) + min(production_drop_pct * 0.6, 40.0) + min(volatility * 0.5, 20.0)

        if risk_score >= 70:
            risk_level = "High"
        elif risk_score >= 40:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        rows.append({
            "well_name": well_name,
            "field_name": field_name,
            "latest_value": round(latest_value, 2),
            "avg_value": round(avg_value, 2),
            "downtime_hours": round(latest_downtime, 2),
            "production_drop_pct": round(production_drop_pct, 2),
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "metric": metric,
        })

    return pd.DataFrame(rows).sort_values(["risk_score", "production_drop_pct"], ascending=[False, False]).reset_index(drop=True)
