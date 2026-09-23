import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

API_URL = "http://localhost:8000/api/v1"

st.set_page_config(page_title="AI Governance Dashboard", layout="wide", page_icon="🛡️")

st.title("🛡️ Enterprise AI Governance & Compliance")

# Fetch data functions
@st.cache_data(ttl=5)
def fetch_applications():
    try:
        res = requests.get(f"{API_URL}/applications")
        return res.json() if res.status_code == 200 else []
    except:
        return []

@st.cache_data(ttl=5)
def fetch_assessments():
    try:
        res = requests.get(f"{API_URL}/assessments")
        return res.json() if res.status_code == 200 else []
    except:
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
    except:
        return []

@st.cache_data(ttl=5)
def fetch_audit_events():
    try:
        res = requests.get(f"{API_URL}/audit/events?limit=50")
        return res.json() if res.status_code == 200 else []
    except:
        return []

apps = fetch_applications()
assessments = fetch_assessments()
approvals = fetch_approvals()
exceptions = fetch_exceptions()
audit_events = fetch_audit_events()

# Layout
tab_overview, tab_apps, tab_approvals, tab_audit = st.tabs(["📊 Overview", "📱 Applications", "✅ Approvals & Exceptions", "📜 Audit Logs"])

with tab_overview:
    st.header("Platform Overview")
    
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
            risk_counts = df_apps['risk_level'].fillna("UNKNOWN").value_counts().reset_index()
            risk_counts.columns = ['Risk Level', 'Count']
            
            color_map = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "orange", "CRITICAL": "red", "UNKNOWN": "gray"}
            fig = px.pie(risk_counts, values='Count', names='Risk Level', color='Risk Level', 
                         color_discrete_map=color_map, hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No applications found.")
            
    with col_chart2:
        st.subheader("Recent Assessments")
        if assessments:
            df_ass = pd.DataFrame(assessments[:10])
            st.dataframe(df_ass[['application_id', 'assessment_type', 'overall_risk_score', 'risk_level', 'decision', 'created_at']], use_container_width=True)
        else:
            st.info("No assessments found.")

with tab_apps:
    st.header("AI Applications Inventory")
    if apps:
        df_apps = pd.DataFrame(apps)
        st.dataframe(df_apps[['name', 'owner', 'department', 'environment', 'risk_level', 'status', 'created_at']], use_container_width=True)
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
            st.dataframe(df_pending[['id', 'assessment_id', 'requested_by', 'created_at']], use_container_width=True)
        else:
            st.success("No pending approvals.")
            
    with col_exc:
        st.subheader("Active Exceptions")
        active = [e for e in exceptions if e.get("status") == "ACTIVE"]
        if active:
            df_active = pd.DataFrame(active)
            st.dataframe(df_active[['application_id', 'policy_id', 'reason', 'expires_at']], use_container_width=True)
        else:
            st.info("No active exceptions.")
            
with tab_audit:
    st.header("Audit Events")
    if audit_events:
        df_events = pd.DataFrame(audit_events)
        st.dataframe(df_events[['event_type', 'actor', 'summary', 'created_at']], use_container_width=True)
    else:
        st.info("No audit events found.")

