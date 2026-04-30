from __future__ import annotations

from typing import Optional, List, Dict

import pandas as pd

from database.queries import get_production_data

GAS_PRICE = 3.00
OIL_PRICE = 75.00


def _safe_float(value) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _pick_primary_metric(df: pd.DataFrame) -> str:
    oil_total = _safe_float(df["oil_bbl"].sum()) if "oil_bbl" in df.columns else 0.0
    gas_total = _safe_float(df["gas_mcf"].sum()) if "gas_mcf" in df.columns else 0.0
    return "gas_mcf" if gas_total >= oil_total else "oil_bbl"


def _get_unit_price(metric: str) -> float:
    return GAS_PRICE if metric == "gas_mcf" else OIL_PRICE


def _prepare_well_history(
    operator_id: str,
    field_name: Optional[str] = None,
    well_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    df = get_production_data(
        operator_id=operator_id,
        field_name=field_name,
        well_name=well_name,
        start_date=start_date,
        end_date=end_date,
    )
    if df.empty:
        return df
    out = df.copy()
    out["production_date"] = pd.to_datetime(out["production_date"], errors="coerce")
    out["oil_bbl"] = pd.to_numeric(out.get("oil_bbl", 0.0), errors="coerce").fillna(0.0)
    out["gas_mcf"] = pd.to_numeric(out.get("gas_mcf", 0.0), errors="coerce").fillna(0.0)
    out["water_bbl"] = pd.to_numeric(out.get("water_bbl", 0.0), errors="coerce").fillna(0.0)
    out["downtime_hours"] = pd.to_numeric(out.get("downtime_hours", 0.0), errors="coerce").fillna(0.0)
    out = out.dropna(subset=["production_date"]).copy()
    out = out.sort_values(["well_name", "production_date"]).reset_index(drop=True)
    return out


def _monthly_well_totals(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["well_name", "field_name", "production_date", metric, "downtime_hours"])
    return (
        df.groupby(["well_name", "field_name", "production_date"], as_index=False)[[metric, "downtime_hours"]]
        .sum()
        .sort_values(["well_name", "production_date"])
        .reset_index(drop=True)
    )


def _compute_recent_baseline(well_df: pd.DataFrame, metric: str) -> Dict[str, float]:
    if well_df.empty:
        return {"latest_value": 0.0, "prior_avg": 0.0, "drop_pct": 0.0, "decline_pct_per_month": 0.0, "downtime_hours": 0.0}
    hist = well_df.sort_values("production_date").reset_index(drop=True)
    latest_value = _safe_float(hist.iloc[-1][metric])
    latest_downtime = _safe_float(hist.iloc[-1]["downtime_hours"])
    prior_window = hist.tail(6).copy()
    if len(prior_window) < 2:
        prior_avg = _safe_float(prior_window[metric].mean()) if not prior_window.empty else 0.0
        return {"latest_value": latest_value, "prior_avg": prior_avg, "drop_pct": 0.0, "decline_pct_per_month": 0.0, "downtime_hours": latest_downtime}
    baseline_window = prior_window.iloc[:-1] if len(prior_window) >= 2 else prior_window
    prior_avg = _safe_float(baseline_window[metric].mean()) if not baseline_window.empty else 0.0
    drop_pct = max(0.0, (prior_avg - latest_value) / prior_avg * 100.0) if prior_avg > 0 else 0.0
    start_val = _safe_float(prior_window.iloc[0][metric])
    end_val = latest_value
    months = max(len(prior_window) - 1, 1)
    decline_pct_per_month = max(0.0, min(100.0, ((start_val - end_val) / start_val) * 100.0 / months)) if start_val > 0 else 0.0
    return {
        "latest_value": latest_value,
        "prior_avg": prior_avg,
        "drop_pct": drop_pct,
        "decline_pct_per_month": decline_pct_per_month,
        "downtime_hours": latest_downtime,
    }


def _classify_issue(drop_pct: float, decline_pct_per_month: float, downtime_hours: float) -> str:
    if downtime_hours >= 6 and drop_pct >= 20:
        return "downtime_risk"
    if drop_pct >= 25:
        return "underperformance"
    if decline_pct_per_month >= 12:
        return "rapid_decline"
    if drop_pct >= 12:
        return "optimization_candidate"
    return "monitor"


def _recommend_action(issue: str) -> str:
    if issue == "downtime_risk":
        return "Investigate downtime and lift/equipment issues"
    if issue == "underperformance":
        return "Review for intervention or workover candidate"
    if issue == "rapid_decline":
        return "Check decline behavior and reservoir / mechanical causes"
    if issue == "optimization_candidate":
        return "Run production optimization review"
    return "Monitor"


def _estimate_value(prior_avg: float, latest_value: float, metric: str) -> float:
    unit_price = _get_unit_price(metric)
    lost_volume_per_month = max(0.0, prior_avg - latest_value)
    return lost_volume_per_month * unit_price * 3.0


def build_action_engine(
    operator_id: str,
    field_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    df = _prepare_well_history(operator_id=operator_id, field_name=field_name, well_name=None, start_date=start_date, end_date=end_date)
    if df.empty:
        return []
    metric = _pick_primary_metric(df)
    hist_df = _monthly_well_totals(df, metric)
    actions: List[Dict] = []
    for well_name, well_df in hist_df.groupby("well_name"):
        well_df = well_df.sort_values("production_date").reset_index(drop=True)
        if len(well_df) < 4:
            continue
        stats = _compute_recent_baseline(well_df, metric)
        issue = _classify_issue(stats["drop_pct"], stats["decline_pct_per_month"], stats["downtime_hours"])
        if issue == "monitor":
            continue
        value = _estimate_value(stats["prior_avg"], stats["latest_value"], metric)
        field_value = str(well_df["field_name"].iloc[-1]) if "field_name" in well_df.columns else ""
        payout_months = None
        assumed_fix_cost = 50000.0
        if value > 0:
            payout_months = round(assumed_fix_cost / max(value / 3.0, 1.0), 1)
        priority_score = value * 0.60 + stats["drop_pct"] * 800.0 + stats["decline_pct_per_month"] * 500.0 + stats["downtime_hours"] * 250.0
        actions.append({
            "well_name": well_name,
            "field_name": field_value,
            "issue": issue,
            "recommended_action": _recommend_action(issue),
            "metric": metric,
            "latest_value": round(stats["latest_value"], 2),
            "recent_avg": round(stats["prior_avg"], 2),
            "drop_pct": round(stats["drop_pct"], 1),
            "decline_pct_per_month": round(stats["decline_pct_per_month"], 1),
            "downtime_hours": round(stats["downtime_hours"], 1),
            "estimated_value": int(round(value, 0)),
            "estimated_payout_months": payout_months,
        })
    if not actions:
        return []
    action_df = pd.DataFrame(actions).sort_values(["estimated_value", "drop_pct"], ascending=[False, False])
    return action_df.to_dict(orient="records")
