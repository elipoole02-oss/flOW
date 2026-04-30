from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="flOW", page_icon="💧", layout="wide")

DEFAULT_API_BASE = "http://localhost:5000"
STATUSES = ["new", "reviewing", "watchlist", "planned", "in_progress", "resolved", "dismissed"]


@st.cache_data(ttl=15)
def fetch_opportunities(api_base: str, operator_id: str, status: str | None) -> list[dict[str, Any]]:
    params = {}
    if status and status != "all":
        params["status"] = status
    response = requests.get(f"{api_base}/operators/{operator_id}/opportunities", params=params, timeout=15)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=15)
def fetch_detail(api_base: str, opportunity_id: int) -> dict[str, Any]:
    response = requests.get(f"{api_base}/opportunities/{opportunity_id}", timeout=15)
    response.raise_for_status()
    return response.json()


def post_status(api_base: str, opportunity_id: int, status: str, note: str) -> dict[str, Any]:
    payload = {"status": status, "changed_by": "streamlit", "note": note or None}
    response = requests.post(f"{api_base}/opportunities/{opportunity_id}/status", json=payload, timeout=15)
    response.raise_for_status()
    st.cache_data.clear()
    return response.json()


def post_note(api_base: str, opportunity_id: int, body: str) -> dict[str, Any]:
    payload = {"body": body, "author_name": "flOW Operator", "author_role": "operator", "is_internal": True}
    response = requests.post(f"{api_base}/opportunities/{opportunity_id}/note", json=payload, timeout=15)
    response.raise_for_status()
    st.cache_data.clear()
    return response.json()


def post_share(api_base: str, opportunity_id: int, vendor_ids: list[str], note: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"note": note or "Shared from flOW operator dashboard"}
    if vendor_ids:
        payload["vendor_account_ids"] = vendor_ids
    response = requests.post(f"{api_base}/opportunities/{opportunity_id}/share", json=payload, timeout=15)
    response.raise_for_status()
    st.cache_data.clear()
    return response.json()


def money(value: Any) -> str:
    try:
        return f"${float(value):,.0f}"
    except Exception:
        return "$0"


def pct(value: Any) -> str:
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return "0.0%"


def clean_text(value: Any, fallback: str = "Not available") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def build_mailto(to_email: str, subject: str, body: str) -> str:
    return f"mailto:{quote(to_email.strip())}?subject={quote(subject)}&body={quote(body)}"


