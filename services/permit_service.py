from __future__ import annotations

import pandas as pd

from database.connection import get_db_connection


def _table_exists(table_name: str) -> bool:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None


def get_permits(operator_id: str | None = None, field_name: str | None = None, limit: int = 500) -> pd.DataFrame:
    if not _table_exists("work_permits"):
        return pd.DataFrame()
    query = "SELECT * FROM work_permits WHERE 1=1"
    params: list[object] = []
    if operator_id:
        query += " AND operator_id = ?"
        params.append(operator_id)
    if field_name:
        query += " AND field_name = ?"
        params.append(field_name)
    query += " ORDER BY approval_date DESC, application_date DESC LIMIT ?"
    params.append(limit)
    with get_db_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_permit_summary(operator_id: str | None = None) -> dict:
    if not _table_exists("work_permits"):
        return {"permit_count": 0, "table_exists": False}
    query = "SELECT COUNT(*) AS permit_count FROM work_permits WHERE 1=1"
    params: list[object] = []
    if operator_id:
        query += " AND operator_id = ?"
        params.append(operator_id)
    with get_db_connection() as conn:
        row = conn.execute(query, params).fetchone()
    return {"permit_count": int(row["permit_count"] or 0), "table_exists": True}
