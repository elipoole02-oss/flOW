from __future__ import annotations

from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.schema import create_tables
from services.opportunity_detail_service import get_opportunity_detail
from services.opportunity_engine import refresh_opportunities
from services.opportunity_workflow import get_opportunity_board, share_opportunity_with_vendors


def main() -> None:
    operator_id = input("Enter operator ID: ").strip()
    create_tables()
    refresh_opportunities(operator_id=operator_id)
    board = get_opportunity_board(operator_id=operator_id)
    if board.empty:
        print(json.dumps({"operator_id": operator_id, "message": "No opportunities found."}, indent=2))
        return

    top = board.iloc[0]
    share_result = share_opportunity_with_vendors(int(top["opportunity_id"]), note="Demo share to suggested vendors")
    detail = get_opportunity_detail(int(top["opportunity_id"]))
    payload = {
        "share_result": share_result,
        "opportunity_detail": detail,
    }
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
