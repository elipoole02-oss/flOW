from __future__ import annotations

import numpy as np
import pandas as pd

from services.inspection_context import InspectionContext
from services.production_service import get_context_production, get_primary_metric


def prepare_single_well_decline_data(ctx: InspectionContext) -> tuple[pd.DataFrame, str, str | None]:
    if not ctx.well_name:
        return pd.DataFrame(), "gas_mcf", "Select one well to run decline."

    df = get_context_production(ctx)
    if df.empty:
        return pd.DataFrame(), "gas_mcf", "No production data in the selected context."
    if df["well_name"].nunique() != 1:
        return pd.DataFrame(), "gas_mcf", "Decline requires exactly one well."

    metric = get_primary_metric(df)
    monthly = (
        df.groupby("production_date", as_index=False)[[metric]]
        .sum()
        .sort_values("production_date")
        .reset_index(drop=True)
    )
    monthly = monthly[monthly[metric] > 0].copy()
    monthly["months_on"] = range(len(monthly))

    if len(monthly) < 3:
        return monthly, metric, "Not enough non-zero monthly data to fit decline."

    return monthly, metric, None


def fit_exponential_decline(single_well_df: pd.DataFrame, metric: str, forecast_months: int = 24) -> dict:
    if single_well_df.empty or len(single_well_df) < 3:
        return {"qi": 0.0, "di": 0.0, "forecast_df": pd.DataFrame()}

    x = single_well_df["months_on"].astype(float).to_numpy()
    y = single_well_df[metric].astype(float).to_numpy()
    y = np.where(y <= 0, np.nan, y)

    valid = ~np.isnan(y)
    x = x[valid]
    y = y[valid]
    if len(y) < 3:
        return {"qi": 0.0, "di": 0.0, "forecast_df": pd.DataFrame()}

    log_y = np.log(y)
    slope, intercept = np.polyfit(x, log_y, 1)
    qi = float(np.exp(intercept))
    di = float(max(0.0, -slope))

    forecast_idx = np.arange(len(single_well_df), len(single_well_df) + forecast_months, dtype=float)
    forecast_values = qi * np.exp(-di * forecast_idx)

    last_date = pd.Timestamp(single_well_df["production_date"].max())
    first_forecast_date = (last_date + pd.offsets.MonthBegin(1)).normalize()
    forecast_dates = pd.date_range(start=first_forecast_date, periods=forecast_months, freq="MS")

    forecast_df = pd.DataFrame({"production_date": forecast_dates, f"forecast_{metric}": forecast_values})
    return {"qi": qi, "di": di, "forecast_df": forecast_df}
