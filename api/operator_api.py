from __future__ import annotations

from flask import Flask, jsonify, request

from services.deal_tracking_service import (
    accept_bid,
    create_proposal_request,
    get_deal_summary,
    get_operator_deals,
    get_opportunity_deal_room,
    submit_vendor_bid,
    update_bid_status,
    update_deal_status,
)
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


@app.get("/operators/<operator_id>/deals")
def list_deals(operator_id: str):
    df = get_operator_deals(operator_id=operator_id)
    return jsonify(df.to_dict(orient="records"))


@app.get("/operators/<operator_id>/deal_summary")
def deal_summary(operator_id: str):
    return jsonify(get_deal_summary(operator_id))


@app.get("/opportunities/<int:opportunity_id>")
def opportunity_detail(opportunity_id: int):
    detail = get_opportunity_detail(opportunity_id)
    detail["deal_room"] = get_opportunity_deal_room(opportunity_id)
    return jsonify(detail)


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


@app.post("/opportunities/<int:opportunity_id>/proposal_request")
def proposal_request(opportunity_id: int):
    payload = request.get_json(force=True) if request.data else {}
    result = create_proposal_request(
        opportunity_id=opportunity_id,
        request_title=payload.get("title"),
        scope=payload.get("scope"),
        requested_by=payload.get("requested_by", "operator"),
        due_date=payload.get("due_date"),
    )
    return jsonify(result)


@app.post("/proposal_requests/<int:request_id>/bid")
def create_bid(request_id: int):
    payload = request.get_json(force=True)
    result = submit_vendor_bid(
        request_id=request_id,
        vendor_name=payload.get("vendor_name"),
        bid_amount=payload.get("bid_amount"),
        estimated_recovered_value=payload.get("estimated_recovered_value"),
        estimated_days_to_complete=payload.get("estimated_days_to_complete"),
        proposal_summary=payload.get("proposal_summary"),
        vendor_account_id=payload.get("vendor_account_id"),
    )
    return jsonify(result)


@app.post("/bids/<int:bid_id>/status")
def change_bid_status(bid_id: int):
    payload = request.get_json(force=True)
    result = update_bid_status(bid_id=bid_id, status=payload.get("status"))
    return jsonify(result)


@app.post("/bids/<int:bid_id>/accept")
def accept_bid_route(bid_id: int):
    payload = request.get_json(force=True) if request.data else {}
    result = accept_bid(bid_id=bid_id, platform_fee_rate=payload.get("platform_fee_rate", 0.08))
    return jsonify(result)


@app.post("/deals/<int:deal_id>/status")
def change_deal_status(deal_id: int):
    payload = request.get_json(force=True)
    result = update_deal_status(deal_id=deal_id, deal_status=payload.get("status"))
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
