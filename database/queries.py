from __future__ import annotations

import pandas as pd

from database.connection import get_db_connection


def get_well_count() -> int:
    with get_db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM wells").fetchone()
        return int(row["count"] or 0)


def get_production_summary(
    operator_id: str | None = None,
    field_name: str | None = None,
    well_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    query = """
        SELECT
            COALESCE(SUM(p.oil_bbl), 0.0) AS oil_bbl,
            COALESCE(SUM(p.gas_mcf), 0.0) AS gas_mcf,
            COALESCE(SUM(p.water_bbl), 0.0) AS water_bbl
        FROM production p
        JOIN wells w ON w.well_id = p.well_id
        WHERE 1=1
    """
    params: list[object] = []
    if operator_id:
        query += " AND w.operator_id = ?"
        params.append(operator_id)
    if field_name:
        query += " AND w.field_name = ?"
        params.append(field_name)
    if well_name:
        query += " AND w.well_name = ?"
        params.append(well_name)
    if start_date:
        query += " AND p.production_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND p.production_date <= ?"
        params.append(end_date)

    with get_db_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return {
            "oil_bbl": float(row["oil_bbl"] or 0.0),
            "gas_mcf": float(row["gas_mcf"] or 0.0),
            "water_bbl": float(row["water_bbl"] or 0.0),
        }


def get_production_data(
    operator_id: str | None = None,
    field_name: str | None = None,
    well_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    query = """
        SELECT
            p.production_id,
            p.well_id,
            p.production_date,
            p.oil_bbl,
            p.gas_mcf,
            p.water_bbl,
            p.downtime_hours,
            w.api_number,
            w.well_serial_num,
            w.operator_id,
            w.operator_name,
            w.well_name,
            w.field_name,
            w.lease_name,
            w.status,
            w.lift_type,
            w.first_production_date
        FROM production p
        JOIN wells w ON p.well_id = w.well_id
        WHERE 1 = 1
    """
    params: list[object] = []
    if operator_id:
        query += " AND w.operator_id = ?"
        params.append(operator_id)
    if field_name:
        query += " AND w.field_name = ?"
        params.append(field_name)
    if well_name:
        query += " AND w.well_name = ?"
        params.append(well_name)
    if start_date:
        query += " AND p.production_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND p.production_date <= ?"
        params.append(end_date)
    query += " ORDER BY p.production_date, w.well_name"
    with get_db_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_monthly_production_by_well(
    operator_id: str | None = None,
    field_name: str | None = None,
    well_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    query = """
        SELECT
            w.operator_id,
            w.field_name,
            w.well_name,
            strftime('%Y-%m', p.production_date) AS production_month,
            SUM(p.oil_bbl) AS oil_bbl,
            SUM(p.gas_mcf) AS gas_mcf,
            SUM(p.water_bbl) AS water_bbl,
            SUM(p.downtime_hours) AS downtime_hours
        FROM production p
        JOIN wells w ON w.well_id = p.well_id
        WHERE 1 = 1
    """
    params: list[object] = []
    if operator_id:
        query += " AND w.operator_id = ?"
        params.append(operator_id)
    if field_name:
        query += " AND w.field_name = ?"
        params.append(field_name)
    if well_name:
        query += " AND w.well_name = ?"
        params.append(well_name)
    if start_date:
        query += " AND p.production_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND p.production_date <= ?"
        params.append(end_date)
    query += """
        GROUP BY w.operator_id, w.field_name, w.well_name, strftime('%Y-%m', p.production_date)
        ORDER BY production_month, w.well_name
    """
    with get_db_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_filter_values() -> dict[str, list[str]]:
    with get_db_connection() as conn:
        operators = [
            str(row["operator_id"])
            for row in conn.execute(
                "SELECT DISTINCT operator_id FROM wells WHERE operator_id IS NOT NULL AND TRIM(operator_id) != '' ORDER BY operator_id"
            ).fetchall()
        ]
        fields = [
            str(row["field_name"])
            for row in conn.execute(
                "SELECT DISTINCT field_name FROM wells WHERE field_name IS NOT NULL AND TRIM(field_name) != '' ORDER BY field_name"
            ).fetchall()
        ]
        wells = [
            str(row["well_name"])
            for row in conn.execute(
                "SELECT DISTINCT well_name FROM wells WHERE well_name IS NOT NULL AND TRIM(well_name) != '' ORDER BY well_name"
            ).fetchall()
        ]
    return {"operators": operators, "fields": fields, "wells": wells}
