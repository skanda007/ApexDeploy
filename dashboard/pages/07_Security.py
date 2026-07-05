import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================================================
# ApexDeploy Dashboard - Security Page
# Vulnerability analysis visualization and findings drilldown
# =========================================================

import requests
import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard.components import inject_custom_css, render_sidebar, render_metric_card, get_status_badge_html

st.set_page_config(
    page_title="ApexDeploy - Security Scanner",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"

st.title("🛡️ Security Scanner & Vulnerability Analysis")
st.caption("Bandit static analysis, credential leak detection, dependency auditing, and risk scoring.")

# Fetch pipeline runs to gather security data
try:
    runs_res = requests.get(f"{API_URL}/api/pipeline/runs", timeout=2)
    runs = runs_res.json() if runs_res.status_code == 200 else []
except Exception:
    runs = []

# Select a pipeline run to inspect findings
if not runs:
    st.info("No pipeline runs found. Trigger a pipeline to generate security scan results.")
    st.stop()

run_options = {f"{r.get('repo_name', '?')} — {r['id'][:8]} ({r['status']})": r["id"] for r in runs}
selected_label = st.selectbox("Select Pipeline Run", list(run_options.keys()))
selected_run_id = run_options[selected_label]

# Fetch full run details (includes security_findings and agent_results)
try:
    detail_res = requests.get(f"{API_URL}/api/pipeline/runs/{selected_run_id}", timeout=2)
    details = detail_res.json() if detail_res.status_code == 200 else None
except Exception:
    details = None

if not details:
    st.error("Failed to load pipeline details.")
    st.stop()

# Extract security agent result
security_result = None
for ar in details.get("agent_results", []):
    if ar["agent_name"] == "security":
        try:
            security_result = json.loads(ar["result_json"])
        except Exception:
            security_result = ar["result_json"]
        break

findings = details.get("security_findings", [])

# KPI Row
score = 100
if security_result and isinstance(security_result, dict):
    score = security_result.get("security_score", 100)

score_icon = "🟢" if score >= 80 else "🟡" if score >= 50 else "🔴"
bandit_count = len([f for f in findings if f.get("category") == "bandit"])
secret_count = len([f for f in findings if f.get("category") == "secrets"])
dep_count = len([f for f in findings if f.get("category") == "dependencies"])
config_count = len([f for f in findings if f.get("category") == "config"])

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Security Score", f"{score}/100", score_icon, "Overall risk rating")
with c2:
    render_metric_card("Bandit Issues", str(bandit_count), "🔍", "Static analysis")
with c3:
    render_metric_card("Leaked Secrets", str(secret_count), "🔑", "Credential scans")
with c4:
    render_metric_card("Dependency Risks", str(dep_count), "📦", "Package audits")
with c5:
    render_metric_card("Config Issues", str(config_count), "⚙️", "Configuration checks")

st.markdown("---")

# Severity distribution
if findings:
    st.markdown("### 📊 Severity Distribution")
    chart_col, detail_col = st.columns([1, 2])

    with chart_col:
        sev_counts = {}
        for f in findings:
            s = f.get("severity", "info")
            sev_counts[s] = sev_counts.get(s, 0) + 1

        fig = go.Figure(data=[go.Bar(
            x=list(sev_counts.keys()),
            y=list(sev_counts.values()),
            marker_color=[
                '#DC2626' if s == 'critical' else
                '#EF4444' if s == 'high' else
                '#F59E0B' if s == 'medium' else
                '#10B981' if s == 'low' else '#3B82F6'
                for s in sev_counts.keys()
            ]
        )])
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#E2E8F0',
            height=300,
            margin=dict(t=10, b=30, l=40, r=10),
            xaxis_title="Severity", yaxis_title="Count"
        )
        st.plotly_chart(fig, use_container_width=True)

    with detail_col:
        st.markdown("### 🔎 Findings Detail")
        for f in findings:
            sev = f.get("severity", "info").upper()
            cat = f.get("category", "general")
            desc = f.get("description", "No description")
            file_path = f.get("file_path", "—")
            line = f.get("line_number", "—")
            rec = f.get("recommendation", "")
            cwe = f.get("cwe_id", "")

            sev_color = (
                '#DC2626' if sev == 'CRITICAL' else
                '#EF4444' if sev == 'HIGH' else
                '#F59E0B' if sev == 'MEDIUM' else
                '#10B981' if sev == 'LOW' else '#3B82F6'
            )

            st.markdown(f"""
            <div class="glass-card" style="padding: 14px; margin-bottom: 10px; border-left: 4px solid {sev_color};">
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: {sev_color}; font-weight: bold; font-size: 0.85rem;">{sev} — {cat.upper()}</span>
                    <span style="color: #64748B; font-size: 0.75rem;">{cwe or ''}</span>
                </div>
                <div style="margin-top: 6px; font-size: 0.85rem; color: #E2E8F0;">{desc}</div>
                <div style="margin-top: 4px; font-size: 0.75rem; color: #94A3B8;">
                    📁 <code>{file_path}</code> &nbsp;|&nbsp; Line: {line}
                </div>
                {f'<div style="margin-top: 6px; font-size: 0.8rem; color: #818CF8;">💡 {rec}</div>' if rec else ''}
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("No security findings recorded for this pipeline run.")

# Security agent JSON result expandable
if security_result:
    st.markdown("---")
    st.markdown("### 📄 Full Security Agent Report")
    with st.expander("Show raw security scan results"):
        if isinstance(security_result, dict):
            st.json(security_result)
        else:
            st.code(str(security_result))
