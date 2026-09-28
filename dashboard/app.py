import streamlit as st
import requests
import pandas as pd
import plotly.express as px

API_URL = "http://localhost:8000/api/v1"

st.set_page_config(page_title="AI Governance Dashboard", layout="wide", page_icon="🛡️")

st.title("🛡️ Enterprise AI Governance & Compliance")

# Fetch data functions
@st.cache_data(ttl=5)
def fetch_applications():
    try:
        res = requests.get(f"{API_URL}/applications")
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []

@st.cache_data(ttl=5)
def fetch_assessments(phase: str | None = None):
    try:
        params = {}
        if phase:
            params["phase"] = phase
        res = requests.get(f"{API_URL}/assessments", params=params)
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []

@st.cache_data(ttl=5)
def fetch_linked_assessments(input_assessment_id: str):
    """Fetch all OUTPUT assessments linked to a given INPUT assessment."""
    try:
        res = requests.get(f"{API_URL}/assessments/{input_assessment_id}/linked")
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []
    
@st.cache_data(ttl=5)
def fetch_approvals():
    try:
        res = requests.get(f"{API_URL}/approvals")
        return res.json() if res.status_code == 200 else []
    except:
        return []

@st.cache_data(ttl=5)
def fetch_exceptions():
    try:
        res = requests.get(f"{API_URL}/approvals/exceptions")
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []

@st.cache_data(ttl=5)
def fetch_audit_events():
    try:
        res = requests.get(f"{API_URL}/audit/events?limit=50")
        return res.json() if res.status_code == 200 else []
    except Exception:
        return []

apps = fetch_applications()
approvals = fetch_approvals()
exceptions = fetch_exceptions()
audit_events = fetch_audit_events()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_overview, tab_assessments, tab_interaction, tab_apps, tab_approvals, tab_audit = st.tabs([
    "📊 Overview",
    "📋 Assessments",
    "🔗 Interaction Trace",
    "📱 Applications",
    "✅ Approvals & Exceptions",
    "📜 Audit Logs",
])

