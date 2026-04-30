from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd

from database.connection import get_db_connection
from services.action_engine import build_action_engine
from services.forecast_service import get_underperforming_wells
from services.inspection_context import InspectionContext
from services.maintenance_service import calculate_maintenance_risk
from services.opportunity_explanations import build_evidence_items, build_opportunity_summary
from services.opportunity_scoring import score_confidence, score_priority
from services.permit_service import get_permits
from services.service_category_mapper import SERVICE_CATEGORIES, classify_service_category
from services.vendor_match_rules import suggest_vendor_matches


def _build_ctx(operator_id: str | None, field_name: str | None = None, well_name: str | None = None) -> InspectionContext:
    return InspectionContext(
        operator_id=operator_id,
        field_name=field_name,
        well_name=well_name,
        date_start=None,
        date_end=None,
    )


def _recent_permit_index(operator_id: str | None, field_name: str | None = None) -> set[Tuple[str, str]]:
    permit_df = get_permits(operator_id=operator_id, field_name=field_name, limit=500)
    if permit_df.empty:
        return set()
    permit_df = permit_df.copy()
    permit_df["event_date"] = pd.to_datetime(permit_df["approval_date"].fillna(permit_df["application_date"]), errors="coerce")
    cutoff = pd.Timestamp.utcnow().tz_localize(None).normalize() - pd.Timedelta(days=365)
    permit_df = permit_df[permit_df["event_date"] >= cutoff]
    return {
        (str(row["well_name"]), str(row.get("field_name") or ""))
        for _, row in permit_df.iterrows()
        if str(row.get("well_name") or "").strip()
    }


def _frame_index(df: pd.DataFrame, key_cols: list[str]) -> dict[Tuple[str, ...], dict]:
    if df.empty:
        return {}
    out: dict[Tuple[str, ...], dict] = {}
    for _, row in df.iterrows():
        key = tuple(str(row.get(col) or "") for col in key_cols)
        out[key] = row.to_dict()
    return out


def _lookup_well_map(operator_id: str | None = None) -> dict[Tuple[str, str], dict]:
    query = "SELECT well_id, operator_id, operator_name, well_name, field_name FROM wells WHERE 1=1"
    params: list[object] = []
    if operator_id:
        query += " AND operator_id = ?"
        params.append(operator_id)
    with get_db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return {(str(row["well_name"]), str(row["field_name"])): dict(row) for row in rows}


def _seed_service_categories(conn) -> None:
    existing = {
        row["service_category_key"]
        for row in conn.execute("SELECT service_category_key FROM service_categories").fetchall()
    }
    for category in SERVICE_CATEGORIES:
        if category["service_category_key"] not in existing:
            conn.execute(
                "INSERT INTO service_categories (service_category_key, label, description) VALUES (?, ?, ?)",
                (category["service_category_key"], category["label"], category["description"]),
            )


def _find_active_opportunity(conn, well_id: int, opportunity_type: str):
    return conn.execute(
        """
        SELECT * FROM opportunities
        WHERE well_id = ?
          AND opportunity_type = ?
          AND status NOT IN ('resolved', 'dismissed')
        ORDER BY priority_score DESC
        LIMIT 1
        """,
        (well_id, opportunity_type),
    ).fetchone()


