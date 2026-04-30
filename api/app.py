from __future__ import annotations

from flask import Flask, jsonify, request

from services.opportunity_detail_service import get_opportunity_detail
from services.opportunity_workflow import (
    add_opportunity_comment,
    get_opportunity_board,
    share_opportunity_with_vendors,
    update_opportunity_status,
)


app = Flask(__name__)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/operators/<operator_id>/opportunities")
def list_opportunities(operator_id: str):
    status = request.args.get("status")
    df = get_opportunity_board(operator_id=operator_id, status=status)
    return jsonify(df.to_dict(orient="records"))


@app.get("/opportunities/<int:opportunity_id>")
def opportunity_detail(opportunity_id: int):
    return jsonify(get_opportunity_detail(opportunity_id))


@app.post("/opportunities/<int:opportunity_id>/status")
def change_status(opportunity_id: int):
    payload = request.get_json(force=True)
    result = update_opportunity_status(
        opportunity_id=opportunity_id,
        new_status=payload.get("status"),
        changed_by=payload.get("changed_by", "api"),
        note=payload.get("note"),
    )
    return jsonify(result)


@app.post("/opportunities/<int:opportunity_id>/note")
def add_note(opportunity_id: int):
    payload = request.get_json(force=True)
    result = add_opportunity_comment(
        opportunity_id=opportunity_id,
        body=payload.get("body"),
        author_name=payload.get("author_name", "operator"),
        author_role=payload.get("author_role", "operator"),
        is_internal=payload.get("is_internal", True),
    )
    return jsonify(result)


@app.post("/opportunities/<int:opportunity_id>/share")
def share(opportunity_id: int):
    payload = request.get_json(force=True) if request.data else {}
    result = share_opportunity_with_vendors(
        opportunity_id=opportunity_id,
        vendor_account_ids=payload.get("vendor_account_ids"),
        note=payload.get("note"),
    )
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
