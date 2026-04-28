from __future__ import annotations

from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.schema import create_tables
from services.opportunity_engine import refresh_opportunities
from services.opportunity_workflow import add_opportunity_comment, get_opportunity_board, update_opportunity_status


def main() -> None:
    operator_id = input("Enter operator ID: ").strip()
    create_tables()
    refresh_opportunities(operator_id=operator_id)
    board = get_opportunity_board(operator_id=operator_id)
    if board.empty:
        print(json.dumps({"operator_id": operator_id, "message": "No opportunities found."}, indent=2))
        return

    top = board.iloc[0]
    update_opportunity_status(int(top["opportunity_id"]), "reviewing", changed_by="demo", note="Initial operator review")
    add_opportunity_comment(
        int(top["opportunity_id"]),
        body="Initial review started. Verify downtime cause and whether a workover quote is needed.",
        author_name="flOW Demo",
        author_role="operator",
    )

    refreshed_board = get_opportunity_board(operator_id=operator_id)
    print(
        json.dumps(
            {
                "operator_id": operator_id,
                "top_opportunity_after_demo": refreshed_board.head(1).to_dict(orient="records"),
                "board_preview": refreshed_board.head(10).to_dict(orient="records"),
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
