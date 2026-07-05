import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================================================
# ApexDeploy Dashboard - Overview Page
# Main overview layout displaying KPI cards, activity feeds, and charts
# =========================================================

import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from dashboard.components import inject_custom_css, render_sidebar, render_metric_card, get_status_badge_html

# Page Configuration
st.set_page_config(
    page_title="ApexDeploy - Overview Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"

st.title("📊 Platform Overview")
st.caption("Real-time telemetry, agent metrics, and pipeline execution reports.")

# Helper to fetch API data
def fetch_data(endpoint: str):
    try:
        res = requests.get(f"{API_URL}{endpoint}", timeout=1.5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

# Load statistics
repos = fetch_data("/api/repositories") or []
runs = fetch_data("/api/pipeline/runs") or []
deployments = fetch_data("/api/deployments") or []

total_repos = len(repos)
total_runs = len(runs)
active_deployments = len([d for d in deployments if d["status"] == "running"])
failed_runs = len([r for r in runs if r["status"] == "failed"])
passed_runs = len([r for r in runs if r["status"] == "passed"])

# Calculate Rollbacks
rollbacks_count = 0
for run in runs:
    try:
        details = fetch_data(f"/api/pipeline/runs/{run['id']}")
        if details:
            for result in details.get("agent_results", []):
                if result["agent_name"] == "rollback" and result["status"] == "completed":
                    rollbacks_count += 1
    except Exception:
        pass

# Display Metric KPI Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    render_metric_card("Repositories", str(total_repos), "📁", f"{len([r for r in repos if r['status'] == 'active'])} Active")
with col2:
    render_metric_card("Pipeline Runs", str(total_runs), "⚡", f"{passed_runs} Passed / {failed_runs} Failed")
with col3:
    render_metric_card("Active Deployments", str(active_deployments), "🐳", "Running locally in Docker")
with col4:
    render_metric_card("Rollbacks Initiated", str(rollbacks_count), "⏪", "Automated system restorations")

# Section: Telemetry Graphs
st.markdown("### 📈 Systems & Quality Telemetry")
graph_col1, graph_col2 = st.columns(2)

with graph_col1:
    st.markdown("#### Pipeline Performance")
    if runs:
        df_runs = pd.DataFrame(runs)
        fig_pie = px.pie(
            df_runs, 
            names='status', 
            hole=0.4,
            color='status',
            color_discrete_map={
                'passed': '#10B981',
                'failed': '#EF4444',
                'running': '#3B82F6',
                'queued': '#64748B',
                'cancelled': '#475569'
            }
        )
        fig_pie.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#E2E8F0',
            height=300,
            margin=dict(t=10, b=10, l=10, r=10)
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No pipeline run data available to show stats.")

with graph_col2:
    st.markdown("#### Security Findings Trend")
    # Gather security findings across latest runs
    finding_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for run in runs[:5]:
        details = fetch_data(f"/api/pipeline/runs/{run['id']}")
        if details:
            for finding in details.get("security_findings", []):
                severity = finding.get("severity", "info").lower()
                if severity in finding_counts:
                    finding_counts[severity] += 1
                    
    df_sec = pd.DataFrame([{"Severity": k.capitalize(), "Findings": v} for k, v in finding_counts.items()])
    fig_bar = px.bar(
        df_sec,
        x="Severity",
        y="Findings",
        color="Severity",
        color_discrete_map={
            'Critical': '#D97706',
            'High': '#EF4444',
            'Medium': '#F59E0B',
            'Low': '#10B981',
            'Info': '#3B82F6'
        }
    )
    fig_bar.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#E2E8F0',
        height=300,
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=False
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# Section: Recent Pipeline Runs
st.markdown("### 🔄 Recent Deployments & Pipeline Logs")
if runs:
    # Build clean interactive dataframe
    data_list = []
    for r in runs[:10]:
        started = r.get("started_at", "N/A")
        if started != "N/A":
            started = started.split(".")[0].replace("T", " ")
        data_list.append({
            "Run ID": r["id"][:8],
            "Repository": r["repo_name"],
            "Trigger": r["trigger"],
            "Started At": started,
            "Duration (s)": round(r["duration_seconds"], 1) if r["duration_seconds"] else None,
            "Status": r["status"]
        })
        
    df_table = pd.DataFrame(data_list)
    # Using streamlit dataframe
    st.dataframe(
        df_table,
        width='stretch',
        column_config={
            "Status": st.column_config.TextColumn(
                "Status",
                help="Pipeline execution status"
            )
        }
    )
else:
    st.info("No deployments registered yet. Navigate to 'Repositories' page to register one!")