def _build_candidates(operator_id: str, field_name: str | None = None) -> List[Dict]:
    actions = build_action_engine(operator_id=operator_id, field_name=field_name)
    ctx = _build_ctx(operator_id=operator_id, field_name=field_name)
    maintenance_df = calculate_maintenance_risk(ctx)
    underperf_df = get_underperforming_wells(ctx)
    permit_keys = _recent_permit_index(operator_id=operator_id, field_name=field_name)

    maintenance_index = _frame_index(maintenance_df, ["well_name", "field_name"])
    underperf_index = _frame_index(underperf_df, ["well_name", "field_name"])

    candidates: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for action in actions:
        key = (str(action.get("well_name") or ""), str(action.get("field_name") or ""), str(action.get("issue") or ""))
        seen.add(key)
        maintenance = maintenance_index.get(key[:2], {})
        underperf = underperf_index.get(key[:2], {})
        permit_signal = key[:2] in permit_keys
        estimated_monthly_value = float(action.get("estimated_value", 0.0) or 0.0) / 3.0
        estimated_90_day_value = float(action.get("estimated_value", 0.0) or 0.0)
        pct_of_forecast = float(underperf.get("pct_of_forecast", 100.0) or 100.0)
        underperf_gap_pct = max(0.0, 100.0 - pct_of_forecast)

        candidate = {
            "well_name": action.get("well_name"),
            "field_name": action.get("field_name"),
            "opportunity_type": action.get("issue"),
            "title": f"{action.get('well_name')} - {str(action.get('issue') or '').replace('_', ' ').title()}",
            "recommended_action": action.get("recommended_action"),
            "primary_metric": action.get("metric"),
            "latest_value": float(action.get("latest_value", 0.0) or 0.0),
            "baseline_value": float(action.get("recent_avg", 0.0) or 0.0),
            "drop_pct": float(action.get("drop_pct", 0.0) or 0.0),
            "decline_pct_per_month": float(action.get("decline_pct_per_month", 0.0) or 0.0),
            "downtime_hours": float(action.get("downtime_hours", 0.0) or 0.0),
            "maintenance_risk_score": float(maintenance.get("risk_score", 0.0) or 0.0),
            "underperf_gap_pct": underperf_gap_pct,
            "permit_signal": permit_signal,
            "estimated_monthly_value": estimated_monthly_value,
            "estimated_90_day_value": estimated_90_day_value,
        }
        candidate["service_category_key"] = classify_service_category(
            candidate["opportunity_type"],
            candidate["primary_metric"],
            candidate["downtime_hours"],
        )
        candidate["evidence_count"] = len(build_evidence_items(candidate))
        candidate["priority_score"] = score_priority(candidate)
        candidate["confidence_score"] = score_confidence(candidate)
        candidate["summary"] = build_opportunity_summary(candidate)
        candidates.append(candidate)

    for _, underperf in underperf_df.iterrows():
        key = (str(underperf["well_name"]), str(underperf["field_name"]), "underperformance")
        if key in seen:
            continue
        pct_of_forecast = float(underperf.get("pct_of_forecast", 100.0) or 100.0)
        underperf_gap_pct = max(0.0, 100.0 - pct_of_forecast)
        if underperf_gap_pct < 10:
            continue
        candidate = {
            "well_name": underperf["well_name"],
            "field_name": underperf["field_name"],
            "opportunity_type": "underperformance",
            "title": f"{underperf['well_name']} - Underperformance",
            "recommended_action": "Review for intervention or optimization",
            "primary_metric": underperf["metric"],
            "latest_value": float(underperf.get("actual_value", 0.0) or 0.0),
            "baseline_value": float(underperf.get("forecast_value", 0.0) or 0.0),
            "drop_pct": underperf_gap_pct,
            "decline_pct_per_month": 0.0,
            "downtime_hours": 0.0,
            "maintenance_risk_score": 0.0,
            "underperf_gap_pct": underperf_gap_pct,
            "permit_signal": (str(underperf["well_name"]), str(underperf["field_name"])) in permit_keys,
            "estimated_monthly_value": max(0.0, float(underperf.get("gap", 0.0) or 0.0)) * 3.0,
            "estimated_90_day_value": max(0.0, float(underperf.get("gap", 0.0) or 0.0)) * 9.0,
        }
        candidate["service_category_key"] = classify_service_category(
            candidate["opportunity_type"],
            candidate["primary_metric"],
            candidate["downtime_hours"],
        )
        candidate["evidence_count"] = len(build_evidence_items(candidate))
        candidate["priority_score"] = score_priority(candidate)
        candidate["confidence_score"] = score_confidence(candidate)
        candidate["summary"] = build_opportunity_summary(candidate)
        candidates.append(candidate)

    return sorted(candidates, key=lambda row: (row["priority_score"], row["estimated_90_day_value"]), reverse=True)


