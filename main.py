import streamlit as st
import requests

st.set_page_config(page_title="flOW", layout="wide")

st.title("flOW Operator Dashboard")

API_BASE = "http://localhost:5000"
operator_id = st.text_input("Operator ID", "A1169")

if st.button("Load Opportunities"):
    try:
        resp = requests.get(f"{API_BASE}/operators/{operator_id}/opportunities")
        data = resp.json()
        st.success(f"Loaded {len(data)} opportunities")
        st.dataframe(data)
    except Exception as e:
        st.error(str(e))

st.markdown("---")
st.subheader("Opportunity Detail")
opp_id = st.number_input("Opportunity ID", min_value=1, step=1)

if st.button("Load Detail"):
    try:
        resp = requests.get(f"{API_BASE}/opportunities/{opp_id}")
        data = resp.json()
        st.json(data)
    except Exception as e:
        st.error(str(e))
