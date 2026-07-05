import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================================================
# ApexDeploy Dashboard - Reports Page
# Aggregated reports viewer for all agent outputs
# =========================================================

import requests
import streamlit as st
import json

from dashboard.components import inject_custom_css, render_sidebar, get_status_badge_html

st.set_page_config(
    page_title="ApexDeploy - Reports",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"

st.title("📋 Execution Reports")
st.caption("Consolidated pipeline reports — code review, testing, security, deployment, monitoring, and rollback artifacts.")

# Fetch pipeline runs
try:
    runs_res = requests.get(f"{API_URL}/api/pipeline/runs", timeout=2)
    runs = runs_res.json() if runs_res.status_code == 200 else []
except Exception:
    runs = []

if not runs:
    st.info("No pipeline runs found. Trigger a pipeline to generate reports.")
    st.stop()

run_options = {f"{r.get('repo_name', '?')} — {r['id'][:8]} ({r['status']})": r["id"] for r in runs}
selected_label = st.selectbox("Select Pipeline Run", list(run_options.keys()))
selected_run_id = run_options[selected_label]

# Fetch consolidated report via API
try:
    report_res = requests.get(f"{API_URL}/api/reports/run/{selected_run_id}", timeout=2)
    reports = report_res.json() if report_res.status_code == 200 else {}
except Exception:
    reports = {}

if not reports:
    st.warning("No agent reports found for this run.")
    st.stop()

# Report type icons and labels mapping
agent_icons = {
    "git": ("📥", "Git Agent Report"),
    "code_review": ("🔍", "Code Review Report"),
    "testing": ("🧪", "Testing Report"),
    "security": ("🛡️", "Security Report"),
    "docker": ("🐳", "Docker Build Report"),
    "deployment": ("🚀", "Deployment Report"),
    "monitoring": ("📊", "Monitoring Report"),
    "rollback": ("⏪", "Rollback Report"),
}

# Render each report in expandable glassmorphic sections
for agent_name, report_data in reports.items():
    icon, label = agent_icons.get(agent_name, ("📄", agent_name.replace("_", " ").title()))
    status_text = report_data.get("status", "unknown")
    duration = report_data.get("duration_seconds", 0) or 0
    created = (report_data.get("created_at") or "N/A").split(".")[0].replace("T", " ")
    artifact_path = report_data.get("artifact_path")

    # Header card
    st.markdown(f"""
    <div class="glass-card" style="padding: 16px; margin-bottom: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="font-size: 1.1rem; font-weight: bold; color: #818CF8;">{icon} {label}</span>
                <br/>
                <span style="font-size: 0.8rem; color: #94A3B8;">
                    ⏱️ {round(duration, 2)}s &nbsp;|&nbsp; 📅 {created}
                    {f' &nbsp;|&nbsp; 📁 <code>{artifact_path}</code>' if artifact_path else ''}
                </span>
            </div>
            <div>{get_status_badge_html(status_text)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Expandable result section
    with st.expander(f"📄 View {label} Details"):
        result_raw = report_data.get("result")
        if result_raw:
            try:
                parsed = json.loads(result_raw)
                # Pretty-print key sections
                if isinstance(parsed, dict):
                    # Summary key highlight
                    for key in ["status", "success", "test_status", "security_score",
                                "health_score", "rollback_status"]:
                        if key in parsed:
                            val = parsed[key]
                            st.write(f"**{key}**: `{val}`")

                    st.json(parsed)
                else:
                    st.json(parsed)
            except Exception:
                st.code(str(result_raw))
        else:
            st.info("No result data available for this agent.")
