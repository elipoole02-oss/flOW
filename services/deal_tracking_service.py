from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from database.connection import get_db_connection
from services.opportunity_workflow import update_opportunity_status


DEAL_FEE_RATE = 0.08
VALID_BID_STATUSES = {"submitted", "shortlisted", "accepted", "rejected", "withdrawn"}


def _now() -> str:
    return datetime.utcnow().isoformat()


def ensure_deal_tables() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS proposal_requests (
            request_id INTEGER PRIMARY KEY,
            opportunity_id INTEGER NOT NULL,
            request_title TEXT NOT NULL,
            scope TEXT,
            requested_by TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            due_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_proposal_requests_opportunity ON proposal_requests (opportunity_id, status)",
        """
        CREATE TABLE IF NOT EXISTS vendor_bids (
            bid_id INTEGER PRIMARY KEY,
            request_id INTEGER NOT NULL,
            opportunity_id INTEGER NOT NULL,
            vendor_account_id TEXT,
            vendor_name TEXT NOT NULL,
            bid_amount REAL NOT NULL DEFAULT 0,
            estimated_recovered_value REAL NOT NULL DEFAULT 0,
            estimated_days_to_complete INTEGER,
            proposal_summary TEXT,
            status TEXT NOT NULL DEFAULT 'submitted',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            accepted_at TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_vendor_bids_opportunity ON vendor_bids (opportunity_id, status)",
        """
        CREATE TABLE IF NOT EXISTS deals (
            deal_id INTEGER PRIMARY KEY,
            opportunity_id INTEGER NOT NULL,
            bid_id INTEGER NOT NULL,
            request_id INTEGER NOT NULL,
            operator_id TEXT,
            vendor_account_id TEXT,
            vendor_name TEXT NOT NULL,
            deal_status TEXT NOT NULL DEFAULT 'accepted',
            contract_value REAL NOT NULL DEFAULT 0,
            estimated_recovered_value REAL NOT NULL DEFAULT 0,
            platform_fee_rate REAL NOT NULL DEFAULT 0,
            platform_fee_amount REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            closed_at TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_deals_operator_status ON deals (operator_id, deal_status)",
    ]
    with get_db_connection() as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


def create_proposal_request(
    opportunity_id: int,
    request_title: str | None = None,
    scope: str | None = None,
    requested_by: str | None = "operator",
    due_date: str | None = None,
) -> dict[str, Any]:
    ensure_deal_tables()
    now = _now()
    with get_db_connection() as conn:
        opportunity = conn.execute("SELECT * FROM opportunities WHERE opportunity_id = ?", (opportunity_id,)).fetchone()
        if opportunity is None:
            raise ValueError(f"Opportunity {opportunity_id} not found.")
        title = request_title or f"Proposal request for {opportunity['well_name']}"
        default_scope = (
            scope
            or f"Review {opportunity['well_name']} and propose work to address: {opportunity['recommended_action'] or opportunity['opportunity_type']}"
        )
        cursor = conn.execute(
            """
            INSERT INTO proposal_requests (
                opportunity_id, request_title, scope, requested_by, status, due_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
            """,
            (opportunity_id, title, default_scope, requested_by, due_date, now, now),
        )
        request_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO opportunity_comments (
                opportunity_id, author_name, author_role, body, is_internal, created_at
            ) VALUES (?, ?, ?, ?, 1, ?)
            """,
            (opportunity_id, "flOW", "system", f"Proposal request opened: {title}", now),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM proposal_requests WHERE request_id = ?", (request_id,)).fetchone())


def submit_vendor_bid(
    request_id: int,
    vendor_name: str,
    bid_amount: float,
    estimated_recovered_value: float,
    estimated_days_to_complete: int | None = None,
    proposal_summary: str | None = None,
    vendor_account_id: str | None = None,
) -> dict[str, Any]:
    ensure_deal_tables()
    now = _now()
    with get_db_connection() as conn:
        request = conn.execute("SELECT * FROM proposal_requests WHERE request_id = ?", (request_id,)).fetchone()
        if request is None:
            raise ValueError(f"Proposal request {request_id} not found.")
        if request["status"] not in {"open", "sent"}:
            raise ValueError(f"Proposal request {request_id} is not open.")
        opportunity_id = int(request["opportunity_id"])
        cursor = conn.execute(
            """
            INSERT INTO vendor_bids (
                request_id, opportunity_id, vendor_account_id, vendor_name, bid_amount,
                estimated_recovered_value, estimated_days_to_complete, proposal_summary,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?)
            """,
            (
                request_id,
                opportunity_id,
                vendor_account_id,
                vendor_name,
                float(bid_amount or 0),
                float(estimated_recovered_value or 0),
                estimated_days_to_complete,
                proposal_summary,
                now,
                now,
            ),
        )
        bid_id = int(cursor.lastrowid)
        conn.execute("UPDATE proposal_requests SET status = 'sent', updated_at = ? WHERE request_id = ?", (now, request_id))
        conn.commit()
        return dict(conn.execute("SELECT * FROM vendor_bids WHERE bid_id = ?", (bid_id,)).fetchone())


def update_bid_status(bid_id: int, status: str) -> dict[str, Any]:
    ensure_deal_tables()
    status = (status or "").strip().lower()
    if status not in VALID_BID_STATUSES:
        raise ValueError(f"Invalid bid status: {status}")
    now = _now()
    with get_db_connection() as conn:
        bid = conn.execute("SELECT * FROM vendor_bids WHERE bid_id = ?", (bid_id,)).fetchone()
        if bid is None:
            raise ValueError(f"Bid {bid_id} not found.")
        accepted_at = now if status == "accepted" else None
        conn.execute(
            "UPDATE vendor_bids SET status = ?, updated_at = ?, accepted_at = COALESCE(?, accepted_at) WHERE bid_id = ?",
            (status, now, accepted_at, bid_id),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM vendor_bids WHERE bid_id = ?", (bid_id,)).fetchone())


def accept_bid(bid_id: int, platform_fee_rate: float = DEAL_FEE_RATE) -> dict[str, Any]:
    ensure_deal_tables()
    now = _now()
    with get_db_connection() as conn:
        bid = conn.execute("SELECT * FROM vendor_bids WHERE bid_id = ?", (bid_id,)).fetchone()
        if bid is None:
            raise ValueError(f"Bid {bid_id} not found.")
        opportunity = conn.execute("SELECT * FROM opportunities WHERE opportunity_id = ?", (bid["opportunity_id"],)).fetchone()
        if opportunity is None:
            raise ValueError(f"Opportunity {bid['opportunity_id']} not found.")

        conn.execute(
            "UPDATE vendor_bids SET status = 'rejected', updated_at = ? WHERE request_id = ? AND bid_id != ? AND status IN ('submitted', 'shortlisted')",
            (now, bid["request_id"], bid_id),
        )
        conn.execute(
            "UPDATE vendor_bids SET status = 'accepted', updated_at = ?, accepted_at = ? WHERE bid_id = ?",
            (now, now, bid_id),
        )
        conn.execute("UPDATE proposal_requests SET status = 'awarded', updated_at = ? WHERE request_id = ?", (now, bid["request_id"]))

        contract_value = float(bid["bid_amount"] or 0)
        estimated_recovered_value = float(bid["estimated_recovered_value"] or 0)
        fee_amount = round(max(contract_value, estimated_recovered_value * 0.10) * float(platform_fee_rate or 0), 2)

        cursor = conn.execute(
            """
            INSERT INTO deals (
                opportunity_id, bid_id, request_id, operator_id, vendor_account_id, vendor_name,
                deal_status, contract_value, estimated_recovered_value, platform_fee_rate,
                platform_fee_amount, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'accepted', ?, ?, ?, ?, ?, ?)
            """,
            (
                int(bid["opportunity_id"]),
                bid_id,
                int(bid["request_id"]),
                opportunity["operator_id"],
                bid["vendor_account_id"],
                bid["vendor_name"],
                contract_value,
                estimated_recovered_value,
                float(platform_fee_rate or 0),
                fee_amount,
                now,
                now,
            ),
        )
        deal_id = int(cursor.lastrowid)
        conn.commit()

    update_opportunity_status(int(bid["opportunity_id"]), "planned", changed_by="deal_tracking", note=f"Accepted bid from {bid['vendor_name']}")
    with get_db_connection() as conn:
        return dict(conn.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,)).fetchone())


def update_deal_status(deal_id: int, deal_status: str) -> dict[str, Any]:
    ensure_deal_tables()
    deal_status = (deal_status or "").strip().lower()
    if deal_status not in {"accepted", "scheduled", "in_progress", "completed", "cancelled", "paid"}:
        raise ValueError(f"Invalid deal status: {deal_status}")
    now = _now()
    closed_at = now if deal_status in {"completed", "cancelled", "paid"} else None
    with get_db_connection() as conn:
        deal = conn.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,)).fetchone()
        if deal is None:
            raise ValueError(f"Deal {deal_id} not found.")
        conn.execute(
            "UPDATE deals SET deal_status = ?, updated_at = ?, closed_at = COALESCE(?, closed_at) WHERE deal_id = ?",
            (deal_status, now, closed_at, deal_id),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,)).fetchone())


def get_opportunity_deal_room(opportunity_id: int) -> dict[str, Any]:
    ensure_deal_tables()
    with get_db_connection() as conn:
        requests = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM proposal_requests WHERE opportunity_id = ? ORDER BY created_at DESC",
                (opportunity_id,),
            ).fetchall()
        ]
        bids = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM vendor_bids WHERE opportunity_id = ? ORDER BY status = 'accepted' DESC, estimated_recovered_value DESC, bid_amount ASC",
                (opportunity_id,),
            ).fetchall()
        ]
        deals = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM deals WHERE opportunity_id = ? ORDER BY created_at DESC",
                (opportunity_id,),
            ).fetchall()
        ]
    return {"proposal_requests": requests, "vendor_bids": bids, "deals": deals}


def get_operator_deals(operator_id: str | None = None) -> pd.DataFrame:
    ensure_deal_tables()
    query = """
        SELECT
            d.deal_id,
            d.opportunity_id,
            d.vendor_name,
            d.deal_status,
            d.contract_value,
            d.estimated_recovered_value,
            d.platform_fee_amount,
            d.created_at,
            o.well_name,
            o.field_name,
            o.opportunity_type,
            o.operator_id
        FROM deals d
        JOIN opportunities o ON o.opportunity_id = d.opportunity_id
        WHERE 1=1
    """
    params: list[Any] = []
    if operator_id:
        query += " AND o.operator_id = ?"
        params.append(operator_id)
    query += " ORDER BY d.created_at DESC"
    with get_db_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_deal_summary(operator_id: str | None = None) -> dict[str, Any]:
    deals = get_operator_deals(operator_id)
    if deals.empty:
        return {
            "deal_count": 0,
            "open_deals": 0,
            "completed_deals": 0,
            "contract_value": 0.0,
            "estimated_recovered_value": 0.0,
            "platform_fee_amount": 0.0,
        }
    return {
        "deal_count": int(len(deals)),
        "open_deals": int(deals[~deals["deal_status"].isin(["completed", "cancelled", "paid"])].shape[0]),
        "completed_deals": int(deals[deals["deal_status"].isin(["completed", "paid"])].shape[0]),
        "contract_value": float(deals["contract_value"].sum()),
        "estimated_recovered_value": float(deals["estimated_recovered_value"].sum()),
        "platform_fee_amount": float(deals["platform_fee_amount"].sum()),
    }
