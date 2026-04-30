from __future__ import annotations

from datetime import datetime

import pandas as pd

from database.connection import get_db_connection


VALID_STATUSES = {
    "new",
    "reviewing",
    "watchlist",
    "planned",
    "in_progress",
    "resolved",
    "dismissed",
}


def update_opportunity_status(opportunity_id: int, new_status: str, changed_by: str | None = None, note: str | None = None) -> dict:
    new_status = (new_status or "").strip().lower()
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")

    with get_db_connection() as conn:
        opportunity = conn.execute(
            "SELECT opportunity_id, status FROM opportunities WHERE opportunity_id = ?",
            (opportunity_id,),
        ).fetchone()
        if opportunity is None:
            raise ValueError(f"Opportunity {opportunity_id} not found.")

        old_status = opportunity["status"]
        now = datetime.utcnow().isoformat()
        resolved_at = now if new_status == "resolved" else None
        conn.execute(
            """
            UPDATE opportunities
            SET status = ?, updated_at = ?, resolved_at = COALESCE(?, resolved_at)
            WHERE opportunity_id = ?
            """,
            (new_status, now, resolved_at, opportunity_id),
        )
        conn.execute(
            """
            INSERT INTO opportunity_status_history (
                opportunity_id, old_status, new_status, changed_by, note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (opportunity_id, old_status, new_status, changed_by, note, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM opportunities WHERE opportunity_id = ?", (opportunity_id,)).fetchone()
        return dict(row)


def add_opportunity_comment(
    opportunity_id: int,
    body: str,
    author_name: str | None = None,
    author_role: str | None = None,
    is_internal: bool = True,
) -> dict:
    now = datetime.utcnow().isoformat()
    with get_db_connection() as conn:
        exists = conn.execute(
            "SELECT opportunity_id FROM opportunities WHERE opportunity_id = ?",
            (opportunity_id,),
        ).fetchone()
        if exists is None:
            raise ValueError(f"Opportunity {opportunity_id} not found.")

        conn.execute(
            """
            INSERT INTO opportunity_comments (
                opportunity_id, author_name, author_role, body, is_internal, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (opportunity_id, author_name, author_role, body, 1 if is_internal else 0, now),
        )
        conn.execute(
            "UPDATE opportunities SET updated_at = ? WHERE opportunity_id = ?",
            (now, opportunity_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM opportunity_comments WHERE opportunity_id = ? ORDER BY comment_id DESC LIMIT 1",
            (opportunity_id,),
        ).fetchone()
        return dict(row)


def get_opportunity_board(operator_id: str | None = None, status: str | None = None) -> pd.DataFrame:
    query = """
        SELECT
            opportunity_id,
            well_name,
            field_name,
            opportunity_type,
            status,
            priority_score,
            estimated_90_day_value,
            service_category_key
        FROM opportunities
        WHERE 1=1
    """
    params: list[object] = []
    if operator_id:
        query += " AND operator_id = ?"
        params.append(operator_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY priority_score DESC, estimated_90_day_value DESC"
    with get_db_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def share_opportunity_with_vendors(opportunity_id: int, vendor_account_ids: list[str] | None = None, note: str | None = None) -> dict:
    vendor_account_ids = vendor_account_ids or []
    now = datetime.utcnow().isoformat()

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT opportunity_id FROM opportunities WHERE opportunity_id = ?",
            (opportunity_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Opportunity {opportunity_id} not found.")

        conn.execute(
            "UPDATE opportunities SET is_vendor_visible = 1, updated_at = ? WHERE opportunity_id = ?",
            (now, opportunity_id),
        )

        if vendor_account_ids:
            placeholders = ",".join(["?"] * len(vendor_account_ids))
            conn.execute(
                f"""
                UPDATE vendor_matches
                SET access_status = 'shared', updated_at = ?
                WHERE opportunity_id = ?
                  AND vendor_account_id IN ({placeholders})
                """,
                [now, opportunity_id, *vendor_account_ids],
            )
        else:
            conn.execute(
                """
                UPDATE vendor_matches
                SET access_status = 'shared', updated_at = ?
                WHERE opportunity_id = ?
                """,
                (now, opportunity_id),
            )

        conn.execute(
            """
            INSERT INTO opportunity_status_history (
                opportunity_id, old_status, new_status, changed_by, note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (opportunity_id, None, "shared_to_vendors", "system", note or "Opportunity shared with vendors", now),
        )
        conn.commit()

        shared_count = conn.execute(
            "SELECT COUNT(*) AS count FROM vendor_matches WHERE opportunity_id = ? AND access_status = 'shared'",
            (opportunity_id,),
        ).fetchone()["count"]
        return {
            "opportunity_id": opportunity_id,
            "shared_vendor_count": int(shared_count or 0),
            "is_vendor_visible": True,
        }
