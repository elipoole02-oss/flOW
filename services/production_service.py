from __future__ import annotations

import pandas as pd

from database.queries import get_production_data
from services.inspection_context import InspectionContext


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()
    out["production_date"] = pd.to_datetime(out["production_date"], errors="coerce")
    for col in ["oil_bbl", "gas_mcf", "water_bbl", "downtime_hours"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    return out


def get_base_production_data() -> pd.DataFrame:
    return _normalize(get_production_data())


def get_filter_options(operator_id: str | None = None, field_name: str | None = None) -> tuple[list[str], list[str], list[str]]:
    df = get_base_production_data()
    if df.empty:
        return [], [], []

    work = df.copy()
    operators = []
    if "operator_id" in work.columns:
        operators = sorted([x for x in work["operator_id"].dropna().astype(str).unique().tolist() if x.strip()])

    if operator_id and "operator_id" in work.columns:
        work = work[work["operator_id"].astype(str) == str(operator_id)]

    fields = sorted([x for x in work["field_name"].dropna().astype(str).unique().tolist() if x.strip()])

    if field_name:
        work = work[work["field_name"].astype(str) == str(field_name)]

    wells = sorted([x for x in work["well_name"].dropna().astype(str).unique().tolist() if x.strip()])
    return operators, fields, wells


def get_context_production(ctx: InspectionContext) -> pd.DataFrame:
    df = get_base_production_data()
    if df.empty:
        return df

    work = df.copy()
    if ctx.operator_id and "operator_id" in work.columns:
        work = work[work["operator_id"].astype(str) == str(ctx.operator_id)]
    if ctx.field_name:
        work = work[work["field_name"].astype(str) == str(ctx.field_name)]
    if ctx.well_name:
        work = work[work["well_name"].astype(str) == str(ctx.well_name)]
    if ctx.date_start:
        work = work[work["production_date"] >= pd.Timestamp(ctx.date_start)]
    if ctx.date_end:
        work = work[work["production_date"] <= pd.Timestamp(ctx.date_end)]

    return work.sort_values(["production_date", "well_name"]).reset_index(drop=True)


def get_kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"well_count": 0, "oil_bbl": 0.0, "gas_mcf": 0.0, "water_bbl": 0.0, "downtime_hours": 0.0}

    return {
        "well_count": int(df["well_name"].nunique()),
        "oil_bbl": float(df["oil_bbl"].sum()),
        "gas_mcf": float(df["gas_mcf"].sum()),
        "water_bbl": float(df["water_bbl"].sum()),
        "downtime_hours": float(df["downtime_hours"].sum()),
    }


def get_primary_metric(df: pd.DataFrame) -> str:
    oil_total = float(df["oil_bbl"].sum()) if "oil_bbl" in df.columns else 0.0
    gas_total = float(df["gas_mcf"].sum()) if "gas_mcf" in df.columns else 0.0
    return "oil_bbl" if oil_total > 0 else "gas_mcf"


def get_primary_label(metric: str) -> str:
    return "Oil (bbl)" if metric == "oil_bbl" else "Gas (mcf)"


def get_monthly_totals(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["production_date", "oil_bbl", "gas_mcf", "water_bbl", "downtime_hours"])

    return (
        df.groupby(pd.Grouper(key="production_date", freq="MS"), as_index=False)[["oil_bbl", "gas_mcf", "water_bbl", "downtime_hours"]]
        .sum()
        .sort_values("production_date")
        .reset_index(drop=True)
    )


def get_top_wells(df: pd.DataFrame, metric: str, top_n: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["well_name", "field_name", metric])

    return (
        df.groupby(["well_name", "field_name"], as_index=False)[["oil_bbl", "gas_mcf", "water_bbl", "downtime_hours"]]
        .sum()
        .sort_values(metric, ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


def get_latest_well_status(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["well_name", "field_name", "production_date", "oil_bbl", "gas_mcf", "water_bbl", "downtime_hours"])

    latest_rows = (
        df.sort_values(["well_name", "production_date"])
        .groupby("well_name", as_index=False)
        .tail(1)
        .sort_values(["field_name", "well_name"])
        .reset_index(drop=True)
    )
    return latest_rows[["well_name", "field_name", "production_date", "oil_bbl", "gas_mcf", "water_bbl", "downtime_hours"]]
