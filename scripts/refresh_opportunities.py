from __future__ import annotations

from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.schema import create_tables
from services.opportunity_engine import refresh_opportunities
from services.opportunity_workflow import get_opportunity_board


def main() -> None:
    operator_id = input("Enter operator ID: ").strip()
    field_name = input("Field name (optional): ").strip() or None
    create_tables()
    result = refresh_opportunities(operator_id=operator_id, field_name=field_name)
    board = get_opportunity_board(operator_id=operator_id)
    payload = {
        "refresh_result": result,
        "top_opportunities": board.head(10).to_dict(orient="records"),
    }
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
