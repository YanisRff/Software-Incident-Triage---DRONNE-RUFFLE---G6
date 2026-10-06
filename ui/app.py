import os
import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.title("Software Incident Triage")
st.caption("Suggestions require human review. The app does not perform external actions.")
api_url = os.getenv("API_URL", "http://localhost:8000")


def fetch_history():
    """Fetch recent analyses and flatten them into table rows."""
    response = httpx.get(api_url + "/api/history", timeout=15, trust_env=False)
    response.raise_for_status()
    payload = response.json()
    # Accept either a plain list or an object wrapping the list
    items = payload if isinstance(payload, list) else payload.get("items", payload.get("history", []))
    rows = []
    for item in items:
        analysis = item.get("analysis", {})
        row = {}
        if "created_at" in item:
            row["Date"] = item["created_at"]
        row.update(
            {
                "ID": item.get("id", "")[:8],
                "Scenario": item.get("scenario", ""),
                "Provider": item.get("provider", ""),
                "Category": analysis.get("category", ""),
                "Priority": analysis.get("priority", ""),
                "Summary": analysis.get("summary", ""),
                "Next action": analysis.get("next_action", ""),
                "Review": "Yes" if item.get("requires_review") else "No",
            }
        )
        rows.append(row)
    return rows


with st.form("request"):
    subject = st.text_input("Subject", "Cannot reset password")
    text = st.text_area("Request", "The reset link expires immediately after I open it.")
    submitted = st.form_submit_button("Analyze")

if submitted:
    try:
        response = httpx.post(
            api_url + "/api/analyze",
            json={"subject": subject, "text": text},
            timeout=75,
            trust_env=False,
        )
        response.raise_for_status()
        data = response.json()
        analysis = data.get("analysis", {})

        st.divider()
        st.subheader("Analysis")

        # Summary
        st.markdown("**Summary**")
        st.write(analysis.get("summary", "—"))

        # Category & priority side by side
        priority = str(analysis.get("priority", "—"))
        col_category, col_priority = st.columns(2)
        col_category.metric("Category", str(analysis.get("category", "—")).capitalize())
        col_priority.metric(
            "Priority",
            f"{priority.capitalize()}",
        )

        # Next action
        st.markdown("**Next action**")
        st.info(analysis.get("next_action", "—"))

        # Human review flag
        if data.get("requires_review"):
            st.error("Human review required before using this suggestion.")
        else:
            st.success("Review the suggestion before using it.")

        # Technical metadata + raw JSON (collapsed)
        with st.expander("Details"):
            st.write(f"**ID:** `{data.get('id', '—')}`")
            st.write(f"**Scenario:** `{data.get('scenario', '—')}`")
            st.write(f"**Provider:** `{data.get('provider', '—')}`")
            st.json(data)

    except httpx.HTTPStatusError as exc:
        st.error(f"API returned {exc.response.status_code}. Check the input or inference server.")
    except httpx.RequestError:
        st.error("API is unreachable. Check API_URL and the backend process.")

st.divider()
st.subheader("Recent analyses")
try:
    history_rows = fetch_history()
    if history_rows:
        st.dataframe(history_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No analyses yet.")
except httpx.HTTPStatusError as exc:
    st.error(f"History: API returned {exc.response.status_code}.")
except httpx.RequestError:
    st.error("History unavailable: API is unreachable.")