with tab_overview:
    st.header("Platform Overview")

    all_assessments = fetch_assessments()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Applications", len(apps))
    
    critical_apps = sum(1 for a in apps if a.get("risk_level") == "CRITICAL")
    col2.metric("Critical Applications", critical_apps)
    
    open_approvals = sum(1 for a in approvals if a.get("status") == "PENDING")
    col3.metric("Pending Approvals", open_approvals)
    
    active_exceptions = sum(1 for e in exceptions if e.get("status") == "ACTIVE")
    col4.metric("Active Exceptions", active_exceptions)

    st.divider()
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Applications by Risk Level")
        if apps:
            df_apps = pd.DataFrame(apps)
            risk_counts = df_apps["risk_level"].fillna("UNKNOWN").value_counts().reset_index()
            risk_counts.columns = ["Risk Level", "Count"]
            color_map = {
                "LOW": "green", "MEDIUM": "yellow",
                "HIGH": "orange", "CRITICAL": "red", "UNKNOWN": "gray",
            }
            fig = px.pie(
                risk_counts, values="Count", names="Risk Level",
                color="Risk Level", color_discrete_map=color_map, hole=0.4,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No applications found.")
            
    with col_chart2:
        st.subheader("Recent Assessments")
        st.subheader("Recent Assessments (all phases)")
        if all_assessments:
            df_ass = pd.DataFrame(all_assessments[:10])
            columns_to_show = [c for c in [
                "assessment_phase", "application_id",
                "overall_risk_score", "risk_level", "decision", "created_at",
            ] if c in df_ass.columns]
            st.dataframe(df_ass[columns_to_show], use_container_width=True)
        else:
            st.info("No assessments found.")

# ── Tab: Assessments (with Phase column + INPUT/OUTPUT filter) ────────────────
with tab_assessments:
    st.header("Governance Assessments")
    col_filter1, col_filter2 = st.columns([2, 3])
    with col_filter1:
        phase_filter = st.selectbox(
            "Filter by Phase",
            options=["All", "INPUT", "OUTPUT"],
            index=0,
            help="INPUT = user prompt audits. OUTPUT = AI response audits.",
        )
    with col_filter2:
        decision_filter = st.multiselect(
            "Filter by Decision",
            options=["ALLOW", "REVIEW", "BLOCK"],
            default=[],
            help="Leave empty to show all decisions.",
        )
    # Fetch with server-side phase filter where possible
    phase_param = None if phase_filter == "All" else phase_filter
    assessments = fetch_assessments(phase=phase_param)
    # Client-side decision filter
    if decision_filter:
        assessments = [a for a in assessments if a.get("decision") in decision_filter]
    if assessments:
        df = pd.DataFrame(assessments)
        # Ensure Phase column is prominent — move it first
        ordered_cols = ["assessment_phase"] + [c for c in df.columns if c != "assessment_phase"]
        df = df[[c for c in ordered_cols if c in df.columns]]
        # Rename for readability
        df = df.rename(columns={"assessment_phase": "Phase"})
        # Color-code Phase column
        def highlight_phase(val):
            if val == "INPUT":
                return "background-color: #1a3a5c; color: #7ec8e3;"
            elif val == "OUTPUT":
                return "background-color: #3a1a4a; color: #d4a8f0;"
            return ""
        display_cols = [c for c in [
            "Phase", "application_id", "overall_risk_score",
            "risk_level", "decision", "status", "created_at",
        ] if c in df.columns]
        st.dataframe(
            df[display_cols].style.map(highlight_phase, subset=["Phase"]),
            use_container_width=True,
        )
        st.caption(f"Showing {len(assessments)} assessment(s)")
    else:
        st.info("No assessments match the current filters.")

# ── Tab: Interaction Trace (INPUT + linked OUTPUTs side-by-side) ──────────────
with tab_interaction:
    st.header("🔗 Interaction Trace Viewer")
    st.markdown(
        "Select an **INPUT** assessment to view its governance result alongside "
        "every **OUTPUT** assessment that was linked to it."
    )
    # Fetch only INPUT assessments for the selector
    input_assessments = fetch_assessments(phase="INPUT")
    if not input_assessments:
        st.info("No INPUT assessments found. Run an input audit first.")
    else:
        # Build a human-readable label for each input assessment
        input_options = {
            f"{a.get('id', '')[:8]}… — {a.get('decision', 'N/A')} — {a.get('created_at', '')[:19]}": a["id"]
            for a in input_assessments
        }
        selected_label = st.selectbox(
            "Select an INPUT assessment",
            options=list(input_options.keys()),
        )
        selected_input_id = input_options[selected_label]
        # Fetch the selected input assessment details
        selected_input = next(
            (a for a in input_assessments if a["id"] == selected_input_id), None
        )
        # Fetch linked OUTPUT assessments
        linked_outputs = fetch_linked_assessments(selected_input_id)
        col_input, col_output = st.columns(2)
        with col_input:
            st.subheader("📥 INPUT Phase")
            if selected_input:
                st.metric("Decision", selected_input.get("decision", "N/A"))
                st.metric("Risk Level", selected_input.get("risk_level", "N/A"))
                st.metric("Risk Score", f"{selected_input.get('overall_risk_score') or 0:.2f}")
                st.caption(f"ID: {selected_input.get('id')}")
                st.caption(f"Audited: {selected_input.get('created_at', '')[:19]}")
                if selected_input.get("evaluated_text_redacted"):
                    st.warning("⚠️ Evaluated text was redacted (PII detected)")
            else:
                st.info("Could not load input assessment details.")
        with col_output:
            st.subheader("📤 OUTPUT Phase")
            if linked_outputs:
                for i, out in enumerate(linked_outputs):
                    with st.expander(
                        f"Output {i+1} — {out.get('decision', 'N/A')} "
                        f"({out.get('created_at', '')[:19]})",
                        expanded=(i == 0),
                    ):
                        st.metric("Decision", out.get("decision", "N/A"))
                        st.metric("Risk Level", out.get("risk_level", "N/A"))
                        st.metric("Risk Score", f"{out.get('overall_risk_score', 0):.2f}")
                        st.caption(f"ID: {out.get('id')}")
                        if out.get("evaluated_text_redacted"):
                            st.warning("⚠️ AI response was redacted (PII detected)")
            else:
                st.info(
                    "No OUTPUT assessments linked to this input yet. "
                    "Submit an output audit with this assessment's ID as input_assessment_id."
                )


# ── Tab: Applications ─────────────────────────────────────────────────────────

with tab_apps:
    st.header("AI Applications Inventory")
    if apps:
        df_apps = pd.DataFrame(apps)
        display_cols = [c for c in [
            "name", "owner", "department", "environment", "risk_level", "status", "created_at",
        ] if c in df_apps.columns]
        st.dataframe(df_apps[display_cols], use_container_width=True)
    else:
        st.info("No applications registered.")
        
with tab_approvals:
    st.header("Approval Workflows")
    col_appr, col_exc = st.columns(2)
    
    with col_appr:
        st.subheader("Pending Approvals")
        pending = [a for a in approvals if a.get("status") == "PENDING"]
        if pending:
            df_pending = pd.DataFrame(pending)
            display_cols = [c for c in [
                "id", "assessment_id", "requested_by", "created_at",
            ] if c in df_pending.columns]
            st.dataframe(df_pending[display_cols], use_container_width=True)
        else:
            st.success("No pending approvals.")
            
    with col_exc:
        st.subheader("Active Exceptions")
        active = [e for e in exceptions if e.get("status") == "ACTIVE"]
        if active:
            df_active = pd.DataFrame(active)
            display_cols = [c for c in [
                "application_id", "policy_id", "reason", "expires_at",
            ] if c in df_active.columns]
            st.dataframe(df_active[display_cols], use_container_width=True)
        else:
            st.info("No active exceptions.")
            
with tab_audit:
    st.header("Audit Events")
    if audit_events:
        df_events = pd.DataFrame(audit_events)
        display_cols = [c for c in [
            "event_type", "actor", "summary", "created_at",
        ] if c in df_events.columns]
        st.dataframe(df_events[display_cols], use_container_width=True)
    else:
        st.info("No audit events found.")