def format_board(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    desired = [
        "opportunity_id",
        "well_name",
        "field_name",
        "opportunity_type",
        "status",
        "priority_score",
        "estimated_90_day_value",
        "service_category_key",
    ]
    available = [col for col in desired if col in df.columns]
    return df[available].sort_values(["priority_score", "estimated_90_day_value"], ascending=[False, False])


def build_operator_report(operator_id: str, board_df: pd.DataFrame) -> str:
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    if board_df.empty:
        return f"# flOW Operator Opportunity Report\n\nOperator: {operator_id}\nGenerated: {generated_at}\n\nNo opportunities found."

    total_value = float(board_df["estimated_90_day_value"].sum()) if "estimated_90_day_value" in board_df else 0.0
    active = int(board_df[~board_df["status"].isin(["resolved", "dismissed"])].shape[0]) if "status" in board_df else len(board_df)
    top = board_df.head(10).copy()

    lines = [
        "# flOW Operator Opportunity Report",
        "",
        f"Operator: {operator_id}",
        f"Generated: {generated_at}",
        "",
        "## Executive Summary",
        f"flOW found {len(board_df)} ranked opportunities, including {active} active opportunities, representing {money(total_value)} in estimated 90-day recoverable value.",
        "",
        "## Top Opportunities",
        "| Rank | Well | Field | Issue | Status | Priority | 90-Day Value | Service Category |",
        "|---:|---|---|---|---|---:|---:|---|",
    ]
    for idx, row in enumerate(top.to_dict(orient="records"), start=1):
        lines.append(
            "| {rank} | {well} | {field} | {issue} | {status} | {priority:.1f} | {value} | {category} |".format(
                rank=idx,
                well=clean_text(row.get("well_name")),
                field=clean_text(row.get("field_name")),
                issue=clean_text(row.get("opportunity_type")).replace("_", " ").title(),
                status=clean_text(row.get("status")),
                priority=float(row.get("priority_score", 0) or 0),
                value=money(row.get("estimated_90_day_value", 0)),
                category=clean_text(row.get("service_category_key")).replace("_", " ").title(),
            )
        )
    lines.extend([
        "",
        "## Recommended Next Steps",
        "First, review the top five opportunities and move confirmed candidates to `planned`. Next, share validated workover or maintenance candidates with matched vendors. Finally, use status history and notes to track recovered-value decisions.",
    ])
    return "\n".join(lines)


def build_opportunity_report(detail: dict[str, Any]) -> str:
    opportunity = detail.get("opportunity", {})
    evidence = detail.get("evidence", [])
    vendors = detail.get("vendor_matches", [])
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    title = clean_text(opportunity.get("title"), f"Opportunity {opportunity.get('opportunity_id', '')}")
    lines = [
        f"# {title}",
        "",
        f"Generated: {generated_at}",
        f"Well: {clean_text(opportunity.get('well_name'))}",
        f"Field: {clean_text(opportunity.get('field_name'))}",
        f"Status: {clean_text(opportunity.get('status'))}",
        "",
        "## Business Case",
        f"Estimated 90-day recoverable value: **{money(opportunity.get('estimated_90_day_value', 0))}**",
        f"Priority score: **{float(opportunity.get('priority_score', 0) or 0):.1f}**",
        f"Confidence score: **{float(opportunity.get('confidence_score', 0) or 0):.1f}**",
        "",
        "## Summary",
        clean_text(opportunity.get("summary")),
        "",
        "## Recommended Action",
        clean_text(opportunity.get("recommended_action")),
        "",
        "## Evidence",
    ]

    if evidence:
        for item in evidence:
            value = item.get("value_text") or item.get("value_number")
            unit = f" {item.get('unit')}" if item.get("unit") else ""
            lines.append(f"- {clean_text(item.get('label'))}: {clean_text(value)}{unit}")
    else:
        lines.append("No evidence rows available.")

    lines.extend(["", "## Suggested Vendors"])
    if vendors:
        for vendor in vendors:
            lines.append(
                f"- {clean_text(vendor.get('vendor_name'))} ({clean_text(vendor.get('service_category_key')).replace('_', ' ').title()}) — match score {float(vendor.get('match_score', 0) or 0):.1f}; status {clean_text(vendor.get('access_status'))}"
            )
    else:
        lines.append("No vendor matches available.")

    lines.extend([
        "",
        "## Operator Decision Log",
        "Use flOW notes and status history to track whether this opportunity is reviewed, planned, shared, resolved, or dismissed.",
    ])
    return "\n".join(lines)


def build_email_body(report: str) -> str:
    return (
        "Here is the flOW opportunity report for review.\n\n"
        "Key details are included below. Please review the recommended action and reply with next steps.\n\n"
        f"{report}"
    )


def show_metric_cards(board_df: pd.DataFrame) -> None:
    total = len(board_df)
    value = float(board_df["estimated_90_day_value"].sum()) if not board_df.empty and "estimated_90_day_value" in board_df else 0.0
    top5 = float(board_df.head(5)["estimated_90_day_value"].sum()) if not board_df.empty and "estimated_90_day_value" in board_df else 0.0
    active = int(board_df[~board_df["status"].isin(["resolved", "dismissed"])].shape[0]) if not board_df.empty and "status" in board_df else 0
    high_value = int(board_df[board_df["estimated_90_day_value"] >= 50000].shape[0]) if not board_df.empty and "estimated_90_day_value" in board_df else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Recoverable 90-Day Value", money(value))
    c2.metric("Top 5 Value", money(top5))
    c3.metric("Active Opportunities", active)
    c4.metric("High-Value Alerts", high_value)


def render_detail(api_base: str, opportunity_id: int) -> None:
    try:
        detail = fetch_detail(api_base, opportunity_id)
    except Exception as exc:
        st.error(f"Could not load opportunity detail: {exc}")
        return

    opportunity = detail.get("opportunity", {})
    evidence = pd.DataFrame(detail.get("evidence", []))
    comments = pd.DataFrame(detail.get("comments", []))
    vendor_matches = pd.DataFrame(detail.get("vendor_matches", []))
    history = pd.DataFrame(detail.get("status_history", []))
    timeline = pd.DataFrame(detail.get("timeline", []))
    opportunity_report = build_opportunity_report(detail)

    st.subheader(opportunity.get("title", f"Opportunity {opportunity_id}"))
    st.caption(opportunity.get("summary", "No summary available."))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", opportunity.get("status", "unknown"))
    c2.metric("Priority", f"{float(opportunity.get('priority_score', 0) or 0):.1f}")
    c3.metric("Confidence", f"{float(opportunity.get('confidence_score', 0) or 0):.1f}")
    c4.metric("90-Day Value", money(opportunity.get("estimated_90_day_value", 0)))

    if float(opportunity.get("estimated_90_day_value", 0) or 0) >= 50000:
        st.error("High-value opportunity: review this candidate before lower-value work.")

    st.markdown("### Recommended Action")
    st.info(opportunity.get("recommended_action") or "No recommendation available.")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Evidence", "Workflow", "Vendors", "Timeline", "Report & Email"])

    with tab1:
        if evidence.empty:
            st.warning("No evidence rows found.")
        else:
            show_cols = [col for col in ["label", "value_text", "value_number", "unit", "evidence_type"] if col in evidence.columns]
            st.dataframe(evidence[show_cols], use_container_width=True, hide_index=True)

    with tab2:
        left, right = st.columns([1, 1])
        with left:
            st.markdown("#### Change Status")
            current = opportunity.get("status", "new")
            idx = STATUSES.index(current) if current in STATUSES else 0
            new_status = st.selectbox("New status", STATUSES, index=idx, key=f"status-{opportunity_id}")
            status_note = st.text_area("Status note", key=f"status-note-{opportunity_id}")
            if st.button("Update status", key=f"update-status-{opportunity_id}"):
                try:
                    post_status(api_base, opportunity_id, new_status, status_note)
                    st.success("Status updated.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not update status: {exc}")
        with right:
            st.markdown("#### Add Internal Note")
            note_body = st.text_area("Note", key=f"note-{opportunity_id}")
            if st.button("Add note", key=f"add-note-{opportunity_id}"):
                if not note_body.strip():
                    st.warning("Write a note first.")
                else:
                    try:
                        post_note(api_base, opportunity_id, note_body)
                        st.success("Note added.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not add note: {exc}")

        st.markdown("#### Recent Notes")
        if comments.empty:
            st.caption("No comments yet.")
        else:
            for _, row in comments.head(8).iterrows():
                st.markdown(f"**{row.get('author_name') or 'operator'}** · {row.get('created_at')}")
                st.write(row.get("body"))
                st.divider()

        st.markdown("#### Status History")
        if history.empty:
            st.caption("No status history yet.")
        else:
            st.dataframe(history, use_container_width=True, hide_index=True)

    with tab3:
        st.markdown("### Vendor Opportunity")
        st.success(f"This opportunity represents about {money(opportunity.get('estimated_90_day_value', 0))} in estimated 90-day recoverable value. Vendors can use the report to propose a specific field response.")
        if vendor_matches.empty:
            st.warning("No vendor matches found.")
        else:
            vendor_cols = [col for col in ["vendor_name", "service_category_key", "match_score", "access_status", "match_reason", "vendor_account_id"] if col in vendor_matches.columns]
            st.dataframe(vendor_matches[vendor_cols], use_container_width=True, hide_index=True)
            vendor_options = vendor_matches.get("vendor_account_id", pd.Series(dtype=str)).dropna().astype(str).tolist()
            selected_vendors = st.multiselect("Share with specific vendors", vendor_options, key=f"vendors-{opportunity_id}")
            share_note = st.text_area("Share note", value="Please review this opportunity and provide recommended next steps.", key=f"share-note-{opportunity_id}")
            if st.button("Share opportunity", key=f"share-{opportunity_id}"):
                try:
                    result = post_share(api_base, opportunity_id, selected_vendors, share_note)
                    st.success(f"Shared with {result.get('shared_vendor_count', 0)} vendor matches.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not share opportunity: {exc}")

    with tab4:
        if timeline.empty:
            st.caption("No timeline events found.")
        else:
            st.dataframe(timeline, use_container_width=True, hide_index=True)

    with tab5:
        st.markdown("### One-Click Report")
        st.download_button(
            "Download Opportunity Report",
            data=opportunity_report,
            file_name=f"flow_opportunity_{opportunity_id}_report.md",
            mime="text/markdown",
        )
        with st.expander("Preview report", expanded=True):
            st.markdown(opportunity_report)

        st.markdown("### Email This Report")
        to_email = st.text_input("Recipient email", key=f"email-to-{opportunity_id}")
        email_subject = f"flOW opportunity report: {clean_text(opportunity.get('well_name'))}"
        email_body = build_email_body(opportunity_report)
        if to_email.strip():
            st.markdown(f"[Open email draft]({build_mailto(to_email, email_subject, email_body)})")
        else:
            st.caption("Enter an email address to create a pre-filled email draft.")


def main() -> None:
    st.title("flOW")
    st.caption("Find missed production revenue, rank it, document it, and route it to action.")

    with st.sidebar:
        st.header("Connection")
        api_base = st.text_input("API base", DEFAULT_API_BASE)
        operator_id = st.text_input("Operator ID", "A1169")
        status = st.selectbox("Status filter", ["all", *STATUSES])
        st.markdown("### Local run")
        st.code("python scripts/bootstrap_demo_data.py\npython api/operator_api.py\nstreamlit run main.py", language="bash")

    try:
        rows = fetch_opportunities(api_base, operator_id, status)
    except Exception as exc:
        st.error(f"Could not reach flOW API at {api_base}: {exc}")
        st.stop()

    board_df = format_board(rows)
    show_metric_cards(board_df)

    if not board_df.empty:
        high_value_df = board_df[board_df["estimated_90_day_value"] >= 50000]
        if not high_value_df.empty:
            st.warning(f"{len(high_value_df)} high-value opportunities exceed $50k in estimated 90-day recoverable value.")

    board_tab, dossier_tab, report_tab = st.tabs(["Opportunity Board", "Dossier", "Operator Report"])

    with board_tab:
        st.subheader("Opportunity Board")
        if board_df.empty:
            st.warning("No opportunities found. Run the demo bootstrap or refresh opportunities first.")
        else:
            st.dataframe(
                board_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "opportunity_id": st.column_config.NumberColumn("ID", format="%d"),
                    "priority_score": st.column_config.ProgressColumn("Priority", min_value=0, max_value=100),
                    "estimated_90_day_value": st.column_config.NumberColumn("90-Day Value", format="$%d"),
                },
            )
            selected_id = st.selectbox(
                "Open opportunity",
                board_df["opportunity_id"].astype(int).tolist(),
                format_func=lambda oid: f"#{oid} · " + str(board_df.loc[board_df["opportunity_id"] == oid, "well_name"].iloc[0]),
            )
            if st.button("Open dossier"):
                st.session_state["selected_opportunity_id"] = int(selected_id)
                st.rerun()

    with dossier_tab:
        st.subheader("Opportunity Dossier")
        default_id = int(board_df["opportunity_id"].iloc[0]) if not board_df.empty else 1
        opportunity_id = int(st.session_state.get("selected_opportunity_id", default_id))
        if not board_df.empty:
            opportunity_id = st.selectbox(
                "Dossier opportunity",
                board_df["opportunity_id"].astype(int).tolist(),
                index=board_df["opportunity_id"].astype(int).tolist().index(opportunity_id) if opportunity_id in board_df["opportunity_id"].astype(int).tolist() else 0,
                format_func=lambda oid: f"#{oid} · " + str(board_df.loc[board_df["opportunity_id"] == oid, "well_name"].iloc[0]),
                key="dossier-select",
            )
        render_detail(api_base, int(opportunity_id))

    with report_tab:
        st.subheader("Operator-Level Report")
        operator_report = build_operator_report(operator_id, board_df)
        st.download_button(
            "Download Operator Report",
            data=operator_report,
            file_name=f"flow_operator_{operator_id}_report.md",
            mime="text/markdown",
        )
        email_to = st.text_input("Email report to", key="operator-email-to")
        if email_to.strip():
            st.markdown(f"[Open email draft]({build_mailto(email_to, f'flOW operator report: {operator_id}', build_email_body(operator_report))})")
        with st.expander("Preview operator report", expanded=True):
            st.markdown(operator_report)


if __name__ == "__main__":
    main()
