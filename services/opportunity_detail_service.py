from __future__ import annotations

from database.connection import get_db_connection
from services.well_timeline_service import get_well_timeline


def get_opportunity_detail(opportunity_id: int) -> dict:
    with get_db_connection() as conn:
        opportunity = conn.execute(
            "SELECT * FROM opportunities WHERE opportunity_id = ?",
            (opportunity_id,),
        ).fetchone()
        if opportunity is None:
            raise ValueError(f"Opportunity {opportunity_id} not found.")

        evidence = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM opportunity_evidence WHERE opportunity_id = ? ORDER BY sort_order, evidence_id",
                (opportunity_id,),
            ).fetchall()
        ]
        comments = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM opportunity_comments WHERE opportunity_id = ? ORDER BY created_at DESC",
                (opportunity_id,),
            ).fetchall()
        ]
        vendor_matches = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM vendor_matches WHERE opportunity_id = ? ORDER BY match_score DESC",
                (opportunity_id,),
            ).fetchall()
        ]
        history = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM opportunity_status_history WHERE opportunity_id = ? ORDER BY created_at DESC",
                (opportunity_id,),
            ).fetchall()
        ]

    timeline = get_well_timeline(
        operator_id=opportunity["operator_id"],
        well_name=opportunity["well_name"],
        field_name=opportunity["field_name"],
    )
    return {
        "opportunity": dict(opportunity),
        "evidence": evidence,
        "comments": comments,
        "vendor_matches": vendor_matches,
        "status_history": history,
        "timeline": timeline.head(20).to_dict(orient="records"),
    }
