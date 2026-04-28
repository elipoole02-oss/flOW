from __future__ import annotations

from database.connection import get_db_connection


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS wells (
        well_id INTEGER PRIMARY KEY,
        api_number TEXT NOT NULL UNIQUE,
        well_serial_num TEXT UNIQUE,
        operator_id TEXT,
        operator_name TEXT,
        well_name TEXT NOT NULL,
        field_name TEXT NOT NULL,
        lease_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        lift_type TEXT,
        first_production_date DATE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_wells_operator_id ON wells (operator_id)",
    "CREATE INDEX IF NOT EXISTS idx_wells_field_name ON wells (field_name)",
    "CREATE INDEX IF NOT EXISTS idx_wells_well_name ON wells (well_name)",
    """
    CREATE TABLE IF NOT EXISTS production (
        production_id INTEGER PRIMARY KEY,
        well_id INTEGER NOT NULL,
        production_date DATE NOT NULL,
        oil_bbl REAL NOT NULL DEFAULT 0,
        gas_mcf REAL NOT NULL DEFAULT 0,
        water_bbl REAL NOT NULL DEFAULT 0,
        downtime_hours REAL NOT NULL DEFAULT 0,
        UNIQUE(well_id, production_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_production_well_id ON production (well_id)",
    "CREATE INDEX IF NOT EXISTS idx_production_date ON production (production_date)",
    """
    CREATE TABLE IF NOT EXISTS work_permits (
        permit_id INTEGER PRIMARY KEY,
        operator_id TEXT,
        operator_name TEXT,
        well_name TEXT,
        field_name TEXT,
        permit_type TEXT,
        application_date DATE,
        approval_date DATE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_work_permits_operator ON work_permits (operator_id)",
    """
    CREATE TABLE IF NOT EXISTS service_categories (
        service_category_key TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        description TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS opportunities (
        opportunity_id INTEGER PRIMARY KEY,
        well_id INTEGER NOT NULL,
        operator_id TEXT,
        operator_name TEXT,
        field_name TEXT,
        well_name TEXT NOT NULL,
        opportunity_type TEXT NOT NULL,
        title TEXT NOT NULL,
        summary TEXT,
        status TEXT NOT NULL DEFAULT 'new',
        priority_score REAL NOT NULL DEFAULT 0,
        confidence_score REAL NOT NULL DEFAULT 0,
        estimated_monthly_value REAL NOT NULL DEFAULT 0,
        estimated_90_day_value REAL NOT NULL DEFAULT 0,
        recommended_action TEXT,
        service_category_key TEXT,
        primary_metric TEXT,
        latest_value REAL,
        baseline_value REAL,
        drop_pct REAL,
        decline_pct_per_month REAL,
        downtime_hours REAL,
        permit_signal INTEGER NOT NULL DEFAULT 0,
        is_operator_visible INTEGER NOT NULL DEFAULT 1,
        is_vendor_visible INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_scored_at TEXT,
        resolved_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_opportunities_operator_status ON opportunities (operator_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_opportunities_priority ON opportunities (priority_score DESC)",
    """
    CREATE TABLE IF NOT EXISTS opportunity_evidence (
        evidence_id INTEGER PRIMARY KEY,
        opportunity_id INTEGER NOT NULL,
        evidence_type TEXT NOT NULL,
        label TEXT NOT NULL,
        value_text TEXT,
        value_number REAL,
        unit TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_opportunity_evidence_opp ON opportunity_evidence (opportunity_id, sort_order)",
    """
    CREATE TABLE IF NOT EXISTS opportunity_status_history (
        history_id INTEGER PRIMARY KEY,
        opportunity_id INTEGER NOT NULL,
        old_status TEXT,
        new_status TEXT NOT NULL,
        changed_by TEXT,
        note TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS opportunity_comments (
        comment_id INTEGER PRIMARY KEY,
        opportunity_id INTEGER NOT NULL,
        author_name TEXT,
        author_role TEXT,
        body TEXT NOT NULL,
        is_internal INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vendor_matches (
        vendor_match_id INTEGER PRIMARY KEY,
        opportunity_id INTEGER NOT NULL,
        service_category_key TEXT NOT NULL,
        vendor_name TEXT,
        vendor_account_id TEXT,
        match_score REAL NOT NULL DEFAULT 0,
        match_reason TEXT,
        access_status TEXT NOT NULL DEFAULT 'suggested',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(opportunity_id, service_category_key, vendor_account_id)
    )
    """,
]


def create_tables() -> None:
    with get_db_connection() as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        conn.commit()


if __name__ == "__main__":
    create_tables()
    print("Database tables created.")
