from __future__ import annotations

from typing import Optional

import pandas as pd

from database.connection import get_db_connection
from database.queries import get_production_data
from services.permit_service import get_permits


def get_well_timeline(operator_id: Optional[str], well_name: str, field_name: Optional[str] = None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    prod_df = get_production_data(operator_id=operator_id, field_name=field_name, well_name=well_name)
    if not prod_df.empty:
        prod = (
            prod_df.sort_values("production_date")
            .assign(
                event_type="production",
                event_date=lambda df: pd.to_datetime(df["production_date"], errors="coerce"),
                detail=lambda df: (
                    "Oil="
                    + df["oil_bbl"].round(1).astype(str)
                    + ", Gas="
                    + df["gas_mcf"].round(1).astype(str)
                    + ", Downtime="
                    + df["downtime_hours"].round(1).astype(str)
                ),
            )[["event_date", "event_type", "detail", "well_name", "field_name"]]
        )
        frames.append(prod)

    permit_df = get_permits(operator_id=operator_id, field_name=field_name)
    if not permit_df.empty:
        permit_df = permit_df[permit_df["well_name"].astype(str) == str(well_name)].copy()
        if not permit_df.empty:
            permit = permit_df.assign(
                event_type="permit",
                event_date=lambda df: pd.to_datetime(df["approval_date"].fillna(df["application_date"]), errors="coerce"),
                detail=lambda df: "Permit: " + df["permit_type"].fillna("Unknown").astype(str),
            )[["event_date", "event_type", "detail", "well_name", "field_name"]]
            frames.append(permit)

    with get_db_connection() as conn:
        history_df = pd.read_sql_query(
            """
            SELECT
                h.created_at AS event_date,
                'workflow' AS event_type,
                'Status changed to ' || h.new_status AS detail,
                o.well_name,
                o.field_name
            FROM opportunity_status_history h
            JOIN opportunities o ON o.opportunity_id = h.opportunity_id
            WHERE o.well_name = ?
            ORDER BY h.created_at
            """,
            conn,
            params=[well_name],
        )
        if not history_df.empty:
            history_df["event_date"] = pd.to_datetime(history_df["event_date"], errors="coerce")
            frames.append(history_df)

    if not frames:
        return pd.DataFrame(columns=["event_date", "event_type", "detail", "well_name", "field_name"])
    return pd.concat(frames, ignore_index=True).sort_values("event_date").reset_index(drop=True)
