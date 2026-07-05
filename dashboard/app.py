# =========================================================
# ApexDeploy Dashboard - Entry Point
# Glassmorphic Dark UI & Core Layout — Landing page
# =========================================================

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
import streamlit as st
import psutil
import pandas as pd
import plotly.graph_objects as go

from dashboard.components import inject_custom_css, render_sidebar, render_metric_card, get_status_badge_html

# Configure page settings
st.set_page_config(
    page_title="ApexDeploy - Autonomous Resilience Engineer",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"


def fetch_data(endpoint: str):
    """Helper to fetch JSON from the backend API."""
    try:
        res = requests.get(f"{API_URL}{endpoint}", timeout=1.5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


# ---- Hero Header ----
st.markdown("""
<div style="text-align: center; padding: 30px 0 20px 0;">
    <h1 style="font-size: 3rem; font-weight: 800; letter-spacing: -0.03em;
               background: linear-gradient(135deg, #818CF8 0%, #6366F1 35%, #4F46E5 70%, #A78BFA 100%);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;
               margin-bottom: 8px;">
        🚀 ApexDeploy
    </h1>
    <p style="font-size: 1.15rem; color: #94A3B8; font-weight: 400;">
        Autonomous Git-to-Cloud Resilience Engineer
    </p>
    <p style="font-size: 0.85rem; color: #64748B; max-width: 700px; margin: 0 auto;">
        AI-powered Multi-Agent DevOps platform that automatically reads repositories,
        reviews code, runs tests, performs security scanning, builds Docker images,
        deploys locally, monitors health, and rolls back failed deployments.
    </p>
</div>
""", unsafe_allow_html=True)

# ---- Quick Stats ----
repos = fetch_data("/api/repositories") or []
runs = fetch_data("/api/pipeline/runs") or []
deployments = fetch_data("/api/deployments") or []

total_repos = len(repos)
total_runs = len(runs)
passed_runs = len([r for r in runs if r["status"] == "passed"])
failed_runs = len([r for r in runs if r["status"] == "failed"])
active_deploys = len([d for d in deployments if d["status"] == "running"])
total_rollbacks = len([d for d in deployments if d["status"] == "rolled_back"])

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    render_metric_card("Repositories", str(total_repos), "📁")
with c2:
    render_metric_card("Pipeline Runs", str(total_runs), "⚡")
with c3:
    render_metric_card("Passed", str(passed_runs), "✅")
with c4:
    render_metric_card("Failed", str(failed_runs), "❌")
with c5:
    render_metric_card("Deployments", str(active_deploys), "🐳")
with c6:
    render_metric_card("Rollbacks", str(total_rollbacks), "⏪")

st.markdown("---")

# ---- Architecture & Quick Actions ----
info_col, action_col = st.columns([2, 1])

with info_col:
    st.markdown("""
    <div class="glass-card">
        <h3 style="color: #818CF8; margin-top: 0;">Multi-Agent Architecture</h3>
        <p style="color: #94A3B8; font-size: 0.9rem;">
            ApexDeploy uses 8 specialized AI agents coordinated by a central orchestrator, 
            powered by Google ADK and Gemini, with MCP tool integrations for filesystem, 
            Git, GitHub, and terminal operations.
        </p>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px;">
            <div style="text-align: center; padding: 12px; background: rgba(15,23,42,0.5); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="font-size: 1.5rem;">📥</div>
                <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">Git Agent</div>
            </div>
            <div style="text-align: center; padding: 12px; background: rgba(15,23,42,0.5); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="font-size: 1.5rem;">🔍</div>
                <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">Review Agent</div>
            </div>
            <div style="text-align: center; padding: 12px; background: rgba(15,23,42,0.5); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="font-size: 1.5rem;">🧪</div>
                <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">Testing Agent</div>
            </div>
            <div style="text-align: center; padding: 12px; background: rgba(15,23,42,0.5); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="font-size: 1.5rem;">🛡️</div>
                <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">Security Agent</div>
            </div>
            <div style="text-align: center; padding: 12px; background: rgba(15,23,42,0.5); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="font-size: 1.5rem;">🐳</div>
                <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">Docker Agent</div>
            </div>
            <div style="text-align: center; padding: 12px; background: rgba(15,23,42,0.5); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="font-size: 1.5rem;">🚀</div>
                <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">Deploy Agent</div>
            </div>
            <div style="text-align: center; padding: 12px; background: rgba(15,23,42,0.5); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="font-size: 1.5rem;">📊</div>
                <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">Monitor Agent</div>
            </div>
            <div style="text-align: center; padding: 12px; background: rgba(15,23,42,0.5); border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="font-size: 1.5rem;">⏪</div>
                <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">Rollback Agent</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with action_col:
    # API status card
    health = fetch_data("/api/health")
    if health:
        st.markdown(f"""
        <div class="glass-card">
            <h4 style="color: #818CF8; margin-top: 0;">API Status</h4>
            <div class="metric-label">Environment</div>
            <div style="color: #E2E8F0; margin-bottom: 8px;">Production-Ready</div>
            <div class="metric-label">Status</div>
            <div>{get_status_badge_html("online")}</div>
            <br/>
            <div class="metric-label">Version</div>
            <div style="color: #E2E8F0;">1.0.0</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="glass-card">
            <h4 style="color: #EF4444; margin-top: 0;">API Offline</h4>
            <p style="color: #94A3B8; font-size: 0.85rem;">
                The FastAPI backend is not responding. Start it with:
            </p>
            <code style="color: #818CF8;">uvicorn src.main:app --reload</code>
        </div>
        """, unsafe_allow_html=True)

    # Quick action buttons
    st.markdown("### Quick Actions")
    if st.button("📁 Manage Repositories", use_container_width=True):
        st.switch_page("pages/02_Repositories.py")
    if st.button("🔄 View Pipeline Runs", use_container_width=True):
        st.switch_page("pages/03_Pipeline.py")
    if st.button("📊 Open Monitoring", use_container_width=True):
        st.switch_page("pages/06_Monitoring.py")

# ---- Recent Activity ----
st.markdown("---")
st.markdown("### 🔄 Recent Pipeline Activity")

if runs:
    data_list = []
    for r in runs[:8]:
        started = (r.get("started_at") or "N/A").split(".")[0].replace("T", " ")
        data_list.append({
            "Run ID": r["id"][:8],
            "Repository": r.get("repo_name", "—"),
            "Trigger": r.get("trigger", "—"),
            "Started At": started,
            "Duration (s)": round(r["duration_seconds"], 1) if r.get("duration_seconds") else "—",
            "Status": r["status"].upper()
        })

    st.dataframe(pd.DataFrame(data_list), use_container_width=True, hide_index=True)
else:
    st.info("No pipeline activity yet. Register a repository and trigger a pipeline to get started!")

# ---- Deployment History Chart ----
if deployments:
    st.markdown("### 📊 Deployment Status History")
    status_groups = {}
    for d in deployments:
        s = d["status"]
        status_groups[s] = status_groups.get(s, 0) + 1

    fig = go.Figure(data=[go.Bar(
        x=list(status_groups.keys()),
        y=list(status_groups.values()),
        marker_color=[
            '#10B981' if s == 'running' else
            '#3B82F6' if s == 'building' else
            '#EF4444' if s == 'failed' else
            '#F59E0B' if s == 'rolled_back' else '#64748B'
            for s in status_groups.keys()
        ],
        text=list(status_groups.values()),
        textposition='outside'
    )])
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#E2E8F0',
        height=280,
        margin=dict(t=10, b=30, l=40, r=10),
        xaxis_title="", yaxis_title="Count"
    )
    st.plotly_chart(fig, use_container_width=True)