def refresh_opportunities(operator_id: str, field_name: str | None = None, make_vendor_visible: bool = False) -> Dict[str, object]:
    candidates = _build_candidates(operator_id=operator_id, field_name=field_name)
    well_map = _lookup_well_map(operator_id=operator_id)

    inserted = 0
    updated = 0
    vendor_matches_created = 0
    skipped = 0

    with get_db_connection() as conn:
        _seed_service_categories(conn)
        now = datetime.utcnow().isoformat()

        for candidate in candidates:
            well = well_map.get((str(candidate["well_name"]), str(candidate["field_name"])))
            if well is None:
                skipped += 1
                continue

            existing = _find_active_opportunity(conn, int(well["well_id"]), str(candidate["opportunity_type"]))
            if existing is None:
                cursor = conn.execute(
                    """
                    INSERT INTO opportunities (
                        well_id, operator_id, operator_name, field_name, well_name, opportunity_type, title, summary,
                        status, priority_score, confidence_score, estimated_monthly_value, estimated_90_day_value,
                        recommended_action, service_category_key, primary_metric, latest_value, baseline_value,
                        drop_pct, decline_pct_per_month, downtime_hours, permit_signal, is_operator_visible,
                        is_vendor_visible, created_at, updated_at, last_scored_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        well["well_id"],
                        well["operator_id"],
                        well["operator_name"],
                        well["field_name"],
                        well["well_name"],
                        candidate["opportunity_type"],
                        candidate["title"],
                        candidate["summary"],
                        "new",
                        candidate["priority_score"],
                        candidate["confidence_score"],
                        candidate["estimated_monthly_value"],
                        candidate["estimated_90_day_value"],
                        candidate["recommended_action"],
                        candidate["service_category_key"],
                        candidate["primary_metric"],
                        candidate["latest_value"],
                        candidate["baseline_value"],
                        candidate["drop_pct"],
                        candidate["decline_pct_per_month"],
                        candidate["downtime_hours"],
                        1 if candidate["permit_signal"] else 0,
                        1,
                        1 if make_vendor_visible else 0,
                        now,
                        now,
                        now,
                    ),
                )
                opportunity_id = int(cursor.lastrowid)
                conn.execute(
                    """
                    INSERT INTO opportunity_status_history (
                        opportunity_id, old_status, new_status, changed_by, note, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (opportunity_id, None, "new", "system", "Opportunity created by refresh_opportunities", now),
                )
                inserted += 1
            else:
                opportunity_id = int(existing["opportunity_id"])
                conn.execute(
                    """
                    UPDATE opportunities
                    SET operator_id = ?, operator_name = ?, field_name = ?, well_name = ?, title = ?, summary = ?,
                        priority_score = ?, confidence_score = ?, estimated_monthly_value = ?, estimated_90_day_value = ?,
                        recommended_action = ?, service_category_key = ?, primary_metric = ?, latest_value = ?,
                        baseline_value = ?, drop_pct = ?, decline_pct_per_month = ?, downtime_hours = ?, permit_signal = ?,
                        is_operator_visible = 1, is_vendor_visible = ?, updated_at = ?, last_scored_at = ?
                    WHERE opportunity_id = ?
                    """,
                    (
                        well["operator_id"],
                        well["operator_name"],
                        well["field_name"],
                        well["well_name"],
                        candidate["title"],
                        candidate["summary"],
                        candidate["priority_score"],
                        candidate["confidence_score"],
                        candidate["estimated_monthly_value"],
                        candidate["estimated_90_day_value"],
                        candidate["recommended_action"],
                        candidate["service_category_key"],
                        candidate["primary_metric"],
                        candidate["latest_value"],
                        candidate["baseline_value"],
                        candidate["drop_pct"],
                        candidate["decline_pct_per_month"],
                        candidate["downtime_hours"],
                        1 if candidate["permit_signal"] else 0,
                        1 if make_vendor_visible else 0,
                        now,
                        now,
                        opportunity_id,
                    ),
                )
                conn.execute("DELETE FROM opportunity_evidence WHERE opportunity_id = ?", (opportunity_id,))
                updated += 1

            for evidence in build_evidence_items(candidate):
                conn.execute(
                    """
                    INSERT INTO opportunity_evidence (
                        opportunity_id, evidence_type, label, value_text, value_number, unit, sort_order, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        opportunity_id,
                        evidence["evidence_type"],
                        evidence["label"],
                        evidence["value_text"],
                        evidence["value_number"],
                        evidence["unit"],
                        evidence["sort_order"],
                        str(evidence["created_at"]),
                    ),
                )

            existing_vendor_matches = {
                (row["service_category_key"], row["vendor_account_id"])
                for row in conn.execute(
                    "SELECT service_category_key, vendor_account_id FROM vendor_matches WHERE opportunity_id = ?",
                    (opportunity_id,),
                ).fetchall()
            }
            for match in suggest_vendor_matches(
                {
                    "well_name": well["well_name"],
                    "service_category_key": candidate["service_category_key"],
                    "priority_score": candidate["priority_score"],
                    "estimated_90_day_value": candidate["estimated_90_day_value"],
                }
            ):
                key = (str(match["service_category_key"]), str(match["vendor_account_id"]))
                if key in existing_vendor_matches:
                    conn.execute(
                        """
                        UPDATE vendor_matches
                        SET vendor_name = ?, match_score = ?, match_reason = ?, access_status = ?, updated_at = ?
                        WHERE opportunity_id = ? AND service_category_key = ? AND vendor_account_id = ?
                        """,
                        (
                            match["vendor_name"],
                            match["match_score"],
                            match["match_reason"],
                            match["access_status"],
                            now,
                            opportunity_id,
                            match["service_category_key"],
                            match["vendor_account_id"],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO vendor_matches (
                            opportunity_id, service_category_key, vendor_name, vendor_account_id,
                            match_score, match_reason, access_status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            opportunity_id,
                            match["service_category_key"],
                            match["vendor_name"],
                            match["vendor_account_id"],
                            match["match_score"],
                            match["match_reason"],
                            match["access_status"],
                            now,
                            now,
                        ),
                    )
                    vendor_matches_created += 1

        conn.commit()

    return {
        "operator_id": operator_id,
        "field_name": field_name,
        "candidates_seen": len(candidates),
        "opportunities_inserted": inserted,
        "opportunities_updated": updated,
        "vendor_matches_created": vendor_matches_created,
        "skipped": skipped,
    }
