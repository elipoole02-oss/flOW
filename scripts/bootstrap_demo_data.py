from __future__ import annotations

import argparse
from datetime import date

from database.connection import get_db_connection
from database.schema import create_tables
from services.opportunity_engine import refresh_opportunities


OPERATOR_ID = "A1169"
OPERATOR_NAME = "A1169 Demo Operating"
FIELDS = ["North Fork", "Cedar Ridge", "Blue Mesa"]


def _month_start(year: int, month: int) -> str:
    return date(year, month, 1).isoformat()


def _well_profile(index: int) -> dict:
    field_name = FIELDS[index % len(FIELDS)]
    well_name = f"{field_name.upper().replace(' ', '-')}-{index + 1:03d}"
    base_oil = 520 + index * 18
    base_gas = 820 + index * 24
    return {
        "well_id": 9000 + index,
        "api_number": f"42-999-{9000 + index}",
        "well_serial_num": f"DEMO-{9000 + index}",
        "operator_id": OPERATOR_ID,
        "operator_name": OPERATOR_NAME,
        "well_name": well_name,
        "field_name": field_name,
        "lease_name": f"{field_name} Demo Lease",
        "status": "ACTIVE",
        "lift_type": "rod_pump" if index % 2 == 0 else "gas_lift",
        "first_production_date": "2024-01-01",
        "base_oil": base_oil,
        "base_gas": base_gas,
    }


def _production_curve(index: int, month_idx: int, base: float, metric: str) -> float:
    # Seven healthy months followed by deterministic degradation patterns that trigger
    # underperformance, rapid decline, downtime risk, and optimization opportunities.
    if month_idx < 6:
        return base * (1.0 - month_idx * 0.018)
    pattern = index % 4
    if pattern == 0:
        return base * 0.52
    if pattern == 1:
        return base * 0.68
    if pattern == 2:
        return base * 0.74
    return base * 0.86 if metric == "oil" else base * 0.70


def reset_demo_data() -> None:
    with get_db_connection() as conn:
        demo_wells = [row["well_id"] for row in conn.execute("SELECT well_id FROM wells WHERE operator_id = ?", (OPERATOR_ID,)).fetchall()]
        if demo_wells:
            placeholders = ",".join(["?"] * len(demo_wells))
            conn.execute(f"DELETE FROM production WHERE well_id IN ({placeholders})", demo_wells)
            conn.execute(f"DELETE FROM opportunities WHERE well_id IN ({placeholders})", demo_wells)
        conn.execute("DELETE FROM wells WHERE operator_id = ?", (OPERATOR_ID,))
        conn.execute("DELETE FROM work_permits WHERE operator_id = ?", (OPERATOR_ID,))
        conn.execute("DELETE FROM opportunity_evidence WHERE opportunity_id NOT IN (SELECT opportunity_id FROM opportunities)")
        conn.execute("DELETE FROM opportunity_comments WHERE opportunity_id NOT IN (SELECT opportunity_id FROM opportunities)")
        conn.execute("DELETE FROM opportunity_status_history WHERE opportunity_id NOT IN (SELECT opportunity_id FROM opportunities)")
        conn.execute("DELETE FROM vendor_matches WHERE opportunity_id NOT IN (SELECT opportunity_id FROM opportunities)")
        conn.commit()


def seed_demo_data(well_count: int = 16) -> None:
    months = [_month_start(2025, month) for month in range(1, 9)]
    wells = [_well_profile(index) for index in range(well_count)]

    with get_db_connection() as conn:
        for well in wells:
            conn.execute(
                """
                INSERT OR REPLACE INTO wells (
                    well_id, api_number, well_serial_num, operator_id, operator_name, well_name,
                    field_name, lease_name, status, lift_type, first_production_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    well["well_id"],
                    well["api_number"],
                    well["well_serial_num"],
                    well["operator_id"],
                    well["operator_name"],
                    well["well_name"],
                    well["field_name"],
                    well["lease_name"],
                    well["status"],
                    well["lift_type"],
                    well["first_production_date"],
                ),
            )
            for month_idx, production_date in enumerate(months):
                downtime = 0.0
                if month_idx == 7 and well["well_id"] % 4 == 0:
                    downtime = 10.0
                elif month_idx == 7 and well["well_id"] % 5 == 0:
                    downtime = 6.5
                conn.execute(
                    """
                    INSERT OR REPLACE INTO production (
                        well_id, production_date, oil_bbl, gas_mcf, water_bbl, downtime_hours
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        well["well_id"],
                        production_date,
                        round(_production_curve(well["well_id"], month_idx, well["base_oil"], "oil"), 2),
                        round(_production_curve(well["well_id"], month_idx, well["base_gas"], "gas"), 2),
                        round(120 + (well["well_id"] % 7) * 8 + month_idx * 3, 2),
                        downtime,
                    ),
                )

        for idx, well in enumerate(wells[:6]):
            conn.execute(
                """
                INSERT OR REPLACE INTO work_permits (
                    permit_id, operator_id, operator_name, well_name, field_name,
                    permit_type, application_date, approval_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    7000 + idx,
                    OPERATOR_ID,
                    OPERATOR_NAME,
                    well["well_name"],
                    well["field_name"],
                    "workover" if idx % 2 == 0 else "recompletion",
                    "2025-07-15",
                    "2025-08-01",
                ),
            )
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a deterministic flOW demo database and refresh opportunities.")
    parser.add_argument("--operator", default=OPERATOR_ID, help="Operator id to refresh after seeding. Defaults to A1169.")
    parser.add_argument("--well-count", type=int, default=16, help="Number of deterministic demo wells to seed.")
    parser.add_argument("--no-reset", action="store_true", help="Keep existing A1169 demo rows before seeding.")
    args = parser.parse_args()

    create_tables()
    if not args.no_reset:
        reset_demo_data()
    seed_demo_data(well_count=args.well_count)
    result = refresh_opportunities(operator_id=args.operator)
    print(result)


if __name__ == "__main__":
    main()
