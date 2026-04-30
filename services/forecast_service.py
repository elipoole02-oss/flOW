from __future__ import annotations

import pandas as pd

from services.inspection_context import InspectionContext
from services.production_service import get_context_production, get_primary_metric, get_primary_label
from services.decline_service import prepare_single_well_decline_data, fit_exponential_decline


def calculate_eur_for_context(ctx: InspectionContext) -> dict:
    single_df, metric, reason = prepare_single_well_decline_data(ctx)
    if reason:
        return {
            "enabled": False,
            "reason": reason,
            "current_cum": 0.0,
            "forecast_cum": 0.0,
            "eur": 0.0,
            "metric": metric,
            "metric_label": get_primary_label(metric),
            "forecast_df": pd.DataFrame(),
            "input_df": single_df,
            "qi": 0.0,
            "di": 0.0,
        }

    result = fit_exponential_decline(single_df, metric)
    forecast_df = result["forecast_df"]
    forecast_col = f"forecast_{metric}"
    current_cum = float(single_df[metric].sum())
    forecast_cum = float(forecast_df[forecast_col].sum()) if not forecast_df.empty else 0.0

    return {
        "enabled": True,
        "reason": None,
        "current_cum": current_cum,
        "forecast_cum": forecast_cum,
        "eur": current_cum + forecast_cum,
        "metric": metric,
        "metric_label": get_primary_label(metric),
        "forecast_df": forecast_df,
        "input_df": single_df,
        "qi": float(result["qi"]),
        "di": float(result["di"]),
    }


def get_underperforming_wells(ctx: InspectionContext) -> pd.DataFrame:
    df = get_context_production(ctx)
    if df.empty:
        return pd.DataFrame(columns=["well_name", "field_name", "actual_value", "forecast_value", "gap", "pct_of_forecast", "metric"])

    rows = []
    for (well_name, field_name), well_df in df.groupby(["well_name", "field_name"]):
        monthly = well_df.groupby("production_date", as_index=False)[["oil_bbl", "gas_mcf", "water_bbl"]].sum().sort_values("production_date")
        metric = get_primary_metric(monthly)
        monthly = monthly[monthly[metric] > 0].copy()
        if len(monthly) < 4:
            continue

        history = monthly.iloc[:-1].copy().reset_index(drop=True)
        latest = monthly.iloc[-1].copy()
        history["months_on"] = range(len(history))
        fitted = fit_exponential_decline(history, metric, forecast_months=1)
        forecast_df = fitted["forecast_df"]
        forecast_col = f"forecast_{metric}"
        if forecast_df.empty:
            continue

        actual_value = float(latest[metric])
        forecast_value = float(forecast_df[forecast_col].iloc[0])
        gap = actual_value - forecast_value
        pct_of_forecast = (actual_value / forecast_value * 100.0) if forecast_value > 0 else 0.0

        rows.append({
            "well_name": well_name,
            "field_name": field_name,
            "actual_value": round(actual_value, 2),
            "forecast_value": round(forecast_value, 2),
            "gap": round(gap, 2),
            "pct_of_forecast": round(pct_of_forecast, 2),
            "metric": metric,
        })

    if not rows:
        return pd.DataFrame(columns=["well_name", "field_name", "actual_value", "forecast_value", "gap", "pct_of_forecast", "metric"])
    return pd.DataFrame(rows).sort_values("pct_of_forecast", ascending=True).reset_index(drop=True)
